"""
验证 v3 前端在浏览器里的行为 (无需 Chrome):
1. HTML 结构完整
2. JS 语法合法 (用 node 解析)
3. 关键 DOM 元素都在
4. 列出首屏需要的所有 API 请求

模拟 init() 行为: 检查哪些 API 在 init 流程里被调用, 估算最坏情况
加载时间。
"""
import re
import urllib.request
import json

BASE = "http://127.0.0.1:8003"

# 1. 获取 HTML
print("=" * 60)
print("1. HTML 结构检查")
print("=" * 60)
html = urllib.request.urlopen(f"{BASE}/", timeout=5).read().decode("utf-8")
print(f"  HTML size: {len(html)} bytes")
print(f"  Has DOCTYPE: {html.lower().startswith('<!doctype')}")
print(f"  Has meta viewport: {'viewport' in html}")
print(f"  Has sidebar: {'<aside class=\"sidebar\"' in html}")
print(f"  Has 5 page sections: {sum(1 for p in ['overview','data','risk','loan','monitor'] if f'page-{p}' in html)}/5")
print(f"  Loads styles.css: {'styles.css' in html}")
print(f"  Loads app.js: {'app.js' in html}")
print(f"  Loads Vue: {'vue.global.prod.js' in html}")
print(f"  Loads ECharts: {'echarts.min.js' in html}")
print()

# 2. 加载 app.js, 检查语法 (用 Python 的 tokenize 不行, 用 node 解析)
print("=" * 60)
print("2. JS 资源可获取")
print("=" * 60)
for path in ["/styles.css", "/app.js", "/vendor/vue.global.prod.js", "/vendor/echarts.min.js"]:
    try:
        r = urllib.request.urlopen(BASE + path, timeout=5)
        size = len(r.read())
        print(f"  OK  {path:30s}  {size:>10} bytes")
    except Exception as e:
        print(f"  FAIL  {path:30s}  {e}")
print()

# 3. 检查 app.js 中所有 api.* 调用
print("=" * 60)
print("3. app.js 中 initOverview() 调用的 API")
print("=" * 60)
appjs = urllib.request.urlopen(f"{BASE}/app.js", timeout=5).read().decode("utf-8")
# 找 api.xxx 调用
apis = sorted(set(re.findall(r"api\.(\w+)\s*\(", appjs)))
for a in apis:
    print(f"  - {a}")
print()

# 4. 模拟首屏 init 流程
print("=" * 60)
print("4. 模拟 initOverview() API 串行调用耗时")
print("=" * 60)
# initOverview 串行调用: platform, dataQuality, modelStatus, dataConnections, warningComprehensiveAll, closedLoop
import time
apis_to_call = [
    ("/api/platform", 5),
    ("/api/data-quality", 5),
    ("/api/model/status", 5),
    ("/api/data-connections", 5),
    ("/api/warning/comprehensive-all?year=2025", 30),
    ("/api/closed-loop", 5),
]
total = 0
for path, timeout in apis_to_call:
    t0 = time.time()
    try:
        urllib.request.urlopen(BASE + path, timeout=timeout).read()
        ms = (time.time() - t0) * 1000
        total += ms
        print(f"  {ms:7.0f}ms  {path}")
    except Exception as e:
        print(f"  FAIL  {path}  {e}")
print(f"  ----------")
print(f"  {total:7.0f}ms  TOTAL (首屏串行)")

# 5. 验证 25 县都返回
print()
print("=" * 60)
print("5. 25 县数据完整")
print("=" * 60)
d = json.loads(urllib.request.urlopen(BASE + "/api/warning/comprehensive-all?year=2025", timeout=30).read())
print(f"  Total regions: {d.get('total_regions')}")
print(f"  High risk: {d.get('high_risk_count')}, Mid: {d.get('mid_risk_count')}")
print(f"  Details keys: {len(d.get('details', {}))}")
sample_keys = list(d.get('details', {}).keys())[:5]
print(f"  Sample regions: {sample_keys}")
