"""测试SHAP可解释性功能"""
import sys
sys.path.insert(0, r"C:\Users\WH\Desktop\gonghangbei - 副本\backend")

from models import get_model

m = get_model()
m.train()

result = m.explain_prediction("naqu-bange")

print("=" * 60)
print("SHAP 风险解释报告测试")
print("=" * 60)
print(f"区域: {result.get('region_name')}")
print(f"月份: {result.get('month')}")
print(f"预测风险分: {result.get('prediction')}")
print(f"风险等级: {result.get('risk_level')}")
print(f"基准值: {result.get('base_value')}")
print(f"模型类型: {result.get('model_type')}")
print(f"SHAP可用: {result.get('shap_available')}")
print()
print("Top 5 风险驱动因素:")
for d in result.get("top_drivers", [])[:5]:
    print(f"  {d['feature']}={d['feature_value']} | SHAP={d['shap_value']} | {d['contribution']} | {d['category']}")
print()
print("风险摘要:")
print(f"  {result.get('summary')}")
print()
print("针对性建议:")
for r in result.get("recommendations", []):
    print(f"  - {r}")
print()
print("=" * 60)
print("测试完成!")
