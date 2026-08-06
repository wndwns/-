"""
牧融绿链 - 保单画像与增信评分模块
============================================================================
基于百巴村牦牛资产登记数据（21户牧民），提供：

1. 百巴村畜牧产业画像 — 统计汇总
2. 农户级资料评分 — 规则评分（非ML），评估资产登记和资料完整度
3. 银保协同核验清单 — 展示需要补齐的保险与授信事实
4. 环境风险联动 — 调用现有linzhi-bayi风险评估

增信评分逻辑：
  保险只能在合同、责任范围和理赔记录核验后作为增信因子
  当前数据只证明资产登记关系，不证明承保责任或贷款风险下降

评分规则（规则评分，可解释）：
  基础分 60（有资产登记即进入资料核验）
  + 规模分 0-25（登记头数）
  + 批次分 0-15（耳标批次，仅作资料线索）
  + 信息完整度 0-10（地址+手机）
  = 原始分 60-110 → 归一化到 0-100
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_STORE_DIR = Path(__file__).resolve().parent / "data_store"
_POLICY_PATH = _STORE_DIR / "insurance_policies.json"


def _load_policies() -> dict[str, Any]:
    """加载保单数据。"""
    if not _POLICY_PATH.exists():
        return {"profile": {}, "farmers": [], "policies": []}
    return json.loads(_POLICY_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 农户级增信评分
# ---------------------------------------------------------------------------

def _scale_score(herd_size: int) -> int:
    """规模分（0-25）：登记头数越多，资料核验范围越大。"""
    if herd_size >= 100:
        return 25
    if herd_size >= 50:
        return 20
    if herd_size >= 10:
        return 15
    if herd_size >= 5:
        return 10
    return 5


def _continuity_score(batch_count: int) -> int:
    """批次分（0-15）：用耳标批次数作为资料线索。

    没有投保日期，不能据此推断连续投保或还款意愿。
    """
    if batch_count >= 4:
        return 15
    if batch_count >= 3:
        return 12
    if batch_count >= 2:
        return 8
    return 5


def _completeness_score(has_address: bool, has_phone: bool) -> int:
    """信息完整度（0-10）。"""
    score = 0
    if has_address:
        score += 5
    if has_phone:
        score += 5
    return score


def _credit_suggestion(credit_score: int) -> dict[str, Any]:
    """资料核验建议；不输出授信金额或违约结论。"""
    if credit_score >= 85:
        return {
            "level": "优质",
            "suggested_amount": None,
            "advice": "资料完整度较高，可进入人工授信核验",
        }
    if credit_score >= 70:
        return {
            "level": "良好",
            "suggested_amount": None,
            "advice": "资料基本完整，补齐保险合同和授信事实后再评估",
        }
    if credit_score >= 60:
        return {
            "level": "一般",
            "suggested_amount": None,
            "advice": "存在资料缺口，建议先做人工核验",
        }
    return {
        "level": "谨慎",
        "suggested_amount": None,
        "advice": "资料缺失，不能据此做授信判断",
    }


def _compute_farmer_score(farmer: dict) -> dict[str, Any]:
    """计算单户资产登记和资料完整度分。"""
    herd = farmer.get("herd_size", 0)
    batches = farmer.get("ear_tag_batch_count", 0)
    has_addr = farmer.get("has_address", False)
    has_phone = farmer.get("has_phone", False)

    base = 60
    scale = _scale_score(herd)
    continuity = _continuity_score(batches)
    completeness = _completeness_score(has_addr, has_phone)

    raw = base + scale + continuity + completeness  # 60-110
    # 归一化到 0-100
    credit_score = round((raw - 60) / 50 * 100)
    credit_score = max(0, min(100, credit_score))

    suggestion = _credit_suggestion(credit_score)

    return {
        "credit_score": credit_score,
        "score_type": "asset_register_completeness",
        "score_note": "资料完整度和资产登记线索分，不是授信额度、违约概率或保险赔付能力",
        "score_breakdown": {
            "base": base,
            "scale": scale,
            "continuity": continuity,
            "completeness": completeness,
            "raw_total": raw,
        },
        "credit_level": suggestion["level"],
        "suggested_amount": suggestion["suggested_amount"],
        "advice": suggestion["advice"],
    }


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------

def get_profile() -> dict[str, Any]:
    """百巴村畜牧产业画像。"""
    data = _load_policies()
    return data.get("profile", {})


def get_farmers() -> list[dict[str, Any]]:
    """21户农户资料完整度列表。"""
    data = _load_policies()
    farmers = data.get("farmers", [])
    result = []
    for f in farmers:
        scored = dict(f)
        scored.update(_compute_farmer_score(f))
        result.append(scored)
    # 按增信分降序
    result.sort(key=lambda x: x.get("credit_score", 0), reverse=True)
    return result


def get_farmer_detail(farmer_id: str) -> dict[str, Any] | None:
    """单户详情。"""
    farmers = get_farmers()
    for f in farmers:
        if f.get("farmer_id") == farmer_id:
            return f
    return None


def get_synergy() -> dict[str, Any]:
    """银保协同核验清单。

    当前数据只支持资产登记和资料完整度展示，不能推导承保责任、贷款余额
    或风险下降比例。
    """
    data = _load_policies()
    profile = data.get("profile", {})
    farmers = data.get("farmers", [])

    total_cattle = profile.get("total_cattle", 0)
    farmer_count = profile.get("farmer_count", 0)

    # 农户级增信统计
    scored_farmers = get_farmers()
    level_dist = {}
    for f in scored_farmers:
        level = f.get("credit_level", "一般")
        level_dist[level] = level_dist.get(level, 0) + 1

    return {
        "scenario": "资产登记 → 保险合同核验 → 工行人工授信/贷后核查",
        "insurance_bank": None,
        "lending_bank": "中国工商银行",
        "livestock_type": "藏系牦牛",
        "total_cattle_insured": total_cattle,
        "farmer_count": farmer_count,
        "coverage_status": "unverified",
        "contract_fields_required": ["保险公司", "保单号", "保额", "保费", "保险期限", "责任范围", "理赔记录"],
        "loan_fields_required": ["授信主体", "贷款余额", "用信状态", "逾期记录", "资金用途"],
        "risk_reduction_pct": None,
        "synergy_logic": [
            "当前数据可核验21户主体与牦牛耳标登记关系",
            "需补齐保险合同字段后，才能判断保障范围和赔付能力",
            "需补齐真实授信与还款字段后，才能评估银保协同效果",
        ],
        "credit_level_distribution": level_dist,
        "summary": (
            f"当前可核验百巴村{farmer_count}户主体、{total_cattle}头牦牛的资产登记关系；"
            "保险责任和贷款风险缓释效果待合同与授信数据核验。"
        ),
    }


def get_environment_risk() -> dict[str, Any]:
    """环境风险联动 — 调用现有linzhi-bayi风险评估。

    复用现有模型，不新建ML。
    """
    try:
        from models import get_model
        model = get_model()
        if not model._trained:
            model.train()
        # 获取林芝巴宜区的风险预测
        predictions = model.predict()
        for p in predictions:
            if p.get("region_id") == "linzhi-bayi":
                return {
                    "region_id": "linzhi-bayi",
                    "region_name": "林芝市巴宜区",
                    "risk_score": p.get("score", 0),
                    "risk_level": p.get("level", "未知"),
                    "model_type": model._model_type,
                    "confidence": model._confidence,
                    "note": "基于现有ML模型的环境风险筛查，不直接决定授信",
                }
        return {
            "region_id": "linzhi-bayi",
            "note": "林芝巴宜区暂无环境风险数据（缺时序气象/遥感数据）",
            "risk_score": None,
        }
    except Exception as e:
        return {
            "error": str(e),
            "note": "环境风险联动调用失败",
        }


def get_comprehensive_risk() -> dict[str, Any]:
    """输出环境风险和资料核验结果；不把未经核验的保险数据折算成风险分。"""
    env = get_environment_risk()
    synergy = get_synergy()

    env_score = env.get("risk_score")
    return {
        "village": "百巴村",
        "environment_risk": env,
        "insurance_synergy": synergy,
        "comprehensive_risk_score": None,
        "comprehensive_risk_level": "需人工核验",
        "next_actions": [
            "核验环境风险对应的时间窗和来源",
            "补齐保险合同、责任范围和理赔记录",
            "补齐真实授信余额、还款和资金用途后再评估银保协同",
        ],
        "conclusion": (
            f"环境风险{'未知' if env_score is None else env_score}分仅用于筛查；"
            "当前资料不足以计算综合授信风险或保险减损比例。"
        ),
    }


def get_due_diligence_case() -> dict[str, Any]:
    """返回一个可追溯的客户经理人工核验案例。

    该输出只暴露聚合事实和数据状态，不返回姓名、电话、地址或耳标明细，
    也不把筛查结果转成授信、定价或拒贷结论。
    """
    data = _load_policies()
    profile = data.get("profile", {})
    farmers = get_farmers()
    environment = get_environment_risk()
    synergy = get_synergy()

    return {
        "case_id": "linzhi-bayi-baba-village",
        "case_title": "林芝巴宜区百巴村牧户资料核验",
        "decision_scope": "manual_due_diligence",
        "subject_snapshot": {
            "subject_count": profile.get("farmer_count", len(farmers)),
            "registered_cattle": profile.get("total_cattle", 0),
            "source": "asset_register",
            "privacy": "aggregated_only",
        },
        "evidence": [
            {
                "key": "asset_register",
                "status": "observed",
                "summary": "存在牧户与牦牛资产登记关系",
                "value": f"{profile.get('farmer_count', len(farmers))}户 / {profile.get('total_cattle', 0)}头",
                "source": "backend/data_store/insurance_policies.json",
            },
            {
                "key": "environment_screen",
                "status": "screening",
                "summary": "环境风险仅用于筛查和核查排序",
                "value": environment.get("risk_score"),
                "source": environment.get("model_type", "environment_screen"),
            },
            {
                "key": "insurance_contract",
                "status": "missing",
                "summary": "保险合同责任和理赔字段待核验",
                "required_fields": synergy.get("contract_fields_required", []),
            },
            {
                "key": "credit_record",
                "status": "missing_or_sample",
                "summary": "真实授信、余额、还款和资金用途待核验",
                "required_fields": synergy.get("loan_fields_required", []),
            },
        ],
        "recommended_actions": [
            "核验主体身份、资产登记和资料完整性",
            "核验保险合同、责任范围和历史理赔",
            "核验授信余额、还款状态和资金用途",
            "由客户经理人工决定后续授信或贷后动作",
        ],
        "not_supported": [
            "自动批准或拒绝授信",
            "计算保险风险减损比例",
            "用公开灾害事件替代完整理赔或逾期标签",
        ],
    }
