#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T2 补丁：bank_view.py 的数值解析加固

背景：data_store 里混着字符串数值 ——
  business_subjects.insurance_coverage = "80%"      (str)
  business_subjects.credit_amount      = "230 万元"  (str)
  finance_credit.interest_rate         = "4.20%"    (str)
直接 float() 会 TypeError。统一用 _num() 兜底。
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

NUM_FN = '''def _num(value: Any) -> float:
    """把 data_store 里可能带单位/百分号的数值安全转成 float。

    源数据里既有 int（credit_line=271），也有 str（insurance_coverage="80%"、
    credit_amount="230 万元"、interest_rate="4.20%"）。缺失或无法解析时返回 0.0。
    """
    if value is None or isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    for unit in ("万元", "元", "%", "％", "头", "亩", "天", "期", "笔", "份"):
        text = text.replace(unit, "")
    text = text.replace(",", "").replace(" ", "").strip()
    try:
        return float(text)
    except ValueError:
        return 0.0


'''

# (旧, 新) —— 全部按字面替换，逐一核对过
REPLACEMENTS: list[tuple[str, str]] = [
    ('    overdue = int((fin or {}).get("overdue_times") or 0)',
     '    overdue = int(_num((fin or {}).get("overdue_times")))'),
    ('    line = float((fin or {}).get("credit_line") or 0)',
     '    line = _num((fin or {}).get("credit_line"))'),
    ('    used = float((fin or {}).get("used_credit") or 0)',
     '    used = _num((fin or {}).get("used_credit"))'),
    ('    coverage = float(subject.get("insurance_coverage") or 0)',
     '    coverage = _num(subject.get("insurance_coverage"))'),
    ('    overdue = int(fin.get("overdue_times") or 0)',
     '    overdue = int(_num(fin.get("overdue_times")))'),
    ('        "amount_yuan": int(float(fin.get("credit_line") or 0) * 10000),',
     '        "amount_yuan": int(_num(fin.get("credit_line")) * 10000),'),
    ('        coverage = float(s.get("insurance_coverage") or 0)',
     '        coverage = _num(s.get("insurance_coverage"))'),
    ('                credit_total += float(fin["credit_line"])  # 单位：万元',
     '                credit_total += _num(fin["credit_line"])  # 单位：万元'),
    ('        v = float(score)', '        v = _num(score)'),
    # evidence 里拿字符串和 int 比大小会 TypeError
    ('"status": "已获取" if (subject.get("insurance_coverage") or 0) > 0 else "缺失",',
     '"status": "已获取" if _num(subject.get("insurance_coverage")) > 0 else "缺失",'),
    # overview() 在循环里反复 _load_all()，提到循环外
    ('''    deployed = 0.0
    for s in _load_all()["subjects"]:
        fin = _load_all()["finance"].get(s.get("name"))
        if fin and fin.get("credit_line"):
            deployed += float(fin["credit_line"])''',
     '''    ctx = _load_all()
    deployed = 0.0
    for s in ctx["subjects"]:
        fin = ctx["finance"].get(s.get("name"))
        if fin and fin.get("credit_line"):
            deployed += _num(fin["credit_line"])'''),
    # 保险台账里的 coverage 判空
    ('        if not ledger["book_head"] and not coverage:',
     '        if not ledger["book_head"] and not coverage:'),
]


def call(tool: str, args: dict) -> str:
    TMP.write_text(json.dumps(args, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "serena_http.py"),
         "call", tool, "--args-file", str(TMP)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "").strip()
    print(f"--- {tool}: {out[:220] or '(无输出)'}")
    if r.returncode != 0:
        raise SystemExit(f"{tool} 失败")
    return out


def main() -> int:
    call("insert_before_symbol", {
        "name_path": "_stable", "relative_path": TARGET, "body": NUM_FN,
    })
    for old, new in REPLACEMENTS:
        if old == new:
            continue
        call("replace_in_files", {
            "needle": old, "repl": new, "mode": "literal",
            "relative_path": TARGET, "expected_count": 1,
        })
    import py_compile
    py_compile.compile(str(ROOT / TARGET), doraise=True)
    print("\ncompile OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
