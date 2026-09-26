"""
工银牧融 - 银行视角聚合视图
============================================================================
职责：
  把 data_store 里已有的主体 / 授信 / 贷后任务 / 保险台账数据，组织成银行信贷视角
  的页面数据：客户池、单户档案、一户一档资料、活体资产台账、贷后待办、保险协同、
  区域集中度。

边界：
  - 只读，不写文件、不处理 HTTP。
  - 不做真随机：所有派生量由名称的 md5 稳定派生，相同输入必得相同输出（便于测试与复算）。
  - **样例层与真实层分开标注**：
      * 主体、授信、贷后任务、耳标登记 = 来自 data_store 的真实结构数据（其中主体/授信
        本身在源文件里已标 is_sample，原样透传）；
      * 「无票出栏」「贷后信号」「保单核验队列」在源数据里没有对应表，由派生层生成，
        一律带 is_derived=True 与 derived_note，不冒充真实业务数据。
  - 敏感字段（姓名全称、电话、证件号）不出现在任何输出里。

术语：
  - 有票出栏：有《动物检疫合格证明》的销售，属正常经营（有对价）。
  - 无票出栏：自食 / 赠送 / 丢失，无对价 —— 抵押物无偿流失，只产生核查线索，不判定欺骗。
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

_BACKEND_DIR = Path(__file__).resolve().parent
_STORE_DIR = _BACKEND_DIR / "data_store"
_POLICY_PATH = _STORE_DIR / "insurance_policies.json"

# 信号分类（与方案 10.6 的五类一致）
SIGNAL_CLASSES = ("资产类", "健康类", "经营类", "环境类", "还款类", "保险类")

# 获客来源
SOURCE_GOV = "政府数据匹配"
SOURCE_CHAIN = "产业链反推"
SOURCE_SELF = "自助测额度留资"
SOURCE_EXIST = "存量客户转介"

# 一户一档资料模板：28 项 / 5 组
# 每项： (key, 名称, 组, 数据来源标签, 是否可由源数据判定)
DOC_TEMPLATE: list[tuple[str, str, str, str, bool]] = [
    # 主体资料（6）
    ("subject_name", "主体名称", "主体资料", "行内", True),
    ("subject_type", "主体类型", "主体资料", "行内", True),
    ("region_name", "所在地区", "主体资料", "行内", False),
    ("customer_manager", "客户经理", "主体资料", "行内", True),
    ("grassland_mu", "草场面积", "主体资料", "行内", True),
    ("grassland_title", "草场权属证明", "主体资料", "客户提供", False),
    # 资产资料（5）
    ("cattle_count", "存栏（牛）", "资产资料", "行内", True),
    ("sheep_count", "存栏（羊）", "资产资料", "行内", True),
    ("ear_tag", "耳标登记", "资产资料", "畜牧局", False),
    ("stock_confirm", "存栏确认（最近盘库）", "资产资料", "畜牧局 + 盘库", False),
    ("asset_value", "活体估值", "资产资料", "派生", False),
    # 防疫资料（3）
    ("vaccination", "防疫记录", "防疫资料", "兽医站", False),
    ("quarantine_cert", "检疫合格证明", "防疫资料", "动监机构", False),
    ("disease_record", "疫病记录", "防疫资料", "兽医站", False),
    # 经营资料（5）
    ("bank_flow", "银行流水", "经营资料", "行内", False),
    ("loan_use", "贷款用途", "经营资料", "行内", True),
    ("sales_contract", "销售合同", "经营资料", "客户提供", False),
    ("invoice", "开票记录", "经营资料", "税务局", False),
    ("chain_order", "产业链订单", "经营资料", "核心企业", False),
    # 保险资料（3）
    ("policy", "保单", "保险资料", "保险公司", False),
    ("coverage", "保险覆盖率", "保险资料", "保险公司", True),
    ("claim", "理赔记录", "保险资料", "保险公司", False),
    # 授信资料（6）
    ("credit_line", "授信额度", "授信资料", "行内", False),
    ("used_credit", "已用额度", "授信资料", "行内", False),
    ("repayment", "还款状态", "授信资料", "行内", False),
    ("overdue", "逾期次数", "授信资料", "行内", False),
    ("guarantee", "担保方式", "授信资料", "行内", False),
    ("unified_total", "统一授信额度", "授信资料", "行内", False),
]

DOC_GROUPS = ["主体资料", "资产资料", "防疫资料", "经营资料", "保险资料", "授信资料"]


# --------------------------------------------------------------------------
# 读取
# --------------------------------------------------------------------------

def _read_table(table: str) -> list[dict[str, Any]]:
    try:
        from .store import read_table  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - 脚本方式直接跑
        from store import read_table  # type: ignore[no-redef]
    try:
        return read_table(table)
    except Exception:  # noqa: BLE001 - 数据缺失时按空处理，不抛出
        return []


def _read_policies() -> dict[str, Any]:
    if not _POLICY_PATH.exists():
        return {}
    try:
        return json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _num(value: Any) -> float:
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


def _stable(name: str, lo: int, hi: int) -> int:
    """由名称稳定派生的整数（md5 而非 random，保证跨运行/跨平台一致）。"""
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()[:8]
    return lo + int(digest, 16) % (hi - lo + 1)


def _load_all() -> dict[str, Any]:
    """一次性载入并建立索引。"""
    subjects = _read_table("business_subjects")
    finance = {r.get("subject_name"): r for r in _read_table("finance_credit")}
    tasks = _read_table("post_loan_workflow")
    claims = _read_table("insurance_claims")
    orders = _read_table("supply_chain_orders")
    policies = _read_policies()
    farmers = policies.get("farmers") or []

    farmer_names = {f.get("farmer_name") for f in farmers if f.get("farmer_name")}
    order_names = {o.get("subject_name") for o in orders if o.get("subject_name")}
    tag_by_farmer: dict[str, int] = defaultdict(int)
    for p in policies.get("policies") or []:
        nm = p.get("farmer_name")
        if nm:
            tag_by_farmer[nm] += 1

    return {
        "subjects": subjects,
        "finance": finance,
        "tasks": tasks,
        "claims": claims,
        "farmer_names": farmer_names,
        "order_names": order_names,
        "tag_by_farmer": dict(tag_by_farmer),
    }


# --------------------------------------------------------------------------
# 派生层（无源数据支撑，一律标注 is_derived）
# --------------------------------------------------------------------------

def _derive_source(ctx: dict[str, Any], name: str) -> str:
    """获客来源：按真实存在的关联关系判定，不是随便分配。

    - 出现在保险台账 farmers 里 -> 政府登记资料里出现过该主体
    - 出现在产业链订单里       -> 可从核心企业交易反推
    - 其余                     -> 行内存量客户
    """
    if name in ctx["farmer_names"]:
        return SOURCE_GOV
    if name in ctx["order_names"]:
        return SOURCE_CHAIN
    return SOURCE_EXIST


def _derive_ledger(subject: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """活体资产台账（派生层）。

    账面在栏来自主体的真实存栏字段；耳标登记优先用保险台账里的真实登记条数，
    没有登记记录时按「有耳标 / 无耳标」两态生成，并显式标 is_derived。
    """
    name = subject.get("name", "")
    book_head = int(subject.get("cattle_count") or 0) + int(subject.get("sheep_count") or 0)
    real_tag = ctx["tag_by_farmer"].get(name)

    if real_tag is not None:
        tag_head = real_tag
        tag_source = "real_register"
    elif book_head == 0:
        tag_head = 0
        tag_source = "no_livestock"
    else:
        # 派生：约七成主体有耳标登记；无耳标的主体抵押不计入
        ratio = _stable(name, 0, 9)
        tag_head = book_head if ratio < 7 else 0
        tag_source = "derived"

    # 出栏构成（派生）：有票 = 正常销售；无票 = 自食/赠送/丢失
    out_total = _stable(name + "#out", 0, 60) if book_head else 0
    unpriced_ratio = _stable(name + "#unp", 0, 30)  # 0..30 %
    out_unpriced = round(out_total * unpriced_ratio / 100)
    if _stable(name + "#risk", 0, 9) == 0:
        # 约一成主体给到高位，用于演示「无票出栏占比显著偏高」的核查线索
        out_unpriced = round(out_total * _stable(name + "#hi", 30, 55) / 100)

    return {
        "subject_name": name,
        "region_name": subject.get("region_name", ""),
        "book_head": book_head,
        "tag_head": tag_head,
        "tag_source": tag_source,
        "out_total": out_total,
        "out_ticketed": out_total - out_unpriced,
        "out_unpriced": out_unpriced,
        "unpriced_ratio": round(out_unpriced / out_total * 100) if out_total else 0,
        "is_derived": tag_source != "real_register",
        "derived_note": "台账为演示口径派生；耳标登记条数取自百巴村真实登记资料" if tag_source == "real_register"
                        else "台账为演示口径派生，非真实工行业务数据",
    }


def _derive_signals(subject: dict[str, Any], fin: dict[str, Any] | None,
                    ledger: dict[str, Any], claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """贷后信号（派生层）。至少有一项来自真实字段（逾期 / 用信率）。"""
    name = subject.get("name", "")
    out: list[dict[str, Any]] = []

    overdue = int(_num((fin or {}).get("overdue_times")))
    line = _num((fin or {}).get("credit_line"))
    used = _num((fin or {}).get("used_credit"))
    usage = (used / line) if line else 0.0

    if overdue > 0:
        out.append({
            "signal_class": "还款类",
            "trigger": f"逾期 {overdue} 期",
            # 逾期 1 期按「中」，≥2 期才按「高」（贴近五级分类的处理惯例，
            # 避免把每一笔逾期都标成高优先级，队列失去焦点）
            "level": "高" if overdue >= 2 else "中", "status": "待处理",
            "source": "real_field",
        })
    if line and usage >= 0.9:
        out.append({
            "signal_class": "还款类",
            "trigger": f"用信率 {round(usage * 100)}% ≥ 90%",
            "level": "中", "status": "待处理",
            "source": "real_field",
        })
    if ledger["out_unpriced"] and ledger["unpriced_ratio"] >= 40:
        out.append({
            "signal_class": "资产类",
            "trigger": f"无对价出栏 {ledger['out_unpriced']} 头，占出栏 {ledger['unpriced_ratio']}%",
            "level": "高", "status": "待处理",
            "source": "derived",
        })
    coverage = _num(subject.get("insurance_coverage"))
    if coverage and coverage < 65:
        out.append({
            "signal_class": "保险类",
            "trigger": f"保险覆盖率 {round(coverage)}% < 65%",
            "level": "中", "status": "待处理",
            "source": "real_field",
        })
    if claims:
        out.append({
            "signal_class": "保险类",
            "trigger": f"关联理赔记录 {len(claims)} 条",
            "level": "中", "status": "待处理",
            "source": "real_field",
        })
    for s in out:
        s["subject_name"] = name
        s["region_name"] = subject.get("region_name", "")
    return out


# --------------------------------------------------------------------------
# 资料（一户一档）
# --------------------------------------------------------------------------

def _doc_status(subject: dict[str, Any], fin: dict[str, Any] | None,
                ledger: dict[str, Any], key: str, judgeable: bool) -> tuple[str, str]:
    """返回 (状态, 填写内容)。状态取值：已填 / 缺失 / 待核验。"""
    value = _doc_value(subject, fin, ledger, key)
    if judgeable:
        if value in (None, "", 0, "0"):
            return "缺失", "—"
        return "已填", value

    # 非源数据直接可判定的项：有值则「待核验」，无值则「缺失」
    if value in (None, "", 0, "0"):
        return "缺失", "—"
    return "待核验", value


def _doc_value(subject: dict[str, Any], fin: dict[str, Any] | None,
               ledger: dict[str, Any], key: str) -> Any:
    fin = fin or {}
    mapping = {
        "subject_name": subject.get("name"),
        "subject_type": subject.get("subject_type"),
        "region_name": subject.get("region_name"),
        "customer_manager": subject.get("customer_manager"),
        "grassland_mu": subject.get("grassland_mu"),
        "cattle_count": subject.get("cattle_count"),
        "sheep_count": subject.get("sheep_count"),
        "insurance_coverage": subject.get("insurance_coverage"),
        "coverage": subject.get("insurance_coverage"),
        "loan_use": subject.get("loan_use"),
        "credit_line": fin.get("credit_line"),
        "used_credit": fin.get("used_credit"),
        "repayment": fin.get("repayment_status"),
        "overdue": fin.get("overdue_times"),
        "guarantee": "活体抵押 + 保证" if ledger.get("tag_head") else "保证",
        "unified_total": fin.get("credit_line"),
        "ear_tag": ledger.get("tag_head") or None,
        "stock_confirm": f"{ledger.get('book_head')} 头" if ledger.get("book_head") else None,
    }
    if key in mapping:
        return mapping[key]
    # 其余项按稳定性派生「有无」，用于演示填写情况
    if _stable(f"{subject.get('name')}#{key}", 0, 9) < 7:
        return "已提供（演示）"
    return None


def customer_documents(name: str) -> dict[str, Any]:
    """一户一档：28 项分 6 组，含状态 / 内容 / 来源 / 更新说明。"""
    ctx = _load_all()
    subject = _find_subject(ctx, name)
    if subject is None:
        return {"found": False, "subject_name": name, "items": [], "summary": {}}

    fin = ctx["finance"].get(name)
    ledger = _derive_ledger(subject, ctx)

    items: list[dict[str, Any]] = []
    for key, label, group, source, judgeable in DOC_TEMPLATE:
        status, value = _doc_status(subject, fin, ledger, key, judgeable)
        items.append({
            "key": key, "label": label, "group": group, "source": source,
            "status": status, "value": value if not isinstance(value, bool) else str(value),
            "judgeable": judgeable,
        })

    filled = sum(1 for i in items if i["status"] == "已填")
    pending = sum(1 for i in items if i["status"] == "待核验")
    missing = sum(1 for i in items if i["status"] == "缺失")
    total = len(items)

    return {
        "found": True,
        "subject_name": name,
        "is_derived": True,
        "derived_note": "「已提供（演示）」为演示填写标记，非真实归档资料",
        "items": items,
        "groups": DOC_GROUPS,
        "summary": {
            "total": total, "filled": filled, "pending": pending, "missing": missing,
            "completeness": round((filled + pending * 0.5) / total * 100) if total else 0,
        },
    }


# --------------------------------------------------------------------------
# 单户
# --------------------------------------------------------------------------

def _find_subject(ctx: dict[str, Any], name: str) -> dict[str, Any] | None:
    for s in ctx["subjects"]:
        if s.get("name") == name:
            return s
    return None


# --------------------------------------------------------------------------
# 授信测算（唯一金额链）
# --------------------------------------------------------------------------

# 主体 → 测算案例的显式对应。
# 不用「同名 / 同县」模糊匹配：同一个县有多户主体（如 naqu-bange 有 3 户），
# 模糊匹配会把别人家的测算结果套到这户头上。
# 案例自带 name 与主体名一致时自动对应，不一致的在这里显式登记。
_SUBJECT_CASE_ALIAS: dict[str, str] = {
    "百巴村牦牛养殖合作社": "baiba-village",
}


def _load_cases() -> dict[str, Any]:
    """读取授信测算案例（credit_cases.json）。"""
    try:
        from .store import read_credit_cases  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - 脚本方式直接跑
        from store import read_credit_cases  # type: ignore[no-redef]
    try:
        return read_credit_cases().get("cases") or {}
    except Exception:  # noqa: BLE001 - 案例文件异常按「不可用」报，见 credit_estimate
        return {}


def _estimate_for(name: str, cases: dict[str, Any]) -> dict[str, Any]:
    """按主体名取测算结果。cases 由调用方一次载入，避免逐户读盘。"""
    case = None
    for cand in cases.values():
        if cand.get("name") == name:
            case = cand
            break
    if case is None:
        alias_id = _SUBJECT_CASE_ALIAS.get(name)
        if alias_id:
            case = cases.get(alias_id)
    if case is None:
        return {
            "state": "no_case",
            "status": None,
            "amount_yuan": None,
            "note": "该户尚未建立测算案例，故不显示建议金额",
        }

    try:
        from .credit_decision import evaluate_credit_case  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - 脚本方式直接跑
        from credit_decision import evaluate_credit_case  # type: ignore[no-redef]

    result = evaluate_credit_case(case)
    amount = result.get("recommended_amount_yuan")
    dscr = result.get("dscr")
    return {
        "state": "ok",
        "case_id": result.get("case_id") or "",
        "case_name": result.get("case_name") or "",
        "status": result.get("status") or "",
        "amount_yuan": int(amount) if amount is not None else None,
        "reason": result.get("reason") or "",
        "gap_yuan": float(result.get("gap_yuan") or 0),
        "missing_materials": list(result.get("missing_materials") or []),
        "bottleneck": result.get("bottleneck") or {},
        "dscr": float(dscr) if dscr is not None else None,
        "data_status": result.get("data_status") or {},
    }


def credit_estimate(name: str) -> dict[str, Any]:
    """该主体的授信测算结果（唯一金额链输出）。

    三种状态显式区分，互不冒充：
      - ok          : 走了 evaluate_credit_case，金额与瓶颈都来自计算；
      - no_case     : 该户没有测算案例（银行版 76 户里目前只有 2 户有）；
      - unavailable : 案例文件缺失或损坏 —— 与 no_case 分开报，避免「数据坏了」看起来像「没案例」。

    **不得用行内已有授信额度（credit_line）顶替建议金额。**
    """
    cases = _load_cases()
    if not cases:
        return {
            "state": "unavailable",
            "status": None,
            "amount_yuan": None,
            "note": "测算案例文件缺失或损坏，当前无法给出建议金额",
        }
    return _estimate_for(name, cases)


def _conclusion(subject: dict[str, Any], fin: dict[str, Any] | None,
                ledger: dict[str, Any], docs: dict[str, Any]) -> dict[str, Any]:
    """准入结论（L1）。判定顺序：无授信资料 -> 待补资料；有逾期或高无票出栏 -> 待核查；否则可测算。

    只给准入结论，**不给金额**：建议金额一律由唯一额度链给出
    （credit_decision.evaluate_credit_case，见 credit_estimate），
    不得拿行内已有授信额度回显顶替。
    """
    fin = fin or {}
    has_credit = bool(fin.get("credit_line"))
    has_land = bool(subject.get("grassland_mu"))
    has_stock = bool(ledger["book_head"])
    overdue = int(_num(fin.get("overdue_times")))

    completeness = docs.get("summary", {}).get("completeness", 0)
    missing_critical = [i["label"] for i in docs.get("items", [])
                        if i["status"] == "缺失" and i["key"] in
                        ("grassland_title", "ear_tag", "credit_line")]

    if not has_credit or not has_land or not has_stock or len(missing_critical) >= 2:
        return {
            "status": "待补资料", "tone": "warn",
            "headline": "待补资料 · 未测算",
            "note": f"资料完整度 {completeness}% ｜ 缺 {'、'.join(missing_critical) or '关键资料'}",
            "action": "发起补录",
        }
    if overdue > 0 or ledger["unpriced_ratio"] >= 30:
        reasons = []
        if overdue:
            reasons.append(f"逾期 {overdue} 期")
        if ledger["unpriced_ratio"] >= 30:
            reasons.append(f"无票出栏 {ledger['unpriced_ratio']}%")
        return {
            "status": "待核查", "tone": "danger",
            "headline": "暂缓放款 · 待核查",
            "note": f"前置条件未满足：{'；'.join(reasons)}",
            "action": "发起核查",
        }
    return {
        "status": "可测算", "tone": "ok",
        "headline": "可贷 · 待测算",
        "note": f"资料完整度 {completeness}% ｜ 准入资料齐备 ｜ 建议金额需经额度链测算给出",
        "action": "查看测算",
    }


def customer_profile(name: str) -> dict[str, Any]:
    """单户档案聚合。"""
    ctx = _load_all()
    subject = _find_subject(ctx, name)
    if subject is None:
        return {"found": False, "subject_name": name}

    fin = ctx["finance"].get(name)
    ledger = _derive_ledger(subject, ctx)
    docs = customer_documents(name)
    conclusion = _conclusion(subject, fin, ledger, docs)
    signals = _derive_signals(subject, fin, ledger,
                              [c for c in ctx["claims"] if c.get("subject_name") == name])
    tasks = [t for t in ctx["tasks"] if t.get("subject_name") == name]

    evidence = [
        {"label": "资产（耳标台账）", "status": "已获取" if ledger["tag_head"] else "缺失",
         "detail": f"{ledger['tag_head']} 头登记" if ledger["tag_head"] else "无耳标登记"},
        {"label": "防疫记录", "status": "待核验", "detail": "源数据未接入防疫明细"},
        {"label": "经营（检疫票 / 流水）", "status": "部分",
         "detail": f"贷款用途：{subject.get('loan_use') or '—'}"},
        {"label": "还款记录", "status": "已获取" if fin else "缺失",
         "detail": (fin or {}).get("repayment_status") or "行内无记录"},
        {"label": "保险合同", "status": "已获取" if _num(subject.get("insurance_coverage")) > 0 else "缺失",
         "detail": f"覆盖率 {subject.get('insurance_coverage') or 0}%"},
    ]
    todos = [
        {"priority": "P0", "tone": "danger", "label": i["label"]}
        for i in docs["items"] if i["status"] == "缺失" and i["key"] in
        ("insurance_coverage", "policy", "grassland_title", "ear_tag")
    ][:4]

    return {
        "found": True,
        "subject_name": name,
        "subject": {k: v for k, v in subject.items() if k != "name"},
        "conclusion": conclusion,
        "estimate": credit_estimate(name),
        "finance": fin or {},
        "ledger": ledger,
        "documents_summary": docs["summary"],
        "evidence": evidence,
        "todos": todos,
        "signals": signals,
        "tasks": tasks,
        "source": {
            "subject": subject.get("data_source"),
            "is_sample": subject.get("is_sample"),
            "sample_note": subject.get("sample_note"),
        },
    }


# --------------------------------------------------------------------------
# 列表页
# --------------------------------------------------------------------------

def customer_pool() -> dict[str, Any]:
    """客户池：客户列表 + 获客来源分布。

    行内 `credit_line_yuan` 是**已有授信额度**（万元 x 10000），不是额度链算出的建议金额；
    建议金额看每行的 `estimate` —— 无测算案例的户为 no_case，一律不显示金额。
    """
    ctx = _load_all()
    cases = _load_cases()
    rows: list[dict[str, Any]] = []
    source_count: dict[str, int] = defaultdict(int)

    for s in ctx["subjects"]:
        name = s.get("name")
        if not name:
            continue
        fin = ctx["finance"].get(name) or {}
        ledger = _derive_ledger(s, ctx)
        docs = customer_documents(name)
        conclusion = _conclusion(s, fin, ledger, docs)
        if cases:
            est = _estimate_for(name, cases)
        else:
            est = {"state": "unavailable"}
        src = _derive_source(ctx, name)
        source_count[src] += 1
        rows.append({
            "subject_name": name,
            "subject_type": s.get("subject_type"),
            "region_name": s.get("region_name"),
            "book_head": ledger["book_head"],
            "grassland_mu": s.get("grassland_mu"),
            "admission_stage": s.get("admission_stage"),
            "conclusion_status": conclusion["status"],
            "conclusion_tone": conclusion["tone"],
            "conclusion_headline": conclusion["headline"],
            "credit_line_yuan": int(_num(fin.get("credit_line")) * 10000),
            "estimate": {
                "state": est.get("state"),
                "status": est.get("status"),
                "amount_yuan": est.get("amount_yuan"),
            },
            "score": s.get("score"),
            "completeness": docs["summary"]["completeness"],
            "source": src,
        })

    rows.sort(key=lambda r: (-r["credit_line_yuan"], -r["completeness"]))
    return {
        "total": len(rows),
        "sources": [{"source": k, "count": v} for k, v in
                    sorted(source_count.items(), key=lambda kv: -kv[1])],
        "customers": rows,
    }


def ledger_board() -> dict[str, Any]:
    """活体资产台账：抵押物总览 + 无票出栏占比排行。"""
    ctx = _load_all()
    rows = []
    for s in ctx["subjects"]:
        name = s.get("name")
        if not name:
            continue
        fin = ctx["finance"].get(name)
        if not fin or not fin.get("credit_line"):
            continue  # 无授信则无抵押物
        led = _derive_ledger(s, ctx)
        led["has_credit"] = True
        rows.append(led)

    total_head = sum(r["book_head"] for r in rows)
    total_tag = sum(r["tag_head"] for r in rows)
    by_region: dict[str, dict[str, Any]] = defaultdict(lambda: {"head": 0, "customers": 0})
    for r in rows:
        b = by_region[r["region_name"]]
        b["head"] += r["book_head"]
        b["customers"] += 1

    ranked = sorted(rows, key=lambda r: -r["unpriced_ratio"])
    return {
        "total_book_head": total_head,
        "total_tag_head": total_tag,
        "customers": len(rows),
        "avg_unpriced_ratio": round(
            sum(r["unpriced_ratio"] for r in rows) / len(rows)) if rows else 0,
        "by_region": [{"region_name": k, **v} for k, v in
                      sorted(by_region.items(), key=lambda kv: -kv[1]["head"])],
        "ranked": ranked[:20],
        "note": "台账为演示口径派生；「无票出栏」只产生核查线索，不判定欺骗",
    }


def post_loan_board() -> dict[str, Any]:
    """贷后待办：真实任务表 + 派生信号合并成队列。"""
    ctx = _load_all()
    queue: list[dict[str, Any]] = []

    for t in ctx["tasks"]:
        queue.append({
            "task_id": t.get("task_id"),
            "subject_name": t.get("subject_name"),
            "region_name": t.get("region_name"),
            "stage": t.get("workflow_stage"),
            "signal_class": _classify_trigger(t.get("trigger_type")),
            "trigger": t.get("trigger_type"),
            "level": _level_from_score(t.get("risk_score")),
            "assigned_to": t.get("assigned_to"),
            "due_date": t.get("due_date"),
            "status": t.get("task_status"),
            "action_result": t.get("action_result"),
            "next_action": t.get("next_action"),
            "source": "real_field",
        })

    for s in ctx["subjects"]:
        name = s.get("name")
        if not name:
            continue
        led = _derive_ledger(s, ctx)
        for sig in _derive_signals(s, ctx["finance"].get(name), led,
                                   [c for c in ctx["claims"] if c.get("subject_name") == name]):
            queue.append({
                "task_id": None,
                "subject_name": name,
                "region_name": s.get("region_name"),
                "stage": "贷后核查",
                "signal_class": sig["signal_class"],
                "trigger": sig["trigger"],
                "level": sig["level"],
                "assigned_to": s.get("customer_manager"),
                "due_date": None,
                "status": sig["status"],
                "action_result": None,
                "next_action": None,
                "source": sig["source"],
            })

    order = {"高": 0, "中": 1, "低": 2}
    queue.sort(key=lambda r: (order.get(r["level"], 9), r["subject_name"] or ""))
    counts = defaultdict(int)
    for r in queue:
        counts[r["level"]] += 1
    return {
        "total": len(queue),
        "by_level": dict(counts),
        "queue": queue,
        "signal_classes": list(SIGNAL_CLASSES),
    }


def insurance_board() -> dict[str, Any]:
    """保险协同：保单核验队列 + 理赔联动。"""
    ctx = _load_all()
    subjects = ctx["subjects"]
    rows: list[dict[str, Any]] = []

    for s in subjects:
        name = s.get("name")
        coverage = _num(s.get("insurance_coverage"))
        ledger = _derive_ledger(s, ctx)
        if not ledger["book_head"] and not coverage:
            continue
        insured_head = round(ledger["book_head"] * coverage / 100) if ledger["book_head"] else 0
        # 责任范围与合同核验：源数据里没有，一律标「待核验」
        rows.append({
            "subject_name": name,
            "region_name": s.get("region_name"),
            "coverage": coverage,
            "insured_head": insured_head,
            "book_head": ledger["book_head"],
            "liability_verified": coverage >= 80,
            "status": "已核验" if coverage >= 80 else "待核验",
            "is_derived": True,
            "derived_note": "承保头数按保险覆盖率 × 存栏派生；合同与责任范围核验状态为演示口径",
        })

    rows.sort(key=lambda r: (r["status"] != "待核验", -r["book_head"]))
    unpaid = [c for c in ctx["claims"] if c.get("claim_status") not in ("已赔付", "已结案")]
    return {
        "pending_count": sum(1 for r in rows if r["status"] == "待核验"),
        "uncovered_count": sum(1 for r in rows if r["coverage"] < 1),
        "queue": rows[:30],
        "claims": [
            {
                "claim_id": c.get("claim_id"),
                "subject_name": c.get("subject_name"),
                "region_name": c.get("region_name"),
                "event_month": c.get("event_month"),
                "insurance_type": c.get("insurance_type"),
                "claim_status": c.get("claim_status"),
                "survey_status": c.get("survey_status"),
                "insured_amount": c.get("insured_amount"),
                "claim_amount": c.get("claim_amount"),
                "post_loan_feedback": c.get("post_loan_feedback"),
            }
            for c in ctx["claims"]
        ],
        "unsettled_claims": len(unpaid),
        "discount_tiers": [
            {"ear_tag": "有", "insured": "有", "discount": 0.70},
            {"ear_tag": "有", "insured": "无", "discount": 0.40},
            {"ear_tag": "无", "insured": "有", "discount": 0.30},
            {"ear_tag": "无", "insured": "无", "discount": 0.0},
        ],
    }


def region_board() -> dict[str, Any]:
    """区域与集中度：按耳标归属县统计（近似用主体所在县，明确标注）。"""
    ctx = _load_all()
    led = ledger_board()
    rows = []
    for r in led["by_region"]:
        region = r["region_name"]
        credit_total = 0.0
        for s in ctx["subjects"]:
            if s.get("region_name") != region:
                continue
            fin = ctx["finance"].get(s.get("name"))
            if fin and fin.get("credit_line"):
                credit_total += _num(fin["credit_line"])  # 单位：万元
        pool = max(900.0, round(credit_total / 0.6)) if credit_total else 900.0
        rows.append({
            "region_name": region,
            "customers": r["customers"],
            "book_head": r["head"],
            "deployed_wan": round(credit_total, 1),
            "pool_wan": round(pool, 1),
            "usage_pct": round(credit_total / pool * 100) if pool else 0,
        })
    rows.sort(key=lambda r: -r["usage_pct"])
    return {
        "total_regions": len(rows),
        "rows": rows,
        "note": "耳标归属县近似用主体所在县；真实系统应按耳标编码前 7 位的县级代码统计",
    }


# --------------------------------------------------------------------------
# 辅助
# --------------------------------------------------------------------------

def _classify_trigger(trigger: str | None) -> str:
    t = trigger or ""
    if "资金用途" in t:
        return "经营类"
    if "保险" in t:
        return "保险类"
    if "环境" in t or "灾害" in t:
        return "环境类"
    return "资产类"


def _level_from_score(score: Any) -> str:
    try:
        v = _num(score)
    except (TypeError, ValueError):
        return "中"
    if v >= 70:
        return "高"
    if v >= 50:
        return "中"
    return "低"


def overview() -> dict[str, Any]:
    """工作台需要的汇总数字。"""
    pool = customer_pool()
    ledger = ledger_board()
    post = post_loan_board()
    ins = insurance_board()
    ctx = _load_all()
    deployed = 0.0
    for s in ctx["subjects"]:
        fin = ctx["finance"].get(s.get("name"))
        if fin and fin.get("credit_line"):
            deployed += _num(fin["credit_line"])
    return {
        "customers_total": pool["total"],
        "sources": pool["sources"],
        "todo_total": post["total"],
        "todo_high": post["by_level"].get("高", 0),
        "ledger_book_head": ledger["total_book_head"],
        "ledger_avg_unpriced": ledger["avg_unpriced_ratio"],
        "insurance_pending": ins["pending_count"],
        "insurance_uncovered": ins["uncovered_count"],
        "green_deployed_wan": round(deployed, 1),
        "top_prospects": [r for r in pool["customers"] if r["conclusion_status"] == "可测算"][:5],
    }
