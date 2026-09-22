#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T3 补丁：server.py 增加 /bank 路由（银行版控制台入口）

原因：serve_frontend() 对未知路径兜底返回 index.html，所以 /bank 必须像 /admin
一样显式注册，否则会落到旧版首页。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import serena_http as S  # noqa: E402

TMP = Path(__file__).resolve().parent / "_args.json"

OLD = '''    @app.get("/admin")
    def admin_page() -> FileResponse:
        target = FRONTEND_DIR / "admin.html"
        return FileResponse(target, headers={"Cache-Control": "no-store"})'''

NEW = '''    @app.get("/admin")
    def admin_page() -> FileResponse:
        target = FRONTEND_DIR / "admin.html"
        return FileResponse(target, headers={"Cache-Control": "no-store"})

    @app.get("/bank")
    def bank_console() -> FileResponse:
        """银行版控制台（左侧边栏 7 页）。

        必须显式注册：serve_frontend() 对未知路径会兜底返回 index.html，
        不注册的话 /bank 会落到旧版首页。
        """
        target = FRONTEND_DIR / "bank.html"
        if not target.exists():
            raise HTTPException(status_code=404, detail="bank.html not found")
        return FileResponse(target, headers={"Cache-Control": "no-store"})'''


def main() -> int:
    TMP.write_text(json.dumps({
        "needle": OLD, "repl": NEW, "mode": "literal",
        "relative_path": "backend/server.py", "expected_count": 1,
    }, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "serena_http.py"),
         "call", "replace_in_files", "--args-file", str(TMP)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    print((r.stdout or "").strip()[:300])
    if r.returncode != 0:
        return 1
    import py_compile
    py_compile.compile(str(ROOT / "backend/server.py"), doraise=True)
    print("compile OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
