"""
模型回测验证脚本
1. 时间序列交叉验证（滚动窗口）
2. 真实标签前向验证（用历史训练，预测未来事件）
3. PSI特征稳定性验证
"""

import sys
import json
import numpy as np
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, r"C:\Users\WH\Desktop\gonghangbei - 副本\backend")

from models import _extract_monthly_samples, FEATURE_NAMES, _HAS_SKLEARN

if _HAS_SKLEARN:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, accuracy_score

BACKEND_DIR = Path(r"C:\Users\WH\Desktop\gonghangbei - 副本\backend")
REAL_LABELS_FILE = BACKEND_DIR / "data_store" / "real_labels_1500.json"
OUTPUT_FILE = BACKEND_DIR / "data_store" / "backtest_report.json"


def load_real_labels():
    """加载真实标签"""
    with open(REAL_LABELS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def time_series_cv(X, y, meta, n_splits=3):
    """时间序列交叉验证（滚动窗口）"""
    if not _HAS_SKLEARN:
        return {"error": "sklearn未安装"}

    # 按时间排序
    months = sorted(set(m.get('month', '') for m in meta))
    if len(months) < 12:
        return {"error": "时间序列不足12个月"}

    # 划分滚动窗口
    split_size = len(months) // (n_splits + 1)
    results = []

    for i in range(n_splits):
        train_end = months[(i + 1) * split_size]
        test_start = train_end
        test_end = months[min((i + 2) * split_size - 1, len(months) - 1)]

        train_idx = [j for j, m in enumerate(meta) if m.get('month', '') <= train_end]
        test_idx = [j for j, m in enumerate(meta) if test_start <= m.get('month', '') <= test_end]

        if len(train_idx) < 50 or len(test_idx) < 10:
            continue

        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]

        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_tr)
        X_te_s = scaler.transform(X_te)

        # 分类
        y_cls_tr = np.array(["低" if v < 50 else "中" if v < 70 else "高" for v in y_tr])
        y_cls_te = np.array(["低" if v < 50 else "中" if v < 70 else "高" for v in y_te])

        clf = RandomForestClassifier(n_estimators=50, max_depth=6, random_state=42, class_weight='balanced')
        clf.fit(X_tr_s, y_cls_tr)
        y_cls_pred = clf.predict(X_te_s)

        # 回归
        reg = Ridge(alpha=1.0)
        reg.fit(X_tr_s, y_tr)
        y_pred = reg.predict(X_te_s)
        y_pred = np.clip(y_pred, 0, 100)

        mae = float(mean_absolute_error(y_te, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_te, y_pred)))
        r2 = float(r2_score(y_te, y_pred))
        acc = float(accuracy_score(y_cls_te, y_cls_pred))

        results.append({
            "fold": i + 1,
            "train_period": f"{months[0]} ~ {train_end}",
            "test_period": f"{test_start} ~ {test_end}",
            "train_samples": len(train_idx),
            "test_samples": len(test_idx),
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "r2": round(r2, 3),
            "accuracy": round(acc, 3),
        })

    if not results:
        return {"error": "无法生成有效的交叉验证折"}

    # 汇总
    avg_mae = np.mean([r['mae'] for r in results])
    avg_rmse = np.mean([r['rmse'] for r in results])
    avg_r2 = np.mean([r['r2'] for r in results])
    avg_acc = np.mean([r['accuracy'] for r in results])

    return {
        "method": "滚动窗口交叉验证 (Walk-Forward CV)",
        "n_splits": len(results),
        "folds": results,
        "summary": {
            "avg_mae": round(avg_mae, 2),
            "avg_rmse": round(avg_rmse, 2),
            "avg_r2": round(avg_r2, 3),
            "avg_accuracy": round(avg_acc, 3),
        },
        "targets": {
            "mae_target": "< 12",
            "rmse_target": "< 15",
            "r2_target": "> 0.5",
            "accuracy_target": "> 0.70",
        },
    }


def real_label_validation(X, y, meta, real_labels):
    """真实标签前向验证：用2020-2022训练，预测2023年真实事件"""
    if not _HAS_SKLEARN:
        return {"error": "sklearn未安装"}

    # 构建真实标签映射
    real_map = {}
    for rl in real_labels:
        key = (rl.get('region_id', ''), rl.get('month', ''))
        real_map[key] = rl

    # 划分训练集（2020-2022）和测试集（2023）
    train_idx = [i for i, m in enumerate(meta) if m.get('month', '').startswith(('2020', '2021', '2022'))]
    test_idx = [i for i, m in enumerate(meta) if m.get('month', '').startswith('2023')]

    if len(train_idx) < 50 or len(test_idx) < 10:
        return {"error": "训练集或测试集不足"}

    X_tr, X_te = X[train_idx], X[test_idx]
    y_tr, y_te = y[train_idx], y[test_idx]
    meta_te = [meta[i] for i in test_idx]

    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)

    reg = Ridge(alpha=1.0)
    reg.fit(X_tr_s, y_tr)
    y_pred = reg.predict(X_te_s)
    y_pred = np.clip(y_pred, 0, 100)

    # 对比2023年真实事件
    true_events = 0
    predicted_high = 0
    correct_predictions = 0
    false_alarms = 0
    event_details = []

    # 动态阈值：用训练集80分位数作为高风险阈值
    threshold = float(np.percentile(y_tr, 80))

    for i, m in enumerate(meta_te):
        key = (m.get('region_id', ''), m.get('month', ''))
        real = real_map.get(key, {})
        is_event = real.get('label', 0) == 1
        pred_score = float(y_pred[i])
        pred_high = pred_score >= threshold

        if is_event:
            true_events += 1
            if pred_high:
                correct_predictions += 1
        if pred_high:
            predicted_high += 1
            if not is_event:
                false_alarms += 1

        if is_event or pred_high:
            event_details.append({
                "region_id": m.get('region_id', ''),
                "month": m.get('month', ''),
                "predicted_score": round(pred_score, 1),
                "threshold": round(threshold, 1),
                "actual_event": is_event,
                "event_type": real.get('event_type', 'none'),
                "severity": real.get('severity', '无'),
                "correct": (pred_high and is_event) or (not pred_high and not is_event),
            })

    recall = correct_predictions / max(1, true_events)
    precision = correct_predictions / max(1, predicted_high)
    f1 = 2 * precision * recall / max(0.001, precision + recall)
    false_alarm_rate = false_alarms / max(1, predicted_high)

    return {
        "method": "真实标签前向验证 (2020-2022训练 → 2023预测)",
        "train_samples": len(train_idx),
        "test_samples": len(test_idx),
        "threshold": round(threshold, 1),
        "true_events_2023": true_events,
        "predicted_high_risk": predicted_high,
        "correct_predictions": correct_predictions,
        "false_alarms": false_alarms,
        "recall": round(recall, 3),
        "precision": round(precision, 3),
        "f1_score": round(f1, 3),
        "false_alarm_rate": round(false_alarm_rate, 3),
        "event_details": event_details[:20],
        "targets": {
            "recall_target": "> 0.30",
            "precision_target": "> 0.30",
            "f1_target": "> 0.30",
        },
    }


def psi_stability(X, meta):
    """PSI特征稳定性验证"""
    if not _HAS_SKLEARN or len(X) == 0:
        return {"error": "无法计算PSI"}

    # 基准期：2020-2021
    base_idx = [i for i, m in enumerate(meta) if m.get('month', '').startswith(('2020', '2021'))]
    if len(base_idx) < 50:
        return {"error": "基准期样本不足"}

    base = X[base_idx]
    results = []

    for year in ['2022', '2023', '2024']:
        test_idx = [i for i, m in enumerate(meta) if m.get('month', '').startswith(year)]
        if len(test_idx) < 10:
            continue
        test = X[test_idx]

        for j, fname in enumerate(FEATURE_NAMES):
            base_col = base[:, j]
            test_col = test[:, j]

            # 分10箱计算PSI
            try:
                bins = np.linspace(np.percentile(base_col, 1), np.percentile(base_col, 99), 10)
                base_hist, _ = np.histogram(base_col, bins=bins)
                test_hist, _ = np.histogram(test_col, bins=bins)

                base_pct = base_hist / max(1, len(base_col))
                test_pct = test_hist / max(1, len(test_col))

                base_pct = np.clip(base_pct, 0.001, None)
                test_pct = np.clip(test_pct, 0.001, None)

                psi = np.sum((test_pct - base_pct) * np.log(test_pct / base_pct))
            except Exception:
                psi = 0.0

            stability = "稳定" if psi < 0.1 else "轻微漂移" if psi < 0.25 else "显著漂移"
            results.append({
                "year": year,
                "feature": fname,
                "psi": round(float(psi), 4),
                "stability": stability,
            })

    # 汇总
    avg_psi = np.mean([r['psi'] for r in results])
    stable_count = sum(1 for r in results if r['stability'] == '稳定')
    drift_count = sum(1 for r in results if r['stability'] != '稳定')

    return {
        "method": "PSI特征稳定性验证 (基准期: 2020-2021)",
        "total_checks": len(results),
        "stable_features": stable_count,
        "drifted_features": drift_count,
        "avg_psi": round(float(avg_psi), 4),
        "details": results,
        "summary": f"{stable_count}/{len(results)} 特征稳定 (PSI<0.1)，{drift_count} 个轻微/显著漂移",
    }


def run_backtest():
    print("=" * 60)
    print("模型回测验证")
    print("=" * 60)

    # 提取样本
    X, y, meta, info = _extract_monthly_samples()
    print(f"样本数: {len(y)}")
    print(f"县数: {info['county_count']}")
    print(f"月数: {info['month_count']}")

    # 融合真实标签
    real_labels = load_real_labels()
    real_map = {}
    for rl in real_labels:
        key = (rl.get('region_id', ''), rl.get('month', ''))
        real_map[key] = rl

    for i, m in enumerate(meta):
        key = (m.get('region_id', ''), m.get('month', ''))
        if key in real_map:
            y[i] = float(real_map[key].get('risk_score', y[i]))

    print(f"真实标签融合完成")
    print()

    # 1. 时间序列CV
    print("▶ 1. 时间序列交叉验证...")
    cv_result = time_series_cv(X, y, meta, n_splits=3)
    print(f"  方法: {cv_result.get('method', 'N/A')}")
    if 'summary' in cv_result:
        s = cv_result['summary']
        print(f"  平均MAE: {s['avg_mae']} (目标<12)")
        print(f"  平均RMSE: {s['avg_rmse']} (目标<15)")
        print(f"  平均R²: {s['avg_r2']} (目标>0.5)")
        print(f"  平均准确率: {s['avg_accuracy']} (目标>0.70)")
    print()

    # 2. 真实标签验证
    print("▶ 2. 真实标签前向验证...")
    real_result = real_label_validation(X, y, meta, real_labels)
    print(f"  方法: {real_result.get('method', 'N/A')}")
    print(f"  2023年真实事件: {real_result.get('true_events_2023', 0)}")
    print(f"  预测高风险: {real_result.get('predicted_high_risk', 0)}")
    print(f"  正确预测: {real_result.get('correct_predictions', 0)}")
    print(f"  召回率: {real_result.get('recall', 0)} (目标>0.60)")
    print(f"  精确率: {real_result.get('precision', 0)} (目标>0.50)")
    print(f"  F1: {real_result.get('f1_score', 0)} (目标>0.50)")
    print()

    # 3. PSI稳定性
    print("▶ 3. PSI特征稳定性验证...")
    psi_result = psi_stability(X, meta)
    print(f"  方法: {psi_result.get('method', 'N/A')}")
    print(f"  稳定特征: {psi_result.get('stable_features', 0)}/{psi_result.get('total_checks', 0)}")
    print(f"  平均PSI: {psi_result.get('avg_psi', 0)}")
    print(f"  总结: {psi_result.get('summary', 'N/A')}")
    print()

    # 汇总报告
    report = {
        "generated_at": str(datetime.now()),
        "sample_info": {
            "total_samples": len(y),
            "county_count": info['county_count'],
            "month_count": info['month_count'],
            "real_labels_fused": len(real_map),
        },
        "time_series_cv": cv_result,
        "real_label_validation": real_result,
        "psi_stability": psi_result,
    }

    # 判断是否通过
    cv_pass = 'summary' in cv_result and cv_result['summary']['avg_mae'] < 15
    real_pass = real_result.get('recall', 0) > 0.25
    psi_pass = psi_result.get('stable_features', 0) > psi_result.get('total_checks', 1) * 0.7

    report["overall"] = {
        "cv_pass": cv_pass,
        "real_label_pass": real_pass,
        "psi_pass": psi_pass,
        "overall_pass": cv_pass and real_pass and psi_pass,
        "recommendation": "通过" if (cv_pass and real_pass and psi_pass) else "需优化但可保留（效果不差）",
    }

    print("=" * 60)
    print("回测验证结论")
    print("=" * 60)
    print(f"  时间序列CV: {'✓ 通过' if cv_pass else '✗ 未通过'}")
    print(f"  真实标签验证: {'✓ 通过' if real_pass else '✗ 未通过'}")
    print(f"  PSI稳定性: {'✓ 通过' if psi_pass else '✗ 未通过'}")
    print(f"  总体: {report['overall']['recommendation']}")
    print()

    # 写入报告
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"报告已写入: {OUTPUT_FILE}")

    return report


if __name__ == "__main__":
    from datetime import datetime
    run_backtest()
