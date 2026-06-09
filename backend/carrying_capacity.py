"""
牧融绿链 - 多维度载畜量精算模型 v3
============================================================================
v3 升级：集成 MCD12Q2 物候数据（返青期/枯黄期/生长季长度），实现:
  维度1 — NPP 净初级生产力基线 (kgC/m²/yr → 羊单位)
  维度2 — NDVI 月内波动修正 (年度 NPP 不体现的月间差异)
  维度3 — 季节系数 (返青/盛草/枯草期)
  维度4 — 退化惩罚 (degradation_level)
  维度5 — 积雪阻碍 (snow_cover)
  维度6 — 物候修正 (生长季长度偏差 + 趋势降解) ← v3 新增

公式:
  refined = npp_base(region, year) × NDVI修正 × 季节 × 退化 × 积雪 × 物候

物候修正逻辑:
  - 当年生长季偏短 → 产草量减少 → 系数 < 1.0
  - 生长季长期缩短趋势 → 草地退化信号 → 额外衰减
  - 数据来源: MCD12Q2.061 (2003-2024), 22 年 MODIS 物候产品

NPP 转换公式:
  干草 = NPP × 0.45(碳→干物质) × 10000(m²→ha) × 0.5(地上) = NPP × 2250 kg/ha
  载畜量 = 干草 × 0.5(利用率) / (2.0 kg/天 × 365天) = NPP × 1.54 羊单位/ha
  县级总量 = 载畜量/ha × 草地面积(ha)
  
  由于缺少县级草地面积，采用比例映射: base = NPP × 15000 + 5000
  此映射使 NPP 0.08→6200, NPP 0.50→12500, NPP 2.0→35000, NPP 3.28→54200
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_STORE_DIR = Path(__file__).resolve().parent / "data_store"

# ── NPP 数据加载 ──
_npp_map: dict[str, dict[str, float]] = {}
_npp_loaded = False


def _load_npp():
    global _npp_map, _npp_loaded
    if _npp_loaded:
        return
    path = _STORE_DIR / "npp_by_region.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data:
            _npp_map[entry["region_id"]] = entry.get("npp_annual", {})
    _npp_loaded = True


# ── 物候数据加载 ──
_pheno_map: dict[str, dict] = {}
_pheno_loaded = False


def _load_phenology():
    global _pheno_map, _pheno_loaded
    if _pheno_loaded:
        return
    path = _STORE_DIR / "phenology_by_region.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data:
            _pheno_map[entry["region_id"]] = {
                "growing_season": entry.get("data", {}).get("growing_season", {}),
                "statistics": entry.get("statistics", {}),
            }
    _pheno_loaded = True


def _phenology_factor(region_id: str, year: int) -> float:
    """维度 6 — 物候修正系数。

    逻辑：
      1. 当年生长季长度 vs 历史均值 → 短期偏差修正
      2. 生长季长期趋势 → 趋势降解（仅对未来年份生效）

    系数范围：0.85 ~ 1.15
    """
    _load_phenology()
    info = _pheno_map.get(region_id)
    if not info:
        return 1.0  # 无物候数据，不修正

    gs = info["growing_season"]
    stats = info["statistics"]

    gs_mean = stats.get("growing_season_mean_days")
    gs_trend = stats.get("growing_season_trend_days_per_year")

    if gs_mean is None:
        return 1.0

    # 短期偏差：当年生长季 vs 历史均值
    gs_current = gs.get(str(year))
    if gs_current is not None:
        # 生长季每偏离均值 10%，载畜量修正 5%
        deviation = (float(gs_current) - gs_mean) / gs_mean
        pheno = 1.0 + deviation * 0.5
    else:
        pheno = 1.0

    # 长期趋势衰减（对未来年份，如果趋势 < 0 则叠加衰减）
    if gs_trend is not None and gs_trend < 0:
        # 如果生长季在缩短，以趋势外推到目标年份
        max_hist_year = max(int(y) for y in gs.keys()) if gs else year
        years_ahead = max(0, year - max_hist_year)
        # 每年衰减 gs_trend/gs_mean 的比例，衰减敏感系数 3.0
        trend_decay = 1.0 + (gs_trend / gs_mean) * years_ahead * 3.0
        pheno *= trend_decay

    return max(0.85, min(1.15, pheno))


def get_phenology_summary(region_id: str) -> dict:
    """获取指定区域的物候摘要。"""
    _load_phenology()
    info = _pheno_map.get(region_id)
    if not info:
        return {"available": False}
    stats = info["statistics"]
    return {
        "available": True,
        "region_id": region_id,
        "data_years": f"{min(int(y) for y in info['growing_season'].keys())}-{max(int(y) for y in info['growing_season'].keys())}",
        **stats,
    }


def _npp_base(region_id: str, year: int) -> float:
    """用 NPP 计算基准载畜量 (羊单位)。

    有当年 NPP 数据时直接用，否则用近 3 年均值预测（回测验证 MAE=5.2%）。
    """
    _load_npp()
    annual = _npp_map.get(region_id, {})
    npp = annual.get(str(year))
    if npp is None:
        npp = _predict_npp(annual)
    return npp * 15000.0 + 5000.0


def _predict_npp(annual: dict[str, float]) -> float:
    """用近 3 年均值预测 NPP（回测验证最优方法，MAE=5.2%）。"""
    years = sorted(int(y) for y in annual.keys())
    vals = [annual[str(y)] for y in years]
    if not vals:
        return 0.35
    if len(vals) >= 3:
        return float(sum(vals[-3:]) / 3)
    return sum(vals) / len(vals)


def predict_npp_for_region(region_id: str, target_year: int | None = None) -> dict[str, Any]:
    """预测指定区域未来年份的 NPP 值（近 3 年均值法）。"""
    _load_npp()
    annual = _npp_map.get(region_id, {})
    if not annual:
        return {"region_id": region_id, "available": False, "message": "无 NPP 数据"}

    years = sorted(int(y) for y in annual.keys())
    actual = annual.get(str(target_year)) if target_year else None

    # 预测时排除目标年份，只用历史数据
    pred_annual = {k: v for k, v in annual.items() if int(k) != target_year}
    predicted = _predict_npp(pred_annual) if target_year else _predict_npp(annual)
    cap = lambda npp: npp * 15000.0 + 5000.0

    result: dict[str, Any] = {
        "region_id": region_id,
        "available": True,
        "method": "recent3(近3年均值)",
        "method_mae": "5.2%",
        "data_years": f"{years[0]}-{years[-1]}",
        "data_points": len(years),
        "predicted_npp": round(predicted, 4),
        "predicted_capacity": round(cap(predicted)),
    }
    if target_year:
        result["target_year"] = target_year
    if actual is not None:
        result["actual_npp"] = round(actual, 4)
        result["actual_capacity"] = round(cap(actual))
        result["error_pct"] = round((predicted - actual) / actual * 100, 1)
    return result


def predict_all_npp(target_year: int | None = None) -> list[dict[str, Any]]:
    """预测所有区域的 NPP 值。"""
    _load_npp()
    return [predict_npp_for_region(rid, target_year) for rid in sorted(_npp_map.keys())]


# ── 月度 → 季节系数 ──
def _season_coef(month: int) -> float:
    if month in (6, 7, 8):
        return 1.00
    if month in (5, 9):
        return 0.85
    if month in (4, 10):
        return 0.70
    if month in (3, 11):
        return 0.55
    return 0.40


# ── 退化等级 → 产草量折扣 ──
DEGRADATION_PENALTY: dict[str, float] = {
    "基本稳定": 1.00,
    "轻度退化": 0.80,
    "中度退化": 0.60,
    "重度退化": 0.40,
    "极重度退化": 0.25,
}


def _degradation_coef(level: str) -> float:
    return DEGRADATION_PENALTY.get(level, 1.0)


# ── Li 2025 GDI 退化预警因子 ──
# 基于遥感+草地科学阈值, 独立于行政区划退化等级的额外安全保障
_GDI_FACTOR_MAP = {
    "高风险": 0.80,   # 草产量低于安全阈值, 额外 20% 安全折减
    "中风险": 0.90,   # 草产量接近阈值, 额外 10% 折减
    "低风险": 1.00,   # 不作 GDI 折减
}


def _gdi_warning_factor(region_id: str) -> float:
    """从 Li 2025 退化评估获取额外安全折减系数。

    这是一个独立于行政退化等级的科学因子:
    - GDI 基于 MODIS NPP+NDVI 的 PCA 降维
    - 阈值来自 743 个野外采样点的曲率分析
    - 按草地类型使用不同高风险线 (高寒草甸 115g/m², 高寒草原 73g/m²)
    
    注意: 即使行政评级为"基本稳定", GDI 仍可能标记高风险
          (如 naqu-bange 行政为中轻度, 但 GDI 标记为高风险)
    """
    try:
        from early_warning import compute_gdi
    except ImportError:
        from backend.early_warning import compute_gdi  # type: ignore[no-redef]

    gdi_result = compute_gdi(region_id)
    if not gdi_result.get("available"):
        return 1.0

    risk_level = gdi_result.get("risk_level", "低风险")
    return _GDI_FACTOR_MAP.get(risk_level, 1.0)


# ── 积雪覆盖 → 可食草比例 ──
def _snow_coef(snow_cover_pct: float) -> float:
    if snow_cover_pct < 5:
        return 1.00
    if snow_cover_pct < 15:
        return 0.90
    if snow_cover_pct < 30:
        return 0.75
    return 0.50


# ── 工具函数 ──

def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        try:
            return float(str(val).replace("%", ""))
        except (ValueError, TypeError):
            return default


def _parse_month_and_year(date_str: str) -> tuple[int | None, int | None]:
    if not date_str:
        return None, None
    try:
        parts = date_str.strip()[:10].split("-")
        return int(parts[1]), int(parts[0])
    except (ValueError, IndexError):
        return None, None


# ── 核心计算 ──

NDVI_BASELINE = 0.35
NDVI_SENSITIVITY = 0.40   # v2: 降低 NDVI 敏感度，因为 NPP 已承担基线


def calculate_all() -> list[dict[str, Any]]:
    path = _STORE_DIR / "remote_sensing_data.json"
    if not path.exists():
        return []

    _load_npp()
    rows = json.loads(path.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []

    for row in rows:
        rid = row.get("region_id", "")
        month, year = _parse_month_and_year(row.get("scene_date", ""))
        if not rid or month is None or year is None:
            continue

        ndvi = _safe_float(row.get("ndvi"), 0.35)
        degradation = row.get("degradation_level", "轻度退化")
        snow_pct = _safe_float(
            str(row.get("snow_cover", "10%")).replace("%", ""), 10.0
        )
        static_cap = _safe_float(row.get("carrying_capacity_sheep_unit"), 35600)

        # ── 六项系数 ──
        base = _npp_base(rid, year)

        # NDVI 修正：捕捉 NPP 年度值不体现的月间波动
        ndvi_adj = 1.0 + (ndvi - NDVI_BASELINE) / NDVI_BASELINE * NDVI_SENSITIVITY
        ndvi_adj = max(0.30, min(1.50, ndvi_adj))

        season = _season_coef(month)
        deg = _degradation_coef(degradation)
        snow = _snow_coef(snow_pct)
        pheno = _phenology_factor(rid, year)

        refined = base * ndvi_adj * season * deg * snow * pheno
        refined = round(refined)

        npp_val = _npp_map.get(rid, {}).get(str(year), 0)

        results.append({
            "region_id": rid,
            "month": f"{month:02d}月",
            "scene_date": row.get("scene_date", ""),
            "degradation_level": degradation,
            "ndvi": round(ndvi, 4),
            "snow_cover_pct": round(snow_pct, 1),
            "npp": round(npp_val, 4),
            "static_capacity": int(static_cap),
            "refined_capacity": refined,
            "coefficients": {
                "npp_base": round(base),
                "ndvi_adj": round(ndvi_adj, 3),
                "season_coef": season,
                "degradation_coef": deg,
                "snow_coef": round(snow, 2),
                "phenology_coef": round(pheno, 3),
            },
            "breakdown": (
                f"NPP{npp_val:.3f}基准{round(base)} → NDVI{ndvi:.2f}(×{ndvi_adj:.2f}) "
                f"→ {month}月(×{season}) → {degradation}(×{deg}) "
                f"→ 积雪{snow_pct:.0f}%(×{snow:.2f}) → 物候(×{pheno:.3f}) = {refined}羊单位"
            ),
        })

    return results


def compare_by_region(region_id: str) -> dict[str, Any]:
    all_calc = calculate_all()
    region_rows = [r for r in all_calc if r["region_id"] == region_id]
    if not region_rows:
        return {"region_id": region_id, "available": False}

    region_rows.sort(key=lambda x: x.get("scene_date", ""))
    static = [r["static_capacity"] for r in region_rows]
    refined = [r["refined_capacity"] for r in region_rows]
    months = [r["month"] for r in region_rows]
    npp_vals = [r.get("npp", 0) for r in region_rows]

    avg_static = round(sum(static) / len(static)) if static else 0
    avg_refined = round(sum(refined) / len(refined)) if refined else 0
    avg_npp = round(sum(npp_vals) / len(npp_vals), 4) if npp_vals else 0

    return {
        "region_id": region_id,
        "available": True,
        "data_points": len(region_rows),
        "average_static": avg_static,
        "average_refined": avg_refined,
        "average_npp": avg_npp,
        "npp_data_source": "MOD17A3HGF v061",
        "static_series": [{"month": m, "value": v} for m, v in zip(months, static)],
        "refined_series": [{"month": m, "value": v} for m, v in zip(months, refined)],
        "details": region_rows,
    }


def summary() -> dict[str, Any]:
    all_calc = calculate_all()
    if not all_calc:
        return {"available": False}

    by_region: dict[str, list[dict]] = {}
    for r in all_calc:
        by_region.setdefault(r["region_id"], []).append(r)

    regions_summary = []
    for rid, rows in by_region.items():
        rows.sort(key=lambda x: x.get("scene_date", ""))
        ref_values = [r["refined_capacity"] for r in rows]
        static_values = [r["static_capacity"] for r in rows]
        npp_vals = [r.get("npp", 0) for r in rows]
        avg_ref = round(sum(ref_values) / len(ref_values))
        avg_sta = round(sum(static_values) / len(static_values))
        avg_npp = round(sum(npp_vals) / len(npp_vals), 4) if npp_vals else 0
        regions_summary.append({
            "region_id": rid,
            "data_points": len(rows),
            "static_capacity": avg_sta,
            "refined_avg": avg_ref,
            "refined_min": min(ref_values),
            "refined_max": max(ref_values),
            "npp_avg": avg_npp,
            "deviation_pct": round(
                abs(avg_ref - avg_sta) / max(1, avg_sta) * 100, 1
            ),
            "degradation_level": rows[0].get("degradation_level", ""),
        })

    all_refined = [r["refined_capacity"] for r in all_calc]
    all_static = [r["static_capacity"] for r in all_calc]

    return {
        "available": True,
        "total_data_points": len(all_calc),
        "region_count": len(by_region),
        "global_average_static": round(sum(all_static) / len(all_static)),
        "global_average_refined": round(sum(all_refined) / len(all_refined)),
        "npp_data_source": "MOD17A3HGF v061 (2001-2025)",
        "regions": regions_summary,
    }


# ═══════════════════════════════════════════════════════════════
#  v3 新增：逐日载畜量预测（未来 90 天）
# ═══════════════════════════════════════════════════════════════

import calendar as _calendar
from datetime import date as _date, timedelta as _td
from urllib.request import Request as _Request, urlopen as _urlopen
from urllib.parse import urlencode as _urlencode


def _load_monthly_ndvi(region_id: str) -> dict[int, float]:
    """从 remote_sensing_data.json 加载某县各月 NDVI 均值。"""
    path = _STORE_DIR / "remote_sensing_data.json"
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    monthly: dict[int, list[float]] = {}
    for r in rows:
        if r.get("region_id") != region_id:
            continue
        month, _ = _parse_month_and_year(r.get("scene_date", ""))
        if month is None:
            continue
        ndvi = _safe_float(r.get("ndvi"))
        if ndvi > 0:
            monthly.setdefault(month, []).append(ndvi)
    return {m: sum(v) / len(v) for m, v in monthly.items()}


def _interpolate_daily(values: dict[int, float], doy: int) -> float:
    """从每月一个值线性插值为逐日值。doy in [1, 365/366]."""
    import bisect
    months = sorted(values.keys())
    if not months:
        return 0.35
    # 每月 15 日对应的近似 DOY
    month_doy = {
        m: sum(_calendar.monthrange(2024, i)[1] for i in range(1, m)) + 15
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


def _daily_season_coef(doy: int, greenup_doy: float = 147, dormancy_doy: float = 288) -> float:
    """基于物候的逐日季节系数（平滑 sigmoid 曲线）。"""
    import math

    def sigmoid(x):
        return 1.0 / (1.0 + math.exp(-x))

    width = 15.0
    greenup_phase = sigmoid((doy - greenup_doy) / (width / 3))
    dormancy_phase = sigmoid((dormancy_doy - doy) / (width / 3))
    return 0.40 + 0.60 * min(greenup_phase, dormancy_phase)


def _fetch_daily_weather_forecast(lat: float, lon: float, start_date: str, days: int) -> list[dict]:
    """从 Open-Meteo 获取逐日天气预报（免费，最多 16 天）。"""
    try:
        forecast_days = min(days, 16)
        end_date = (_date.fromisoformat(start_date) + _td(days=forecast_days - 1)).isoformat()
        params = _urlencode({
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,snow_depth",
            "start_date": start_date,
            "end_date": end_date,
            "timezone": "Asia/Shanghai",
        })
        req = _Request(
            f"https://api.open-meteo.com/v1/forecast?{params}",
            headers={"User-Agent": "yak-risk-platform/1.0"},
        )
        with _urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        daily = payload.get("daily", {})
        dates = daily.get("time", [])
        result = []
        for i, d in enumerate(dates):
            sd = daily.get("snow_depth", [0] * len(dates))[i] or 0
            sf = daily.get("snowfall_sum", [0] * len(dates))[i] or 0
            result.append({
                "date": d,
                "temp_max": daily.get("temperature_2m_max", [None])[i],
                "temp_min": daily.get("temperature_2m_min", [None])[i],
                "precip_mm": daily.get("precipitation_sum", [0])[i] or 0,
                "snowfall_cm": sf / 10.0,
                "snow_depth_cm": sd / 100.0,
            })
        return result
    except Exception:
        return []


def predict_daily_capacity(
    region_id: str,
    start_date: str | None = None,
    days: int = 90,
) -> dict[str, Any]:
    """预测未来 N 天逐日载畜量。

    NPP 基准为年度预测值（不变），NDVI/季节/积雪/物候/退化每日变化。
    """
    if start_date is None:
        start_date = _date.today().isoformat()
    start = _date.fromisoformat(start_date)
    target_year = start.year

    _load_npp()
    _load_phenology()

    # NPP 基准
    annual = _npp_map.get(region_id, {})
    npp = annual.get(str(target_year))
    if npp is None:
        npp = _predict_npp(annual)
    npp_base = npp * 15000.0 + 5000.0

    # 退化系数 (行政等级)
    deg_level = "轻度退化"
    rs_path = _STORE_DIR / "remote_sensing_data.json"
    if rs_path.exists():
        rs_all = json.loads(rs_path.read_text(encoding="utf-8"))
        for r in rs_all:
            if r.get("region_id") == region_id:
                deg_level = r.get("degradation_level", deg_level)
                break
    deg_coef = _degradation_coef(deg_level)

    # Li 2025 GDI 风险标记 (不影响预测公式, 作为独立安全建议)
    gdi_factor = _gdi_warning_factor(region_id)
    gdi_risk = "高风险" if gdi_factor <= 0.80 else "中风险" if gdi_factor <= 0.90 else "低风险"
    gdi_advisory = (
        f"GDI 标记 {gdi_risk}, 建议在 {deg_level}(×{deg_coef}) 基础上额外降低 "
        f"{round((1 - gdi_factor) * 100)}% 放贷额度" if gdi_factor < 1.0
        else "GDI 未触发风险预警"
    )

    # 物候
    pheno_info = _pheno_map.get(region_id, {})
    stats = pheno_info.get("statistics", {})
    greenup_doy = stats.get("greenup_mean_doy", 147)
    dormancy_doy = stats.get("dormancy_mean_doy", 288)
    gs_mean = stats.get("growing_season_mean_days", 140)

    # 月度 NDVI
    monthly_ndvi = _load_monthly_ndvi(region_id)
    if not monthly_ndvi:
        monthly_ndvi = {
            1: 0.10, 2: 0.12, 3: 0.15, 4: 0.20, 5: 0.35,
            6: 0.55, 7: 0.65, 8: 0.60, 9: 0.45, 10: 0.25,
            11: 0.15, 12: 0.10,
        }

    # 天气预报
    county_coords = _load_county_coords()
    lat = county_coords.get(region_id, {}).get("lat", 31.36)
    lon = county_coords.get(region_id, {}).get("lon", 90.01)
    weather_forecast = _fetch_daily_weather_forecast(lat, lon, start_date, days)
    weather_by_date = {w["date"]: w for w in weather_forecast}

    # 逐日计算
    daily_results = []
    for offset in range(days):
        current = start + _td(days=offset)
        date_str = current.isoformat()
        doy = current.timetuple().tm_yday

        ndvi_daily = _interpolate_daily(monthly_ndvi, doy)
        ndvi_adj = 1.0 + (ndvi_daily - NDVI_BASELINE) / NDVI_BASELINE * NDVI_SENSITIVITY
        ndvi_adj = max(0.30, min(1.50, ndvi_adj))

        season_daily = _daily_season_coef(doy, greenup_doy, dormancy_doy)

        w = weather_by_date.get(date_str, {})
        snow_depth = w.get("snow_depth_cm", 0)
        snow_pct = min(100, snow_depth * 15)
        snow_daily = _snow_coef(snow_pct)

        days_from_greenup = doy - greenup_doy
        if days_from_greenup < 0:
            pheno_daily = 0.95
        elif days_from_greenup > dormancy_doy - greenup_doy:
            pheno_daily = 0.95
        else:
            pheno_daily = 1.0

        capacity = npp_base * ndvi_adj * season_daily * snow_daily * pheno_daily * deg_coef
        capacity = round(capacity)

        daily_results.append({
            "date": date_str,
            "doy": doy,
            "ndvi": round(ndvi_daily, 4),
            "ndvi_adj": round(ndvi_adj, 3),
            "season_coef": round(season_daily, 3),
            "snow_depth_cm": round(snow_depth, 1),
            "snow_coef": round(snow_daily, 3),
            "pheno_coef": round(pheno_daily, 3),
            "degradation_coef": deg_coef,
            "temp_max": w.get("temp_max"),
            "temp_min": w.get("temp_min"),
            "precip_mm": w.get("precip_mm"),
            "capacity": capacity,
        })

    caps = [d["capacity"] for d in daily_results]
    has_weather = len(weather_forecast) > 0

    return {
        "region_id": region_id,
        "target_year": target_year,
        "start_date": start_date,
        "end_date": (start + _td(days=days)).isoformat(),
        "days": days,
        "npp_base": round(npp_base),
        "npp_value": round(npp, 4),
        "npp_method": "实测" if annual.get(str(target_year)) else "近3年均值预测",
        "degradation_level": deg_level,
        "degradation_coef": round(deg_coef, 2),
        "gdi_risk": gdi_risk,
        "gdi_advisory": gdi_advisory,
        "phenology": {
            "greenup_mean_doy": round(greenup_doy, 1),
            "dormancy_mean_doy": round(dormancy_doy, 1),
            "growing_season_mean_days": round(gs_mean, 1),
        },
        "weather_available": has_weather,
        "weather_days": len(weather_forecast),
        "weather_source": "Open-Meteo 免费预报 (16天)" if has_weather else "无",
        "daily": daily_results,
        "statistics": {
            "capacity_min": min(caps),
            "capacity_max": max(caps),
            "capacity_mean": round(sum(caps) / len(caps)),
            "capacity_std": round(
                (sum((c - sum(caps) / len(caps)) ** 2 for c in caps) / len(caps)) ** 0.5
            ),
        },
    }


# 县坐标缓存
_county_coords_cache: dict[str, dict] = {}


def _load_county_coords() -> dict[str, dict]:
    """加载县域经纬度。"""
    global _county_coords_cache
    if _county_coords_cache:
        return _county_coords_cache
    csv_path = _STORE_DIR.parent / "public_data" / "region_list.csv"
    if csv_path.exists():
        import csv as _csv
        with open(csv_path, encoding="utf-8-sig") as f:
            for row in _csv.DictReader(f):
                rid = row.get("region_id", "")
                if rid:
                    _county_coords_cache[rid] = {
                        "lat": float(row.get("latitude", 31)),
                        "lon": float(row.get("longitude", 90)),
                    }
    return _county_coords_cache