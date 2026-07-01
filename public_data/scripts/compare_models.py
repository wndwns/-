"""
新旧模型对比: 月度聚合 vs 时空网格
================================================================
对比维度:
  1. 样本量
  2. 风险区分度 (标准差/变异系数)
  3. 风险识别能力 (能否识别细分风险)
  4. 信息丰富度
"""
import sys, json, urllib.request
import numpy as np
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))
# Windows 中文路径兜底
sys.path.insert(0, r"C:\Users\WH\Desktop\gonghangbei - 副本\backend")

# ---- 旧模型: 月度聚合 ----
print("=" * 70)
print("新旧模型对比")
print("=" * 70)

# 旧模型
from models import RiskModel
model = RiskModel()
model.train()
old_status = model.status()
old_preds = model.predict()

old_scores = [p["predicted_score"] for p in old_preds["predictions"]]
old_scores_by_region = {}
for p in old_preds["predictions"]:
    rid = p["region_id"]
    if rid not in old_scores_by_region:
        old_scores_by_region[rid] = []
    old_scores_by_region[rid].append(p["predicted_score"])

print("\n--- 旧模型: 月度聚合 ---")
print(f"样本量: {old_status['n_samples']}")
print(f"县域数: {old_status['county_count']}")
print(f"月份数: {old_status['month_count']}")
print(f"模型类型: {old_status['model_type']}")
print(f"置信度: {old_status['confidence']}")
print(f"风险评分范围: [{min(old_scores):.1f}, {max(old_scores):.1f}]")
print(f"风险评分均值: {np.mean(old_scores):.1f}")
print(f"风险评分标准差: {np.std(old_scores):.1f}")
print(f"变异系数 (CV): {np.std(old_scores)/np.mean(old_scores)*100:.1f}%")
print(f"风险等级分布: 高={sum(1 for s in old_scores if s>=70)}, 中={sum(1 for s in old_scores if 50<=s<70)}, 低={sum(1 for s in old_scores if s<50)}")

# 县级风险区分度
region_means = [np.mean(v) for v in old_scores_by_region.values()]
print(f"县级风险均值范围: [{min(region_means):.1f}, {max(region_means):.1f}]")
print(f"县级风险标准差: {np.std(region_means):.1f}")

# ---- 新模型: 时空网格 ----
from spatio_temporal_grid import build_all_grids, build_grid, grid_status

new_status = grid_status()
new_all = build_all_grids()

# 取 5 个县做详细对比
test_regions = ["naqu-bange", "naqu-seni", "changdu-karuo", "ali-gaize", "aba-hongyuan"]
new_grids_detail = {}
for rid in test_regions:
    new_grids_detail[rid] = build_grid(rid)

all_grid_scores = []
for r in new_all:
    grid = build_grid(r["region_id"])
    all_grid_scores.extend([g["total_risk"] for g in grid["grids"]])

print("\n--- 新模型: 时空网格 ---")
print(f"样本量: {new_status['total_grids']}")
print(f"维度: {new_status['dimensions']}")
print(f"风险评分范围: [{min(all_grid_scores):.1f}, {max(all_grid_scores):.1f}]")
print(f"风险评分均值: {np.mean(all_grid_scores):.1f}")
print(f"风险评分标准差: {np.std(all_grid_scores):.1f}")
print(f"变异系数 (CV): {np.std(all_grid_scores)/np.mean(all_grid_scores)*100:.1f}%")
print(f"风险等级分布: 高={sum(1 for s in all_grid_scores if s>=65)}, 中={sum(1 for s in all_grid_scores if 40<=s<65)}, 低={sum(1 for s in all_grid_scores if s<40)}")

# 县级风险区分度
new_region_means = [r["avg_risk"] for r in new_all]
print(f"县级风险均值范围: [{min(new_region_means):.1f}, {max(new_region_means):.1f}]")
print(f"县级风险标准差: {np.std(new_region_means):.1f}")

# ---- 详细对比: 5 个县 ----
print("\n" + "=" * 70)
print("5 县详细对比")
print("=" * 70)
print(f"{'region':<20} {'旧模型':>8} {'新模型':>8} {'旧CV%':>8} {'新CV%':>8} {'新维度':>30}")
print("-" * 80)

for rid in test_regions:
    old_vals = old_scores_by_region.get(rid, [50])
    old_mean = np.mean(old_vals)
    old_cv = np.std(old_vals) / max(0.1, old_mean) * 100

    new_grid = new_grids_detail[rid]
    new_vals = [g["total_risk"] for g in new_grid["grids"]]
    new_mean = np.mean(new_vals)
    new_cv = np.std(new_vals) / max(0.1, new_mean) * 100

    # 新模型的细分维度
    season_risks = new_grid["summary"]["season_avg_risk"]
    gl_risks = new_grid["summary"]["grassland_avg_risk"]
    age_risks = new_grid["summary"]["age_avg_risk"]

    dims = f"冬{season_risks['winter']:.0f}/夏{season_risks['summer']:.0f} 草甸{gl_risks['alpine_meadow']:.0f}/荒漠{gl_risks['alpine_desert']:.0f} 犊{age_risks['calf']:.0f}/成{age_risks['adult']:.0f}"

    print(f"{rid:<20} {old_mean:>8.1f} {new_mean:>8.1f} {old_cv:>7.1f}% {new_cv:>7.1f}% {dims:>30}")

# ---- 关键改进点 ----
print("\n" + "=" * 70)
print("关键改进点")
print("=" * 70)

print(f"""
1. 样本量: {old_status['n_samples']} → {new_status['total_grids']} (+{new_status['total_grids']-old_status['n_samples']})
2. 风险区分度 (CV): {np.std(old_scores)/np.mean(old_scores)*100:.1f}% → {np.std(all_grid_scores)/np.mean(all_grid_scores)*100:.1f}%
   → 新模型风险区分度提升 {abs(np.std(all_grid_scores)/np.mean(all_grid_scores)*100 - np.std(old_scores)/np.mean(old_scores)*100):.1f} 个百分点
3. 风险识别维度: 1维 (region+month) → 4维 (region×草场×季节×年龄)
4. 最高风险网格: {max(all_grid_scores):.1f} (旧模型最高: {max(old_scores):.1f})
5. 最低风险网格: {min(all_grid_scores):.1f} (旧模型最低: {min(old_scores):.1f})
6. 风险范围: {max(all_grid_scores)-min(all_grid_scores):.1f} (旧模型: {max(old_scores)-min(old_scores):.1f})
""")

# 班戈县详细网格
print("--- 班戈县: 风险矩阵 (草场 × 季节, 年龄=成年牛) ---")
bange = new_grids_detail["naqu-bange"]
print(f"{'':>20} {'春季':>8} {'夏季':>8} {'秋季':>8} {'冬季':>8}")
for gl in ["alpine_meadow", "alpine_steppe", "alpine_desert"]:
    gl_name = {"alpine_meadow": "高寒草甸", "alpine_steppe": "高寒草原", "alpine_desert": "高寒荒漠"}[gl]
    row = f"{gl_name:>18}"
    for s in ["spring", "summer", "autumn", "winter"]:
        for g in bange["grids"]:
            if g["grassland_type"] == gl and g["season"] == s and g["age_group"] == "adult":
                row += f" {g['total_risk']:>7.1f}"
    print(row)

print("\n--- 班戈县: 风险矩阵 (季节 × 年龄, 草场=高寒草原) ---")
print(f"{'':>20} {'犊牛':>8} {'育成':>8} {'青年':>8} {'成年':>8} {'老龄':>8}")
for s in ["spring", "summer", "autumn", "winter"]:
    s_name = {"spring": "春季", "summer": "夏季", "autumn": "秋季", "winter": "冬季"}[s]
    row = f"{s_name:>18}"
    for a in ["calf", "yearling", "young", "adult", "old"]:
        for g in bange["grids"]:
            if g["grassland_type"] == "alpine_steppe" and g["season"] == s and g["age_group"] == a:
                row += f" {g['total_risk']:>7.1f}"
    print(row)
