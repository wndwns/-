"""
生成 GEE 脚本: 用县域边界框做区域统计，导出 NPP/NDVI/Snow 区域均值。
================================================================
改进: 从 ee.Geometry.Point (单点) 改为 ee.Geometry.Rectangle (县域边界框)。

用法:
    python public_data/scripts/generate_gee_script.py

输出:
    public_data/scripts/gee_export_regional.js
    (复制到 https://code.earthengine.google.com/ 运行)

导出 3 个数据集:
    1. MOD17A3HGF (NPP) - 年度, 2001-2024
    2. MOD13Q1 (NDVI) - 月度, 2020-2024
    3. MOD10A1 (Snow) - 月度, 2020-2024
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOUNDS_PATH = ROOT / "region_bounds.json"
REGION_LIST = ROOT / "region_list.csv"
OUT_JS = ROOT / "scripts" / "gee_export_regional.js"

import csv


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
            })
    with open(BOUNDS_PATH, "r", encoding="utf-8") as f:
        bounds = json.load(f)
    for r in regions:
        r["bbox"] = bounds.get(r["region_id"])
    return regions


def generate_js(regions):
    """生成 GEE JavaScript 代码。"""

    # 生成县边界框数组
    sites_js = []
    for r in regions:
        b = r["bbox"]
        if b:
            sites_js.append(
                f"  ee.Feature(null, {{region_id: '{r['region_id']}', region_name: '{r['region_name']}', "
                f"minLon: {b['min_lon']}, maxLon: {b['max_lon']}, "
                f"minLat: {b['min_lat']}, maxLat: {b['max_lat']}}})"
            )
    sites_js_str = ",\n".join(sites_js)

    js = f"""/**
 * Google Earth Engine - 25 县区域统计导出 (边界框均值)
 * ============================================================================
 * 改进: 从 ee.Geometry.Point (单点) 改为 ee.Geometry.Rectangle (县域边界框)
 *
 * 使用方法:
 *   1. 打开 https://code.earthengine.google.com/
 *   2. 粘贴此脚本, 点击 Run
 *   3. 右侧 Tasks 标签页, 逐个点击 Run 执行导出任务
 *   4. 从 Google Drive 下载 CSV
 *   5. 放到:
 *      - NPP:  public_data/raw/modis/npp/npp_modis_regional_2001_2024.csv
 *      - NDVI: public_data/raw/modis/ndvi/ndvi_modis_regional_2020_2024.csv
 *      - Snow: public_data/raw/modis/snow/snow_modis_regional_2020_2024.csv
 *   6. 运行后处理:
 *      python public_data/scripts/regenerate_json_data.py
 */

// ---- 25 县边界框 (从 DataV 行政边界获取) ----
var sites = [
{sites_js_str}
];

// 将边界框转为 Rectangle 几何
var fc = ee.FeatureCollection(sites).map(function(f) {{
  var rect = ee.Geometry.Rectangle([
    ee.Number(f.get('minLon')),
    ee.Number(f.get('minLat')),
    ee.Number(f.get('maxLon')),
    ee.Number(f.get('maxLat'))
  ]);
  return ee.Feature(rect, f.toDictionary());
}});

// ============================================================================
// 1. MOD17A3HGF NPP (年度, 500m, 2001-2024)
// ============================================================================
var nppCollection = ee.ImageCollection('MODIS/061/MOD17A3HGF')
    .select('Npp');

var nppYears = ee.List.sequence(2001, 2024);
var nppRows = ee.FeatureCollection(nppYears.map(function(year) {{
  var img = nppCollection
      .filter(ee.Filter.calendarRange(year, year, 'year'))
      .first();
  if (img === null) return ee.FeatureCollection([]);

  var scaled = img.multiply(0.0001).rename('npp');  // kgC/m²/year

  var reduced = scaled.reduceRegions({{
    collection: fc,
    reducer: ee.Reducer.mean(),
    scale: 500,
    crs: 'EPSG:4326'
  }});

  return reduced.map(function(f) {{
    return f.set('year', year).select(['region_id', 'region_name', 'year', 'mean']);
  }};
}})).flatten();

Export.table.toDrive({{
  collection: nppRows,
  description: 'npp_modis_regional_2001_2024',
  fileFormat: 'CSV',
  selectors: ['region_id', 'region_name', 'year', 'mean']
}});

// ============================================================================
// 2. MOD13Q1 NDVI (月度, 250m, 2020-2024)
// ============================================================================
var modisNDVI = ee.ImageCollection('MODIS/061/MOD13Q1')
    .filterDate('2020-01-01', '2024-12-31')
    .select('NDVI');

var startMonth = ee.Date.fromYMD(2020, 1, 1);
var monthOffsets = ee.List.sequence(0, 59);

var ndviRows = ee.FeatureCollection(monthOffsets.map(function(offset) {{
  offset = ee.Number(offset);
  var start = startMonth.advance(offset, 'month');
  var end = start.advance(1, 'month');

  var monthMean = modisNDVI.filterDate(start, end)
      .mean()
      .multiply(0.0001)
      .rename('ndvi');

  var reduced = monthMean.reduceRegions({{
    collection: fc,
    reducer: ee.Reducer.mean(),
    scale: 250,
    crs: 'EPSG:4326'
  }});

  return reduced.map(function(f) {{
    return f.set('date', start.format('YYYY-MM')).select(['region_id', 'region_name', 'date', 'mean']);
  }};
}})).flatten();

Export.table.toDrive({{
  collection: ndviRows,
  description: 'ndvi_modis_regional_2020_2024',
  fileFormat: 'CSV',
  selectors: ['region_id', 'region_name', 'date', 'mean']
}});

// ============================================================================
// 3. MOD10A1 Snow Cover (月度, 500m, 2020-2024)
// ============================================================================
var modisSnow = ee.ImageCollection('MODIS/061/MOD10A1')
    .filterDate('2020-01-01', '2024-12-31')
    .select('NDSI_Snow_Cover');

var snowRows = ee.FeatureCollection(monthOffsets.map(function(offset) {{
  offset = ee.Number(offset);
  var start = startMonth.advance(offset, 'month');
  var end = start.advance(1, 'month');

  var monthMean = modisSnow.filterDate(start, end)
      .mean()
      .rename('snow_cover');

  var reduced = monthMean.reduceRegions({{
    collection: fc,
    reducer: ee.Reducer.mean(),
    scale: 500,
    crs: 'EPSG:4326'
  }});

  return reduced.map(function(f) {{
    return f.set('date', start.format('YYYY-MM')).select(['region_id', 'region_name', 'date', 'mean']);
  }};
}})).flatten();

Export.table.toDrive({{
  collection: snowRows,
  description: 'snow_modis_regional_2020_2024',
  fileFormat: 'CSV',
  selectors: ['region_id', 'region_name', 'date', 'mean']
}});

print('NPP rows:', nppRows.size());
print('NDVI rows:', ndviRows.size());
print('Snow rows:', snowRows.size());
print('Done! Check Tasks tab to export.');
"""
    return js


if __name__ == "__main__":
    print("=" * 60)
    print("生成 GEE 区域统计导出脚本")
    print("=" * 60)

    regions = load_regions()
    print(f"区域: {len(regions)} 个县")
    n_with_bbox = sum(1 for r in regions if r.get("bbox"))
    print(f"有边界框: {n_with_bbox}/{len(regions)}")

    js = generate_js(regions)
    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"\nGEE 脚本已生成: {OUT_JS}")
    print(f"\n下一步:")
    print(f"  1. 打开 https://code.earthengine.google.com/")
    print(f"  2. 粘贴 {OUT_JS.name} 的内容")
    print(f"  3. 点击 Run, 然后在 Tasks 标签页导出 3 个 CSV")
    print(f"  4. 下载 CSV 放到 public_data/raw/modis/ 对应目录")
    print(f"  5. 运行 python public_data/scripts/regenerate_json_data.py")
