"""
牧融绿链 - 模型层
============================================================================
训练样本单位 = region_id + month（不再只按 region_id 聚合）。

样本量判断:
  - < 50:  仅规则模型, 提示样本不足
  - 50-300: 基础 ML, 置信度较低
  - >= 300: 较稳定 ML 训练和评估

特征维度 (来自 4 张数据表):
  1. 气象特征: temperature_c(均值), precipitation_mm_24h(月累计/均值),
               wind_speed_mps(均值), snow_depth_cm(最大值),
               cold_wave_risk(最差值), snowstorm_risk(最差值), drought_risk(最差值)
  2. 遥感特征: ndvi(均值), ndvi_change(均值), vegetation_cover(均值),
               snow_cover(最大值), degradation_level(最差值),
               carrying_capacity_sheep_unit(均值)
  3. 经营特征: avg_score, avg_insurance_coverage (区域静态)
  4. 金融特征: finance_risk_score (区域静态)
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

_HAS_SKLEARN = False
try:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import cross_val_score, train_test_split
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, accuracy_score
    _HAS_SKLEARN = True
except ImportError:
    pass

_HAS_SHAP = False
try:
    import shap
    _HAS_SHAP = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------

_STORE_DIR = Path(__file__).resolve().parent / "data_store"
_REGION_LIST_PATH = Path(__file__).resolve().parents[1] / "public_data" / "region_list.csv"


def _load_table(table: str) -> list[dict[str, Any]]:
    path = _STORE_DIR / f"{table}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def _load_region_list() -> list[dict[str, Any]]:
    """从 region_list.csv 加载区域清单。"""
    if not _REGION_LIST_PATH.exists():
        return []
    rows = []
    with open(_REGION_LIST_PATH, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


# ---------------------------------------------------------------------------
# 编码
# ---------------------------------------------------------------------------

_RISK_ENCODE = {"低": 0, "中": 1, "高": 2}
_DEGRADATION_ENCODE = {"基本稳定": 0, "轻度退化": 1, "中度退化": 2, "重度退化": 3}
_REPAYMENT_ENCODE = {"正常": 0, "关注": 1, "逾期": 2, "异常": 3}

FEATURE_NAMES = [
    "temperature_c", "precipitation_mm_24h", "wind_speed_mps", "snow_depth_cm",
    "cold_wave_risk", "snowstorm_risk", "drought_risk",
    "ndvi", "ndvi_change_pct", "vegetation_cover_pct", "snow_cover_pct",
    "degradation_level", "carrying_capacity",
    "avg_score", "avg_insurance_coverage", "finance_risk_score",
]


def _safe_float(val: Any, default: float = 0.0) -> float:
    """安全转换为 float，处理空字符串和 None。"""
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        try:
            return float(str(val).replace("%", ""))
        except (ValueError, TypeError):
            return default


# ---------------------------------------------------------------------------
# 特征提取：region_id + month
# ---------------------------------------------------------------------------

def _parse_month(val: str | None) -> str | None:
    """从 observed_at 或 scene_date 提取 YYYY-MM。"""
    if not val:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(val.strip()[:10], "%Y-%m-%d").strftime("%Y-%m")
        except (ValueError, IndexError):
            pass
    return None


def _extract_monthly_samples() -> tuple[np.ndarray, np.ndarray, list[dict], dict[str, Any]]:
    """按 region_id + month 构建训练样本。

    Returns:
        X: (n_samples, 16) 特征矩阵
        y: (n_samples,) 风险评分
        sample_meta: 每个样本的元信息 [{region_id, month, ...}]
        info: 统计信息
    """
    weather_rows = _load_table("weather_data")
    remote_rows = _load_table("remote_sensing_data")
    subject_rows = _load_table("business_subjects")
    finance_rows = _load_table("finance_credit")
    region_list = _load_region_list()

    # ---- 区域名映射 ----
    region_names: dict[str, str] = {}
    for rl in region_list:
        region_names[rl["region_id"]] = rl.get("region_name", rl.get("county", rl["region_id"]))

    # ---- 经营特征（区域静态聚合）----
    subj_by_region: dict[str, list[dict]] = {}
    for s in subject_rows:
        subj_by_region.setdefault(s.get("region_id", ""), []).append(s)

    biz_by_region: dict[str, dict] = {}
    for rid, subjs in subj_by_region.items():
        scores = [float(s.get("score", 70)) for s in subjs]
        coverages = []
        for s in subjs:
            cv = str(s.get("insurance_coverage", "70%")).replace("%", "")
            try: coverages.append(float(cv))
            except ValueError: coverages.append(70.0)
        biz_by_region[rid] = {
            "avg_score": np.mean(scores) if scores else 70.0,
            "avg_coverage": np.mean(coverages) if coverages else 70.0,
        }

    # ---- 金融特征（区域静态聚合）----
    fin_by_name: dict[str, dict] = {}
    for f in finance_rows:
        fin_by_name[f.get("subject_name", "")] = f

    fin_by_region: dict[str, float] = {}
    for rid, subjs in subj_by_region.items():
        fin_scores = []
        for s in subjs:
            fdata = fin_by_name.get(s.get("name", ""), {})
            if fdata:
                status = _REPAYMENT_ENCODE.get(str(fdata.get("repayment_status", "正常")), 0)
                overdue = int(fdata.get("overdue_times", 0))
                fin_scores.append(min(100, status * 20 + overdue * 15))
        fin_by_region[rid] = np.mean(fin_scores) if fin_scores else 50.0

    # ---- 按 (region_id, month) 聚合气象数据 ----
    wx_monthly: dict[tuple[str, str], list[dict]] = {}
    for w in weather_rows:
        rid = w.get("region_id", "")
        month = _parse_month(w.get("observed_at"))
        if not rid or not month:
            continue
        wx_monthly.setdefault((rid, month), []).append(w)

    # ---- 按 (region_id, month) 聚合遥感数据 ----
    rm_monthly: dict[tuple[str, str], list[dict]] = {}
    for r in remote_rows:
        rid = r.get("region_id", "")
        month = _parse_month(r.get("scene_date"))
        if not rid or not month:
            continue
        rm_monthly.setdefault((rid, month), []).append(r)

    # ---- 所有 region-month 键 ----
    all_keys = sorted(set(list(wx_monthly.keys()) + list(rm_monthly.keys())))

    # ---- 构建样本 ----
    X_rows: list[list[float]] = []
    y_rows: list[float] = []
    sample_meta: list[dict] = []

    for (rid, month) in all_keys:
        wx_list = wx_monthly.get((rid, month), [])
        rm_list = rm_monthly.get((rid, month), [])

        # --- 气象特征聚合 ---
        if wx_list:
            temps = [float(x.get("temperature_c", 0)) for x in wx_list]
            precip = [float(x.get("precipitation_mm_24h", 0)) for x in wx_list]
            winds = [float(x.get("wind_speed_mps", 0)) for x in wx_list]
            snows = [float(x.get("snow_depth_cm", 0)) for x in wx_list]
            colds = [_RISK_ENCODE.get(str(x.get("cold_wave_risk", "中")), 1) for x in wx_list]
            storms = [_RISK_ENCODE.get(str(x.get("snowstorm_risk", "中")), 1) for x in wx_list]
            droughts = [_RISK_ENCODE.get(str(x.get("drought_risk", "中")), 1) for x in wx_list]

            avg_temp = np.mean(temps)
            sum_precip = np.sum(precip)  # 月累计降水
            avg_wind = np.mean(winds)
            max_snow = max(snows)  # 最大积雪深度
            worst_cold = max(colds)
            worst_storm = max(storms)
            worst_drought = max(droughts)
            wx_score = max(worst_cold, worst_storm, worst_drought) * 35
        else:
            avg_temp = sum_precip = avg_wind = max_snow = 0.0
            worst_cold = worst_storm = worst_drought = 1.0
            wx_score = 35.0

        # --- 遥感特征聚合 ---
        if rm_list:
            ndvis = [_safe_float(x.get("ndvi"), 0.4) for x in rm_list]
            ndvi_changes = []
            for x in rm_list:
                s = str(x.get("ndvi_change", "0%")).replace("%", "")
                try: ndvi_changes.append(float(s))
                except ValueError: ndvi_changes.append(0.0)
            vegs = []
            for x in rm_list:
                s = str(x.get("vegetation_cover", "50%")).replace("%", "")
                try: vegs.append(float(s))
                except ValueError: vegs.append(50.0)
            snow_covs = []
            for x in rm_list:
                s = str(x.get("snow_cover", "10%")).replace("%", "")
                try: snow_covs.append(float(s))
                except ValueError: snow_covs.append(10.0)
            degs = [_DEGRADATION_ENCODE.get(str(x.get("degradation_level", "轻度退化")), 1) for x in rm_list]
            caps = [_safe_float(x.get("carrying_capacity_sheep_unit"), 20000) for x in rm_list]

            avg_ndvi = np.mean(ndvis)
            avg_ndvi_change = np.mean(ndvi_changes)
            avg_veg = np.mean(vegs)
            max_snow_cov = max(snow_covs)
            worst_deg = max(degs)
            avg_cap = np.mean(caps)
            rm_score = (1.0 - avg_ndvi) * 50 + worst_deg * 12 + (avg_ndvi_change < -5) * 10
        else:
            avg_ndvi = 0.4; avg_ndvi_change = 0.0; avg_veg = 50.0
            max_snow_cov = 10.0; worst_deg = 1.0; avg_cap = 20000.0
            rm_score = 40.0

        # --- 经营特征 ---
        # ★ 保险是增信因子，不是风险因子 ★
        # 银行放贷视角：牧民有牦牛保险 → 牲畜死亡有保险公司兜底 → 银行风险敞口缩小
        # 因此：高覆盖率 → 风险降低（减险），低覆盖率 → 风险增加（无兜底）
        biz = biz_by_region.get(rid, {"avg_score": 70.0, "avg_coverage": 70.0})
        avg_s = biz["avg_score"]
        avg_cv = biz["avg_coverage"]
        biz_risk = max(0, min(100, 100 - avg_s))
        # 保险增信/减险逻辑
        if avg_cv >= 90:
            biz_risk -= 10  # 高保险覆盖率：银行风险显著降低（有充分兜底）
        elif avg_cv >= 80:
            biz_risk -= 5   # 较高覆盖率：银行风险适度降低
        elif avg_cv < 60:
            biz_risk += 15  # 低覆盖率：无兜底，银行风险增加
        elif avg_cv < 75:
            biz_risk += 5   # 中等覆盖率：兜底不足，风险略增
        biz_risk = max(0, min(100, biz_risk))

        # --- 金融特征 ---
        fin_risk = fin_by_region.get(rid, 50.0)

        # --- 构造特征 ---
        feat = [
            avg_temp, sum_precip, avg_wind, max_snow,
            worst_cold, worst_storm, worst_drought,
            avg_ndvi, avg_ndvi_change, avg_veg, max_snow_cov,
            worst_deg, avg_cap,
            avg_s, avg_cv, fin_risk,
        ]
        X_rows.append(feat)

        total = wx_score * 0.30 + rm_score * 0.25 + biz_risk * 0.20 + fin_risk * 0.25
        y_rows.append(total)

        sample_meta.append({
            "region_id": rid,
            "region_name": region_names.get(rid, rid),
            "month": month,
            "weather_count": len(wx_list),
            "remote_count": len(rm_list),
        })

    X = np.array(X_rows, dtype=np.float64)
    y = np.array(y_rows, dtype=np.float64)

    # 数据来源统计 —— 自动统计所有来源类型
    ds_counts: dict[str, int] = {}
    for row in weather_rows + remote_rows + subject_rows + finance_rows:
        src = str(row.get("data_source", "sample")).lower().strip()
        ds_counts[src] = ds_counts.get(src, 0) + 1
    # 检查 is_sample 标记
    non_sample_rows = sum(1 for row in weather_rows + remote_rows + subject_rows + finance_rows if str(row.get("is_sample", "true")).lower() not in ("true", "1", "yes", "t"))
    # 真实数据 = 明确标记为真实来源的行
    real_sources = {"tpdc", "modis", "cma", "real", "gldas", "era5", "ncep"}
    real_rows = sum(v for k, v in ds_counts.items() if k in real_sources or (k not in ("sample", "simulated", "csv") and k != ""))

    region_ids = sorted(set(m["region_id"] for m in sample_meta))
    months = sorted(set(m["month"] for m in sample_meta))

    info = {
        "n_samples": len(sample_meta),
        "n_features": X.shape[1],
        "county_count": len(region_ids),
        "month_count": len(months),
        "feature_names": FEATURE_NAMES,
        "regions": region_ids,
        "months": months,
        "data_source_counts": ds_counts,
        "total_rows": len(weather_rows) + len(remote_rows) + len(subject_rows) + len(finance_rows),
        "real_rows": real_rows,
        "sample_rows": ds_counts.get("sample", 0),
        "simulated_rows": ds_counts.get("simulated", 0),
    }
    return X, y, sample_meta, info


# ---------------------------------------------------------------------------
# 风险模型
# ---------------------------------------------------------------------------

class RiskModel:
    def __init__(self) -> None:
        self._X: np.ndarray | None = None
        self._y: np.ndarray | None = None
        self._sample_meta: list[dict] = []
        self._info: dict[str, Any] = {}
        self._trained = False
        self._trained_at: str | None = None
        self._model_type = "rule"
        self._clf: Any = None
        self._reg: Any = None
        self._scaler: Any = None
        self._confidence = 0.0
        self._eval_metrics: dict[str, Any] = {}
        self._warnings: list[str] = []

        self._rule_importance = np.array([
            0.10, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05,
            0.10, 0.05, 0.02, 0.03, 0.08, 0.02,
            0.12, 0.08, 0.10,
        ], dtype=np.float64)
        self._rule_importance /= self._rule_importance.sum()

    # ------------------------------------------------------------------
    # 数据级缺口检测
    # ------------------------------------------------------------------

    def _add_data_gap_warnings(self) -> None:
        """检查各数据表的字段级缺口，补入 _warnings。"""
        remote_rows = _load_table("remote_sensing_data")
        if remote_rows:
            n = len(remote_rows)
            deg_empty = sum(1 for r in remote_rows if str(r.get("degradation_level", "")).strip() in ("", "待评估"))
            cap_empty = sum(1 for r in remote_rows if str(r.get("carrying_capacity_sheep_unit", "")).strip() == "")
            snow_zero = sum(1 for r in remote_rows if str(r.get("snow_cover", "0%")).replace("%", "").strip() in ("0", "0%", ""))
            veg_estimated = sum(1 for r in remote_rows if str(r.get("vegetation_cover", "50%")).strip() == "50%")

            if deg_empty == n:
                self._warnings.append("遥感: 草地退化等级尚未接入 (degradation_level 全部为待评估)")
            if cap_empty == n:
                self._warnings.append("遥感: 载畜量数据尚未接入 (carrying_capacity_sheep_unit 全部为空)")
            else:
                # 检查是否为样例/衍生数据
                cap_demo = sum(1 for r in remote_rows if str(r.get("capacity_is_sample", "false")).lower() in ("true", "1", "yes", "t"))
                cap_derived = sum(1 for r in remote_rows if str(r.get("capacity_derived", "false")).lower() in ("true", "1", "yes", "t"))
                if cap_demo > 0:
                    self._warnings.append("载畜量: 当前使用样例/演示 NPP 派生数据, 仅用于流程验证, 待真实 TPDC NPP 替换")
                elif cap_derived > 0:
                    self._warnings.append("载畜量: 由 NPP 衍生估算 (derived), 非实测值")
            if snow_zero == n:
                self._warnings.append("遥感: 积雪数据尚未接入 (snow_cover 全部为默认值)")
            elif snow_zero > n * 0.5:
                self._warnings.append(f"遥感: 积雪数据覆盖不足 ({snow_zero}/{n} 行为默认值)")
            if veg_estimated > n * 0.8:
                self._warnings.append("遥感: 植被覆盖度可能由 NDVI 估算, 建议接入独立 FVC")

        subj_rows = _load_table("business_subjects")
        if subj_rows:
            sample_n = sum(1 for r in subj_rows if str(r.get("data_source", "")).lower() == "sample")
            if sample_n == len(subj_rows):
                self._warnings.append("经营主体: 全部为样例数据, 未接入真实经营台账")

        fin_rows = _load_table("finance_credit")
        if fin_rows:
            sample_n = sum(1 for r in fin_rows if str(r.get("data_source", "")).lower() == "sample")
            if sample_n == len(fin_rows):
                self._warnings.append("金融保险: 全部为样例数据, 未接入真实授信/保单记录")

    def macro_background(self) -> dict[str, Any]:
        """宏观背景数据摘要（不参与训练，仅供解释）。"""
        forage_rows = _load_table("forage_supply_demand")
        risk_rows = _load_table("risk_event_labels")
        return {
            "forage_supply_demand": {
                "available": len(forage_rows) > 0,
                "row_count": len(forage_rows),
                "note": "全国/区域年度宏观饲草供需 (Geodoi), 不参与县域训练, 仅作宏观背景参考。",
            },
            "risk_event_labels": {
                "available": len(risk_rows) > 0,
                "row_count": len(risk_rows),
                "real_count": sum(1 for r in risk_rows if r.get("is_real_label")),
                "sample_count": sum(1 for r in risk_rows if not r.get("is_real_label")),
                "note": self._risk_labels_note(risk_rows),
            },
        }

    @staticmethod
    def _risk_labels_note(risk_rows: list[dict[str, Any]]) -> str:
        """生成风险标签说明文本。"""
        if not risk_rows:
            return "真实灾害/理赔/逾期标签, 当前为空, 模型使用规则标签。"
        real_n = sum(1 for r in risk_rows if r.get("is_real_label"))
        sample_n = len(risk_rows) - real_n
        if real_n == 0:
            return f"{len(risk_rows)} 条 demo/sample 标签，仅用于跑通标签链路；不作为真实监督标签。"
        parts = [f"共 {len(risk_rows)} 条标签：{real_n} 条真实事件标签（来源：应急管理部公报/气候公报/县政府通报）"]
        if sample_n > 0:
            parts.append(f"{sample_n} 条 demo 样例标签")
        parts.append("真实标签含牲畜死亡/降水极值/低温冻害等事件，附 source_url 可溯源")
        return "；".join(parts) + "。"

    # ------------------------------------------------------------------
    # 训练
    # ------------------------------------------------------------------

    def train(self) -> dict[str, Any]:
        X, y, meta, info = _extract_monthly_samples()

        # ---- 来源支持的事件融合 ----
        # 只使用带来源 URL 的公开事件；“未检索到报道”不是负标签。
        real_labels_path = Path(__file__).parent / "data_store" / "real_labels_1500.json"
        real_label_count = 0
        if real_labels_path.exists():
            try:
                with open(real_labels_path, 'r', encoding='utf-8') as f:
                    real_labels = json.load(f)
                # 构建 (region_id, month) → 来源支持事件映射
                real_map = {}
                for rl in real_labels:
                    if not rl.get('source_url'):
                        continue
                    key = (rl.get('region_id', ''), rl.get('month', ''))
                    real_map[key] = rl

                # 融合：对每个样本，如果有真实标签则覆盖
                for i, m in enumerate(meta):
                    key = (m.get('region_id', ''), m.get('month', ''))
                    if key in real_map:
                        rl = real_map[key]
                        old_y = y[i]
                        new_y = float(rl.get('risk_score', old_y))
                        # 来源支持事件覆盖规则标签
                        y[i] = new_y
                        m['has_source_event_label'] = True
                        m['real_event_type'] = rl.get('event_type', '')
                        m['real_severity'] = rl.get('severity', '')
                        real_label_count += 1
                    else:
                        m['has_source_event_label'] = False
            except Exception as e:
                print(f"[train] 真实标签融合失败: {e}", file=sys.stderr)

        self._X = X
        self._y = y
        self._sample_meta = meta
        self._info = info
        self._real_label_count = real_label_count
        self._trained_at = datetime.now(timezone.utc).isoformat()
        self._trained = True
        self._warnings = []

        n = info["n_samples"]
        county_count = info["county_count"]
        month_count = info["month_count"]

        # 数据质量检查
        if n < 50:
            self._warnings.append(f"样本不足 (当前 {n}，需要 >= 50)。仅使用规则模型，不具备机器学习泛化评估意义。")
            self._warnings.append(f"推荐至少 10 县 × 24 个月 = 240 条样本。当前 {county_count} 县 × {month_count} 月 = {n} 条。")
        real_ratio = info.get("real_rows", 0) / max(1, info.get("total_rows", 1))
        if real_ratio < 0.5 and n > 0:
            self._warnings.append(f"真实数据占比过低 ({real_ratio:.0%})，多数为样例数据，模型泛化能力有限。")
        if county_count < 5:
            self._warnings.append(f"县域数量不足 ({county_count})，建议至少覆盖 10 个高原牧区县。")

        if real_label_count > 0:
            self._warnings.append(
                f"已融合 {real_label_count} 条带来源 URL 的公开灾害事件；其余月份保持未知，不作为真实无灾标签。"
            )

        # ---- 数据级缺口检测 ----
        self._add_data_gap_warnings()

        if n >= 50 and _HAS_SKLEARN:
            try:
                self._scaler = StandardScaler()
                X_scaled = self._scaler.fit_transform(X)

                y_cls = np.array(["低" if v < 50 else "中" if v < 70 else "高" for v in y])

                # 类别不平衡处理：给有真实标签的样本更高权重
                sample_weights = np.ones(n)
                for i, m in enumerate(meta):
                    if m.get('has_source_event_label'):
                        sample_weights[i] = 5.0  # 来源支持事件权重5倍

                self._clf = RandomForestClassifier(
                    n_estimators=min(100, max(20, n // 3)),
                    max_depth=6,
                    random_state=42,
                    class_weight='balanced'
                )
                self._clf.fit(X_scaled, y_cls, sample_weight=sample_weights)

                self._reg = Ridge(alpha=1.0)
                self._reg.fit(X_scaled, y, sample_weight=sample_weights)

                self._model_type = "ml_hybrid"
                if hasattr(self._clf, "feature_importances_"):
                    ml_imp = self._clf.feature_importances_
                    self._rule_importance = (self._rule_importance + ml_imp) / 2.0
                    self._rule_importance /= self._rule_importance.sum()

                # 基础评估
                if n >= 100:
                    X_tr, X_te, y_tr, y_te, sw_tr, sw_te = train_test_split(
                        X_scaled, y, sample_weights, test_size=0.2, random_state=42
                    )
                    self._reg.fit(X_tr, y_tr, sample_weight=sw_tr)
                    y_pred = self._reg.predict(X_te)
                    self._eval_metrics = {
                        "mae": round(float(mean_absolute_error(y_te, y_pred)), 2),
                        "rmse": round(float(np.sqrt(mean_squared_error(y_te, y_pred))), 2),
                        "r2": round(float(r2_score(y_te, y_pred)), 3),
                        "test_samples": len(y_te),
                        "real_labels_used": real_label_count,
                    }
                else:
                    try:
                        cv_scores = cross_val_score(self._reg, X_scaled, y, cv=min(3, n), scoring="neg_mean_absolute_error")
                        self._eval_metrics = {"cv_mae": round(float(-np.mean(cv_scores)), 2), "cv_folds": min(3, n)}
                    except Exception:
                        self._eval_metrics = {}

                # 置信度（有真实标签时提升）
                if n >= 300: self._confidence = 0.75 if real_label_count > 0 else 0.7
                elif n >= 100: self._confidence = 0.55 if real_label_count > 0 else 0.5
                else: self._confidence = 0.4 if real_label_count > 0 else 0.35
            except Exception:
                self._model_type = "rule"
                self._confidence = 0.2
                self._warnings.append("ML 训练失败，降级为规则模型。")
        else:
            self._model_type = "rule"
            self._confidence = 0.15 if n < 20 else 0.25

        return self.status()

    # ------------------------------------------------------------------
    # 预测
    # ------------------------------------------------------------------

    def predict(self) -> dict[str, Any]:
        if not self._trained:
            self.train()

        predictions = []
        for i, meta in enumerate(self._sample_meta):
            feat = self._X[i]
            y_true = float(self._y[i])

            if self._model_type == "ml_hybrid" and self._reg is not None and self._scaler is not None:
                X_scaled = self._scaler.transform(feat.reshape(1, -1))
                y_pred = float(self._reg.predict(X_scaled)[0])
                y_pred = max(0, min(100, y_pred))
            else:
                y_pred = y_true

            level = "高" if y_pred >= 70 else "中" if y_pred >= 50 else "低"

            drivers = {
                "weather": {
                    "score_part": round(max(feat[4], feat[5], feat[6]) * 35 * 0.30),
                    "detail": f"寒潮={_risk_decode(feat[4])}, 暴雪={_risk_decode(feat[5])}, 干旱={_risk_decode(feat[6])}",
                },
                "remote": {
                    "score_part": round(((1.0 - feat[7]) * 50 + feat[11] * 12 + (feat[8] < -5) * 10) * 0.25),
                    "detail": f"NDVI={feat[7]:.2f}(Δ{feat[8]:+.1f}%), 退化={_deg_decode(feat[11])}",
                },
                "business": {
                    "score_part": round((max(0, min(100, 100 - feat[13] + (5 if feat[14] < 75 else 0) + (15 if feat[14] < 60 else 0) - (5 if feat[14] >= 80 else 0) - (10 if feat[14] >= 90 else 0)))) * 0.20),
                    "detail": f"评分={feat[13]:.0f}, 保险覆盖率={feat[14]:.0f}%",
                },
                "finance": {
                    "score_part": round(feat[15] * 0.25),
                    "detail": f"金融风险分={feat[15]:.0f}",
                },
            }

            predictions.append({
                "region_id": meta["region_id"],
                "region_name": meta.get("region_name", ""),
                "month": meta["month"],
                "predicted_score": round(y_pred, 1),
                "predicted_level": level,
                "rule_score": round(y_true, 1),
                "drivers": drivers,
            })

        # 按区域聚合最新预测
        latest_by_region: dict[str, dict] = {}
        for p in predictions:
            rid = p["region_id"]
            if rid not in latest_by_region or p["month"] > latest_by_region[rid].get("month", ""):
                latest_by_region[rid] = p

        return {
            "model_type": self._model_type,
            "trained_at": self._trained_at,
            "n_samples": self._info["n_samples"],
            "county_count": self._info["county_count"],
            "month_count": self._info["month_count"],
            "confidence": round(self._confidence, 2),
            "predictions": predictions,
            "latest_by_region": list(latest_by_region.values()),
        }

    # ------------------------------------------------------------------
    # 特征重要性
    # ------------------------------------------------------------------

    def feature_importance(self) -> list[dict[str, Any]]:
        if not self._trained:
            self.train()
        return [
            {"feature": FEATURE_NAMES[i], "importance": round(float(self._rule_importance[i]), 4),
             "category": "气象" if i < 7 else "遥感" if i < 13 else "经营" if i < 15 else "金融"}
            for i in range(len(FEATURE_NAMES))
        ]

    # ------------------------------------------------------------------
    # SHAP 可解释性 — 生成农户/区域风险解释报告
    # ------------------------------------------------------------------

    def explain_prediction(self, region_id: str, top_k: int = 8) -> dict[str, Any]:
        """为指定区域生成 SHAP 风险解释报告。

        返回:
          - region_id, region_name
          - base_value: 训练集平均预测风险分
          - prediction: 当前预测风险分
          - top_drivers: 贡献最大的 top_k 个特征（含方向）
          - full_explanation: 全部16维特征的SHAP值
          - summary: 自然语言风险摘要
          - recommendations: 基于解释的针对性建议
        """
        if not self._trained:
            self.train()

        # 找到该区域的样本索引
        idx_list = [i for i, m in enumerate(self._sample_meta) if m["region_id"] == region_id]
        if not idx_list:
            return {"error": f"无数据: {region_id}", "region_id": region_id}

        # 取最新样本
        idx = idx_list[-1]
        feat = self._X[idx]
        meta = self._sample_meta[idx]

        # 计算预测值
        if self._model_type == "ml_hybrid" and self._reg is not None and self._scaler is not None:
            X_scaled = self._scaler.transform(feat.reshape(1, -1))
            prediction = float(self._reg.predict(X_scaled)[0])
            prediction = max(0, min(100, prediction))
        else:
            prediction = float(self._y[idx])

        # SHAP 解释
        shap_values = None
        base_value = float(np.mean(self._y)) if self._y is not None else 50.0

        if _HAS_SHAP and self._model_type == "ml_hybrid" and self._reg is not None:
            try:
                # 用TreeExplainer（RF/Ridge兼容）
                if hasattr(self._reg, 'estimators_'):
                    explainer = shap.TreeExplainer(self._reg)
                    X_scaled = self._scaler.transform(self._X)
                    shap_values = explainer.shap_values(X_scaled)
                    base_value = float(explainer.expected_value)
                    if isinstance(shap_values, list):
                        shap_values = shap_values[0]
                    sample_shap = shap_values[idx]
                else:
                    # Ridge 用 KernelExplainer（采样背景数据）
                    background = self._scaler.transform(self._X[:min(100, len(self._X))])
                    explainer = shap.KernelExplainer(self._reg.predict, background)
                    sample_shap = explainer.shap_values(X_scaled)[0]
                    base_value = float(explainer.expected_value)
            except Exception as e:
                # SHAP 失败时用规则权重近似
                sample_shap = (feat - np.mean(self._X, axis=0)) * self._rule_importance
        else:
            # 无 SHAP 或非 ML 模型，用规则权重近似
            feat_mean = np.mean(self._X, axis=0) if self._X is not None else np.zeros_like(feat)
            sample_shap = (feat - feat_mean) * self._rule_importance

        # 构建特征解释列表
        explanations = []
        for i in range(len(FEATURE_NAMES)):
            explanations.append({
                "feature": FEATURE_NAMES[i],
                "feature_value": round(float(feat[i]), 4),
                "shap_value": round(float(sample_shap[i]), 4),
                "contribution": "正向(增险)" if sample_shap[i] > 0 else "负向(减险)" if sample_shap[i] < 0 else "中性",
                "category": "气象" if i < 7 else "遥感" if i < 13 else "经营" if i < 15 else "金融",
            })

        # 按绝对值排序取 top_k
        explanations_sorted = sorted(explanations, key=lambda x: abs(x["shap_value"]), reverse=True)
        top_drivers = explanations_sorted[:top_k]

        # 生成自然语言摘要
        risk_level = "高" if prediction >= 70 else "中" if prediction >= 50 else "低"
        top_pos = [e for e in top_drivers if e["shap_value"] > 0][:3]
        top_neg = [e for e in top_drivers if e["shap_value"] < 0][:3]

        summary_parts = [f"区域 {meta.get('region_name', region_id)} 当前风险等级：{risk_level}（预测分 {prediction:.1f}）。"]
        if top_pos:
            pos_desc = "、".join([f"{e['feature']}={e['feature_value']}" for e in top_pos])
            summary_parts.append(f"主要增险因素：{pos_desc}。")
        if top_neg:
            neg_desc = "、".join([f"{e['feature']}={e['feature_value']}" for e in top_neg])
            summary_parts.append(f"主要减险因素：{neg_desc}。")

        # 生成针对性建议
        recommendations = self._generate_recommendations(top_drivers, prediction)

        return {
            "region_id": region_id,
            "region_name": meta.get("region_name", region_id),
            "month": meta.get("month", ""),
            "base_value": round(base_value, 2),
            "prediction": round(prediction, 2),
            "risk_level": risk_level,
            "model_type": self._model_type,
            "shap_available": _HAS_SHAP and self._model_type == "ml_hybrid",
            "top_drivers": top_drivers,
            "full_explanation": explanations,
            "summary": "".join(summary_parts),
            "recommendations": recommendations,
        }

    def _generate_recommendations(self, top_drivers: list[dict], prediction: float) -> list[str]:
        """基于 SHAP 解释生成针对性建议。"""
        recs = []
        driver_features = {d["feature"]: d for d in top_drivers}

        # 气象类建议
        if "snow_depth_cm" in driver_features and driver_features["snow_depth_cm"]["shap_value"] > 0:
            recs.append("积雪深度偏高：建议提前储备60天以上饲草料，加强棚圈保暖设施")
        if "cold_wave_risk" in driver_features and driver_features["cold_wave_risk"]["shap_value"] > 0:
            recs.append("寒潮风险较高：关注天气预报，极端低温时增加补饲频次")
        if "snowstorm_risk" in driver_features and driver_features["snowstorm_risk"]["shap_value"] > 0:
            recs.append("暴雪风险较高：建议购买畜牧险，转移自然灾害风险")
        if "drought_risk" in driver_features and driver_features["drought_risk"]["shap_value"] > 0:
            recs.append("干旱风险偏高：优化草场轮牧计划，避免过度放牧")

        # 遥感类建议
        if "ndvi" in driver_features and driver_features["ndvi"]["shap_value"] > 0:
            recs.append("NDVI偏低：草场长势不佳，建议延长休牧期或补播改良")
        if "degradation_level" in driver_features and driver_features["degradation_level"]["shap_value"] > 0:
            recs.append("草地退化严重：实施草畜平衡，核定载畜量不超过理论值的80%")
        if "snow_cover_pct" in driver_features and driver_features["snow_cover_pct"]["shap_value"] > 0:
            recs.append("积雪覆盖率偏高：影响牲畜采食，建议人工补饲")

        # 经营类建议
        if "avg_insurance_coverage" in driver_features and driver_features["avg_insurance_coverage"]["shap_value"] > 0:
            recs.append("保险覆盖率偏低：建议提高参保率至80%以上，增强风险兜底能力")
        if "avg_score" in driver_features and driver_features["avg_score"]["shap_value"] > 0:
            recs.append("经营评分偏低：加强合作社规范化管理，提升信用等级")

        # 金融类建议
        if "finance_risk_score" in driver_features and driver_features["finance_risk_score"]["shap_value"] > 0:
            recs.append("金融风险偏高：关注还款能力，必要时调整贷款期限或增加担保")

        # 综合建议
        if prediction >= 70:
            recs.append("综合风险较高：建议暂缓新增贷款，加强贷后监控频次至每周一次")
        elif prediction >= 50:
            recs.append("综合风险中等：可适度放贷，但需设置风险预警阈值")
        else:
            recs.append("综合风险较低：可正常开展信贷业务，保持季度复查")

        return recs if recs else ["当前无明显风险驱动因素，保持常规监控即可"]

    def explain_batch(self, region_ids: list[str] | None = None) -> list[dict[str, Any]]:
        """批量生成风险解释报告。"""
        if not self._trained:
            self.train()
        if region_ids is None:
            region_ids = list(set(m["region_id"] for m in self._sample_meta))
        return [self.explain_prediction(rid) for rid in region_ids if rid]

    # ------------------------------------------------------------------
    # 趋势预测
    # ------------------------------------------------------------------

    def forecast(self, region_id: str, days: int = 30) -> dict[str, Any]:
        if not self._trained:
            self.train()

        remote_rows = [r for r in _load_table("remote_sensing_data") if r.get("region_id") == region_id]
        now = datetime.now(timezone.utc)
        days_list = list(range(0, days + 1, 7))

        current_pred = 50.0
        for i, meta in enumerate(self._sample_meta):
            if meta["region_id"] == region_id:
                if self._model_type == "ml_hybrid" and self._reg is not None and self._scaler is not None:
                    current_pred = float(self._reg.predict(self._scaler.transform(self._X[i].reshape(1, -1)))[0])
                else:
                    current_pred = float(self._y[i])
                current_pred = max(0, min(100, current_pred))
                break

        ndvi_vals = []
        for r in remote_rows:
            try:
                ndvi_vals.append((r.get("scene_date", ""), float(r.get("ndvi", 0.4))))
            except (ValueError, TypeError):
                pass
        ndvi_vals.sort(key=lambda x: x[0])

        trend_slope = 0.0
        if len(ndvi_vals) >= 2:
            t0 = datetime.strptime(ndvi_vals[0][0], "%Y-%m-%d")
            tn = datetime.strptime(ndvi_vals[-1][0], "%Y-%m-%d")
            days_diff = max(1, (tn - t0).days)
            trend_slope = (ndvi_vals[-1][1] - ndvi_vals[0][1]) / days_diff

        forecast_points = []
        rng = np.random.RandomState(42)
        for d in days_list:
            date = (now + timedelta(days=d)).strftime("%Y-%m-%d")
            seasonal = 5 * math.sin(2 * math.pi * d / 365)
            trend_effect = -trend_slope * d * 50
            noise = rng.normal(0, 2)
            score = current_pred + seasonal + trend_effect + noise
            score = max(0, min(100, score))
            level = "高" if score >= 70 else "中" if score >= 50 else "低"
            forecast_points.append({"date": date, "predicted_score": round(score, 1), "predicted_level": level, "days_from_now": d})

        return {
            "region_id": region_id,
            "current_score": round(current_pred, 1),
            "current_level": "高" if current_pred >= 70 else "中" if current_pred >= 50 else "低",
            "trend": "上升" if trend_slope < -0.0005 else "下降" if trend_slope > 0.0005 else "稳定",
            "forecast_days": days,
            "points": forecast_points,
            "confidence_interval_lower": [max(0, fp["predicted_score"] - 10) for fp in forecast_points],
            "confidence_interval_upper": [min(100, fp["predicted_score"] + 10) for fp in forecast_points],
            "data_points_used": len(remote_rows),
        }

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        n = self._info.get("n_samples", 0)
        if n < 50:
            note = f"规则模型 (样本不足 50, 当前 {n})"
        elif n < 300:
            note = f"基础 ML (样本 {n}, 50-300, 置信度较低)"
        else:
            note = f"ML 模型 (样本 {n}, >=300, 较稳定)"
        return {
            "trained": self._trained,
            "trained_at": self._trained_at,
            "model_type": self._model_type,
            "label_type": "rule_label",
            "n_samples": n,
            "n_features": self._info.get("n_features", 16),
            "county_count": self._info.get("county_count", 0),
            "month_count": self._info.get("month_count", 0),
            "total_rows": self._info.get("total_rows", 0),
            "real_rows": self._info.get("real_rows", 0),
            "sample_rows": self._info.get("sample_rows", 0),
            "real_data_ratio": round(self._info.get("real_rows", 0) / max(1, self._info.get("total_rows", 1)), 2),
            "data_source_counts": self._info.get("data_source_counts", {}),
            "confidence": round(self._confidence, 2),
            "sklearn_available": _HAS_SKLEARN,
            "note": note,
            "data_quality_warnings": self._warnings,
        }

    def label_info(self) -> dict[str, Any]:
        """返回模型标签来源说明。"""
        return {
            "label_type": "weak_label_with_source_events",
            "has_real_disaster_labels": True,
            "real_disaster_label_count": 42,
            "unknown_month_count": 1458,
            "has_real_claims_overdue_labels": False,
            "is_rule_risk_score": True,
            "label_features": [
                "气象风险评分 (寒潮/暴雪/干旱 等级映射)",
                "遥感生态风险评分 (NDVI + 退化等级)",
                "主体经营风险评分 (信用评分 + 保险覆盖率)",
                "金融保险风险评分 (还款状态 + 逾期次数)",
            ],
            "weak_label_available": True,
            "weak_label_description": (
                "基于真实环境异常构建的弱标签，加上42条带来源 URL 的公开灾害事件: "
                "低温异常、降水异常、NDVI同比下降、积雪高值、"
                "退化等级、载畜量低值。其余1458个月份为未确认状态，不等于真实无灾。"
            ),
            "note": (
                "当前模型是'环境数据 + 规则弱标签 + 少量来源支持事件'的筛查模型，"
                "不应宣称已经完成真实灾害预测或贷款逾期预测。"
                "如需业务效果评估，需要接入完整灾害、保险理赔和银行逾期记录。"
            ),
        }

    # ------------------------------------------------------------------
    # 评估
    # ------------------------------------------------------------------

    def evaluation(self) -> dict[str, Any]:
        if not self._trained:
            self.train()
        n = self._info["n_samples"]
        result: dict[str, Any] = {
            "model_type": self._model_type,
            "n_samples": n,
            "n_features": self._info.get("n_features", 16),
            "county_count": self._info.get("county_count", 0),
            "month_count": self._info.get("month_count", 0),
            "train_samples": n,
            "test_samples": 0,
            "metrics": {},
            "cross_validation_available": n >= 9,
            "data_quality_warnings": self._warnings,
            "evaluation_note": "",
        }

        if n < 50:
            result["evaluation_note"] = "样本不足，仅规则模型，不具备机器学习泛化评估意义。"
        elif self._model_type == "rule":
            result["evaluation_note"] = "当前使用规则模型（sklearn 不可用或训练失败）。"
        elif self._eval_metrics:
            result["metrics"] = self._eval_metrics
            if "test_samples" in self._eval_metrics:
                result["test_samples"] = self._eval_metrics["test_samples"]
            result["evaluation_note"] = "评估完成。指标基于规则标签计算，需真实标签验证。"
        else:
            result["evaluation_note"] = "样本数 50-100，不具备可靠评估条件。"

        return result


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _risk_decode(v: float) -> str:
    if v >= 2: return "高"
    if v >= 1: return "中"
    return "低"


def _deg_decode(v: float) -> str:
    if v >= 3: return "重度退化"
    if v >= 2: return "中度退化"
    if v >= 1: return "轻度退化"
    return "基本稳定"


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_model: RiskModel | None = None


def get_model() -> RiskModel:
    global _model
    if _model is None:
        _model = RiskModel()
        _model.train()
    return _model


def reset_model() -> RiskModel:
    global _model
    _model = RiskModel()
    _model.train()
    return _model
