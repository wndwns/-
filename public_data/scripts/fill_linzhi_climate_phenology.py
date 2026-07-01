"""
补林芝巴宜区气候+物候数据
================================================================
- climate_era5.json: 补 2020-2025 逐日 temp_mean + precip_mm
- phenology_by_region.json: 补 2003-2024 物候（温度阈值法推导）

数据源：Open-Meteo Archive API (ERA5)
"""
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(r"c:\Users\WH\Desktop\gonghangbei - 副本")
CLIMATE_JSON = ROOT / "backend" / "data_store" / "climate_era5.json"
PHEN_JSON = ROOT / "backend" / "data_store" / "phenology_by_region.json"

LAT, LON = 29.64, 94.36  # 林芝巴宜区
REGION_ID = "linzhi-bayi"
REGION_NAME = "林芝市巴宜区"

def fetch_daily(lat, lon, start, end, variables):
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": variables,
        "timezone": "UTC",
    }
    url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def fill_climate():
    """补 climate_era5.json 林芝 2020-2025 逐日数据"""
    print("\n[1] 补 climate_era5.json 林芝数据")
    with open(CLIMATE_JSON, encoding="utf-8") as f:
        climate = json.load(f)

    if REGION_ID in climate:
        print(f"  林芝已存在，跳过")
        return

    print(f"  获取 2020-01-01 ~ 2025-12-31 逐日数据...")
    data = fetch_daily(LAT, LON, "2020-01-01", "2025-12-31",
                       "temperature_2m_mean,precipitation_sum")

    rows = []
    for date, t, p in zip(data["daily"]["time"],
                          data["daily"]["temperature_2m_mean"],
                          data["daily"]["precipitation_sum"]):
        rows.append({
            "date": date,
            "temp_mean": round(t, 1) if t is not None else None,
            "precip_mm": round(p, 1) if p is not None else 0.0,
        })

    climate[REGION_ID] = rows
    with open(CLIMATE_JSON, "w", encoding="utf-8") as f:
        json.dump(climate, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 添加 {len(rows)} 天，林芝已写入 climate_era5.json")

def fill_phenology():
    """补 phenology_by_region.json 林芝 2003-2024 物候（温度阈值法）"""
    print("\n[2] 补 phenology_by_region.json 林芝物候")
    with open(PHEN_JSON, encoding="utf-8") as f:
        phen = json.load(f)

    if any(r["region_id"] == REGION_ID for r in phen):
        print(f"  林芝已存在，跳过")
        return

    print(f"  获取 2003-2024 逐日温度数据（用于推导物候）...")
    data = fetch_daily(LAT, LON, "2003-01-01", "2024-12-31",
                       "temperature_2m_mean,precipitation_sum")

    dates = data["daily"]["time"]
    temps = data["daily"]["temperature_2m_mean"]
    precs = data["daily"]["precipitation_sum"]

    # 按年聚合，找 greenup（连续5天日均温>=5°C）和 dormancy（连续5天<0°C）
    by_year = {}
    for date, t, p in zip(dates, temps, precs):
        y = int(date[:4])
        if y not in by_year:
            by_year[y] = []
        by_year[y].append((date, t, p))

    greenup_dict = {}
    dormancy_dict = {}
    growing_season_dict = {}

    for y in sorted(by_year.keys()):
        days = by_year[y]
        # 找 greenup: 连续5天 >= 5°C 的第一天
        g_doy = None
        for i in range(len(days) - 4):
            window = days[i:i+5]
            if all(d[1] is not None and d[1] >= 5.0 for d in window):
                g_doy = i + 1
                break

        # 找 dormancy: greenup 之后连续5天 < 0°C 的第一天
        d_doy = None
        if g_doy is not None:
            for i in range(g_doy, len(days) - 4):
                window = days[i:i+5]
                if all(d[1] is not None and d[1] < 0.0 for d in window):
                    d_doy = i + 1
                    break

        if g_doy and d_doy and d_doy > g_doy:
            greenup_dict[str(y)] = {"doy": g_doy, "days_since_epoch": None}
            dormancy_dict[str(y)] = {"doy": d_doy, "days_since_epoch": None}
            growing_season_dict[str(y)] = d_doy - g_doy

    # 统计
    gs_vals = list(growing_season_dict.values())
    g_doy_vals = [v["doy"] for v in greenup_dict.values()]
    d_doy_vals = [v["doy"] for v in dormancy_dict.values()]

    record = {
        "region_id": REGION_ID,
        "region_name": REGION_NAME,
        "longitude": LON,
        "latitude": LAT,
        "pixel_row": None,
        "pixel_col": None,
        "window_size": None,
        "years": sorted([int(y) for y in greenup_dict.keys()]),
        "data": {
            "greenup": greenup_dict,
            "dormancy": dormancy_dict,
            "growing_season": growing_season_dict,
        },
        "statistics": {
            "greenup_mean_doy": round(sum(g_doy_vals)/len(g_doy_vals), 1) if g_doy_vals else None,
            "greenup_min_doy": min(g_doy_vals) if g_doy_vals else None,
            "greenup_max_doy": max(g_doy_vals) if g_doy_vals else None,
            "dormancy_mean_doy": round(sum(d_doy_vals)/len(d_doy_vals), 1) if d_doy_vals else None,
            "dormancy_min_doy": min(d_doy_vals) if d_doy_vals else None,
            "dormancy_max_doy": max(d_doy_vals) if d_doy_vals else None,
            "growing_season_mean_days": round(sum(gs_vals)/len(gs_vals), 1) if gs_vals else None,
            "growing_season_min_days": min(gs_vals) if gs_vals else None,
            "growing_season_max_days": max(gs_vals) if gs_vals else None,
            "growing_season_std_days": None,
            "greenup_trend_days_per_year": None,
            "dormancy_trend_days_per_year": None,
            "growing_season_trend_days_per_year": None,
        },
        "interpretation": {
            "greenup": "温度阈值法推导(>=5°C连续5天)",
            "dormancy": "温度阈值法推导(<0°C连续5天)",
            "growing_season": f"基于温度推导，{len(gs_vals)}年有效",
        },
        "note": "由 Open-Meteo ERA5 日均温推导，非 MODIS MCD12Q2 真实物候"
    }

    phen.append(record)
    with open(PHEN_JSON, "w", encoding="utf-8") as f:
        json.dump(phen, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 添加 {len(greenup_dict)} 年物候数据")
    if gs_vals:
        print(f"  生长季均值: {sum(gs_vals)/len(gs_vals):.1f} 天")
        print(f"  greenup DOY: {min(g_doy_vals)}~{max(g_doy_vals)}")
        print(f"  dormancy DOY: {min(d_doy_vals)}~{max(d_doy_vals)}")

def main():
    print("=" * 70)
    print("补林芝气候+物候数据")
    print("=" * 70)
    fill_climate()
    fill_phenology()
    print("\n" + "=" * 70)
    print("完成")

if __name__ == "__main__":
    main()
