#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Serena 本地 HTTP 客户端（零依赖）

用途：不经过 WorkBuddy 的 MCP 层，直接调用本地跑起来的 Serena
（`serena start-mcp-server --transport streamable-http --port 24282`）。

用法：
  python serena_http.py list                                  # 列出可用工具
  python serena_http.py call get_symbols_overview '{"relative_path":"backend/credit_decision.py"}'
  python serena_http.py call find_symbol '{"name_path_pattern":"evaluate_credit_case","relative_path":"backend/credit_decision.py","include_body":true}'
  python serena_http.py call find_referencing_symbols '{"name_path":"_affordable_limits","relative_path":"backend/credit_decision.py"}'

环境变量：
  SERENA_URL   默认 http://127.0.0.1:24282/mcp
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

URL = os.environ.get("SERENA_URL", "http://127.0.0.1:24282/mcp")
PROTOCOL = "2025-06-18"


def _post(payload: dict[str, Any], session: str | None) -> tuple[dict[str, Any] | None, str | None]:
    """发一次 JSON-RPC。返回 (响应体, 会话 id)。"""
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session:
        headers["mcp-session-id"] = session
        headers["MCP-Protocol-Version"] = PROTOCOL

    req = urllib.request.Request(URL, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            sid = resp.headers.get("mcp-session-id") or session
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:800]
        raise SystemExit(f"HTTP {e.code}: {detail}") from e

    # streamable-http 可能返回 SSE（data: {...}）或纯 JSON
    if raw.lstrip().startswith("{"):
        return json.loads(raw), sid
    for line in raw.splitlines():
        if line.startswith("data:"):
            chunk = line[5:].strip()
            if chunk and chunk != "[DONE]":
                return json.loads(chunk), sid
    return None, sid


def connect() -> str:
    """initialize + notifications/initialized，返回会话 id。"""
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL,
            "capabilities": {},
            "clientInfo": {"name": "serena-http-cli", "version": "1.0"},
        },
    }
    resp, sid = _post(init, None)
    if resp is None or "result" not in resp:
        raise SystemExit(f"initialize 失败：{resp}")
    if not sid:
        raise SystemExit("服务端未返回 mcp-session-id，无法继续")

    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    info = resp["result"].get("serverInfo", {})
    print(f"[已连接] {info.get('name', 'serena')} {info.get('version', '')}  会话 {sid[:8]}…",
          file=sys.stderr)
    return sid


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    action = sys.argv[1]
    sid = connect()

    if action == "list":
        resp, _ = _post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, sid)
        tools = resp["result"]["tools"]  # type: ignore[index]
        for t in tools:
            print(f"{t['name']:<28} {t.get('description','').splitlines()[0][:90]}")
        return 0

    if action == "call":
        if len(sys.argv) < 3:
            print("用法：call <tool_name> [json_args]")
            print("      call <tool_name> --args-file <path.json>   # 参数较长时用，避免命令行转义")
            return 2
        name = sys.argv[2]
        if len(sys.argv) > 4 and sys.argv[3] == "--args-file":
            args = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
        elif len(sys.argv) > 3:
            args = json.loads(sys.argv[3])
        else:
            args = {}
        resp, _ = _post(
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": name, "arguments": args}},
            sid,
        )
        if resp is None:
            print("(无响应)")
            return 1
        if "error" in resp:
            print(json.dumps(resp["error"], ensure_ascii=False, indent=2))
            return 1
        result = resp["result"]
        if result.get("isError"):
            for c in result.get("content", []):
                print(c.get("text", ""))
            return 1
        for c in result.get("content", []):
            print(c.get("text", ""))
        return 0

    print(f"未知动作：{action}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
