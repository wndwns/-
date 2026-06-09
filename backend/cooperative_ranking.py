"""
牧融绿链 — 潍坊模式：公共数据企业筛选排序
============================================================================
核心理念:
  把工商数据 + 遥感生态数据 + 气象历史数据融合，
  输出"该县最值得放贷的前 N 个合作社排序"。

当前状态:
  - 工商 API 需要企业认证，牧区在线数据可能不完整
  - 采用高仿真模拟数据 + 真实遥感/气象/NPP 跑通完整算法链路
  - 预留工商 API 接入接口，数据到位即可切换

评分公式:
  综合得分 = 0.40×工商维度 + 0.30×生态维度 + 0.20×气象维度 + 0.10×经营维度

工商维度:
  - 注册资本 (25%): 归一化 0-100
  - 社保人数 (20%): 有社保=高分, 无社保=低分
  - 纳税记录 (25%): 正常=100, 欠税=0
  - 无行政处罚 (15%): 0次=100, 3+次=0
  - 成立年限 (15%): 5年+ =100, 1年=40

生态维度:
  - NPP 草场质量 (50%): 从 MODIS NPP 数据获取
  - NDVI 植被趋势 (30%): 正趋势高分
  - 退化程度 (20%): 未退化=100, 重度=30

气象维度:
  - 灾害频率倒数 (60%): 受灾次数越少越高
  - 积雪稳定性 (40%): 积雪天数越少越高

经营维度:
  - 存栏规模 (40%): 归一化
  - 草场面积 (30%): 归一化
  - 历史信用 (30%): 还款记录评分
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

_STORE_DIR = Path(__file__).resolve().parent / "data_store"

# ── 合作社名称素材 ──
_TIBETAN_FIRST_NAMES = [
    "扎西", "格桑", "丹增", "洛桑", "顿珠", "卓玛", "索朗",
    "米玛", "白玛", "普布", "达瓦", "旺堆", "罗布", "央金",
    "次仁", "巴桑", "曲珍", "尼玛", "拉姆", "多吉", "平措",
    "桑珠", "才让", "仁青", "德吉", "贡布", "阿旺", "强巴",
]

_COOP_SUFFIXES = [
    "牧业合作社", "高原养殖合作社", "生态畜牧合作社",
    "牦牛养殖专业合作社", "藏羊繁育合作社", "农牧民专业合作社",
    "畜牧业联合社", "家庭牧场联合社", "草原生态合作社",
]

# ── 现有数据加载 ──
_npp_map: dict[str, dict[str, float]] = {}
_npp_loaded = False
_regions: list[dict[str, Any]] = []
_regions_loaded = False
_weather_data: list[dict[str, Any]] = []
_remote_data: list[dict[str, Any]] = []


def _load_npp():
    global _npp_map, _npp_loaded
    if _npp_loaded:
        return
    path = _STORE_DIR / "npp_by_region.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data:
            _npp_map[entry["region_id"]] = entry.get("npp_annual", {})
    _npp_loaded = True


def _load_regions():
    global _regions, _regions_loaded
    if _regions_loaded:
        return
    try:
        from .data import get_regions as _gr
    except ImportError:
        try:
            from data import get_regions as _gr
        except ImportError:
            _regions = []
            _regions_loaded = True
            return
    _regions = _gr()
    _regions_loaded = True


def _load_weather():
    global _weather_data
    if _weather_data:
        return
    try:
        from .data import get_weather as _gw
    except ImportError:
        try:
            from data import get_weather as _gw
        except ImportError:
            return
    _weather_data.extend(_gw())


def _load_remote():
    global _remote_data
    if _remote_data:
        return
    try:
        from .data import get_remote_sensing as _grs
    except ImportError:
        try:
            from data import get_remote_sensing as _grs
        except ImportError:
            return
    _remote_data.extend(_grs())


# ── 真实合作社数据加载 ──
_real_coops: dict[str, list[dict[str, Any]]] = {}
_real_coops_loaded = False


def _load_real_cooperatives():
    """加载真实合作社数据（仅班戈县，逐县补充）。"""
    global _real_coops, _real_coops_loaded
    if _real_coops_loaded:
        return
    path = _STORE_DIR / "real_cooperatives.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        # 新格式: {"_meta": {...}, "cooperatives": [...]}
        coops = data.get("cooperatives", data if isinstance(data, list) else [])
        for coop in coops:
            rid = coop["region_id"]
            _real_coops.setdefault(rid, []).append(coop)
    _real_coops_loaded = True


# ── 合作社数据生成（真实 + 模拟混合） ──

def _generate_cooperatives_for_county(region: dict[str, Any]) -> list[dict[str, Any]]:
    """生成一个县的合作社数据。优先使用真实数据，不足时模拟补充。"""
    _load_real_cooperatives()
    rid = region["id"]
    rname = region["name"]

    # 加载真实数据
    real_list = _real_coops.get(rid, [])
    coops = list(real_list)  # 复制真实数据

    # 如果真实数据不足 8 个，模拟补充
    if len(coops) < 8:
        province = region.get("province", "西藏自治区")
        altitude = int(region.get("altitude", 4500))

        rng = random.Random(rid + "_sim")  # 独立种子，不影响真实数据
        if altitude >= 4700:
            extra = rng.randint(8 - len(coops), 12 - len(coops))
        elif altitude >= 4000:
            extra = rng.randint(8 - len(coops), 12 - len(coops))
        else:
            extra = rng.randint(8 - len(coops), 12 - len(coops))
        extra = max(2, extra)

        digit_factor = 0.7 if "西藏" in province else 1.0
        used_names = {c["name"] for c in coops}

        for i in range(extra):
            for _ in range(100):
                first = rng.choice(_TIBETAN_FIRST_NAMES)
                suffix = rng.choice(_COOP_SUFFIXES)
                name = f"{rname}{first}{suffix}"
                if name not in used_names:
                    used_names.add(name)
                    break
            else:
                name = f"{rname}第{i + 1}{rng.choice(_COOP_SUFFIXES)}"

            registered_capital = rng.choice([30, 50, 80, 100, 150, 200, 300, 500, 800, 1000])
            social_security_count = max(0, int(rng.gauss(3.5 * digit_factor, 2.5)))
            tax_compliant = rng.random() < (0.75 * digit_factor + 0.1)
            penalty_count = 0 if rng.random() < 0.7 else rng.randint(1, 3)
            years_since_establishment = rng.randint(1, 12)
            cattle = rng.randint(50, 2000)
            sheep = rng.randint(100, 5000)
            grassland_mu = rng.randint(5000, 120000)
            overdue_times = max(0, int(rng.gauss(0.8, 1.2)))
            credit_limit = rng.choice([50, 80, 100, 150, 200, 300, 500])

            coops.append({
                "name": name,
                "region_id": rid,
                "region_name": rname,
                "province": province,
                "pasture_type": region.get("pasture_type", "高寒草甸"),
                "altitude": altitude,
                "biz_registered_capital_wan": registered_capital,
                "biz_social_security_count": social_security_count,
                "biz_tax_compliant": tax_compliant,
                "biz_penalty_count": penalty_count,
                "biz_years_established": years_since_establishment,
                "ops_cattle_count": cattle,
                "ops_sheep_count": sheep,
                "ops_grassland_mu": grassland_mu,
                "ops_overdue_times": overdue_times,
                "ops_credit_limit_wan": credit_limit,
                "data_source": "simulated",
            })

    return coops


def _generate_cooperatives_for_county_old(region: dict[str, Any]) -> list[dict[str, Any]]:
    """为一个县生成 12-18 个合作社的工商数据。

    基于县域特征（海拔、草地类型、省份）生成差异化数据：
      - 高海拔县：合作社数量偏少但规模偏大
      - 青海/四川/甘肃：数字化程度略高于西藏
    """
    rid = region["id"]
    rname = region["name"]
    province = region.get("province", "西藏自治区")
    pasture = region.get("pasture_type", "高寒草甸")
    altitude = int(region.get("altitude", 4500))

    rng = random.Random(rid)  # 确定性随机，保证同县每次生成一致

    # 合作社数量：海拔越高越少
    if altitude >= 4700:
        count = rng.randint(8, 12)
    elif altitude >= 4000:
        count = rng.randint(12, 16)
    else:
        count = rng.randint(15, 18)

    # 数字化程度因子：青海/四川/甘肃 > 西藏
    digit_factor = 0.7 if "西藏" in province else 1.0

    cooperatives = []
    used_names: set[str] = set()

    for i in range(count):
        # 生成不重名合作社
        for _ in range(100):
            first = rng.choice(_TIBETAN_FIRST_NAMES)
            suffix = rng.choice(_COOP_SUFFIXES)
            name = f"{rname}{first}{suffix}"
            if name not in used_names:
                used_names.add(name)
                break
        else:
            name = f"{rname}第{i+1}{rng.choice(_COOP_SUFFIXES)}"

        # ── 工商维度 ──
        registered_capital = rng.choice([30, 50, 80, 100, 150, 200, 300, 500, 800, 1000])  # 万元
        social_security_count = max(0, int(rng.gauss(3.5 * digit_factor, 2.5)))
        # 西藏地区纳税数据更不完整
        tax_compliant = rng.random() < (0.75 * digit_factor + 0.1)
        penalty_count = 0 if rng.random() < 0.7 else rng.randint(1, 3)
        years_since_establishment = rng.randint(1, 12)

        # ── 经营维度 ──
        cattle = rng.randint(50, 2000)
        sheep = rng.randint(100, 5000)
        grassland_mu = rng.randint(5000, 120000)

        # 历史信用 (模拟还款记录)
        overdue_times = max(0, int(rng.gauss(0.8, 1.2)))
        credit_limit = rng.choice([50, 80, 100, 150, 200, 300, 500])

        cooperatives.append({
            "name": name,
            "region_id": rid,
            "region_name": rname,
            "province": province,
            "pasture_type": pasture,
            "altitude": altitude,
            # 工商数据
            "biz_registered_capital_wan": registered_capital,
            "biz_social_security_count": social_security_count,
            "biz_tax_compliant": tax_compliant,
            "biz_penalty_count": penalty_count,
            "biz_years_established": years_since_establishment,
            # 经营数据
            "ops_cattle_count": cattle,
            "ops_sheep_count": sheep,
            "ops_grassland_mu": grassland_mu,
            "ops_overdue_times": overdue_times,
            "ops_credit_limit_wan": credit_limit,
            "data_source": "simulated",
        })

    return cooperatives


# ── 评分算法 ──

def _norm(x: float, min_val: float, max_val: float) -> float:
    """归一化到 0-100。"""
    if max_val == min_val:
        return 50.0
    return max(0.0, min(100.0, (x - min_val) / (max_val - min_val) * 100.0))


def _score_biz(coop: dict[str, Any],
               cap_max: float, emp_max: float) -> tuple[float, dict[str, float]]:
    """工商维度评分 (0-100)。"""
    # 注册资本
    cap_score = _norm(coop["biz_registered_capital_wan"], 10, cap_max)
    # 社保人数
    emp_score = _norm(coop["biz_social_security_count"], 0, emp_max)
    # 纳税
    tax_score = 100.0 if coop["biz_tax_compliant"] else 30.0
    # 行政处罚 (反向)
    p = coop["biz_penalty_count"]
    penalty_score = 100.0 if p == 0 else (60.0 if p == 1 else (25.0 if p == 2 else 0.0))
    # 成立年限
    years_score = _norm(coop["biz_years_established"], 0.5, 12)

    detail = {
        "注册资本": round(cap_score, 1),
        "社保人数": round(emp_score, 1),
        "纳税记录": round(tax_score, 1),
        "无行政处罚": round(penalty_score, 1),
        "成立年限": round(years_score, 1),
    }
    total = 0.25 * cap_score + 0.20 * emp_score + 0.25 * tax_score + 0.15 * penalty_score + 0.15 * years_score
    return round(total, 1), detail


def _score_eco(coop: dict[str, Any], remote: dict[str, Any] | None) -> tuple[float, dict[str, float]]:
    """生态维度评分 (0-100)。

    使用 NPP 草场质量 + NDVI 趋势 + 退化程度。
    """
    rid = coop["region_id"]

    # NPP 得分 — 取最近年份
    _load_npp()
    annual = _npp_map.get(rid, {})
    years = sorted(int(y) for y in annual.keys())
    npp_val = annual.get(str(max(years)), 0.35) if years else 0.35
    npp_score = _norm(npp_val, 0.05, 2.5)  # NPP 范围 0.05-2.5

    # NDVI 趋势
    ndvi = 0.42
    ndvi_change = 0.0
    degradation = "中度退化"
    if remote:
        ndvi = float(remote.get("ndvi", 0.42))
        ndvi_str = remote.get("ndvi_change", "0%")
        try:
            ndvi_change = float(ndvi_str.replace("%", "").replace("+", ""))
        except (ValueError, AttributeError):
            ndvi_change = 0.0
        degradation = remote.get("degradation_level", "中度退化")

    ndvi_score = _norm(ndvi, 0.2, 0.7)
    trend_score = 50 + ndvi_change * 3  # 正趋势加分，负趋势扣分
    trend_score = max(10.0, min(100.0, trend_score))

    deg_map = {"基本稳定": 95, "轻度退化": 70, "中度退化": 45, "重度退化": 20}
    degradation_score = float(deg_map.get(degradation, 45))

    detail = {
        "NPP草场质量": round(npp_score, 1),
        "NDVI趋势": round(trend_score, 1),
        "退化程度": round(degradation_score, 1),
    }
    total = 0.50 * npp_score + 0.30 * trend_score + 0.20 * degradation_score
    return round(total, 1), detail


def _score_weather(coop: dict[str, Any]) -> tuple[float, dict[str, float]]:
    """气象维度评分 (0-100)。

    基于县域天气数据: 灾害风险越低越高分。
    """
    _load_weather()
    rid = coop["region_id"]
    region_weather = [w for w in _weather_data if w.get("region_id") == rid]
    if not region_weather:
        w = _weather_data[0] if _weather_data else {}
    else:
        w = region_weather[0]

    snow_cm = float(w.get("snow_depth_cm", 10))
    # 积雪深度 0cm=100, 30cm=0
    snow_score = max(0.0, 100.0 - snow_cm * 3.33)

    # 灾害风险: 低=100, 中=60, 高=30
    risk_map = {"低": 100, "中": 60, "高": 30}
    cold_wave = risk_map.get(w.get("cold_wave_risk", "中"), 60)
    snowstorm = risk_map.get(w.get("snowstorm_risk", "中"), 60)
    drought = risk_map.get(w.get("drought_risk", "低"), 100)

    disaster_score = (cold_wave + snowstorm + drought) / 3

    detail = {
        "积雪稳定性": round(snow_score, 1),
        "灾害风险": round(disaster_score, 1),
    }
    total = 0.40 * snow_score + 0.60 * disaster_score
    return round(total, 1), detail


def _score_ops(coop: dict[str, Any]) -> tuple[float, dict[str, float]]:
    """经营维度评分 (0-100)。"""
    # 存栏规模 (牦牛+藏羊折算)
    livestock = coop["ops_cattle_count"] * 1.0 + coop["ops_sheep_count"] * 0.3
    livestock_score = _norm(livestock, 50, 3000)

    # 草场面积
    grass_score = _norm(coop["ops_grassland_mu"], 2000, 120000)

    # 历史信用
    overdue = coop["ops_overdue_times"]
    credit_score = 100.0 if overdue == 0 else (70.0 if overdue == 1 else (40.0 if overdue == 2 else 10.0))

    detail = {
        "存栏规模": round(livestock_score, 1),
        "草场面积": round(grass_score, 1),
        "历史信用": round(credit_score, 1),
    }
    total = 0.40 * livestock_score + 0.30 * grass_score + 0.30 * credit_score
    return round(total, 1), detail


def rank_cooperatives(region_id: str, top_n: int = 50) -> list[dict[str, Any]]:
    """对指定县域的合作社进行综合排序。

    Args:
        region_id: 县域 ID，如 "naqu-bange"
        top_n: 返回前 N 名

    Returns:
        排序后的合作社列表，含各项评分明细
    """
    _load_regions()
    _load_weather()
    _load_remote()

    # 找到对应县域
    region = next((r for r in _regions if r["id"] == region_id), None)
    if not region:
        return []

    # 生成合作社数据
    coops = _generate_cooperatives_for_county(region)

    # 获取该县遥感数据
    remote = next((r for r in _remote_data if r.get("region_id") == region_id), None)

    # 计算各维度最大/最小值用于归一化
    cap_values = [c["biz_registered_capital_wan"] for c in coops]
    emp_values = [c["biz_social_security_count"] for c in coops]
    cap_max = max(cap_values) if cap_values else 1000
    emp_max = max(emp_values) if emp_values else 10
    if emp_max == 0:
        emp_max = 1

    results = []
    for coop in coops:
        biz_score, biz_detail = _score_biz(coop, cap_max, emp_max)
        eco_score, eco_detail = _score_eco(coop, remote)
        weather_score, weather_detail = _score_weather(coop)
        ops_score, ops_detail = _score_ops(coop)

        total = 0.40 * biz_score + 0.30 * eco_score + 0.20 * weather_score + 0.10 * ops_score

        results.append({
            **coop,
            "score_total": round(total, 1),
            "score_biz": biz_score,
            "score_eco": eco_score,
            "score_weather": weather_score,
            "score_ops": ops_score,
            "score_detail": {
                "工商维度": biz_detail,
                "生态维度": eco_detail,
                "气象维度": weather_detail,
                "经营维度": ops_detail,
            },
            "loan_recommendation": _make_recommendation(total),
        })

    # 按综合得分降序
    results.sort(key=lambda x: x["score_total"], reverse=True)

    # 添加排名
    for rank, r in enumerate(results, 1):
        r["rank"] = rank

    # ── 多维度交叉验证 ──
    _load_real_cooperatives()
    real_list = _real_coops.get(region_id, [])
    for coop in results:
        name = coop["name"]
        source = coop.get("data_source", "simulated")
        sources = set()
        if "government_open_data" in source:
            sources.add("government_open_data")
        if "gsxt" in source:
            sources.add("gsxt")
        for real in real_list:
            if real["name"] != name and _name_similarity(name, real["name"]) >= 0.75:
                for s in real.get("data_source", "").replace("+", " ").split():
                    if s and s != "simulated":
                        sources.add(s)
        sources.discard("simulated")

        if len(sources) >= 2:
            coop["verification"] = {"level": "★★★", "label": "双源验证", "code": "dual", "sources": list(sources)}
        elif len(sources) == 1:
            coop["verification"] = {"level": "★★☆", "label": "单源验证", "code": "single", "sources": list(sources)}
        else:
            coop["verification"] = {"level": "★☆☆", "label": "模拟数据", "code": "none", "sources": []}

    return results[:top_n]


def _make_recommendation(total_score: float) -> dict[str, Any]:
    """根据得分生成贷款建议。"""
    if total_score >= 80:
        return {
            "level": "重点推荐",
            "color": "#22c55e",
            "suggestion": "建议优先放贷，可适度提高额度",
            "max_credit_ratio": 1.0,
        }
    elif total_score >= 65:
        return {
            "level": "可以放贷",
            "color": "#3b82f6",
            "suggestion": "正常放贷，建议追加保险覆盖",
            "max_credit_ratio": 0.85,
        }
    elif total_score >= 50:
        return {
            "level": "审慎放贷",
            "color": "#f59e0b",
            "suggestion": "建议降低额度或要求联保增信",
            "max_credit_ratio": 0.6,
        }
    else:
        return {
            "level": "暂不建议",
            "color": "#ef4444",
            "suggestion": "待工商/生态/经营指标改善后再议",
            "max_credit_ratio": 0.0,
        }


def rank_all_counties(top_n_per_county: int = 10) -> list[dict[str, Any]]:
    """对所有县域进行排序，返回各县 Top N。"""
    _load_regions()
    all_results = []
    for region in _regions:
        ranked = rank_cooperatives(region["id"], top_n_per_county)
        all_results.append({
            "region_id": region["id"],
            "region_name": region["name"],
            "total_cooperatives": len(ranked),
            "top_cooperatives": ranked,
        })
    return all_results


def get_county_summary(region_id: str) -> dict[str, Any]:
    """获取县域合作社统计摘要。"""
    ranked = rank_cooperatives(region_id, top_n=200)
    if not ranked:
        return {}

    scores = [r["score_total"] for r in ranked]
    return {
        "region_id": region_id,
        "total_count": len(ranked),
        "avg_score": round(sum(scores) / len(scores), 1),
        "max_score": round(max(scores), 1),
        "min_score": round(min(scores), 1),
        "recommend_count": sum(1 for r in ranked if r["score_total"] >= 65),
        "caution_count": sum(1 for r in ranked if 50 <= r["score_total"] < 65),
        "not_recommend_count": sum(1 for r in ranked if r["score_total"] < 50),
    }


# ── 多维度数据交叉验证引擎 ──

def _normalize_name(name: str) -> str:
    """归一化合作社名称，用于跨数据源匹配。"""
    n = name.replace("专业合作社", "").replace("牧民", "").replace("农牧民", "")
    n = n.replace("经济合作组织", "").replace("牧业经济合作社", "").replace("扶贫", "")
    n = n.replace("特色", "").replace("（", "(").replace("）", ")")
    n = n.strip()
    return n


def _name_similarity(a: str, b: str) -> float:
    """计算两个合作社名称的相似度 (0-1)。"""
    na = _normalize_name(a)
    nb = _normalize_name(b)
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.85
    words_a = set(na)
    words_b = set(nb)
    if not words_a or not words_b:
        return 0.0
    overlap = len(words_a & words_b)
    return overlap / max(len(words_a), len(words_b))


# ── 维度 1: 统一社会信用代码校验 ──

# 统一社会信用代码字符集与权重
_USCC_CHARS = "0123456789ABCDEFGHJKLMNPQRTUWXY"
_USCC_WEIGHTS = [1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28]


def _validate_uscc(code: str | None) -> dict[str, Any]:
    """校验统一社会信用代码格式与校验位。

    规则:
      - 18 位，前 17 位为数字+大写字母（不含 I/O/Z/S/V），第 18 位为校验码
      - 校验算法: 加权求和 mod 31
    """
    if not code:
        return {"valid": None, "status": "missing", "detail": "无统一社会信用代码"}
    code = str(code).strip().upper()
    if len(code) != 18:
        return {"valid": False, "status": "invalid", "detail": f"长度应为18位，实际{len(code)}位"}
    # 前 17 位字符集检查
    for i, ch in enumerate(code[:17]):
        if ch not in _USCC_CHARS:
            return {"valid": False, "status": "invalid", "detail": f"第{i+1}位'{ch}'不在合法字符集中"}
    # 校验位计算
    total = sum(_USCC_CHARS.index(ch) * _USCC_WEIGHTS[i] for i, ch in enumerate(code[:17]))
    check_idx = 31 - (total % 31)
    if check_idx == 31:
        check_idx = 0
    expected_check = _USCC_CHARS[check_idx]
    actual_check = code[17]
    if expected_check != actual_check:
        return {"valid": False, "status": "invalid",
                "detail": f"校验位不匹配: 期望'{expected_check}'，实际'{actual_check}'"}
    # 提取登记管理机关和机构类别
    reg_dept = code[8:10] if len(code) >= 10 else ""
    org_type = code[16] if len(code) >= 17 else ""
    org_type_map = {"1": "企业", "2": "事业单位", "3": "社会团体", "9": "其他"}
    return {
        "valid": True, "status": "valid",
        "detail": "校验通过",
        "registration_authority": reg_dept,
        "organization_type": org_type_map.get(org_type, org_type),
    }


# ── 维度 2: 法人代表交叉对比 ──

def _check_legal_representative(coop: dict[str, Any], all_real_coops: list[dict[str, Any]]) -> dict[str, Any]:
    """检查法人代表是否在多个合作社中出现（潜在关联风险）。"""
    rep = coop.get("legal_representative")
    if not rep:
        return {"status": "missing", "detail": "无法人代表信息", "related_count": 0}
    # 同一法人代表下的其他合作社
    related = [
        c["name"] for c in all_real_coops
        if c.get("legal_representative") == rep and c["name"] != coop.get("name", "")
    ]
    if len(related) >= 3:
        return {"status": "warning", "detail": f"法人代表'{rep}'同时关联{len(related)}个合作社",
                "related_count": len(related), "related_names": related[:5]}
    elif len(related) >= 1:
        return {"status": "info", "detail": f"法人代表'{rep}'关联{len(related)}个合作社",
                "related_count": len(related), "related_names": related}
    return {"status": "ok", "detail": "法人代表唯一", "related_count": 0}


# ── 维度 3: 历史名称变更追踪 ──

def _check_name_history(coop: dict[str, Any]) -> dict[str, Any]:
    """检查历史名称变更记录，频繁更名可能是风险信号。"""
    names = coop.get("historical_names") or []
    if not names:
        return {"status": "ok", "detail": "无历史名称变更", "change_count": 0}
    count = len(names)
    if count >= 3:
        return {"status": "warning", "detail": f"曾更名{count}次，需关注经营连续性",
                "change_count": count, "historical_names": names}
    elif count >= 2:
        return {"status": "info", "detail": f"曾更名{count}次", "change_count": count, "historical_names": names}
    return {"status": "ok", "detail": f"曾更名{count}次", "change_count": count, "historical_names": names}


# ── 维度 4: 经营状态校验 ──

def _check_business_status(coop: dict[str, Any]) -> dict[str, Any]:
    """校验经营状态，非'存续'状态为风险信号。"""
    status = coop.get("status", "存续")
    if status == "存续":
        return {"status": "ok", "detail": "正常存续"}
    elif status in ("吊销", "注销"):
        return {"status": "warning", "detail": f"经营状态异常: {status}"}
    elif status in ("迁出", "停业"):
        return {"status": "warning", "detail": f"经营状态: {status}"}
    return {"status": "info", "detail": f"经营状态: {status}"}


# ── 维度 5: 内部一致性校验 ──

def _check_internal_consistency(coop: dict[str, Any]) -> list[dict[str, Any]]:
    """检查合作社内部数据是否自洽。

    检查项:
      1. 成立日期 vs 成立年限 — 是否一致
      2. 注册资本 vs 存栏规模 — 资本是否与规模匹配
      3. 草场面积 vs 牲畜数量 — 载畜量是否合理
    """
    checks: list[dict[str, Any]] = []
    from datetime import date

    # 5a. 成立日期 vs 成立年限
    est_date = coop.get("establish_date")
    years = coop.get("biz_years_established")
    if est_date and years:
        try:
            d = str(est_date)
            if "-" in d:
                est_year = int(d[:4])
                calc_years = date.today().year - est_year
                diff = abs(years - calc_years)
                if diff <= 1:
                    checks.append({
                        "dimension": "成立日期一致性",
                        "status": "match",
                        "detail": f"成立日期({est_date})与成立年限({years}年)一致",
                    })
                elif diff <= 3:
                    checks.append({
                        "dimension": "成立日期一致性",
                        "status": "partial",
                        "detail": f"成立日期推算{calc_years}年，记录{years}年，差{diff}年",
                    })
                else:
                    checks.append({
                        "dimension": "成立日期一致性",
                        "status": "conflict",
                        "detail": f"成立日期推算{calc_years}年，记录{years}年，差{diff}年",
                    })
        except (ValueError, TypeError):
            pass

    # 5b. 注册资本 vs 存栏规模 (粗略合理性: 每万元资本对应 0.5-5 头牲畜折算)
    capital = coop.get("biz_registered_capital_wan", 0)
    cattle = coop.get("ops_cattle_count", 0)
    sheep = coop.get("ops_sheep_count", 0)
    if capital and (cattle or sheep):
        livestock = cattle + sheep * 0.3  # 折算为牛单位
        ratio = livestock / capital if capital > 0 else 0
        if 0.2 <= ratio <= 20:
            checks.append({
                "dimension": "资本规模匹配度",
                "status": "match",
                "detail": f"每万元资本对应{ratio:.1f}头牲畜，规模合理",
            })
        elif ratio < 0.2:
            checks.append({
                "dimension": "资本规模匹配度",
                "status": "partial",
                "detail": f"每万元资本仅对应{ratio:.1f}头牲畜，资本偏高或存栏偏低",
            })
        else:
            checks.append({
                "dimension": "资本规模匹配度",
                "status": "partial",
                "detail": f"每万元资本对应{ratio:.1f}头牲畜，存栏偏高",
            })

    # 5c. 草场面积 vs 牲畜数量 (西藏高寒草甸: 约 15-30 亩/羊单位)
    grass = coop.get("ops_grassland_mu", 0)
    if grass and livestock:
        mu_per_unit = grass / livestock if livestock > 0 else 0
        if 8 <= mu_per_unit <= 60:
            checks.append({
                "dimension": "草场载畜合理性",
                "status": "match",
                "detail": f"每羊单位{mu_per_unit:.0f}亩草场，载畜量合理",
            })
        elif mu_per_unit < 8:
            checks.append({
                "dimension": "草场载畜合理性",
                "status": "warning",
                "detail": f"每羊单位仅{mu_per_unit:.0f}亩草场，可能超载",
            })
        else:
            checks.append({
                "dimension": "草场载畜合理性",
                "status": "info",
                "detail": f"每羊单位{mu_per_unit:.0f}亩草场，草场充裕",
            })

    return checks


# ── 维度 6: 异常值检测 ──

def _detect_outliers(coop: dict[str, Any], all_coops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """检测合作社在各维度上是否为异常值（超过 2 倍标准差）。"""
    import statistics
    alerts: list[dict[str, Any]] = []
    if len(all_coops) < 3:
        return alerts

    # 收集各维度数据
    fields = [
        ("biz_registered_capital_wan", "注册资本"),
        ("biz_years_established", "成立年限"),
        ("ops_cattle_count", "牦牛数量"),
        ("ops_sheep_count", "藏羊数量"),
        ("ops_grassland_mu", "草场面积"),
    ]
    for field, label in fields:
        values = [c.get(field, 0) for c in all_coops if c.get(field) is not None]
        if len(values) < 3:
            continue
        avg = statistics.mean(values)
        std = statistics.stdev(values)
        if std == 0:
            continue
        val = coop.get(field, 0)
        if val is None:
            continue
        z = (val - avg) / std
        if abs(z) > 2.5:
            alerts.append({
                "dimension": f"{label}异常",
                "status": "outlier_high" if z > 0 else "outlier_low",
                "detail": f"{label}: {val} (均值{avg:.0f}, σ={std:.0f}, z={z:+.1f})",
                "z_score": round(z, 1),
            })
    return alerts


# ── 维度 7: 数据来源可信度 ──

_SOURCE_CREDIBILITY = {
    "government_open_data": 0.90,   # 农业农村厅官方数据
    "gsxt": 0.85,                    # 国家企业信用信息公示系统
    "government_open_data+gsxt": 0.95,  # 双源交叉验证
    "simulated": 0.30,               # 模拟数据
}


def _assess_source_credibility(coop: dict[str, Any]) -> dict[str, Any]:
    """评估数据来源可信度。"""
    source = coop.get("data_source", "simulated")
    credibility = _SOURCE_CREDIBILITY.get(source, 0.30)
    # 有统一社会信用代码加分
    if coop.get("unified_social_credit_code"):
        credibility = min(1.0, credibility + 0.05)
    # 有法人代表加分
    if coop.get("legal_representative"):
        credibility = min(1.0, credibility + 0.03)
    # 有成立日期加分
    if coop.get("establish_date"):
        credibility = min(1.0, credibility + 0.02)

    if credibility >= 0.90:
        label = "高可信"
    elif credibility >= 0.70:
        label = "中可信"
    elif credibility >= 0.50:
        label = "低可信"
    else:
        label = "模拟数据"

    return {
        "source": source,
        "credibility": round(credibility, 2),
        "label": label,
    }


# ── 主验证函数 ──

def verify_county(region_id: str) -> dict[str, Any]:
    """多维度交叉验证一个县的所有合作社数据。

    数据源:
      1. 农业农村厅示范社名单 (government_open_data)
      2. 国家企业信用信息公示系统 (gsxt)
      3. 模拟补充数据 (simulated)

    验证维度 (7 个):
      1. 统一社会信用代码格式校验
      2. 法人代表交叉对比 (关联风险)
      3. 历史名称变更追踪 (经营连续性)
      4. 经营状态校验
      5. 内部一致性校验 (成立日期/资本规模/载畜量)
      6. 异常值检测 (各维度离群值)
      7. 数据来源可信度评估

    返回:
      - 每个合作社的多维度验证结果
      - 冲突检测与风险信号
      - 整体数据质量评分
    """
    _load_regions()
    _load_real_cooperatives()

    region = next((r for r in _regions if r["id"] == region_id), None)
    if not region:
        return {"error": f"县域 {region_id} 不存在"}

    real_list = _real_coops.get(region_id, [])
    all_coops = _generate_cooperatives_for_county(region)

    # 全局分析：法人代表交叉对比
    all_real_coops = [c for coops in _real_coops.values() for c in coops]

    results = []
    verified_count = 0
    dual_sourced_count = 0
    conflict_count = 0
    warning_count = 0

    for coop in all_coops:
        source = coop.get("data_source", "simulated")
        name = coop["name"]

        # ── 跨数据源匹配 ──
        matches: list[dict[str, Any]] = []
        for real in real_list:
            sim = _name_similarity(name, real["name"])
            if sim >= 0.75:
                matches.append({
                    "name": real["name"],
                    "source": real.get("data_source", ""),
                    "similarity": round(sim, 2),
                })

        # ── 验证级别 ──
        sources = set()
        if "government_open_data" in source or "gsxt" in source:
            for s in source.replace("+", " ").split():
                if s and s != "simulated":
                    sources.add(s)
        if matches:
            for m in matches:
                for s in m["source"].replace("+", " ").split():
                    if s and s != "simulated":
                        sources.add(s)

        if len(sources) >= 2:
            level = "★★★ 双源验证"
            level_code = "verified"
            verified_count += 1
            dual_sourced_count += 1
        elif len(sources) == 1:
            level = "★★☆ 单源验证"
            level_code = "partial"
            verified_count += 1
        else:
            level = "★☆☆ 未验证（模拟数据）"
            level_code = "unverified"

        # ── 维度 1: 统一社会信用代码校验 ──
        uscc_check = _validate_uscc(coop.get("unified_social_credit_code"))

        # ── 维度 2: 法人代表交叉对比 ──
        legal_check = _check_legal_representative(coop, all_real_coops)

        # ── 维度 3: 历史名称变更 ──
        history_check = _check_name_history(coop)

        # ── 维度 4: 经营状态校验 ──
        status_check = _check_business_status(coop)

        # ── 维度 5: 内部一致性 ──
        consistency_checks = _check_internal_consistency(coop)

        # ── 维度 6: 异常值检测 ──
        outlier_alerts = _detect_outliers(coop, all_coops)

        # ── 维度 7: 数据来源可信度 ──
        credibility = _assess_source_credibility(coop)

        # ── 字段级对比（跨数据源） ──
        field_checks: list[dict[str, Any]] = []
        if matches:
            best = matches[0]
            for real_coop in real_list:
                if real_coop["name"] == best["name"]:
                    # 成立年限
                    years1 = coop.get("biz_years_established")
                    if real_coop.get("establish_date"):
                        from datetime import date
                        try:
                            d = str(real_coop["establish_date"])
                            if "-" in d:
                                est_year = int(d[:4])
                                calc_years = date.today().year - est_year
                            else:
                                calc_years = years1
                        except (ValueError, TypeError):
                            calc_years = years1
                        field_checks.append({
                            "field": "成立年限",
                            "match": abs(years1 - calc_years) <= 1 if years1 else True,
                            "status": "match" if abs(years1 - calc_years) <= 1 else "conflict",
                            "values": [f"约{years1}年", f"约{calc_years}年"],
                        })
                    # 注册资本
                    cr1 = coop.get("biz_registered_capital_wan")
                    cr2 = real_coop.get("biz_registered_capital_wan")
                    if cr1 and cr2:
                        field_checks.append({
                            "field": "注册资本",
                            "match": abs(cr1 - cr2) / max(cr1, cr2) < 0.3,
                            "status": "match" if abs(cr1 - cr2) / max(cr1, cr2) < 0.3 else "conflict",
                            "values": [f"{cr1}万", f"{cr2}万"],
                        })
                    break

        # ── 汇总所有维度的问题 ──
        all_issues: list[dict[str, Any]] = []
        # 维度 1
        if uscc_check["status"] == "invalid":
            all_issues.append({"dimension": "统一社会信用代码", "severity": "error", **uscc_check})
        # 维度 2
        if legal_check["status"] == "warning":
            all_issues.append({"dimension": "法人代表关联", "severity": "warning", **legal_check})
            warning_count += 1
        # 维度 3
        if history_check["status"] == "warning":
            all_issues.append({"dimension": "历史名称变更", "severity": "warning", **history_check})
            warning_count += 1
        # 维度 4
        if status_check["status"] == "warning":
            all_issues.append({"dimension": "经营状态", "severity": "error", **status_check})
        # 维度 5
        for c in consistency_checks:
            if c["status"] in ("conflict", "warning"):
                all_issues.append({"dimension": c["dimension"], "severity": c["status"], **c})
        # 维度 6
        for o in outlier_alerts:
            all_issues.append({"dimension": o["dimension"], "severity": "info", **o})
        # 字段冲突
        conflicts = [c for c in field_checks if c["status"] == "conflict"]
        if conflicts:
            conflict_count += 1
        for c in conflicts:
            all_issues.append({"dimension": c["field"], "severity": "conflict", **c})

        # 计算单个合作社的验证得分
        dim_scores = {
            "uscc": 1.0 if uscc_check["valid"] else (0.5 if uscc_check["valid"] is None else 0.0),
            "legal": 0.0 if legal_check["status"] == "warning" else 1.0,
            "history": 0.0 if history_check["status"] == "warning" else 1.0,
            "status": 0.0 if status_check["status"] == "warning" else 1.0,
            "consistency": 1.0 - 0.2 * sum(1 for c in consistency_checks if c["status"] in ("conflict", "warning")),
            "credibility": credibility["credibility"],
        }
        dim_scores["consistency"] = max(0.0, dim_scores["consistency"])
        verify_score = round(
            sum(dim_scores.values()) / len(dim_scores) * 100, 1
        )

        results.append({
            "name": name,
            "rank": coop.get("rank", 0),
            "data_sources": list(sources),
            "source_count": len(sources),
            "cross_matches": matches,
            "verification": {
                "level": level,
                "level_code": level_code,
                "verify_score": verify_score,
                # 各维度详情
                "dimensions": {
                    "uscc": uscc_check,
                    "legal_representative": legal_check,
                    "name_history": history_check,
                    "business_status": status_check,
                    "internal_consistency": consistency_checks,
                    "outliers": outlier_alerts,
                    "credibility": credibility,
                    "field_checks": field_checks,
                },
                "field_checks": field_checks,
                "has_conflicts": len(conflicts) > 0,
                "conflicts": conflicts,
                "issues": all_issues,
                "issue_count": len(all_issues),
            },
        })

    # ── 整体数据质量评分（加权多维度） ──
    total = len(results)
    if total == 0:
        return {"error": "无合作社数据"}

    # 源验证得分 (40%)
    source_score = (verified_count / total * 0.6 + dual_sourced_count / total * 0.4) * 100
    # 冲突率惩罚 (20%)
    conflict_penalty = (conflict_count / total) * 100
    # 平均合作社验证得分 (30%)
    avg_verify = sum(r["verification"]["verify_score"] for r in results) / total
    # 风险信号惩罚 (10%)
    warning_penalty = (warning_count / total) * 20

    quality_score = round(
        source_score * 0.40
        + avg_verify * 0.30
        - conflict_penalty * 0.20
        - warning_penalty * 0.10,
        1
    )
    quality_score = max(0, min(100, quality_score))

    return {
        "region_id": region_id,
        "region_name": region["name"],
        "total_cooperatives": total,
        "verified_count": verified_count,
        "dual_sourced_count": dual_sourced_count,
        "conflict_count": conflict_count,
        "warning_count": warning_count,
        "data_quality_score": quality_score,
        "quality_label": (
            "优秀" if quality_score >= 80 else
            "良好" if quality_score >= 60 else
            "一般" if quality_score >= 40 else
            "待改善"
        ),
        "quality_breakdown": {
            "source_verification": round(source_score * 0.40, 1),
            "avg_verify_score": round(avg_verify * 0.30, 1),
            "conflict_penalty": round(-conflict_penalty * 0.20, 1),
            "warning_penalty": round(-warning_penalty * 0.10, 1),
        },
        "cooperatives": results,
    }


# ── 多源交叉比对 ──

# 可比对字段列表（不同数据源可能提供的字段）
_CROSS_COMPARABLE_FIELDS = [
    ("name", "合作社名称", "string"),
    ("biz_registered_capital_wan", "注册资本(万)", "number"),
    ("biz_years_established", "成立年限", "number"),
    ("ops_cattle_count", "牦牛数量", "number"),
    ("ops_sheep_count", "藏羊数量", "number"),
    ("ops_grassland_mu", "草场面积(亩)", "number"),
    ("unified_social_credit_code", "统一社会信用代码", "string"),
    ("legal_representative", "法人代表", "string"),
    ("establish_date", "成立日期", "date"),
    ("status", "经营状态", "string"),
    ("biz_penalty_count", "行政处罚次数", "number"),
    ("biz_social_security_count", "社保人数", "number"),
    ("biz_tax_compliant", "纳税合规", "bool"),
    ("ops_overdue_times", "逾期次数", "number"),
    ("ops_credit_limit_wan", "信用额度(万)", "number"),
]


def cross_source_compare(coop_name: str) -> dict[str, Any]:
    """对指定合作社，从多个可信数据源获取信息并逐字段交叉比对。

    数据源优先级:
      1. 农业农村厅示范社名单 (government_open_data) — 权威性最高
      2. 国家企业信用信息公示系统 (gsxt) — 法律效力最高
      3. 信用中国 (creditchina) — 补充信用信息
      4. 天眼查/企查查 (tianyancha) — 商业补充

    比对逻辑:
      - 同一字段在多个数据源间的一致性
      - 数值型字段: 相对误差 < 10% 视为一致
      - 字符串字段: 精确匹配或语义等价
      - 日期字段: 年月日完全一致
    """
    _load_real_cooperatives()
    all_real = [c for coops in _real_coops.values() for c in coops]

    # 查找该合作社（精确匹配 + 模糊匹配 + 历史名称匹配）
    candidates: list[dict[str, Any]] = []
    for coop in all_real:
        if coop["name"] == coop_name:
            candidates.append(coop)
        elif _name_similarity(coop_name, coop["name"]) >= 0.75:
            candidates.append(coop)
        else:
            # 检查历史名称
            for hist_name in coop.get("historical_names") or []:
                if _name_similarity(coop_name, hist_name) >= 0.75:
                    candidates.append(coop)
                    break

    if not candidates:
        return {"error": f"未找到合作社 '{coop_name}' 的多源数据", "coop_name": coop_name}

    # 按数据源分组
    sources_data: dict[str, dict[str, Any]] = {}
    for c in candidates:
        src = c.get("data_source", "simulated")
        for s in src.replace("+", " ").split():
            if s == "simulated":
                continue
            if s not in sources_data:
                sources_data[s] = dict(c)
            else:
                # 合并：补充缺失字段
                existing = sources_data[s]
                for k, v in c.items():
                    if k not in existing or existing[k] is None:
                        existing[k] = v

    if len(sources_data) < 2:
        return {
            "coop_name": coop_name,
            "source_count": len(sources_data),
            "available_sources": list(sources_data.keys()),
            "comparison_possible": False,
            "message": "仅有一个数据源，无法进行交叉比对。建议从以下渠道补充：\n"
                       "  1. 国家企业信用信息公示系统 (gsxt.gov.cn)\n"
                       "  2. 信用中国 (creditchina.gov.cn)\n"
                       "  3. 天眼查 (tianyancha.com)\n"
                       "  4. 企查查 (qcc.com)",
            "suggested_sources": ["gsxt.gov.cn", "creditchina.gov.cn", "tianyancha.com", "qcc.com"],
        }

    # 逐字段比对
    field_comparisons: list[dict[str, Any]] = []
    matched_count = 0
    conflict_count = 0
    missing_count = 0

    source_names = list(sources_data.keys())

    for field_key, field_label, field_type in _CROSS_COMPARABLE_FIELDS:
        values = {}
        for src_name in source_names:
            val = sources_data[src_name].get(field_key)
            if val is not None:
                values[src_name] = val

        if len(values) < 2:
            missing_count += 1
            field_comparisons.append({
                "field": field_label,
                "field_key": field_key,
                "status": "insufficient",
                "detail": f"仅{len(values)}个数据源有此字段",
                "values": {k: str(v) for k, v in values.items()},
            })
            continue

        # 判断一致性
        vals_list = list(values.values())
        if field_type == "number":
            ref = float(vals_list[0])
            all_match = all(
                abs(float(v) - ref) / max(abs(ref), 1) < 0.10
                for v in vals_list[1:]
            )
        elif field_type == "date":
            all_match = all(str(v)[:10] == str(vals_list[0])[:10] for v in vals_list[1:])
        elif field_type == "bool":
            all_match = all(bool(v) == bool(vals_list[0]) for v in vals_list[1:])
        else:  # string
            all_match = all(str(v).strip() == str(vals_list[0]).strip() for v in vals_list[1:])

        if all_match:
            matched_count += 1
            field_comparisons.append({
                "field": field_label,
                "field_key": field_key,
                "status": "match",
                "detail": f"{len(source_names)}个数据源一致",
                "values": {k: str(v) for k, v in values.items()},
            })
        else:
            conflict_count += 1
            field_comparisons.append({
                "field": field_label,
                "field_key": field_key,
                "status": "conflict",
                "detail": f"{len(source_names)}个数据源存在差异",
                "values": {k: str(v) for k, v in values.items()},
            })

    total = len(field_comparisons)
    agreement_rate = round(matched_count / total * 100, 1) if total > 0 else 0

    # 数据源可信度评估
    source_reliability = {
        "government_open_data": {"label": "农业农村厅", "reliability": 0.90,
                                  "desc": "政府官方示范社名单，权威性高"},
        "gsxt": {"label": "国家企业信用信息公示系统", "reliability": 0.85,
                 "desc": "法定登记信息，法律效力高"},
        "creditchina": {"label": "信用中国", "reliability": 0.80,
                        "desc": "公共信用信息，覆盖面广"},
        "tianyancha": {"label": "天眼查", "reliability": 0.75,
                       "desc": "商业数据平台，更新及时但可能有滞后"},
        "qcc": {"label": "企查查", "reliability": 0.75,
                "desc": "商业数据平台，与天眼查互补"},
    }

    return {
        "coop_name": coop_name,
        "source_count": len(sources_data),
        "available_sources": list(sources_data.keys()),
        "source_details": {
            k: source_reliability.get(k, {"label": k, "reliability": 0.5, "desc": "未知来源"})
            for k in sources_data
        },
        "comparison_possible": True,
        "total_fields": total,
        "matched_fields": matched_count,
        "conflict_fields": conflict_count,
        "missing_fields": missing_count,
        "agreement_rate": agreement_rate,
        "agreement_label": (
            "高度一致" if agreement_rate >= 90 else
            "基本一致" if agreement_rate >= 70 else
            "存在差异" if agreement_rate >= 50 else
            "差异较大"
        ),
        "field_comparisons": field_comparisons,
        "conflicts": [f for f in field_comparisons if f["status"] == "conflict"],
        "recommendation": _make_comparison_recommendation(agreement_rate, conflict_count),
    }


def _make_comparison_recommendation(agreement_rate: float, conflict_count: int) -> dict[str, Any]:
    """根据多源比对结果给出建议。"""
    if agreement_rate >= 90 and conflict_count == 0:
        return {
            "level": "数据可信",
            "color": "#22c55e",
            "suggestion": "多源数据高度一致，可直接用于信贷决策",
        }
    elif agreement_rate >= 70:
        return {
            "level": "基本可信",
            "color": "#3b82f6",
            "suggestion": f"存在{conflict_count}个字段差异，建议以政府数据为准，人工复核差异项",
        }
    elif agreement_rate >= 50:
        return {
            "level": "需人工复核",
            "color": "#f59e0b",
            "suggestion": f"存在{conflict_count}个字段冲突，建议人工核实后使用",
        }
    else:
        return {
            "level": "数据存疑",
            "color": "#ef4444",
            "suggestion": "多源数据差异较大，暂不建议直接使用，建议补充数据后重新比对",
        }


def cross_source_compare_all(region_id: str) -> dict[str, Any]:
    """对指定县域所有合作社进行多源交叉比对。"""
    _load_real_cooperatives()
    real_list = _real_coops.get(region_id, [])

    results = []
    for coop in real_list:
        result = cross_source_compare(coop["name"])
        results.append(result)

    # 统计
    comparable = [r for r in results if r.get("comparison_possible")]
    high_agreement = sum(1 for r in comparable if r.get("agreement_rate", 0) >= 90)
    with_conflicts = sum(1 for r in comparable if r.get("conflict_fields", 0) > 0)

    return {
        "region_id": region_id,
        "total_cooperatives": len(results),
        "comparable_count": len(comparable),
        "single_source_count": len(results) - len(comparable),
        "high_agreement_count": high_agreement,
        "with_conflicts_count": with_conflicts,
        "overall_agreement_rate": round(
            sum(r.get("agreement_rate", 0) for r in comparable) / max(len(comparable), 1), 1
        ) if comparable else 0,
        "cooperatives": results,
    }