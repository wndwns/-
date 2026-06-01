/**
 * Google Earth Engine - MODIS Snow Cover 25县月度导出模板
 * ============================================================================
 *
 * 使用方法:
 *   1. 打开 https://code.earthengine.google.com/
 *   2. 粘贴此脚本, 点击 Run
 *   3. 右侧 Tasks 标签页, 点击 Run 执行导出任务
 *   4. 从 Google Drive 下载 CSV
 *   5. 放到: public_data/raw/modis/snow/snow_modis_real_2020_2024.csv
 *   6. 运行合并转换:
 *      python public_data/scripts/ingest_public_data.py --source modis --dataset ndvi \
 *          --remote-ndvi public_data/raw/modis/ndvi/ndvi_modis_real_2020_2024.csv \
 *          --remote-snow public_data/raw/modis/snow/snow_modis_real_2020_2024.csv \
 *          --start-year 2020 --end-year 2024 --mark-real \
 *          --remote-source-id modis-ndvi-snow-2020-2024 \
 *          --dataset-name MODIS_MOD13Q1_MOD10A1_2020_2024 \
 *          --output public_data/processed/remote_sensing_modis_ndvi_snow_2020_2024.csv
 *
 * 数据源: MODIS/061/MOD10A1 (500m daily NDSI Snow Cover)
 * 输出: 25 县 × 5 年 × 12 月 = 1500 行
 * 字段: region_id, region_name, date, snow_cover
 */

// ---- 25 个高原牧区示范县 ----
var sites = [
  ee.Feature(null, {region_id: 'naqu-bange',        region_name: '那曲市班戈县',     lon: 90.01, lat: 31.36}),
  ee.Feature(null, {region_id: 'naqu-seni',         region_name: '那曲市色尼区',     lon: 92.05, lat: 31.48}),
  ee.Feature(null, {region_id: 'naqu-nierong',      region_name: '那曲市聂荣县',     lon: 92.30, lat: 32.12}),
  ee.Feature(null, {region_id: 'naqu-anduo',        region_name: '那曲市安多县',     lon: 91.68, lat: 32.27}),
  ee.Feature(null, {region_id: 'naqu-shenzha',      region_name: '那曲市申扎县',     lon: 88.71, lat: 30.94}),
  ee.Feature(null, {region_id: 'changdu-karuo',     region_name: '昌都市卡若区',     lon: 97.18, lat: 31.14}),
  ee.Feature(null, {region_id: 'changdu-luolong',   region_name: '昌都市洛隆县',     lon: 95.82, lat: 30.74}),
  ee.Feature(null, {region_id: 'changdu-leiwuqi',   region_name: '昌都市类乌齐县',   lon: 96.60, lat: 31.21}),
  ee.Feature(null, {region_id: 'changdu-jiangda',   region_name: '昌都市江达县',     lon: 98.22, lat: 31.50}),
  ee.Feature(null, {region_id: 'rikaze-xietongmen', region_name: '日喀则市谢通门县', lon: 88.26, lat: 29.43}),
  ee.Feature(null, {region_id: 'rikaze-jiangzi',    region_name: '日喀则市江孜县',   lon: 89.60, lat: 28.92}),
  ee.Feature(null, {region_id: 'rikaze-kangma',     region_name: '日喀则市康马县',   lon: 89.68, lat: 28.56}),
  ee.Feature(null, {region_id: 'rikaze-zhongba',    region_name: '日喀则市仲巴县',   lon: 84.19, lat: 29.66}),
  ee.Feature(null, {region_id: 'shannan-cuona',     region_name: '山南市措那县',     lon: 91.96, lat: 27.99}),
  ee.Feature(null, {region_id: 'ali-gaize',         region_name: '阿里地区改则县',   lon: 84.06, lat: 32.30}),
  ee.Feature(null, {region_id: 'yushu-chengduo',    region_name: '玉树州称多县',     lon: 97.11, lat: 33.37}),
  ee.Feature(null, {region_id: 'yushu-zaduo',       region_name: '玉树州杂多县',     lon: 95.30, lat: 32.90}),
  ee.Feature(null, {region_id: 'guoluo-maqin',      region_name: '果洛州玛沁县',     lon: 100.24,lat: 34.48}),
  ee.Feature(null, {region_id: 'guoluo-jiuzhi',     region_name: '果洛州久治县',     lon: 101.48,lat: 33.43}),
  ee.Feature(null, {region_id: 'haibei-gangcha',    region_name: '海北州刚察县',     lon: 100.15,lat: 37.33}),
  ee.Feature(null, {region_id: 'huangnan-zeku',     region_name: '黄南州泽库县',     lon: 101.47,lat: 35.04}),
  ee.Feature(null, {region_id: 'ganzi-shiqu',       region_name: '甘孜州石渠县',     lon: 98.10, lat: 32.98}),
  ee.Feature(null, {region_id: 'ganzi-seda',        region_name: '甘孜州色达县',     lon: 100.33,lat: 32.27}),
  ee.Feature(null, {region_id: 'aba-hongyuan',      region_name: '阿坝州红原县',     lon: 102.55,lat: 32.79}),
  ee.Feature(null, {region_id: 'gannan-luqu',       region_name: '甘南州碌曲县',     lon: 102.49,lat: 34.59}),
];

var fc = ee.FeatureCollection(sites).map(function(f) {
  return ee.Feature(ee.Geometry.Point([ee.Number(f.get('lon')), ee.Number(f.get('lat'))]), f.toDictionary());
});

// ---- MODIS Snow Cover (MOD10A1) ----
var modisSnow = ee.ImageCollection('MODIS/061/MOD10A1')
    .filterDate('2020-01-01', '2024-12-31')
    .select('NDSI_Snow_Cover');

// ---- 按年-月遍历: 2020-01 ~ 2024-12 (60个月) ----
// Build a one-dimensional list of month offsets. This avoids creating
// List<List<FeatureCollection>>, which Earth Engine cannot cast directly.
var startMonth = ee.Date.fromYMD(2020, 1, 1);
var monthOffsets = ee.List.sequence(0, 59);

var monthlyRows = ee.FeatureCollection(monthOffsets.map(function(offset) {
  offset = ee.Number(offset);
  var start = startMonth.advance(offset, 'month');
  var end = start.advance(1, 'month');

  var monthMean = modisSnow.filterDate(start, end)
      .mean()
      .rename('snow_cover');

  var reduced = monthMean.reduceRegions({
    collection: fc,
    reducer: ee.Reducer.mean(),
    scale: 500,
    crs: 'EPSG:4326'
  });

  return reduced.map(function(f) {
    return f.set({
      'date': start.format('YYYY-MM'),
      'snow_cover': f.get('mean')
    }).select(['region_id', 'region_name', 'date', 'snow_cover']);
  });
})).flatten();

// ---- 导出到 Google Drive ----
Export.table.toDrive({
  collection: monthlyRows,
  description: 'snow_modis_real_2020_2024',
  fileFormat: 'CSV',
  selectors: ['region_id', 'region_name', 'date', 'snow_cover']
});
