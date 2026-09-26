"""反向验证 test_warning_month.py 的每一条都真的会咬人。

四条注入，各自对应一个原始 bug：
  I1  compute_spi 默认月改回「系统当前月」（原 bug 4）
  I2  latest_climate_month 改回「取数据最后一个月」（会踩冬季 Z-score 爆表）
  I3  坐标表路径改回 BASE/public_data（原 bug 1）
  I4  daily 变量改回 snow_depth（原 bug 2）
  I5  单位改成 ÷100（原 bug 3）

测试不红 = 该条没覆盖住。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "backend" / "early_warning.py").exists())
TARGET = ROOT / "backend" / "early_warning.py"
TEST = ROOT / "backend" / "test_warning_month.py"
PY = sys.executable

INJECTIONS = [
    ("I1 默认月改回系统当前月", [
        ("    if target_month is None:\n        target_month = latest_climate_month(region_id)",
         "    if target_month is None:\n        target_month = date.today().strftime(\"%Y-%m\")"),
    ]),
    ("I2 改回取数据最后一个月", [
        ("    cur_month = date.today().strftime(\"%m\")\n"
         "    same = sorted({d[:7] for d in dates if d[5:7] == cur_month})\n"
         "    if same:\n        return same[-1]\n    return max(d[:7] for d in dates)",
         "    return max(d[:7] for d in dates)"),
    ]),
    ("I3 坐标表路径改回 backend 目录", [
        ('csv_path = Path(__file__).resolve().parents[1] / "public_data" / "region_list.csv"',
         'csv_path = Path(__file__).resolve().parent / "public_data" / "region_list.csv"'),
    ]),
    ("I4 daily 变量改回 snow_depth", [
        ('"daily": "snow_depth_max,snowfall_sum"', '"daily": "snow_depth,snowfall_sum"'),
    ]),
    ("I5 单位改成除以 100", [
        ('"snow_depth_cm": round((depth_m or 0) * 100, 1)',
         '"snow_depth_cm": round((depth_m or 0) / 100, 1)'),
    ]),
]


def run_test() -> tuple[int, str]:
    r = subprocess.run([PY, str(TEST)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(ROOT))
    out = (r.stdout or "") + (r.stderr or "")
    failed = [ln.split()[1] for ln in out.splitlines() if ln.startswith("FAIL ")]
    return r.returncode, ",".join(failed)


def main() -> int:
    orig = TARGET.read_text(encoding="utf-8")
    code, _ = run_test()
    print(f"[基线] {'绿' if code == 0 else '红'}（应为绿）")
    print()

    bad = 0
    try:
        for label, pairs in INJECTIONS:
            src = orig
            ok = True
            for old, new in pairs:
                if old not in src:
                    print(f"{label}: ⚠️ 锚点未找到，跳过")
                    ok = False
                    break
                src = src.replace(old, new, 1)
            if not ok:
                bad += 1
                continue
            TARGET.write_text(src, encoding="utf-8")
            code, failed = run_test()
            if code != 0:
                print(f"{label}: ✅ 变红  ← {failed}")
            else:
                print(f"{label}: ❌ 仍全绿（这条没覆盖住）")
                bad += 1
    finally:
        TARGET.write_text(orig, encoding="utf-8")
        print()
        print("已还原源码")
        code, _ = run_test()
        print(f"[还原后] {'绿 ✅' if code == 0 else '红 ❌'}")

    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
