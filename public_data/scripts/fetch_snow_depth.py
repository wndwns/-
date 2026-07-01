"""
从 Open-Meteo Archive API 获取 26县 2015-2024 逐月雪深数据
================================================================
- daily snow_depth_max (m) → 月最大值 → 转 cm
- daily snowfall_sum (cm) → 月累计降雪
- 合并到 weather_data.json 的 snow_depth_cm 字段
"""
import json
import time
import urllib.request
import urllib.parse
from collections import defaultdict
from pathlib import Path
from datetime import datetime
import csv

ROOT = Path(r"c:\Users\WH\Desktop\gonghangbei - 副本")
REGION_CSV = ROOT / "public_data" / "region_list.csv"
WEATHER_JSON = ROOT / "backend" / "data_store" / "weather_data.json"
OUT_BACKUP = ROOT / "backend" / "data_store" / "weather_data.json.bak_snow"

START_DATE = "2015-01-01"
END_DATE = "2024-12-31"

def load_regions():
    regions = []
    with open(REGION_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            regions.append({
                "region_id": r["region_id"].strip(),
                "region_name": r["region_name"].strip(),
                "longitude": float(r["longitude"]),
                "latitude": float(r["latitude"]),
            })
    return regions

def fetch_snow(lat, lon):
    """请求 Open-Meteo 获取 2015-2024 逐日雪深+降雪"""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "daily": "snowfall_sum,snow_depth_max",
        "timezone": "UTC",
    }
    url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def aggregate_monthly(daily_data):
    """日数据 → 月聚合：snow_depth_max 取月内最大值，snowfall_sum 取月累计"""
    months = defaultdict(lambda: {"snow_depth_max": 0.0, "snowfall_sum": 0.0, "days": 0})
    times = daily_data["daily"]["time"]
    snow_depths = daily_data["daily"]["snow_depth_max"]
    snowfalls = daily_data["daily"]["snowfall_sum"]

    for date, sd, sf in zip(times, snow_depths, snowfalls):
        ym = date[:7]  # YYYY-MM
        if sd is not None:
            months[ym]["snow_depth_max"] = max(months[ym]["snow_depth_max"], sd)
        if sf is not None:
            months[ym]["snowfall_sum"] += sf
        months[ym]["days"] += 1

    # 转换：m → cm
    result = {}
    for ym, v in months.items():
        result[ym] = {
            "snow_depth_cm": round(v["snow_depth_max"] * 100, 1),  # m → cm
            "snowfall_cm": round(v["snowfall_sum"], 1),
        }
    return result

def main():
    print("=" * 70)
    print("Open-Meteo 雪深数据获取（26县 × 2015-2024）")
    print("=" * 70)

    regions = load_regions()
    print(f"区域数: {len(regions)}")

    # 备份
    if not OUT_BACKUP.exists():
        import shutil
        shutil.copy(WEATHER_JSON, OUT_BACKUP)
        print(f"已备份: {OUT_BACKUP.name}")

    # 加载现有 weather_data
    with open(WEATHER_JSON, encoding="utf-8") as f:
        weather = json.load(f)
    print(f"现有 weather_data: {len(weather)} 条")

    # 索引：(region_id, YYYY-MM) → record
    idx = {}
    for r in weather:
        ym = r["observed_at"][:7]
        idx[(r["region_id"], ym)] = r

    # 逐县获取
    all_snow = {}
    success, fail = 0, 0
    for i, reg in enumerate(regions, 1):
        rid = reg["region_id"]
        print(f"\n[{i}/{len(regions)}] {rid} ({reg['region_name']})", flush=True)

        retries = 0
        while retries < 3:
            try:
                data = fetch_snow(reg["latitude"], reg["longitude"])
                monthly = aggregate_monthly(data)
                all_snow[rid] = monthly
                success += 1
                # 统计有效雪深月数
                snowy = sum(1 for v in monthly.values() if v["snow_depth_cm"] > 0)
                print(f"  ✓ {len(monthly)} 月，{snowy} 月有雪", flush=True)
                break
            except Exception as e:
                retries += 1
                print(f"  ✗ 尝试 {retries}/3 失败: {e}", flush=True)
                time.sleep(3 * retries)
        else:
            fail += 1
            all_snow[rid] = {}

        # 礼貌延迟
        time.sleep(0.5)

    print(f"\n获取完成: {success} 成功, {fail} 失败")

    # 合并到 weather_data
    updated = 0
    new_records = []
    for rid, monthly in all_snow.items():
        for ym, v in monthly.items():
            key = (rid, ym)
            if key in idx:
                # 更新现有记录
                idx[key]["snow_depth_cm"] = v["snow_depth_cm"]
                # 同时更新 snowstorm_risk
                if v["snow_depth_cm"] >= 15:
                    idx[key]["snowstorm_risk"] = "高"
                elif v["snow_depth_cm"] >= 10:
                    idx[key]["snowstorm_risk"] = "中"
                else:
                    idx[key]["snowstorm_risk"] = "低"
                updated += 1
            # 不存在则跳过（避免破坏现有结构）
            # 因为 weather_data 还需要其他字段，单雪深记录不完整

    print(f"\n更新记录: {updated} 条")

    # 保存
    with open(WEATHER_JSON, "w", encoding="utf-8") as f:
        json.dump(weather, f, ensure_ascii=False, indent=2)
    print(f"已写回: {WEATHER_JSON}")

    # 额外：单独保存雪深数据备用
    snow_out = ROOT / "backend" / "data_store" / "snow_depth_openmeteo.json"
    with open(snow_out, "w", encoding="utf-8") as f:
        json.dump(all_snow, f, ensure_ascii=False, indent=2)
    print(f"雪深原始数据: {snow_out}")

    # 统计
    snowy_total = sum(
        1 for rid, monthly in all_snow.items()
        for v in monthly.values() if v["snow_depth_cm"] > 0
    )
    total_months = sum(len(m) for m in all_snow.values())
    print(f"\n雪深>0 的月份: {snowy_total}/{total_months} ({snowy_total*100//max(total_months,1)}%)")

if __name__ == "__main__":
    main()
