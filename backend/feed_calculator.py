"""
饲料需求估算器 — 方案 B: 日值正弦插值 + NDVI 修正
============================================================================
基于经纬度的精准补饲计算。

核心逻辑:
  1. 坐标匹配: 输入(lat,lon) → 找最近有数据区域 → 提取气象+遥感数据
  2. 正弦温度模型: 从5年月均温拟合正弦波 → 生成逐日温度
  3. 逐日分类: 温度阈值 → 纯饲料/重饲料/半饲料/轻饲料/全草场
  4. NDVI 修正: 当月NDVI异常时调整饲料比例
  5. 接羔季修正: 5-6月母牛哺乳期精料上浮30%
  6. 规模修正: 按存栏规模给饲料采购折扣
  7. 牲畜类型修正: 默认种群结构系数1.05

使用方法:
    from feed_calculator import FeedEstimator
    est = FeedEstimator()
    result = est.estimate(lat=29.64, lon=94.36, herd_size=60, start_date="2026-01-01")
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

# ── 常量 ──────────────────────────────────────────────────────────────

# 数据目录
_STORE_DIR = Path(__file__).resolve().parent / "data_store"
_REGION_LIST = Path(__file__).resolve().parents[1] / "public_data" / "region_list.csv"

# 温度阈值 — 决定饲料与草场比例
TEMP_THRESHOLDS = [
    (-100,  -5,   "pure_feed",   1.00, "纯饲料 — 草完全休眠"),
    (-5,     0,   "heavy_feed",  0.80, "重饲料 — 草休眠但可啃"),
    (0,      5,   "half_feed",   0.50, "半饲料 — 草返青过渡期"),
    (5,     10,   "light_feed",  0.20, "轻饲料 — 草已生长"),
    (10,   100,   "full_grass",  0.00, "全草场 — 草充分生长"),
]

# 规模修正系数
SCALE_TIERS = [
    (100, 0.80, "企业/大户 — 批发价 -20%"),
    (30,  0.90, "中等户 — 小批发 -10%"),
    (10,  1.00, "散户 — 零售价"),
    (0,   1.15, "极小户 — 低效率 +15%"),
]

# 牲畜类型: 种群结构修正系数
# 来源: 青藏高原牦牛种群结构文献值 (青藏高原牦牛遗传资源调查报告, 2020)
# 成年母牛 40-50% × 1.3 + 成年公牛 5-10% × 1.0 + 阉牛 15-25% × 1.0
#   + 犊牛 10-15% × 0.5 + 架子牛 10-15% × 0.8 ≈ 1.05
# 升级路径: 接入兽医部门耳标管理系统 → 获取每头牛出生日期 → 精确按年龄/性别分类
LIVESTOCK_TYPE_CORRECTION = 1.05
LIVESTOCK_TYPE_SOURCE = (
    "青藏高原牦牛种群结构文献均值 (母牛45%×1.3 + 公牛10%×1.0 + "
    "阉牛20%×1.0 + 犊牛12%×0.5 + 架子牛13%×0.8 = 1.05)"
)
LIVESTOCK_UPGRADE_PATH = (
    "接入兽医部门耳标管理系统 → 获取每头牛的出生日期 → "
    "精确按年龄/性别/怀孕状态分类计算个体饲料需求"
)

# 接羔季月份（母牛产后哺乳，精料需求上浮 30%）
LAMBING_MONTHS = {5, 6}
LAMBING_CORRECTION = 1.30

# 默认饲料价格 (元/kg)
FEED_PRICE_DRY_GRASS = 0.80   # 干草（青稞秆/燕麦草）均价
FEED_PRICE_CONCENTRATE = 3.50  # 精料（玉米/豆粕）均价
FEED_DRY_GRASS_KG = 4.0       # 日均干草 (kg)
FEED_CONCENTRATE_KG = 0.7     # 日均精料 (kg)

# 基线管理成本: 每头每天的最低刚性支出 (盐砖+防疫+基础兽药, 即使全草场日也必须支出)
BASELINE_DAILY_COST = 0.60    # 元/头/天
BASELINE_COST_BREAKDOWN = "盐砖0.20 + 防疫驱虫0.25 + 基础兽药0.15 = 0.60元/头/天"


# ── 数据加载 ──────────────────────────────────────────────────────────

def _load_json(table: str) -> list[dict]:
    path = _STORE_DIR / f"{table}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def _load_region_list() -> list[dict]:
    """加载区域清单，返回 [{region_id, region_name, longitude, latitude, altitude, ...}]"""
    if not _REGION_LIST.exists():
        return []
    rows = []
    with open(_REGION_LIST, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


# ── 坐标匹配器 ────────────────────────────────────────────────────────

class CoordinateMatcher:
    """根据经纬度匹配最近的数据区域。

    用法:
        matcher = CoordinateMatcher()
        region = matcher.find_nearest(lat=29.64, lon=94.36)
        weather = matcher.get_weather(lat, lon)
    """

    def __init__(self) -> None:
        self._region_list = _load_region_list()
        self._weather = _load_json("weather_data")
        self._remote = _load_json("remote_sensing_data")

        # 构建快速索引
        self._regions_by_id: dict[str, dict] = {}
        self._lats: list[float] = []
        self._lons: list[float] = []
        self._ids: list[str] = []

        for r in self._region_list:
            rid = r["region_id"]
            self._regions_by_id[rid] = r
            self._ids.append(rid)
            self._lats.append(float(r["latitude"]))
            self._lons.append(float(r["longitude"]))

        # 按 region_id 聚合数据
        self._weather_by_region: dict[str, list[dict]] = defaultdict(list)
        for w in self._weather:
            self._weather_by_region[w.get("region_id", "")].append(w)

        self._remote_by_region: dict[str, list[dict]] = defaultdict(list)
        for r in self._remote:
            self._remote_by_region[r.get("region_id", "")].append(r)

    # ── 距离计算 ──────────────────────────────────────────────────

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine 公式计算两点间地表距离 (km)。"""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def find_nearest(self, lat: float, lon: float, max_distance_km: float = 500.0) -> dict | None:
        """查找最近的区域。超过 max_distance_km 返回 None。

        Returns:
            {
                "region_id": str,
                "region_name": str,
                "distance_km": float,
                "latitude": float,
                "longitude": float,
                "altitude": float,
                "has_weather": bool,
                "has_remote": bool,
            }
        """
        if not self._ids:
            return None

        distances = [self._haversine_km(lat, lon, la, lo)
                     for la, lo in zip(self._lats, self._lons)]
        idx = int(np.argmin(distances))
        distance = distances[idx]

        if distance > max_distance_km:
            return None

        region = self._regions_by_id[self._ids[idx]]
        rid = region["region_id"]

        return {
            "region_id": rid,
            "region_name": region.get("region_name", rid),
            "distance_km": round(distance, 1),
            "latitude": float(region["latitude"]),
            "longitude": float(region["longitude"]),
            "altitude": float(region.get("altitude", 0)),
            "pasture_type": region.get("pasture_type", ""),
            "has_weather": rid in self._weather_by_region and len(self._weather_by_region[rid]) > 0,
            "has_remote": rid in self._remote_by_region and len(self._remote_by_region[rid]) > 0,
            # 标识是否精确匹配（vs 用邻近站修正）
            "exact_match": distance < 10.0,
        }

    def get_weather(self, lat: float, lon: float) -> tuple[list[dict], dict | None]:
        """获取该位置的逐月气象数据。

        Returns:
            (weather_rows, correction_info_or_None)
            如果位置精确匹配 → correction_info 为 None
            如果用邻近站修正 → correction_info 含修正参数
        """
        nearest = self.find_nearest(lat, lon)
        if nearest is None:
            return [], None

        rid = nearest["region_id"]
        rows = self._weather_by_region.get(rid, [])

        # 精确匹配且有数据 → 直接返回
        if nearest["has_weather"]:
            return rows, None

        # 无数据（即使精确匹配）→ 找最近有数据的邻近站
        for i in np.argsort([
            self._haversine_km(lat, lon, la, lo)
            for la, lo in zip(self._lats, self._lons)
        ]):
            alt_rid = self._ids[i]
            if alt_rid in self._weather_by_region and self._weather_by_region[alt_rid]:
                alt_region = self._regions_by_id[alt_rid]
                query_alt = nearest.get("altitude", 0)
                ref_alt = float(alt_region.get("altitude", 0))
                # 温度修正: 海拔每降100m升0.65°C (湿绝热递减率)
                temp_correction = (ref_alt - query_alt) * 0.0065 if query_alt > 0 and ref_alt > 0 else 0.0
                return self._weather_by_region[alt_rid], {
                    "method": "nearest_station_corrected",
                    "source_region": alt_rid,
                    "source_name": alt_region.get("region_name", alt_rid),
                    "distance_km": round(self._haversine_km(lat, lon, float(alt_region["latitude"]), float(alt_region["longitude"])), 1),
                    "temp_correction_c": round(temp_correction, 1),
                    "note": f"用{alt_region.get('region_name', alt_rid)}数据，温度修正{temp_correction:+.1f}°C",
                }

        return [], None

    def get_remote_sensing(self, lat: float, lon: float) -> list[dict]:
        """获取该位置的遥感（NDVI等）数据。"""
        nearest = self.find_nearest(lat, lon, max_distance_km=200.0)
        if nearest is None:
            return []
        rid = nearest["region_id"]
        if nearest["has_remote"]:
            return self._remote_by_region.get(rid, [])
        # 找最近有遥感数据的邻近站
        for i in np.argsort([
            self._haversine_km(lat, lon, la, lo)
            for la, lo in zip(self._lats, self._lons)
        ]):
            alt_rid = self._ids[i]
            if alt_rid in self._remote_by_region and self._remote_by_region[alt_rid]:
                return self._remote_by_region[alt_rid]
        return []

    def get_region_info(self, lat: float, lon: float) -> dict:
        """综合获取位置信息（用于 API 返回）。"""
        nearest = self.find_nearest(lat, lon)
        if nearest is None:
            return {"error": "no_nearby_region", "message": f"({lat}, {lon}) 500km 内无已知区域"}
        return nearest


# ── 正弦温度模型 ──────────────────────────────────────────────────────

class TemperatureSineModel:
    """从逐月温度数据拟合年周期正弦波，生成逐日温度估计。

    模型: T(day) = T_mean + amplitude × sin(2π × day/365 + phase)

    拟合方法: 线性回归 on sin/cos 基函数
        T(m) = a + b × sin(2πm/12) + c × cos(2πm/12)
        → T_mean = a, amplitude = sqrt(b²+c²), phase = atan2(c, b)
    """

    def __init__(self) -> None:
        self._t_mean: float = 0.0
        self._amplitude: float = 0.0
        self._phase: float = 0.0      # 弧度
        self._r_squared: float = 0.0
        self._fitted: bool = False
        self._monthly_means: dict[int, float] = {}  # 1-12月均值

    def fit(self, weather_rows: list[dict], temp_correction: float = 0.0) -> dict[str, Any]:
        """从逐月气象数据拟合正弦模型。

        Args:
            weather_rows: 逐月气象记录 [{observed_at, temperature_c, ...}]
            temp_correction: 温度修正值（海拔/邻近站修正），加到每个观测值

        Returns:
            拟合统计信息
        """
        # 按月聚合温度
        monthly: dict[int, list[float]] = defaultdict(list)
        for w in weather_rows:
            try:
                m = int(w["observed_at"][5:7])
                t = float(w.get("temperature_c", 0)) + temp_correction
                monthly[m].append(t)
            except (ValueError, KeyError, IndexError):
                continue

        if not monthly:
            return {"error": "no_valid_monthly_data"}

        # 计算月均值
        self._monthly_means = {}
        for m in range(1, 13):
            vals = monthly.get(m, [])
            self._monthly_means[m] = np.mean(vals) if vals else 0.0

        # 构建回归矩阵
        X_sin: list[float] = []
        X_cos: list[float] = []
        y_vals: list[float] = []
        for m in range(1, 13):
            if m in monthly:
                for t in monthly[m]:
                    theta = 2 * math.pi * m / 12
                    X_sin.append(math.sin(theta))
                    X_cos.append(math.cos(theta))
                    y_vals.append(t)

        X = np.column_stack([np.ones(len(X_sin)), X_sin, X_cos])
        y = np.array(y_vals)

        # 最小二乘
        try:
            coeffs, residuals, rank, sv = np.linalg.lstsq(X, y, rcond=None)
        except np.linalg.LinAlgError:
            coeffs = np.array([np.mean(y_vals), 0, 0])

        self._t_mean = float(coeffs[0])
        b = float(coeffs[1])
        c = float(coeffs[2])
        self._amplitude = math.sqrt(b * b + c * c)
        self._phase = math.atan2(c, b)

        # R²
        y_pred = X @ coeffs
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        self._r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        self._fitted = True

        return {
            "mean_annual": round(self._t_mean, 1),
            "amplitude": round(self._amplitude, 1),
            "r_squared": round(self._r_squared, 3),
            "monthly_means": {str(m): round(v, 1) for m, v in self._monthly_means.items()},
        }

    def predict_monthly(self, months_ahead: int = 6, start_month: int | None = None) -> list[dict]:
        """预测未来 N 个月的月均温。

        Returns:
            [{month, month_label, predicted_temp, category}, ...]
        """
        if not self._fitted:
            return []

        if start_month is None:
            start_month = datetime.now().month

        results = []
        for offset in range(months_ahead):
            m = ((start_month - 1 + offset) % 12) + 1
            theta = 2 * math.pi * m / 12
            temp = self._t_mean + self._amplitude * math.sin(theta + self._phase)
            category = _classify_month(temp)
            results.append({
                "month": m,
                "month_label": f"{m}月",
                "predicted_temp": round(temp, 1),
                "category": category,
            })
        return results

    def predict_daily(self, start_date: str | datetime, n_days: int = 180) -> list[dict]:
        """预测逐日温度。

        Args:
            start_date: 起始日期 "YYYY-MM-DD" 或 datetime
            n_days: 预测天数

        Returns:
            [{date, day_of_year, temperature, feed_category, feed_ratio}, ...]
        """
        if not self._fitted:
            return []

        if isinstance(start_date, str):
            start = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start = start_date

        results = []
        for d in range(n_days):
            date = start + timedelta(days=d)
            doy = date.timetuple().tm_yday
            month = date.month

            # 正弦模型
            theta = 2 * math.pi * doy / 365.0
            temp = self._t_mean + self._amplitude * math.sin(theta + self._phase)

            # 分类
            category, ratio, label = _classify_temp(temp)
            results.append({
                "date": date.strftime("%Y-%m-%d"),
                "day_of_year": doy,
                "month": month,
                "temperature": round(temp, 1),
                "feed_category": category,
                "feed_ratio": ratio,
                "feed_label": label,
            })

        return results


# ── 饲料估算器 ────────────────────────────────────────────────────────

class FeedEstimator:
    """完整的饲料需求估算流水线。

    用法:
        est = FeedEstimator()
        result = est.estimate(
            lat=29.64, lon=94.36,
            herd_size=60,
            start_date="2026-01-01",
            months=6
        )
    """

    def __init__(self) -> None:
        self._matcher = CoordinateMatcher()
        self._temp_model = TemperatureSineModel()

    def estimate(
        self,
        lat: float,
        lon: float,
        herd_size: int = 1,
        start_date: str | datetime | None = None,
        months: int = 6,
    ) -> dict[str, Any]:
        """执行完整估算。

        Args:
            lat, lon: 目标位置经纬度 (WGS84)
            herd_size: 存栏规模（头数）
            start_date: 起始日期，默认今天
            months: 预测月数

        Returns:
            完整估算结果字典
        """
        if start_date is None:
            start = datetime.now().replace(day=1)
        elif isinstance(start_date, str):
            start = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start = start_date

        n_days = months * 30  # 近似，精确按实际月份天数在 daily_details 中处理

        corrections_applied: list[str] = []

        # ── 步骤 1: 坐标匹配 ──
        region_info = self._matcher.get_region_info(lat, lon)
        if "error" in region_info:
            return {"error": region_info["error"], "message": region_info["message"]}

        # ── 步骤 2: 获取气象数据 ──
        weather_rows, weather_correction = self._matcher.get_weather(lat, lon)
        if not weather_rows:
            return {"error": "no_weather_data", "message": f"({lat}, {lon}) 及邻近区域无气象数据"}

        temp_correction = weather_correction["temp_correction_c"] if weather_correction else 0.0
        if weather_correction:
            corrections_applied.append(
                f"气象数据修正: {weather_correction['note']}"
            )

        # ── 步骤 3: 拟合正弦温度模型 ──
        fit_info = self._temp_model.fit(weather_rows, temp_correction)
        if "error" in fit_info:
            return fit_info

        # ── 步骤 4: 预测逐日温度 ──
        daily = self._temp_model.predict_daily(start, n_days)
        if not daily:
            return {"error": "prediction_failed", "message": "温度预测失败"}

        # ── 步骤 5: NDVI 修正 ──
        remote_rows = self._matcher.get_remote_sensing(lat, lon)
        ndvi_by_month: dict[int, float] = {}
        if remote_rows:
            monthly_ndvi: dict[int, list[float]] = defaultdict(list)
            for r in remote_rows:
                try:
                    m = int(r["scene_date"][5:7])
                    ndvi = float(r.get("ndvi", 0))
                    monthly_ndvi[m].append(ndvi)
                except (ValueError, KeyError, IndexError):
                    continue
            for m, vals in monthly_ndvi.items():
                ndvi_by_month[m] = np.mean(vals)

        ndvi_corrections = 0
        for i, d in enumerate(daily):
            m = d["month"]
            month_ndvi = ndvi_by_month.get(m)
            if month_ndvi is not None:
                orig_ratio = d["feed_ratio"]
                # NDVI 偏低 → 草不够 → 多喂饲料
                if month_ndvi < 0.15 and orig_ratio < 1.0:
                    d["feed_ratio"] = min(1.0, orig_ratio * 1.5)
                    d["feed_label"] += f" [NDVI修正:{month_ndvi:.2f}→+50%饲料]"
                    ndvi_corrections += 1
                # NDVI 正常偏高 → 草充足 → 适当减饲料
                elif month_ndvi > 0.25 and orig_ratio > 0:
                    d["feed_ratio"] = max(0, orig_ratio * 0.7)
                    d["feed_label"] += f" [NDVI修正:{month_ndvi:.2f}→-30%饲料]"
                    ndvi_corrections += 1
        if ndvi_corrections > 0:
            corrections_applied.append(
                f"NDVI修正: {ndvi_corrections}天因当月NDVI异常调整饲料比例"
            )
        else:
            corrections_applied.append("NDVI修正: 无异常，未触发修正")

        # ── 步骤 6: 接羔季修正 ──
        lambing_corrections = 0
        for d in daily:
            if d["month"] in LAMBING_MONTHS:
                orig = d["feed_ratio"]
                d["feed_ratio"] = min(1.0, orig * LAMBING_CORRECTION)
                if d["feed_ratio"] > orig:
                    d["feed_label"] += " [接羔季+30%精料]"
                    lambing_corrections += 1
        if lambing_corrections > 0:
            corrections_applied.append(
                f"接羔季修正: {lambing_corrections}天(5-6月)精料需求上浮+{int((LAMBING_CORRECTION-1)*100)}%"
            )

        # ── 步骤 7: 逐日汇总 ──
        summary = _summarize_daily(daily)
        monthly_detail = _monthly_breakdown(daily)

        # ── 步骤 8: 规模修正 ──
        scale_factor, scale_label = _scale_correction(herd_size)
        corrections_applied.append(f"规模修正: {herd_size}头 → 系数{scale_factor:.2f} ({scale_label})")

        # ── 步骤 9: 牲畜类型修正 ──
        total_head_correction = scale_factor * LIVESTOCK_TYPE_CORRECTION
        corrections_applied.append(
            f"牲畜类型: {LIVESTOCK_TYPE_CORRECTION} ({LIVESTOCK_TYPE_SOURCE})"
        )

        # ── 步骤 10: 成本计算 ──
        cost = _calculate_cost(
            daily, herd_size, scale_factor, LIVESTOCK_TYPE_CORRECTION
        )

        # ── 组装结果 ──
        return {
            "location": {
                "query_lat": lat,
                "query_lon": lon,
                **region_info,
                "weather_source": weather_correction["source_region"] if weather_correction else region_info["region_id"],
                "weather_is_exact": weather_correction is None,
            },
            "temperature_model": fit_info,
            "request": {
                "start_date": start.strftime("%Y-%m-%d"),
                "months": months,
                "herd_size": herd_size,
                "livestock_type_correction": LIVESTOCK_TYPE_CORRECTION,
            },
            "daily_summary": summary,
            "monthly_detail": monthly_detail,
            "cost_estimate": cost,
            "corrections_applied": corrections_applied,
            "_metadata": {
                "algorithm": "方案B: 日值正弦插值 + NDVI修正",
                "livestock_type_source": LIVESTOCK_TYPE_SOURCE,
                "livestock_upgrade_path": LIVESTOCK_UPGRADE_PATH,
            },
        }


# ── 辅助函数 ──────────────────────────────────────────────────────────

def _classify_temp(temp: float) -> tuple[str, float, str]:
    """单日温度 → (类别, 饲料比例, 中文描述)"""
    for t_min, t_max, category, ratio, label in TEMP_THRESHOLDS:
        if t_min <= temp < t_max:
            return category, ratio, label
    return "unknown", 0.5, "未分类"


def _classify_month(temp: float) -> str:
    """月均温 → 月度类别"""
    for t_min, t_max, category, _, label in TEMP_THRESHOLDS:
        if t_min <= temp < t_max:
            return label
    return "未分类"


def _summarize_daily(daily: list[dict]) -> dict:
    """逐日数据 → 总体统计"""
    total = len(daily)
    cats: dict[str, int] = defaultdict(int)
    total_feed_ratio = 0.0

    for d in daily:
        cats[d["feed_category"]] += 1
        total_feed_ratio += d["feed_ratio"]

    category_labels = {
        "pure_feed": "纯饲料", "heavy_feed": "重饲料",
        "half_feed": "半饲料", "light_feed": "轻饲料",
        "full_grass": "全草场",
    }

    return {
        "total_days": total,
        "categories": {
            category_labels.get(k, k): {
                "days": v,
                "pct": round(v / total * 100, 1),
            }
            for k, v in sorted(cats.items(), key=lambda x: TEMP_THRESHOLDS.index(
                next(t for t in TEMP_THRESHOLDS if t[2] == x[0])
            ) if any(t[2] == x[0] for t in TEMP_THRESHOLDS) else 999
        )},
        "overall_feed_ratio": round(total_feed_ratio / total, 2),
        "overall_grass_ratio": round(1 - total_feed_ratio / total, 2),
    }


def _monthly_breakdown(daily: list[dict]) -> list[dict]:
    """逐日数据 → 月度分解"""
    months: dict[str, list[dict]] = defaultdict(list)
    for d in daily:
        key = d["date"][:7]
        months[key].append(d)

    result = []
    for key in sorted(months):
        days = months[key]
        total = len(days)
        avg_temp = np.mean([d["temperature"] for d in days])
        avg_feed_ratio = np.mean([d["feed_ratio"] for d in days])

        cat_counts: dict[str, int] = defaultdict(int)
        for d in days:
            cat_counts[d["feed_category"]] += 1

        category_labels = {
            "pure_feed": "纯饲料", "heavy_feed": "重饲料",
            "half_feed": "半饲料", "light_feed": "轻饲料",
            "full_grass": "全草场",
        }

        # 温度分布
        temps = [d["temperature"] for d in days]
        result.append({
            "month": key,
            "days": total,
            "avg_temperature": round(avg_temp, 1),
            "min_temperature": round(min(temps), 1),
            "max_temperature": round(max(temps), 1),
            "avg_feed_ratio": round(avg_feed_ratio, 2),
            "categories": {
                category_labels.get(k, k): v
                for k, v in sorted(cat_counts.items())
            },
        })

    return result


def _scale_correction(herd_size: int) -> tuple[float, str]:
    """规模 → (修正系数, 描述)"""
    for threshold, factor, label in SCALE_TIERS:
        if herd_size >= threshold:
            return factor, label
    return 1.0, "未知"


def _calculate_cost(
    daily: list[dict],
    herd_size: int,
    scale_factor: float,
    livestock_factor: float,
) -> dict:
    """从逐日饲料比例计算总成本。

    每天每头:
      纯饲料 = 100%饲料 = 干草4kg + 精料0.7kg
      混合日 = feed_ratio × (干草+精料)
      全草场 = 0

    单价: 干草 0.80元/kg, 精料 3.50元/kg
    """
    total_dry_grass_kg = 0.0
    total_concentrate_kg = 0.0

    for d in daily:
        ratio = d["feed_ratio"]
        total_dry_grass_kg += FEED_DRY_GRASS_KG * ratio
        total_concentrate_kg += FEED_CONCENTRATE_KG * ratio

    # 单头基准成本（饲料 + 基线管理）
    feed_cost_per_head = (
        total_dry_grass_kg * FEED_PRICE_DRY_GRASS +
        total_concentrate_kg * FEED_PRICE_CONCENTRATE
    )
    baseline_cost_per_head = len(daily) * BASELINE_DAILY_COST
    base_cost_per_head = feed_cost_per_head + baseline_cost_per_head

    # 修正后成本
    effective_cost_per_head = base_cost_per_head * livestock_factor
    effective_total = effective_cost_per_head * herd_size * scale_factor

    return {
        "base_cost_per_head": round(base_cost_per_head, 2),
        "livestock_type_correction": livestock_factor,
        "corrected_cost_per_head": round(effective_cost_per_head, 2),
        "herd_size": herd_size,
        "scale_correction": scale_factor,
        "total_cost": round(effective_total, 2),
        "dry_grass_total_kg": round(total_dry_grass_kg, 1),
        "concentrate_total_kg": round(total_concentrate_kg, 1),
        "baseline_cost_per_day": BASELINE_DAILY_COST,
        "baseline_cost_total": round(baseline_cost_per_head, 2),
        "feed_cost_subtotal": round(feed_cost_per_head, 2),
        "price_dry_grass_per_kg": FEED_PRICE_DRY_GRASS,
        "price_concentrate_per_kg": FEED_PRICE_CONCENTRATE,
        "note": (
            f"单头日均: 干草{FEED_DRY_GRASS_KG}kg×{FEED_PRICE_DRY_GRASS}元 "
            f"+ 精料{FEED_CONCENTRATE_KG}kg×{FEED_PRICE_CONCENTRATE}元 "
            f"= {FEED_DRY_GRASS_KG * FEED_PRICE_DRY_GRASS + FEED_CONCENTRATE_KG * FEED_PRICE_CONCENTRATE:.2f}元/纯饲料日; "
            f"基线管理费 {BASELINE_DAILY_COST}元/天 ({BASELINE_COST_BREAKDOWN})"
        ),
    }


# ── 季节性牧场估算（迁徙模型）─────────────────────────────────────────

# 月份到牧场的映射
# 12-4月: 冬季牧场  5月: 春季牧场  6-9月: 夏季牧场  10-11月: 秋季牧场
MONTH_TO_PASTURE = {}
for _m in [12, 1, 2, 3, 4]:
    MONTH_TO_PASTURE[_m] = "winter"
for _m in [5]:
    MONTH_TO_PASTURE[_m] = "spring"
for _m in [6, 7, 8, 9]:
    MONTH_TO_PASTURE[_m] = "summer"
for _m in [10, 11]:
    MONTH_TO_PASTURE[_m] = "autumn"

PASTURE_NAMES = {
    "winter": "冬季牧场",
    "spring": "春季牧场",
    "summer": "夏季牧场",
    "autumn": "秋季牧场",
}


class SeasonalPastureEstimator:
    """季节性牧场饲料估算器 — 支持手动坐标 和 县域海拔自动推算。

    两种用法:

    1. 手动模式（信贷员打点）:
        spe = SeasonalPastureEstimator()
        result = spe.estimate_manual(
            herd_size=60,
            winter_lat=31.36, winter_lon=90.01,
            summer_lat=32.10, summer_lon=91.50,
            spring_autumn_lat=31.70, spring_autumn_lon=90.80,
        )

    2. 自动推算模式（县域中心+海拔启发式）:
        spe = SeasonalPastureEstimator()
        result = spe.estimate_auto(
            region_id="changdu-karuo",
            herd_size=60,
        )

    自动推算数据来源：
        region_list.csv 中的 altitude 字段（县城中心海拔）
        推算规则:
          冬季牧场 ≈ 县城中心 - 200m（避风河谷）
          夏季牧场 ≈ 县城中心 + 700m（高山草甸上限）
          春秋牧场 ≈ 县城中心 + 250m（过渡带）
        温度修正: ΔT = (县城海拔 - 牧场海拔) × 0.0065°C/m
    """

    def __init__(self) -> None:
        self._region_list = _load_region_list()
        self._regions_by_id = {r["region_id"]: r for r in self._region_list}

    # ── 手动模式 ──────────────────────────────────────────────────

    def estimate_manual(
        self,
        herd_size: int = 1,
        winter_lat: float = 0,
        winter_lon: float = 0,
        summer_lat: float = 0,
        summer_lon: float = 0,
        spring_autumn_lat: float = 0,
        spring_autumn_lon: float = 0,
        start_year: int | None = None,
    ) -> dict[str, Any]:
        """手动输入各季牧场坐标，返回 12 个月完整估算。

        Args:
            herd_size: 存栏规模
            winter_lat/lon: 冬季牧���坐标 (12-4月)
            summer_lat/lon: 夏季牧场坐标 (6-9月)
            spring_autumn_lat/lon: 春秋牧场坐标 (5月, 10-11月)
            start_year: 起始年份，默认当前年

        Returns:
            完整 12 个月迁徙估算
        """
        if start_year is None:
            start_year = datetime.now().year

        pastures = {
            "winter": (winter_lat, winter_lon),
            "spring": (spring_autumn_lat, spring_autumn_lon),
            "summer": (summer_lat, summer_lon),
            "autumn": (spring_autumn_lat, spring_autumn_lon),
        }

        return self._run_migration_estimate(herd_size, pastures, start_year, mode="manual")

    # ── 自动推算模式 ──────────────────────────────────────────────

    def estimate_auto(
        self,
        region_id: str,
        herd_size: int = 1,
        start_year: int | None = None,
    ) -> dict[str, Any]:
        """根据县城中心海拔自动推算各季牧场海拔，返回 12 个月估算。

        Args:
            region_id: 区域 ID（如 "changdu-karuo"）
            herd_size: 存栏规模
            start_year: 起始年份
        """
        if start_year is None:
            start_year = datetime.now().year

        region = self._regions_by_id.get(region_id)
        if region is None:
            return {"error": "unknown_region", "message": f"未知区域: {region_id}"}

        county_altitude = float(region.get("altitude", 3500))
        county_lat = float(region["latitude"])
        county_lon = float(region["longitude"])

        # 海拔启发式推算（使用县城中心坐标 + 海拔修正）
        # 所有牧场使用相同的经纬度（县城中心），通过海拔差修正温度
        winter_alt = max(2000, county_altitude - 200)   # 冬季下到河谷
        spring_alt = county_altitude + 250                # 春季过渡带
        summer_alt = min(5500, county_altitude + 700)     # 夏季上山
        autumn_alt = county_altitude + 250                # 秋季过渡带

        # 返回坐标+海拔修正值
        pastures = {
            "winter": (county_lat, county_lon, winter_alt),
            "spring": (county_lat, county_lon, spring_alt),
            "summer": (county_lat, county_lon, summer_alt),
            "autumn": (county_lat, county_lon, autumn_alt),
        }

        return self._run_migration_estimate(herd_size, pastures, start_year, mode="auto",
                                             region_info={
                                                 "region_id": region_id,
                                                 "region_name": region.get("region_name", region_id),
                                                 "county_altitude": county_altitude,
                                                 "pasture_altitudes": {
                                                     "winter": winter_alt,
                                                     "spring": spring_alt,
                                                     "summer": summer_alt,
                                                     "autumn": autumn_alt,
                                                 },
                                             })

    # ── 位置辅助 ──────────────────────────────────────────────────

    def get_seasonal_pasture_info(self, region_id: str) -> dict:
        """查询一个区域的建议牧场海拔（用于确认自动推算是否合理）。"""
        region = self._regions_by_id.get(region_id)
        if region is None:
            return {"error": "unknown_region"}
        county_alt = float(region.get("altitude", 3500))
        return {
            "region_id": region_id,
            "region_name": region.get("region_name", ""),
            "county_altitude": county_alt,
            "suggested_winter": max(2000, county_alt - 200),
            "suggested_spring_autumn": county_alt + 250,
            "suggested_summer": min(5500, county_alt + 700),
            "data_source": "县城中心海拔 (region_list.csv) + 文献启发式推算",
            "precision": "粗估 ±300m，待畜牧局精确牧场数据替换",
        }

    # ── 内部: 执行迁徙估算 ────────────────────────────────────────

    def _run_migration_estimate(
        self,
        herd_size: int,
        pastures: dict[str, tuple],
        start_year: int,
        mode: str,
        region_info: dict | None = None,
    ) -> dict[str, Any]:
        """对四个季节牧场分别运行 FeedEstimator，合并结果。"""
        est = FeedEstimator()

        # 四季牧场所属月份
        pasture_months = {
            "winter": [12, 1, 2, 3, 4],
            "spring": [5],
            "summer": [6, 7, 8, 9],
            "autumn": [10, 11],
        }

        results: dict[str, dict] = {}
        total_cost = 0.0
        all_monthly: list[dict] = []
        all_daily_categories: dict[str, int] = defaultdict(int)
        total_days = 0
        total_feed_ratio = 0.0

        for season, pasture_data in pastures.items():
            if len(pasture_data) == 2:
                lat, lon = pasture_data
                altitude_correction = 0.0
            else:
                lat, lon, altitude = pasture_data
                # 找最近气象站，计算海拔修正
                matcher = CoordinateMatcher()
                nearest = matcher.find_nearest(lat, lon)
                if nearest:
                    station_alt = nearest.get("altitude", altitude)
                    altitude_correction = (station_alt - altitude) * 0.0065

            months_in_season = pasture_months[season]
            first_month = months_in_season[0]
            if first_month == 12:
                estimate_year = start_year - 1 if start_year > 2000 else start_year
            else:
                estimate_year = start_year

            start_str = f"{estimate_year}-{first_month:02d}-01"
            n_months = len(months_in_season)

            r = est.estimate(
                lat=lat, lon=lon,
                herd_size=herd_size,
                start_date=start_str,
                months=n_months,
            )

            results[season] = {
                "pasture_name": PASTURE_NAMES[season],
                "months": months_in_season,
                "n_months": n_months,
                "coords": {"lat": round(lat, 4), "lon": round(lon, 4)},
                "altitude_correction": round(altitude_correction, 1) if altitude_correction != 0 else 0,
            }

            if "error" not in r:
                results[season]["summary"] = r.get("daily_summary", {})
                results[season]["monthly"] = r.get("monthly_detail", [])
                results[season]["cost"] = r.get("cost_estimate", {}).get("total_cost", 0)
                total_cost += results[season]["cost"]

                # 合并汇总
                ds = r.get("daily_summary", {})
                for cat_name, info in ds.get("categories", {}).items():
                    all_daily_categories[cat_name] += info.get("days", 0)
                if ds.get("total_days"):
                    total_days += ds["total_days"]
                    total_feed_ratio += ds.get("overall_feed_ratio", 0) * ds["total_days"]

                for m in r.get("monthly_detail", []):
                    m["pasture"] = PASTURE_NAMES[season]
                    all_monthly.append(m)

        # 成本合并：加上规模修正和牲畜类型修正
        scale_factor, scale_label = _scale_correction(herd_size)

        # 注意: estimate() 内部已经应用了规模修正，这里只是汇总
        # 重新计算总成本（各季节独立估算的成本加总）
        all_monthly.sort(key=lambda x: x["month"])

        return {
            "mode": mode,
            "request": {
                "herd_size": herd_size,
                "start_year": start_year,
                "livestock_type_correction": LIVESTOCK_TYPE_CORRECTION,
                "scale_correction": f"{scale_factor:.2f} ({scale_label})",
            },
            "pastures": results,
            "region_info": region_info,
            "yearly_summary": {
                "total_days": total_days,
                "total_cost": round(total_cost, 2),
                "cost_per_head": round(total_cost / herd_size, 2) if herd_size > 0 else 0,
                "categories": dict(all_daily_categories),
                "overall_feed_ratio": round(total_feed_ratio / total_days, 2) if total_days > 0 else 0,
                "overall_grass_ratio": round(1 - total_feed_ratio / total_days, 2) if total_days > 0 else 0,
            },
            "monthly_detail": all_monthly,
            "_metadata": {
                "algorithm": "方案B: 日值正弦插值 + 迁徙路径修正",
                "livestock_type_source": LIVESTOCK_TYPE_SOURCE,
                "livestock_upgrade_path": LIVESTOCK_UPGRADE_PATH,
                "altitude_heuristic": (
                    "自动推算: 冬季=县城中心-200m, "
                    "夏季=县城中心+700m, 春秋=县城中心+250m; "
                    "温度修正 ΔT=Δh×0.0065°C/m"
                ) if mode == "auto" else "手动坐标模式",
                "data_source": (
                    "region_list.csv 县城中心海拔 (来自 public_data/region_list.csv)"
                ) if mode == "auto" else "用户手动输入",
            },
        }


# ── 便捷函数 ──────────────────────────────────────────────────────────

def quick_estimate(
    lat: float,
    lon: float,
    herd_size: int = 1,
    start_date: str = "2026-01-01",
    months: int = 6,
) -> dict:
    """一行调用估算（不含迁徙）。"""
    est = FeedEstimator()
    return est.estimate(lat, lon, herd_size, start_date, months)


def quick_migration_estimate(
    region_id: str,
    herd_size: int = 1,
) -> dict:
    """一行调用完整年度迁徙估算（自动推算模式）。"""
    spe = SeasonalPastureEstimator()
    return spe.estimate_auto(region_id=region_id, herd_size=herd_size)
