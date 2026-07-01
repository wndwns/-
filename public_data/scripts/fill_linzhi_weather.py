"""
补林芝巴宜区 weather_data.json 2019-2024 月度数据
================================================================
当前林芝只有 48 月 (2015-2018)，其他县都有 108 月 (2015-2024)
需要补 60 月 (2019-2024) 的 temp/precip/wind/snow_depth

数据源：Open-Meteo Archive API
"""
import json
import urllib.request
import urllib.parse
from collections import defaultdict
from pathlib import Path
from datetime import datetime

ROOT = Path(r"c:\Users\WH\Desktop\gonghangbei - 副本")
WEATHER_JSON = ROOT / "backend" / "data_store" / "weather_data.json"

LAT, LON = 29.64, 94.36
REGION_ID = "linzhi-bayi"
START, END = "2019-01-01", "2024-12-31"

DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def fetch_daily(lat, lon, start, end):
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": "temperature_2m_mean,precipitation_sum,snowfall_sum,snow_depth_max,wind_speed_10m_max",
        "timezone": "UTC",
        "wind_speed_unit": "ms",
    }
    url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def is_leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)

def main():
    print("=" * 70)
    print("补林芝 weather_data.json 2019-2024 月度数据")
    print("=" * 70)

    with open(WEATHER_JSON, encoding="utf-8") as f:
        weather = json.load(f)

    # 看看现有林芝记录
    linzhi = [r for r in weather if r["region_id"] == REGION_ID]
    print(f"现有林芝记录: {len(linzhi)}")
    if linzhi:
        dates = sorted(r["observed_at"][:7] for r in linzhi)
        print(f"  时间范围: {dates[0]} ~ {dates[-1]}")

    # 看看现有记录的字段结构（用其他县参考）
    sample = next(r for r in weather if r["region_id"] == "naqu-bange" and r["observed_at"].startswith("2020-01"))
    print(f"\n字段模板: {list(sample.keys())}")

    # 获取 2019-2024 逐日数据
    print(f"\n[1] 获取林芝 {START} ~ {END} 逐日数据...")
    data = fetch_daily(LAT, LON, START, END)

    # 按月聚合
    months = defaultdict(lambda: {
        "temps": [], "precip": 0.0, "snowfall": 0.0,
        "snow_depth_max": 0.0, "wind_max": []
    })
    for date, t, p, sf, sd, w in zip(
        data["daily"]["time"],
        data["daily"]["temperature_2m_mean"],
        data["daily"]["precipitation_sum"],
        data["daily"]["snowfall_sum"],
        data["daily"]["snow_depth_max"],
        data["daily"]["wind_speed_10m_max"],
    ):
        ym = date[:7]
        if t is not None:
            months[ym]["temps"].append(t)
        if p is not None:
            months[ym]["precip"] += p
        if sf is not None:
            months[ym]["snowfall"] += sf
        if sd is not None:
            months[ym]["snow_depth_max"] = max(months[ym]["snow_depth_max"], sd)
        if w is not None:
            months[ym]["wind_max"].append(w)

    print(f"  获取 {len(months)} 月数据")

    # 生成新记录
    new_records = []
    for ym in sorted(months.keys()):
        # 跳过已存在的月份
        if any(r["observed_at"].startswith(ym) for r in linzhi):
            continue

        m = months[ym]
        y, mo = int(ym[:4]), int(ym[5:7])
        temp_c = round(sum(m["temps"]) / max(len(m["temps"]), 1), 1)
        precip_mm = round(m["precip"], 1)
        wind_ms = round(sum(m["wind_max"]) / max(len(m["wind_max"]), 1), 1) if m["wind_max"] else 0
        snow_depth_cm = round(m["snow_depth_max"] * 100, 1)  # m → cm

        # 风险等级判定
        cold_wave = "高" if temp_c < -10 else "中" if temp_c < 0 else "低"
        snowstorm = "高" if snow_depth_cm >= 15 else "中" if snow_depth_cm >= 10 else "低"
        drought = "中"  # 默认

        new_records.append({
            "region_id": REGION_ID,
            "station": f"OpenMeteo_linzhi",
            "observed_at": f"{ym}-01 00:00",
            "temperature_c": temp_c,
            "precipitation_mm_24h": precip_mm,
            "wind_speed_mps": wind_ms,
            "snow_depth_cm": snow_depth_cm,
            "cold_wave_risk": cold_wave,
            "snowstorm_risk": snowstorm,
            "drought_risk": drought,
            "data_source": "openmeteo",
            "source_id": "openmeteo-archive-linzhi",
            "dataset_name": "OPENMETEO_LINZHI_2019_2024",
            "is_sample": False,
            "imported_at": datetime.now().isoformat() + "+00:00",
        })

    print(f"\n[2] 新增 {len(new_records)} 条林芝月度记录")

    # 写回
    weather.extend(new_records)
    with open(WEATHER_JSON, "w", encoding="utf-8") as f:
        json.dump(weather, f, ensure_ascii=False, indent=2)
    print(f"\n已写回 weather_data.json: 总 {len(weather)} 条")

    # 验证
    linzhi_after = [r for r in weather if r["region_id"] == REGION_ID]
    print(f"林芝现有: {len(linzhi_after)} 月")
    dates = sorted(r["observed_at"][:7] for r in linzhi_after)
    print(f"  时间范围: {dates[0]} ~ {dates[-1]}")

    # 温度范围
    temps = [r["temperature_c"] for r in linzhi_after]
    print(f"  温度范围: {min(temps)}°C ~ {max(temps)}°C")
    snows = [r.get("snow_depth_cm", 0) for r in linzhi_after]
    snowy = sum(1 for s in snows if s > 0)
    print(f"  有雪月: {snowy}/{len(snows)}")

if __name__ == "__main__":
    main()
