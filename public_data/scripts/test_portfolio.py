"""保单模块测试脚本"""
import sys
sys.path.insert(0, r"c:\Users\WH\Desktop\gonghangbei - 副本\backend")

from insurance_portfolio import get_profile, get_farmers, get_synergy, get_comprehensive_risk

print("=== 画像 ===")
p = get_profile()
print(f"保单: {p.get('total_policies')}, 农户: {p.get('farmer_count')}, 牲畜: {p.get('total_cattle')}")
print(f"户均规模: {p.get('avg_herd_size')}, 最大: {p.get('max_herd_size')}, 最小: {p.get('min_herd_size')}")
print(f"规模分布: {p.get('scale_distribution')}")
print(f"耳标批次: {p.get('ear_tag_batches')}")

print("\n=== 农户评分Top5 ===")
fs = get_farmers()
for f in fs[:5]:
    print(f"  {f['farmer_name']}: {f['herd_size']}头, 批次={f['ear_tag_batch_count']}, "
          f"增信分={f['credit_score']}, {f['credit_level']}, 建议={f['suggested_amount']}")

print(f"\n=== 农户评分末3名 ===")
for f in fs[-3:]:
    print(f"  {f['farmer_name']}: {f['herd_size']}头, 增信分={f['credit_score']}, {f['credit_level']}")

print("\n=== 银保协同 ===")
s = get_synergy()
print(f"保险兜底总额: {s['total_insurance_coverage']}元 = {s['total_insurance_coverage']/10000:.1f}万元")
print(f"预计贷款总额: {s['estimated_total_loan']}元 = {s['estimated_total_loan']/10000:.1f}万元")
print(f"风险缩减: {s['risk_reduction_pct']}%")
print(f"等级分布: {s['credit_level_distribution']}")
print(f"总结: {s['summary']}")

print("\n=== 综合风险 ===")
c = get_comprehensive_risk()
print(f"环境风险: {c['environment_risk'].get('risk_score')}")
print(f"综合风险: {c['comprehensive_risk_score']} ({c['comprehensive_risk_level']})")
print(f"结论: {c['conclusion']}")

print("\n[OK] 所有测试通过")
