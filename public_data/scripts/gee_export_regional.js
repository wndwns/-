/**
 * Google Earth Engine - 25 县区域统计导出 (边界框均值 + 草地掩膜)
 * ============================================================================
 * 改进:
 *   1. 从 ee.Geometry.Point (单点) 改为 ee.Geometry.Rectangle (县域边界框)
 *   2. 加草地掩膜 (MODIS MCD12Q1 IGBP 类别 6-10), 过滤非草地区域
 *
 * 使用方法:
 *   1. 打开 https://code.earthengine.google.com/
 *   2. 粘贴此脚本, 点击 Run
 *   3. 右侧 Tasks 标签页, 逐个点击 Run 执行导出任务
 *   4. 从 Google Drive 下载 CSV
 *   5. 放到:
 *      - NDVI: public_data/raw/modis/ndvi/ndvi_modis_regional_2020_2024.csv
 *      - Snow: public_data/raw/modis/snow/snow_modis_regional_2020_2024.csv
 *   6. 运行后处理:
 *      python public_data/scripts/regenerate_json_data.py
 */

// ---- 草地掩膜 (MODIS MCD12Q1 IGBP 分类) ----
// IGBP 类别 6-10: 封闭灌丛/开放灌丛/稀树草原/稀树草原/草地
var landcover = ee.ImageCollection('MODIS/061/MCD12Q1')
    .select('LC_Type1')
    .sort('system:time_start', false)
    .first();

var grasslandMask = landcover.gte(6).and(landcover.lte(10));
print('草地掩膜已创建');

// ---- 25 县边界框 (从 DataV 行政边界获取) ----
var sites = [
  ee.Feature(null, {region_id: 'naqu-bange', region_name: '那曲市班戈县', minLon: 89.0032, maxLon: 91.2774, minLat: 29.939, maxLat: 32.2436}),
  ee.Feature(null, {region_id: 'naqu-seni', region_name: '那曲市色尼区', minLon: 90.9926, maxLon: 93.0169, minLat: 30.5173, maxLat: 31.8712}),
  ee.Feature(null, {region_id: 'naqu-nierong', region_name: '那曲市聂荣县', minLon: 91.8285, maxLon: 93.477, minLat: 31.6763, maxLat: 32.766}),
  ee.Feature(null, {region_id: 'naqu-anduo', region_name: '那曲市安多县', minLon: 88.7146, maxLon: 92.5781, minLat: 31.4386, maxLat: 36.2372}),
  ee.Feature(null, {region_id: 'naqu-shenzha', region_name: '那曲市申扎县', minLon: 87.7891, maxLon: 89.7897, minLat: 30.0503, maxLat: 32.314}),
  ee.Feature(null, {region_id: 'changdu-karuo', region_name: '昌都市卡若区', minLon: 96.6952, maxLon: 97.9564, minLat: 30.6982, maxLat: 32.3033}),
  ee.Feature(null, {region_id: 'changdu-luolong', region_name: '昌都市洛隆县', minLon: 95.2486, maxLon: 96.5711, minLat: 30.1968, maxLat: 31.1575}),
  ee.Feature(null, {region_id: 'changdu-leiwuqi', region_name: '昌都市类乌齐县', minLon: 95.8131, maxLon: 96.9612, minLat: 30.9479, maxLat: 31.9296}),
  ee.Feature(null, {region_id: 'changdu-jiangda', region_name: '昌都市江达县', minLon: 97.3284, maxLon: 98.887, minLat: 31.0101, maxLat: 32.5872}),
  ee.Feature(null, {region_id: 'rikaze-xietongmen', region_name: '日喀则市谢通门县', minLon: 87.0801, maxLon: 89.0358, minLat: 29.3106, maxLat: 30.4309}),
  ee.Feature(null, {region_id: 'rikaze-jiangzi', region_name: '日喀则市江孜县', minLon: 89.1327, maxLon: 90.2258, minLat: 28.4771, maxLat: 29.2331}),
  ee.Feature(null, {region_id: 'rikaze-kangma', region_name: '日喀则市康马县', minLon: 89.0197, maxLon: 90.2348, minLat: 28.0899, maxLat: 28.8491}),
  ee.Feature(null, {region_id: 'rikaze-zhongba', region_name: '日喀则市仲巴县', minLon: 82.1435, maxLon: 84.775, minLat: 29.1625, maxLat: 31.8068}),
  ee.Feature(null, {region_id: 'shannan-cuona', region_name: '山南市错那县', minLon: 91.4012, maxLon: 94.3649, minLat: 26.8548, maxLat: 28.4597}),
  ee.Feature(null, {region_id: 'ali-gaize', region_name: '阿里地区改则县', minLon: 81.9817, maxLon: 86.3286, minLat: 31.4788, maxLat: 35.8607}),
  ee.Feature(null, {region_id: 'yushu-chengduo', region_name: '玉树州称多县', minLon: 96.1307, maxLon: 97.7588, minLat: 32.9039, maxLat: 34.7913}),
  ee.Feature(null, {region_id: 'yushu-zaduo', region_name: '玉树州杂多县', minLon: 92.5609, maxLon: 96.0489, minLat: 32.1461, maxLat: 33.8201}),
  ee.Feature(null, {region_id: 'guoluo-maqin', region_name: '果洛州玛沁县', minLon: 98.8088, maxLon: 100.9776, minLat: 33.722, maxLat: 35.2994}),
  ee.Feature(null, {region_id: 'guoluo-jiuzhi', region_name: '果洛州久治县', minLon: 100.3372, maxLon: 101.7785, minLat: 33.026, maxLat: 34.0481}),
  ee.Feature(null, {region_id: 'haibei-gangcha', region_name: '海北州刚察县', minLon: 99.3576, maxLon: 100.6189, minLat: 36.8673, maxLat: 38.0683}),
  ee.Feature(null, {region_id: 'huangnan-zeku', region_name: '黄南州泽库县', minLon: 100.6877, maxLon: 102.1325, minLat: 34.7416, maxLat: 35.5068}),
  ee.Feature(null, {region_id: 'ganzi-shiqu', region_name: '甘孜州石渠县', minLon: 97.3481, maxLon: 99.2669, minLat: 32.3237, maxLat: 34.2094}),
  ee.Feature(null, {region_id: 'ganzi-seda', region_name: '甘孜州色达县', minLon: 99.3546, maxLon: 101.0117, minLat: 31.6746, maxLat: 33.0488}),
  ee.Feature(null, {region_id: 'aba-hongyuan', region_name: '阿坝州红原县', minLon: 101.8527, maxLon: 103.3475, minLat: 31.8514, maxLat: 33.3198}),
  ee.Feature(null, {region_id: 'gannan-luqu', region_name: '甘南州碌曲县', minLon: 102.0112, maxLon: 102.9736, minLat: 33.9672, maxLat: 34.8258}),
  ee.Feature(null, {region_id: 'linzhi-bayi', region_name: '林芝市巴宜区', minLon: 93.455, maxLon: 95.2876, minLat: 29.3594, maxLat: 30.2478}),
];

// 将边界框转为 Rectangle 几何
var fc = ee.FeatureCollection(sites).map(function(f) {
  var rect = ee.Geometry.Rectangle([
    ee.Number(f.get('minLon')),
    ee.Number(f.get('minLat')),
    ee.Number(f.get('maxLon')),
    ee.Number(f.get('maxLat'))
  ]);
  return ee.Feature(rect, f.toDictionary());
});

// ============================================================================
// 1. MOD13Q1 NDVI (月度, 250m, 2020-2024) + 草地掩膜
// ============================================================================
var modisNDVI = ee.ImageCollection('MODIS/061/MOD13Q1')
    .filterDate('2020-01-01', '2024-12-31')
    .select('NDVI');

var startMonth = ee.Date.fromYMD(2020, 1, 1);
var monthOffsets = ee.List.sequence(0, 59);

var ndviRows = ee.FeatureCollection(monthOffsets.map(function(offset) {
  offset = ee.Number(offset);
  var start = startMonth.advance(offset, 'month');
  var end = start.advance(1, 'month');

  var monthMean = modisNDVI.filterDate(start, end)
      .mean()
      .multiply(0.0001)               // MODIS NDVI scale factor -> 0-1
      .updateMask(grasslandMask)      // 只保留草地像素
      .rename('ndvi');

  var reduced = monthMean.reduceRegions({
    collection: fc,
    reducer: ee.Reducer.mean(),
    scale: 250,
    crs: 'EPSG:4326'
  });

  return reduced.map(function(f) {
    return f.set('date', start.format('YYYY-MM')).select(['region_id', 'region_name', 'date', 'mean']);
  });
})).flatten();

Export.table.toDrive({
  collection: ndviRows,
  description: 'ndvi_modis_regional_grassland_2020_2024',
  fileFormat: 'CSV',
  selectors: ['region_id', 'region_name', 'date', 'mean']
});

// ============================================================================
// 2. MOD10A1 Snow Cover (月度, 500m, 2020-2024) + 草地掩膜
// ============================================================================
var modisSnow = ee.ImageCollection('MODIS/061/MOD10A1')
    .filterDate('2020-01-01', '2024-12-31')
    .select('NDSI_Snow_Cover');

var snowRows = ee.FeatureCollection(monthOffsets.map(function(offset) {
  offset = ee.Number(offset);
  var start = startMonth.advance(offset, 'month');
  var end = start.advance(1, 'month');

  var monthMean = modisSnow.filterDate(start, end)
      .mean()
      .updateMask(grasslandMask)      // 只保留草地像素
      .rename('snow_cover');

  var reduced = monthMean.reduceRegions({
    collection: fc,
    reducer: ee.Reducer.mean(),
    scale: 500,
    crs: 'EPSG:4326'
  });

  return reduced.map(function(f) {
    return f.set('date', start.format('YYYY-MM')).select(['region_id', 'region_name', 'date', 'mean']);
  });
})).flatten();

Export.table.toDrive({
  collection: snowRows,
  description: 'snow_modis_regional_grassland_2020_2024',
  fileFormat: 'CSV',
  selectors: ['region_id', 'region_name', 'date', 'mean']
});

print('NDVI rows:', ndviRows.size());
print('Snow rows:', snowRows.size());
print('Done! Check Tasks tab to export.');
