"""Small regression checks for the competition-facing data claims."""

from insurance_portfolio import get_comprehensive_risk, get_synergy


def test_insurance_outputs_do_not_invent_underwriting_effect():
    synergy = get_synergy()
    comprehensive = get_comprehensive_risk()

    assert synergy["risk_reduction_pct"] is None
    assert synergy["coverage_status"] == "unverified"
    assert comprehensive["comprehensive_risk_score"] is None


if __name__ == "__main__":
    test_insurance_outputs_do_not_invent_underwriting_effect()
    print("truthful output checks passed")
