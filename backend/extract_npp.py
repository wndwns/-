"""
从 MOD17A3HGF NetCDF 提取 25 个高原牧区县的 NPP 数据
================================================================
坐标转换：WGS84 经纬度 → MODIS 正弦投影
每个县取 3×3 像素窗口均值，避免单像素噪声
输出：data_store/npp_by_region.json
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
import xarray as xr

# ── 配置 ──
ROOT = Path(__file__).resolve().parent
NC_PATH = Path("C:/Users/WH/Desktop/MOD17A3HGF.061_500m_aid0001.nc")
CSV_PATH = ROOT.parent / "public_data" / "region_list.csv"
OUT_PATH = ROOT / "data_store" / "npp_by_region.json"

# MODIS 正弦投影参数
R = 6371007.181          # 球体半径 (m)
PIXEL_SIZE = 463.31271652  # 实际像素大小 (m)
WINDOW = 30              # 30×30 窗口 (约 15km×15km)，避免单点异常


def lonlat_to_sinusoidal(lon: float, lat: float) -> tuple[float, float]:
    """WGS84 经纬度 → MODIS 正弦投影 (x, y)，单位米。"""
    lon_rad = math.radians(lon)
    lat_rad = math.radians(lat)
    x = R * lon_rad * math.cos(lat_rad)
    y = R * lat_rad
    return x, y


def extract_npp_for_county(
    ds: xr.Dataset,
    lon: float,
    lat: float,
    region_id: str,
) -> dict | None:
    """提取一个县 2001-2025 年的 NPP 时间序列。"""
    x_m, y_m = lonlat_to_sinusoidal(lon, lat)

    x_coords = ds["xdim"].values
    y_coords = ds["ydim"].values

    # 找最近像素
    ix = np.argmin(np.abs(x_coords - x_m))
    iy = np.argmin(np.abs(y_coords - y_m))

    # 窗口范围
    half = WINDOW // 2
    x_start = max(0, ix - half)
    x_end = min(len(x_coords) - 1, ix + half) + 1  # +1 for slice exclusive
    y_start = max(0, iy - half)
    y_end = min(len(y_coords) - 1, iy + half) + 1

    actual_window = (x_end - x_start, y_end - y_start)

    # 提取时间序列 —— 每个时间步取窗口内有效像素均值
    npp_full = ds["Npp_500m"].values  # (time, ydim, xdim)
    times = [str(t) for t in ds["time"].values]

    annual: dict[str, float] = {}
    for t_idx, t_label in enumerate(times):
        year = t_label[:4]
        window_data = npp_full[t_idx, y_start:y_end, x_start:x_end]
        # 过滤填充值：32767 = 无效, 32766 = 水体, 32765 = 荒漠等
        valid = window_data[(window_data >= 0) & (window_data < 32700)]
        if len(valid) == 0:
            continue
        annual[year] = round(float(np.mean(valid)), 4)

    if not annual:
        # 尝试扩大搜索窗口
        big_half = 50
        bx_start = max(0, ix - big_half)
        bx_end = min(len(x_coords) - 1, ix + big_half) + 1
        by_start = max(0, iy - big_half)
        by_end = min(len(y_coords) - 1, iy + big_half) + 1
        big_window = npp_full[0, by_start:by_end, bx_start:bx_end]
        valid = big_window[(big_window >= 0) & (big_window < 32700)]
        if len(valid) == 0:
            return None
        # 扩大窗口找到了，重新提取
        for t_idx, t_label in enumerate(times):
            year = t_label[:4]
            window_data = npp_full[t_idx, by_start:by_end, bx_start:bx_end]
            valid = window_data[(window_data >= 0) & (window_data < 32700)]
            if len(valid) == 0:
                continue
            annual[year] = round(float(np.mean(valid)), 4)
        actual_window = (bx_end - bx_start, by_end - by_start)

    if not annual:
        return None

    values = list(annual.values())
    return {
        "region_id": region_id,
        "longitude": lon,
        "latitude": lat,
        "pixel_ix": int(ix),
        "pixel_iy": int(iy),
        "window_size": [int(actual_window[0]), int(actual_window[1])],
        "years": sorted(annual.keys()),
        "npp_annual": annual,
        "npp_mean": round(float(np.mean(values)), 4),
        "npp_min": round(float(np.min(values)), 4),
        "npp_max": round(float(np.max(values)), 4),
        "npp_std": round(float(np.std(values)), 4),
        "npp_2024": annual.get("2024"),
        "unit": "kg_C/m²/yr",
    }


def main():
    print("Opening NetCDF...")
    ds = xr.open_dataset(NC_PATH)

    print("Reading region list...")
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        counties = list(csv.DictReader(f))

    results = []
    for row in counties:
        rid = row["region_id"]
        lon = float(row["longitude"])
        lat = float(row["latitude"])
        print(f"  Extracting {rid} ({row['region_name']}) @ lon={lon}, lat={lat}...")
        entry = extract_npp_for_county(ds, lon, lat, rid)
        if entry:
            results.append(entry)
            print(f"    NPP mean: {entry['npp_mean']} kgC/m²/yr, 2024: {entry['npp_2024']}")
        else:
            print(f"    WARNING: No valid pixels found for {rid}")

    ds.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(results)} counties to {OUT_PATH}")
    print("Done!")


if __name__ == "__main__":
    main()