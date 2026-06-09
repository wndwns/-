import time, urllib.request, json
t0=time.time()
d=json.loads(urllib.request.urlopen('http://127.0.0.1:8003/api/warning/comprehensive-all?year=2025', timeout=30).read())
print(f'all: {time.time()-t0:.1f}s, regions={d.get("total_regions")}, high={d.get("high_risk_count")}, mid={d.get("mid_risk_count")}')
