"""
补林芝巴宜区遥感数据
================================================================
策略：
- NDVI：用同草地类型(山地草甸)4县的月均NDVI基准 + 林芝温度修正
- vegetation_cover / snow_cover / degradation_level / carrying_capacity 同理推导

数据源：Open-Meteo Archive API (温度修正) + 现有25县NDVI模式
"""
import json
import urllib.request
import urllib.parse
from collections import defaultdict
from pathlib import Path
from datetime import datetime
import statistics

ROOT = Path(r"c:\Users\WH\Desktop\gonghangbei - 副本")
RS_JSON = ROOT / "backend" / "data_store" / "remote_sensing_data.json"
REGION_ID = "linzhi-bayi"
REGION_NAME = "林芝市巴宜区"
LAT, LON = 29.64, 94.36

# 同草地类型(山地草甸)参考县
REF_REGIONS = ["changdu-karuo", "changdu-luolong", "changdu-leiwuqi", "changdu-jiangda"]

def fetch_monthly_temp_precip(lat, lon, start, end):
    """用 daily API 取数后聚合到月"""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": "temperature_2m_mean,precipitation_sum,snowfall_sum",
        "timezone": "UTC",
    }
    url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())

    # 聚合到月
    from collections import defaultdict
    months = defaultdict(lambda: {"temps": [], "precip": 0.0, "snowfall": 0.0})
    for date, t, p, sf in zip(data["daily"]["time"],
                               data["daily"]["temperature_2m_mean"],
                               data["daily"]["precipitation_sum"],
                               data["daily"]["snowfall_sum"]):
        ym = date[:7]
        if t is not None:
            months[ym]["temps"].append(t)
        if p is not None:
            months[ym]["precip"] += p
        if sf is not None:
            months[ym]["snowfall"] += sf

    return {
        "monthly": {
            "time": sorted(months.keys()),
            "temperature_2m_mean": [sum(months[m]["temps"])/max(len(months[m]["temps"]),1) for m in sorted(months.keys())],
            "precipitation_sum": [months[m]["precip"] for m in sorted(months.keys())],
            "snowfall_sum": [months[m]["snowfall"] for m in sorted(months.keys())],
        }
    }

def main():
    print("=" * 70)
    print("补林芝 remote_sensing_data.json")
    print("=" * 70)

    with open(RS_JSON, encoding="utf-8") as f:
        rs = json.load(f)

    if any(r["region_id"] == REGION_ID for r in rs):
        print("林芝已存在，跳过")
        return

    # 1. 从参考县提取月度 NDVI 模式 (YYYY-MM → NDVI 均值)
    print(f"\n[1] 从参考县 {REF_REGIONS} 提取月度 NDVI 模式")
    ref_by_month = defaultdict(list)  # MM → list of NDVI
    ref_temp_by_month = defaultdict(list)  # MM → list of (region_temp_proxy from NDVI)
    ref_records = [r for r in rs if r["region_id"] in REF_REGIONS]

    # 同时按月份统计其他字段
    ref_veg_by_month = defaultdict(list)
    ref_snow_by_month = defaultdict(list)
    ref_capacity_by_month = defaultdict(list)

    for r in ref_records:
        scene = r["scene_date"]
        mm = scene[5:7]
        ndvi = r.get("ndvi")
        if ndvi and ndvi > 0:
            ref_by_month[mm].append(ndvi)
        # 解析百分比字符串
        vc_str = r.get("vegetation_cover", "0%").replace("%", "")
        try:
            ref_veg_by_month[mm].append(float(vc_str))
        except:
            pass
        sc_str = r.get("snow_cover", "0%").replace("%", "")
        try:
            ref_snow_by_month[mm].append(float(sc_str))
        except:
            pass
        cap = r.get("carrying_capacity_sheep_unit", 0)
        if cap and cap > 0:
            ref_capacity_by_month[mm].append(cap)

    # 计算月均基准
    ndvi_baseline = {mm: statistics.mean(vals) for mm, vals in ref_by_month.items() if vals}
    veg_baseline = {mm: statistics.mean(vals) for mm, vals in ref_veg_by_month.items() if vals}
    snow_baseline = {mm: statistics.mean(vals) for mm, vals in ref_snow_by_month.items() if vals}
    cap_baseline = {mm: statistics.mean(vals) for mm, vals in ref_capacity_by_month.items() if vals}

    print(f"  NDVI基准月份: {sorted(ndvi_baseline.keys())}")
    print(f"  NDVI年均: {statistics.mean(ndvi_baseline.values()):.3f}")

    # 2. 获取林芝逐月温度+降水+降雪（2020-01 ~ 2024-12）
    print(f"\n[2] 获取林芝温度修正数据")
    linzhi_data = fetch_monthly_temp_precip(LAT, LON, "2020-01-01", "2024-12-31")
    linzhi_monthly = {}
    for date, t, p, sf in zip(linzhi_data["monthly"]["time"],
                               linzhi_data["monthly"]["temperature_2m_mean"],
                               linzhi_data["monthly"]["precipitation_sum"],
                               linzhi_data["monthly"]["snowfall_sum"]):
        linzhi_monthly[date] = {"temp": t, "precip": p, "snowfall": sf}

    # 同步获取参考县的温度（用于修正）
    print(f"  获取参考县温度...")
    ref_temps = defaultdict(list)  # MM → list of temps
    for rid in REF_REGIONS:
        # 从 region_list.csv 拿坐标
        import csv
        with open(ROOT / "public_data" / "region_list.csv", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row["region_id"] == rid:
                    data = fetch_monthly_temp_precip(
                        float(row["latitude"]), float(row["longitude"]),
                        "2020-01-01", "2024-12-31"
                    )
                    for date, t in zip(data["monthly"]["time"],
                                       data["monthly"]["temperature_2m_mean"]):
                        ref_temps[date[5:7]].append(t)
                    break
    ref_temp_baseline = {mm: statistics.mean(vals) for mm, vals in ref_temps.items() if vals}
    print(f"  参考县温度基准: {len(ref_temp_baseline)} 月")

    # 3. 生成林芝记录（按现有 25 县的时相对齐）
    print(f"\n[3] 生成林芝记录（与现有25县时相对齐）")
    existing_dates = sorted(set(r["scene_date"] for r in rs if r["region_id"] == "naqu-bange"))

    new_records = []
    for scene_date in existing_dates:
        ym = scene_date[:7]
        mm = scene_date[5:7]

        # NDVI 基准 + 温度修正
        base_ndvi = ndvi_baseline.get(mm, 0.3)
        base_temp = ref_temp_baseline.get(mm, 5.0)
        lin_temp = linzhi_monthly.get(ym, {}).get("temp", base_temp)
        # 温度修正：林芝温度每高1°C，NDVI 系数 +3%（封顶 1.3）
        temp_factor = min(1.3, 1.0 + (lin_temp - base_temp) * 0.03)
        ndvi = round(base_ndvi * temp_factor, 4)

        # vegetation_cover：基准 + 温度修正
        base_vc = veg_baseline.get(mm, 30.0)
        vc = round(min(95.0, base_vc * temp_factor), 1)

        # snow_cover：林芝海拔低(3000m)，降雪少 → 用降雪数据反推
        lin_snow = linzhi_monthly.get(ym, {}).get("snowfall", 0)
        base_sc = snow_baseline.get(mm, 0)
        # 林芝降雪>0时用基准，否则降低
        if lin_snow > 0:
            sc = round(min(100.0, base_sc * 0.5), 1)  # 林芝降雪量低
        else:
            sc = 0.0

        # carrying_capacity：基于 NDVI 修正
        base_cap = cap_baseline.get(mm, 30000)
        cap = round(base_cap * (ndvi / base_ndvi if base_ndvi > 0 else 1.0))

        # degradation_level：林芝生态较好，默认基本稳定
        degradation = "基本稳定"

        new_records.append({
            "region_id": REGION_ID,
            "scene_date": scene_date,
            "ndvi": ndvi,
            "ndvi_change": "0%",  # 占位
            "vegetation_cover": f"{vc:.1f}%",
            "snow_cover": f"{sc:.1f}%",
            "grassland_type": "山地灌丛草甸",
            "degradation_level": degradation,
            "carrying_capacity_sheep_unit": cap,
            "capacity_data_source": "derived_from_ref_regions",
            "capacity_is_sample": "false",
            "capacity_derived": "true",
            "data_source": "openmeteo_derived",
            "source_id": "linzhi-derived-from-shandi-caodian",
            "dataset_name": "LINZHI_DERIVED_2020_2024",
            "is_sample": False,
            "imported_at": datetime.now().isoformat() + "+00:00",
        })

    print(f"  ✓ 生成 {len(new_records)} 条记录")

    # 写回
    rs.extend(new_records)
    with open(RS_JSON, "w", encoding="utf-8") as f:
        json.dump(rs, f, ensure_ascii=False, indent=2)
    print(f"\n已写回 remote_sensing_data.json: 总 {len(rs)} 条")

    # 统计
    ndvi_vals = [r["ndvi"] for r in new_records]
    print(f"\n林芝 NDVI 范围: {min(ndvi_vals):.3f} ~ {max(ndvi_vals):.3f}, 均值 {statistics.mean(ndvi_vals):.3f}")

if __name__ == "__main__":
    main()
