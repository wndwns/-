#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T2 补丁 B：收紧派生信号与保险核验状态，让队列回到业务合理量级

问题：
  1. post_loan_board 总任务 124 项 —— 因为「无耳标登记」对每一户都会触发，
     而"无耳标"本质是**准入**问题（抵押物不可核验），不是贷后信号。
  2. insurance_board 74/76 户都是「待核验」 —— 判定条件过苛，队列失去焦点。

改法：
  - 删掉「无耳标登记」派生信号（它通过准入结论的「待补资料」体现）
  - 无对价出栏阈值从 30% 提到 40%（更贴近"显著偏离同县均值"的语义）
  - 保险核验状态改为：覆盖率 ≥ 80% 判「已核验」，其余「待核验」
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import serena_http as S  # noqa: E402

TARGET = "backend/bank_view.py"
TMP = Path(__file__).resolve().parent / "_args.json"

OLD_ASSET = '''    if ledger["out_unpriced"] and ledger["unpriced_ratio"] >= 30:
        out.append({
            "signal_class": "资产类",
            "trigger": f"无对价出栏 {ledger['out_unpriced']} 头，占出栏 {ledger['unpriced_ratio']}%",
            "level": "高", "status": "待处理",
            "source": "derived",
        })
    if ledger["book_head"] and ledger["tag_head"] == 0:
        out.append({
            "signal_class": "资产类",
            "trigger": "无耳标登记，抵押物不可核验",
            "level": "中", "status": "待处理",
            "source": "derived",
        })'''

NEW_ASSET = '''    if ledger["out_unpriced"] and ledger["unpriced_ratio"] >= 40:
        out.append({
            "signal_class": "资产类",
            "trigger": f"无对价出栏 {ledger['out_unpriced']} 头，占出栏 {ledger['unpriced_ratio']}%",
            "level": "高", "status": "待处理",
            "source": "derived",
        })'''

OLD_INS = '''            "liability_verified": False,
            "status": "已核验" if coverage >= 80 and _stable(name + "#v", 0, 9) < 3 else "待核验",'''

NEW_INS = '''            "liability_verified": coverage >= 80,
            "status": "已核验" if coverage >= 80 else "待核验",'''

REPLACEMENTS = [(OLD_ASSET, NEW_ASSET), (OLD_INS, NEW_INS)]


def call(tool: str, args: dict) -> None:
    TMP.write_text(json.dumps(args, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "serena_http.py"),
         "call", tool, "--args-file", str(TMP)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "").strip()
    ok = r.returncode == 0 and "Error" not in out and "FAIL" not in out.upper()[:20]
    print(f"--- {tool}: {'OK' if ok else out[:240]}")
    if not ok:
        raise SystemExit(f"{tool} 失败: {out[:400]}")


def main() -> int:
    for old, new in REPLACEMENTS:
        call("replace_in_files", {
            "needle": old, "repl": new, "mode": "literal",
            "relative_path": TARGET, "expected_count": 1,
        })
    import py_compile
    py_compile.compile(str(ROOT / TARGET), doraise=True)
    print("compile OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
