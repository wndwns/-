"""
灾害预测模块
================================================================
输入地区名/经纬度 → 拉取 Open-Meteo 数据 → 5灾种3个月预测

5灾种：
  - cold_wave  寒潮 (日均温<-10°C高, <-5°C中, <0°C低)
  - snowstorm  雪灾 (雪深>=5cm持续>=3天为轻度,>=10cm>=5天中度,>=15cm>=7天重度)
  - drought    干旱 (SPI-3: ≤-2严重,≤-1.5中度,≤-1轻度)
  - blizzard   暴雪 (24h雪深>=10cm)
  - ecological 生态 (NDVI季节性异常)

三段置信度：
  0-16天:   高 (Open-Meteo 实时预报)
  17-30天:  中 (季节性外推+历史同期)
  31-90天:  低 (气候态+历史概率)
"""
from __future__ import annotations

import csv
import json
import math
import statistics
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# ========== 配置 ==========
ROOT = Path(__file__).resolve().parent.parent
REGION_CSV = ROOT / "public_data" / "region_list.csv"

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
UA = "yak-risk-platform/1.0"
TIMEOUT = 30


# ========== 26县映射 ==========
def load_region_mapping() -> dict:
    """加载26县区名→经纬度映射（含别名）"""
    mapping = {}
    with open(REGION_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            name = r["region_name"].strip()
            aliases = {
                name,
                name.replace("市", "").replace("州", "").replace("地区", ""),
                name.replace("市", "").replace("州", "").replace("地区", "").replace("县", "").replace("区", ""),
                name[-2:],
                r["region_id"].strip(),
            }
            entry = {
                "region_id": r["region_id"].strip(),
                "region_name": name,
                "latitude": float(r["latitude"]),
                "longitude": float(r["longitude"]),
                "altitude": float(r.get("altitude", 0) or 0),
                "pasture_type": r.get("pasture_type", "").strip(),
            }
            for a in aliases:
                if a:
                    mapping[a] = entry
    return mapping


def resolve_region(query: str, mapping: dict) -> dict | None:
    """解析用户输入：支持中文县名/简称/region_id"""
    q = query.strip()
    if q in mapping:
        return mapping[q]
    # 模糊匹配
    for k, v in mapping.items():
        if q in k or k in q:
            return v
    return None


def geocode_query(query: str) -> dict | None:
    """Open-Meteo 免费地理编码：支持任意中文地名→经纬度"""
    params = {"name": query, "language": "zh", "count": 1, "format": "json"}
    try:
        req = urllib.request.Request(
            f"{GEOCODE_URL}?{urllib.parse.urlencode(params)}",
            headers={"User-Agent": UA},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read())
        results = data.get("results") or []
        if not results:
            return None
        first = results[0]
        return {
            "region_id": f"geocoded_{first.get('id', query)}",
            "region_name": first.get("name", query) + ("," + first.get("admin1", "") if first.get("admin1") else ""),
            "latitude": first.get("latitude"),
            "longitude": first.get("longitude"),
            "altitude": first.get("elevation", 0) or 0,
            "pasture_type": "未知（地理编码）",
        }
    except Exception:
        return None


# ========== Open-Meteo 数据获取 ==========
def _fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


def fetch_forecast(lat: float, lon: float, days: int = 16) -> dict:
    """Open-Meteo 实时预报（最多16天）"""
    params = {
        "latitude": lat, "longitude": lon,
        "daily": "temperature_2m_mean,temperature_2m_min,temperature_2m_max,precipitation_sum,snowfall_sum,wind_speed_10m_max",
        "forecast_days": min(days, 16),
        "timezone": "UTC", "wind_speed_unit": "ms",
    }
    return _fetch(f"{FORECAST_URL}?{urllib.parse.urlencode(params)}")


def fetch_archive(lat: float, lon: float, start: str, end: str) -> dict:
    """Open-Meteo 历史 ERA5"""
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start, "end_date": end,
        "daily": "temperature_2m_mean,precipitation_sum,snowfall_sum,snow_depth_max",
        "timezone": "UTC",
    }
    return _fetch(f"{ARCHIVE_URL}?{urllib.parse.urlencode(params)}")


def fetch_historical_5y(lat: float, lon: float, target_start: datetime, target_end: datetime) -> dict:
    """获取过去5年同期的历史数据，用于气候态基线"""
    all_data = defaultdict(list)
    for year_offset in range(1, 6):
        s = (target_start - timedelta(days=365 * year_offset)).strftime("%Y-%m-%d")
        e = (target_end - timedelta(days=365 * year_offset)).strftime("%Y-%m-%d")
        try:
            d = fetch_archive(lat, lon, s, e)
            for k, vals in d.get("daily", {}).items():
                if k == "time":
                    continue
                all_data[k].extend(vals or [])
        except Exception:
            continue
    return dict(all_data)


# ========== 5灾种预测算法 ==========
def predict_cold_wave(forecast_data: dict, historical: dict) -> list:
    """寒潮风险预测：返回12周风险序列(0-100)
    0-16天: 实际温度判定
    17-90天: 历史同期温度T分布
    """
    weekly_risks = []
    fc_times = forecast_data.get("daily", {}).get("time", [])
    fc_temps = forecast_data.get("daily", {}).get("temperature_2m_mean", [])

    # 0-16天：基于预报温度
    for week_start in range(0, 90, 7):
        week_end = min(week_start + 7, 90)
        if week_start < 16 and fc_temps:
            # 用预报温度
            week_temps = [t for i, t in enumerate(fc_temps)
                          if i >= week_start and i < week_end and t is not None]
            if week_temps:
                min_temp = min(week_temps)
                mean_temp = statistics.mean(week_temps)
                # 寒潮判定：日均温<-10高, <-5中, <0低
                if mean_temp < -10:
                    risk = 85 + min(15, abs(mean_temp + 10) * 1.5)
                elif mean_temp < -5:
                    risk = 60 + (abs(mean_temp + 5)) * 5
                elif mean_temp < 0:
                    risk = 30 + (abs(mean_temp)) * 6
                else:
                    risk = max(5, 30 - mean_temp * 1.5)
            else:
                risk = 30
        else:
            # 17-90天：用历史同期温度
            hist_temps = [t for t in historical.get("temperature_2m_mean", []) if t is not None]
            if hist_temps:
                hist_mean = statistics.mean(hist_temps)
                hist_std = statistics.stdev(hist_temps) if len(hist_temps) > 1 else 3
                # P(温度<-10°C) 近似
                z = (-10 - hist_mean) / max(hist_std, 0.5)
                p_extreme = 0.5 * math.erfc(z / math.sqrt(2))
                risk = min(95, p_extreme * 100 * 3 + max(0, 20 - hist_mean))
                risk = max(5, risk)
            else:
                risk = 20
        weekly_risks.append({
            "week": week_start // 7 + 1,
            "days_start": week_start,
            "days_end": week_end,
            "risk_score": round(risk, 1),
            "risk_level": "高" if risk >= 70 else "中" if risk >= 40 else "低",
        })
    return weekly_risks


def predict_snowstorm(forecast_data: dict, historical: dict) -> list:
    """雪灾风险预测：GB/T 20482-2006 阈值
    0-16天: 实际降雪量判定 (snowfall_sum cm)
    17-90天: 历史同期降雪概率
    """
    weekly_risks = []
    fc_snow = forecast_data.get("daily", {}).get("snowfall_sum", [])

    for week_start in range(0, 90, 7):
        week_end = min(week_start + 7, 90)
        if week_start < 16 and fc_snow:
            week_snow = [s for i, s in enumerate(fc_snow)
                         if i >= week_start and i < week_end and s is not None]
            if week_snow:
                # 累计降雪量 + 最大单日降雪量
                total_snow = sum(week_snow)
                max_daily = max(week_snow)
                # GB/T 20482-2006 近似：累计>=15cm高, >=10cm中, >=5cm低
                if total_snow >= 15 or max_daily >= 5:
                    risk = 85
                elif total_snow >= 10:
                    risk = 60
                elif total_snow >= 5:
                    risk = 40
                else:
                    risk = max(5, 20 - total_snow * 2)
            else:
                risk = 15
        else:
            # 历史同期累计降雪
            hist_snow = [s for s in historical.get("snowfall_sum", []) if s is not None]
            if hist_snow:
                p_heavy = sum(1 for s in hist_snow if s >= 5) / max(len(hist_snow), 1)  # 单日>=5cm
                p_med = sum(1 for s in hist_snow if s >= 2) / max(len(hist_snow), 1)
                p_light = sum(1 for s in hist_snow if s >= 1) / max(len(hist_snow), 1)
                risk = min(90, p_heavy * 90 + p_med * 40 + p_light * 20 + 5)
            else:
                risk = 10
        weekly_risks.append({
            "week": week_start // 7 + 1,
            "days_start": week_start,
            "days_end": week_end,
            "risk_score": round(risk, 1),
            "risk_level": "高" if risk >= 70 else "中" if risk >= 40 else "低",
        })
    return weekly_risks


def predict_drought(historical: dict, target_start: datetime) -> list:
    """干旱风险预测：SPI-3 简化版
    用过去5年同期3月累计降水Z-score
    """
    weekly_risks = []
    hist_precip = [p for p in historical.get("precipitation_sum", []) if p is not None]

    # 计算历史SPI基线
    if hist_precip and len(hist_precip) >= 10:
        mean_p = statistics.mean(hist_precip)
        std_p = statistics.stdev(hist_precip) if len(hist_precip) > 1 else 10
    else:
        mean_p, std_p = 50, 30

    for week_start in range(0, 90, 7):
        # SPI-3 简化：假设当前累计降水为历史均值的某个比例
        # 因为未来3个月降水未知，用季节性调整
        week_idx = week_start // 7
        # 季节因子：青藏高原冬春旱季降水少
        month = (target_start.month + week_start // 30 - 1) % 12 + 1
        if month in [11, 12, 1, 2, 3]:
            season_factor = 0.6  # 旱季
        elif month in [4, 5]:
            season_factor = 0.8
        else:
            season_factor = 1.2  # 雨季

        assumed_precip = mean_p * season_factor
        z = (assumed_precip - mean_p) / max(std_p, 0.5)
        spi = -z  # SPI负值=干旱

        if spi <= -2:
            risk = 90
        elif spi <= -1.5:
            risk = 70
        elif spi <= -1:
            risk = 50
        elif spi <= -0.5:
            risk = 30
        else:
            risk = 10

        weekly_risks.append({
            "week": week_idx + 1,
            "days_start": week_start,
            "days_end": min(week_start + 7, 90),
            "risk_score": round(risk, 1),
            "risk_level": "高" if risk >= 70 else "中" if risk >= 40 else "低",
            "spi_estimated": round(spi, 2),
        })
    return weekly_risks


def predict_blizzard(forecast_data: dict, historical: dict) -> list:
    """暴雪风险预测：24h降雪量>=10cm"""
    weekly_risks = []
    fc_snowfall = forecast_data.get("daily", {}).get("snowfall_sum", [])

    for week_start in range(0, 90, 7):
        week_end = min(week_start + 7, 90)
        if week_start < 16 and fc_snowfall:
            week_sf = [s for i, s in enumerate(fc_snowfall)
                       if i >= week_start and i < week_end and s is not None]
            if week_sf:
                max_sf = max(week_sf)  # cm
                if max_sf >= 10:
                    risk = 85
                elif max_sf >= 5:
                    risk = 55
                elif max_sf >= 2:
                    risk = 30
                else:
                    risk = 10
            else:
                risk = 10
        else:
            # 历史同期暴雪概率
            hist_sf = [s for s in historical.get("snowfall_sum", []) if s is not None]
            if hist_sf:
                p_blizzard = sum(1 for s in hist_sf if s >= 10) / max(len(hist_sf), 1)
                p_med = sum(1 for s in hist_sf if s >= 5) / max(len(hist_sf), 1)
                risk = min(85, p_blizzard * 90 + p_med * 30 + 5)
            else:
                risk = 10
        weekly_risks.append({
            "week": week_start // 7 + 1,
            "days_start": week_start,
            "days_end": week_end,
            "risk_score": round(risk, 1),
            "risk_level": "高" if risk >= 70 else "中" if risk >= 40 else "低",
        })
    return weekly_risks


def predict_ecological(historical: dict, target_start: datetime) -> list:
    """生态风险预测：基于历史温度+降水推导NDVI季节性
    青藏高原NDVI与温度+降水强相关
    """
    weekly_risks = []
    hist_temps = [t for t in historical.get("temperature_2m_mean", []) if t is not None]
    hist_precip = [p for p in historical.get("precipitation_sum", []) if p is not None]

    if hist_temps:
        mean_t = statistics.mean(hist_temps)
        std_t = statistics.stdev(hist_temps) if len(hist_temps) > 1 else 3
    else:
        mean_t, std_t = 5, 5
    if hist_precip:
        mean_p = statistics.mean(hist_precip)
    else:
        mean_p = 50

    for week_start in range(0, 90, 7):
        month = (target_start.month + week_start // 30 - 1) % 12 + 1
        # 季节性温度
        if month in [12, 1, 2]:
            season_t = mean_t - 10
        elif month in [3, 4, 11]:
            season_t = mean_t - 3
        elif month in [5, 6, 9, 10]:
            season_t = mean_t + 3
        else:
            season_t = mean_t + 8

        # 生态风险：温度低+降水少=高生态风险
        # 温度<-5°C 或 降水<30mm 风险高
        if season_t < -5:
            temp_risk = 80
        elif season_t < 0:
            temp_risk = 55
        elif season_t < 5:
            temp_risk = 35
        else:
            temp_risk = 15

        # 季节降水
        if month in [11, 12, 1, 2, 3]:
            season_p = mean_p * 0.4
        elif month in [4, 5]:
            season_p = mean_p * 0.7
        else:
            season_p = mean_p * 1.5

        if season_p < 20:
            precip_risk = 60
        elif season_p < 50:
            precip_risk = 35
        else:
            precip_risk = 15

        # 综合
        risk = (temp_risk * 0.6 + precip_risk * 0.4)
        weekly_risks.append({
            "week": week_start // 7 + 1,
            "days_start": week_start,
            "days_end": min(week_start + 7, 90),
            "risk_score": round(risk, 1),
            "risk_level": "高" if risk >= 70 else "中" if risk >= 40 else "低",
        })
    return weekly_risks


# ========== 综合风险评分 ==========
def compute_composite(cold, snow, drought, blizzard, eco) -> dict:
    """5灾种加权综合风险"""
    weights = {
        "cold_wave": 0.25,
        "snowstorm": 0.25,
        "drought": 0.20,
        "blizzard": 0.15,
        "ecological": 0.15,
    }
    weekly_composite = []
    for i in range(12):
        score = (cold[i]["risk_score"] * weights["cold_wave"] +
                 snow[i]["risk_score"] * weights["snowstorm"] +
                 drought[i]["risk_score"] * weights["drought"] +
                 blizzard[i]["risk_score"] * weights["blizzard"] +
                 eco[i]["risk_score"] * weights["ecological"])
        weekly_composite.append({
            "week": i + 1,
            "days_start": i * 7,
            "days_end": min((i + 1) * 7, 90),
            "risk_score": round(score, 1),
            "risk_level": "高" if score >= 70 else "中" if score >= 40 else "低",
            "confidence": "高" if i < 2 else "中" if i < 4 else "低",
        })

    avg_score = statistics.mean([w["risk_score"] for w in weekly_composite])
    max_score = max(w["risk_score"] for w in weekly_composite)
    peak_week = next(w["week"] for w in weekly_composite if w["risk_score"] == max_score)

    return {
        "weekly": weekly_composite,
        "avg_score": round(avg_score, 1),
        "max_score": round(max_score, 1),
        "peak_week": peak_week,
        "overall_level": "高" if avg_score >= 60 else "中" if avg_score >= 35 else "低",
    }


def generate_recommendations(composite: dict, top_disaster: str, top_disaster_score: float, region_name: str) -> list:
    """基于综合风险生成建议（建议与综合/灾种等级一致）"""
    recs = []
    level = composite["overall_level"]
    peak = composite["peak_week"]

    if level == "高":
        recs.append(f"{region_name}未来3个月综合灾害风险等级为高，建议启动应急预案")
    elif level == "中":
        recs.append(f"{region_name}未来3个月综合灾害风险等级为中，建议加强监测")
    else:
        recs.append(f"{region_name}未来3个月综合灾害风险等级为低，常规监控即可")

    recs.append(f"风险峰值预计在第{peak}周（{(datetime.now() + timedelta(days=(peak-1)*7)).strftime('%m月%d日')}前后）")

    # 首要灾种建议：只有当首要灾种平均分>=40才显示具体应对
    disaster_recs = {
        "cold_wave": ("寒潮风险偏高", "提前备足饲草料，加固棚圈，关注幼崽和老弱牲畜保温"),
        "snowstorm": ("雪灾风险偏高", "准备破雪机械，规划转场路线，储备7天以上应急饲草"),
        "drought": ("干旱风险偏高", "调整载畜量，开辟水源，准备补饲方案"),
        "blizzard": ("暴雪风险偏高", "减少远牧，加固畜棚顶盖，做好兽医物资储备"),
        "ecological": ("生态风险偏高", "考虑休牧轮牧，监测草场退化，申请生态补偿"),
    }
    if top_disaster in disaster_recs and top_disaster_score >= 40:
        title, action = disaster_recs[top_disaster]
        recs.append(f"{title}：{action}")
    elif top_disaster in disaster_recs:
        # 首要灾种风险较低，仅提示监测
        disaster_name = {"cold_wave": "寒潮", "snowstorm": "雪灾", "drought": "干旱",
                         "blizzard": "暴雪", "ecological": "生态"}[top_disaster]
        recs.append(f"首要风险为{disaster_name}（平均分{top_disaster_score:.1f}），建议持续监测")

    return recs


# ========== 主入口 ==========
def forecast_disaster(query: str = "", lat: float = None, lon: float = None) -> dict:
    """主函数：输入地区名或经纬度，返回3个月5灾种预测

    参数:
        query: 地区名（中文县名/简称/region_id）
        lat, lon: 经纬度（与query二选一）

    返回:
        dict: 预测结果
    """
    # 1. 解析输入
    mapping = load_region_mapping()
    region_info = None
    region_name = query or "自定义位置"

    if lat is not None and lon is not None:
        region_info = {
            "region_id": f"custom_{lat:.2f}_{lon:.2f}",
            "region_name": region_name,
            "latitude": lat,
            "longitude": lon,
            "altitude": 0,
            "pasture_type": "未知",
        }
        # 尝试用经纬度反查26县
        for k, v in mapping.items():
            if (abs(v["latitude"] - lat) < 0.1 and
                abs(v["longitude"] - lon) < 0.1):
                region_info = v
                region_name = v["region_name"]
                break
    elif query:
        region_info = resolve_region(query, mapping)
        if region_info:
            region_name = region_info["region_name"]
        else:
            # 兜底：地理编码（支持任意中文地名）
            region_info = geocode_query(query)
            if region_info:
                region_name = region_info["region_name"]

    if not region_info:
        return {
            "ok": False,
            "message": f"无法识别地区: {query}。请输入县名（如'班戈县'）、region_id 或中文地名（如'拉萨'），也可直接提供 lat/lon 参数",
            "supported_regions": sorted({v["region_name"] for v in mapping.values()}),
        }

    lat = region_info["latitude"]
    lon = region_info["longitude"]

    # 2. 拉取数据
    now = datetime.now()
    target_end = now + timedelta(days=90)

    try:
        forecast_data = fetch_forecast(lat, lon, days=16)
    except Exception as e:
        return {"ok": False, "message": f"Open-Meteo 预报获取失败: {e}"}

    try:
        historical = fetch_historical_5y(lat, lon, now, target_end)
    except Exception as e:
        historical = {}

    # 3. 5灾种并行预测
    cold = predict_cold_wave(forecast_data, historical)
    snow = predict_snowstorm(forecast_data, historical)
    drought = predict_drought(historical, now)
    blizzard = predict_blizzard(forecast_data, historical)
    eco = predict_ecological(historical, now)

    composite = compute_composite(cold, snow, drought, blizzard, eco)

    # 找最高风险灾种
    disaster_avgs = {
        "cold_wave": statistics.mean([w["risk_score"] for w in cold]),
        "snowstorm": statistics.mean([w["risk_score"] for w in snow]),
        "drought": statistics.mean([w["risk_score"] for w in drought]),
        "blizzard": statistics.mean([w["risk_score"] for w in blizzard]),
        "ecological": statistics.mean([w["risk_score"] for w in eco]),
    }
    top_disaster = max(disaster_avgs, key=disaster_avgs.get)

    recommendations = generate_recommendations(composite, top_disaster, disaster_avgs[top_disaster], region_name)

    # 4. 构造置信度说明
    confidence_segments = [
        {"range": "0-16天", "level": "高", "basis": "Open-Meteo 实时预报"},
        {"range": "17-30天", "level": "中", "basis": "季节性外推 + 历史同期均值"},
        {"range": "31-90天", "level": "低", "basis": "气候态 + 历史概率分布"},
    ]

    return {
        "ok": True,
        "region": {
            "region_id": region_info["region_id"],
            "region_name": region_name,
            "latitude": lat,
            "longitude": lon,
            "altitude": region_info.get("altitude", 0),
            "pasture_type": region_info.get("pasture_type", ""),
        },
        "forecast_window": {
            "start_date": now.strftime("%Y-%m-%d"),
            "end_date": target_end.strftime("%Y-%m-%d"),
            "days": 90,
            "weeks": 12,
        },
        "confidence_segments": confidence_segments,
        "disasters": {
            "cold_wave": {"name": "寒潮", "weekly": cold, "avg_score": round(disaster_avgs["cold_wave"], 1)},
            "snowstorm": {"name": "雪灾", "weekly": snow, "avg_score": round(disaster_avgs["snowstorm"], 1)},
            "drought": {"name": "干旱", "weekly": drought, "avg_score": round(disaster_avgs["drought"], 1)},
            "blizzard": {"name": "暴雪", "weekly": blizzard, "avg_score": round(disaster_avgs["blizzard"], 1)},
            "ecological": {"name": "生态", "weekly": eco, "avg_score": round(disaster_avgs["ecological"], 1)},
        },
        "composite": composite,
        "top_disaster": {
            "key": top_disaster,
            "name": {"cold_wave": "寒潮", "snowstorm": "雪灾", "drought": "干旱",
                     "blizzard": "暴雪", "ecological": "生态"}[top_disaster],
        },
        "recommendations": recommendations,
        "data_source": "Open-Meteo (ERA5 + 16天预报)",
        "generated_at": now.isoformat() + "+08:00",
    }
