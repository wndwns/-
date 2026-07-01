"""
CMFD 气象数据区域提取脚本
================================================================
改进: 从"县中心单格点"改为"县域边界框内所有格点均值"。

用法:
    python public_data/scripts/extract_cmfd_regional.py

输入:
    - public_data/raw/tpdc/cmfd/temp_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc
    - public_data/region_bounds.json (县域边界框)
    - public_data/region_list.csv (县域元数据)

输出:
    - public_data/processed/weather_data_cmfd_regional_2015_2018.csv
    - backend/data_store/climate_era5_regional.json (逐日格式, 供 early_warning.py 用)
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT.parent / "backend"

NC_PATH = ROOT / "raw" / "tpdc" / "cmfd" / "temp_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc"
NC_PREC_PATH = ROOT / "raw" / "tpdc" / "cmfd" / "prec_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc"
NC_WIND_PATH = ROOT / "raw" / "tpdc" / "cmfd" / "wind_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc"
BOUNDS_PATH = ROOT / "region_bounds.json"
REGION_LIST = ROOT / "region_list.csv"

OUT_CSV = ROOT / "processed" / "weather_data_cmfd_regional_2015_2018.csv"
OUT_JSON = BACKEND / "data_store" / "climate_era5_regional.json"

START_YEAR = 2015
END_YEAR = 2018


def load_region_meta():
    """读取 region_list.csv + region_bounds.json，合并返回。"""
    regions = []
    with open(REGION_LIST, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            regions.append({
                "region_id": r["region_id"].strip(),
                "region_name": r["region_name"].strip(),
                "longitude": float(r["longitude"]),
                "latitude": float(r["latitude"]),
                "altitude": float(r.get("altitude", 0) or 0),
                "pasture_type": r.get("pasture_type", "").strip(),
            })
    with open(BOUNDS_PATH, "r", encoding="utf-8") as f:
        bounds = json.load(f)
    for r in regions:
        b = bounds.get(r["region_id"])
        if b:
            r["bbox"] = b
        else:
            print(f"[warn] {r['region_id']} 无边界框, 回退到单点")
            r["bbox"] = None
    return regions


def extract_cmfd_regional(regions: list[dict]) -> int:
    """用边界框提取 CMFD 温度区域均值。"""
    import netCDF4
    import numpy as np

    if not NC_PATH.exists():
        print(f"[error] CMFD NetCDF 不存在: {NC_PATH}")
        return 0

    print(f"[cmfd] 打开 {NC_PATH.name}...")
    ds = netCDF4.Dataset(str(NC_PATH), "r")

    # 找变量名
    var_name = None
    for v in ds.variables:
        if v not in ("lat", "lon", "time", "latitude", "longitude"):
            var_name = v
            break
    print(f"[cmfd] 变量: {var_name}")

    lon_arr = np.asarray(ds.variables["lon"][:])  # 700
    lat_arr = np.asarray(ds.variables["lat"][:])  # 400
    n_total = ds.dimensions["time"].size  # 888

    # 计算时间索引 (V0106从1979-01起算)
    months = []
    indices = []
    for i in range(n_total):
        y = 1979 + i // 12
        m = (i % 12) + 1
        if START_YEAR <= y <= END_YEAR:
            months.append(f"{y}-{m:02d}")
            indices.append(i)
    print(f"[cmfd] 时间范围: {months[0]} ~ {months[-1]} ({len(months)} 个月)")

    # 预计算每县的格点掩膜
    region_masks = {}
    for r in regions:
        if r.get("bbox"):
            b = r["bbox"]
            # 边界框内的格点
            mask = (lon_arr >= b["min_lon"]) & (lon_arr <= b["max_lon"]) & \
                   (lat_arr >= b["min_lat"]) & (lat_arr <= b["max_lat"])
            # 转为二维索引
            lon_idx = np.where((lon_arr >= b["min_lon"]) & (lon_arr <= b["max_lon"]))[0]
            lat_idx = np.where((lat_arr >= b["min_lat"]) & (lat_arr <= b["max_lat"]))[0]
            n_cells = len(lon_idx) * len(lat_idx)
            region_masks[r["region_id"]] = (lon_idx, lat_idx, n_cells)
            print(f"  {r['region_id']}: {n_cells} 格点 (lon:{len(lon_idx)} x lat:{len(lat_idx)})")
        else:
            # 回退到单点
            li = int(np.argmin(np.abs(lat_arr - r["latitude"])))
            lj = int(np.argmin(np.abs(lon_arr - r["longitude"])))
            region_masks[r["region_id"]] = (np.array([lj]), np.array([li]), 1)
            print(f"  {r['region_id']}: 1 格点 (回退到单点)")

    # 逐月提取
    print(f"\n[cmfd] 提取 {len(regions)} 县 × {len(months)} 月 = {len(regions) * len(months)} 行...")
    sys.stdout.flush()

    rows = []
    for i, idx in enumerate(indices):
        try:
            data_2d = ds.variables[var_name][idx]  # (lat, lon)
        except Exception:
            print(f"  [warn] 月份 {months[i]} 读取失败, 跳过")
            continue

        for r in regions:
            lon_idx, lat_idx, n_cells = region_masks[r["region_id"]]
            # 提取边界框内的格点
            sub = data_2d[np.ix_(lat_idx, lon_idx)]
            # 求均值 (忽略 NaN)
            valid = sub[~np.isnan(sub)]
            temp_val = float(np.mean(valid)) if len(valid) > 0 else None

            if temp_val is not None:
                # CMFD 温度单位是 0.1°C, 需要转换
                if abs(temp_val) > 100:
                    temp_val = temp_val / 10.0

                rows.append({
                    "region_id": r["region_id"],
                    "station": f"CMFD_regional_{r['region_id']}",
                    "observed_at": f"{months[i]}-01 00:00",
                    "temperature_c": round(temp_val, 1),
                    "precipitation_mm_24h": "",  # CMFD prec 文件不在
                    "wind_speed_mps": "",         # CMFD wind 文件不在
                    "snow_depth_cm": 0,
                    "cold_wave_risk": "高" if temp_val < -10 else "中" if temp_val < 0 else "低",
                    "snowstorm_risk": "低",
                    "drought_risk": "中",
                    "data_source": "tpdc",
                    "source_id": "cmfd-regional",
                    "dataset_name": "CMFD_V0106_regional",
                    "is_sample": False,
                    "imported_at": datetime.now().isoformat() + "+00:00",
                    "n_grid_cells": n_cells,
                })

        if (i + 1) % 12 == 0:
            print(f"  进度: {i+1}/{len(indices)} 月 ({months[i]})")
            sys.stdout.flush()

    ds.close()

    # 写 CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    print(f"\n[cmfd] CSV 已保存: {OUT_CSV} ({len(rows)} 行)")

    # 写 JSON (逐日格式, 每月一条, 供 early_warning.py 用)
    climate = {}
    for row in rows:
        rid = row["region_id"]
        if rid not in climate:
            climate[rid] = []
        climate[rid].append({
            "date": row["observed_at"][:10],  # YYYY-MM-01
            "temp_mean": row["temperature_c"],
            "precip_mm": 0.0,  # CMFD prec 不在, 填 0
        })

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(climate, f, ensure_ascii=False, indent=2)
    print(f"[cmfd] JSON 已保存: {OUT_JSON} ({len(climate)} 县)")

    return len(rows)


def compare_old_vs_new(regions: list[dict]):
    """对比旧数据(单点)和新数据(区域均值)的温度差异。"""
    import json as json_mod

    old_json = BACKEND / "data_store" / "climate_era5.json"
    new_json = OUT_JSON

    if not old_json.exists() or not new_json.exists():
        return

    with open(old_json, encoding="utf-8") as f:
        old = json_mod.load(f)
    with open(new_json, encoding="utf-8") as f:
        new = json_mod.load(f)

    print("\n=== 新旧数据对比 (温度均值) ===")
    print(f"{'region_id':<25} {'旧(单点)':>10} {'新(区域)':>10} {'差异':>10} {'格点数':>8}")
    print("-" * 70)

    for r in regions:
        rid = r["region_id"]
        old_vals = [v["temp_mean"] for v in old.get(rid, []) if v.get("temp_mean") is not None]
        new_vals = [v["temp_mean"] for v in new.get(rid, []) if v.get("temp_mean") is not None]
        if old_vals and new_vals:
            old_mean = sum(old_vals) / len(old_vals)
            new_mean = sum(new_vals) / len(new_vals)
            diff = new_mean - old_mean
            n_cells = r.get("bbox", {}).get("n_vertices", 1) if r.get("bbox") else 1
            print(f"{rid:<25} {old_mean:>10.1f} {new_mean:>10.1f} {diff:>+10.1f} {n_cells:>8}")


if __name__ == "__main__":
    print("=" * 60)
    print("CMFD 气象数据区域提取 (边界框多格点均值)")
    print(f"年份: {START_YEAR}-{END_YEAR}")
    print("=" * 60)

    regions = load_region_meta()
    print(f"区域: {len(regions)} 个县\n")

    n = extract_cmfd_regional(regions)
    if n > 0:
        compare_old_vs_new(regions)

    print(f"\n完成: {n} 行数据")
