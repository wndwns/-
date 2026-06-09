import urllib.request, json
d = json.loads(urllib.request.urlopen('http://127.0.0.1:8003/api/platform', timeout=5).read())
print('top-level keys:', list(d.keys())[:20])
print('regions count:', len(d.get('regions', [])))
print('subjects count:', len(d.get('subjects', [])))
print('finance count:', len(d.get('finance', [])))
print('first region:', d.get('regions', [{}])[0] if d.get('regions') else 'NONE')
print('first subject:', d.get('subjects', [{}])[0] if d.get('subjects') else 'NONE')
print('first finance:', d.get('finance', [{}])[0] if d.get('finance') else 'NONE')
