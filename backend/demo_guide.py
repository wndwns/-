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

# 客服对外唯一知识源：一份面向用户的客服文档，全量固定进 system，不检索、不喂内部文档。
# （内部/答辩/开发类文档不进客服上下文，从源头杜绝仓库地址、版本分层等内部信息流出。）
_KB_PATH = BACKEND.parent / "客服知识库（面向用户）.md"
_KB_FULL = _KB_PATH.read_text(encoding="utf-8", errors="replace") if _KB_PATH.exists() else ""

# 参考来源标记（用于前端元信息展示）
KB_SECTIONS_REF = ["客服知识库（面向用户）·全文"]

# 固定进 system 的核心口径与红线（总是携带，不参与选段）
SYSTEM_HEAD = """你是「工银牧融（前端品牌：牧融绿链）·高原畜牧绿色金融演示助手」。任务是教用户这个平台怎么用、每个页面能干什么、结论怎么来的、能算什么、什么时候不能算。

【该怎么答】
- 先直接给出答案和数字，再补一句依据；不自说自话地堆免责声明，语气自然、具体，像平台的产品引导。
- 面向“教用户用项目”。用户问“贷多少 / 能贷吗 / 某案例建议多少”时，优先调用工具 credit_evaluate 拿本地测算的真实金额，不要自己编数。

【必须守住的口径（关系到数据可靠性与合规，违反就是错答）】
1. 金额与状态一律引用本地授信测算结果(credit_evaluate)；只有测算链给出的推荐金额才算数。
2. 四维风险分 / 模型只用于人工核查的优先级排序，不直接决定贷多少，也不代表能预测灾害或违约概率；表述成“用于优先核查”即可，不要升级成“预测”。
3. 演示样例与待核验资料要如实说明是“演示 / 待核验”口径，不要当成真实现有保单或真实工行台账。
4. “当前条件下无可行贷款方案”是“按现有资料暂算不出可行方案”，不是被拒贷，也不是永远不能贷；补充资料后可重算。
5. 不输出个人敏感信息（姓名、手机号、地址、耳标明细、密钥、数据库密码）。自动审批 / 承诺放款不在平台能力内，最终由人工决定；点到一句即可，不必反复强调。
6. 不要复述数据规模的精确行数、牲畜头数清单或演示样例的具体金额等数字（例如“3120 行”“2392 行”“980 头牛”“271 万”），改用定性描述（如“覆盖高原牧区县”“脱敏的比赛样例”）；平台授信测算给出的唯一建议金额除外。
7. 用户询问源码 / 代码 / 仓库 / 内部实现时，用一句话简短回绝即可，不算作功能，不做引导性展开或解释。

【不要给内部开发信息】
- 不要提供或复述任何仓库地址、git 分支 / commit、服务器或目录路径、内部分层(如 server_v2/server_v3、frontend_v2)或“以某分支/某代码为准”“去代码 / data 文件核对”这类指向内部维护的内容。
- 用户问到“源码 / 代码 / 放在哪”时，简短说明这是演示项目即可，不给仓库链接或内部入口。
"""

# 全量知识块：固定拼进每个 system（约 2k token），保证所有对外要点常驻、不依赖检索命中。
KNOWLEDGE_BLOCK = ("\n\n【项目知识库（全量，仅对外客服文档）】\n" + _KB_FULL) if _KB_FULL else ""

# 选择系统可用时，给出可调用的工具说明（用于提示 LLM 何时走工具）
TOOL_HINT = """
【可用工具】
- credit_evaluate(case_id): 调用本地授信测算，返回唯一建议金额/状态/关键财务字段。当用户问“贷多少、建议金额、能否可行、授信测算结果”时，必须优先调用它，不能自己算金额。
"""


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


def _chat_text_stream(system: str, user: str) -> Any:
    """调用 LLM，返回流式响应对象（调用方逐 chunk 读取 output_text）。"""
    return _get_client().responses.create(
        model=os.environ.get("OPENAI_CHAT_MODEL", "gpt-5.6-luna"),
        input=user,
        instructions=system,
        stream=True,
    )


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
    q = query
    # 优先：明确的授信测算触发词（要"给某主体算额度/测算结果"）
    tool_kw = ["建议贷多少", "能贷多少", "可贷多少", "贷多少", "贷多少钱", "贷款多少",
               "授信测算结果", "credit_evaluate", "帮我算", "帮我测算", "算一下",
               "测算一下", "建议贷款", "推荐贷款", "建议授信"]
    if any(k in q for k in tool_kw):
        return "tools"
    # 次优先：教学 / 使用引导问法（怎么用、怎么算、步骤、是什么）→ 知识，别再误触测算
    teach_kw = ["怎么用", "如何用", "怎么操作", "如何操作", "怎么弄", "怎么算",
                "怎么计算", "如何计算", "计算步骤", "使用方法", "怎么", "如何",
                "是什么", "干什么", "干嘛", "流程", "步骤", "介绍"]
    if any(k in q for k in teach_kw):
        return "knowledge"
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

    # 2) 知识：对外文档全量固定进 system（KNOWLEDGE_BLOCK），此处仅保留参考来源标记
    sections = KB_SECTIONS_REF

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
    if tool_result:
        safe = _strip_sensitive(json.dumps(tool_result, ensure_ascii=False, default=str)[:3000])
        user_prompt += f"实时授信测算结果（本地复算，供你引用真实数据）：\n{safe}\n"

    sys_p = SYSTEM_HEAD + KNOWLEDGE_BLOCK
    if route == "tools":
        sys_p += "\n\n用户明确要授信结果。请把上方【实时授信测算结果】中的关键字段（状态、唯一建议金额、关键瓶颈)转述给用户，并说明这是本地授信测算链的可复算结果、非自动审批决定。"

    answer_text = _chat_text(sys_p, user_prompt)

    return {
        "answer": answer_text,
        "tool": tool,
        "tool_result": tool_result,
        "sections": sections,
        "needs_verification": route == "tools" and bool(tool_result),
    }


def _prepare(query: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """公共的意图路由 + 上下文/工具准备（answer 与 answer_stream 共用）。"""
    query = (query or "").strip()
    history = history or []
    route = _route(query)
    sections = KB_SECTIONS_REF
    tool_result = None
    tool = None
    if route == "tools":
        cid = "bankgong-green-coop"
        if any(k in query for k in ["百巴", "babba", "资料不足", "blocked"]):
            for c in available_cases():
                if c.get("blocked"):
                    cid = c["id"]
                    break
        raw_result = run_credit_evaluate(cid)
        tool = "credit_evaluate"
        tool_result = raw_result
    user_prompt = f"用户问题：{query}\n\n"
    if tool_result:
        safe = _strip_sensitive(json.dumps(tool_result, ensure_ascii=False, default=str)[:3000])
        user_prompt += f"实时授信测算结果（本地复算，供你引用真实数据）：\n{safe}\n"
    sys_p = SYSTEM_HEAD + KNOWLEDGE_BLOCK
    if route == "tools":
        sys_p += "\n\n用户明确要授信结果。请把上方【实时授信测算结果】中的关键字段（状态、唯一建议金额、关键瓶颈)转述给用户，并说明这是本地授信测算链的可复算结果、非自动审批决定。"
    return {
        "route": route, "sys_p": sys_p, "user_prompt": user_prompt,
        "tool": tool, "tool_result": tool_result,
        "sections": sections,
    }


def answer_stream(query: str, history: list[dict[str, str]] | None = None):
    """流式回答生成器。yield dict 事件序列：
      {"type":"meta", "tool":..., "tool_result":..., "needs_verification":bool, "sections":[...]}
      {"type":"chunk", "text": "..."}           # 逐段文本
      {"type":"done"}
    问候/空输入同样以 chunk/done 给出。
    """
    query = (query or "").strip()
    if not query:
        yield {"type": "meta", "tool": None, "tool_result": None, "needs_verification": False, "sections": []}
        yield {"type": "chunk", "text": "请问想了解工银牧融平台的哪一方面？"}
        yield {"type": "done"}
        return
    if query in {"你好", "您好", "hi", "hello", "在吗"}:
        yield {"type": "meta", "tool": None, "tool_result": None, "needs_verification": False, "sections": []}
        greeting = ("你好，我是工银牧融演示助手。我懂这个项目的口径和用法，也能帮你调本地授信测算。你可以问我：\n"
                    "· 这个平台是做什么的？\n· 授信工作台怎么用？\n· 某案例建议贷多少？\n· 模型和授信是什么关系？")
        yield {"type": "chunk", "text": greeting}
        yield {"type": "done"}
        return
    prep = _prepare(query, history)
    yield {
        "type": "meta",
        "tool": prep["tool"], "tool_result": prep["tool_result"],
        "needs_verification": prep["route"] == "tools" and bool(prep["tool_result"]),
        "sections": prep["sections"],
    }
    try:
        stream = _chat_text_stream(prep["sys_p"], prep["user_prompt"])
        # 流式响应必须迭代事件才有增量文本；不能读未消费的 stream.output_text（迭代前为空）
        for ev in stream:
            piece = ""
            dt = getattr(ev, "delta", None)
            if isinstance(dt, str):
                piece = dt
            elif dt is not None:
                piece = getattr(dt, "text", None) or ""
            if not piece:
                piece = getattr(ev, "text", None) or ""
            if piece:
                yield {"type": "chunk", "text": piece}
    except Exception:
        yield {"type": "chunk", "text": "\n\n[回答生成中断，请稍后再试。]"}
    yield {"type": "done"}


def _strip_sensitive(text: str) -> str:
    """兜底移除可能出现的敏感字段（防泄露）。"""
    # 邮箱/手机/长串 key
    text = re.sub(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", "[邮箱已隐藏]", text)
    text = re.sub(r"1[3-9]\d{9}", "[手机已隐藏]", text)
    text = re.sub(r"sk-[A-Za-z0-9]{12,}", "[key已隐藏]", text)
    return text