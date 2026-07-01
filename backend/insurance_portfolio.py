"""
牧融绿链 - 保单画像与增信评分模块
============================================================================
基于百巴村1135条真实保单数据（21户牧民），提供：

1. 百巴村畜牧产业画像 — 统计汇总
2. 农户级增信评分 — 规则评分（非ML），评估保险兜底能力
3. 银保协同场景 — 农行承保→工行放贷的风险对冲逻辑
4. 环境风险联动 — 调用现有linzhi-bayi风险评估

增信评分逻辑：
  保险是增信因子（高覆盖=低风险），不是风险因子
  牧民有牦牛保险 → 牲畜死亡农行赔 → 工行贷款有兜底 → 工行风险降低

评分规则（规则评分，可解释）：
  基础分 60（有保险即加分）
  + 规模分 0-25（投保头数越多→保险兜底越充分）
  + 连续性分 0-15（耳标批次数代理投保连续性）
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
    """规模分（0-25）：投保头数越多，保险兜底越充分。"""
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
    """连续性分（0-15）：用耳标批次数代理投保连续性。

    没有投保日期，但耳标号前缀可能对应不同投保批次。
    批次越多→可能多年投保→连续性好→还款意愿强。
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
    """授信建议（基于增信分）。"""
    if credit_score >= 85:
        return {
            "level": "优质",
            "suggested_amount": "30-50万元",
            "advice": "保险兜底充分，规模较大，建议优先授信",
        }
    if credit_score >= 70:
        return {
            "level": "良好",
            "suggested_amount": "15-30万元",
            "advice": "保险覆盖较好，可正常授信",
        }
    if credit_score >= 60:
        return {
            "level": "一般",
            "suggested_amount": "5-15万元",
            "advice": "保险覆盖一般，建议适度授信",
        }
    return {
        "level": "谨慎",
        "suggested_amount": "建议人工复核",
        "advice": "保险覆盖不足或信息缺失，建议人工核实后决定",
    }


def _compute_farmer_score(farmer: dict) -> dict[str, Any]:
    """计算单户增信评分。"""
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
    """21户农户增信评分列表。"""
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
    """银保协同场景数据。

    场景：农行承保1135头牦牛 → 工行放贷给21户牧民
    保险兜底逻辑：牲畜死亡→农行理赔→工行贷款有保障
    """
    data = _load_policies()
    profile = data.get("profile", {})
    farmers = data.get("farmers", [])

    total_cattle = profile.get("total_cattle", 0)
    farmer_count = profile.get("farmer_count", 0)

    # 保险兜底能力评估
    # 假设：每头牦牛保险金额约3000元（藏系牦牛市场价参考）
    # 保险兜底总额 = 总头数 × 每头保额
    per_cattle_insurance = 3000
    total_insurance_coverage = total_cattle * per_cattle_insurance

    # 工行风险敞口缩减
    # 假设：每户平均贷款20万，21户总贷款420万
    # 保险兜底340.5万 → 工行风险敞口缩减约81%
    avg_loan = 200000
    total_loan = farmer_count * avg_loan
    risk_reduction_pct = round(
        min(100, total_insurance_coverage / total_loan * 100), 1
    ) if total_loan > 0 else 0

    # 农户级增信统计
    scored_farmers = get_farmers()
    level_dist = {}
    for f in scored_farmers:
        level = f.get("credit_level", "一般")
        level_dist[level] = level_dist.get(level, 0) + 1

    return {
        "scenario": "农行承保 → 工行放贷 → 保险兜底",
        "insurance_bank": "中国农业银行",
        "lending_bank": "中国工商银行",
        "livestock_type": "藏系牦牛",
        "total_cattle_insured": total_cattle,
        "farmer_count": farmer_count,
        "per_cattle_insurance_amount": per_cattle_insurance,
        "total_insurance_coverage": total_insurance_coverage,
        "estimated_total_loan": total_loan,
        "risk_reduction_pct": risk_reduction_pct,
        "synergy_logic": [
            "农行为1135头牦牛承保养殖险",
            "工行为21户牧民提供牦牛养殖贷款",
            "牲畜因灾死亡时，农行保险理赔 → 牧民有资金偿还工行贷款",
            "保险兜底使工行贷款风险敞口缩减约{}%".format(risk_reduction_pct),
        ],
        "credit_level_distribution": level_dist,
        "summary": (
            f"百巴村{farmer_count}户牧民的{total_cattle}头牦牛已由农行承保，"
            f"保险兜底总额约{total_insurance_coverage/10000:.1f}万元，"
            f"可使工行放贷风险敞口缩减约{risk_reduction_pct}%。"
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
                    "note": "基于现有ML模型预测，与保险增信评分联动",
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
    """综合风险评估 = 环境风险 + 保险增信。

    输出百巴村综合风险画像，供工行客户经理参考。
    """
    env = get_environment_risk()
    synergy = get_synergy()

    env_score = env.get("risk_score")
    insurance_coverage_pct = synergy.get("risk_reduction_pct", 0)

    # 综合风险 = 环境风险 × (1 - 保险增信缩减比例)
    if env_score is not None:
        adjusted_risk = round(env_score * (1 - insurance_coverage_pct / 100))
        adjusted_risk = max(0, min(100, adjusted_risk))
    else:
        adjusted_risk = None

    return {
        "village": "百巴村",
        "environment_risk": env,
        "insurance_synergy": synergy,
        "comprehensive_risk_score": adjusted_risk,
        "comprehensive_risk_level": (
            "高" if adjusted_risk and adjusted_risk >= 70
            else "中" if adjusted_risk and adjusted_risk >= 50
            else "低" if adjusted_risk is not None
            else "未知"
        ),
        "conclusion": (
            f"环境风险{'未知' if env_score is None else env_score}分，"
            f"保险增信缩减{insurance_coverage_pct}%风险敞口，"
            f"综合风险{'未知' if adjusted_risk is None else adjusted_risk}分。"
        ),
    }
