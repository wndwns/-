"""
ingest_public_data.py —— 处理公开数据文件，转换为系统 CSV。

=== CMFD 2.0 月尺度 NetCDF ===

用法:
    python public_data/scripts/ingest_public_data.py --source tpdc --dataset cmfd \
        --temp C:/temp/cmfd/temp_CMFD_V0200_B-01_01mo_010deg_195101-202412.nc \
        --prec C:/temp/cmfd/prec_CMFD_V0200_B-01_01mo_010deg_195101-202412.nc \
        --wind C:/temp/cmfd/wind_CMFD_V0200_B-01_01mo_010deg_195101-202412.nc \
        --start-year 2024 --end-year 2024 \
        --output public_data/processed/weather_data_cmfd_2024.csv

注意: NetCDF 路径不要含中文（netCDF4 C 库不支持）。
依赖: pip install netCDF4 numpy
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_region_meta(path: str) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        print(f"[error] 区域列表文件不存在: {p}")
        sys.exit(1)
    rows = []
    with open(p, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({
                "region_id": r.get("region_id", "").strip(),
                "region_name": r.get("region_name", "").strip(),
                "province": r.get("province", "").strip(),
                "city": r.get("city", "").strip(),
                "county": r.get("county", "").strip(),
                "longitude": float(r.get("longitude", 0)),
                "latitude": float(r.get("latitude", 0)),
                "altitude": float(r.get("altitude", 0)) if r.get("altitude") else 0.0,
                "pasture_type": r.get("pasture_type", "").strip(),
            })
    return rows


def _days_in_month(y: int, m: int) -> int:
    if m == 2:
        return 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28
    return 31 if m in (1, 3, 5, 7, 8, 10, 12) else 30


# ============================================================================
# CMFD NetCDF 处理
# ============================================================================

def _load_cmfd_to_memory(nc_path: str, start_year: int, end_year: int) -> tuple[Any, Any, Any, list[str], int]:
    """用 netCDF4 直接加载 CMFD 文件指定年份切片到内存。

    CMFD 2.0: 888 个月 (1951-01 ~ 2024-12), 网格 400×700 (0.1°)

    Returns:
        (data_3d, lon_1d, lat_1d, month_labels, n_months)
    """
    import netCDF4
    import numpy as np

    ds = netCDF4.Dataset(nc_path, "r")
    fname = Path(nc_path).name

    # 找变量名 (排除坐标)
    var_name = None
    for v in ds.variables:
        if v not in ("lat", "lon", "time", "latitude", "longitude"):
            var_name = v
            break

    # 坐标
    lon_arr = np.asarray(ds.variables["lon"][:])
    lat_arr = np.asarray(ds.variables["lat"][:])
    n_total = ds.dimensions["time"].size  # 888

    # 时间轴: CMFD 从 1951-01 开始，每月一步
    # 时间变量可能损坏，直接用索引计算月份
    months = []
    indices = []
    for i in range(n_total):
        y = 1951 + i // 12
        m = (i % 12) + 1
        if start_year <= y <= end_year:
            months.append(f"{y}-{m:02d}")
            indices.append(i)

    # 逐时间步加载（CMFD 文件可能部分损坏，需要逐步容错）
    print(f"[cmfd]   加载 {fname}: {len(indices)}/{n_total} 个月 (逐步, 索引 {indices[0]}..{indices[-1]})...")
    first_slice = ds.variables[var_name][indices[0]]  # 获取空间shape
    sp_shape = first_slice.shape
    data = np.zeros((len(indices),) + sp_shape, dtype=np.float32)
    ok_count = 0
    for i, idx in enumerate(indices):
        try:
            data[i] = ds.variables[var_name][idx]
            ok_count += 1
        except Exception:
            data[i] = np.nan
    if ok_count < len(indices):
        print(f"[cmfd]   [warn] {len(indices) - ok_count}/{len(indices)} 个月读取失败, 填充 NaN")

    ds.close()
    print(f"[cmfd]   shape={data.shape}, ~{data.nbytes/1e6:.0f}MB")
    return data, lon_arr, lat_arr, months, len(indices)


def process_cmfd_netcdf(
    region_list_path: str,
    temp_path: str | None, prec_path: str | None, wind_path: str | None,
    start_year: int, end_year: int,
    output_path: str, report_path: str,
) -> int:
    import numpy as np

    print("=" * 60)
    print("[cmfd] CMFD 2.0 NetCDF 处理")
    print(f"[cmfd] 年份: {start_year}-{end_year}")
    print("=" * 60)

    regions = load_region_meta(region_list_path)
    print(f"[cmfd] 区域: {len(regions)} 个县")

    # ---- 加载所有变量到内存 ----
    mem: dict[str, np.ndarray] = {}
    all_months: list[str] = []
    grid_lon: np.ndarray | None = None
    grid_lat: np.ndarray | None = None
    missing: list[str] = []

    for tag, fpath in [("temp", temp_path), ("prec", prec_path), ("wind", wind_path)]:
        if fpath is None:
            missing.append(tag)
            continue
        p = Path(fpath)
        if not p.exists():
            print(f"[warn] 文件不存在: {fpath}")
            missing.append(tag)
            continue

        data, lon_a, lat_a, months, n = _load_cmfd_to_memory(str(p), start_year, end_year)
        mem[tag] = data
        if not all_months:
            all_months = months
        if grid_lon is None:
            grid_lon = lon_a
            grid_lat = lat_a

    if not mem:
        print("[error] 无可用数据")
        return 0

    # ---- 预计算格点索引 ----
    indices = []
    for r in regions:
        li = int(np.argmin(np.abs(grid_lat - r["latitude"])))
        lj = int(np.argmin(np.abs(grid_lon - r["longitude"])))
        indices.append((li, lj))
    print(f"[cmfd] 格点索引: {len(indices)} 个区域已就绪")

    # ---- 批量提取 ----
    n_months = len(all_months)
    total = len(regions) * n_months
    print(f"[cmfd] 提取: {len(regions)}县 × {n_months}月 = {total} 行")
    sys.stdout.flush()

    OUT_COLS = [
        "region_id", "station", "observed_at", "temperature_c",
        "precipitation_mm_24h", "wind_speed_mps", "snow_depth_cm",
        "cold_wave_risk", "snowstorm_risk", "drought_risk",
        "data_source", "source_id", "dataset_name", "is_sample",
    ]
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLS, extrasaction="ignore")
        w.writeheader()

        for mi, month_str in enumerate(all_months):
            if mi % 6 == 0:
                print(f"[cmfd]   {mi+1}/{n_months} {month_str}")
                sys.stdout.flush()

            y, m = map(int, month_str.split("-"))
            _ = _days_in_month(y, m)  # kept for potential future use

            for ri, region in enumerate(regions):
                rid = region["region_id"]
                li, lj = indices[ri]

                tv = float(mem["temp"][mi, li, lj]) if "temp" in mem else None
                pv = float(mem["prec"][mi, li, lj]) if "prec" in mem else None
                wv = float(mem["wind"][mi, li, lj]) if "wind" in mem else None

                tc = round(tv - 273.15, 1) if tv is not None and not math.isnan(tv) else None
                pd = round(pv * 3600 * 24, 2) if pv is not None and not math.isnan(pv) else None  # CMFD prec: stored as mm/s → mm/day
                ws = round(wv, 1) if wv is not None and not math.isnan(wv) else None

                cold = "高" if (tc is not None and tc < -10) else ("中" if (tc is not None and tc < 0) else "低")

                w.writerow({
                    "region_id": rid, "station": f"CMFD_{rid}",
                    "observed_at": f"{month_str}-01 00:00",
                    "temperature_c": tc if tc is not None else "",
                    "precipitation_mm_24h": pd if pd is not None else "",
                    "wind_speed_mps": ws if ws is not None else "",
                    "snow_depth_cm": 0,
                    "cold_wave_risk": cold, "snowstorm_risk": "低", "drought_risk": "中",
                    "data_source": "tpdc", "source_id": "cmfd-v2",
                    "dataset_name": "CMFD_V0200", "is_sample": "false",
                })
                count += 1

    print(f"[cmfd] 输出: {count} 行 → {out_path}")

    # 警告
    warnings = [
        "snow_depth_cm=0: CMFD 不含雪深数据",
        "cold_wave_risk 由月均温度阈值自动判定",
        "drought_risk 默认='中'",
    ]
    if missing:
        warnings.append(f"缺少变量: {missing}")
    for w in warnings:
        print(f"[cmfd] [warn] {w}")

    # 报告
    rpt = {
        "source": "tpdc", "source_id": "cmfd-v2", "dataset_name": "CMFD_V0200",
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "input_files": {"temp": temp_path, "prec": prec_path, "wind": wind_path},
        "year_range": f"{start_year}-{end_year}",
        "county_count": len(regions), "month_count": n_months, "total_rows": count,
        "variables_loaded": list(mem.keys()), "variables_missing": missing,
        "warnings": warnings, "output_file": str(out_path),
        "next_step": "打开 http://127.0.0.1:8000/admin 上传此 CSV 到 weather_data 表",
    }
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(rpt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[cmfd] 报告: {report_path}")
    return count


# ============================================================================
# 遥感数据处理 (NDVI / Snow / FVC)
# ============================================================================

def process_ndvi_csv(input_path: str, region_list_path: str,
                     start_year: int, end_year: int,
                     source_id: str = "modis-ndvi-mod13q1",
                     mark_real: bool = False) -> tuple[list[dict], list[str]]:
    """处理 NDVI CSV 文件（来自 GEE 导出或 TPDC 下载）。

    支持列名：region_id, date/scene_date, ndvi/NDVI
    也支持经纬度模式：longitude, latitude, date, ndvi（自动匹配最近区域）

    自动按 region_id + month 聚合，计算 ndvi_change（同比）。
    """
    import numpy as np
    from collections import defaultdict

    regions = load_region_meta(region_list_path)
    region_ids = {r["region_id"] for r in regions}
    id_to_coords = {r["region_id"]: (r["longitude"], r["latitude"]) for r in regions}
    # 用于经纬度匹配
    coords_list = [(r["longitude"], r["latitude"]) for r in regions]
    id_list = [r["region_id"] for r in regions]

    path = Path(input_path)
    if not path.exists():
        print(f"[ndvi] 文件不存在: {input_path}")
        return [], ["文件不存在"]

    with open(path, "r", encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))

    warnings: list[str] = []
    print(f"[ndvi] 读取 {len(raw)} 行, 列: {list(raw[0].keys()) if raw else '?'}")

    # 识别列名
    has_region = any(c in raw[0] for c in ("region_id", "region_name")) if raw else False
    has_coords = all(c in raw[0] for c in ("longitude", "latitude")) if raw else False

    # 按月聚合: (region_id, YYYY-MM) → [ndvi_values]
    monthly: dict[tuple[str, str], list[float]] = defaultdict(list)

    for r in raw:
        rid = ""
        if has_region:
            rid = r.get("region_id", r.get("region_name", "")).strip()
        elif has_coords:
            try:
                lon = float(r.get("longitude", 0))
                lat = float(r.get("latitude", 0))
                dists = [(abs(lon - cl[0]) + abs(lat - cl[1]), i)
                         for i, cl in enumerate(coords_list)]
                _, nearest = min(dists)
                rid = id_list[nearest]
            except (ValueError, TypeError):
                continue
        else:
            warnings.append("CSV 缺少 region_id 或 longitude/latitude 列，无法定位区域")
            continue

        if rid not in region_ids:
            continue

        # 日期
        date_str = r.get("date", r.get("scene_date", "")).strip()
        if len(date_str) >= 7:
            month = date_str[:7]  # YYYY-MM
        elif len(date_str) >= 4:
            month = date_str[:4] + "-01"  # 只有年份
        else:
            continue

        # NDVI 值
        ndvi_str = r.get("ndvi", r.get("NDVI", "")).strip()
        if not ndvi_str:
            continue
        try:
            ndvi_val = float(ndvi_str)
            if 0 <= ndvi_val <= 1:
                ndvi_val = ndvi_val  # NDVI 0-1
            elif 1 < ndvi_val <= 10000:
                ndvi_val = ndvi_val / 10000.0  # MODIS scaled NDVI
            monthly[(rid, month)].append(ndvi_val)
        except (ValueError, TypeError):
            continue

    if not monthly:
        warnings.append("未能解析任何有效的 NDVI 行")
        return [], warnings

    # 按月聚合（均值）
    agg: dict[tuple[str, str], float] = {}
    for (rid, month), vals in monthly.items():
        agg[(rid, month)] = float(np.mean(vals))

    # 计算 ndvi_change（与去年同月比较）
    rows: list[dict] = []
    missing_change = 0
    for (rid, month), ndvi in sorted(agg.items()):
        y = int(month[:4])
        prev_month = f"{y-1}-{month[5:]}"
        prev_ndvi = agg.get((rid, prev_month))
        if prev_ndvi is not None and prev_ndvi > 0:
            ndvi_change = round((ndvi - prev_ndvi) / prev_ndvi * 100, 1)
            change_str = f"{ndvi_change:+.1f}%"
        else:
            change_str = "0%"
            missing_change += 1

        rows.append({
            "region_id": rid,
            "scene_date": f"{month}-15",
            "ndvi": round(ndvi, 4),
            "ndvi_change": change_str,
        })

    if missing_change > 0:
        warnings.append(f"{missing_change}/{len(rows)} 行无上年同期数据, ndvi_change 设为 0%")

    print(f"[ndvi] 聚合: {len(rows)} 行 ({len(agg)} 个 region-month)")
    return rows, warnings


def process_snow_csv(input_path: str, region_list_path: str,
                     start_year: int, end_year: int) -> tuple[list[dict], list[str]]:
    """处理积雪覆盖 CSV → 提取 25 县月度 snow_cover 百分比。

    预期列: region_id, date, snow_cover
    """
    from collections import defaultdict
    import numpy as np

    regions = load_region_meta(region_list_path)
    region_ids = {r["region_id"] for r in regions}
    path = Path(input_path)
    if not path.exists():
        return [], ["积雪文件不存在"]

    with open(path, "r", encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))

    warnings: list[str] = []
    monthly: dict[tuple[str, str], list[float]] = defaultdict(list)

    for r in raw:
        rid = r.get("region_id", "").strip()
        if rid not in region_ids:
            continue
        date_str = r.get("date", r.get("scene_date", "")).strip()
        if len(date_str) >= 7:
            month = date_str[:7]
        else:
            continue
        try:
            sc = float(r.get("snow_cover", r.get("snow", 0)))
            monthly[(rid, month)].append(sc)
        except (ValueError, TypeError):
            continue

    rows = []
    for (rid, month), vals in monthly.items():
        rows.append({
            "region_id": rid,
            "scene_date": f"{month}-15",
            "snow_cover": f"{np.mean(vals):.1f}%",
        })
    print(f"[snow] 聚合: {len(rows)} 行")
    return rows, warnings


def process_fvc_csv(input_path: str, region_list_path: str,
                    start_year: int, end_year: int) -> tuple[list[dict], list[str]]:
    """处理植被覆盖度 CSV → 提取 25 县月度 FVC 百分比。

    预期列: region_id, date, fvc / vegetation_cover
    """
    from collections import defaultdict
    import numpy as np

    regions = load_region_meta(region_list_path)
    region_ids = {r["region_id"] for r in regions}
    path = Path(input_path)
    if not path.exists():
        return [], ["FVC 文件不存在"]

    with open(path, "r", encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))

    warnings: list[str] = []
    monthly: dict[tuple[str, str], list[float]] = defaultdict(list)

    for r in raw:
        rid = r.get("region_id", "").strip()
        if rid not in region_ids:
            continue
        date_str = r.get("date", r.get("scene_date", "")).strip()
        if len(date_str) >= 7:
            month = date_str[:7]
        else:
            continue
        try:
            fvc = float(r.get("fvc", r.get("vegetation_cover", r.get("FVC", 0))))
            monthly[(rid, month)].append(fvc)
        except (ValueError, TypeError):
            continue

    rows = []
    for (rid, month), vals in monthly.items():
        rows.append({
            "region_id": rid,
            "scene_date": f"{month}-15",
            "vegetation_cover": f"{np.mean(vals):.1f}%",
        })
    print(f"[fvc] 聚合: {len(rows)} 行")
    return rows, warnings


def merge_remote_sensing_outputs(
    ndvi_rows: list[dict], fvc_rows: list[dict], snow_rows: list[dict],
    degradation_rows: list[dict] | None = None,
    capacity_rows: list[dict] | None = None,
    source: str = "tpdc", source_id: str = "remote-sensing",
    dataset_name: str = "TPDC_Remote", region_list_path: str = "",
    is_sample_str: str = "false",
    capacity_is_demo: bool = False,
) -> tuple[list[dict], list[str]]:
    """合并 NDVI + FVC + Snow + Degradation + CarryingCapacity → remote_sensing_data。"""
    from collections import defaultdict
    import csv as _csv

    warnings: list[str] = []
    pasture_map: dict[str, str] = {}
    if region_list_path:
        p = Path(region_list_path)
        if p.exists():
            with open(p, "r", encoding="utf-8-sig") as f:
                for r in _csv.DictReader(f):
                    pasture_map[r.get("region_id", "").strip()] = r.get("pasture_type", "").strip()

    merged: dict[tuple[str, str], dict] = defaultdict(lambda: {
        "region_id": "", "scene_date": "",
        "ndvi": "", "ndvi_change": "", "vegetation_cover": "",
        "snow_cover": "", "grassland_type": "", "degradation_level": "",
        "carrying_capacity_sheep_unit": "",
        "data_source": source, "source_id": source_id,
        "dataset_name": dataset_name, "is_sample": is_sample_str,
        # 容量字段级来源（独立于主表）
        "capacity_data_source": "", "capacity_is_sample": "false", "capacity_derived": "false",
    })

    for r in ndvi_rows:
        k = (r.get("region_id", ""), r.get("scene_date", ""))
        merged[k].update({"region_id": k[0], "scene_date": k[1],
                          "ndvi": r.get("ndvi", ""), "ndvi_change": r.get("ndvi_change", "")})

    for r in fvc_rows:
        k = (r.get("region_id", ""), r.get("scene_date", ""))
        merged[k].update({"vegetation_cover": r.get("vegetation_cover", ""),
                          "region_id": k[0], "scene_date": k[1]})

    for r in snow_rows:
        k = (r.get("region_id", ""), r.get("scene_date", ""))
        merged[k].update({"snow_cover": r.get("snow_cover", ""),
                          "region_id": k[0], "scene_date": k[1]})

    for r in (degradation_rows or []):
        k = (r.get("region_id", ""), r.get("scene_date", ""))
        merged[k].update({"degradation_level": r.get("degradation_level", ""),
                          "region_id": k[0], "scene_date": k[1]})

    for r in (capacity_rows or []):
        k = (r.get("region_id", ""), r.get("scene_date", ""))
        merged[k].update({
            "carrying_capacity_sheep_unit": r.get("carrying_capacity_sheep_unit", ""),
            "capacity_data_source": r.get("capacity_data_source", ""),
            "capacity_is_sample": r.get("capacity_is_sample", "false"),
            "capacity_derived": r.get("capacity_derived", "false"),
            "region_id": k[0], "scene_date": k[1],
        })

    result = []
    for (rid, date), m in merged.items():
        # 从 region_list 取草地类型
        if not m.get("grassland_type") and pasture_map:
            m["grassland_type"] = pasture_map.get(rid, "")
        # 没有 FVC 时从 NDVI 估算
        if not m.get("vegetation_cover") and m.get("ndvi"):
            try:
                ndvi_v = float(m["ndvi"])
                m["vegetation_cover"] = f"{ndvi_v * 100:.0f}%"
            except (ValueError, TypeError):
                pass
        if not m.get("vegetation_cover"):
            m["vegetation_cover"] = "50%"
            warnings.append("vegetation_cover 无数据, 默认 50%")
        if not m.get("degradation_level"):
            m["degradation_level"] = "待评估"
        if not m.get("snow_cover"):
            m["snow_cover"] = "0%"
        if not m.get("carrying_capacity_sheep_unit"):
            m["carrying_capacity_sheep_unit"] = ""
        result.append(m)

    if not fvc_rows:
        warnings.append("FVC 数据缺失, vegetation_cover 由 NDVI 估算 (ndvi*100) 或默认 50%")
    if not snow_rows:
        warnings.append("积雪数据缺失, snow_cover 默认 0%")
    return result, warnings


def _is_sample_file(filepath: str) -> bool:
    """检测文件名是否暗示是样例数据。"""
    name = Path(filepath).name.lower()
    for keyword in ("sample", "demo", "mock", "test", "fake", "sim"):
        if keyword in name:
            return True
    return False


def process_remote_sensing_pipeline(
    region_list_path: str, output_path: str, report_path: str,
    ndvi_path: str | None, snow_path: str | None, fvc_path: str | None,
    degradation_path: str | None = None, capacity_path: str | None = None,
    degradation_raster_path: str | None = None,
    start_year: int = 2020, end_year: int = 2024,
    source: str = "tpdc", source_id: str = "remote-sensing",
    dataset_name: str = "Remote_Sensing",
    mark_real: bool = False, mark_simulated: bool = False,
) -> int:
    """遥感数据处理总管线：NDVI + Snow + FVC → remote_sensing CSV。"""
    print("=" * 60)
    print("[remote] 遥感数据处理管线")
    print(f"[remote] 年份: {start_year}-{end_year}")
    # 自动检测样例文件
    sample_inputs = [
        p for p in (ndvi_path, snow_path, fvc_path, degradation_path, capacity_path, degradation_raster_path)
        if p and _is_sample_file(p)
    ]
    if sample_inputs and not mark_real:
        print(f"[remote] 检测到样例文件: {sample_inputs}")
        print("[remote] 将标记为 sample/simulated。如需标记为真实数据，请加 --mark-real")
    print("=" * 60)

    all_warnings: list[str] = []
    ndvi_rows: list[dict] = []
    snow_rows: list[dict] = []
    fvc_rows: list[dict] = []

    if ndvi_path:
        ndvi_rows, w = process_ndvi_csv(ndvi_path, region_list_path, start_year, end_year, mark_real=mark_real)
        all_warnings.extend(w)
    else:
        all_warnings.append("未提供 NDVI 文件, 遥感 CSV 缺少核心字段")

    if snow_path:
        snow_rows, w = process_snow_csv(snow_path, region_list_path, start_year, end_year)
        all_warnings.extend(w)

    if fvc_path:
        fvc_rows, w = process_fvc_csv(fvc_path, region_list_path, start_year, end_year)
        all_warnings.extend(w)

    degradation_rows: list[dict] = []
    if degradation_raster_path:
        raster_rows, w = process_degradation_raster(
            degradation_raster_path, region_list_path, start_year, end_year
        )
        degradation_rows.extend(raster_rows)
        all_warnings.extend(w)
    if degradation_path:
        csv_rows, w = process_degradation_csv(degradation_path, region_list_path, start_year, end_year)
        degradation_rows.extend(csv_rows)
        all_warnings.extend(w)

    capacity_rows: list[dict] | None = None
    if capacity_path:
        capacity_rows, w = process_carrying_capacity_csv(capacity_path, region_list_path, start_year, end_year)
        all_warnings.extend(w)

    # 确定整体来源标记
    # 核心数据 (NDVI/Snow/Degradation) 是否真实决定主表 is_sample
    # 容量数据可能是独立的 sample/demo，不应拉低主表标记
    is_real = mark_real and not mark_simulated
    if mark_simulated:
        final_source = "simulated"
        is_sample_val = "true"
    elif mark_real:
        final_source = source
        is_sample_val = "false"
    else:
        # 自动检测：如果所有输入都是 sample，则标记 sample
        all_sample = all(
            not p or _is_sample_file(p)
            for p in (ndvi_path, snow_path, fvc_path, degradation_path)
        )
        final_source = "sample" if all_sample else source
        is_sample_val = "true" if all_sample else "false"

    # 检测容量数据是否为独立样例
    capacity_is_demo = capacity_path and _is_sample_file(str(capacity_path))
    if capacity_is_demo:
        all_warnings.append("载畜量数据来自样例/演示文件, 仅用于流程验证, 待真实 TPDC NPP 数据替换")

    merged, w = merge_remote_sensing_outputs(
        ndvi_rows, fvc_rows, snow_rows,
        degradation_rows=degradation_rows, capacity_rows=capacity_rows,
        source=final_source, source_id=source_id, dataset_name=dataset_name,
        region_list_path=region_list_path, is_sample_str=is_sample_val,
        capacity_is_demo=capacity_is_demo,
    )
    all_warnings.extend(w)

    if not merged:
        print("[remote] 无可输出的行")
        # 写报告但无 CSV
        rpt = {"error": "无有效数据行", "warnings": all_warnings}
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(rpt, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0

    OUT_COLS = [
        "region_id", "scene_date", "ndvi", "ndvi_change",
        "vegetation_cover", "snow_cover", "grassland_type", "degradation_level",
        "carrying_capacity_sheep_unit",
        "capacity_data_source", "capacity_is_sample", "capacity_derived",
        "data_source", "source_id", "dataset_name", "is_sample",
    ]
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLS, extrasaction="ignore")
        w.writeheader()
        for r in merged:
            w.writerow(r)

    print(f"[remote] 输出: {len(merged)} 行 → {out_path}")

    # 报告
    rpt = {
        "source": source, "source_id": source_id,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "year_range": f"{start_year}-{end_year}",
        "county_count": len(set(r.get("region_id", "") for r in merged)),
        "month_count": len(set(r.get("scene_date", "")[:7] for r in merged)),
        "total_rows": len(merged),
        "ndvi_rows": len(ndvi_rows), "snow_rows": len(snow_rows), "fvc_rows": len(fvc_rows),
        "degradation_rows": len(degradation_rows),
        "warnings": all_warnings, "output_file": str(out_path),
        "next_step": "打开 http://127.0.0.1:8000/admin 上传此 CSV 到 remote_sensing_data 表",
    }
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(rpt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[remote] 报告: {report_path}")
    for w in all_warnings:
        print(f"[remote] [warn] {w}")

    return len(merged)


# ============================================================================
# Degradation / Carrying Capacity 处理
# ============================================================================

def _parse_envi_header(hdr_path: Path) -> dict[str, Any]:
    """Parse the subset of ENVI metadata needed for TPDC raster sampling."""
    meta: dict[str, Any] = {}
    for raw_line in hdr_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, val = line.split("=", 1)
        meta[key.strip().lower()] = val.strip().strip("{}").strip()
    return meta


def _csv_float_list(value: str) -> list[float]:
    nums: list[float] = []
    for item in value.split(","):
        item = item.strip()
        try:
            nums.append(float(item))
        except ValueError:
            pass
    return nums


def _albers_wgs84_to_xy(lon: float, lat: float) -> tuple[float, float]:
    """Project WGS84 lon/lat into the TPDC Albers raster grid."""
    a = 6378137.0
    b = 6356752.3
    e = math.sqrt(1 - (b * b) / (a * a))
    lon0 = math.radians(105.0)
    lat0 = math.radians(0.0)
    sp1 = math.radians(25.0)
    sp2 = math.radians(47.0)

    def m(phi: float) -> float:
        return math.cos(phi) / math.sqrt(1 - e * e * math.sin(phi) ** 2)

    def q(phi: float) -> float:
        s = math.sin(phi)
        return (1 - e * e) * (
            s / (1 - e * e * s * s)
            - (1 / (2 * e)) * math.log((1 - e * s) / (1 + e * s))
        )

    n = (m(sp1) ** 2 - m(sp2) ** 2) / (q(sp2) - q(sp1))
    c = m(sp1) ** 2 + n * q(sp1)
    rho0 = a * math.sqrt(c - n * q(lat0)) / n

    phi = math.radians(lat)
    lam = math.radians(lon)
    theta = n * (lam - lon0)
    rho = a * math.sqrt(c - n * q(phi)) / n
    return rho * math.sin(theta), rho0 - rho * math.cos(theta)


def _nearest_valid_raster_value(
    raster: Any,
    row: int,
    col: int,
    nodata: float,
    max_radius: int = 30,
) -> tuple[float | None, int | None]:
    """Return the center value or nearest valid value within max_radius pixels."""
    import numpy as np

    rows, cols = raster.shape

    def valid(v: float) -> bool:
        return math.isfinite(v) and not math.isclose(v, nodata, rel_tol=0.0, abs_tol=1e-8)

    if 0 <= row < rows and 0 <= col < cols:
        center = float(raster[row, col])
        if valid(center):
            return center, 0

    for radius in range(1, max_radius + 1):
        r0 = max(0, row - radius)
        r1 = min(rows - 1, row + radius)
        c0 = max(0, col - radius)
        c1 = min(cols - 1, col + radius)
        window = np.asarray(raster[r0:r1 + 1, c0:c1 + 1], dtype=np.float64)
        mask = np.isfinite(window) & (~np.isclose(window, nodata, rtol=0.0, atol=1e-8))
        if not mask.any():
            continue
        coords = np.argwhere(mask)
        rr = coords[:, 0] + r0
        cc = coords[:, 1] + c0
        dist2 = (rr - row) ** 2 + (cc - col) ** 2
        idx = int(np.argmin(dist2))
        return float(raster[int(rr[idx]), int(cc[idx])]), int(round(math.sqrt(float(dist2[idx]))))

    return None, None


def _classify_degradation_from_slope(slope: float, pasture_type: str) -> tuple[str, str, str]:
    """Classify TPDC NDVI trend slope into the system's four risk levels."""
    if "荒漠" in pasture_type:
        group = "荒漠草地阈值"
        medium_cut = -0.005
        heavy_cut = -0.009
    else:
        group = "草原/草丛/草甸通用阈值"
        medium_cut = -0.004
        heavy_cut = -0.007

    if slope > 0.001:
        return "基本稳定", "改善", group
    if slope >= -0.001:
        return "基本稳定", "无明显变化", group
    if slope >= medium_cut:
        return "轻度退化", "轻度退化", group
    if slope >= heavy_cut:
        return "中度退化", "中度退化", group
    return "重度退化", "重度退化", group


def process_degradation_raster(input_path: str, region_list_path: str,
                               start_year: int, end_year: int) -> tuple[list[dict], list[str]]:
    """Sample TPDC 2010-2019 NDVI-slope raster and expand to region-month rows."""
    import numpy as np

    path = Path(input_path)
    if not path.exists():
        return [], [f"退化栅格文件不存在: {input_path}"]

    hdr_path = path.with_suffix(".hdr")
    if not hdr_path.exists():
        return [], [f"退化栅格缺少 ENVI 头文件: {hdr_path}"]

    meta = _parse_envi_header(hdr_path)
    try:
        samples = int(meta.get("samples", "0"))
        lines = int(meta.get("lines", "0"))
        data_type = int(meta.get("data type", "4"))
    except ValueError:
        return [], [f"退化栅格头文件解析失败: {hdr_path}"]

    if data_type != 4:
        return [], [f"暂不支持 data type={data_type} 的退化栅格，仅支持 ENVI float32"]

    map_nums = _csv_float_list(meta.get("map info", ""))
    if len(map_nums) < 6:
        return [], [f"退化栅格 map info 不完整: {hdr_path}"]

    ref_col, ref_row, x0, y0, pixel_x, pixel_y = map_nums[:6]
    nodata = float(meta.get("data ignore value", "-3"))
    dtype = "<f4" if int(meta.get("byte order", "0")) == 0 else ">f4"
    raster = np.memmap(path, dtype=dtype, mode="r", shape=(lines, samples))
    regions = load_region_meta(region_list_path)

    warnings: list[str] = [
        "degradation_level 由 TPDC 2010-2019 生长季 NDVI 趋势率栅格抽样派生，非灾害/理赔真实标签"
    ]
    static_rows: list[dict[str, Any]] = []

    for region in regions:
        rid = region["region_id"]
        lon = float(region["longitude"])
        lat = float(region["latitude"])
        pasture_type = str(region.get("pasture_type", ""))
        x, y = _albers_wgs84_to_xy(lon, lat)
        col = int(round((x - x0) / pixel_x + (ref_col - 1)))
        row = int(round((y0 - y) / pixel_y + (ref_row - 1)))
        slope, radius = _nearest_valid_raster_value(raster, row, col, nodata)

        if slope is None:
            level = "待评估"
            trend_status = "无有效栅格"
            threshold_group = "未分类"
            warnings.append(f"{rid}: 县中心及周边 30km 内无有效退化栅格值")
        else:
            level, trend_status, threshold_group = _classify_degradation_from_slope(slope, pasture_type)

        static_rows.append({
            "region_id": rid,
            "region_name": region.get("region_name", rid),
            "longitude": lon,
            "latitude": lat,
            "pasture_type": pasture_type,
            "ndvi_slope_2010_2019": "" if slope is None else round(float(slope), 8),
            "degradation_level": level,
            "trend_status": trend_status,
            "threshold_group": threshold_group,
            "nearest_valid_pixel_km": "" if radius is None else radius,
            "data_source": "tpdc",
            "source_id": "tpdc-grassland-degradation-2010-2019",
            "dataset_name": "TPDC_Grassland_Degradation_NDVI_Slope_2010_2019",
            "is_sample": "false",
            "derived": "true",
        })

    region_path = Path(region_list_path)
    processed_dir = region_path.parent / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    static_path = processed_dir / "degradation_static_tpdc_2010_2019.csv"
    static_cols = [
        "region_id", "region_name", "longitude", "latitude", "pasture_type",
        "ndvi_slope_2010_2019", "degradation_level", "trend_status",
        "threshold_group", "nearest_valid_pixel_km", "data_source",
        "source_id", "dataset_name", "is_sample", "derived",
    ]
    with open(static_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=static_cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(static_rows)
    print(f"[degradation-raster] 静态县域表: {static_path}")

    rows: list[dict] = []
    for s in static_rows:
        for y in range(start_year, end_year + 1):
            for m in range(1, 13):
                rows.append({
                    "region_id": s["region_id"],
                    "scene_date": f"{y}-{m:02d}-15",
                    "degradation_level": s["degradation_level"],
                })

    level_counts: dict[str, int] = {}
    for row in static_rows:
        level = str(row["degradation_level"])
        level_counts[level] = level_counts.get(level, 0) + 1
    print(f"[degradation-raster] 输出: {len(rows)} 行 ({len(static_rows)} 个区域, {level_counts})")
    return rows, warnings


def process_degradation_csv(input_path: str, region_list_path: str,
                            start_year: int, end_year: int) -> tuple[list[dict], list[str]]:
    """处理草地退化等级 CSV → 按 region_id + month 展开。

    允许的退化等级: 基本稳定, 轻度退化, 中度退化, 重度退化
    静态数据（无 date/year 列）自动复制到每个 region-month。
    """
    regions = load_region_meta(region_list_path)
    region_ids = {r["region_id"] for r in regions}
    path = Path(input_path)
    if not path.exists():
        print(f"[degradation] 文件不存在: {input_path}")
        return [], ["退化数据文件不存在"]

    with open(path, "r", encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))

    valid_levels = {"基本稳定", "轻度退化", "中度退化", "重度退化"}
    warnings: list[str] = []

    # 判断是静态还是年度数据
    has_date = any(c in raw[0] for c in ("date", "year", "scene_date")) if raw else False

    # 构建 region_id → degradation_level 映射
    deg_map: dict[str, str] = {}
    for r in raw:
        rid = r.get("region_id", "").strip()
        level = r.get("degradation_level", r.get("level", "")).strip()
        if not rid or rid not in region_ids:
            continue
        if level not in valid_levels:
            warnings.append(f"未知退化等级 '{level}' for {rid}, 跳过")
            continue
        deg_map[rid] = level

    if not deg_map:
        warnings.append("未能解析任何有效退化等级行")
        return [], warnings

    # 生成 region×month 行
    rows = []
    for rid, level in deg_map.items():
        if has_date:
            # 按日期行，只过滤年份范围
            date_col = next((c for c in ("date", "scene_date", "year") if c in raw[0]), "date")
            for r in raw:
                if r.get("region_id", "").strip() != rid:
                    continue
                d = str(r.get(date_col, "")).strip()
                if len(d) >= 7:
                    month = d[:7]
                elif len(d) == 4:
                    month = f"{d}-01"
                else:
                    continue
                y = int(month[:4])
                if start_year <= y <= end_year:
                    rows.append({"region_id": rid, "scene_date": f"{month}-15", "degradation_level": level})
        else:
            # 静态: 复制到每年每月
            for y in range(start_year, end_year + 1):
                for m in range(1, 13):
                    rows.append({"region_id": rid, "scene_date": f"{y}-{m:02d}-15", "degradation_level": level})

    print(f"[degradation] 输出: {len(rows)} 行 ({len(deg_map)} 个区域)")
    return rows, warnings


def process_carrying_capacity_csv(input_path: str, region_list_path: str,
                                   start_year: int, end_year: int) -> tuple[list[dict], list[str]]:
    """处理载畜量 / 草地生产力 CSV → 按 region_id + month 展开。

    直接列: region_id, year/date, carrying_capacity_sheep_unit
    推导列: NPP → carrying_capacity（标记 derived）
    """
    regions = load_region_meta(region_list_path)
    region_ids = {r["region_id"] for r in regions}
    path = Path(input_path)
    if not path.exists():
        print(f"[capacity] 文件不存在: {input_path}")
        return [], ["载畜量数据文件不存在"]

    with open(path, "r", encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))

    warnings: list[str] = []
    has_date = any(c in raw[0] for c in ("date", "year", "scene_date")) if raw else False

    cap_map: dict[str, float] = {}
    is_derived = False
    for r in raw:
        rid = r.get("region_id", "").strip()
        if not rid or rid not in region_ids:
            continue

        # 直接值
        cap_str = r.get("carrying_capacity_sheep_unit", r.get("capacity", "")).strip()
        if cap_str:
            try:
                cap_map[rid] = float(cap_str)
            except ValueError:
                pass
            continue

        # NPP → carrying_capacity 估算（标记 derived）
        npp = r.get("npp", r.get("NPP", "")).strip()
        if npp:
            try:
                npp_val = float(npp)
                # 简化估算: 1 gC/m² NPP ≈ 0.005-0.01 羊单位/亩/年
                # 此处仅为预留框架，不伪装真实
                cap_map[rid] = round(npp_val * 0.008, 0)
                is_derived = True
            except ValueError:
                pass
            continue

    if not cap_map:
        warnings.append("未能解析任何有效载畜量行")
        return [], warnings
    if is_derived:
        warnings.append("载畜量由 NPP 衍生估算 (derived), 非实测值")

    rows = []
    # 从首行读取容量来源标记（用于 field-level provenance）
    cap_source = str(raw[0].get("data_source", "sample")).strip() if raw else "sample"
    cap_is_sample = str(raw[0].get("is_sample", "true")).strip().lower() in ("true", "1", "yes", "t")
    cap_derived = str(raw[0].get("derived", "false")).strip().lower() in ("true", "1", "yes", "t") or is_derived
    cap_src_id = str(raw[0].get("source_id", "")).strip() if raw else ""

    for rid, cap in cap_map.items():
        if has_date:
            date_col = next((c for c in ("date", "scene_date", "year") if c in raw[0]), "date")
            for r in raw:
                if r.get("region_id", "").strip() != rid:
                    continue
                d = str(r.get(date_col, "")).strip()
                month = d[:7] if len(d) >= 7 else f"{d}-01"
                y = int(month[:4])
                if start_year <= y <= end_year:
                    rows.append({
                        "region_id": rid, "scene_date": f"{month}-15",
                        "carrying_capacity_sheep_unit": cap,
                        "capacity_data_source": cap_source,
                        "capacity_is_sample": "true" if cap_is_sample else "false",
                        "capacity_derived": "true" if cap_derived else "false",
                    })
        else:
            for y in range(start_year, end_year + 1):
                for m in range(1, 13):
                    rows.append({
                        "region_id": rid, "scene_date": f"{y}-{m:02d}-15",
                        "carrying_capacity_sheep_unit": cap,
                        "capacity_data_source": cap_source,
                        "capacity_is_sample": "true" if cap_is_sample else "false",
                        "capacity_derived": "true" if cap_derived else "false",
                    })

    if cap_is_sample:
        warnings.append(f"载畜量数据来源为 {cap_source}/sample, 仅用于流程验证, 待真实 TPDC NPP 数据替换")
    print(f"[capacity] 输出: {len(rows)} 行 ({len(cap_map)} 个区域, derived={cap_derived}, is_sample={cap_is_sample})")
    return rows, warnings


# ============================================================================
# CLI
# ============================================================================

def main():
    p = argparse.ArgumentParser(description="处理公开数据 (CMFD NetCDF / 遥感 CSV)")
    p.add_argument("--source", required=True, choices=["tpdc","modis","cma","manual"])
    p.add_argument("--dataset", default="cmfd")
    # CMFD
    p.add_argument("--temp", default=None); p.add_argument("--prec", default=None)
    p.add_argument("--wind", default=None)
    # 遥感
    p.add_argument("--remote-ndvi", default=None, help="NDVI CSV 文件路径")
    p.add_argument("--remote-snow", default=None, help="积雪覆盖 CSV 文件路径")
    p.add_argument("--remote-fvc", default=None, help="植被覆盖度 CSV 文件路径")
    p.add_argument("--remote-degradation", default=None, help="草地退化等级 CSV 文件路径")
    p.add_argument("--remote-degradation-raster", default=None, help="TPDC 退化 NDVI 趋势率栅格 TIF 文件路径")
    p.add_argument("--remote-capacity", default=None, help="载畜量 CSV 文件路径")
    p.add_argument("--remote-source-id", default="remote-sensing", help="遥感数据源标识")
    p.add_argument("--dataset-name", default="Remote_Sensing", help="数据集名称")
    p.add_argument("--mark-real", action="store_true", help="标记为真实数据 (is_sample=false)")
    p.add_argument("--mark-simulated", action="store_true", help="标记为模拟数据")
    # 通用
    p.add_argument("--start-year", type=int, required=True)
    p.add_argument("--end-year", type=int, required=True)
    p.add_argument("--input", default=None); p.add_argument("--output", required=True)
    p.add_argument("--table", default="weather_data")
    p.add_argument("--region-list", default="public_data/region_list.csv")
    p.add_argument("--report", default=None)
    args = p.parse_args()
    rpt = args.report or (str(Path(args.output).with_suffix("")) + "_report.json")

    if args.remote_ndvi or args.remote_snow or args.remote_fvc or args.remote_degradation or args.remote_degradation_raster or args.remote_capacity:
        n = process_remote_sensing_pipeline(
            region_list_path=args.region_list, output_path=args.output, report_path=rpt,
            ndvi_path=args.remote_ndvi, snow_path=args.remote_snow, fvc_path=args.remote_fvc,
            degradation_path=args.remote_degradation, capacity_path=args.remote_capacity,
            degradation_raster_path=args.remote_degradation_raster,
            start_year=args.start_year, end_year=args.end_year,
            source=args.source, source_id=args.remote_source_id,
            dataset_name=args.dataset_name,
            mark_real=args.mark_real, mark_simulated=args.mark_simulated,
        )
    elif args.temp or args.prec or args.wind:
        n = process_cmfd_netcdf(args.region_list, args.temp, args.prec, args.wind,
                                args.start_year, args.end_year, args.output, rpt)
    elif args.input:
        print("[error] CSV 通用模式暂未实现")
        sys.exit(1)
    else:
        print("[error] 请指定运行模式: --temp (CMFD) 或 --remote-ndvi (遥感)")
        sys.exit(1)
    if n == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
