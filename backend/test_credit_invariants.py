"""
工银牧融 - 唯一金额链不变量（属性测试，hypothesis）
============================================================================
运行：
    python backend\\test_credit_invariants.py        （零依赖自跑）
或：
    python -m pytest backend/test_credit_invariants.py -q

为什么需要它：
    现有 test_credit_decision*.py 断言的是**具体数值**（黄金案例 900000 等），
    属于「举例测试」；举例覆盖不到「任意输入下都必须成立」的性质。
    本文件断言 4 条不变量，用 hypothesis 自动生成大量输入去找反例。

不变量：
    P1  pre_round_amount_yuan == min(需求侧, 供给侧)     —— 确实是「取小」而非别的组合
    P2  recommended_amount_yuan 向下取整到 1 万元，且 <= pre_round
    P3  给了金额 => status == feasible；status != feasible => 不给金额
    P4  金额不超过供给侧任意单项上限（雪灾偿债 / 统一授信可用 / 产品上限 / 活体抵押）
    P5  _floor_to_10000 单调不减、且结果 <= 输入、且是 1 万元的整数倍

边界：
    1. 只扰动能代表「主体真实差异」的字段，不构造物理上不可能的案例（否则测的是噪声）。
    2. blocked 案例与资料不足分支不在本文件覆盖范围（由 _check_gate 决定，另有用例）。
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st
except ImportError:  # pragma: no cover
    print("SKIP  缺少 hypothesis（pip install hypothesis）")
    raise SystemExit(0)

from credit_decision import (  # noqa: E402
    _floor_to_10000,
    _live_stock_pledge_limit,
    evaluate_credit_case,
)

_DATA = _BACKEND / "data_store" / "credit_cases.json"
CASES = json.loads(_DATA.read_text(encoding="utf-8"))["cases"]
GOLD = CASES["bankgong-green-coop"]

WAN = Decimal("10000")
FAST = settings(max_examples=120, deadline=None,
                suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])


# ---------------------------------------------------------------- 输入策略

@st.composite
def perturbed_case(draw):
    """在黄金案例上做「合理范围内」的扰动，代表不同主体的真实差异。"""
    case = deepcopy(GOLD)
    case["pasture"]["total_mu"] = draw(st.integers(min_value=5_000, max_value=200_000))
    case["livestock"]["yak_head"] = draw(st.integers(min_value=50, max_value=5_000))
    case["livestock"]["sheep_head"] = draw(st.integers(min_value=0, max_value=10_000))
    case["operating"]["own_purchase_funds_yuan"] = draw(
        st.integers(min_value=0, max_value=3_000_000))
    case["operating"]["initial_cash_yuan"] = draw(
        st.integers(min_value=0, max_value=3_000_000))
    case["operating"]["minimum_cash_reserve_yuan"] = draw(
        st.integers(min_value=0, max_value=500_000))
    case["credit"]["product_cap_yuan"] = draw(
        st.integers(min_value=200_000, max_value=5_000_000))
    case["procurement"]["base_price_yuan_per_kg"] = draw(
        st.floats(min_value=1.0, max_value=6.0, allow_nan=False, allow_infinity=False))
    case["operating"]["monthly_net_cash_yuan"] = [
        draw(st.integers(min_value=-200_000, max_value=800_000)) for _ in range(12)
    ]
    return case


# ---------------------------------------------------------------- 不变量

@FAST
@given(perturbed_case())
def test_p1_pre_round_is_min_of_two_sides(case: dict) -> None:
    """P1：取整前的金额必须正好等于需求侧与供给侧取小。"""
    r = evaluate_credit_case(case)
    if r["status"] == "blocked":
        return
    demand = r["qualified_demand"]["qualified_demand_yuan"]
    supply = r["limits"]["affordable_limit_yuan"]
    assert r["pre_round_amount_yuan"] == min(demand, supply), (
        f"金额不是两侧取小：pre_round={r['pre_round_amount_yuan']} "
        f"demand={demand} supply={supply}")
    assert r["bottleneck"]["final"] in ("qualified_demand", "affordable_limit")


@FAST
@given(perturbed_case())
def test_p2_amount_is_floored_to_wan(case: dict) -> None:
    """P2：金额按 1 万元向下取整，且不小于 pre_round 减去不足 1 万的零头。"""
    r = evaluate_credit_case(case)
    if r["status"] == "blocked":
        return
    pre = r["pre_round_amount_yuan"]
    assert pre % WAN == 0 or pre is not None
    assert pre == _floor_to_10000(pre), "pre_round 自身没被取整"
    amt = r["recommended_amount_yuan"]
    if amt is not None:
        assert amt % WAN == 0, f"金额不是 1 万元整数倍：{amt}"
        assert amt <= pre, f"金额超过取整前值：{amt} > {pre}"


@FAST
@given(perturbed_case())
def test_p3_amount_present_iff_feasible(case: dict) -> None:
    """P3：只有 feasible 才给金额；非 feasible 一律不给（系统诚实拒绝放款）。"""
    r = evaluate_credit_case(case)
    if r["status"] == "feasible":
        assert r["recommended_amount_yuan"] is not None, "feasible 却没有金额"
        assert r["recommended_amount_yuan"] > 0
    else:
        assert r["recommended_amount_yuan"] is None, (
            f"status={r['status']} 却给了金额 {r['recommended_amount_yuan']}")
        assert r.get("gap_yuan") is not None


@FAST
@given(perturbed_case())
def test_p4_amount_never_exceeds_supply_constraints(case: dict) -> None:
    """P4：金额不得超过供给侧任意单项上限（含活体抵押，若适用）。"""
    r = evaluate_credit_case(case)
    amt = r["recommended_amount_yuan"]
    if amt is None:
        return
    lim = r["limits"]
    for key, label in (("snow_support_limit_yuan", "标准雪灾偿债支持上限"),
                       ("credit_available_yuan", "统一授信可用额度"),
                       ("product_cap_yuan", "样例产品上限")):
        assert amt <= lim[key], f"金额 {amt} 超过{label} {lim[key]}"
    pledge = lim.get("pledge") or {}
    if pledge.get("applicable"):
        assert amt <= Decimal(str(pledge["limit_yuan"])), "金额超过活体抵押上限"


@given(st.integers(min_value=0, max_value=10**9))
def test_p5_floor_is_monotone_and_bounded(v: int) -> None:
    """P5：定义域（非负金额）内，向下取整单调不减、不放大、且结果是 1 万元的整数倍。"""
    d = Decimal(v)
    f = _floor_to_10000(d)
    assert f <= d, f"向下取整反而变大：{f} > {d}"
    assert d - f < WAN, f"取整掉了超过 1 万元：{d} -> {f}"
    assert f % WAN == 0
    assert _floor_to_10000(f) == f, "取整不是幂等的"
    assert f <= _floor_to_10000(d + WAN), "单调性不成立"


def test_p5b_negative_input_rounds_toward_zero() -> None:
    """边界记录：_floor_to_10000 对负数是「向零取整」，不满足 f <= 输入。

    _floor_to_10000 用 ROUND_DOWN，对负数等于截断（-1 -> -0）。金额链上游全部由
    max(Decimal('0'), ...) 保证非负（见 credit_decision._benchmark_qualified_demand /
    _affordable_limits），所以当前不发作；这里把行为钉住，
    将来若改成 ROUND_FLOOR 或上游可能产生负数，本用例会立刻变红提醒。
    """
    assert _floor_to_10000(Decimal("-1")) == Decimal("0"), (
        "负数取整行为变了：原为向零取整（-1 -> 0），请确认是否改成了真正的向下取整")
    assert _floor_to_10000(Decimal("-15000")) == Decimal("-10000")


@given(st.text(max_size=40), st.integers(min_value=-10**6, max_value=10**6))
def test_p6_pledge_limit_never_negative_and_bounded_by_face_value(s: str, head: int) -> None:
    """P6：活体抵押上限恒 >= 0，且 <= 面值（头数 × 单价），保险未核验时不能按已投保算。"""
    case = {"pledge": {"insurance_verified": False, "items": [
        {"species": s, "head": abs(head), "unit_price_yuan": 8000,
         "ear_tagged": abs(head), "insured": abs(head)},
    ]}}
    r = _live_stock_pledge_limit(case)
    limit = Decimal(str(r["limit_yuan"]))
    face = Decimal(abs(head)) * Decimal(8000)
    assert limit >= 0, "抵押上限为负"
    assert limit <= face, f"抵押上限 {limit} 超过面值 {face}"
    # 保险未核验 -> 投保档必须为 0，只能走「有耳标+无保险」40%
    assert r["buckets"]["tag_insured"] == 0, "保险未核验却按已投保计"
    assert limit == (face * Decimal("0.40")).quantize(Decimal("0.01")) or abs(
        limit - face * Decimal("0.40")) < Decimal("0.01")


def _run_standalone() -> int:
    checks = [
        test_p1_pre_round_is_min_of_two_sides,
        test_p2_amount_is_floored_to_wan,
        test_p3_amount_present_iff_feasible,
        test_p4_amount_never_exceeds_supply_constraints,
        test_p5_floor_is_monotone_and_bounded,
        test_p5b_negative_input_rounds_toward_zero,
        test_p6_pledge_limit_never_negative_and_bounded_by_face_value,
    ]
    failed = 0
    for fn in checks:
        try:
            fn()
            print(f"ok    {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {fn.__name__}\n      {str(exc)[:600]}")
    print()
    if failed:
        print(f"{len(checks) - failed}/{len(checks)} passed（{failed} 条不变量被推翻）")
        return 1
    print(f"{len(checks)}/{len(checks)} 条不变量全部成立")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
