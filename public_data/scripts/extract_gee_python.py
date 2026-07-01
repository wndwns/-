"""
GEE Python API - NDVI/Snow 区域提取 (边界框 + 草地掩膜)
================================================================
需要先认证: python -m ee.cli authenticate  (浏览器登录 Google)

用法:
    python public_data/scripts/extract_gee_python.py

输出:
    - public_data/raw/modis/ndvi/ndvi_modis_regional_2020_2024.csv
    - public_data/raw/modis/snow/snow_modis_regional_2020_2024.csv
"""
import csv
import json
import sys
import time
from pathlib import Path

try:
    import ee
except ImportError:
    print("[error] 请先安装: pip install earthengine-api")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
BOUNDS_PATH = ROOT / "region_bounds.json"
REGION_LIST = ROOT / "region_list.csv"

OUT_NDVI = ROOT / "raw" / "modis" / "ndvi" / "ndvi_modis_regional_2020_2024.csv"
OUT_SNOW = ROOT / "raw" / "modis" / "snow" / "snow_modis_regional_2020_2024.csv"


def init_ee():
    """初始化 GEE，如果未认证则提示。"""
    try:
        ee.Initialize()
        print("[gee] 认证成功")
    except Exception:
        print("[gee] 未认证，正在启动认证流程...")
        print("[gee] 请在弹出的浏览器中登录 Google 账号并授权")
        ee.Authenticate()
        ee.Initialize()
        print("[gee] 认证完成")


def load_regions():
    """加载 26 县边界框。"""
    with open(BOUNDS_PATH, encoding="utf-8") as f:
        bounds = json.load(f)
    import csv as csv_mod
    regions = []
    with open(REGION_LIST, encoding="utf-8-sig") as f:
        for r in csv_mod.DictReader(f):
            rid = r["region_id"].strip()
            b = bounds.get(rid)
            if b:
                regions.append({
                    "region_id": rid,
                    "region_name": r["region_name"].strip(),
                    "min_lon": b["min_lon"],
                    "max_lon": b["max_lon"],
                    "min_lat": b["min_lat"],
                    "max_lat": b["max_lat"],
                })
    return regions


def create_fc(regions):
    """创建 GEE FeatureCollection (边界框矩形)。"""
    features = []
    for r in regions:
        rect = ee.Geometry.Rectangle([
            r["min_lon"], r["min_lat"],
            r["max_lon"], r["max_lat"]
        ])
        feat = ee.Feature(rect, {
            "region_id": r["region_id"],
            "region_name": r["region_name"],
        })
        features.append(feat)
    return ee.FeatureCollection(features)


def get_grassland_mask():
    """获取草地掩膜 (MODIS MCD12Q1 IGBP 类别 6-10)。"""
    lc = ee.ImageCollection("MODIS/061/MCD12Q1") \
        .select("LC_Type1") \
        .sort("system:time_start", False) \
        .first()
    return lc.gte(6).and(lc.lte(10))


def extract_ndvi(fc, grass_mask):
    """提取 NDVI 月度区域均值 (2020-2024)。"""
    print("\n[gee] 提取 NDVI (2020-2024, 月度, 草地掩膜)...")

    modis_ndvi = ee.ImageCollection("MODIS/061/MOD13Q1") \
        .filterDate("2020-01-01", "2024-12-31") \
        .select("NDVI")

    rows = []
    for year in range(2020, 2025):
        for month in range(1, 13):
            start = f"{year}-{month:02d}-01"
            if month == 12:
                end = f"{year+1}-01-01"
            else:
                end = f"{year}-{month+1:02d}-01"

            try:
                img = modis_ndvi.filterDate(start, end).mean()
                img = img.multiply(0.0001).updateMask(grass_mask).rename("ndvi")

                reduced = img.reduceRegions(
                    collection=fc,
                    reducer=ee.Reducer.mean(),
                    scale=250,
                    crs="EPSG:4326"
                )

                features = reduced.getInfo()["features"]
                for feat in features:
                    props = feat["properties"]
                    mean_val = props.get("mean")
                    if mean_val is not None:
                        rows.append({
                            "region_id": props.get("region_id", ""),
                            "region_name": props.get("region_name", ""),
                            "date": f"{year}-{month:02d}",
                            "ndvi": round(mean_val, 4),
                        })

                print(f"  {year}-{month:02d}: {len(features)} 县")
            except Exception as e:
                print(f"  {year}-{month:02d}: FAIL - {e}")

            time.sleep(0.5)  # 避免 GEE 配额限制

    return rows


def extract_snow(fc, grass_mask):
    """提取 Snow Cover 月度区域均值 (2020-2024)。"""
    print("\n[gee] 提取 Snow Cover (2020-2024, 月度, 草地掩膜)...")

    modis_snow = ee.ImageCollection("MODIS/061/MOD10A1") \
        .filterDate("2020-01-01", "2024-12-31") \
        .select("NDSI_Snow_Cover")

    rows = []
    for year in range(2020, 2025):
        for month in range(1, 13):
            start = f"{year}-{month:02d}-01"
            if month == 12:
                end = f"{year+1}-01-01"
            else:
                end = f"{year}-{month+1:02d}-01"

            try:
                img = modis_snow.filterDate(start, end).mean()
                img = img.updateMask(grass_mask).rename("snow_cover")

                reduced = img.reduceRegions(
                    collection=fc,
                    reducer=ee.Reducer.mean(),
                    scale=500,
                    crs="EPSG:4326"
                )

                features = reduced.getInfo()["features"]
                for feat in features:
                    props = feat["properties"]
                    mean_val = props.get("mean")
                    if mean_val is not None:
                        rows.append({
                            "region_id": props.get("region_id", ""),
                            "region_name": props.get("region_name", ""),
                            "date": f"{year}-{month:02d}",
                            "snow_cover": round(mean_val, 2),
                        })

                print(f"  {year}-{month:02d}: {len(features)} 县")
            except Exception as e:
                print(f"  {year}-{month:02d}: FAIL - {e}")

            time.sleep(0.5)

    return rows


def save_csv(rows, path, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[gee] 已保存: {path} ({len(rows)} 行)")


if __name__ == "__main__":
    print("=" * 60)
    print("GEE Python API - NDVI/Snow 区域提取")
    print("边界框均值 + 草地掩膜 (MCD12Q1 IGBP 6-10)")
    print("=" * 60)

    init_ee()

    regions = load_regions()
    print(f"区域: {len(regions)} 个县")

    fc = create_fc(regions)
    grass_mask = get_grassland_mask()
    print("草地掩膜已创建")

    # NDVI
    ndvi_rows = extract_ndvi(fc, grass_mask)
    if ndvi_rows:
        save_csv(ndvi_rows, OUT_NDVI, ["region_id", "region_name", "date", "ndvi"])

    # Snow
    snow_rows = extract_snow(fc, grass_mask)
    if snow_rows:
        save_csv(snow_rows, OUT_SNOW, ["region_id", "region_name", "date", "snow_cover"])

    print(f"\n完成: NDVI {len(ndvi_rows)} 行, Snow {len(snow_rows)} 行")
    print("下一步: python public_data/scripts/regenerate_json_data.py")
