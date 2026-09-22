#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T7：删壳页（A2/A3/A4）

引用链（已核实）：
  backend/server.py  ADMIN_PAGES   -> 3 条
  frontend/app.js    navMore       -> 3 条
  frontend/app.js    moduleHref()  -> 死代码（index.html 里无任何调用）
  data.html / 壳页互链             -> 移走后 data.html 有 3 个死链，属已知遗留

做法：文件**移动**到 _原型/_removed/（可回退），不做不可逆删除。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PATCH_DIR.parent))
import serena_http as S  # noqa: E402

TMP = PATCH_DIR / "_args.json"
REMOVED = PATCH_DIR.parent / "_removed"

SHELLS = ["overview.html", "modules.html", "module.html"]

OLD_ADMIN = '''ADMIN_PAGES = {
    "",
    "index.html",
    "overview.html",
    "modules.html",
    "module.html",
    "data.html",
    "roadmap.html",
    "admin.html",
}'''
NEW_ADMIN = '''ADMIN_PAGES = {
    "",
    "index.html",
    # 2026-09-23：overview.html / modules.html / module.html 三个纯宣传壳页已下线
    # （见《银行视角改造方案探讨》A2-A4），文件移至 _原型/_removed/ 可回退。
    "data.html",
    "roadmap.html",
    "admin.html",
    "bank.html",
}'''

OLD_NAVMORE = '''      navMore: [
        { page: "insurance-portfolio", name: "资产/保险资料核验" },
        { page: "livelihood", name: "边疆民生与治理协同" },
        { href: "/overview.html", name: "平台概览" },
        { href: "/modules.html", name: "业务模块" },
        { href: "/module.html", name: "模块详情" },
        { href: "/roadmap.html", name: "实施路线" },
      ],'''
NEW_NAVMORE = '''      navMore: [
        { page: "insurance-portfolio", name: "资产/保险资料核验" },
        { page: "livelihood", name: "边疆民生与治理协同" },
        { href: "/roadmap.html", name: "实施路线" },
        // 2026-09-23：平台概览 / 业务模块 / 模块详情 三个壳页已下线（方案 A2-A4）
      ],'''

OLD_HREF = '''    moduleHref(code) {
      return `/module.html?code=${encodeURIComponent(code || "eco-monitor")}`;
    },

'''
NEW_HREF = ''


def call(tool: str, args: dict) -> None:
    TMP.write_text(json.dumps(args, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(PATCH_DIR.parent / "serena_http.py"),
         "call", tool, "--args-file", str(TMP)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "").strip()
    bad = r.returncode != 0 or "Error executing" in out
    print(f"--- {tool}: {'OK' if not bad else out[:240]}")
    if bad:
        raise SystemExit(f"{tool} 失败: {out[:400]}")


def main() -> int:
    # 1) 移动文件（可回退）
    REMOVED.mkdir(parents=True, exist_ok=True)
    moved = []
    for f in SHELLS:
        src = ROOT / "frontend" / f
        if src.exists():
            shutil.move(str(src), str(REMOVED / f))
            moved.append(f)
    print(f"--- 已移至 _原型/_removed/: {moved}")

    # 2) 清理引用
    call("replace_in_files", {"needle": OLD_ADMIN, "repl": NEW_ADMIN, "mode": "literal",
                              "relative_path": "backend/server.py", "expected_count": 1})
    call("replace_in_files", {"needle": OLD_NAVMORE, "repl": NEW_NAVMORE, "mode": "literal",
                              "relative_path": "frontend/app.js", "expected_count": 1})
    call("replace_in_files", {"needle": OLD_HREF, "repl": NEW_HREF, "mode": "literal",
                              "relative_path": "frontend/app.js", "expected_count": 1})

    # 3) 语法检查
    import py_compile
    py_compile.compile(str(ROOT / "backend/server.py"), doraise=True)
    r = subprocess.run(
        [str(Path.home() / ".workbuddy/binaries/node/versions/22.22.2-2/node.exe"),
         "--check", str(ROOT / "frontend/app.js")],
        capture_output=True, text=True,
    )
    print(f"--- node --check app.js: {'OK' if r.returncode == 0 else r.stderr[:300]}")
    if r.returncode != 0:
        return 1
    print("全部完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
