"""
把CMFD V0106提取的CSV数据导入到后端weather_data.json
"""
import csv
import json
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT.parent / "backend"

CSV_PATH = ROOT / "processed" / "weather_data_cmfd_regional_2015_2018.csv"
JSON_PATH = BACKEND / "data_store" / "weather_data.json"


def main():
    # 1. 加载现有数据
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        existing = json.load(f)
    print(f"[1] 现有weather_data: {len(existing)}行")
    if existing:
        print(f"    字段: {list(existing[0].keys())}")
        linzhi_old = sum(1 for r in existing if "linzhi" in r.get("region_id", ""))
        print(f"    林芝行数: {linzhi_old}")

    # 2. 读取新CSV
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        new_rows = list(csv.DictReader(f))
    print(f"[2] 新CSV数据: {len(new_rows)}行")

    # 3. 去重: 用 (region_id, observed_at) 作为唯一键
    existing_keys = set()
    for r in existing:
        key = (r.get("region_id", ""), r.get("observed_at", ""))
        existing_keys.add(key)

    added = 0
    skipped = 0
    for row in new_rows:
        key = (row["region_id"], row["observed_at"])
        if key in existing_keys:
            skipped += 1
        else:
            # 转换为与现有数据一致的格式
            new_row = {
                "region_id": row["region_id"],
                "station": row["station"],
                "observed_at": row["observed_at"],
                "temperature_c": float(row["temperature_c"]) if row["temperature_c"] else None,
                "precipitation_mm_24h": float(row["precipitation_mm_24h"]) if row["precipitation_mm_24h"] else None,
                "wind_speed_mps": float(row["wind_speed_mps"]) if row["wind_speed_mps"] else None,
                "snow_depth_cm": int(row["snow_depth_cm"]) if row["snow_depth_cm"] else 0,
                "cold_wave_risk": row["cold_wave_risk"],
                "snowstorm_risk": row["snowstorm_risk"],
                "drought_risk": row["drought_risk"],
                "data_source": row["data_source"],
                "source_id": row["source_id"],
                "dataset_name": row["dataset_name"],
                "is_sample": row["is_sample"] == "True",
                "imported_at": row["imported_at"],
            }
            existing.append(new_row)
            existing_keys.add(key)
            added += 1

    print(f"[3] 导入结果: 新增{added}行, 跳过{skipped}行(重复)")

    # 4. 保存
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"[4] 已保存: {JSON_PATH} (共{len(existing)}行)")

    # 5. 验证林芝
    linzhi_new = sum(1 for r in existing if "linzhi" in r.get("region_id", ""))
    print(f"[5] 林芝数据: {linzhi_new}行")

    # 6. 统计
    regions = set(r.get("region_id", "") for r in existing)
    months = set(r.get("observed_at", "")[:7] for r in existing)
    print(f"[6] 统计: {len(regions)}县, {len(months)}月, 共{len(existing)}行")
    print(f"    月份范围: {sorted(months)[:3]}...{sorted(months)[-3:]}")


if __name__ == "__main__":
    main()
