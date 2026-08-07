"""
工银牧融 - 唯一授信决策黄金样例与边界回归检查
============================================================================
运行：
    python backend\\test_credit_decision.py
或：
    python test_credit_decision.py  （在 backend 目录下）

覆盖：
  - 黄金主案例：feasible / 900000 / 利息 34020 / DSCR≈1.2416 / 支持上限≈988716.52
     / 雪灾最低现金≈303065.50 @ 2027-01 / 峰值余额 2560000 / 瓶颈=基准合格融资需求
  - 复合极端：不生成第二金额，采购成本 2087670 / 可用现金 2777675.50 / DSCR≈1.0451
     / 2027-01 现金≈109672 / 缺口≈40328
  - 不可行反例：雪灾偿债现金 3127248 → 支持上限 850000 → infeasible / 缺口 50000
  - 取整边界：必要外部资金 895000 → infeasible（不向上取整）
  - 百巴村资料不足 → blocked，无推荐金额
  - 保险不影响金额；N/A 约束不阻断；草畜守恒；情景单调性
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from decimal import Decimal

_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from credit_decision import evaluate_credit_case  # noqa: E402


def _load_cases() -> dict:
    path = _BACKEND_DIR / "data_store" / "credit_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def _load_main() -> dict:
    return deepcopy(_load_cases()["bankgong-green-coop"])


def _assert_close(actual, expected, tol, label):
    a = float(actual)
    e = float(expected)
    assert abs(a - e) <= tol, f"{label}: 期望 {e}，实际 {a}（差值 {abs(a - e)} > {tol}）"


# ---------------------------------------------------------------------------
# 黄金主案例
# ---------------------------------------------------------------------------

def test_golden_case():
    case = _load_main()
    result = evaluate_credit_case(case)

    assert result["status"] == "feasible", f"黄金案例状态应为 feasible，实际 {result['status']}：{result.get('reason')}"
    assert result["recommended_amount_yuan"] is not None
    _assert_close(result["recommended_amount_yuan"], 900000, 0.01, "唯一建议新增贷款")
    _assert_close(result["new_loan_interest_yuan"], 34020, 0.01, "新增贷款利息")
    _assert_close(result["dscr"], 1.2416, 0.0005, "推荐金额下标准雪灾 DSCR")
    _assert_close(result["limits"]["snow_support_limit_yuan"], 988716.52, 0.5, "标准雪灾偿债支持上限")
    _assert_close(result["limits"]["credit_available_yuan"], 1050000, 0.01, "统一授信可用额度")
    _assert_close(result["limits"]["product_cap_yuan"], 1200000, 0.01, "产品上限")
    assert result["limits"]["collateral_applicable"] is False, "保证/抵质押支持上限应标记为不适用"
    assert result["snow_cashflow"]["min_cash_month"] == "2027-01"
    _assert_close(result["snow_cashflow"]["min_cash_yuan"], 303065.50, 0.5, "标准雪灾最低月末现金")
    _assert_close(result["snow_cashflow"]["peak_loan_balance_yuan"], 2560000, 0.01, "12 个月峰值贷款余额")
    assert result["limits"]["bottleneck"] == "标准雪灾偿债支持上限" or result["limits"]["bottleneck"] == "基准合格融资需求"
    _assert_close(result["qualified_demand"]["min_external_financing_yuan"], 900000, 0.01, "必要采购最低外部资金")
    _assert_close(result["qualified_demand"]["purchase_total_yuan"], 1250000, 0.01, "必要采购总额")


def test_golden_monthly_storage_balance():
    case = _load_main()
    result = evaluate_credit_case(case)
    baseline = result["monthly_scenarios"]["baseline"]
    # 期末储草保持安全库存 104720，且不小于 0
    _assert_close(baseline["ending_storage_kg"], 104720, 0.5, "基准期末储草")
    assert baseline["storage_balanced"] is True
    assert baseline["total_purchase_kg"] == 500000
    # 全年需求 = 2379800
    _assert_close(baseline["total_demand_kg"], 2379800, 0.5, "全年基准干物质需求")
    # 任意月份储草不为负
    for row in baseline["rows"]:
        assert row["storage_balance_kg"] >= 0, f"储草出现负库存: {row['month']}"
        assert row["forage_gap_kg"] >= 0


# ---------------------------------------------------------------------------
# 复合极端
# ---------------------------------------------------------------------------

def test_composite_does_not_generate_second_amount():
    case = _load_main()
    result = evaluate_credit_case(case)
    c = result["composite"]
    assert c["generates_second_amount"] is False
    assert "recommended_amount_yuan" not in c or c.get("recommended_amount_yuan") is None
    _assert_close(c["purchase_cost_yuan"], 2087670, 0.5, "复合极端采购成本")
    _assert_close(c["available_cash_yuan"], 2777675.50, 0.5, "复合极端可用于偿债经营现金")
    _assert_close(c["dscr"], 1.0451, 0.0005, "复合极端 DSCR")
    _assert_close(c["min_cash_yuan"], 109672, 1.0, "复合极端 2027-01 月末现金")
    assert c["min_cash_month"] == "2027-01"
    _assert_close(c["min_cash_gap_yuan"], 40328, 1.0, "复合极端现金缺口")
    assert c["vulnerable"] is True


# ---------------------------------------------------------------------------
# 不可行反例：标准雪灾偿债现金不足
# ---------------------------------------------------------------------------

def test_infeasible_when_snow_repayment_short():
    case = _load_main()
    # 把标准雪灾全周期可用于偿债经营现金改为 3127248 → 支持上限约 850000 < 900000
    case["operating"]["monthly_net_cash_yuan"][11] = 665345.50 - 172752.0
    result = evaluate_credit_case(case)
    assert result["status"] == "infeasible", f"反例状态应为 infeasible，实际 {result['status']}"
    assert result["recommended_amount_yuan"] is None or result["recommended_amount_yuan"] == 0
    _assert_close(result["limits"]["snow_support_limit_yuan"], 850000, 0.5, "反例偿债支持上限")
    _assert_close(result["gap_yuan"], 50000, 0.5, "资金缺口")
    assert "必要采购" in result["reason"] and "不形成推荐贷款金额" in result["reason"]


# ---------------------------------------------------------------------------
# 取整边界：向下取整后不足必要资金，不得向上取整
# ---------------------------------------------------------------------------

def test_floor_boundary_infeasible():
    case = _load_main()
    # 必要外部资金 895000（自有采购资金 355000 → 1250000-355000=895000）
    inputs = {"operating": {"own_purchase_funds_yuan": 355000}}
    result = evaluate_credit_case(case, inputs)
    assert result["status"] == "infeasible", f"取整边界状态应为 infeasible，实际 {result['status']}"
    assert result["recommended_amount_yuan"] is None or result["recommended_amount_yuan"] == 0
    _assert_close(result["qualified_demand"]["min_external_financing_yuan"], 895000, 0.01, "取整边界必要外部资金")


# ---------------------------------------------------------------------------
# 百巴村资料不足
# ---------------------------------------------------------------------------

def test_baiba_blocked():
    cases = _load_cases()
    result = evaluate_credit_case(cases["baiba-village"])
    assert result["status"] == "blocked", f"百巴村应为 blocked，实际 {result['status']}"
    assert result["recommended_amount_yuan"] is None
    assert len(result["missing_materials"]) > 0
    assert "保险" in "".join(result["missing_materials"]) or "授信" in "".join(result["missing_materials"])


def test_empty_case_blocked():
    result = evaluate_credit_case({})
    assert result["status"] == "blocked"


# ---------------------------------------------------------------------------
# 保险不进入金额主链 / N/A 约束不阻断
# ---------------------------------------------------------------------------

def test_insurance_does_not_change_amount():
    case = _load_main()
    base = evaluate_credit_case(case)
    case2 = deepcopy(case)
    case2["insurance_probe"] = {"coverage": 0.95, "verified_policies": 999}
    result2 = evaluate_credit_case(case2)
    assert result2["recommended_amount_yuan"] == base["recommended_amount_yuan"]
    assert result2["dscr"] == base["dscr"]
    assert result2["composite"]["min_cash_yuan"] == base["composite"]["min_cash_yuan"]


def test_legacy_model_fields_ignored():
    case = _load_main()
    case["legacy_probe"] = {"rf_score": 88, "ridge_score": 91, "four_dim_score": 75, "risk_multiplier": 0.7}
    result = evaluate_credit_case(case)
    assert result["status"] == "feasible"
    _assert_close(result["recommended_amount_yuan"], 900000, 0.01, "旧模型字段不应影响金额")


# ---------------------------------------------------------------------------
# 单调性与守恒
# ---------------------------------------------------------------------------

def test_more_demand_never_less_purchase_cost():
    case = _load_main()
    base = evaluate_credit_case(case)
    case2 = deepcopy(case)
    case2["livestock"]["monthly_demand_kg"] = [int(round(v * 1.05)) for v in case2["livestock"]["monthly_demand_kg"]]
    result2 = evaluate_credit_case(case2)
    assert result2["monthly_scenarios"]["baseline"]["total_demand_kg"] > base["monthly_scenarios"]["baseline"]["total_demand_kg"]
    assert result2["monthly_scenarios"]["baseline"]["total_purchase_cost_yuan"] >= base["monthly_scenarios"]["baseline"]["total_purchase_cost_yuan"]


def test_snow_worsening_increases_cost():
    case = _load_main()
    base_snow = evaluate_credit_case(case)["monthly_scenarios"]["snow"]
    case2 = deepcopy(case)
    case2["scenarios"]["snow"]["price_factor"] = 1.30  # 价格加重
    result2_snow = evaluate_credit_case(case2)["monthly_scenarios"]["snow"]
    assert result2_snow["total_purchase_cost_yuan"] > base_snow["total_purchase_cost_yuan"]


def test_no_negative_inventory_in_snow():
    case = _load_main()
    result = evaluate_credit_case(case)
    for sc in ("baseline", "snow", "composite"):
        for row in result["monthly_scenarios"][sc]["rows"]:
            assert row["storage_balance_kg"] >= 0, f"{sc} 储草负库存: {row['month']}"
            assert row["forage_gap_kg"] >= 0, f"{sc} 缺口为负: {row['month']}"


def test_monthly_cashflow_rows_present():
    case = _load_main()
    result = evaluate_credit_case(case)
    for sc in ("baseline", "snow", "composite"):
        rows = result["monthly_cashflow"][sc]
        assert len(rows) == 12, f"{sc} 现金流应为 12 个月"
        for row in rows:
            assert "cash_after_financing_yuan" in row


# ---------------------------------------------------------------------------
# 用户输入覆盖：草场面积变化后标记未核验并重新测算
# ---------------------------------------------------------------------------

def test_user_input_override_changes_result():
    case = _load_main()
    # 降低自有采购资金 → 外部资金需求上升
    inputs = {"operating": {"own_purchase_funds_yuan": 200000}}
    result = evaluate_credit_case(case, inputs)
    assert result["inputs_overridden"] is True
    _assert_close(result["qualified_demand"]["min_external_financing_yuan"], 1050000, 0.01, "覆盖后必要外部资金")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    tests = [
        test_golden_case,
        test_golden_monthly_storage_balance,
        test_composite_does_not_generate_second_amount,
        test_infeasible_when_snow_repayment_short,
        test_floor_boundary_infeasible,
        test_baiba_blocked,
        test_empty_case_blocked,
        test_insurance_does_not_change_amount,
        test_legacy_model_fields_ignored,
        test_more_demand_never_less_purchase_cost,
        test_snow_worsening_increases_cost,
        test_no_negative_inventory_in_snow,
        test_monthly_cashflow_rows_present,
        test_user_input_override_changes_result,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {type(exc).__name__}: {exc}")
    if failed:
        print(f"\n{len(tests) - failed}/{len(tests)} passed, {failed} failed")
        raise SystemExit(1)
    print(f"\nAll {len(tests)} credit-decision checks passed")


if __name__ == "__main__":
    main()
