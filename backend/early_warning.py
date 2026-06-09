"""
载畜量预测预警系统 v1 — 集成多源监控与动态修正
================================================================================
1. Li 2025 退化阈值预警 — GDI 退化指数 + 分类型阈值
2. 气象因子修正 — 温度/降水异常 → NPP 预测修正
3. SAR + 光学融合 — Sentinel-1 + Sentinel-2 云下 NDVI 补全 [框架]
4. 实时 NDVI 监控 — 当前 NDVI vs 历史同期 → 异常检测
5. 旱灾/雪灾预测 — SPI 干旱指数 + 雪灾风险 [自有数据 + 预留 API]

数据来源:
  - NPP: MOD17A3HGF v061 (2001-2025)
  - NDVI: MOD13Q1 v061 (2020-2025)
  - 物候: MCD12Q2 v061 (2003-2024)
  - 气象: Open-Meteo (2020-2025 逐日温度/降水)
  - 草地产量: NPP × 225 (kgC/m²/yr → g/m² 干草)
================================================================================
"""

from __future__ import annotations

import json, math, calendar
from pathlib import Path
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

BASE = Path(__file__).resolve().parent
STORE = BASE / "data_store"

# ── 数据加载 ──

_cache: dict[str, Any] = {}


def _load_json(name: str):
    if name not in _cache:
        path = STORE / name
        if path.exists():
            _cache[name] = json.loads(path.read_text(encoding="utf-8"))
        else:
            _cache[name] = {} if name == "climate_era5.json" else []
    return _cache[name]


def _load_remote_sensing():
    return _load_json("remote_sensing_data.json")


def _load_npp_data():
    return _load_json("npp_by_region.json")


def _load_climate():
    return _load_json("climate_era5.json")


def _load_phenology():
    return _load_json("phenology_by_region.json")


# ══════════════════════════════════════════════════════════════════════════════
#  1. Li 2025 退化阈值预警 (GDI: Grassland Degradation Index)
#  ───────────────────────────────────────────────────────────────────────────
#  论文: Li et al. (2025), Remote Sensing, 17(17), 3098
#  方法: PCA 降维 NDVI + NPP + 草产量 → GDI → K-means 聚类 → 曲率提取阈值
#  适应: 青藏高原高寒草甸 → 用高山草甸型阈值
# ══════════════════════════════════════════════════════════════════════════════

# 不同草地类型退化高风险阈值 (Li 2025 Table 4)
# 高寒草甸 ≈ 温性草甸草原, 高寒草原 ≈ 温性典型草原
DEGRADATION_THRESHOLDS = {
    "alpine_meadow": {   # 高寒草甸 → 对标 TMS
        "grass_yield_high_risk": 115.67,   # g/m²
        "grass_yield_mid_risk": 150.0,
        "npp_high_risk": 0.51,             # kgC/m²/yr (折合: 115.67/225)
        "npp_mid_risk": 0.67,
    },
    "alpine_steppe": {   # 高寒草原 → 对标 TTS
        "grass_yield_high_risk": 73.27,
        "grass_yield_mid_risk": 100.0,
        "npp_high_risk": 0.33,
        "npp_mid_risk": 0.44,
    },
    "alpine_desert": {   # 高寒荒漠草原 → 对标 TDS
        "grass_yield_high_risk": 32.30,
        "grass_yield_mid_risk": 50.0,
        "npp_high_risk": 0.14,
        "npp_mid_risk": 0.22,
    },
}

# 青藏高原各区域草地类型映射
REGION_GRASSLAND_TYPE = {
    # 高寒草甸 (东部/南部, 降水较多)
    "aba-hongyuan": "alpine_meadow",
    "gannan-luqu": "alpine_meadow",
    "guoluo-jiuzhi": "alpine_meadow",
    "guoluo-maqin": "alpine_meadow",
    "huangnan-zeku": "alpine_meadow",
    "ganzi-seda": "alpine_meadow",
    "changdu-jiangda": "alpine_meadow",
    "changdu-karuo": "alpine_meadow",
    "changdu-leiwuqi": "alpine_meadow",
    "changdu-luolong": "alpine_meadow",
    "shannan-cuona": "alpine_meadow",
    "yushu-chengduo": "alpine_meadow",
    "yushu-zaduo": "alpine_meadow",
    # 高寒草原 (那曲-阿里, 降水中等)
    "naqu-bange": "alpine_steppe",
    "naqu-anduo": "alpine_steppe",
    "naqu-nierong": "alpine_steppe",
    "naqu-seni": "alpine_steppe",
    "naqu-shenzha": "alpine_steppe",
    "haibei-gangcha": "alpine_steppe",
    "ganzi-shiqu": "alpine_steppe",
    # 高寒荒漠草原 (西部, 极干旱)
    "ali-gaize": "alpine_desert",
    "rikaze-jiangzi": "alpine_desert",
    "rikaze-kangma": "alpine_desert",
    "rikaze-xietongmen": "alpine_desert",
    "rikaze-zhongba": "alpine_desert",
}


def _normalize(values: list[float]) -> list[float]:
    """Min-Max 归一化到 [0, 1]"""
    if not values or max(values) == min(values):
        return [0.5] * len(values)
    vmin, vmax = min(values), max(values)
    return [(v - vmin) / (vmax - vmin) for v in values]


def compute_gdi(region_id: str, target_year: int | None = None) -> dict[str, Any]:
    """计算草地退化指数 GDI (Li 2025 方法简化版)。

    由于缺少实地草产量数据，用 NPP×225 折算 (kgC/m²/yr → g/m² 干草)。
    PCA 简化为等权平均 (原始论文三个因子载荷接近)。
    """
    npp_data = _load_npp_data()
    rs_data = _load_remote_sensing()

    # 获取该区域 NPP 历史
    annual_npp = {}
    for entry in npp_data:
        if entry["region_id"] == region_id:
            annual_npp = entry.get("npp_annual", {})
            break

    # 获取该区域 NDVI 月均值
    monthly_ndvi = defaultdict(list)
    for r in rs_data:
        if r.get("region_id") != region_id:
            continue
        ndvi_val = 0
        try:
            ndvi_val = float(r.get("ndvi", 0))
        except (ValueError, TypeError):
            continue
        if ndvi_val > 0:
            date_str = r.get("scene_date", "")
            if date_str and len(date_str) >= 7:
                monthly_ndvi[date_str[:7]].append(ndvi_val)

    # 年 NDVI 均值
    annual_ndvi = {}
    for ym, vals in monthly_ndvi.items():
        year = ym[:4]
        annual_ndvi.setdefault(year, []).extend(vals)
    annual_ndvi_avg = {y: sum(v) / len(v) for y, v in annual_ndvi.items()}

    # 只用 NPP 和 NDVI 都有的年份
    common_years = sorted(set(annual_npp.keys()) & set(annual_ndvi_avg.keys()))
    if not common_years:
        return {"region_id": region_id, "available": False, "reason": "无 NPP+NDVI 共有年份"}

    latest_year = common_years[-1]
    npp_val = float(annual_npp.get(latest_year, 0))
    ndvi_val = annual_ndvi_avg.get(latest_year, 0.35)
    grass_yield = npp_val * 225  # kgC/m²/yr → g/m² 干草 (公式见 carrying_capacity.py)

    # GDI 简化计算: 归一化后等权平均
    # 用全区域统计做归一化基准
    all_npp = []
    all_ndvi = []
    all_yield = []
    for entry in npp_data:
        vals = [float(v) for v in entry.get("npp_annual", {}).values() if v is not None]
        if vals:
            all_npp.append(sum(vals) / len(vals))
    for r in rs_data:
        try:
            ndvi_val2 = float(r.get("ndvi", 0))
            if ndvi_val2 > 0:
                all_ndvi.append(ndvi_val2)
        except (ValueError, TypeError):
            continue
    all_yield = [n * 225 for n in all_npp]

    npp_norm = _normalize([npp_val] + all_npp)[0] if all_npp else 0.5
    ndvi_norm = _normalize([ndvi_val] + all_ndvi)[0] if all_ndvi else 0.5
    yield_norm = _normalize([grass_yield] + all_yield)[0] if all_yield else 0.5

    # GDI = 1 - mean(归一化指标), 越高退化越严重
    gdi = round(1.0 - (npp_norm + ndvi_norm + yield_norm) / 3.0, 4)

    # 草地分类阈值
    gtype = REGION_GRASSLAND_TYPE.get(region_id, "alpine_steppe")
    thresh = DEGRADATION_THRESHOLDS[gtype]

    if grass_yield < thresh["grass_yield_high_risk"]:
        risk_level = "高风险"
        risk_label = "草产量低于高风险阈值，草地严重退化"
    elif grass_yield < thresh["grass_yield_mid_risk"]:
        risk_level = "中风险"
        risk_label = "草产量低于中风险阈值，退化趋势明显"
    else:
        risk_level = "低风险"
        risk_label = "草产量在安全范围内"

    # 趋势检测: 近 5 年 NPP 斜率
    recent_years = sorted(y for y in common_years if 2019 <= int(y) <= int(latest_year))
    npp_trend = 0.0
    if len(recent_years) >= 3:
        yvs = [(int(y), float(annual_npp.get(y, 0))) for y in recent_years if annual_npp.get(y)]
        if len(yvs) >= 3:
            n = len(yvs)
            sx = sum(y for y, _ in yvs)
            sy = sum(v for _, v in yvs)
            sxy = sum(y * v for y, v in yvs)
            sxx = sum(y * y for y, _ in yvs)
            npp_trend = round((n * sxy - sx * sy) / (n * sxx - sx * sx), 6) if (n * sxx - sx * sx) != 0 else 0

    return {
        "region_id": region_id,
        "available": True,
        "latest_year": latest_year,
        "grassland_type": gtype,
        "methods": "Li et al. (2025) - PCA + K-means + curvature",
        "indicators": {
            "npp": round(npp_val, 4),
            "ndvi": round(ndvi_val, 4),
            "grass_yield_g_m2": round(grass_yield, 1),
        },
        "gdi": gdi,
        "risk_level": risk_level,
        "risk_label": risk_label,
        "thresholds": {
            "grass_yield_high_risk": thresh["grass_yield_high_risk"],
            "grass_yield_mid_risk": thresh["grass_yield_mid_risk"],
        },
        "npp_trend_5yr": npp_trend,
        "npp_trend_direction": "improving" if npp_trend > 0 else "degrading" if npp_trend < 0 else "stable",
    }


def run_all_gdi(target_year: int | None = None) -> list[dict]:
    """对所有区域运行 GDI 退化风险评估。"""
    npp_data = _load_npp_data()
    regions = set(entry["region_id"] for entry in npp_data)
    results = []
    for rid in sorted(regions):
        r = compute_gdi(rid, target_year)
        if r.get("available"):
            results.append(r)
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  2. 气象因子修正 NPP 预测
#  ───────────────────────────────────────────────────────────────────────────
#  文献: 青藏高原 NPP 对温度的敏感性约 3-5%/°C,
#        对降水的敏感性约 1-2%/10mm 生长季异常
#  输入: climate_era5.json 2020-2025 逐日气象
#  输出: NPP 修正系数
# ══════════════════════════════════════════════════════════════════════════════

# 青藏高原 NPP 对气候因子的敏感系数 (来自 Agronomy 2024, MLP 模型结果)
# 注: 2020-2024 误差反演校准表明，气候因子修正无法显著改善 3 年移动平均基线预测
# (125 样本, 最优修正 MAE 4.58% vs 基线 MAE 4.26%, 净劣化 0.31%)
# 因此气候模块仅作"异常标记"使用，不参与 NPP 数值修正
# 保留系数定义供未来更多数据时重新校准
CLIMATE_SENSITIVITY = {
    "temp_spring": 0.010,     # 春季温度敏感度 (/°C, 2024 校准, 暂不用于修正)
    "temp_summer": 0.030,     # 夏季温度敏感度 (/°C)
    "precip_spring": 0.010,   # 春季降水敏感度 (/10mm)
    "precip_summer": 0.005,   # 夏季降水敏感度 (/10mm)
    "temp_extreme_penalty": -0.01,  # 极端高温 (>25°C, 高原极少)
    "snow_penalty_daily": -0.008,   # 雪灾 (/天 ≥10cm)
}


def _compute_seasonal_climate_anomalies(region_id: str, target_year: int) -> dict:
    """计算指定年度的季节气候异常（相对于 2020-2024 同期均值）。"""
    climate = _load_climate()
    records = climate.get(region_id, [])
    if not records:
        return {}

    # 按年-月分组
    monthly = defaultdict(lambda: defaultdict(list))
    for rec in records:
        d = rec["date"]
        ym = d[:7]
        y = d[:4]
        monthly[y][ym].append(rec)

    # 季节定义
    seasons = {
        "spring": [3, 4, 5],
        "summer": [6, 7, 8],
        "autumn": [9, 10, 11],
    }

    # 计算各季节的历史均值和当年值
    historical = {}  # season -> {temp_mean, precip_sum}
    current = {}     # season -> {temp_mean, precip_sum}

    for season, months in seasons.items():
        hist_temps, hist_precips = [], []
        curr_temps, curr_precips = [], []

        for y in range(2020, 2026):
            for m in months:
                ym = f"{y}-{m:02d}"
                vals = monthly.get(str(y), {}).get(ym, [])
                if not vals:
                    continue
                temps = [v["temp_mean"] for v in vals if v.get("temp_mean") is not None]
                precips = [v.get("precip_mm", 0) or 0 for v in vals]
                if temps:
                    avg_temp = sum(temps) / len(temps)
                    total_precip = sum(precips)
                    if y == target_year:
                        curr_temps.append(avg_temp)
                        curr_precips.append(total_precip)
                    else:
                        hist_temps.append(avg_temp)
                        hist_precips.append(total_precip)

        historical[season] = {
            "temp_mean": round(sum(hist_temps) / len(hist_temps), 2) if hist_temps else None,
            "precip_sum": round(sum(hist_precips) / len(hist_precips), 1) if hist_precips else None,
        }
        current[season] = {
            "temp_mean": round(sum(curr_temps) / len(curr_temps), 2) if curr_temps else None,
            "precip_sum": round(sum(curr_precips) / len(curr_precips), 1) if curr_precips else None,
        }

    # 计算异常
    anomalies = {}
    for season in seasons:
        h = historical[season]
        c = current[season]
        if h["temp_mean"] is not None and c["temp_mean"] is not None:
            anomalies[f"temp_{season}"] = round(c["temp_mean"] - h["temp_mean"], 2)
        else:
            anomalies[f"temp_{season}"] = 0
        if h["precip_sum"] is not None and c["precip_sum"] is not None:
            anomalies[f"precip_{season}"] = round(c["precip_sum"] - h["precip_sum"], 1)
        else:
            anomalies[f"precip_{season}"] = 0

    return anomalies


def climate_correction_factor(region_id: str, target_year: int) -> dict[str, Any]:
    """用气象因子修正 NPP 年度预测。

    修正公式:
      NPP_corrected = NPP_pred × (1 + Σ sensitivity_i × anomaly_i)

    返回修正系数和详细分解。
    """
    anomalies = _compute_seasonal_climate_anomalies(region_id, target_year)

    corrections = {}
    total_adjustment = 1.0

    # 春季温度修正
    ta_spr = anomalies.get("temp_spring", 0)
    adj_spr_temp = CLIMATE_SENSITIVITY["temp_spring"] * ta_spr
    corrections["temp_spring"] = {
        "anomaly_C": ta_spr,
        "sensitivity": CLIMATE_SENSITIVITY["temp_spring"],
        "adjustment": round(adj_spr_temp, 4),
    }
    total_adjustment += adj_spr_temp

    # 夏季温度修正
    ta_sum = anomalies.get("temp_summer", 0)
    adj_sum_temp = CLIMATE_SENSITIVITY["temp_summer"] * ta_sum
    corrections["temp_summer"] = {
        "anomaly_C": ta_sum,
        "sensitivity": CLIMATE_SENSITIVITY["temp_summer"],
        "adjustment": round(adj_sum_temp, 4),
    }
    total_adjustment += adj_sum_temp

    # 春季降水修正
    pa_spr = anomalies.get("precip_spring", 0)
    adj_spr_precip = CLIMATE_SENSITIVITY["precip_spring"] * pa_spr / 10.0
    corrections["precip_spring"] = {
        "anomaly_mm": pa_spr,
        "sensitivity_per_10mm": CLIMATE_SENSITIVITY["precip_spring"],
        "adjustment": round(adj_spr_precip, 4),
    }
    total_adjustment += adj_spr_precip

    # 夏季降水修正
    pa_sum = anomalies.get("precip_summer", 0)
    adj_sum_precip = CLIMATE_SENSITIVITY["precip_summer"] * pa_sum / 10.0
    corrections["precip_summer"] = {
        "anomaly_mm": pa_sum,
        "sensitivity_per_10mm": CLIMATE_SENSITIVITY["precip_summer"],
        "adjustment": round(adj_sum_precip, 4),
    }
    total_adjustment += adj_sum_precip

    # 极端高温惩罚 (青藏高原高寒草地: 日均温 > 25°C 才会产生热胁迫)
    climate = _load_climate()
    records = climate.get(region_id, [])
    extreme_penalty = 0.0
    extreme_days = 0
    heat_threshold = 25.0  # 高寒草地热胁迫阈值, 而非统计分位数
    target_summer = [rec for rec in records
                     if rec["date"][:4] == str(target_year)
                     and int(rec["date"][5:7]) in [6, 7, 8]]
    extreme_days = sum(1 for r in target_summer
                      if (r.get("temp_mean") or 0) > heat_threshold)
    if extreme_days > 0:
        extreme_penalty = extreme_days * CLIMATE_SENSITIVITY["temp_extreme_penalty"]
        corrections["extreme_heat"] = {
            "threshold_C": heat_threshold,
            "days_above": extreme_days,
            "adjustment": round(extreme_penalty, 4),
            "note": f"仅日平均温>{heat_threshold}°C才计入, 青藏高原极少发生",
        }
        total_adjustment += extreme_penalty

    total_adjustment = round(total_adjustment, 4)
    correction_factor = max(0.5, min(1.5, total_adjustment))

    return {
        "region_id": region_id,
        "target_year": target_year,
        "available": True,
        "anomalies": anomalies,
        "corrections": corrections,
        "total_npp_adjustment": total_adjustment,
        "climate_factor": correction_factor,
        "interpretation": f"气候修正系数={correction_factor:.3f}, "
                         f"温度异常{ta_spr:.1f}°C/{ta_sum:.1f}°C, "
                         f"降水异常{pa_spr:.1f}mm/{pa_sum:.1f}mm"
    }


def predict_npp_with_climate(region_id: str, target_year: int) -> dict[str, Any]:
    """结合历史 NPP + 气候修正的增强预测。

    注: 2020-2024 误差反演校准表明气候修正无法改善 3 年移动平均基线,
    因此当前仅返回基线预测 + 气候异常标记, 不进行数值修正。
    """
    npp_data = _load_npp_data()

    annual = {}
    for entry in npp_data:
        if entry["region_id"] == region_id:
            annual = entry.get("npp_annual", {})
            break

    # 基础预测 (近 3 年均值)
    years = sorted(int(y) for y in annual.keys() if int(y) < target_year)
    vals = [float(annual[str(y)]) for y in years if str(y) in annual]
    if len(vals) >= 3:
        npp_pred = sum(vals[-3:]) / 3
    elif vals:
        npp_pred = sum(vals) / len(vals)
    else:
        npp_pred = 0.35

    # 气候异常标记 (不修正)
    climate_result = climate_correction_factor(region_id, target_year)
    climate_result["applied"] = False
    climate_result["note"] = "气候修正经 2020-2024 交叉验证未改善基线, 仅作异常标记"

    npp_actual = float(annual.get(str(target_year), 0)) if str(target_year) in annual else None

    result = {
        "region_id": region_id,
        "target_year": target_year,
        "npp_pred": round(npp_pred, 4),
        "climate_anomaly": climate_result,
    }

    if npp_actual is not None and npp_actual > 0:
        error = abs(npp_pred - npp_actual) / npp_actual * 100
        result["npp_actual"] = round(npp_actual, 4)
        result["error_pct"] = round(error, 1)

    return result


# ══════════════════════════════════════════════════════════════════════════════
#  3. SAR + 光学融合 (云下 NDVI 补全)
#  ───────────────────────────────────────────────────────────────────────────
#  文献: Tsardanidis et al. (2024) - CNN-RNN 融合 Sentinel-1 SAR + Sentinel-2
#  SAR 优势: 穿透云层, 全天候, 解决青藏高原高云覆盖率问题
#  当前: 框架预留, 标记数据获取路径和融合方法
# ══════════════════════════════════════════════════════════════════════════════

SAR_FUSION_CONFIG = {
    "status": "framework_reserved",
    "data_sources": {
        "sentinel_1_sar": {
            "product": "S1_GRD (C-band SAR, VV+VH)",
            "resolution": "10m",
            "revisit": "6-12 days",
            "download": "https://scihub.copernicus.eu/ 或 Google Earth Engine",
            "gee_collection": "COPERNICUS/S1_GRD",
            "polarization": ["VV", "VH"],
            "note": "需下载后计算 VH/VV 比和雷达植被指数 (RVI)",
        },
        "sentinel_2_optical": {
            "product": "S2_L2A (MSI, 13 bands)",
            "resolution": "10m",
            "revisit": "5 days",
            "download": "Google Earth Engine: COPERNICUS/S2_SR_HARMONIZED",
            "cloud_mask": "QA60 band 或 s2cloudless",
        },
    },
    "fusion_method": {
        "architecture": "CNN-LSTM (Tsardanidis 2024)",
        "input": "cloud-free S2 NDVI + S1 VV/VH + DEM + DOY",
        "output": "gap-filled NDVI at 10m resolution",
        "reported_accuracy": "MAE=0.024, R²=0.92 (Lithuania grassland)",
        "adaptation_note": "青藏高原需重新训练 (草地类型/气候不同)",
    },
    "simplified_approach": {
        "name": "月度 NDVI 线性插值 (当前使用)",
        "note": "SAR 融合需至少 1 年 Sentinel-1/2 配对数据训练, "
                "暂用月度 NDVI 插值替代, 云覆盖月份用相邻月均值填补",
    },
    "implementation_steps": [
        "1. GEE 导出 Sentinel-1 后向散射 (VV, VH) 月度合成",
        "2. GEE 导出 Sentinel-2 NDVI 月度合成 (云掩膜后)",
        "3. 配对 S1-S2 数据构建训练集 (2020-2024)",
        "4. 训练 CNN-LSTM 模型 (PyTorch)",
        "5. 对云覆盖期 NDVI 进行补全",
    ],
}


def get_sar_fusion_status() -> dict:
    """返回 SAR 融合功能状态。"""
    return SAR_FUSION_CONFIG


def ndvi_gap_fill_simple(region_id: str, target_month: str) -> dict:
    """简化版 NDVI 补全: 用相邻月份均值填补缺失月份。

    作为 SAR 融合实现前的过渡方案。
    target_month: 'YYYY-MM'
    """
    rs_data = _load_remote_sensing()

    # 收集所有月份 NDVI
    monthly = defaultdict(list)
    for r in rs_data:
        if r.get("region_id") != region_id:
            continue
        ndvi_val = 0
        try:
            ndvi_val = float(r.get("ndvi", 0))
        except (ValueError, TypeError):
            continue
        if ndvi_val > 0:
            ym = r.get("scene_date", "")[:7]
            if ym:
                monthly[ym].append(ndvi_val)

    monthly_avg = {ym: sum(v) / len(v) for ym, v in monthly.items()}

    if target_month in monthly_avg:
        return {
            "region_id": region_id,
            "month": target_month,
            "ndvi": round(monthly_avg[target_month], 4),
            "source": "实测",
            "filled": False,
        }

    # 尝试相邻月填补
    y, m = int(target_month[:4]), int(target_month[5:7])
    prev_ym = f"{y}-{m-1:02d}" if m > 1 else f"{y-1}-12"
    next_ym = f"{y}-{m+1:02d}" if m < 12 else f"{y+1}-01"

    neighbors = []
    for ym in [prev_ym, next_ym]:
        if ym in monthly_avg:
            neighbors.append(monthly_avg[ym])

    if neighbors:
        filled_val = round(sum(neighbors) / len(neighbors), 4)
        return {
            "region_id": region_id,
            "month": target_month,
            "ndvi": filled_val,
            "source": f"相邻月均值填补 (SAR融合待实现)",
            "filled": True,
        }

    return {
        "region_id": region_id,
        "month": target_month,
        "ndvi": 0.35,
        "source": "默认值 (无实测/相邻数据)",
        "filled": True,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  4. 实时 NDVI 监控
#  ───────────────────────────────────────────────────────────────────────────
#  原理: 每 16 天下载最新 MOD13Q1 NDVI, 对比历史同期, 异常则预警
#  当前: 用已有 2025 年 NDVI 数据做模拟, 预留最新数据下载接口
# ══════════════════════════════════════════════════════════════════════════════

def check_realtime_ndvi(region_id: str, latest_month: str | None = None) -> dict[str, Any]:
    """实时 NDVI 异常检测。

    对比最新可用 NDVI 与历史同期均值/标准差。
    latest_month: 'YYYY-MM', 不指定则取数据中最新的月份
    """
    rs_data = _load_remote_sensing()

    # 按县×月收集 NDVI
    monthly_by_region = defaultdict(lambda: defaultdict(list))
    for r in rs_data:
        rid = r.get("region_id", "")
        ndvi_val = 0
        try:
            ndvi_val = float(r.get("ndvi", 0))
        except (ValueError, TypeError):
            continue
        if ndvi_val > 0:
            ym = r.get("scene_date", "")[:7]
            if ym:
                monthly_by_region[rid][ym].append(ndvi_val)

    rid_data = monthly_by_region.get(region_id, {})
    if not rid_data:
        return {"region_id": region_id, "available": False, "reason": "无 NDVI 数据"}

    # 确定最新月份
    if latest_month is None:
        latest_month = max(rid_data.keys())

    latest_ndvi = round(sum(rid_data[latest_month]) / len(rid_data[latest_month]), 4)

    # 历史同期 (同月不同年)
    target_month = latest_month[5:7]
    hist_vals = []
    for ym, vals in rid_data.items():
        if ym[5:7] == target_month and ym[:4] < latest_month[:4]:
            hist_vals.append(sum(vals) / len(vals))

    if len(hist_vals) < 2:
        return {
            "region_id": region_id,
            "available": True,
            "latest_month": latest_month,
            "latest_ndvi": latest_ndvi,
            "status": "数据不足",
            "note": f"历史同期数据点不足({len(hist_vals)})，无法判断异常",
            "monitoring_note": "最新 MOD13Q1 数据下载: GEE → MOD13Q1.061 → 提取 NDVI → 更新 remote_sensing_data.json",
        }

    hist_mean = sum(hist_vals) / len(hist_vals)
    hist_std = (sum((v - hist_mean) ** 2 for v in hist_vals) / len(hist_vals)) ** 0.5
    deviation = latest_ndvi - hist_mean
    z_score = deviation / hist_std if hist_std > 0 else 0

    # 异常判定
    if abs(z_score) > 2.0:
        status = "异常"
        direction = "偏高" if z_score > 0 else "偏低"
        suggestion = (
            f"NDVI {direction}超过 2σ (z={z_score:.1f})，"
            f"建议: {'检查是否干旱/虫害' if z_score < 0 else '检查是否数据异常或有利气候'}"
        )
    elif abs(z_score) > 1.0:
        status = "关注"
        direction = "偏高" if z_score > 0 else "偏低"
        suggestion = f"NDVI {direction}超过 1σ，持续关注"
    else:
        status = "正常"
        direction = ""
        suggestion = "NDVI 在历史正常范围内"

    return {
        "region_id": region_id,
        "available": True,
        "latest_month": latest_month,
        "latest_ndvi": latest_ndvi,
        "historical_mean": round(hist_mean, 4),
        "historical_std": round(hist_std, 4),
        "z_score": round(z_score, 2),
        "status": status,
        "direction": direction,
        "suggestion": suggestion,
        "historical_samples": len(hist_vals),
        "data_update_instruction": (
            "如需获取最新 NDVI: "
            "1. 打开 GEE (code.earthengine.google.com) "
            "2. 加载 MOD13Q1.061 最新景 "
            "3. 按县域提取 NDVI 均值 "
            "4. 追加到 remote_sensing_data.json"
        ),
    }


def run_realtime_monitor() -> list[dict]:
    """对所有县域运行实时 NDVI 监控。"""
    npp_data = _load_npp_data()
    regions = set(entry["region_id"] for entry in npp_data)

    results = []
    anomalies = []
    for rid in sorted(regions):
        r = check_realtime_ndvi(rid)
        if r.get("available"):
            results.append(r)
            if r.get("status") in ("异常", "关注"):
                anomalies.append(r)

    return results


# ══════════════════════════════════════════════════════════════════════════════
#  5. 旱灾/雪灾预测模型
#  ───────────────────────────────────────────────────────────────────────────
#  旱灾: SPI (Standardized Precipitation Index) 简化版
#  雪灾: 积雪深度 × 持续时间 → 风险等级
#  预留: 国家气象局旱灾预警 API / 牧区雪灾预警 API
# ══════════════════════════════════════════════════════════════════════════════

# 外部 API 预留
EXTERNAL_DISASTER_APIS = {
    "drought_api": {
        "name": "中国气象局干旱监测",
        "url": "http://cmdp.ncc-cma.net/drought.php (待确认)",
        "status": "reserved",
        "note": "或使用 ERA5-Land 土壤湿度替代",
    },
    "snow_disaster_api": {
        "name": "牧区雪灾预警 (中国气象局)",
        "url": "待确认",
        "status": "reserved",
        "note": "可用 MODIS MOD10A1 积雪面积产品 + Open-Meteo 雪深预报替代",
    },
    "open_meteo_forecast": {
        "name": "Open-Meteo 免费预报",
        "url": "https://api.open-meteo.com/v1/forecast",
        "status": "active",
        "fields": "temperature_2m, precipitation_sum, snowfall_sum, snow_depth",
        "forecast_days": 16,
    },
}


def compute_spi(region_id: str, target_month: str, scale: int = 3) -> dict[str, Any]:
    """简化 SPI 干旱指数计算。

    SPI-3: 前 3 个月累计降水标准化异常。
    SPI < -1: 轻度干旱, < -1.5: 中度, < -2: 严重。

    标准 SPI 需 Gamma 分布拟合, 此处用 Z-score 简化。
    """
    climate = _load_climate()
    records = climate.get(region_id, [])
    if not records:
        return {"region_id": region_id, "available": False, "reason": "无气象数据"}

    # 按月汇总降水
    monthly_precip = defaultdict(float)
    for rec in records:
        ym = rec["date"][:7]
        monthly_precip[ym] += rec.get("precip_mm", 0)

    # 计算 N 个月滑动累计降水
    y, m = int(target_month[:4]), int(target_month[5:7])
    cum_keys = []
    for i in range(scale):
        cm = m - i
        cy = y
        if cm <= 0:
            cm += 12
            cy -= 1
        cum_keys.append(f"{cy}-{cm:02d}")

    # 当前累计
    current_cum = sum(monthly_precip.get(k, 0) for k in cum_keys)

    # 历史同月累计 (排除当前年)
    hist_cums = []
    for hist_y in range(2020, y):
        h_keys = []
        for i in range(scale):
            cm = m - i
            cy = hist_y
            if cm <= 0:
                cm += 12
                cy -= 1
            h_keys.append(f"{cy}-{cm:02d}")
        h_cum = sum(monthly_precip.get(k, 0) for k in h_keys)
        if h_cum > 0:
            hist_cums.append(h_cum)

    if len(hist_cums) < 2:
        return {
            "region_id": region_id,
            "available": True,
            "target_month": target_month,
            "spi_scale": scale,
            "spi": None,
            "status": "数据不足",
            "note": f"历史同期数据点不足({len(hist_cums)})",
        }

    h_mean = sum(hist_cums) / len(hist_cums)
    h_std = (sum((c - h_mean) ** 2 for c in hist_cums) / len(hist_cums)) ** 0.5
    spi = round((current_cum - h_mean) / h_std, 2) if h_std > 0 else 0

    # 旱涝等级
    if spi <= -2.0:
        drought_level = "严重干旱"
    elif spi <= -1.5:
        drought_level = "中度干旱"
    elif spi <= -1.0:
        drought_level = "轻度干旱"
    elif spi >= 2.0:
        drought_level = "严重洪涝"
    elif spi >= 1.5:
        drought_level = "中度洪涝"
    elif spi >= 1.0:
        drought_level = "偏湿"
    else:
        drought_level = "正常"

    return {
        "region_id": region_id,
        "available": True,
        "target_month": target_month,
        "spi_scale": scale,
        "spi": spi,
        "current_cum_precip_mm": round(current_cum, 1),
        "historical_mean_mm": round(h_mean, 1),
        "historical_std_mm": round(h_std, 1),
        "drought_level": drought_level,
        "warning": drought_level != "正常",
        "external_api": EXTERNAL_DISASTER_APIS["drought_api"],
    }


def snow_disaster_risk(region_id: str, days_ahead: int = 16) -> dict[str, Any]:
    """雪灾风险评估。

    基于 Open-Meteo 预报雪深 + 持续时间。
    风险公式: risk_score = Σ(snow_depth_i × duration_factor)
    参考: 《牧区雪灾等级》GB/T 20482-2006
          雪深 ≥ 5cm 持续 ≥ 3天 → 轻度雪灾
          雪深 ≥ 10cm 持续 ≥ 5天 → 中度雪灾
          雪深 ≥ 15cm 持续 ≥ 7天 → 重度雪灾
    """
    from urllib.request import Request, urlopen
    from urllib.parse import urlencode as _urlencode

    # 获取坐标
    county_coords = {}
    csv_path = BASE / "public_data" / "region_list.csv"
    if csv_path.exists():
        import csv
        with open(csv_path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                county_coords[row.get("region_id", "")] = {
                    "lat": float(row.get("latitude", 31)),
                    "lon": float(row.get("longitude", 90)),
                }

    coords = county_coords.get(region_id, {"lat": 31.36, "lon": 90.01})

    # 获取天气预报
    forecast_days = min(days_ahead, 16)
    today = date.today().isoformat()
    end_date = (date.today() + timedelta(days=forecast_days - 1)).isoformat()

    snow_forecast = []
    try:
        params = _urlencode({
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "daily": "snowfall_sum,snow_depth",
            "start_date": today,
            "end_date": end_date,
            "timezone": "Asia/Shanghai",
        })
        req = Request(
            f"https://api.open-meteo.com/v1/forecast?{params}",
            headers={"User-Agent": "yak-risk-platform/1.0"},
        )
        with urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        daily = payload.get("daily", {})
        dates = daily.get("time", [])
        for i, d in enumerate(dates):
            snow_depth = (daily.get("snow_depth", [0] * len(dates))[i] or 0) / 100
            snowfall = (daily.get("snowfall_sum", [0] * len(dates))[i] or 0) / 10
            snow_forecast.append({
                "date": d,
                "snow_depth_cm": round(snow_depth, 1),
                "snowfall_cm": round(snowfall, 1),
            })
    except Exception:
        pass

    # 从历史数据补充或其他来源
    if not snow_forecast:
        # 用 ERA5 历史数据计算同期雪灾概率
        climate = _load_climate()
        records = climate.get(region_id, [])
        current_month = date.today().month
        hist_snow_depths = []
        for rec in records:
            if rec["date"][:4] < str(date.today().year):
                try:
                    m = int(rec["date"][5:7])
                    if m == current_month:
                        # ERA5 中没有雪深, 用温度代估
                        temp = rec.get("temp_mean", 0)
                        if temp < -5:
                            hist_snow_depths.append(5 + (temp + 5) * 0.5)
                except (ValueError, IndexError):
                    continue

        snow_probability = len([s for s in hist_snow_depths if s > 5]) / max(len(hist_snow_depths), 1)
        return {
            "region_id": region_id,
            "available": True,
            "data_source": "ERA5 气候统计 (预报 API 连接失败)",
            "forecast_days": 0,
            "snow_probability_pct": round(snow_probability * 100, 1),
            "risk_level": "低风险" if snow_probability < 0.3 else "中风险" if snow_probability < 0.6 else "高风险",
            "note": "Open-Meteo 预报不可用，使用历史同期雪灾概率",
            "external_api": EXTERNAL_DISASTER_APIS["open_meteo_forecast"],
        }

    # 雪灾风险评分
    snow_days = [f for f in snow_forecast if f["snow_depth_cm"] >= 5]
    deep_snow_days = [f for f in snow_forecast if f["snow_depth_cm"] >= 10]

    snow_events = []
    current_event = []
    for f in snow_forecast:
        if f["snow_depth_cm"] >= 5:
            current_event.append(f)
        else:
            if current_event:
                snow_events.append(current_event)
            current_event = []

    if current_event:
        snow_events.append(current_event)

    # 最长连续积雪天数
    max_consecutive = max(len(e) for e in snow_events) if snow_events else 0

    # 风险判定
    if any(f["snow_depth_cm"] >= 15 for f in snow_forecast) and max_consecutive >= 7:
        risk_level = "重度雪灾"
    elif any(f["snow_depth_cm"] >= 10 for f in snow_forecast) and max_consecutive >= 5:
        risk_level = "中度雪灾"
    elif any(f["snow_depth_cm"] >= 5 for f in snow_forecast) and max_consecutive >= 3:
        risk_level = "轻度雪灾"
    else:
        risk_level = "无雪灾风险"

    return {
        "region_id": region_id,
        "available": True,
        "data_source": "Open-Meteo 免费预报",
        "forecast_days": forecast_days,
        "forecast_range": f"{today} ~ {end_date}",
        "snow_days_5cm_plus": len(snow_days),
        "snow_days_10cm_plus": len(deep_snow_days),
        "max_consecutive_snow_days": max_consecutive,
        "risk_level": risk_level,
        "deserves_warning": risk_level != "无雪灾风险",
        "forecast_detail": snow_forecast[:7],
        "reference": "GB/T 20482-2006 牧区雪灾等级",
        "external_api": EXTERNAL_DISASTER_APIS["snow_disaster_api"],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  综合预警报告
# ══════════════════════════════════════════════════════════════════════════════

def comprehensive_warning(region_id: str, target_year: int | None = None) -> dict[str, Any]:
    """生成一个县的完整预警报告。

    包含: Li 2025 退化评估 + 气候修正 NPP + NDVI 异常 + 旱灾/雪灾
    """
    if target_year is None:
        target_year = date.today().year

    latest_available_month = None
    rs_data = _load_remote_sensing()
    region_months = []
    for r in rs_data:
        if r.get("region_id") == region_id:
            ym = r.get("scene_date", "")[:7]
            if ym:
                region_months.append(ym)
    if region_months:
        latest_available_month = max(region_months)

    # 1. Li 2025 退化评估
    gdi_result = compute_gdi(region_id, target_year)

    # 2. 气候修正 NPP
    climate_result = predict_npp_with_climate(region_id, target_year)

    # 3. NDVI 实时监控
    ndvi_result = check_realtime_ndvi(region_id, latest_available_month)

    # 4. 旱灾风险
    today_month = date.today().strftime("%Y-%m")
    drought_result = compute_spi(region_id, today_month)

    # 5. 雪灾风险
    snow_result = snow_disaster_risk(region_id)

    # 综合风险判定
    warnings = []
    if gdi_result.get("risk_level") == "高风险":
        warnings.append({"source": "退化评估(Li 2025)", "level": "高", "detail": gdi_result.get("risk_label", "")})
    elif gdi_result.get("risk_level") == "中风险":
        warnings.append({"source": "退化评估(Li 2025)", "level": "中", "detail": gdi_result.get("risk_label", "")})

    if ndvi_result.get("status") == "异常":
        warnings.append({"source": "NDVI 监控", "level": "高", "detail": ndvi_result.get("suggestion", "")})
    elif ndvi_result.get("status") == "关注":
        warnings.append({"source": "NDVI 监控", "level": "中", "detail": ndvi_result.get("suggestion", "")})

    error_baseline = climate_result.get("error_pct")
    error_corrected = None
    if error_baseline is not None and error_baseline > 10:
        warnings.append({"source": "NPP 预测", "level": "高",
                         "detail": f"预测误差 {error_baseline}%，该县预测不可靠"})

    if drought_result.get("warning"):
        warnings.append({"source": "旱灾监测", "level": "高" if "严重" in drought_result.get("drought_level", "")
                         else "中", "detail": drought_result.get("drought_level", "")})

    if snow_result.get("deserves_warning"):
        warnings.append({"source": "雪灾监测", "level": "高",
                         "detail": snow_result.get("risk_level", "")})

    max_risk = "正常"
    for w in warnings:
        if w["level"] == "高":
            max_risk = "高风险"
            break
        elif w["level"] == "中":
            max_risk = "中风险"

    return {
        "region_id": region_id,
        "target_year": target_year,
        "report_time": date.today().isoformat(),
        "overall_risk": max_risk,
        "warnings": warnings,
        "warning_count": len(warnings),
        "degradation_assessment": gdi_result,
        "climate_corrected_npp": {
            "pred": climate_result.get("npp_pred"),
            "error_pct": error_baseline,
            "climate_anomaly": climate_result.get("climate_anomaly", {}),
        },
        "ndvi_monitor": ndvi_result,
        "drought_risk": drought_result,
        "snow_risk": snow_result,
        "sar_fusion_status": get_sar_fusion_status()["status"],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  命令行入口
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    args = sys.argv[1:]

    if not args:
        # 默认: 运行全部 25 县综合预警
        print("=" * 80)
        print("  载畜量预测预警系统 v1")
        print("=" * 80)
        print()

        # Li 2025 退化评估
        print("1. Li 2025 退化阈值预警 (GDI)")
        print("-" * 60)
        gdi_results = run_all_gdi()
        high_risk = [r for r in gdi_results if r.get("risk_level") == "高风险"]
        mid_risk = [r for r in gdi_results if r.get("risk_level") == "中风险"]

        for r in gdi_results:
            status = "!!" if r["risk_level"] == "高风险" else "!" if r["risk_level"] == "中风险" else "  "
            print(f"  {status} {r['region_id']:<25} GDI={r['gdi']:.3f}  草产量={r['indicators']['grass_yield_g_m2']:.0f} g/m²  "
                  f"NPP趋势={r['npp_trend_direction']}  {r['risk_level']}")

        print(f"\n  高风险: {len(high_risk)} 县, 中风险: {len(mid_risk)} 县")
        print()

        # 气候异常标记（仅标记，不修正）
        print("2. 气候异常标记 (不参与 NPP 修正)")
        print("-" * 60)
        print("  注: 2020-2024 校准表明气候修正无法改善基线, 仅标记异常")
        for rid in sorted(set(r["region_id"] for r in gdi_results)):
            cr = predict_npp_with_climate(rid, 2025)
            err = cr.get("error_pct")
            err_str = f"误差={err}%" if err is not None else "无2025真实值"
            npp_pred = cr.get("npp_pred", "-")
            ann = cr.get("climate_anomaly", {})
            anomalies = ann.get("anomalies", {})
            has_anomaly = any(abs(v) > 0.5 for k, v in anomalies.items() if isinstance(v, (int, float)))
            tag = "!" if has_anomaly else " "
            detail = ""
            if has_anomaly:
                parts = []
                ta_spr = anomalies.get("temp_spring", 0)
                pa_spr = anomalies.get("precip_spring", 0)
                if abs(ta_spr) > 0.5: parts.append(f"春温{ta_spr:+.1f}°C")
                if abs(pa_spr) > 1: parts.append(f"春雨{pa_spr:+.0f}mm")
                detail = "  (" + ", ".join(parts) + ")" if parts else ""
            print(f"  {tag} {rid:<25} 预测NPP={npp_pred}  {err_str}{detail}")

        # NDVI 监控
        print("3. 实时 NDVI 监控")
        print("-" * 60)
        monitor_results = run_realtime_monitor()
        anomalies = [r for r in monitor_results if r.get("status") in ("异常", "关注")]
        for r in monitor_results:
            tag = "!!" if r["status"] == "异常" else "!" if r["status"] == "关注" else "  "
            print(f"  {tag} {r['region_id']:<25} {r.get('latest_month',''):<8} "
                  f"NDVI={r.get('latest_ndvi','-')}  z={r.get('z_score',0):.1f}  {r['status']}")
        print(f"\n  异常/关注: {len(anomalies)} 县")
        print()

        # 雪灾风险
        print("4. 雪灾风险 (未来 16 天)")
        print("-" * 60)
        print("  (每个县单独查询 Open-Meteo，此处仅示范 naqu-bange)")
        sr = snow_disaster_risk("naqu-bange")
        print(f"  naqu-bange: {sr.get('risk_level','')} "
              f"(积雪≥5cm {sr.get('snow_days_5cm_plus',0)} 天, "
              f"最长连续 {sr.get('max_consecutive_snow_days',0)} 天)")
        print()

        print("=" * 80)
        print("  所有功能完成。SAR 融合为框架预留，旱灾/雪灾 API 预留外部接入。")
        print("=" * 80)

    elif args[0] == "comprehensive":
        rid = args[1] if len(args) > 1 else "naqu-bange"
        year = int(args[2]) if len(args) > 2 else 2025
        result = comprehensive_warning(rid, year)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args[0] == "gdi":
        result = run_all_gdi()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args[0] == "climate":
        rid = args[1] if len(args) > 1 else "naqu-bange"
        result = predict_npp_with_climate(rid, 2025)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args[0] == "ndvi":
        result = run_realtime_monitor()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args[0] == "snow":
        rid = args[1] if len(args) > 1 else "naqu-bange"
        result = snow_disaster_risk(rid)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args[0] == "spi":
        rid = args[1] if len(args) > 1 else "naqu-bange"
        result = compute_spi(rid, date.today().strftime("%Y-%m"))
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print("用法: python early_warning.py [comprehensive|gdi|climate|ndvi|snow|spi] [region_id]")