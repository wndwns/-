"""
工银牧融 - 活体抵押上限与两级瓶颈回归检查（方案 D7 / D8 / D9）
============================================================================
运行：
    python backend\\test_credit_decision_pledge.py
或：
    python -m pytest backend/test_credit_decision_pledge.py -q

覆盖：
  - 抵押折扣四档计算（有耳标/无耳标 × 有保险/无保险）
  - 保险未核验时，投保档不计入（按未投保处理）
  - 数据缺失时 applicable=False 且**不参与 min 比较**（不得按 0 处理）
  - 抵押上限足够高时不成为瓶颈：黄金案例金额仍为 900000
  - 两级瓶颈：需求侧 ≤ 供给侧 -> final=qualified_demand；
              供给侧 < 需求侧  -> final=affordable_limit
  - 旧字段兼容：limits["bottleneck"] 仍为供给侧标签，limits["collateral_applicable"] 语义不变
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from credit_decision import (  # noqa: E402
    _PLEDGE_DISCOUNT,
    _live_stock_pledge_limit,
    evaluate_credit_case,
)


def _load_main() -> dict:
    path = _BACKEND_DIR / "data_store" / "credit_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))["cases"]["bankgong-green-coop"]


def _with_pledge(items: list[dict], verified: bool = True) -> dict:
    case = deepcopy(_load_main())
    case["pledge"] = {"insurance_verified": verified, "items": items}
    return case


# --------------------------------------------------------------- 折扣档位本身

def test_pledge_discount_table_matches_plan() -> None:
    """四档折扣与方案 D8 一致。"""
    assert _PLEDGE_DISCOUNT["tag_insured"] == Decimal("0.70")
    assert _PLEDGE_DISCOUNT["tag_uninsured"] == Decimal("0.40")
    assert _PLEDGE_DISCOUNT["untag_insured"] == Decimal("0.30")
    assert _PLEDGE_DISCOUNT["untag_uninsured"] == Decimal("0")


def test_pledge_four_tiers_are_split_correctly() -> None:
    """100 头、8 万/头、80 头有耳标、50 头已投保（已核验）：
       50 头 70% + 30 头 40% + 20 头 0% = 35 万 + 12 万 = 47 万
    """
    case = _with_pledge([
        {"species": "牦牛", "head": 100, "unit_price_yuan": 10000,
         "ear_tagged": 80, "insured": 50},
    ])
    pledge = _live_stock_pledge_limit(case)
    assert pledge["applicable"] is True
    assert pledge["limit_yuan"] == Decimal("470000"), pledge["limit_yuan"]
    assert pledge["buckets"]["tag_insured"] == 50.0
    assert pledge["buckets"]["tag_uninsured"] == 30.0
    assert pledge["buckets"]["untag_insured"] == 0.0
    assert pledge["buckets"]["untag_uninsured"] == 20.0


def test_pledge_untagged_but_insured_uses_30_percent() -> None:
    """全部无耳标、其中 40 头投保（已核验）：40 × 30% = 12 万。"""
    case = _with_pledge([
        {"species": "牦牛", "head": 100, "unit_price_yuan": 10000,
         "ear_tagged": 0, "insured": 40},
    ])
    pledge = _live_stock_pledge_limit(case)
    assert pledge["limit_yuan"] == Decimal("120000"), pledge["limit_yuan"]
    assert pledge["buckets"]["untag_insured"] == 40.0
    assert pledge["buckets"]["untag_uninsured"] == 60.0


def test_pledge_insurance_unverified_falls_back_to_uninsured() -> None:
    """保险未核验：投保档不计入，全部按「有耳标 + 无保险」= 40%。"""
    case = _with_pledge(
        [{"species": "牦牛", "head": 100, "unit_price_yuan": 10000,
          "ear_tagged": 100, "insured": 100}],
        verified=False,
    )
    pledge = _live_stock_pledge_limit(case)
    assert pledge["insurance_verified"] is False
    assert pledge["limit_yuan"] == Decimal("400000"), pledge["limit_yuan"]
    assert pledge["buckets"]["tag_insured"] == 0.0
    assert pledge["buckets"]["tag_uninsured"] == 100.0


# ------------------------------------------------- 缺失时「不适用」而非按 0

def test_pledge_missing_is_not_applicable_and_excluded_from_min() -> None:
    """无 pledge 段：不适用、不计入 min，绝不能把金额压成 0。"""
    case = _load_main()
    assert "pledge" not in case
    result = evaluate_credit_case(case)
    assert result["limits"]["pledge"]["applicable"] is False
    assert result["limits"]["collateral_applicable"] is False
    assert result["recommended_amount_yuan"] == 900000, result["recommended_amount_yuan"]


def test_pledge_all_zero_is_not_applicable() -> None:
    """pledge 存在但头数全为 0：仍属不适用，不参与 min。"""
    case = _with_pledge([{"species": "牦牛", "head": 0, "unit_price_yuan": 8000,
                          "ear_tagged": 0, "insured": 0}])
    result = evaluate_credit_case(case)
    assert result["limits"]["pledge"]["applicable"] is False
    assert result["recommended_amount_yuan"] == 900000


# --------------------------------------------- 抵押上限足够高 -> 不改动金额

def test_high_pledge_does_not_change_golden_amount() -> None:
    """980 头牦牛 + 2600 只羊按 70% 计，抵押上限远高于 90 万 -> 不成为瓶颈。"""
    case = _with_pledge([
        {"species": "牦牛", "head": 980, "unit_price_yuan": 8000,
         "ear_tagged": 980, "insured": 980},
        {"species": "藏羊", "head": 2600, "unit_price_yuan": 800,
         "ear_tagged": 2600, "insured": 2600},
    ])
    result = evaluate_credit_case(case)
    pledge = result["limits"]["pledge"]
    assert pledge["applicable"] is True
    # 980×8000×0.7 + 2600×800×0.7 = 5,488,000 + 1,456,000 = 6,944,000
    assert pledge["limit_yuan"] == Decimal("6944000"), pledge["limit_yuan"]
    assert result["limits"]["affordable_limit_yuan"] == Decimal("988716.5157063017922528425516")
    assert result["recommended_amount_yuan"] == 900000
    assert result["bottleneck"]["final"] == "qualified_demand"


def test_low_pledge_becomes_supply_side_bottleneck() -> None:
    """抵押上限刻意压低到 40 万 -> 成为供给侧瓶颈，触发 infeasible（不输出正金额）。"""
    case = _with_pledge([
        {"species": "牦牛", "head": 100, "unit_price_yuan": 10000,
         "ear_tagged": 100, "insured": 0},  # 100×10000×0.4 = 400,000
    ])
    result = evaluate_credit_case(case)
    assert result["limits"]["affordable_limit_yuan"] == Decimal("400000")
    assert result["limits"]["bottleneck"] == "活体抵押上限"
    assert result["status"] == "infeasible"
    assert result["recommended_amount_yuan"] is None
    assert result["bottleneck"]["final"] == "affordable_limit"
    assert result["bottleneck"]["supply_side"] == "活体抵押上限"


# ------------------------------------------------------- 两级瓶颈（方案 D9）

def test_bottleneck_two_levels_demand_side_wins() -> None:
    """黄金案例：需求 90 万 < 供给 98.87 万 -> 最终瓶颈是需求侧（不是偿债能力）。"""
    result = evaluate_credit_case(_load_main())
    assert result["bottleneck"]["final"] == "qualified_demand"
    assert result["bottleneck"]["final_label"] == "基准合格融资需求（饲草采购资金缺口）"
    assert result["bottleneck"]["supply_side"] == "标准雪灾偿债支持上限"
    assert result["bottleneck"]["demand_side_yuan"] == 900000.0
    assert abs(result["bottleneck"]["supply_side_yuan"] - 988716.5157) < 0.01


def test_bottleneck_two_levels_supply_side_wins() -> None:
    """把统一授信可用额度压到 50 万 -> 供给侧成为最终瓶颈。"""
    case = deepcopy(_load_main())
    case["credit"]["unified_total_yuan"] = 1660000 + 500000
    result = evaluate_credit_case(case)
    assert result["limits"]["affordable_limit_yuan"] == Decimal("500000")
    assert result["bottleneck"]["final"] == "affordable_limit"
    assert result["bottleneck"]["final_label"] == "统一授信可用额度"
    assert result["bottleneck"]["supply_side"] == "统一授信可用额度"
    assert result["bottleneck"]["demand_side_yuan"] == 900000.0
    assert result["bottleneck"]["supply_side_yuan"] == 500000.0


def test_legacy_fields_keep_their_meaning() -> None:
    """兼容性：limits.bottleneck 仍是供给侧标签；collateral_support_yuan 原样透传。"""
    result = evaluate_credit_case(_load_main())
    assert isinstance(result["limits"]["bottleneck"], str)
    assert result["limits"]["collateral_support_yuan"] == "N/A"
    assert result["limits"]["collateral_applicable"] is False


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {fn.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(exc).__name__}: {exc}")
        else:
            print(f"ok    {fn.__name__}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
