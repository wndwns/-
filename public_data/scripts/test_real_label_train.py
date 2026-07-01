"""测试真实标签融合训练"""
import sys
sys.path.insert(0, r"C:\Users\WH\Desktop\gonghangbei - 副本\backend")

from models import get_model

m = get_model()
status = m.train()

print("=" * 60)
print("真实标签融合训练测试")
print("=" * 60)
print(f"模型类型: {status.get('model_type')}")
print(f"样本数: {status.get('n_samples')}")
print(f"置信度: {status.get('confidence')}")
print(f"真实标签数: {m._real_label_count}")
print()

metrics = status.get('metrics', {})
print("评估指标:")
for k, v in metrics.items():
    print(f"  {k}: {v}")
print()

print("警告信息:")
for w in status.get('warnings', []):
    print(f"  - {w}")
print()

# 测试SHAP解释
result = m.explain_prediction("naqu-bange")
print(f"班戈县SHAP测试:")
print(f"  预测分: {result.get('prediction')}")
print(f"  风险等级: {result.get('risk_level')}")
print(f"  SHAP可用: {result.get('shap_available')}")
print(f"  真实标签: {result.get('region_name', '')}")
print()
print("Top 3 驱动因素:")
for d in result.get('top_drivers', [])[:3]:
    print(f"  {d['feature']}={d['feature_value']} SHAP={d['shap_value']} ({d['contribution']})")
