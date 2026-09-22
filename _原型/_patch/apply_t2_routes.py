#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T2 补丁 C：逾期分级 + 接入 server.py 路由"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import serena_http as S  # noqa: E402

TMP = Path(__file__).resolve().parent / "_args.json"

# --- 1) 逾期分级：1 期算中，≥2 期才算高 ---
OLD_LEVEL = '''    if overdue > 0:
        out.append({
            "signal_class": "还款类",
            "trigger": f"逾期 {overdue} 期",
            "level": "高", "status": "待处理",
            "source": "real_field",
        })'''
NEW_LEVEL = '''    if overdue > 0:
        out.append({
            "signal_class": "还款类",
            "trigger": f"逾期 {overdue} 期",
            # 逾期 1 期按「中」，≥2 期才按「高」（贴近五级分类的处理惯例，
            # 避免把每一笔逾期都标成高优先级，队列失去焦点）
            "level": "高" if overdue >= 2 else "中", "status": "待处理",
            "source": "real_field",
        })'''

# --- 2) server.py：模块级导入 bank_view ---
OLD_IMPORT = "_data = _import_data()"
NEW_IMPORT = '''_data = _import_data()


def _import_bank_view():
    """银行视角聚合视图（客户池 / 单户档案 / 一户一档 / 台账 / 贷后 / 保险 / 区域）。"""
    try:
        import bank_view as module  # type: ignore[import-not-found]
    except ImportError:
        from backend import bank_view as module  # type: ignore[no-redef,import-not-found]
    return module


_bank_view = _import_bank_view()'''

# --- 3) server.py：新增银行视角路由 ---
OLD_ROUTE = '''    @app.get("/api/alerts")
    def alerts() -> list[dict[str, Any]]:
        return _data["get_alerts"]()'''

NEW_ROUTE = '''    @app.get("/api/alerts")
    def alerts() -> list[dict[str, Any]]:
        return _data["get_alerts"]()

    # ------------------------------------------------------------------
    # 银行视角页面（bank_view 聚合；均为只读）
    # 派生层数据一律带 is_derived / derived_note，不冒充真实工行业务数据。
    # ------------------------------------------------------------------

    @app.get("/api/bank/overview")
    def bank_overview() -> dict[str, Any]:
        """工作台汇总：客户数、待办、抵押物、保险、绿色信贷余额、待营销 TOP。"""
        return _bank_view.overview()

    @app.get("/api/bank/customer-pool")
    def bank_customer_pool() -> dict[str, Any]:
        """客户池：客户列表（含准入结论、资料完整度）+ 获客来源分布。"""
        return _bank_view.customer_pool()

    @app.get("/api/bank/customer/{name}")
    def bank_customer_profile(name: str) -> dict[str, Any]:
        """单户档案：准入结论、四条证据、台账、资料摘要、信号、任务。"""
        result = _bank_view.customer_profile(name)
        if not result.get("found"):
            raise HTTPException(status_code=404, detail=f"Customer not found: {name}")
        return result

    @app.get("/api/bank/customer/{name}/documents")
    def bank_customer_documents(name: str) -> dict[str, Any]:
        """一户一档：28 项分 6 组，含状态 / 内容 / 来源。"""
        result = _bank_view.customer_documents(name)
        if not result.get("found"):
            raise HTTPException(status_code=404, detail=f"Customer not found: {name}")
        return result

    @app.get("/api/bank/ledger")
    def bank_ledger() -> dict[str, Any]:
        """活体资产台账：抵押物总览 + 无票出栏占比排行 + 按县分布。"""
        return _bank_view.ledger_board()

    @app.get("/api/bank/post-loan")
    def bank_post_loan() -> dict[str, Any]:
        """贷后待办：真实任务表 + 派生信号合并成队列。"""
        return _bank_view.post_loan_board()

    @app.get("/api/bank/insurance")
    def bank_insurance() -> dict[str, Any]:
        """保险协同：保单核验队列 + 理赔联动 + 抵押折扣分档。"""
        return _bank_view.insurance_board()

    @app.get("/api/bank/regions")
    def bank_regions() -> dict[str, Any]:
        """区域与集中度：按县统计投放、额度池占用与耳标归属头数。"""
        return _bank_view.region_board()'''


def call(tool: str, args: dict) -> None:
    TMP.write_text(json.dumps(args, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "serena_http.py"),
         "call", tool, "--args-file", str(TMP)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "").strip()
    bad = r.returncode != 0 or "Error executing" in out
    print(f"--- {tool}: {'OK' if not bad else out[:260]}")
    if bad:
        raise SystemExit(f"{tool} 失败: {out[:400]}")


def main() -> int:
    call("replace_in_files", {"needle": OLD_LEVEL, "repl": NEW_LEVEL, "mode": "literal",
                              "relative_path": "backend/bank_view.py", "expected_count": 1})
    call("replace_in_files", {"needle": OLD_IMPORT, "repl": NEW_IMPORT, "mode": "literal",
                              "relative_path": "backend/server.py", "expected_count": 1})
    call("replace_in_files", {"needle": OLD_ROUTE, "repl": NEW_ROUTE, "mode": "literal",
                              "relative_path": "backend/server.py", "expected_count": 1})
    import py_compile
    for f in ("backend/bank_view.py", "backend/server.py"):
        py_compile.compile(str(ROOT / f), doraise=True)
    print("compile OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
