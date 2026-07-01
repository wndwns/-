"""
用 Python 启动 headless Chrome 截图 5 个页面。
"""
import subprocess
import os
import time
import sys
from pathlib import Path

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUT_DIR = Path(r"c:\Users\WH\Desktop\gonghangbei\frontend_v3")
PAGES = ["overview", "data", "risk", "loan", "monitor"]

# 清理旧图
for f in OUT_DIR.glob("screenshot-*.png"):
    f.unlink()

# 一个独立 user-data-dir 避免冲突
user_data = Path(r"c:\Users\WH\Desktop\gonghangbei\.chrome-tmp")
user_data.mkdir(parents=True, exist_ok=True)

for page in PAGES:
    out = OUT_DIR / f"screenshot-{page}.png"
    # 用 ?page=xxx 而非 hash 触发初始页切换
    url = f"http://127.0.0.1:8003/?page={page}"
    print(f"[{page}] {url}")
    cmd = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--window-size=1440,900",
        f"--user-data-dir={user_data}",
        f"--screenshot={out}",
        "--virtual-time-budget=35000",
        "--run-all-compositor-stages-before-draw",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    if out.exists():
        size = out.stat().st_size
        print(f"  -> {size} bytes")
    else:
        print(f"  -> FAILED")
        print(f"  stderr: {result.stderr[:300]}")
    # 强制清理 chrome 进程
    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
    time.sleep(0.5)

print("\nFinal:")
for f in sorted(OUT_DIR.glob("screenshot-*.png")):
    print(f"  {f.name}  {f.stat().st_size} bytes")
