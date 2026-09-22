#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T1 补丁：credit_decision.py 的抵押上限（D7/D8）与两级 bottleneck（D9）

用 Serena 的符号级编辑工具改代码（不走文本替换），步骤：
  1. insert_after_symbol  SCENARIOS              -> 加 _PLEDGE_DISCOUNT 常量
  2. insert_before_symbol _affordable_limits     -> 加 _live_stock_pledge_limit 函数
  3. replace_symbol_body  _affordable_limits     -> 抵押上限接入 min 比较
  4. replace_in_files     （literal）            -> evaluate_credit_case 里插入两级 bottleneck
  5. replace_in_files     （literal）            -> 返回体加 "bottleneck" 字段
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import serena_http as S  # noqa: E402

TARGET = "backend/credit_decision.py"
TMP = Path(__file__).resolve().parent / "_args.json"

# ---------------------------------------------------------------- 1) 常量
CONST = '''# 活体抵押折扣分档（方案 D8，起始值）
# 量级依据：活体处置有折价、有周期，处置折扣本质是"这头牛死了有没有保险赔"；
# 非监管规定，随市场行情与实际处置数据标定后可调。
_PLEDGE_DISCOUNT: dict[str, Decimal] = {
    "tag_insured": Decimal("0.70"),      # 有耳标 + 有保险（已核验）
    "tag_uninsured": Decimal("0.40"),    # 有耳标 + 无保险
    "untag_insured": Decimal("0.30"),    # 无耳标 + 有保险
    "untag_uninsured": Decimal("0"),     # 都无 -> 不计入抵押
}


'''

# ------------------------------------------------------- 2) 抵押上限函数
PLEDGE_FN = '''def _live_stock_pledge_limit(case: dict[str, Any]) -> dict[str, Any]:
    """按「耳标 × 保险」分档计算活体资产抵押上限（方案 D7/D8）。

    输入来自 case["pledge"]：
      {
        "insurance_verified": bool,          # 保单是否已核验合同与责任范围
        "items": [
          {"species": "牦牛", "head": 980, "unit_price_yuan": 8000,
           "ear_tagged": 980, "insured": 0},  # 数量均为「有 / 已投保的头数」
          ...
        ]
      }

    分档（起始值，见 _PLEDGE_DISCOUNT）：
      有耳标 + 有保险 70% / 有耳标 + 无保险 40% / 无耳标 + 有保险 30% / 都无 不计入

    两条硬规则：
      1. 保险未核验时，投保档不计入（不知道哪头牛真的保了，不能按已投保认抵押）；
      2. 数据缺失时 applicable=False 并排除出 min 比较——**不得按 0 处理**，
         否则抵押上限会立刻成为瓶颈，把所有客户的额度压到 0。
    """
    pledge = case.get("pledge") or {}
    if not isinstance(pledge, dict):
        return {
            "applicable": False,
            "insurance_verified": False,
            "buckets": {},
            "discounts": {k: float(v) for k, v in _PLEDGE_DISCOUNT.items()},
            "limit_yuan": Decimal("0"),
            "items": [],
            "note": "case 未提供 pledge 段，抵押上限不适用（不参与 min 比较）",
        }

    insurance_verified = bool(pledge.get("insurance_verified", False))
    raw_items = pledge.get("items") or []

    buckets = {
        "tag_insured": Decimal("0"),
        "tag_uninsured": Decimal("0"),
        "untag_insured": Decimal("0"),
        "untag_uninsured": Decimal("0"),
    }
    limit = Decimal("0")
    detail: list[dict[str, Any]] = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        head = _dec(item.get("head"), "0")
        if head <= 0:
            continue
        price = _dec(item.get("unit_price_yuan"), "0")
        tagged = min(_dec(item.get("ear_tagged"), "0"), head)
        # 未核验保险 -> 投保数按 0 计
        insured = min(_dec(item.get("insured"), "0"), head) if insurance_verified else Decimal("0")

        tag_insured = min(tagged, insured)
        tag_uninsured = tagged - tag_insured
        untag_insured = max(Decimal("0"), insured - tag_insured)
        untag_uninsured = max(
            Decimal("0"), head - tag_insured - tag_uninsured - untag_insured
        )

        item_value = Decimal("0")
        for key, count in (
            ("tag_insured", tag_insured),
            ("tag_uninsured", tag_uninsured),
            ("untag_insured", untag_insured),
            ("untag_uninsured", untag_uninsured),
        ):
            buckets[key] += count
            item_value += count * price * _PLEDGE_DISCOUNT[key]

        limit += item_value
        detail.append({
            "species": item.get("species", ""),
            "head": float(head),
            "unit_price_yuan": float(price),
            "ear_tagged": float(tagged),
            "insured": float(insured),
            "recognized_yuan": float(item_value),
        })

    return {
        "applicable": limit > 0,
        "insurance_verified": insurance_verified,
        "buckets": {k: float(v) for k, v in buckets.items()},
        "discounts": {k: float(v) for k, v in _PLEDGE_DISCOUNT.items()},
        "limit_yuan": limit,
        "items": detail,
    }


'''

# ------------------------------------------------- 3) 新版 _affordable_limits
AFFORDABLE = '''def _affordable_limits(case: dict[str, Any]) -> dict[str, Any]:
    """标准雪灾偿债支持上限 + 其他授信约束（统一授信可用、产品上限、活体抵押上限）。

    活体抵押上限自 2026-09-23 起由 _live_stock_pledge_limit() 按耳标/保险分档计算
    （方案 D7：推翻原先的 limits.no_live_stock_collateral）；数据缺失时标为不适用、
    不参与 min 比较。返回的 "bottleneck" 仅为**供给侧**瓶颈，最终瓶颈见
    evaluate_credit_case() 返回的顶层 "bottleneck"（需求侧 vs 供给侧两级）。
    """
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

    pledge = _live_stock_pledge_limit(case)

    candidates = [snow_support, credit_available, product_cap]
    labels = ["标准雪灾偿债支持上限", "统一授信可用额度", "样例产品上限"]
    if pledge["applicable"]:
        candidates.append(pledge["limit_yuan"])
        labels.append("活体抵押上限")
    affordable = min(candidates)
    bottleneck = labels[candidates.index(affordable)]

    return {
        "snow_available_cash_yuan": available_cash,
        "snow_support_limit_yuan": snow_support,
        "dscr_threshold": dscr_threshold,
        "credit_available_yuan": credit_available,
        "product_cap_yuan": product_cap,
        # 兼容保留：旧字段原名（现由活体抵押计算取代，不再直接参与 min）
        "collateral_support_yuan": case["credit"].get("collateral_support_yuan"),
        "collateral_applicable": pledge["applicable"],
        "pledge": pledge,
        "affordable_limit_yuan": affordable,
        "bottleneck": bottleneck,
    }
'''

# ------------------------------------------- 4) evaluate_credit_case 的两处插桩
ANCHOR_AMOUNT = """    # 唯一金额：先精确比较，最后向下取整到 1 万元
    pre_round = min(qualified["qualified_demand_yuan"], affordable)"""

AMOUNT_WITH_BOTTLENECK = """    # 最终瓶颈（两级，方案 D9）：需求侧与供给侧各算一遍，谁小谁卡住金额。
    # 旧版只报供给侧四约束里最小的是谁，会把"卡在饲草资金需求"误报成"卡在偿债能力"。
    demand_side = qualified["qualified_demand_yuan"]
    supply_side = affordable
    if demand_side <= supply_side:
        final_key, final_label = "qualified_demand", "基准合格融资需求（饲草采购资金缺口）"
    else:
        final_key, final_label = "affordable_limit", limits["bottleneck"]
    bottleneck = {
        "final": final_key,
        "final_label": final_label,
        "supply_side": limits["bottleneck"],
        "demand_side_yuan": float(demand_side),
        "supply_side_yuan": float(supply_side),
    }

    # 唯一金额：先精确比较，最后向下取整到 1 万元
    pre_round = min(qualified["qualified_demand_yuan"], affordable)"""

ANCHOR_RETURN = '        "limits": limits,'
RETURN_WITH_BOTTLENECK = '        "limits": limits,\n        "bottleneck": bottleneck,'


def call(tool: str, args: dict) -> None:
    TMP.write_text(json.dumps(args, ensure_ascii=False), encoding="utf-8")
    import subprocess

    r = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "serena_http.py"),
         "call", tool, "--args-file", str(TMP)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    print(f"--- {tool}")
    if err:
        print("   stderr:", err.splitlines()[-1][:200])
    print("   ", out[:400] if out else "(无输出)")
    if r.returncode != 0:
        raise SystemExit(f"{tool} 失败")


def main() -> int:
    # 常量与函数一起插在 _affordable_limits 之前（insert_after 不支持常量符号）
    call("insert_before_symbol", {
        "name_path": "_affordable_limits", "relative_path": TARGET,
        "body": CONST + PLEDGE_FN,
    })
    call("replace_symbol_body", {"name_path": "_affordable_limits", "relative_path": TARGET, "body": AFFORDABLE})
    call("replace_in_files", {
        "needle": ANCHOR_AMOUNT, "repl": AMOUNT_WITH_BOTTLENECK,
        "mode": "literal", "relative_path": TARGET, "expected_count": 1,
    })
    call("replace_in_files", {
        "needle": ANCHOR_RETURN, "repl": RETURN_WITH_BOTTLENECK,
        "mode": "literal", "relative_path": TARGET, "expected_count": 1,
    })
    print("\n=== 语法编译检查 ===")
    import py_compile
    py_compile.compile(str(Path(__file__).resolve().parents[2] / TARGET), doraise=True)
    print("compile OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
