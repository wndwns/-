import zipfile, json, re, collections, sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding='utf-8')

# ============================================================
# 1. 解析保单数据
# ============================================================
xlsx_path = r'C:\Users\WH\Desktop\保单模板.xlsx'
ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'

with zipfile.ZipFile(xlsx_path) as z:
    strings = []
    with z.open('xl/sharedStrings.xml') as f:
        tree = ET.parse(f)
        for si in tree.findall(f'.//{{{ns}}}si'):
            strings.append(''.join(t.text or '' for t in si.iter() if t.text))

    with z.open('xl/worksheets/sheet1.xml') as f:
        tree = ET.parse(f)
        rows = tree.findall(f'.//{{{ns}}}row')

    records = []
    for row in rows[1:]:
        cells = {}
        for c in row.findall(f'{{{ns}}}c'):
            ref = c.get('r')
            t = c.get('t')
            v = c.find(f'{{{ns}}}v')
            if v is not None and v.text is not None:
                val = v.text
                if t == 's':
                    try:
                        val = strings[int(val)]
                    except:
                        pass
                cells[ref[0]] = val
        if cells:
            records.append(cells)

print(f'=== 原始保单数据: {len(records)} 条 ===')

# ============================================================
# 2. 空间统计 - 按村聚合
# ============================================================
village_stats = collections.defaultdict(lambda: {'count': 0, 'farmers': []})
town_stats = collections.defaultdict(lambda: {'count': 0, 'villages': set()})

for r in records:
    addr = r.get('C', '')
    village = ''
    for suffix in ['村', '镇', '乡']:
        idx = addr.rfind(suffix)
        if idx > 0:
            start = max(0, addr.rfind('镇', 0, idx))
            if start > 0:
                village = addr[start+1:idx+1]
            else:
                start2 = max(0, addr.rfind('县', 0, idx))
                village = addr[start2+1:idx+1] if start2 > 0 else addr[:idx+1]
            break
    if not village:
        village = '未知'
    village_stats[village]['count'] += 1
    village_stats[village]['farmers'].append(r.get('D', ''))

for r in records:
    addr = r.get('C', '')
    m = re.search(r'([^镇]+镇)', addr)
    if m:
        t = m.group(1)
        town_stats[t]['count'] += 1
        vsuf = addr.rfind('村')
        if vsuf > 0:
            town_stats[t]['villages'].add(addr[max(0, addr.rfind('镇', 0, vsuf)):vsuf+1])

print('\n=== 按村统计 (Top 15) ===')
print(f"{'村名':<20} {'保单数':>8} {'占比':>8}")
print('-' * 40)
total = len(records)
for v, s in sorted(village_stats.items(), key=lambda x: -x[1]['count'])[:15]:
    print(f'{v:<20} {s["count"]:>8} {s["count"]/total*100:>7.1f}%')

print(f'\n=== 按乡镇统计 ===')
print(f"{'乡镇名':<25} {'保单数':>8} {'覆盖村数':>8}")
print('-' * 45)
for t, s in sorted(town_stats.items(), key=lambda x: -x[1]['count']):
    print(f'{t:<25} {s["count"]:>8} {len(s["villages"]):>8}')

# ============================================================
# 3. 关联外部数据做特征工程
# ============================================================
weather_regions = {
    'naqu-bange': {'name': '那曲市班戈县', 'temp': -3.8, 'precip': 11.6, 'wind': 8.2, 'snow': 18, 'cold_wave': '高', 'snowstorm': '高', 'drought': '低'},
    'changdu-luolong': {'name': '昌都市洛隆县', 'temp': 2.4, 'precip': 4.8, 'wind': 5.1, 'snow': 7, 'cold_wave': '中', 'snowstorm': '中', 'drought': '低'},
    'rikaze-xietongmen': {'name': '日喀则市谢通门县', 'temp': 5.7, 'precip': 1.2, 'wind': 3.6, 'snow': 2, 'cold_wave': '低', 'snowstorm': '低', 'drought': '中'},
}

remote_regions = {
    'naqu-bange': {'ndvi': 0.34, 'ndvi_change': -8.6, 'veg_cover': 42, 'snow_cover': 31, 'grassland': '高寒草甸', 'degradation': '中度退化', 'capacity': 18200},
    'changdu-luolong': {'ndvi': 0.47, 'ndvi_change': -3.2, 'veg_cover': 55, 'snow_cover': 18, 'grassland': '山地草甸', 'degradation': '轻度退化', 'capacity': 23600},
    'rikaze-xietongmen': {'ndvi': 0.52, 'ndvi_change': 1.4, 'veg_cover': 61, 'snow_cover': 11, 'grassland': '河谷草地', 'degradation': '基本稳定', 'capacity': 19800},
}

linzhi_weather = {
    'name': '林芝市巴宜区', 'temp': 9.5, 'precip': 3.2, 'wind': 2.8, 'snow': 3,
    'cold_wave': '低', 'snowstorm': '低', 'drought': '低',
}
linzhi_remote = {
    'ndvi': 0.62, 'ndvi_change': 2.1, 'veg_cover': 72, 'snow_cover': 8,
    'grassland': '山地灌丛草甸', 'degradation': '基本稳定', 'capacity': 28500,
}

print('\n=== 林芝地区 天气/遥感数据 ===')
for k, v in linzhi_weather.items():
    print(f'  {k}: {v}')
for k, v in linzhi_remote.items():
    print(f'  {k}: {v}')

# ============================================================
# 4. 特征工程
# ============================================================
risk_map = {'低': 0, '中': 1, '高': 2}
deg_map = {'基本稳定': 0, '轻度退化': 0.33, '中度退化': 0.67, '重度退化': 1.0}

linzhi_features = {
    'cold_wave_risk': risk_map.get(linzhi_weather['cold_wave'], 0),
    'snowstorm_risk': risk_map.get(linzhi_weather['snowstorm'], 0),
    'drought_risk': risk_map.get(linzhi_weather['drought'], 0),
    'snow_risk': linzhi_weather['snow'] / 30.0,
    'ndvi_score': linzhi_remote['ndvi'],
    'veg_cover_score': linzhi_remote['veg_cover'] / 100.0,
    'snow_cover_risk': linzhi_remote['snow_cover'] / 100.0,
    'degradation_risk': deg_map.get(linzhi_remote['degradation'], 0),
    'capacity_score': linzhi_remote['capacity'] / 30000.0,
    'farmer_count': len(records),
    'insurance_coverage_pct': 0.88,
    'village_count': len(village_stats),
}

# 加权综合风险
raw_risk = (
    linzhi_features['cold_wave_risk'] * 0.15 +
    linzhi_features['snowstorm_risk'] * 0.15 +
    linzhi_features['drought_risk'] * 0.10 +
    linzhi_features['snow_cover_risk'] * 0.10 +
    linzhi_features['degradation_risk'] * 0.15 +
    (1 - linzhi_features['ndvi_score']) * 0.15 +
    (1 - linzhi_features['veg_cover_score']) * 0.10 +
    (1 - linzhi_features['insurance_coverage_pct']) * 0.10
)

# ============================================================
# 5. 模型验证 - 四地区对比
# ============================================================
print('\n' + '=' * 60)
print('=== 模型验证：四地区风险对比 ===')
print('=' * 60)

regions = [
    {'name': '那曲市班戈县', 'weather': weather_regions['naqu-bange'], 'remote': remote_regions['naqu-bange'], 'farmers': 3, 'coverage': 0.82},
    {'name': '昌都市洛隆县', 'weather': weather_regions['changdu-luolong'], 'remote': remote_regions['changdu-luolong'], 'farmers': 3, 'coverage': 0.72},
    {'name': '日喀则市谢通门县', 'weather': weather_regions['rikaze-xietongmen'], 'remote': remote_regions['rikaze-xietongmen'], 'farmers': 3, 'coverage': 0.65},
    {'name': '林芝市巴宜区', 'weather': linzhi_weather, 'remote': linzhi_remote, 'farmers': len(records), 'coverage': 0.88},
]

for r in regions:
    w = r['weather']
    rm = r['remote']
    risk = (
        risk_map.get(w['cold_wave'], 0) * 2.5 +
        risk_map.get(w['snowstorm'], 0) * 2.5 +
        risk_map.get(w['drought'], 0) * 1.5 +
        w['snow'] * 0.3 +
        (1 - rm['ndvi']) * 20 +
        (100 - rm['veg_cover']) * 0.1 +
        deg_map.get(rm['degradation'], 0) * 10 +
        (1 - r['coverage']) * 5
    )
    r['risk_score'] = risk
    level = '高风险' if risk > 15 else ('中风险' if risk > 8 else '低风险')
    print(f'{r["name"]:15s}  风险分={risk:5.1f}  {level}  参保{int(r["farmers"]):>5d}户  cv={r["coverage"]:.0%}')

# 排序
regions.sort(key=lambda x: x['risk_score'])
print(f'\n风险排名（低到高）:')
for i, r in enumerate(regions):
    print(f'  {i+1}. {r["name"]} (风险分: {r["risk_score"]:.1f})')

# ============================================================
# 6. 保存JSON结果
# ============================================================
output = {
    'analysis_time': '2026-06-08',
    'source': '保单模板.xlsx',
    'total_records': len(records),
    'spatial_stats': {
        'total_villages': len(village_stats),
        'total_towns': len(town_stats),
        'top_villages': [{'name': k, 'count': v['count']} for k, v in sorted(village_stats.items(), key=lambda x: -x[1]['count'])[:10]],
        'towns': [{'name': k, 'count': v['count'], 'villages': len(v['villages'])} for k, v in sorted(town_stats.items(), key=lambda x: -x[1]['count'])],
    },
    'new_region_linzhi': {
        'region_id': 'linzhi-bayi',
        'region_name': '林芝市巴宜区',
        'weather': linzhi_weather,
        'remote_sensing': linzhi_remote,
        'farmer_count': len(records),
        'insurance_coverage': 0.88,
    },
    'features': {k: round(v, 4) if isinstance(v, float) else v for k, v in linzhi_features.items()},
    'risk_assessment': {
        'composite_score': round(raw_risk, 4),
        'level': '低风险' if raw_risk < 0.35 else ('中风险' if raw_risk < 0.65 else '高风险'),
        'ranking': [{'name': r['name'], 'score': round(r['risk_score'], 1)} for r in regions],
    },
}

out_path = r'C:\Users\WH\Desktop\gonghangbei - 副本\保单分析结果.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f'\nanalysis saved to: {out_path}')
