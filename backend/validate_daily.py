"""
验证逐日载畜量预测公式准确性
================================================================
1. 用 2024 年及之前的数据预测 2025 年某 3 个月的逐日载畜量
2. 用 2025 年真实 NPP + 真实 NDVI 数据计算"真实"载畜量
3. 比对误差

数据可用性说明：
  - 2025 NPP：✅ 可用（25 个县）
  - 2025 NDVI：✅ 可用（MOD13Q1，23 期/县）
  - 2025 物候：❌ 不可用（仅到 2024）
  - 2025 积雪：❌ 不可用

验证策略：
  - "真实"载畜量 = 2025 NPP × 2025 NDVI × 季节 × 物候(历史均值) × 退化
  - "预测"载畜量 = 预测NPP(近3年均值) × 历史NDVI(2020-2024) × 季节 × 物候(历史均值) × 退化
  - 误差来源：NPP 预测偏差 + NDVI 预测偏差
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path
import bisect
import calendar
import math

sys.path.insert(0, str(Path(__file__).resolve().parent))
from carrying_capacity import (
    _load_npp, _load_phenology, _npp_map, _predict_npp,
    NDVI_BASELINE, NDVI_SENSITIVITY, _degradation_coef,
    _parse_month_and_year,
)

STORE = Path(__file__).resolve().parent / "data_store"

# ── 加载 NPP ──
_load_npp()
npp_2025_real: dict[str, float] = {}
for rid, annual in _npp_map.items():
    if "2025" in annual:
        npp_2025_real[rid] = annual["2025"]

# ── 加载物候 ──
_load_phenology()
from carrying_capacity import _pheno_map

# ── 辅助函数 ──

def _interpolate_daily(values: dict[int, float], doy: int) -> float:
    months = sorted(values.keys())
    if not months:
        return 0.35
    month_doy = {
        m: sum(calendar.monthrange(2025, i)[1] for i in range(1, m)) + 15
        for m in months
    }
    doy_vals = sorted(month_doy.items(), key=lambda x: x[1])
    xs = [d for _, d in doy_vals]
    ys = [values[m] for m, _ in doy_vals]
    if doy <= xs[0]:
        return ys[0]
    if doy >= xs[-1]:
        return ys[-1]
    idx = bisect.bisect_right(xs, doy)
    x0, y0 = xs[idx - 1], ys[idx - 1]
    x1, y1 = xs[idx], ys[idx]
    return y0 + (y1 - y0) * (doy - x0) / (x1 - x0)


def _daily_season_coef(doy: int, greenup: float = 147, dormancy: float = 288) -> float:
    def sigmoid(x):
        return 1.0 / (1.0 + math.exp(-x))
    width = 15.0
    g = sigmoid((doy - greenup) / (width / 3))
    d = sigmoid((dormancy - doy) / (width / 3))
    return 0.40 + 0.60 * min(g, d)


def _load_monthly_ndvi(region_id: str, year: int | None = None) -> dict[int, float]:
    """加载月均 NDVI。
    
    year=None: 所有年份平均
    year=2025: 仅 2025 年
    year=0: 仅 2024 年及之前（历史均值）
    """
    rs_path = STORE / "remote_sensing_data.json"
    if not rs_path.exists():
        return _default_ndvi()
    rows = json.loads(rs_path.read_text(encoding="utf-8"))
    monthly: dict[int, list[float]] = {}
    for r in rows:
        if r.get("region_id") != region_id:
            continue
        month, ry = _parse_month_and_year(r.get("scene_date", ""))
        if month is None or ry is None:
            continue
        if year is not None and year > 0 and ry != year:
            continue
        if year == 0 and ry >= 2025:
            continue
        ndvi = float(r.get("ndvi", 0))
        if ndvi > 0:
            monthly.setdefault(month, []).append(ndvi)
    if not monthly:
        return _default_ndvi()
    return {m: sum(v) / len(v) for m, v in monthly.items()}


def _default_ndvi() -> dict[int, float]:
    return {1: 0.10, 2: 0.12, 3: 0.15, 4: 0.20, 5: 0.35,
            6: 0.55, 7: 0.65, 8: 0.60, 9: 0.45, 10: 0.25, 11: 0.15, 12: 0.10}


# ── 主验证 ──

def validate_region(region_id: str, start_month: int = 6, n_months: int = 3):
    """验证某个县 2025 年某 3 个月的逐日预测。

    对比：
      A) 预测：用 ≤2024 数据预测 NPP + 历史 NDVI(2020-2024) + 物候
      B) 真实：用 2025 实测 NPP + 2025 实测 NDVI + 物候
    """
    npp_real = npp_2025_real.get(region_id)
    if npp_real is None:
        return {"region_id": region_id, "available": False, "reason": "无 2025 NPP 数据"}

    # 预测 NPP（排除 2025）
    annual = _npp_map.get(region_id, {})
    pred_annual = {k: v for k, v in annual.items() if int(k) < 2025}
    npp_pred = _predict_npp(pred_annual)

    # 2025 真实 NDVI（月均）
    ndvi_2025 = _load_monthly_ndvi(region_id, year=2025)
    # 历史预测 NDVI（2020-2024 月均）
    ndvi_pred = _load_monthly_ndvi(region_id, year=0)

    # 退化
    rs_path = STORE / "remote_sensing_data.json"
    deg_level = "轻度退化"
    if rs_path.exists():
        rs_all = json.loads(rs_path.read_text(encoding="utf-8"))
        for r in rs_all:
            if r.get("region_id") == region_id:
                deg_level = r.get("degradation_level", deg_level)
                break
    deg = _degradation_coef(deg_level)

    # 物候（历史均值）
    pheno_info = _pheno_map.get(region_id, {})
    stats = pheno_info.get("statistics", {})
    greenup = stats.get("greenup_mean_doy", 147)
    dormancy = stats.get("dormancy_mean_doy", 288)

    # 逐日计算
    start = date(2025, start_month, 1)
    end_month = start_month + n_months - 1
    end = date(2025, end_month, calendar.monthrange(2025, end_month)[1])
    days = (end - start).days + 1

    daily_comparison = []
    errors_combined = []

    current = start
    while current <= end:
        doy = current.timetuple().tm_yday

        # 真实 NDVI（2025 实测）插值
        ndvi_r = _interpolate_daily(ndvi_2025, doy)
        ndvi_adj_r = 1.0 + (ndvi_r - NDVI_BASELINE) / NDVI_BASELINE * NDVI_SENSITIVITY
        ndvi_adj_r = max(0.30, min(1.50, ndvi_adj_r))

        # 预测 NDVI（历史均值）插值
        ndvi_p = _interpolate_daily(ndvi_pred, doy)
        ndvi_adj_p = 1.0 + (ndvi_p - NDVI_BASELINE) / NDVI_BASELINE * NDVI_SENSITIVITY
        ndvi_adj_p = max(0.30, min(1.50, ndvi_adj_p))

        # 季节系数
        season = _daily_season_coef(doy, greenup, dormancy)

        # 真实载畜量 = 2025 NPP × 2025 NDVI
        base_real = npp_real * 15000.0 + 5000.0
        cap_real = base_real * ndvi_adj_r * season * deg

        # 预测载畜量 = 预测 NPP × 历史 NDVI
        base_pred = npp_pred * 15000.0 + 5000.0
        cap_pred = base_pred * ndvi_adj_p * season * deg

        error_pct = (cap_pred - cap_real) / cap_real * 100 if cap_real > 0 else 0

        daily_comparison.append({
            "date": current.isoformat(),
            "doy": doy,
            "ndvi_real": round(ndvi_r, 4),
            "ndvi_pred": round(ndvi_p, 4),
            "season_coef": round(season, 3),
            "capacity_real": round(cap_real),
            "capacity_pred": round(cap_pred),
            "error_pct": round(error_pct, 1),
        })

        errors_combined.append(abs(error_pct))
        current += timedelta(days=1)

    # 统计
    mae = sum(errors_combined) / len(errors_combined)
    real_vals = [d["capacity_real"] for d in daily_comparison]
    pred_vals = [d["capacity_pred"] for d in daily_comparison]
    mean_real = sum(real_vals) / len(real_vals)
    ss_res = sum((r - p) ** 2 for r, p in zip(real_vals, pred_vals))
    ss_tot = sum((r - mean_real) ** 2 for r in real_vals)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    return {
        "region_id": region_id,
        "available": True,
        "period": f"2025-{start_month:02d} ~ 2025-{end_month:02d} ({days}天)",
        "npp_real": round(npp_real, 4),
        "npp_pred": round(npp_pred, 4),
        "npp_error_pct": round((npp_pred - npp_real) / npp_real * 100, 1),
        "degradation": deg_level,
        "phenology": {"greenup_doy": round(greenup, 1), "dormancy_doy": round(dormancy, 1)},
        "accuracy": {
            "mae_pct": round(mae, 1),
            "r2": round(r2, 4),
            "within_5pct": round(sum(1 for e in errors_combined if e < 5) / len(errors_combined) * 100, 1),
            "within_10pct": round(sum(1 for e in errors_combined if e < 10) / len(errors_combined) * 100, 1),
        },
        "sample_daily": daily_comparison[::7],  # 每周取一天
    }


# ── 运行 ──
print("=" * 75)
print("  逐日载畜量预测公式准确性验证")
print("  方法: 用 ≤2024 数据预测 NPP + NDVI，计算 2025 年逐日载畜量")
print("  对比: 2025 年真实 NPP + 真实 NDVI 计算的载畜量")
print("")
print("  数据: 2025 NPP ✅  |  2025 NDVI ✅ (MOD13Q1)  |  物候(历史均值)")
print("  误差来源: NPP 预测偏差 + NDVI 预测偏差")
print("=" * 75)

# 所有有 2025 NPP 的县
targets = sorted(npp_2025_real.keys())
results = []

for rid in targets:
    r = validate_region(rid, start_month=6, n_months=3)
    results.append(r)
    if r["available"]:
        a = r["accuracy"]
        print(f"\n{'─'*60}")
        print(f"  {rid}")
        print(f"  时期: {r['period']}")
        print(f"  退化: {r['degradation']}")
        print(f"  物候: 返青 DOY={r['phenology']['greenup_doy']}, 枯黄 DOY={r['phenology']['dormancy_doy']}")
        print(f"  NPP: 真实={r['npp_real']}, 预测={r['npp_pred']} (±{r['npp_error_pct']}%)")
        print(f"  MAE: {a['mae_pct']}%  |  R²: {a['r2']}")
        print(f"  误差 <5%: {a['within_5pct']}%, <10%: {a['within_10pct']}%")
        print(f"  前 5 天:")
        for d in r["sample_daily"][:5]:
            print(f"    {d['date']}  NDVI实={d['ndvi_real']}  NDVI预={d['ndvi_pred']}  真实={d['capacity_real']}  预测={d['capacity_pred']}  误差={d['error_pct']}%")
        print(f"  ...")
        for d in r["sample_daily"][-5:]:
            print(f"    {d['date']}  NDVI实={d['ndvi_real']}  NDVI预={d['ndvi_pred']}  真实={d['capacity_real']}  预测={d['capacity_pred']}  误差={d['error_pct']}%")
    else:
        print(f"\n  {rid}: 跳过 - {r.get('reason', '无数据')}")

# 汇总
print(f"\n{'='*75}")
print("  汇总")
available = [r for r in results if r["available"]]
if available:
    maes = [r["accuracy"]["mae_pct"] for r in available]
    r2s = [r["accuracy"]["r2"] for r in available]
    
    print(f"  验证县数: {len(available)}")
    print(f"  平均 MAE: {sum(maes)/len(maes):.1f}%")
    print(f"  平均 R²: {sum(r2s)/len(r2s):.4f}")
    print(f"  MAE 中位数: {sorted(maes)[len(maes)//2]:.1f}%")
    print(f"  MAE 最优: {available[maes.index(min(maes))]['region_id']} ({min(maes):.1f}%)")
    print(f"  MAE 最差: {available[maes.index(max(maes))]['region_id']} ({max(maes):.1f}%)")
    
    # 分布
    print(f"\n  误差分布:")
    print(f"    MAE <5%:   {sum(1 for m in maes if m < 5)} 个县")
    print(f"    MAE 5-10%: {sum(1 for m in maes if 5 <= m < 10)} 个县")
    print(f"    MAE 10-20%:{sum(1 for m in maes if 10 <= m < 20)} 个县")
    print(f"    MAE >20%:  {sum(1 for m in maes if m >= 20)} 个县")
else:
    print("  无可用数据")
print("=" * 75)