"""对比新旧 NPP 数据下的载畜量预测差异。"""
import sys, json, copy
sys.path.insert(0, "backend")

# 先用新数据跑
import carrying_capacity as cc

# 强制重新加载
cc._npp_loaded = False
cc._npp_map = {}
results_new = cc.calculate_all()

# 切换到旧数据
import shutil
from pathlib import Path
store = Path("backend/data_store")
shutil.copy(store / "npp_by_region_old_30x30.json", store / "npp_by_region.json")

cc._npp_loaded = False
cc._npp_map = {}
results_old = cc.calculate_all()

# 切换回新数据
shutil.copy(store / "npp_by_region_regional.json", store / "npp_by_region.json")

# 对比 (按县去重, 取最新月)
def dedup(results):
    seen = {}
    for r in results:
        seen[r["region_id"]] = r
    return seen

old = dedup(results_old)
new = dedup(results_new)

print("=" * 90)
print("载畜量预测对比: 旧(30×30窗口) vs 新(县域边界框均值)")
print("=" * 90)
print(f"{'region_id':<25} {'旧NPP':>8} {'新NPP':>8} {'旧基准':>8} {'新基准':>8} {'旧修正':>8} {'新修正':>8} {'变化%':>8}")
print("-" * 90)

total_old = 0
total_new = 0
for rid in sorted(old.keys()):
    o = old[rid]
    n = new.get(rid, {})
    o_npp = o.get("npp", 0)
    n_npp = n.get("npp", 0)
    o_base = o.get("coefficients", {}).get("npp_base", 0)
    n_base = n.get("coefficients", {}).get("npp_base", 0)
    o_ref = o.get("refined_capacity", 0)
    n_ref = n.get("refined_capacity", 0)
    pct = ((n_ref - o_ref) / o_ref * 100) if o_ref else 0
    total_old += o_ref
    total_new += n_ref
    print(f"{rid:<25} {o_npp:>8.4f} {n_npp:>8.4f} {o_base:>8} {n_base:>8} {o_ref:>8} {n_ref:>8} {pct:>+7.1f}%")

print("-" * 90)
print(f"{'合计':<25} {'':>8} {'':>8} {'':>8} {'':>8} {total_old:>8} {total_new:>8} {(total_new-total_old)/total_old*100:>+7.1f}%")
