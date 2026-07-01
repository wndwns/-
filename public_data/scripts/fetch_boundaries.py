"""
获取 25 县行政边界 GeoJSON，保存到 public_data/boundaries/。
同时计算每县的边界框 (bbox)，保存到 public_data/region_bounds.json。
"""
import urllib.request, json, os, time, sys
from pathlib import Path

# 25 县 (措那县已改名为错那市)
COUNTIES = [
    ("naqu-bange", "班戈县"),
    ("naqu-seni", "色尼区"),
    ("naqu-nierong", "聂荣县"),
    ("naqu-anduo", "安多县"),
    ("naqu-shenzha", "申扎县"),
    ("changdu-karuo", "卡若区"),
    ("changdu-luolong", "洛隆县"),
    ("changdu-leiwuqi", "类乌齐县"),
    ("changdu-jiangda", "江达县"),
    ("rikaze-xietongmen", "谢通门县"),
    ("rikaze-jiangzi", "江孜县"),
    ("rikaze-kangma", "康马县"),
    ("rikaze-zhongba", "仲巴县"),
    ("shannan-cuona", "错那"),      # 模糊匹配
    ("ali-gaize", "改则县"),
    ("yushu-chengduo", "称多县"),
    ("yushu-zaduo", "杂多县"),
    ("guoluo-maqin", "玛沁县"),
    ("guoluo-jiuzhi", "久治县"),
    ("haibei-gangcha", "刚察县"),
    ("huangnan-zeku", "泽库县"),
    ("ganzi-shiqu", "石渠县"),
    ("ganzi-seda", "色达县"),
    ("aba-hongyuan", "红原县"),
    ("gannan-luqu", "碌曲县"),
    ("linzhi-bayi", "巴宜区"),
]

ROOT = Path(__file__).resolve().parent.parent
BOUND_DIR = ROOT / "boundaries"
BOUND_DIR.mkdir(exist_ok=True)

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read())

def extract_all_coords(coords, lons, lats):
    """递归提取所有坐标点。"""
    if isinstance(coords[0], (int, float)):
        lons.append(coords[0])
        lats.append(coords[1])
    else:
        for sub in coords:
            extract_all_coords(sub, lons, lats)

# Step 1: 获取行政区划列表
print("=== 获取行政区划列表 ===")
raw = fetch_json("https://geo.datav.aliyun.com/areas_v3/bound/all.json")
print(f"  {len(raw)} 个区划")

# Step 2: 匹配 adcode
print("\n=== 匹配 adcode ===")
adcode_map = {}
for rid, cname in COUNTIES:
    found = None
    for f in raw:
        name = f.get("name", "")
        if cname in name:  # 模糊匹配
            found = f.get("adcode")
            matched_name = name
            break
    if found:
        adcode_map[rid] = found
        print(f"  {rid}: {matched_name} -> adcode={found}")
    else:
        print(f"  {rid}: NOT FOUND")

# Step 3: 获取每县边界
print(f"\n=== 获取 {len(adcode_map)} 县边界 ===")
bounds = {}
for rid, adcode in adcode_map.items():
    url = f"https://geo.datav.aliyun.com/areas_v3/bound/{adcode}.json"
    try:
        geo = fetch_json(url)
        feat = geo["features"][0]
        coords = feat["geometry"]["coordinates"]

        lons, lats = [], []
        extract_all_coords(coords, lons, lats)

        bbox = {
            "min_lon": round(min(lons), 4),
            "max_lon": round(max(lons), 4),
            "min_lat": round(min(lats), 4),
            "max_lat": round(max(lats), 4),
            "center_lon": round(sum(lons) / len(lons), 4),
            "center_lat": round(sum(lats) / len(lats), 4),
            "n_vertices": len(lons),
        }
        bounds[rid] = bbox
        print(f"  {rid}: bbox=lon[{bbox['min_lon']},{bbox['max_lon']}] lat[{bbox['min_lat']},{bbox['max_lat']}] ({bbox['n_vertices']} pts)")

        # 保存 GeoJSON
        out_file = BOUND_DIR / f"{rid}.geojson"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(geo, f, ensure_ascii=False)

        time.sleep(0.3)  # 别太快
    except Exception as e:
        print(f"  {rid}: FAIL - {e}")

# Step 4: 保存边界框映射
out_bounds = ROOT / "region_bounds.json"
with open(out_bounds, "w", encoding="utf-8") as f:
    json.dump(bounds, f, ensure_ascii=False, indent=2)
print(f"\n=== 完成: {len(bounds)}/{len(COUNTIES)} 县 ===")
print(f"  边界 GeoJSON -> {BOUND_DIR}/")
print(f"  边界框映射 -> {out_bounds}")
