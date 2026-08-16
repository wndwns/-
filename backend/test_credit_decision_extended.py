"""Additional regression checks for the credit-decision contract.

Run with:
    python backend\\test_credit_decision_extended.py
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from credit_decision import MONTHS, evaluate_credit_case  # noqa: E402


def load_cases() -> dict:
    path = BACKEND_DIR / "data_store" / "credit_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def main_case() -> dict:
    return deepcopy(load_cases()["bankgong-green-coop"])


def assert_close(actual, expected, tolerance=0.01):
    assert abs(float(actual) - float(expected)) <= tolerance, (actual, expected)


def test_case_fixture_truthfulness():
    case = main_case()
    assert case["pasture"]["total_mu"] == 42000
    assert case["livestock"]["yak_head"] == 980
    assert case["livestock"]["sheep_head"] == 2600
    assert case["data_status"]["草场与牲畜"] == "sample_assumption"
    assert case["data_status"]["月度经营现金"] == "sample_assumption"


def test_result_shape_and_single_amount_contract():
    result = evaluate_credit_case(main_case())
    required = {
        "status", "recommended_amount_yuan", "qualified_demand", "limits",
        "snow_cashflow", "monthly_cashflow", "monthly_scenarios", "composite",
    }
    assert required <= result.keys()
    assert result["status"] == "feasible"
    assert result["recommended_amount_yuan"] == 900000
    assert result["composite"].get("generates_second_amount") is False
    assert result["composite"].get("recommended_amount_yuan") in (None, 0)


def test_all_scenarios_have_twelve_balanced_rows():
    result = evaluate_credit_case(main_case())
    for scenario in ("baseline", "snow", "composite"):
        plan = result["monthly_scenarios"][scenario]
        assert len(plan["rows"]) == len(MONTHS)
        assert plan["storage_balanced"] is True
        assert all(row["storage_balance_kg"] >= 0 for row in plan["rows"])
        assert all(row["forage_gap_kg"] == 0 for row in plan["rows"])
        assert len(result["monthly_cashflow"][scenario]) == len(MONTHS)


def test_pressure_is_monotonic_and_composite_is_stress_only():
    result = evaluate_credit_case(main_case())
    baseline = result["monthly_scenarios"]["baseline"]
    snow = result["monthly_scenarios"]["snow"]
    composite = result["monthly_scenarios"]["composite"]
    assert snow["total_demand_kg"] > baseline["total_demand_kg"]
    assert snow["total_purchase_cost_yuan"] > baseline["total_purchase_cost_yuan"]
    assert composite["total_demand_kg"] > snow["total_demand_kg"]
    assert composite["total_purchase_cost_yuan"] > snow["total_purchase_cost_yuan"]
    assert result["composite"]["generates_second_amount"] is False


def test_input_override_does_not_mutate_fixture():
    case = main_case()
    before = deepcopy(case)
    result = evaluate_credit_case(case, {"pasture": {"total_mu": 21000}})
    assert result["inputs_overridden"] is True
    assert case == before
    assert result["monthly_scenarios"]["baseline"]["pasture_growth_scale"] == 0.5


def test_limit_bottleneck_changes_without_creating_second_amount():
    case = main_case()
    case["credit"]["unified_total_yuan"] = 2560000
    result = evaluate_credit_case(case)
    assert result["status"] == "feasible"
    assert result["limits"]["bottleneck"] == "统一授信可用额度"
    assert result["recommended_amount_yuan"] == 900000
    assert result["composite"].get("recommended_amount_yuan") in (None, 0)

    case["credit"]["unified_total_yuan"] = 2460000
    result = evaluate_credit_case(case)
    assert result["status"] == "infeasible"
    assert result["recommended_amount_yuan"] is None
    assert result["gap_yuan"] == 100000
    assert "必要采购" in result["reason"]


def test_abnormal_repayment_is_blocked_before_amount_calculation():
    case = main_case()
    case["debt"]["repayment_status"] = "逾期"
    result = evaluate_credit_case(case)
    assert result["status"] == "blocked"
    assert result["recommended_amount_yuan"] is None
    assert any("还款" in item or "逾期" in item for item in result["missing_materials"])


def test_zero_insurance_and_high_insurance_are_amount_invariant():
    base = evaluate_credit_case(main_case())
    for coverage in (0, 0.5, 1.0):
        case = main_case()
        case["insurance_probe"] = {"coverage": coverage, "verified_policies": 999}
        result = evaluate_credit_case(case)
        assert result["recommended_amount_yuan"] == base["recommended_amount_yuan"]
        assert result["dscr"] == base["dscr"]
        assert result["snow_cashflow"]["peak_loan_balance_yuan"] == base["snow_cashflow"]["peak_loan_balance_yuan"]


def test_peak_balance_is_not_approval_amount():
    result = evaluate_credit_case(main_case())
    assert result["snow_cashflow"]["peak_loan_balance_yuan"] == 2560000
    assert result["snow_cashflow"]["peak_loan_balance_yuan"] != result["recommended_amount_yuan"]
    assert result["limits"]["snow_support_limit_yuan"] > result["recommended_amount_yuan"]


def test_frontend_discloses_sample_and_approval_boundaries():
    html = (PROJECT_DIR / "frontend" / "index.html").read_text(encoding="utf-8")
    app = (PROJECT_DIR / "frontend" / "app.js").read_text(encoding="utf-8")
    case_json = (BACKEND_DIR / "data_store" / "credit_cases.json").read_text(encoding="utf-8")
    for text in ("42000", "980", "2600"):
        assert text in case_json, text
    for text in ("42000", "12 个月峰值贷款余额", "最终决定由客户经理和审批人员完成"):
        assert text in html or text in app, text
    assert "保险第一版不进入金额与现金流" in html
    assert "样例假设" in html
    assert "不生成第二个推荐金额" in html
    assert "补齐真实业务数据" in app


def run():
    tests = [
        test_case_fixture_truthfulness,
        test_result_shape_and_single_amount_contract,
        test_all_scenarios_have_twelve_balanced_rows,
        test_pressure_is_monotonic_and_composite_is_stress_only,
        test_input_override_does_not_mutate_fixture,
        test_limit_bottleneck_changes_without_creating_second_amount,
        test_abnormal_repayment_is_blocked_before_amount_calculation,
        test_zero_insurance_and_high_insurance_are_amount_invariant,
        test_peak_balance_is_not_approval_amount,
        test_frontend_discloses_sample_and_approval_boundaries,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} extended checks passed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    run()
