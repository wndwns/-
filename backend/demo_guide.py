"""演示助手核心：知识库 + 意图路由 + 实时数据工具桥。

设计约束（已与用户确认）：
- 不依赖 embedding/向量库（当前 LLM 代理 embedding 不稳定）。
- 不依赖 Responses function-calling（代理偶发超时）。
- 采用两段式 LLM：第一次做意图路由（JSON 输出），第二次生成最终回答。
- 实时金额/授信数据绝不靠 LLM 编造，必须走本地 credit_decision.evaluate_credit_case。
- 输出严格遵守公演真实性边界（红线见 SYSTEM_HEAD）。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

# ---------------------------------------------------------------------------
# 路径与配置
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
BACKEND = Path(__file__).resolve().parent

KNOWLEDGE_FILES = [
    ("项目全景说明", BACKEND.parent / "项目全景说明（Codex读）.md"),
    ("答辩口径", BACKEND.parent / "答辩口径.md"),
    ("项目书用户阅读版", BACKEND.parent / "工银牧融项目书（用户阅读版）.md"),
    ("深化优化方案", BACKEND.parent / "项目深化优化方案（实施前待批准）.md"),
]

# 固定进 system 的核心口径与红线（总是携带，不参与选段）
SYSTEM_HEAD = """你是「工银牧融（前端品牌：牧融绿链）·高原畜牧绿色金融演示助手」。你的任务是帮用户理解这个项目怎么用、能算什么、什么时候不能算。

【项目定性】这是一个面向青藏高原牧区的绿色金融辅助决策平台，把气象、遥感、草场、牲畜、经营、授信、保险和贷后资料整理成工行客户经理可核验的证据链。它【不是】自动审批系统、【不是】工行生产系统、【不是】违约或灾害预测器。

【真实性红线——必须严格遵守，任何回答不得违反】
1. 不得把样例/派生/待核验数据说成真实工行业务：百巴村 21 户主体与 1135 头牦牛是“资产/耳标登记参考”，不是“1135 份有效保险合同”。
2. 不得出现放款/批贷/拒贷承诺，不给“自动审批结论”。最终授信由人工完成。
3. 授信金额/偿债上限数值若用户问到，必须引用本地授信测算（工具 credit_evaluate 返回的真实字段），不得由你编造数字。
4. 模型(四维风险分 / XGBoost)只用于“人工核查优先排序”，不进入金额计算，不得说成能预测灾害或违约概率。
5. 不得输出个人敏感字段：姓名、手机号、地址、耳标明细、API Key、会话文件、数据库密码。
6. “当前条件下无可行贷款方案”是正常业务结果（infeasible/blocked），不是自动拒贷，也不是永远不能贷。
7. 数据审定事实：气象 3120 行/26 县、遥感 2392 行、NPP 26 县、环境数据多为公开/派生；经营与金融主表多为脱敏比赛样例。

【回答要求】
- 回答简短、清晰，面向“教用户怎么用这个项目/这个页面能干什么/这个结论怎么来的”。
- 所有结论先给答案，再给依据（依据要能从项目口径追溯）。
- 若问题需要计算实时授信额，优先调用工具 credit_evaluate 而非自己推算。
"""

# 选择系统可用时，给出可调用的工具说明（用于提示 LLM 何时走工具）
TOOL_HINT = """
【可用工具】
- credit_evaluate(case_id): 调用本地授信测算，返回唯一建议金额/状态/关键财务字段。当用户问“贷多少、建议金额、能否可行、授信测算结果”时，必须优先调用它，不能自己算金额。
"""


# ---------------------------------------------------------------------------
# 知识库：按标题分节
# ---------------------------------------------------------------------------

_KNOWLEDGE: list[dict[str, Any]] | None = None


def _split_markdown(path: Path) -> list[dict[str, str]]:
    """按二级/三级标题把 md 分成节。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    sections: list[dict[str, str]] = []
    cur_title = "(前言)"
    cur_lines: list[str] = []
    heading_re = re.compile(r"^\s{0,3}(#{1,4})\s+(.*)$")

    def flush():
        body = "\n".join(cur_lines).strip()
        if body and len(body) >= 8:
            sections.append({
                "source": path.stem,
                "title": cur_title,
                "text": body,
            })

    for ln in lines:
        m = heading_re.match(ln)
        if m and len(ln) < 120:
            flush()
            cur_title = m.group(2).strip()
            cur_lines = [ln.strip()]
        else:
            if ln.strip():
                cur_lines.append(ln.strip())
    flush()
    return sections


def get_knowledge() -> list[dict[str, Any]]:
    """返回知识节列表（惰性构建，进程内缓存）。"""
    global _KNOWLEDGE
    if _KNOWLEDGE is not None:
        return _KNOWLEDGE
    sections: list[dict[str, Any]] = []
    for _, path in KNOWLEDGE_FILES:
        if path.exists():
            for sec in _split_markdown(path):
                sec["source"] = sec["source"]
                sec["chars"] = len(sec["text"])
                sections.append(sec)
    _KNOWLEDGE = sections
    return sections


# ---------------------------------------------------------------------------
# 选段：关键词 + 来源加权（无外部依赖，稳定）
# ---------------------------------------------------------------------------

_EMPTY_STOP = {"的", "了", "吗", "呢", "是", "为", "吗", "什么", "怎么", "如何", "一个", "这个", "那个"}


def _tokens(text: str) -> set[str]:
    toks = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{2,}|\d+", text))
    return toks - _EMPTY_STOP


def select_sections(query: str, top_n: int = 4) -> list[dict[str, Any]]:
    """基于关键词重叠 + 标题加成，返回最相关的知识节。"""
    k = get_knowledge()
    qtok = _tokens(query)
    if not qtok:
        return k[:top_n]
    scored: list[tuple[float, dict[str, Any]]] = []
    for sec in k:
        text_tok = _tokens(sec["text"])
        title_tok = _tokens(sec["title"])
        text_hits = len(qtok & text_tok)
        title_hits = len(qtok & title_tok)
        score = text_hits * 2 + title_hits * 4
        if len(sec["text"]) < 120:
            score -= 4  # 过短的段落较少成段信息
        scored.append((score, sec))
    scored.sort(key=lambda x: x[0], reverse=True)
    # 只保留有命中或相关性最高的几段
    best = [s for sc, s in scored if sc > 0][:top_n]
    if not best:
        best = [s for _, s in scored[:top_n]]
    return best


# ---------------------------------------------------------------------------
# LLM 客户端
# ---------------------------------------------------------------------------

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            base_url=os.environ.get("OPENAI_BASE_URL", "https://ai.codesonline.dev"),
            timeout=90.0,
        )
    return _client


def _chat_json(system: str, user: str) -> dict[str, Any]:
    """调用 LLM，要求返回 JSON 对象。"""
    r = _get_client().responses.create(
        model=os.environ.get("OPENAI_CHAT_MODEL", "gpt-5.6-luna"),
        input=user,
        instructions=system,
        text={"format": {"type": "json_object"}},
    )
    raw = r.output_text if hasattr(r, "output_text") else str(r)
    raw = raw.strip()
    # 去掉可能的 ```json 包裹
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", raw).strip()
    return json.loads(raw)


def _chat_text(system: str, user: str) -> str:
    """调用 LLM，返回纯文本回答。"""
    r = _get_client().responses.create(
        model=os.environ.get("OPENAI_CHAT_MODEL", "gpt-5.6-luna"),
        input=user,
        instructions=system,
    )
    return r.output_text if hasattr(r, "output_text") else str(r)


# ---------------------------------------------------------------------------
# 实时数据工具桥（本地求值，绝不 LLM 编造）
# ---------------------------------------------------------------------------

def _load_case(case_id: str) -> dict[str, Any]:
    try:
        from store import read_credit_cases  # noqa
        path = BACKEND / "data_store" / "credit_cases.json"
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        try:
            from backend.store import read_credit_cases  # noqa
            path = BACKEND / "data_store" / "credit_cases.json"
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"error": str(exc)}
    cases = data.get("cases") or {}
    if case_id in cases:
        return cases[case_id]
    # 允许按名字模糊
    for cid, c in cases.items():
        if isinstance(c, dict) and c.get("name") and case_id in str(c["name"]):
            return c
    return {"error": f"unknown case_id: {case_id}"}


def available_cases() -> list[dict[str, Any]]:
    try:
        path = BACKEND / "data_store" / "credit_cases.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        out = [{"id": k, "name": (v or {}).get("name", ""), "blocked": bool((v or {}).get("blocked"))}
               for k, v in (data.get("cases") or {}).items()]
        out.sort(key=lambda x: x["id"])
        return out
    except Exception:
        return []


def run_credit_evaluate(case_id: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    """本地调授信测算。返回可复算的真实结果（不持久化、不改案例）。"""
    case = _load_case(case_id)
    if not case or "error" in case:
        return case if isinstance(case, dict) else {"error": "case not found"}
    try:
        from credit_decision import evaluate_credit_case
    except ImportError:
        from backend.credit_decision import evaluate_credit_case
    res = evaluate_credit_case(case, inputs)
    return dict(res)


# ---------------------------------------------------------------------------
# 意图路由
# ---------------------------------------------------------------------------

def _route(query: str) -> str:
    """判断是否需要实时数据。返回 'tools' 或 'knowledge'。"""
    # 强信号：直接提到授信测算 / 建议金额 / 可行方案
    tool_kw = ["建议金额", "贷多少", "贷款金额", "授信测算", "授信结果", "测算看看",
               "建议贷款", "金额", "可行", "可行性", "能贷多少", "credit_evaluate"]
    q = query
    if any(k in q for k in tool_kw):
        return "tools"
    # 进一步用一次轻量 LLM 判断（知识问题走这里）
    try:
        sys_p = (
            "判断用户问题是否需要调用平台实时数据接口(credit_evaluate 授信测算)。"
            "如果问题是在问项目的概念、页面功能、怎么使用、数据口径、模型是什么——属于纯知识问题→返回 knowledge。"
            "只有明确要求'给某个案例的授信/贷款/金额测算结果'时→返回 tools。"
            '只输出一个词，不要其他内容。'
        )
        r = _get_client().responses.create(
            model=os.environ.get("OPENAI_CHAT_MODEL", "gpt-5.6-luna"),
            input=query,
            instructions=sys_p,
        )
        txt = (r.output_text if hasattr(r, "output_text") else str(r)).strip().lower()
        if "tool" in txt:
            return "tools"
    except Exception:
        pass
    return "knowledge"


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def answer(query: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """处理一条用户消息，返回给前端渲染。

    Args:
        query: 用户问题。
        history: 可选对话历史（role: user/assistant）。
    Returns:
        {answer, tool, tool_result, sections, needs_verification}
    """
    query = (query or "").strip()
    if not query:
        return {"answer": "请问想了解工银牧融平台的哪一方面？", "tool": None, "tool_result": None, "needs_verification": False}

    # 0) 常见引导/问候
    if query in {"你好", "您好", "hi", "hello", "在吗"}:
        return {
            "answer": "你好，我是工银牧融演示助手。我懂这个项目的口径和用法，也能帮你调本地授信测算。你可以问我：\n"
                      "· 这个平台是做什么的？\n· 授信工作台怎么用？\n· 某案例建议贷多少？\n· 模型和授信是什么关系？",
            "tool": None, "tool_result": None, "needs_verification": False,
        }

    history = history or []

    # 1) 意图路由
    route = _route(query)

    # 2) 准备上下文片段
    sections = select_sections(query, top_n=4)
    context_blob = "\n\n".join(
        f"【来自《{s['source']}》·{s['title']}】\n{s['text'][:1500]}" for s in sections
    )

    tool_result = None
    tool = None
    if route == "tools":
        # 默认黄金主案例；若提问指定了百巴村/资料不足，路由到 blocked 案例
        cid = "bankgong-green-coop"
        if any(k in query for k in ["百巴", "babba", "资料不足", "blocked"]):
            for c in available_cases():
                if c.get("blocked"):
                    cid = c["id"]
                    break
        raw_result = run_credit_evaluate(cid)
        tool = "credit_evaluate"
        tool_result = raw_result

    # 3) 拼装回答 prompt
    user_prompt = f"用户问题：{query}\n\n"
    if context_blob:
        user_prompt += f"以下是与问题相关的项目资料片段：\n{context_blob}\n\n"
    if tool_result:
        safe = _strip_sensitive(json.dumps(tool_result, ensure_ascii=False, default=str)[:3000])
        user_prompt += f"实时授信测算结果（本地复算，供你引用真实数据）：\n{safe}\n"

    sys_p = SYSTEM_HEAD
    if route == "tools":
        sys_p += "\n\n用户明确要授信结果。请把上方【实时授信测算结果】中的关键字段（状态、唯一建议金额、关键瓶颈)转述给用户，并说明这是本地授信测算链的可复算结果、非自动审批决定。"

    answer_text = _chat_text(sys_p, user_prompt)

    return {
        "answer": answer_text,
        "tool": tool,
        "tool_result": tool_result,
        "sections": [f"{s['source']}·{s['title']}" for s in sections],
        "needs_verification": route == "tools" and bool(tool_result),
    }


def _strip_sensitive(text: str) -> str:
    """兜底移除可能出现的敏感字段（防泄露）。"""
    # 邮箱/手机/长串 key
    text = re.sub(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", "[邮箱已隐藏]", text)
    text = re.sub(r"1[3-9]\d{9}", "[手机已隐藏]", text)
    text = re.sub(r"sk-[A-Za-z0-9]{12,}", "[key已隐藏]", text)
    return text