"""
牧融绿链 — NPP 载畜量模型回测验证
====================================================================
用 2001-2024 年 NPP 数据预测 2025 年，对比 MODIS 2025 真实值。
同时评估预测值对载畜量精算的影响。

训练集: 2001-2024 (24年)
测试集: 2025 (1年)

预测方法:
  1. Naive (上年值)   —— 直接用 2024 预测 2025
  2. 均值法             —— 24 年均值
  3. 线性趋势           —— 最小二乘拟合
  4. 近3年均值          —— 2022-2024 均值
  5. 近5年均值          —— 2020-2024 均值
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

# ── 配置 ──
ROOT = Path(__file__).resolve().parent
NPP_PATH = ROOT / "data_store" / "npp_by_region.json"


def load_npp_data() -> list[dict]:
    return json.loads(NPP_PATH.read_text(encoding="utf-8"))


def train_predict(history: dict[str, float]) -> tuple[float, dict[str, float]]:
    """用 2001-2024 训练，预测 2025，返回 (真实值, {方法: 预测值})。"""
    actual_2025 = history.get("2025", 0.0)
    years = sorted(int(y) for y in history if y != "2025")
    vals = np.array([history[str(y)] for y in years])

    if len(vals) < 2:
        return actual_2025, {}

    # 1) Naive: 上年值
    naive = history.get("2024", 0.0)

    # 2) 均值
    mean_val = float(np.mean(vals))

    # 3) 线性趋势
    x = np.array(years).astype(float)
    x_mean = float(np.mean(x))
    y_mean = float(np.mean(vals))
    slope = float(np.sum((x - x_mean) * (vals - y_mean)) / np.sum((x - x_mean) ** 2))
    intercept = y_mean - slope * x_mean
    linear = intercept + slope * 2025.0

    # 4) 近 3 年均值
    recent3 = float(np.mean(vals[-3:])) if len(vals) >= 3 else mean_val

    # 5) 近 5 年均值
    recent5 = float(np.mean(vals[-5:])) if len(vals) >= 5 else mean_val

    return actual_2025, {
        "naive(上年值)": naive,
        "mean(24年均值)": mean_val,
        "linear(线性趋势)": linear,
        "recent3(近3年)": recent3,
        "recent5(近5年)": recent5,
    }


def npp_to_capacity(npp: float) -> float:
    """NPP (kgC/m²/yr) → 载畜量基线 (羊单位)。与 carrying_capacity.py 一致。"""
    return npp * 15000.0 + 5000.0


def format_pct(v: float) -> str:
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.1f}%"


def main():
    counties = load_npp_data()
    print(f"回测验证: {len(counties)} 个县, 训练集 2001-2024, 测试集 2025\n")

    # ── 每县明细 ──
    all_errors: dict[str, list[float]] = {}
    rows: list[dict[str, Any]] = []

    for entry in counties:
        rid = entry["region_id"]
        history = entry["npp_annual"]
        actual, preds = train_predict(history)
        if actual == 0.0:
            continue

        row = {
            "region_id": rid,
            "actual_2025": round(actual, 4),
            "mean_24yr": round(float(np.mean([float(history[str(y)]) for y in range(2001, 2025)])), 4),
        }
        for method, pred in preds.items():
            err_pct = (pred - actual) / actual * 100.0
            row[f"{method}_pred"] = round(pred, 4)
            row[f"{method}_err%"] = round(err_pct, 1)
            all_errors.setdefault(method, []).append(abs(err_pct))
        rows.append(row)

    # ── 排名 ──
    best_rankings: dict[str, int] = {}
    for method in all_errors:
        sorted_rows = sorted(rows, key=lambda r: abs(r.get(f"{method}_err%", 999)))
        best_rankings[method] = sorted_rows[0].get(f"{method}_err%", 0)

    # ── 全局指标 ──
    print("=" * 80)
    print(f"{'方法':<20s} {'MAE':>8s} {'中位误差':>8s} {'平均偏差':>8s} {'最大误差':>8s} {'R²':>8s}")
    print("-" * 80)

    best_method = ""
    best_mae = 999.0

    for method in ["naive(上年值)", "mean(24年均值)", "linear(线性趋势)", "recent3(近3年)", "recent5(近5年)"]:
        errors = all_errors.get(method, [])
        if not errors:
            continue

        # 收集所有预测值和真实值计算 R²
        all_actual = []
        all_pred = []
        for r in rows:
            all_actual.append(r["actual_2025"])
            all_pred.append(r.get(f"{method}_pred", 0))

        actual_arr = np.array(all_actual)
        pred_arr = np.array(all_pred)
        ss_res = float(np.sum((actual_arr - pred_arr) ** 2))
        ss_tot = float(np.sum((actual_arr - float(np.mean(actual_arr))) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        mae = round(float(np.mean(errors)), 1)
        median_err = round(float(np.median(errors)), 1)
        max_err = round(float(np.max(errors)), 1)

        # 平均偏差（带符号）
        signed_errs = [(r.get(f"{method}_pred", 0) - r["actual_2025"]) / max(0.0001, r["actual_2025"]) * 100 for r in rows]
        avg_bias = round(float(np.mean(signed_errs)), 1)
        bias_str = format_pct(avg_bias)

        print(f"{method:<20s} {mae:>8.1f}% {median_err:>8.1f}% {bias_str:>8s} {max_err:>8.1f}% {r2:>8.3f}")

        if mae < best_mae:
            best_mae = mae
            best_method = method

    print("-" * 80)
    print(f"\n最优方法: {best_method} (MAE={best_mae}%)\n")

    # ── 每县明细表 ──
    print("=" * 80)
    print(f"{'县':<22s} {'2025真实':>10s} {'24年均值':>10s} {'最优预测':>10s} {'误差%':>7s}")
    print("-" * 80)
    rows.sort(key=lambda r: r["actual_2025"])
    for r in rows:
        err_key = f"{best_method}_err%"
        pred_key = f"{best_method}_pred"
        actual = r["actual_2025"]
        pred = r.get(pred_key, 0)
        err = r.get(err_key, 0)
        marker = " ←" if abs(err) > 30 else ""
        print(f"{r['region_id']:<22s} {actual:>10.4f} {r['mean_24yr']:>10.4f} {pred:>10.4f} {err:>+6.1f}%{marker}")

    print("-" * 80)

    # ── 载畜量影响分析 ──
    print(f"\n{'='*80}")
    print(f"载畜量影响分析 (最优方法: {best_method})")
    print(f"{'县':<22s} {'真实NPP→载畜量':>18s} {'预测NPP→载畜量':>18s} {'偏差':>10s}")
    print("-" * 80)
    total_actual_cap = 0
    total_pred_cap = 0
    for r in rows:
        pred_key = f"{best_method}_pred"
        actual_cap = npp_to_capacity(r["actual_2025"])
        pred_cap = npp_to_capacity(r.get(pred_key, 0))
        total_actual_cap += actual_cap
        total_pred_cap += pred_cap
        diff = pred_cap - actual_cap
        marker = " ⚠️" if abs(diff) > 3000 else ""
        print(f"{r['region_id']:<22s} {r['actual_2025']:.4f}→{actual_cap:>7.0f}羊单位   {r.get(pred_key, 0):.4f}→{pred_cap:>7.0f}羊单位   {diff:>+7.0f}{marker}")

    total_diff = total_pred_cap - total_actual_cap
    total_err_pct = total_diff / total_actual_cap * 100
    print("-" * 80)
    print(f"{'合计':<22s} 真实总载畜量: {total_actual_cap:>8.0f}  预测总载畜量: {total_pred_cap:>8.0f}  偏差: {format_pct(total_err_pct)}")

    # ── 结论 ──
    print(f"\n{'='*80}")
    print("结论:")
    print(f"  NPP 预测最优方法: {best_method}, MAE={best_mae}%")
    print(f"  全县合计载畜量偏差: {format_pct(total_err_pct)}")
    if abs(total_err_pct) < 10:
        print(f"  ✅ 算法准确度可接受 (< 10%)，可用于生产环境")
    elif abs(total_err_pct) < 20:
        print(f"  ⚠️ 算法准确度一般 (10-20%)，需关注高误差县")
    else:
        print(f"  ❌ 算法准确度不足 (> 20%)，需要优化")
    print("=" * 80)


if __name__ == "__main__":
    main()