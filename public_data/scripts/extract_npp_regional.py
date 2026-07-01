"""
NPP 区域提取脚本 (改进版)
================================================================
改进: 从"县中心 30×30 像素窗口(~15km)"改为"县域边界框内所有像素均值"。

NPP NetCDF: C:/Users/WH/Desktop/MOD17A3HGF.061_500m_aid0001.nc
  - MODIS 正弦投影坐标 (xdim/ydim, 单位: 米)
  - 变量 Npp, 单位: kgC/m²/year (需 ×0.0001 转换)
  - 时间: 2001-2024 (年度)

用法:
    python public_data/scripts/extract_npp_regional.py

输出:
    - backend/data_store/npp_by_region_regional.json
    - public_data/processed/npp_regional_comparison.csv (新旧对比)
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT.parent / "backend"

NC_PATH = Path("C:/Users/WH/Desktop/MOD17A3HGF.061_500m_aid0001.nc")
BOUNDS_PATH = ROOT / "region_bounds.json"
REGION_LIST = ROOT / "region_list.csv"

OUT_JSON = BACKEND / "data_store" / "npp_by_region_regional.json"
OUT_CSV = ROOT / "processed" / "npp_regional_comparison.csv"

# MODIS 正弦投影参数
R = 6371007.181          # 球体半径 (m)
PIXEL_SIZE = 463.31271652  # 像素大小 (m)


def lonlat_to_sinusoidal(lon: float, lat: float) -> tuple[float, float]:
    """WGS84 经纬度 → MODIS 正弦投影 (x, y)，单位米。"""
    lon_rad = math.radians(lon)
    lat_rad = math.radians(lat)
    x = R * lon_rad * math.cos(lat_rad)
    y = R * lat_rad
    return x, y


def load_regions():
    """读取 region_list.csv + region_bounds.json。"""
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
        r["bbox"] = bounds.get(r["region_id"])
    return regions


def extract_npp_regional(regions: list[dict]) -> dict:
    """用县域边界框提取 NPP 区域均值。"""
    if not NC_PATH.exists():
        print(f"[error] NPP NetCDF 不存在: {NC_PATH}")
        return {}

    print(f"[npp] 打开 {NC_PATH.name}...")
    ds = xr.open_dataset(str(NC_PATH))

    # 查看数据结构
    print(f"[npp] 维度: {dict(ds.dims)}")
    print(f"[npp] 变量: {list(ds.data_vars)}")
    print(f"[npp] 坐标: {list(ds.coords)}")

    # 获取坐标轴
    x_coords = ds["xdim"].values  # 米
    y_coords = ds["ydim"].values  # 米
    print(f"[npp] x: [{x_coords.min():.0f}, {x_coords.max():.0f}] ({len(x_coords)} pts)")
    print(f"[npp] y: [{y_coords.min():.0f}, {y_coords.max():.0f}] ({len(y_coords)} pts)")

    # 找 NPP 变量
    npp_var = None
    for v in ds.data_vars:
        if "npp" in v.lower() or "Npp" in v:
            npp_var = v
            break
    if not npp_var:
        npp_var = list(ds.data_vars)[0]
    print(f"[npp] 变量: {npp_var}")

    # 获取时间维度
    npp_data = ds[npp_var]
    print(f"[npp] shape: {npp_data.shape}")

    # 判断时间维度
    if len(npp_data.dims) == 3:
        # (time, y, x) 或 (y, x, time)
        time_dim = npp_data.dims[0] if "time" in str(npp_data.dims[0]) else npp_data.dims[-1]
        n_years = npp_data.sizes[time_dim]
        print(f"[npp] 时间维度: {time_dim}, {n_years} 年")

        # 年份标签 (MOD17A3HGF 从 2001 开始)
        start_year = 2001
        years = list(range(start_year, start_year + n_years))
    else:
        print(f"[npp] 无时间维度, 单年数据")
        years = [2024]
        npp_data = npp_data.expand_dims({"time": [0]})

    # 预计算每县的像素范围 (正弦投影)
    # 检查坐标排序方向
    x_ascending = x_coords[0] < x_coords[-1]
    y_ascending = y_coords[0] < y_coords[-1]
    print(f"[npp] x {'升序' if x_ascending else '降序'}, y {'升序' if y_ascending else '降序'}")

    region_windows = {}
    for r in regions:
        if not r.get("bbox"):
            # 回退到 30×30 窗口
            x_m, y_m = lonlat_to_sinusoidal(r["longitude"], r["latitude"])
            xi = int(np.argmin(np.abs(x_coords - x_m)))
            yi = int(np.argmin(np.abs(y_coords - y_m)))
            half = 15  # 30×30 窗口
            region_windows[r["region_id"]] = (max(0, xi-half), xi+half+1, max(0, yi-half), yi+half+1, 30*30)
            print(f"  {r['region_id']}: 30×30 窗口 (回退)")
            continue

        b = r["bbox"]
        # 边界框四角转正弦投影
        x_min, y_min = lonlat_to_sinusoidal(b["min_lon"], b["min_lat"])
        x_max, y_max = lonlat_to_sinusoidal(b["max_lon"], b["max_lat"])

        # 用 np.where 找像素范围 (不依赖排序方向)
        x_lo, x_hi = min(x_min, x_max), max(x_min, x_max)
        y_lo, y_hi = min(y_min, y_max), max(y_min, y_max)

        x_mask = (x_coords >= x_lo) & (x_coords <= x_hi)
        y_mask = (y_coords >= y_lo) & (y_coords <= y_hi)
        xi_indices = np.where(x_mask)[0]
        yi_indices = np.where(y_mask)[0]

        if len(xi_indices) == 0 or len(yi_indices) == 0:
            # 回退到 30×30 窗口
            x_m, y_m = lonlat_to_sinusoidal(r["longitude"], r["latitude"])
            xi = int(np.argmin(np.abs(x_coords - x_m)))
            yi = int(np.argmin(np.abs(y_coords - y_m)))
            half = 15
            region_windows[r["region_id"]] = (max(0, xi-half), xi+half+1, max(0, yi-half), yi+half+1, 30*30)
            print(f"  {r['region_id']}: 30×30 窗口 (边界框无像素, 回退)")
            continue

        xi_start, xi_end = int(xi_indices[0]), int(xi_indices[-1]) + 1
        yi_start, yi_end = int(yi_indices[0]), int(yi_indices[-1]) + 1

        n_pixels = (xi_end - xi_start) * (yi_end - yi_start)
        region_windows[r["region_id"]] = (xi_start, xi_end, yi_start, yi_end, n_pixels)

        # 估算覆盖面积
        area_km2 = n_pixels * (PIXEL_SIZE / 1000) ** 2
        print(f"  {r['region_id']}: {n_pixels} 像素 (~{area_km2:.0f} km²)")

    # 逐年提取
    print(f"\n[npp] 提取 {len(regions)} 县 × {len(years)} 年...")
    sys.stdout.flush()

    result = {}
    for r in regions:
        rid = r["region_id"]
        result[rid] = {
            "region_id": rid,
            "region_name": r["region_name"],
            "longitude": r["longitude"],
            "latitude": r["latitude"],
            "altitude": r["altitude"],
            "pasture_type": r["pasture_type"],
            "extraction_method": "bbox_regional",
            "n_pixels": region_windows[rid][4],
            "npp_annual": {},  # 与后端兼容的字段名
            "unit": "kg_C/m²/yr",
        }

    for yr_idx, year in enumerate(years):
        if year > 2025:
            break
        try:
            if len(npp_data.dims) == 3:
                # 提取这一年的数据
                if time_dim == npp_data.dims[0]:
                    year_data = npp_data.isel({time_dim: yr_idx}).values
                else:
                    year_data = npp_data.isel({time_dim: yr_idx}).values
            else:
                year_data = npp_data.values
        except Exception as e:
            print(f"  [warn] {year} 读取失败: {e}")
            continue

        for r in regions:
            rid = r["region_id"]
            xi_start, xi_end, yi_start, yi_end, _ = region_windows[rid]

            # 提取窗口
            if len(year_data.shape) == 2:
                sub = year_data[yi_start:yi_end, xi_start:xi_end]
            elif len(year_data.shape) == 3:
                sub = year_data[:, yi_start:yi_end, xi_start:xi_end]
            else:
                continue

            # 求均值 (忽略 NaN 和 0)
            valid = sub[np.isfinite(sub) & (sub != 0)]
            if len(valid) > 0:
                npp_val = float(np.mean(valid))
                # MOD17A3HGF scale factor: ×0.0001 → kgC/m²/year
                if abs(npp_val) > 10:
                    npp_val = npp_val * 0.0001
                result[rid]["npp_annual"][str(year)] = round(npp_val, 4)
            else:
                result[rid]["npp_annual"][str(year)] = None

        if (yr_idx + 1) % 5 == 0:
            print(f"  进度: {yr_idx+1}/{len(years)} 年 ({year})")
            sys.stdout.flush()

    ds.close()

    # 添加统计字段 (与旧格式兼容)
    for rid, item in result.items():
        vals = [v for v in item["npp_annual"].values() if v is not None]
        if vals:
            item["npp_mean"] = round(sum(vals) / len(vals), 4)
            item["npp_min"] = round(min(vals), 4)
            item["npp_max"] = round(max(vals), 4)
            item["npp_std"] = round(float(np.std(vals)), 4)
            item["npp_2024"] = item["npp_annual"].get("2024")
        else:
            item["npp_mean"] = 0
            item["npp_min"] = 0
            item["npp_max"] = 0
            item["npp_std"] = 0
            item["npp_2024"] = None

    return result


def compare_old_vs_new(new_data: dict):
    """对比旧数据(30×30窗口)和新数据(区域均值)的 NPP 差异。"""
    old_json = BACKEND / "data_store" / "npp_by_region.json"
    if not old_json.exists():
        print("[warn] 旧 NPP 数据不存在, 跳过对比")
        return

    with open(old_json, encoding="utf-8") as f:
        old = json.load(f)

    # 转为 dict
    old_dict = {}
    if isinstance(old, list):
        for item in old:
            old_dict[item["region_id"]] = item
    else:
        old_dict = old

    print("\n=== NPP 新旧对比 (2020-2024 均值) ===")
    print(f"{'region_id':<25} {'旧(30×30)':>12} {'新(区域)':>12} {'差异':>10} {'变化%':>8} {'像素数':>10}")
    print("-" * 80)

    rows = []
    for rid, new_item in new_data.items():
        old_item = old_dict.get(rid, {})
        old_npp = old_item.get("npp_annual", {})
        new_npp = new_item.get("npp_annual", {})

        # 对比 2020-2024
        old_vals = [v for y, v in old_npp.items() if 2020 <= int(y) <= 2024 and v is not None]
        new_vals = [v for y, v in new_npp.items() if 2020 <= int(y) <= 2024 and v is not None]

        if old_vals and new_vals:
            old_mean = sum(old_vals) / len(old_vals)
            new_mean = sum(new_vals) / len(new_vals)
            diff = new_mean - old_mean
            pct = (diff / old_mean * 100) if old_mean != 0 else 0
            n_px = new_item.get("n_pixels", 0)
            print(f"{rid:<25} {old_mean:>12.4f} {new_mean:>12.4f} {diff:>+10.4f} {pct:>+7.1f}% {n_px:>10}")
            rows.append({
                "region_id": rid,
                "old_npp_mean": round(old_mean, 4),
                "new_npp_mean": round(new_mean, 4),
                "diff": round(diff, 4),
                "diff_pct": round(pct, 1),
                "old_pixels": 900,  # 30×30
                "new_pixels": n_px,
            })

    # 写对比 CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    print(f"\n对比 CSV: {OUT_CSV}")


if __name__ == "__main__":
    print("=" * 60)
    print("NPP 区域提取 (边界框所有像素均值)")
    print("=" * 60)

    regions = load_regions()
    print(f"区域: {len(regions)} 个县\n")

    result = extract_npp_regional(regions)
    if result:
        # 保存 JSON
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        # 转为 list 格式 (与 npp_by_region.json 兼容)
        result_list = list(result.values())
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(result_list, f, ensure_ascii=False, indent=2)
        print(f"\nNPP JSON 已保存: {OUT_JSON} ({len(result_list)} 县)")

        # 对比
        compare_old_vs_new(result)

    print("\n完成")
