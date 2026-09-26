"""
工银牧融 - 银行版操作任务（最小可落库实现）
============================================================================
职责：
  银行版控制台上「补录 / 核验 / 处置 / 转派」这类按钮的落库与留痕。
  只做一件事：追加一条任务记录到 data_store/bank_tasks.json，并把最近的任务读出来。

边界：
  - 这是**最小实现**：只记录「谁、对哪户、做了什么动作、什么时候、写了什么」，不做流转状态机。
  - 完整闭环（责任人 / 时限 / 状态流转 / 处置结果 / 统计）是方案稿二期「贷后任务闭环」的内容。
  - 不覆盖已有任务：只追加。
  - 与 bank_view 分开：bank_view 保持只读，写操作集中在本模块。

数据文件结构：
    [
      {"task_id": "...", "subject_name": "...", "action": "发起核验",
       "detail": "...", "owner": "...", "due": "", "created_at": "ISO8601",
       "source": "bank_console"}
    ]
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_VERSION = 1
_BACKEND_DIR = Path(__file__).resolve().parent
_TASKS_PATH = _BACKEND_DIR / "data_store" / "bank_tasks.json"

# ⚠️ 写锁：读-改-写不是原子操作。FastAPI 的同步路由跑在线程池里，
# 前端的批量登记又是并发 POST —— 不加锁会互相覆盖，把 JSON 写坏
#（实测：10 个并发请求直接把文件写成 "Extra data: line 46"）。
# 单进程内加锁即可；多进程部署要换成文件锁。
_WRITE_LOCK = threading.Lock()

# 银行版允许的动作白名单（防止任意字符串落库）
ACTIONS: dict[str, str] = {
    "补录": "发起补录",
    "核验": "发起核验",
    "查看": "查看",
    "处置": "发起处置",
    "转派": "转派客户经理",
    "批量处置": "批量处置",
    "提交测算": "提交测算",
}
# 不落库的纯跳转动作
NAV_ONLY = {"查看", "提交测算"}


class TaskWriteError(Exception):
    """任务写入失败（数据文件损坏或不可写）。"""


def _read() -> list[dict[str, Any]]:
    if not _TASKS_PATH.exists():
        return []
    try:
        data = json.loads(_TASKS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise TaskWriteError(f"任务表损坏或无法读取：{exc}") from exc
    if isinstance(data, dict):
        data = data.get("tasks") or []
    return [r for r in data if isinstance(r, dict)]


def list_tasks(subject_name: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """最近的任务，默认按时间倒序。读失败时抛 TaskWriteError（不静默吞）。"""
    rows = _read()
    if subject_name:
        rows = [r for r in rows if r.get("subject_name") == subject_name]
    rows.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    return rows[:limit]


def _new_id(subject_name: str, action: str, created_at: str) -> str:
    raw = f"{subject_name}|{action}|{created_at}".encode("utf-8")
    return "T" + hashlib.md5(raw).hexdigest()[:10].upper()


def create_task(subject_name: str, action: str, detail: str = "",
                owner: str = "", due_days: int | None = None) -> dict[str, Any]:
    """追加一条任务。action 必须在 ACTIONS 白名单里，纯跳转动作不落库。

    Raises:
        TaskWriteError: 动作非法、主体为空、或写入失败。
    """
    subject_name = (subject_name or "").strip()
    action = (action or "").strip()
    if not subject_name:
        raise TaskWriteError("缺少主体名称")
    if action not in ACTIONS:
        raise TaskWriteError(f"未知动作：{action}（可用：{'、'.join(ACTIONS)}）")
    if action in NAV_ONLY:
        raise TaskWriteError(f"动作「{action}」是纯跳转，不需要落库")

    now = datetime.now()
    created_at = now.isoformat(timespec="seconds")
    due = (now + timedelta(days=due_days)).date().isoformat() if due_days else ""

    row = {
        "task_id": _new_id(subject_name, action, created_at),
        "subject_name": subject_name,
        "action": ACTIONS[action],
        "detail": (detail or "").strip()[:200],
        "owner": (owner or "").strip()[:40],
        "due": due,
        "created_at": created_at,
        "source": "bank_console",
        "version": _VERSION,
    }

    # 读-改-写必须整体加锁，否则并发登记会互相覆盖（见文件头的说明）
    with _WRITE_LOCK:
        rows = _read()          # 顺带校验现有文件没坏
        rows.append(row)
        try:
            _TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
            # 先写临时文件再替换：中途失败不会留下半截 JSON
            tmp = _TASKS_PATH.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(_TASKS_PATH)
        except OSError as exc:
            raise TaskWriteError(f"任务写入失败：{exc}") from exc
    return row


def summary() -> dict[str, Any]:
    """任务概览：总数 + 按动作分布（读失败时返回带 unavailable 标记，不撒谎）。"""
    try:
        rows = _read()
    except TaskWriteError as exc:
        return {"available": False, "total": 0, "by_action": {}, "note": str(exc)}
    by_action: dict[str, int] = {}
    for r in rows:
        a = str(r.get("action") or "未分类")
        by_action[a] = by_action.get(a, 0) + 1
    return {"available": True, "total": len(rows), "by_action": by_action,
            "latest": rows[-1] if rows else None}
