"""验证 v3 前端依赖的所有 API 端点响应时间和返回结构。"""
import time
import urllib.request
import json
import sys

BASE = "http://127.0.0.1:8003"

ENDPOINTS = [
    ("GET", "/api/health", None, 5),
    ("GET", "/api/platform", None, 5),
    ("GET", "/api/regions", None, 5),
    ("GET", "/api/subjects", None, 5),
    ("GET", "/api/finance", None, 5),
    ("GET", "/api/data-sources", None, 5),
    ("GET", "/api/data-quality", None, 5),
    ("GET", "/api/data-connections", None, 5),
    ("GET", "/api/closed-loop", None, 5),
    ("GET", "/api/model/status", None, 5),
    ("GET", "/api/model/importance", None, 5),
    ("GET", "/api/public-data/samples", None, 5),
    ("GET", "/api/public-data/processed", None, 5),
    ("GET", "/api/warning/comprehensive-all?year=2025", None, 30),
    ("GET", "/api/warning/comprehensive/naqu-bange?year=2025", None, 10),
    ("GET", "/api/warning/ndvi?region_id=naqu-bange", None, 10),
    ("GET", "/api/warning/gdi", None, 30),
    ("GET", "/api/cooperative-ranking/naqu-bange?top_n=5", None, 10),
    ("GET", "/api/carrying-capacity/daily?region_id=naqu-bange&days=10", None, 10),
    ("GET", "/api/warning/disaster/naqu-bange", None, 10),
]

ok = 0
fail = 0
for method, path, body, timeout in ENDPOINTS:
    t0 = time.time()
    try:
        url = BASE + path
        req = urllib.request.Request(url, method=method)
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = resp.read()
        ms = (time.time() - t0) * 1000
        # try parse JSON, show size
        try:
            obj = json.loads(data)
            if isinstance(obj, list):
                size = f"list[{len(obj)}]"
            elif isinstance(obj, dict):
                size = f"dict({len(obj)} keys)"
            else:
                size = type(obj).__name__
        except Exception:
            size = f"{len(data)}B"
        print(f"  OK  {ms:6.0f}ms  {path:60s}  {size}")
        ok += 1
    except Exception as e:
        ms = (time.time() - t0) * 1000
        print(f"  FAIL {ms:6.0f}ms  {path:60s}  {e}")
        fail += 1

print(f"\n{ok} OK, {fail} FAIL out of {len(ENDPOINTS)}")
sys.exit(0 if fail == 0 else 1)
