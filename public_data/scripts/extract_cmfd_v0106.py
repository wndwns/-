"""
CMFD V0106 三变量区域提取脚本
================================================================
从 temp/prec/wind 三个NC文件提取25县气象数据。
时间范围: 2015-2018 (48个月, 与真实标签交集)

注意: netCDF4 C库不支持中文路径，NC文件须放在无中文路径下。
"""
import csv
import json
import sys
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT.parent / "backend"

# NC文件在无中文路径下
NC_DIR = Path(r"c:\Users\WH\Desktop\cmfd_temp")
NC_TEMP = NC_DIR / "temp_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc"
NC_PREC = NC_DIR / "prec_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc"
NC_WIND = NC_DIR / "wind_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc"

BOUNDS_PATH = ROOT / "region_bounds.json"
REGION_LIST = ROOT / "region_list.csv"

OUT_CSV = ROOT / "processed" / "weather_data_cmfd_regional_2015_2018.csv"
OUT_JSON = BACKEND / "data_store" / "climate_era5_regional.json"

START_YEAR = 2015
END_YEAR = 2018


def load_region_meta():
    regions = []
    with open(REGION_LIST, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            regions.append({
                "region_id": r["region_id"].strip(),
                "region_name": r["region_name"].strip(),
                "longitude": float(r["longitude"]),
                "latitude": float(r["latitude"]),
            })
    with open(BOUNDS_PATH, "r", encoding="utf-8") as f:
        bounds = json.load(f)
    for r in regions:
        b = bounds.get(r["region_id"])
        r["bbox"] = b if b else None
    return regions


def main():
    import netCDF4
    import numpy as np

    regions = load_region_meta()
    print(f"[1] 加载了 {len(regions)} 个县")

    # 打开3个NC文件
    print("[2] 打开NC文件...")
    ds_temp = netCDF4.Dataset(str(NC_TEMP), "r")
    ds_prec = netCDF4.Dataset(str(NC_PREC), "r")
    ds_wind = netCDF4.Dataset(str(NC_WIND), "r")

    lon_arr = np.asarray(ds_temp.variables["lon"][:])  # 700
    lat_arr = np.asarray(ds_temp.variables["lat"][:])  # 400
    n_total = ds_temp.dimensions["time"].size  # 480

    # 计算时间索引 (V0106从1979-01起算)
    months = []
    indices = []
    for i in range(n_total):
        y = 1979 + i // 12
        m = (i % 12) + 1
        if START_YEAR <= y <= END_YEAR:
            months.append(f"{y}-{m:02d}")
            indices.append(i)
    print(f"[3] 时间范围: {months[0]} ~ {months[-1]} ({len(months)} 个月)")

    # 检查scale_factor
    temp_var = ds_temp.variables["temp"]
    prec_var = ds_prec.variables["prec"]
    wind_var = ds_wind.variables["wind"]
    print(f"    temp: scale_factor={getattr(temp_var, 'scale_factor', None)}, add_offset={getattr(temp_var, 'add_offset', None)}")
    print(f"    prec: scale_factor={getattr(prec_var, 'scale_factor', None)}, add_offset={getattr(prec_var, 'add_offset', None)}")
    print(f"    wind: scale_factor={getattr(wind_var, 'scale_factor', None)}, add_offset={getattr(wind_var, 'add_offset', None)}")

    # 预计算每县的格点索引
    region_masks = {}
    for r in regions:
        if r.get("bbox"):
            b = r["bbox"]
            lon_idx = np.where((lon_arr >= b["min_lon"]) & (lon_arr <= b["max_lon"]))[0]
            lat_idx = np.where((lat_arr >= b["min_lat"]) & (lat_arr <= b["max_lat"]))[0]
            n_cells = len(lon_idx) * len(lat_idx)
            region_masks[r["region_id"]] = (lon_idx, lat_idx, n_cells)
        else:
            li = int(np.argmin(np.abs(lat_arr - r["latitude"])))
            lj = int(np.argmin(np.abs(lon_arr - r["longitude"])))
            region_masks[r["region_id"]] = (np.array([lj]), np.array([li]), 1)

    print(f"[4] 开始提取 {len(regions)} 县 × {len(months)} 月 = {len(regions) * len(months)} 行...")

    # 每月天数 (用于降水mm/hr转mm/month)
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    rows = []
    for i, idx in enumerate(indices):
        try:
            # 读取3个变量的该月数据
            temp_2d = ds_temp.variables["temp"][idx]  # (lat, lon)
            prec_2d = ds_prec.variables["prec"][idx]
            wind_2d = ds_wind.variables["wind"][idx]
        except Exception as e:
            print(f"  [warn] 月份 {months[i]} 读取失败: {e}")
            continue

        for r in regions:
            lon_idx, lat_idx, n_cells = region_masks[r["region_id"]]

            # 提取边界框内格点
            temp_sub = temp_2d[np.ix_(lat_idx, lon_idx)]
            prec_sub = prec_2d[np.ix_(lat_idx, lon_idx)]
            wind_sub = wind_2d[np.ix_(lat_idx, lon_idx)]

            # 均值 (netCDF4自动应用scale_factor+add_offset，掩膜填充值)
            # 用 np.ma.mean 自动忽略掩膜值
            temp_val = float(np.ma.mean(temp_sub)) if not np.ma.is_masked(temp_sub) or temp_sub.count() > 0 else None
            prec_val = float(np.ma.mean(prec_sub)) if not np.ma.is_masked(prec_sub) or prec_sub.count() > 0 else None
            wind_val = float(np.ma.mean(wind_sub)) if not np.ma.is_masked(wind_sub) or wind_sub.count() > 0 else None

            # 如果掩膜后全空，尝试手动过滤
            if temp_val is None or np.isnan(temp_val):
                t = np.asarray(temp_sub)
                t = t[t < 32700]
                temp_val = float(np.mean(t)) if len(t) > 0 else None
            if prec_val is None or np.isnan(prec_val):
                p = np.asarray(prec_sub)
                p = p[p < 32700]
                prec_val = float(np.mean(p)) if len(p) > 0 else None
            if wind_val is None or np.isnan(wind_val):
                w = np.asarray(wind_sub)
                w = w[w < 32700]
                wind_val = float(np.mean(w)) if len(w) > 0 else None

            if temp_val is not None:
                # 温度: K → ℃
                temp_c = temp_val - 273.15

                # 降水: mm/hr → mm/month
                m_idx = int(months[i].split("-")[1]) - 1
                prec_mm = prec_val * 24 * days_in_month[m_idx] if prec_val is not None else 0.0

                # 风速: m/s 直接用
                wind_ms = wind_val if wind_val is not None else 0.0

                # 寒潮风险
                if temp_c < -10:
                    cold_wave = "高"
                elif temp_c < 0:
                    cold_wave = "中"
                else:
                    cold_wave = "低"

                # 暴雪风险 (降水多+温度低)
                if prec_mm > 50 and temp_c < 0:
                    snowstorm = "高"
                elif prec_mm > 20 and temp_c < 0:
                    snowstorm = "中"
                else:
                    snowstorm = "低"

                # 干旱风险 (降水少)
                if prec_mm < 5:
                    drought = "高"
                elif prec_mm < 20:
                    drought = "中"
                else:
                    drought = "低"

                rows.append({
                    "region_id": r["region_id"],
                    "station": f"CMFD_regional_{r['region_id']}",
                    "observed_at": f"{months[i]}-01 00:00",
                    "temperature_c": round(temp_c, 1),
                    "precipitation_mm_24h": round(prec_mm, 1),
                    "wind_speed_mps": round(wind_ms, 1),
                    "snow_depth_cm": 0,
                    "cold_wave_risk": cold_wave,
                    "snowstorm_risk": snowstorm,
                    "drought_risk": drought,
                    "data_source": "tpdc",
                    "source_id": "cmfd-regional-v0106",
                    "dataset_name": "CMFD_V0106_regional",
                    "is_sample": False,
                    "imported_at": datetime.now().isoformat() + "+00:00",
                    "n_grid_cells": n_cells,
                })

        if (i + 1) % 12 == 0:
            print(f"  进度: {i+1}/{len(indices)} 月 ({months[i]})")
            sys.stdout.flush()

    ds_temp.close()
    ds_prec.close()
    ds_wind.close()

    # 写CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    print(f"\n[5] CSV已保存: {OUT_CSV} ({len(rows)} 行)")

    # 特别检查林芝
    linzhi_rows = [r for r in rows if "linzhi" in r["region_id"]]
    print(f"[6] 林芝数据: {len(linzhi_rows)} 行")
    if linzhi_rows:
        print(f"    首行: {linzhi_rows[0]}")

    # 写JSON (供early_warning.py用)
    climate = {}
    for row in rows:
        rid = row["region_id"]
        if rid not in climate:
            climate[rid] = []
        climate[rid].append({
            "date": row["observed_at"][:10],
            "temp_mean": row["temperature_c"],
            "precip_mm": row["precipitation_mm_24h"],
            "wind_speed": row["wind_speed_mps"],
        })

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(climate, f, ensure_ascii=False, indent=2)
    print(f"[7] JSON已保存: {OUT_JSON} ({len(climate)} 县)")

    return len(rows)


if __name__ == "__main__":
    main()
