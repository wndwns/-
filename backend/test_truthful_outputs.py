"""Small regression checks for the competition-facing data claims."""

from insurance_portfolio import get_comprehensive_risk, get_synergy
from models import RiskModel


def test_insurance_outputs_do_not_invent_underwriting_effect():
    synergy = get_synergy()
    comprehensive = get_comprehensive_risk()

    assert synergy["risk_reduction_pct"] is None
    assert synergy["coverage_status"] == "unverified"
    assert comprehensive["comprehensive_risk_score"] is None


def test_labels_keep_unknown_months_out_of_business_claims():
    info = RiskModel().label_info()

    assert info["label_type"] == "weak_label_with_source_events"
    assert info["real_disaster_label_count"] == 127
    assert info["unknown_month_count"] == 1373


if __name__ == "__main__":
    test_insurance_outputs_do_not_invent_underwriting_effect()
    test_labels_keep_unknown_months_out_of_business_claims()
    print("truthful output checks passed")
