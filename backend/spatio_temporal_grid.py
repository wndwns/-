"""
牧融绿链 - 时空网格模型
================================================================
从"月度聚合"升级为"时空网格"模型。

样本结构: 25 县 × 3 类草场 × 4 季节 × 5 年龄段 = 1500 个时空网格

每个网格有独立的:
  - NDVI (按草场类型×季节)
  - 产草量 (按草场类型×季节×退化)
  - 饲草需求 (按年龄段×季节)
  - 气象风险 (按季节×草场脆弱性)
  - 载畜能力 (按草场类型×季节×年龄段)
  - 经济价值 (按年龄段)

设计依据:
  - 草场类型: early_warning.py REGION_GRASSLAND_TYPE + Li 2025 退化阈值
  - 季节系数: carrying_capacity.py _season_coef (复用)
  - 年龄段: 畜牧学经验值 (牦牛饲养标准)
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

_STORE_DIR = Path(__file__).resolve().parent / "data_store"
_REGION_LIST = Path(__file__).resolve().parents[1] / "public_data" / "region_list.csv"


# ══════════════════════════════════════════════════════════════════════════════
#  维度定义
# ══════════════════════════════════════════════════════════════════════════════

# 3 类草场
GRASSLAND_TYPES = ["alpine_meadow", "alpine_steppe", "alpine_desert"]
GRASSLAND_NAMES = {
    "alpine_meadow": "高寒草甸",
    "alpine_steppe": "高寒草原",
    "alpine_desert": "高寒荒漠",
}

# 草场类型的基础生产力系数 (相对值, 基于李 2025 阈值)
GRASSLAND_PRODUCTIVITY = {
    "alpine_meadow": 1.00,   # 草产量 ~150 g/m²
    "alpine_steppe": 0.55,   # 草产量 ~80 g/m²
    "alpine_desert": 0.25,   # 草产量 ~35 g/m²
}

# 草场脆弱性系数 (荒漠 > 草原 > 草甸, 越脆弱气象风险越大)
GRASSLAND_VULNERABILITY = {
    "alpine_meadow": 0.70,
    "alpine_steppe": 1.00,
    "alpine_desert": 1.40,
}

# 4 季节 (青藏高原牧草生长季)
SEASONS = ["spring", "summer", "autumn", "winter"]
SEASON_NAMES = {
    "spring": "春季 (4-6月)",
    "summer": "夏季 (7-9月)",
    "autumn": "秋季 (10-11月)",
    "winter": "冬季 (12-3月)",
}
SEASON_MONTHS = {
    "spring": [4, 5, 6],
    "summer": [7, 8, 9],
    "autumn": [10, 11],
    "winter": [12, 1, 2, 3],
}

# 季节系数 (复用 carrying_capacity.py 的 _season_coef 逻辑)
SEASON_COEF = {
    "spring": 0.78,   # (0.70+0.85+1.00)/3 ≈ 返青期
    "summer": 1.00,   # 盛草期
    "autumn": 0.62,   # (0.70+0.55)/2 ≈ 枯草期
    "winter": 0.40,   # 休牧期
}

# 季节气象风险系数 (冬季雪灾/春季干旱/秋季霜冻)
SEASON_WEATHER_RISK = {
    "spring": 1.20,   # 春旱 + 倒春寒
    "summer": 0.60,   # 气候最适宜
    "autumn": 0.90,   # 早霜
    "winter": 1.60,   # 雪灾/寒潮最高
}

# 5 年龄段 (牦牛饲养标准)
AGE_GROUPS = ["calf", "yearling", "young", "adult", "old"]
AGE_NAMES = {
    "calf": "犊牛 (0-1岁)",
    "yearling": "育成牛 (1-2岁)",
    "young": "青年牛 (2-3岁)",
    "adult": "成年牛 (3-5岁)",
    "old": "老龄牛 (5+岁)",
}

# 年龄段系数: (饲草需求, 抗灾能力, 经济价值, 载畜折算)
# 数据来源: 牦牛饲养学 (青藏高原畜牧业标准)
AGE_COEF = {
    #              饲草需求  抗灾能力  经济价值  载畜折算(羊单位)
    "calf":      (0.30,    0.40,    0.20,    0.3),   # 需求低, 抗灾弱, 价值低
    "yearling":  (0.55,    0.60,    0.50,    0.5),   # 需求中, 抗灾中, 价值中
    "young":     (0.75,    0.75,    0.80,    0.7),   # 需求中高, 抗灾中高
    "adult":     (1.00,    1.00,    1.00,    1.0),   # 基准: 需求高, 抗灾强, 价值高
    "old":       (0.90,    0.50,    0.60,    0.9),   # 需求高但抗灾弱, 价值下降
}


# ══════════════════════════════════════════════════════════════════════════════
#  数据加载
# ══════════════════════════════════════════════════════════════════════════════

def _load_json(name: str) -> Any:
    p = _STORE_DIR / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return []


def _load_region_list() -> list[dict]:
    if not _REGION_LIST.exists():
        return []
    rows = []
    with open(_REGION_LIST, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


# ══════════════════════════════════════════════════════════════════════════════
#  草场类型比例分配
# ══════════════════════════════════════════════════════════════════════════════

# 从 early_warning.py 复用区域→草场类型映射
_REGION_GRASSLAND_TYPE = {
    "aba-hongyuan": "alpine_meadow", "gannan-luqu": "alpine_meadow",
    "guoluo-jiuzhi": "alpine_meadow", "guoluo-maqin": "alpine_meadow",
    "huangnan-zeku": "alpine_meadow", "ganzi-seda": "alpine_meadow",
    "changdu-jiangda": "alpine_meadow", "changdu-karuo": "alpine_meadow",
    "changdu-leiwuqi": "alpine_meadow", "changdu-luolong": "alpine_meadow",
    "shannan-cuona": "alpine_meadow", "yushu-chengduo": "alpine_meadow",
    "yushu-zaduo": "alpine_meadow",
    "naqu-bange": "alpine_steppe", "naqu-anduo": "alpine_steppe",
    "naqu-nierong": "alpine_steppe", "naqu-seni": "alpine_steppe",
    "naqu-shenzha": "alpine_steppe", "haibei-gangcha": "alpine_steppe",
    "ganzi-shiqu": "alpine_steppe",
    "ali-gaize": "alpine_desert", "rikaze-jiangzi": "alpine_desert",
    "rikaze-kangma": "alpine_desert",
    "rikaze-xietongmen": "alpine_desert", "rikaze-zhongba": "alpine_desert",
    "linzhi-bayi": "alpine_meadow",
}

# 主类型 → 3 类草场的面积比例 (经验值)
_GRASSLAND_MIX = {
    "alpine_meadow":  {"alpine_meadow": 0.70, "alpine_steppe": 0.20, "alpine_desert": 0.10},
    "alpine_steppe":  {"alpine_meadow": 0.20, "alpine_steppe": 0.60, "alpine_desert": 0.20},
    "alpine_desert":  {"alpine_meadow": 0.10, "alpine_steppe": 0.30, "alpine_desert": 0.60},
}


def _grassland_ratio(region_id: str) -> dict[str, float]:
    """获取某县 3 类草场的面积比例。"""
    main_type = _REGION_GRASSLAND_TYPE.get(region_id, "alpine_steppe")
    return _GRASSLAND_MIX[main_type]


# ══════════════════════════════════════════════════════════════════════════════
#  网格构建
# ══════════════════════════════════════════════════════════════════════════════

def _get_npp(region_id: str, npp_data: list[dict]) -> float:
    """获取某县最新年 NPP。"""
    for item in npp_data:
        if item.get("region_id") == region_id:
            annual = item.get("npp_annual", {})
            if annual:
                latest = max(annual.keys())
                val = annual.get(latest)
                if val is not None:
                    return float(val)
    return 0.15  # 默认值


def _get_ndvi(region_id: str, remote_data: list[dict]) -> float:
    """获取某县最新 NDVI。"""
    vals = []
    for r in remote_data:
        if r.get("region_id") == region_id:
            try:
                v = float(r.get("ndvi", 0))
                if v > 0:
                    vals.append(v)
            except (ValueError, TypeError):
                pass
    return float(np.mean(vals[-3:])) if vals else 0.35


def _get_degradation(region_id: str, remote_data: list[dict]) -> str:
    """获取某县退化等级。"""
    for r in reversed(remote_data):
        if r.get("region_id") == region_id:
            deg = r.get("degradation_level", "轻度退化")
            if deg and deg != "待评估":
                return deg
    return "轻度退化"


_DEG_COEF = {"基本稳定": 1.0, "轻度退化": 0.8, "中度退化": 0.6, "重度退化": 0.4, "极重度退化": 0.25}


def _get_weather_risk(region_id: str, weather_data: list[dict], season: str) -> tuple[float, str]:
    """获取某县某季节的气象风险 (0-100) 和主要风险类型。"""
    months = SEASON_MONTHS[season]
    risks = []
    risk_types = []

    for w in weather_data:
        if w.get("region_id") != region_id:
            continue
        obs = w.get("observed_at", "")
        try:
            m = int(obs[5:7]) if len(obs) >= 7 else 0
        except (ValueError, IndexError):
            continue
        if m not in months:
            continue

        for risk_field, risk_name in [("cold_wave_risk", "寒潮"), ("snowstorm_risk", "暴雪"), ("drought_risk", "干旱")]:
            val = w.get(risk_field, "低")
            if val == "高":
                risks.append(2)
                risk_types.append(risk_name)
            elif val == "中":
                risks.append(1)

    if not risks:
        return 30.0 * SEASON_WEATHER_RISK[season], "低风险"

    max_risk = max(risks)
    score = max_risk * 35
    score *= SEASON_WEATHER_RISK[season]
    score = min(100, score)

    main_risk = max(set(risk_types), key=risk_types.count) if risk_types else "低风险"
    return score, main_risk


def build_grid(region_id: str) -> dict[str, Any]:
    """构建某县的时空网格 (3×4×5 = 60 个网格)。"""
    region_list = _load_region_list()
    npp_data = _load_json("npp_by_region")
    remote_data = _load_json("remote_sensing_data")
    weather_data = _load_json("weather_data")

    # 县域元数据
    region_info = None
    for r in region_list:
        if r["region_id"].strip() == region_id:
            region_info = r
            break
    region_name = region_info.get("region_name", region_id) if region_info else region_id

    # 基础数据
    npp = _get_npp(region_id, npp_data)
    ndvi = _get_ndvi(region_id, remote_data)
    deg_level = _get_degradation(region_id, remote_data)
    deg_coef = _DEG_COEF.get(deg_level, 0.8)
    grass_ratio = _grassland_ratio(region_id)

    grids = []
    for gl_type in GRASSLAND_TYPES:
        ratio = grass_ratio[gl_type]
        if ratio == 0:
            continue

        gl_prod = GRASSLAND_PRODUCTIVITY[gl_type]
        gl_vuln = GRASSLAND_VULNERABILITY[gl_type]
        gl_name = GRASSLAND_NAMES[gl_type]

        for season in SEASONS:
            s_coef = SEASON_COEF[season]
            s_risk = SEASON_WEATHER_RISK[season]
            s_name = SEASON_NAMES[season]

            # 按季节调整 NDVI 和产草量
            ndvi_adj = ndvi * s_coef
            grass_yield = npp * 225 * gl_prod * s_coef * deg_coef  # g/m², NPP→草产量转换
            weather_score, weather_type = _get_weather_risk(region_id, weather_data, season)

            for age in AGE_GROUPS:
                age_name = AGE_NAMES[age]
                feed_need, age_resist, age_value, age_su = AGE_COEF[age]

                # 载畜能力 (羊单位/亩)
                # 基础载畜量 × 草场类型 × 季节 × 退化 × 年龄折算
                base_capacity = npp * 15000 + 5000
                capacity = base_capacity * gl_prod * s_coef * deg_coef * age_su * ratio

                # 饲草需求 (kg/头/日)
                daily_feed = 5.0 * feed_need  # 成年牦牛 ~5kg 干草/日
                seasonal_feed = daily_feed * (1.5 if season == "winter" else 1.0)  # 冬季补饲加 50%

                # 网格风险评分 (0-100)
                eco_risk = (1.0 - ndvi_adj) * 40 + (1.0 - deg_coef) * 30 + (1.0 - gl_prod) * 20
                eco_risk = min(100, eco_risk)

                weather_risk = weather_score * gl_vuln * (1.2 - age_resist)
                weather_risk = min(100, weather_risk)

                # 经营风险: 载畜量超载 + 年龄结构
                ops_risk = 0
                if capacity > 0:
                    load_ratio = base_capacity / max(1, capacity)
                    if load_ratio > 1.5:
                        ops_risk = 60
                    elif load_ratio > 1.2:
                        ops_risk = 40
                    else:
                        ops_risk = 20
                ops_risk += (1.0 - age_resist) * 20
                ops_risk = min(100, ops_risk)

                # 总风险
                total_risk = eco_risk * 0.30 + weather_risk * 0.35 + ops_risk * 0.35
                risk_level = "高" if total_risk >= 65 else "中" if total_risk >= 40 else "低"

                grids.append({
                    "region_id": region_id,
                    "region_name": region_name,
                    "grassland_type": gl_type,
                    "grassland_name": gl_name,
                    "grassland_ratio": round(ratio, 2),
                    "season": season,
                    "season_name": s_name,
                    "age_group": age,
                    "age_name": age_name,
                    # 特征值
                    "ndvi": round(ndvi_adj, 3),
                    "grass_yield_g_m2": round(grass_yield, 1),
                    "npp": round(npp, 4),
                    "degradation": deg_level,
                    "degradation_coef": round(deg_coef, 2),
                    # 载畜与饲草
                    "carrying_capacity": round(capacity),
                    "daily_feed_kg": round(seasonal_feed, 1),
                    # 风险评分
                    "eco_risk": round(eco_risk, 1),
                    "weather_risk": round(weather_risk, 1),
                    "ops_risk": round(ops_risk, 1),
                    "total_risk": round(total_risk, 1),
                    "risk_level": risk_level,
                    "weather_type": weather_type,
                    # 年龄系数
                    "feed_need_coef": round(feed_need, 2),
                    "age_resist_coef": round(age_resist, 2),
                    "age_value_coef": round(age_value, 2),
                })

    # 统计
    risk_dist = {"高": 0, "中": 0, "低": 0}
    season_risk = {s: [] for s in SEASONS}
    gl_risk = {g: [] for g in GRASSLAND_TYPES}
    age_risk = {a: [] for a in AGE_GROUPS}

    for g in grids:
        risk_dist[g["risk_level"]] += 1
        season_risk[g["season"]].append(g["total_risk"])
        gl_risk[g["grassland_type"]].append(g["total_risk"])
        age_risk[g["age_group"]].append(g["total_risk"])

    return {
        "region_id": region_id,
        "region_name": region_name,
        "n_grids": len(grids),
        "grids": grids,
        "summary": {
            "risk_distribution": risk_dist,
            "avg_risk": round(float(np.mean([g["total_risk"] for g in grids])), 1),
            "max_risk": round(float(np.max([g["total_risk"] for g in grids])), 1),
            "min_risk": round(float(np.min([g["total_risk"] for g in grids])), 1),
            "season_avg_risk": {s: round(float(np.mean(v)), 1) if v else 0 for s, v in season_risk.items()},
            "grassland_avg_risk": {g: round(float(np.mean(v)), 1) if v else 0 for g, v in gl_risk.items()},
            "age_avg_risk": {a: round(float(np.mean(v)), 1) if v else 0 for a, v in age_risk.items()},
            "highest_risk_grid": max(grids, key=lambda x: x["total_risk"]),
            "lowest_risk_grid": min(grids, key=lambda x: x["total_risk"]),
        },
    }


def build_all_grids() -> list[dict]:
    """构建所有县的时空网格。"""
    region_list = _load_region_list()
    results = []
    for r in region_list:
        rid = r["region_id"].strip()
        grid = build_grid(rid)
        results.append({
            "region_id": rid,
            "region_name": grid["region_name"],
            "n_grids": grid["n_grids"],
            "avg_risk": grid["summary"]["avg_risk"],
            "max_risk": grid["summary"]["max_risk"],
            "risk_distribution": grid["summary"]["risk_distribution"],
            "highest_risk": {
                "grassland": grid["summary"]["highest_risk_grid"]["grassland_name"],
                "season": grid["summary"]["highest_risk_grid"]["season_name"],
                "age": grid["summary"]["highest_risk_grid"]["age_name"],
                "risk": grid["summary"]["highest_risk_grid"]["total_risk"],
            },
        })
    return results


def grid_status() -> dict[str, Any]:
    """时空网格模型状态。"""
    region_list = _load_region_list()
    n_regions = len(region_list)
    n_grids_per_region = len(GRASSLAND_TYPES) * len(SEASONS) * len(AGE_GROUPS)
    return {
        "model": "spatio_temporal_grid",
        "dimensions": {
            "regions": n_regions,
            "grassland_types": len(GRASSLAND_TYPES),
            "seasons": len(SEASONS),
            "age_groups": len(AGE_GROUPS),
        },
        "total_grids": n_regions * n_grids_per_region,
        "grassland_types": [{"code": g, "name": GRASSLAND_NAMES[g], "productivity": GRASSLAND_PRODUCTIVITY[g]} for g in GRASSLAND_TYPES],
        "seasons": [{"code": s, "name": SEASON_NAMES[s], "coef": SEASON_COEF[s], "weather_risk": SEASON_WEATHER_RISK[s]} for s in SEASONS],
        "age_groups": [{"code": a, "name": AGE_NAMES[a], "feed_need": AGE_COEF[a][0], "age_resist": AGE_COEF[a][1], "age_value": AGE_COEF[a][2]} for a in AGE_GROUPS],
        "description": "25县 × 3草场 × 4季节 × 5年龄段 = 1500 个时空网格, 每个网格有独立的风险评分",
    }


if __name__ == "__main__":
    # CLI 测试
    print("=" * 60)
    print("时空网格模型测试")
    print("=" * 60)

    status = grid_status()
    print(f"总网格数: {status['total_grids']}")
    print(f"维度: {status['dimensions']}")

    # 测试班戈县
    print("\n--- 班戈县 ---")
    result = build_grid("naqu-bange")
    print(f"网格数: {result['n_grids']}")
    print(f"平均风险: {result['summary']['avg_risk']}")
    print(f"风险分布: {result['summary']['risk_distribution']}")
    print(f"季节风险: {result['summary']['season_avg_risk']}")
    print(f"草场风险: {result['summary']['grassland_avg_risk']}")
    print(f"年龄风险: {result['summary']['age_avg_risk']}")
    hr = result['summary']['highest_risk_grid']
    print(f"最高风险: {hr['grassland_name']} × {hr['season_name']} × {hr['age_name']} = {hr['total_risk']}")
    lr = result['summary']['lowest_risk_grid']
    print(f"最低风险: {lr['grassland_name']} × {lr['season_name']} × {lr['age_name']} = {lr['total_risk']}")
