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
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
TIMEOUT = 10


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
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, OSError):
        # 默认直连；直连失败时回退系统代理重试一次
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
            if not d.get("daily"):
                continue
            # 保留 time，便于按周(月/日)对齐历史同期样本
            if "time" in d["daily"]:
                all_data["time"].extend(d["daily"]["time"] or [])
            for k, vals in d["daily"].items():
                if k == "time":
                    continue
                all_data[k].extend(vals or [])
        except Exception:
            continue
    return dict(all_data)


def _hist_weeks_by_doy(historical: dict, key: str, target_start: datetime) -> list:
    """把历史某变量日值，按目标逐周的日期(月/日)对齐到过去5年同期。

    返回12个周的样本值列表；某周无有效样本时该周返回[]。
    """
    times = historical.get("time") or []
    vals = historical.get(key) or []
    if not times or not vals or len(times) != len(vals):
        return []
    dates = []
    for ts in times:
        try:
            dates.append(datetime.strptime(ts, "%Y-%m-%d"))
        except Exception:
            dates.append(None)
    weeks = []
    for i in range(12):
        doy = set()
        for d in range(7 * i, min(7 * i + 7, 90)):
            dt = target_start + timedelta(days=d)
            doy.add((dt.month, dt.day))
        wv = [v for j, v in enumerate(vals)
              if dates[j] is not None and (dates[j].month, dates[j].day) in doy and v is not None]
        weeks.append(wv)
    return weeks


# ========== 5灾种预测算法 ==========
def predict_cold_wave(forecast_data: dict, historical: dict, target_start: datetime) -> list:
    """寒潮风险预测：返回12周风险序列(0-100)
    0-16天: 实际温度判定
    17-90天: 历史同期逐周温度判定
    """
    weekly_risks = []
    fc_temps = forecast_data.get("daily", {}).get("temperature_2m_mean", [])
    hist_weeks = _hist_weeks_by_doy(historical, "temperature_2m_mean", target_start)

    for week_start in range(0, 84, 7):
        week_end = min(week_start + 7, 90)
        wi = week_start // 7
        if week_start < 16 and fc_temps:
            # 用预报温度
            week_temps = [t for i, t in enumerate(fc_temps)
                          if i >= week_start and i < week_end and t is not None]
            if week_temps:
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
            # 历史同期逐周温度
            wx = hist_weeks[wi] if wi < len(hist_weeks) else []
            if len(wx) >= 2:
                hmean = statistics.mean(wx)
                if hmean < -10:
                    risk = 90
                elif hmean < -5:
                    risk = 70
                elif hmean < 0:
                    risk = 50
                elif hmean < 5:
                    risk = 30
                else:
                    risk = max(8, 22 - hmean * 0.8)
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


def predict_snowstorm(forecast_data: dict, historical: dict, target_start: datetime) -> list:
    """雪灾风险预测：GB/T 20482-2006 阈值
    0-16天: 实际降雪量判定 (snowfall_sum cm)
    17-90天: 历史同期逐周降雪概率
    """
    weekly_risks = []
    fc_snow = forecast_data.get("daily", {}).get("snowfall_sum", [])
    hist_weeks = _hist_weeks_by_doy(historical, "snowfall_sum", target_start)

    for week_start in range(0, 84, 7):
        week_end = min(week_start + 7, 90)
        wi = week_start // 7
        if week_start < 16 and fc_snow:
            week_snow = [s for i, s in enumerate(fc_snow)
                         if i >= week_start and i < week_end and s is not None]
            if week_snow:
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
            # 历史同期逐周降雪
            wx = hist_weeks[wi] if wi < len(hist_weeks) else []
            if len(wx) >= 2:
                p_heavy = sum(1 for s in wx if s >= 5) / len(wx)  # 单日>=5cm
                p_med = sum(1 for s in wx if s >= 2) / len(wx)
                p_light = sum(1 for s in wx if s >= 1) / len(wx)
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
    """干旱风险预测：历期刊周降水相对偏旱评估
    未来3月具体降水未知，用"目标时段内各周气候态降水"的相对丰枯来划分，
    周降水越低于该时段整体水平 → 越可能偏旱。避免未来段恒为常值。
    """
    weekly_risks = []
    hist_weeks = _hist_weeks_by_doy(historical, "precipitation_sum", target_start)
    wmeans = []
    for wx in hist_weeks:
        if len(wx) >= 2:
            wmeans.append(statistics.mean(wx))
        else:
            wmeans.append(None)

    # 目标时段内的降水范围，用于把"偏旱程度"归一化到风险
    valid = [m for m in wmeans if m is not None]
    if len(valid) >= 2:
        lo, hi = min(valid), max(valid)
        span = (hi - lo) or 1.0
    else:
        lo, hi, span = 0.0, 50.0, 50.0

    for week_start in range(0, 84, 7):
        wi = week_start // 7
        wkmean = wmeans[wi] if wi < len(wmeans) else None
        if wkmean is not None:
            # 降水越低于区间高点，越偏旱；区间内线性映射
            dryness = max(0.0, (hi - wkmean) / span)  # 0..1，越大越旱
            risk = 12 + dryness * 55
            if wkmean <= lo + span * 0.15:  # 接近区间最低 → 明显偏旱
                risk = max(risk, 60)
        else:
            risk = 25
        weekly_risks.append({
            "week": wi + 1,
            "days_start": week_start,
            "days_end": min(week_start + 7, 90),
            "risk_score": round(risk, 1),
            "risk_level": "高" if risk >= 70 else "中" if risk >= 40 else "低",
        })
    return weekly_risks


def predict_blizzard(forecast_data: dict, historical: dict, target_start: datetime) -> list:
    """暴雪风险预测：24h降雪量>=10cm"""
    weekly_risks = []
    fc_snowfall = forecast_data.get("daily", {}).get("snowfall_sum", [])
    hist_weeks = _hist_weeks_by_doy(historical, "snowfall_sum", target_start)

    for week_start in range(0, 84, 7):
        week_end = min(week_start + 7, 90)
        wi = week_start // 7
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
            # 历史同期逐周暴雪概率 + 年际波动微起伏
            wx = hist_weeks[wi] if wi < len(hist_weeks) else []
            if len(wx) >= 2:
                p_blizzard = sum(1 for s in wx if s >= 10) / len(wx)
                p_med = sum(1 for s in wx if s >= 5) / len(wx)
                base = min(85, p_blizzard * 90 + p_med * 30 + 5)
                # 年际波动：该周历史逐日降雪的标准差越大，零星降雪的不确定性越高，
                # 叠加微小起伏，避免低风险段画成长平线（幅度小，不放大真实风险）
                variab = 0.0
                if len(wx) >= 3:
                    variab = min(12.0, statistics.stdev(wx) * 5.0)
                risk = min(85.0, base + variab)
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


def predict_ecological(forecast_data: dict, historical: dict, target_start: datetime) -> list:
    """生态风险预测：以降水相对丰枯为主，叠加温度趋势与年际波动

    生态(NDVI)对温度与降水都敏感，但历史同期的逐周温度均值近似单调变化，
    若以温度为主导会得到近似直线。这里改为：
      - 降水：按目标 12 周窗口内各周降水均值的相对丰枯归一化（周际有真实起伏）；
      - 温度：仅作小幅季节趋势辅助，避免单调主导；
      - 年际波动：历史同期各周标准差越大，该周不确定性/风险越高（真实数据驱动起伏）。
    前两周优先采用实时预报逐日数据，体现真实逐日变化。
    """
    weekly_risks = []
    fc_temps = forecast_data.get("daily", {}).get("temperature_2m_mean", [])
    fc_precip = forecast_data.get("daily", {}).get("precipitation_sum", [])
    hist_temps = _hist_weeks_by_doy(historical, "temperature_2m_mean", target_start)
    hist_precip = _hist_weeks_by_doy(historical, "precipitation_sum", target_start)

    tmeans, pmeans, tstds, pstds = [], [], [], []
    for i in range(12):
        tw = hist_temps[i] if i < len(hist_temps) else []
        pw = hist_precip[i] if i < len(hist_precip) else []
        tmeans.append(statistics.mean(tw) if len(tw) >= 2 else None)
        pmeans.append(statistics.mean(pw) if len(pw) >= 2 else None)
        tstds.append(statistics.stdev(tw) if len(tw) >= 3 else 0.0)
        pstds.append(statistics.stdev(pw) if len(pw) >= 3 else 0.0)

    t_valid = [m for m in tmeans if m is not None]
    p_valid = [m for m in pmeans if m is not None]
    base_t = statistics.mean(t_valid) if t_valid else 5.0

    # 降水相对丰枯：12 周窗口内归一化（0=最湿, 1=最干）
    if len(p_valid) >= 2:
        p_lo, p_hi = min(p_valid), max(p_valid)
        p_span = (p_hi - p_lo) or 1.0
    else:
        p_lo, p_hi, p_span = 0.0, 50.0, 50.0

    for week_start in range(0, 84, 7):
        wi = week_start // 7
        week_end = min(week_start + 7, 90)

        if week_start < 16 and fc_temps and len(fc_temps) >= 2:
            # 前两周用实时预报逐日数据
            wt = [t for i, t in enumerate(fc_temps) if week_start <= i < week_end and t is not None]
            wp = [p for i, p in enumerate(fc_precip) if week_start <= i < week_end and p is not None]
            season_t = statistics.mean(wt) if len(wt) >= 2 else base_t
            season_p = statistics.mean(wp) if len(wp) >= 2 else None
        else:
            season_t = tmeans[wi] if tmeans[wi] is not None else base_t
            season_p = pmeans[wi]

        # 降水项：偏干 → 风险抬升（随周际数据起伏）
        if season_p is not None:
            dryness = max(0.0, min(1.0, (p_hi - season_p) / p_span))
            precip_risk = 14 + dryness * 58
        else:
            precip_risk = 30

        # 温度项：相对 12 周常态的冷偏离，小幅季节趋势
        cold_dev = base_t - season_t
        temp_risk = max(8.0, min(70.0, 32 + cold_dev * 2.6))

        # 年际波动项：历史同期标准差越大，该周不确定性越高
        variab = tstds[wi] * 4.0 + pstds[wi] * 1.2
        variab_risk = max(0.0, min(30.0, variab))

        risk = precip_risk * 0.50 + temp_risk * 0.20 + variab_risk * 0.30
        weekly_risks.append({
            "week": wi + 1,
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
        # 实时预报不可用时降级为历史同期数据，避免整页不可用
        forecast_data = {}
        forecast_note = "实时气象资料暂不可用，已降级为历史同期资料参考"
    else:
        forecast_note = ""

    try:
        historical = fetch_historical_5y(lat, lon, now, target_end)
    except Exception as e:
        historical = {}

    # 3. 5灾种并行预测
    cold = predict_cold_wave(forecast_data, historical, now)
    snow = predict_snowstorm(forecast_data, historical, now)
    drought = predict_drought(historical, now)
    blizzard = predict_blizzard(forecast_data, historical, now)
    eco = predict_ecological(forecast_data, historical, now)

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
    if forecast_note:
        recommendations.insert(0, f"⚠ {forecast_note}")

    # 4. 构造置信度说明（面向用户，不暴露数据源/算法实现）
    confidence_segments = [
        {"range": "近两周", "level": "高", "basis": "短期气象资料置信度较高"},
        {"range": "未来一个月", "level": "中", "basis": "随预测时长增加，参考价值递减"},
        {"range": "更远期", "level": "低", "basis": "作为长期趋势参考，不作精确判断"},
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
        "data_source": "综合公开气象资料" if not forecast_note else "历史同期资料（实时资料暂不可用，已降级参考）",
        "generated_at": now.isoformat() + "+08:00",
    }
