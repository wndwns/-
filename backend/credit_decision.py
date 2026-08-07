"""
工银牧融 - 唯一授信决策纯计算模块
============================================================================
职责：
  草场/储草分池守恒、牲畜月度干物质需求、必要饲草采购量与采购成本、
  融资前经营现金流、基准合格融资需求、标准雪灾偿债支持上限、
  唯一建议新增贷款金额、复合极端脆弱性、可行/暂不可行/资料不足判定。

边界：
  - 只公开 evaluate_credit_case() 一个入口。
  - 接收已完成基础校验的案例 dict 与本次试算输入，返回结构化结果。
  - 不读取/写入文件、不处理 HTTP、不依赖前端状态。
  - 不读取 RF/Ridge、四维综合分、旧风险乘数或保险覆盖率乘数。
  - 保险第一版不进入现金流、融资需求、偿债上限或建议金额。
  - 金额统一以元（Decimal）计算，仅在最后向下取整到 1 万元。

单位约定（方案 12.5）：
  金额 *_yuan；草场面积 *_mu；饲草重量 *_kg；比例 *_rate（0~1）。
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_DOWN
from typing import Any

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

MONTHS = [
    "2027-01", "2027-02", "2027-03", "2027-04", "2027-05", "2027-06",
    "2027-07", "2027-08", "2027-09", "2027-10", "2027-11", "2027-12",
]

# 每月天数（2027 年非闰年，2 月 28 天），用于存栏 × 日需求 → 月度需求
MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

_FLOOR_UNIT = Decimal("10000")

# 情景配置：压力月（1-based 索引）、需求系数、草场可达比例、到场价系数
SCENARIOS: dict[str, dict[str, Any]] = {
    "baseline": {
        "label": "基准情景",
        "pressure_months": [],
        "demand_factor": Decimal("1.00"),
        "reachability": Decimal("1.00"),
        "price_factor": Decimal("1.00"),
    },
    "snow": {
        "label": "标准雪灾情景",
        "pressure_months": [1, 2],
        "demand_factor": Decimal("1.10"),
        "reachability": Decimal("0.70"),
        "price_factor": Decimal("1.15"),
    },
    "composite": {
        "label": "复合极端情景",
        "pressure_months": [1, 2, 12],
        "demand_factor": Decimal("1.20"),
        "reachability": Decimal("0.50"),
        "price_factor": Decimal("1.30"),
    },
}


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _dec(value: Any, default: str = "0") -> Decimal:
    """安全转换为 Decimal。None / 空字符串使用默认值。"""
    if value is None:
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError):
        return Decimal(default)


def _floor_to_10000(value: Decimal) -> Decimal:
    """向下取整到 1 万元（金额主链只在最后调用一次）。"""
    return (value / _FLOOR_UNIT).quantize(Decimal("1"), rounding=ROUND_DOWN) * _FLOOR_UNIT


def _effective_factor(
    case: dict[str, Any],
    key: str,
    month_index_1: int,
    pressure_months: list[int],
    scenario_value: Decimal,
) -> Decimal:
    """情景系数：非压力月为 1.0，压力月使用情景值。"""
    baseline = Decimal(case.get("scenarios", {}).get("baseline", {}).get(key, "1"))
    if month_index_1 not in pressure_months:
        return baseline
    return scenario_value


# ---------------------------------------------------------------------------
# 月度草畜与采购
# ---------------------------------------------------------------------------

def _monthly_plan(case: dict[str, Any], scenario_key: str) -> dict[str, Any]:
    """按情景计算逐月需求、草场供给、缺口、采购量、采购成本。

    草场与储草分池守恒（方案 7.4）：
      - 草场池：当月新增（含可达比例）→ 放牧采食（不超过需求）→ 剩余自储转入储草池。
      - 储草池：期初储草 + 自储转入 + 采购到货 - 补饲出库，不得为负。
      - 采购：基准采购计划到货 + 压力月因需求/可达变化新增的必要采购。
    期末保留安全储草，任一池不为负。
    """
    scenarios = case.get("scenarios", {})
    sc = scenarios.get(scenario_key, SCENARIOS[scenario_key])
    pressure_months = list(sc.get("pressure_months", []))
    demand_factor = _dec(sc.get("demand_factor"), "1")
    reachability = _dec(sc.get("reachability"), "1")
    price_factor = _dec(sc.get("price_factor"), "1")

    pasture = case["pasture"]
    base_demand = case.get("monthly_demand_kg") or case["livestock"].get("monthly_demand_kg") or []
    base_growth = case.get("monthly_pasture_growth_kg") or pasture.get("monthly_growth_kg") or []
    base_arrival = case.get("procurement", {}).get("base_arrival_kg", {})
    base_price = _dec(case.get("procurement", {}).get("base_price_yuan_per_kg"), "0")

    initial_storage = _dec(pasture.get("initial_storage_kg"), "0")
    safety_storage = _dec(pasture.get("safety_storage_kg"), "0")
    reference_mu = _dec(pasture.get("monthly_growth_reference_total_mu"), "0")
    total_mu = _dec(pasture.get("total_mu"), "0")
    growth_scale = total_mu / reference_mu if reference_mu > 0 else Decimal("1")

    storage = initial_storage
    pasture_balance = Decimal("0")

    total_demand = Decimal("0")
    total_pasture = Decimal("0")
    total_purchase_kg = Decimal("0")
    total_purchase_cost = Decimal("0")

    rows: list[dict[str, Any]] = []
    for i, month in enumerate(MONTHS):
        m1 = i + 1
        base_d = _dec(base_demand[i], "0")
        base_g = _dec(base_growth[i], "0") * growth_scale
        d_factor = _effective_factor(case, "demand_factor", m1, pressure_months, demand_factor)
        r_factor = _effective_factor(case, "reachability", m1, pressure_months, reachability)
        p_factor = _effective_factor(case, "price_factor", m1, pressure_months, price_factor)

        demand = base_d * d_factor
        growth = base_g * r_factor
        total_demand += demand
        total_pasture += growth

        # 草场池：当月新增进入，放牧采食不超过需求
        pasture_balance += growth
        graze = min(pasture_balance, demand)
        pasture_balance -= graze
        gap = demand - graze

        # 草场剩余自储转入储草池（6-9 月典型场景）
        if pasture_balance > 0:
            storage += pasture_balance
            pasture_balance = Decimal("0")

        # 固定到货与情景增量先入库；若仍有当月缺口，则补充必要采购。
        planned = _dec(base_arrival.get(month, 0), "0")
        demand_inc = base_d * (d_factor - Decimal("1"))
        pasture_dec = base_g * (Decimal("1") - r_factor)
        scenario_extra = max(Decimal("0"), demand_inc + pasture_dec)
        purchase_kg = planned + scenario_extra
        price = base_price * p_factor

        storage += purchase_kg
        shortfall_purchase = max(Decimal("0"), gap - storage)
        storage += shortfall_purchase
        purchase_kg += shortfall_purchase
        supplement = min(storage, gap)
        storage -= supplement
        unmet_forage = gap - supplement

        # 期末安全库存不足时，显式形成当月必要采购。
        safety_replenishment = Decimal("0")
        if i == len(MONTHS) - 1 and storage < safety_storage:
            safety_replenishment = safety_storage - storage
            storage += safety_replenishment
            purchase_kg += safety_replenishment

        purchase_cost = purchase_kg * price
        total_purchase_kg += purchase_kg
        total_purchase_cost += purchase_cost

        rows.append({
            "month": month,
            "demand_kg": demand,
            "pasture_growth_kg": growth,
            "graze_kg": graze,
            "forage_gap_kg": unmet_forage,
            "grazing_gap_kg": gap,
            "storage_supplement_kg": supplement,
            "storage_balance_kg": storage,
            "purchase_kg": purchase_kg,
            "purchase_price_yuan_per_kg": price,
            "purchase_cost_yuan": purchase_cost,
        })

    return {
        "scenario": scenario_key,
        "rows": rows,
        "total_demand_kg": total_demand,
        "total_pasture_supply_kg": total_pasture,
        "total_purchase_kg": total_purchase_kg,
        "total_purchase_cost_yuan": total_purchase_cost,
        "ending_storage_kg": storage,
        "safety_storage_kg": safety_storage,
        "pasture_growth_scale": growth_scale,
        "storage_balanced": storage >= safety_storage and all(r["forage_gap_kg"] == 0 for r in rows),
    }


# ---------------------------------------------------------------------------
# 月度现金流（融资前 + 融资后）
# ---------------------------------------------------------------------------

def _loan_schedule(case: dict[str, Any], principal: Decimal, months: list[str]) -> dict[str, Any]:
    """生成一笔贷款的逐月提款、利息、还本和余额。

    结构来自案例 product / debt 配置：
      draw_plan:  {month: 提款比例}
      repay_plan: {month: 还本比例}
    月利率 = 年利率 / 12，利息按余额计算（先提款、再计息、月末还本）。
    存量贷款无提款计划时，视为期初已全额提款（初始余额 = 本金）。
    """
    rate_annual = _dec(case.get("annual_rate"), "0")  # 4.20% 场景用 0.042 传入
    monthly_rate = rate_annual / Decimal("12")
    draw_plan = case.get("draw_plan", {})
    repay_plan = case.get("repay_plan", {})

    balance = Decimal("0")
    if not draw_plan:
        balance = principal
    rows = []
    total_interest = Decimal("0")
    for month in months:
        drawn = principal * _dec(draw_plan.get(month, 0), "0")
        # 先提款，再按提款后余额计息，最后月末还本（与 _service_factor 保持一致）
        balance += drawn
        interest = balance * monthly_rate
        repaid = principal * _dec(repay_plan.get(month, 0), "0")
        balance -= repaid
        if balance < 0:
            balance = Decimal("0")
        total_interest += interest
        rows.append({
            "month": month,
            "drawn_yuan": drawn,
            "interest_yuan": interest,
            "repaid_yuan": repaid,
            "ending_balance_yuan": balance,
        })
    service = principal + total_interest
    return {"rows": rows, "total_interest_yuan": total_interest, "total_service_yuan": service}


def _run_cashflow(case: dict[str, Any], candidate: Decimal, scenario_key: str) -> dict[str, Any]:
    """逐月现金流：融资前（不含新增提款）与融资后（含候选新增贷款）。

    融资前月末现金 = 月初现金 + 非饲草非债务净经营现金 - 采购付款 - 存量本息
    新增贷款提款不计入可用于偿债的经营现金，只进入融资后现金余额。
    """
    plan = _monthly_plan(case, scenario_key)
    non_forage = case.get("monthly_non_forage_net_cash_yuan") or case["operating"].get("monthly_net_cash_yuan") or []
    initial_cash = _dec(case["operating"].get("initial_cash_yuan"), "0")
    min_reserve = _dec(case["operating"].get("minimum_cash_reserve_yuan"), "0")

    existing_principal = _dec(case["debt"].get("existing_loan_yuan"), "0")
    existing_schedule = _loan_schedule(
        {
            **case,
            "annual_rate": case["debt"].get("annual_rate"),
            "draw_plan": {},  # 存量贷款期初已全额提款，无新增提款计划
            "repay_plan": case["debt"].get("repay_plan", {}),
        },
        existing_principal,
        MONTHS,
    )
    new_schedule = _loan_schedule(case, candidate, MONTHS)

    cash_pre = initial_cash
    cash_post = initial_cash
    month_rows = []
    for i, month in enumerate(MONTHS):
        net = _dec(non_forage[i], "0")
        purchase_cost = plan["rows"][i]["purchase_cost_yuan"]
        ex_int = existing_schedule["rows"][i]["interest_yuan"]
        ex_repay = existing_schedule["rows"][i]["repaid_yuan"]
        new_int = new_schedule["rows"][i]["interest_yuan"]
        new_repay = new_schedule["rows"][i]["repaid_yuan"]
        new_drawn = new_schedule["rows"][i]["drawn_yuan"]

        cash_pre += net - purchase_cost - ex_int - ex_repay

        cash_post += net - purchase_cost - ex_int - ex_repay - new_int - new_repay + new_drawn

        month_rows.append({
            "month": month,
            "non_forage_net_cash_yuan": net,
            "purchase_cost_yuan": purchase_cost,
            "existing_interest_yuan": ex_int,
            "existing_repayment_yuan": ex_repay,
            "new_loan_interest_yuan": new_int,
            "new_loan_repayment_yuan": new_repay,
            "new_loan_draw_yuan": new_drawn,
            "cash_before_financing_yuan": cash_pre,
            "cash_after_financing_yuan": cash_post,
            "loan_balance_yuan": existing_schedule["rows"][i]["ending_balance_yuan"]
            + new_schedule["rows"][i]["ending_balance_yuan"],
        })

    pre_cash_values = [r["cash_before_financing_yuan"] for r in month_rows]
    post_cash_values = [r["cash_after_financing_yuan"] for r in month_rows]
    min_post_idx = min(range(len(post_cash_values)), key=lambda k: post_cash_values[k])
    peak_balance = max(r["loan_balance_yuan"] for r in month_rows)

    return {
        "scenario": scenario_key,
        "monthly_rows": month_rows,
        "min_cash_yuan": post_cash_values[min_post_idx],
        "min_cash_month": MONTHS[min_post_idx],
        "min_pre_cash_yuan": min(pre_cash_values),
        "peak_loan_balance_yuan": peak_balance,
        "existing_service_yuan": existing_schedule["total_service_yuan"],
        "new_loan_interest_yuan": new_schedule["total_interest_yuan"],
        "new_loan_service_yuan": new_schedule["total_service_yuan"],
        "minimum_cash_reserve_yuan": min_reserve,
    }


def _service_factor(case: dict[str, Any]) -> Decimal:
    """候选新增贷款本息系数（本息合计 / 本金），由提款/还本/利率结构决定。"""
    rate_annual = _dec(case.get("annual_rate"), "0")
    monthly_rate = rate_annual / Decimal("12")
    draw_plan = case.get("draw_plan", {})
    repay_plan = case.get("repay_plan", {})
    balance = Decimal("0")
    interest = Decimal("0")
    for month in MONTHS:
        balance += _dec(draw_plan.get(month, 0), "0")
        interest += balance * monthly_rate
        balance -= _dec(repay_plan.get(month, 0), "0")
    return Decimal("1") + interest


# ---------------------------------------------------------------------------
# 唯一金额链
# ---------------------------------------------------------------------------

def _benchmark_qualified_demand(case: dict[str, Any]) -> dict[str, Any]:
    """基准情景合格融资需求 = 必要采购最低外部资金。"""
    base_plan = _monthly_plan(case, "baseline")
    purchase_total = base_plan["total_purchase_cost_yuan"]
    own_funds = _dec(case["operating"].get("own_purchase_funds_yuan"), "0")
    subsidy = _dec(case["operating"].get("confirmed_subsidy_yuan"), "0")
    min_external = max(Decimal("0"), purchase_total - own_funds - subsidy)
    return {
        "purchase_total_yuan": purchase_total,
        "own_funds_yuan": own_funds,
        "confirmed_subsidy_yuan": subsidy,
        "min_external_financing_yuan": min_external,
        "qualified_demand_yuan": min_external,
    }


def _affordable_limits(case: dict[str, Any]) -> dict[str, Any]:
    """标准雪灾偿债支持上限 + 其他授信约束（统一授信可用、产品上限、增信支持）。"""
    snow_plan = _monthly_plan(case, "snow")
    available_cash = Decimal("0")
    non_forage = case.get("monthly_non_forage_net_cash_yuan") or case["operating"].get("monthly_net_cash_yuan") or []
    for i in range(len(MONTHS)):
        available_cash += _dec(non_forage[i], "0")
    available_cash -= snow_plan["total_purchase_cost_yuan"]

    dscr_threshold = _dec(case["credit"].get("dscr_threshold"), "0")
    existing_principal = _dec(case["debt"].get("existing_loan_yuan"), "0")
    existing_schedule = _loan_schedule(
        {
            **case,
            "annual_rate": case["debt"].get("annual_rate"),
            "draw_plan": {},
            "repay_plan": case["debt"].get("repay_plan", {}),
        },
        existing_principal,
        MONTHS,
    )
    existing_service = existing_schedule["total_service_yuan"]
    factor = _service_factor(case)

    if dscr_threshold > 0 and factor > 0:
        snow_support = (available_cash / dscr_threshold - existing_service) / factor
        snow_support = max(snow_support, Decimal("0"))
    else:
        snow_support = Decimal("0")

    unified_total = _dec(case["credit"].get("unified_total_yuan"), "0")
    used = _dec(case["credit"].get("used_yuan"), "0")
    credit_available = max(Decimal("0"), unified_total - used)
    product_cap = _dec(case["credit"].get("product_cap_yuan"), "0")

    collateral_support = case["credit"].get("collateral_support_yuan")
    collateral_applicable = isinstance(collateral_support, (int, float)) or (
        isinstance(collateral_support, str) and collateral_support.strip().lower() not in ("", "n/a", "na", "none", "不适用")
    )
    collateral_value = _dec(collateral_support, "0") if collateral_applicable else None

    candidates = [snow_support, credit_available, product_cap]
    labels = ["标准雪灾偿债支持上限", "统一授信可用额度", "样例产品上限"]
    if collateral_value is not None:
        candidates.append(collateral_value)
        labels.append("保证/抵质押支持上限")
    affordable = min(candidates)
    bottleneck = labels[candidates.index(affordable)]

    return {
        "snow_available_cash_yuan": available_cash,
        "snow_support_limit_yuan": snow_support,
        "dscr_threshold": dscr_threshold,
        "credit_available_yuan": credit_available,
        "product_cap_yuan": product_cap,
        "collateral_support_yuan": collateral_support,
        "collateral_applicable": collateral_applicable,
        "affordable_limit_yuan": affordable,
        "bottleneck": bottleneck,
    }


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def evaluate_credit_case(case: dict[str, Any], inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    """唯一授信决策主入口。

    Args:
        case: 基础案例 dict（已完成基础校验，来自 credit_cases.json）。
        inputs: 本次试算输入，覆盖案例默认值（不持久化）。

    Returns:
        结构化测算结果 dict。
    """
    if not isinstance(case, dict) or not case:
        return {
            "status": "blocked",
            "reason": "案例数据缺失",
            "missing_materials": ["主体基础案例数据"],
            "recommended_amount_yuan": None,
            "message": "缺少完成测算所需的主体资料。",
        }

    # 资料不足（blocked）案例
    if case.get("blocked"):
        return {
            "status": "blocked",
            "reason": case.get("blocked_reason", "关键资料缺失"),
            "missing_materials": list(case.get("missing_materials", [])),
            "recommended_amount_yuan": None,
            "message": case.get("blocked_message", "缺少完成测算所需的主体资料。"),
        }

    # 合并本次试算输入（不修改原案例）
    ctx = deepcopy(case)
    if inputs:
        for section, fields in inputs.items():
            if isinstance(fields, dict) and isinstance(ctx.get(section), dict):
                ctx[section].update(fields)
            else:
                ctx[section] = fields

    # 准入检查：关键经营/融资资料
    missing = _check_gate(ctx)
    if missing:
        return {
            "status": "blocked",
            "reason": "关键资料缺失或还款状态异常",
            "missing_materials": missing,
            "recommended_amount_yuan": None,
            "message": "缺少完成测算所需的主体资料，当前不进入金额计算。",
        }

    qualified = _benchmark_qualified_demand(ctx)
    limits = _affordable_limits(ctx)
    min_external = qualified["min_external_financing_yuan"]
    affordable = limits["affordable_limit_yuan"]

    # 唯一金额：先精确比较，最后向下取整到 1 万元
    pre_round = min(qualified["qualified_demand_yuan"], affordable)
    floor_amount = _floor_to_10000(pre_round)

    if affordable < min_external or floor_amount < min_external:
        # 暂不可行：按实际可放的取整金额计算缺口，不输出正的推荐金额。
        status = "infeasible"
        candidate = floor_amount
        gap = max(Decimal("0"), min_external - candidate)
        recommended = None
        reason = (
            f"标准雪灾情景下主体最多可承受贷款 {_yuan_to_wan(affordable)} 万元，"
            f"按万元向下取整后实际可放 {_yuan_to_wan(candidate)} 万元；"
            f"完成必要饲草采购仍需贷款 {_yuan_to_wan(min_external)} 万元，差额 "
            f"{_yuan_to_wan(gap)} 万元。若仅发放可承受上限，必要采购仍无法完成且主体将新增债务，"
            f"因此当前不形成推荐贷款金额。"
        )
    else:
        status = "feasible"
        gap = Decimal("0")
        recommended = floor_amount
        candidate = recommended
        reason = "资料完整，必要采购资金、现金储备和偿债能力同时闭合。"

    snow_cf = _run_cashflow(ctx, candidate, "snow")
    available_snow = limits["snow_available_cash_yuan"]
    dscr = available_snow / (snow_cf["existing_service_yuan"] + snow_cf["new_loan_service_yuan"])
    reserve_gap = max(
        Decimal("0"),
        snow_cf["minimum_cash_reserve_yuan"] - snow_cf["min_cash_yuan"],
    )
    if status == "feasible" and reserve_gap > 0:
        status = "infeasible"
        recommended = None
        gap = reserve_gap
        reason = (
            f"标准雪灾情景下，按必要采购贷款 {_yuan_to_wan(candidate)} 万元测算时，"
            f"{snow_cf['min_cash_month']} 月末现金低于最低现金储备 {_yuan_to_wan(reserve_gap)} 万元；"
            "需补充非贷款应急资金或调整回款安排后重新测算。"
        )

    # 复合极端 DSCR（用候选金额检验），不生成第二个金额
    composite_cf = _run_cashflow(ctx, candidate, "composite")
    composite_plan = _monthly_plan(ctx, "composite")
    non_forage = ctx.get("monthly_non_forage_net_cash_yuan") or ctx["operating"].get("monthly_net_cash_yuan") or []
    composite_avail = sum(_dec(non_forage[i], "0") for i in range(len(MONTHS))) - composite_plan["total_purchase_cost_yuan"]
    composite_dscr = composite_avail / (
        composite_cf["existing_service_yuan"] + composite_cf["new_loan_service_yuan"]
    )

    return {
        "status": status,
        "case_id": ctx.get("id", ""),
        "case_name": ctx.get("name", ""),
        "region_name": ctx.get("region_name", ""),
        "data_status": ctx.get("data_status", {}),
        "inputs_overridden": bool(inputs),
        "recommended_amount_yuan": recommended,
        "pre_round_amount_yuan": pre_round,
        "new_loan_interest_yuan": snow_cf["new_loan_interest_yuan"] if recommended is not None else None,
        "dscr": dscr if recommended is not None else None,
        "reason": reason,
        "gap_yuan": gap,
        "qualified_demand": qualified,
        "limits": limits,
        "snow_cashflow": {
            "min_cash_yuan": snow_cf["min_cash_yuan"],
            "min_cash_month": snow_cf["min_cash_month"],
            "peak_loan_balance_yuan": snow_cf["peak_loan_balance_yuan"],
            "existing_service_yuan": snow_cf["existing_service_yuan"],
            "new_loan_service_yuan": snow_cf["new_loan_service_yuan"],
            "minimum_cash_reserve_yuan": snow_cf["minimum_cash_reserve_yuan"],
            "cash_reserve_gap_yuan": reserve_gap,
        },
        "composite": {
            "purchase_cost_yuan": composite_plan["total_purchase_cost_yuan"],
            "available_cash_yuan": composite_avail,
            "dscr": composite_dscr,
            # 复合极端固定展示首个压力月（2027-01）的现金与缺口，不输出第二个金额
            "min_cash_yuan": composite_cf["monthly_rows"][0]["cash_after_financing_yuan"],
            "min_cash_month": composite_cf["monthly_rows"][0]["month"],
            "min_cash_gap_yuan": max(
                Decimal("0"),
                composite_cf["minimum_cash_reserve_yuan"] - composite_cf["monthly_rows"][0]["cash_after_financing_yuan"],
            ),
            "vulnerable": composite_cf["monthly_rows"][0]["cash_after_financing_yuan"]
            < composite_cf["minimum_cash_reserve_yuan"],
            "generates_second_amount": False,
        },
        "monthly_scenarios": {
            "baseline": _monthly_plan(ctx, "baseline"),
            "snow": _monthly_plan(ctx, "snow"),
            "composite": _monthly_plan(ctx, "composite"),
        },
        "monthly_cashflow": {
            "snow": snow_cf["monthly_rows"],
            "composite": composite_cf["monthly_rows"],
            "baseline": _run_cashflow(ctx, candidate, "baseline")["monthly_rows"],
        },
        "notes": {
            "insurance_excluded": True,
            "legacy_models_excluded": True,
            "amounts_in_yuan": True,
            "floor_unit_yuan": 10000,
        },
    }


def _check_gate(case: dict[str, Any]) -> list[str]:
    """准入门槛：缺少关键材料或存在存量逾期时返回缺失/异常清单。"""
    missing: list[str] = []
    pasture = case.get("pasture") or {}
    livestock = case.get("livestock") or {}
    operating = case.get("operating") or {}
    debt = case.get("debt") or {}
    credit = case.get("credit") or {}

    if not pasture.get("monthly_growth_kg") and not case.get("monthly_pasture_growth_kg"):
        missing.append("草场月度可食供给")
    if not livestock.get("monthly_demand_kg") and not case.get("monthly_demand_kg"):
        missing.append("牲畜月度干物质需求")
    if not operating.get("monthly_net_cash_yuan") and not case.get("monthly_non_forage_net_cash_yuan"):
        missing.append("连续 12 个月经营回款与成本")
    if debt.get("existing_loan_yuan") is None:
        missing.append("存量债务本息")
    if debt.get("repayment_status") not in (None, "", "正常", "normal"):
        missing.append("存量还款状态异常（存在逾期）")
    if not credit.get("product_cap_yuan"):
        missing.append("样例产品上限")
    if not credit.get("dscr_threshold"):
        missing.append("DSCR 阈值")
    if not case.get("monthly_demand_kg") and not livestock.get("yak_head") and not livestock.get("sheep_head"):
        missing.append("牲畜存栏")
    return missing


def _yuan_to_wan(value: Decimal) -> str:
    """元 → 万元展示（保留两位小数，去掉末尾多余的 0）。"""
    wan = value / Decimal("10000")
    text = f"{wan:.2f}".rstrip("0").rstrip(".")
    return text if text else "0"
