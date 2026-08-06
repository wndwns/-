"""
工银牧融 - 数据访问层
============================================================================
数据优先级: JSON Store > MySQL > 内置样例数据

读取流程:
  1. 先尝试从 store.py (JSON 文件) 读取 —— CSV 上传的数据存这里
  2. 如果 store 无数据，尝试 MySQL
  3. 都没有则回退到内置 _SAMPLE_xxx

数据闭环:
  管理端 CSV 上传 → store.import_csv_to_table() → data.py get_xxx() 读到新数据
  → 前端 /api/platform 返回最新数据 → 风险评估重算
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 数据源：优先 store，其次 MySQL，最后内置样例
# ---------------------------------------------------------------------------

_store_available = False
_db_available = False

# 尝试加载 JSON store
try:
    from .store import read_table as _store_read, table_info as _store_info
    _store_available = True
except ImportError:
    try:
        from store import read_table as _store_read, table_info as _store_info  # type: ignore[no-redef]
        _store_available = True
    except ImportError:
        def _store_read(table: str) -> list[dict[str, Any]]: return []
        def _store_info(table: str) -> dict[str, Any]: return {}
        _store_available = False

# 尝试加载 MySQL
try:
    from .db import ensure_initialized, fetch_all, fetch_one, execute, is_db_available
    _db_available = is_db_available()
except ImportError:
    try:
        from db import ensure_initialized, fetch_all, fetch_one, execute, is_db_available  # type: ignore[no-redef]
        _db_available = is_db_available()
    except ImportError:
        def fetch_all(sql, params=None): return []
        def fetch_one(sql, params=None): return None
        def execute(sql, params=None): return 0
        def is_db_available(): return False
        def ensure_initialized(): return False
        _db_available = False


def _read(store_table: str, db_query: str, sample_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """统一读取：store > mysql > sample。"""
    # 1. JSON store
    if _store_available:
        rows = _store_read(store_table)
        if rows:
            return rows
    # 2. MySQL
    if _db_available:
        rows = fetch_all(db_query)
        if rows:
            return rows
    # 3. 内置样例
    return list(sample_data)


_LINZHI_ENSURE_ENABLED = True   # 始终补入林芝资产登记参考数据（1135条耳标记录）


def _ensure_linzhi_data(rows: list[dict[str, Any]], data_type: str) -> None:
    if not _LINZHI_ENSURE_ENABLED:
        return
    if any(r.get("region_id") == "linzhi-bayi" for r in rows):
        return
    if data_type == "weather":
        rows.append({
            "region_id": "linzhi-bayi", "region_name": "林芝市巴宜区",
            "station": "林芝市国家基准气候站", "observed_at": "2026-05-21 08:00",
            "temperature_c": 9.5, "precipitation_mm_24h": 3.2, "wind_speed_mps": 2.8,
            "snow_depth_cm": 3, "cold_wave_risk": "低", "snowstorm_risk": "低",
            "drought_risk": "低", "data_source": "asset_register_reference",
        })
    elif data_type == "remote":
        rows.append({
            "region_id": "linzhi-bayi", "region_name": "林芝市巴宜区",
            "scene_date": "2026-05-20", "ndvi": 0.62, "ndvi_change": "+2.1%",
            "vegetation_cover": "72%", "snow_cover": "8%",
            "grassland_type": "山地灌丛草甸", "degradation_level": "基本稳定",
            "carrying_capacity_sheep_unit": 28500, "data_source": "asset_register_reference",
        })


def db_available() -> bool:
    return _db_available


def store_available() -> bool:
    return _store_available


# ============================================================================
# 内置样例数据（三级 fallback）
# ============================================================================

_SAMPLE_WEATHER = [
    {"region_id": "naqu-bange", "region_name": "那曲市班戈县", "station": "班戈县高原气象站", "observed_at": "2026-05-21 08:00", "temperature_c": -3.8, "precipitation_mm_24h": 11.6, "wind_speed_mps": 8.2, "snow_depth_cm": 18, "cold_wave_risk": "高", "snowstorm_risk": "高", "drought_risk": "低", "data_source": "sample"},
    {"region_id": "changdu-luolong", "region_name": "昌都市洛隆县", "station": "洛隆县牧区气象站", "observed_at": "2026-05-21 08:00", "temperature_c": 2.4, "precipitation_mm_24h": 4.8, "wind_speed_mps": 5.1, "snow_depth_cm": 7, "cold_wave_risk": "中", "snowstorm_risk": "中", "drought_risk": "低", "data_source": "sample"},
    {"region_id": "rikaze-xietongmen", "region_name": "日喀则市谢通门县", "station": "谢通门县生态监测站", "observed_at": "2026-05-21 08:00", "temperature_c": 5.7, "precipitation_mm_24h": 1.2, "wind_speed_mps": 3.6, "snow_depth_cm": 2, "cold_wave_risk": "低", "snowstorm_risk": "低", "drought_risk": "中", "data_source": "sample"},
    {"region_id": "linzhi-bayi", "region_name": "林芝市巴宜区", "station": "林芝市国家基准气候站", "observed_at": "2026-05-21 08:00", "temperature_c": 9.5, "precipitation_mm_24h": 3.2, "wind_speed_mps": 2.8, "snow_depth_cm": 3, "cold_wave_risk": "低", "snowstorm_risk": "低", "drought_risk": "低", "data_source": "asset_register_reference"},
]

_SAMPLE_REMOTE = [
    {"region_id": "naqu-bange", "region_name": "那曲市班戈县", "scene_date": "2026-05-20", "ndvi": 0.34, "ndvi_change": "-8.6%", "vegetation_cover": "42%", "snow_cover": "31%", "grassland_type": "高寒草甸", "degradation_level": "中度退化", "carrying_capacity_sheep_unit": 18200, "data_source": "sample"},
    {"region_id": "changdu-luolong", "region_name": "昌都市洛隆县", "scene_date": "2026-05-20", "ndvi": 0.47, "ndvi_change": "-3.2%", "vegetation_cover": "55%", "snow_cover": "18%", "grassland_type": "山地草甸", "degradation_level": "轻度退化", "carrying_capacity_sheep_unit": 23600, "data_source": "sample"},
    {"region_id": "rikaze-xietongmen", "region_name": "日喀则市谢通门县", "scene_date": "2026-05-20", "ndvi": 0.52, "ndvi_change": "+1.4%", "vegetation_cover": "61%", "snow_cover": "11%", "grassland_type": "河谷草地", "degradation_level": "基本稳定", "carrying_capacity_sheep_unit": 19800, "data_source": "sample"},
    {"region_id": "linzhi-bayi", "region_name": "林芝市巴宜区", "scene_date": "2026-05-20", "ndvi": 0.62, "ndvi_change": "+2.1%", "vegetation_cover": "72%", "snow_cover": "8%", "grassland_type": "山地灌丛草甸", "degradation_level": "基本稳定", "carrying_capacity_sheep_unit": 28500, "data_source": "asset_register_reference"},
]

_SAMPLE_SUBJECTS = [
    {"name": "扎西高原牧业合作社", "region_id": "naqu-bange", "region_name": "那曲市班戈县", "subject_type": "合作社", "cattle_count": 1260, "sheep_count": 3200, "grassland_mu": 85000, "credit_amount": "280 万元", "credit_value": 280, "score": 83, "insurance_coverage": "82%", "status": "正常监控", "loan_use": "冬季补饲", "data_source": "sample"},
    {"name": "德吉牦牛养殖联合体", "region_id": "changdu-luolong", "region_name": "昌都市洛隆县", "subject_type": "联合体", "cattle_count": 910, "sheep_count": 1500, "grassland_mu": 62000, "credit_amount": "180 万元", "credit_value": 180, "score": 76, "insurance_coverage": "71%", "status": "关注回款", "loan_use": "活体交易", "data_source": "sample"},
    {"name": "央金家庭牧场", "region_id": "naqu-bange", "region_name": "那曲市班戈县", "subject_type": "家庭牧场", "cattle_count": 380, "sheep_count": 600, "grassland_mu": 18000, "credit_amount": "65 万元", "credit_value": 65, "score": 68, "insurance_coverage": "58%", "status": "需补保险", "loan_use": "补饲", "data_source": "sample"},
    {"name": "仁青冷链供草中心", "region_id": "rikaze-xietongmen", "region_name": "日喀则市谢通门县", "subject_type": "供应商", "cattle_count": 0, "sheep_count": 0, "grassland_mu": 0, "credit_amount": "120 万元", "credit_value": 120, "score": 79, "insurance_coverage": "75%", "status": "正常监控", "loan_use": "饲草采购", "data_source": "sample"},
    {"name": "百巴村牦牛养殖合作社", "region_id": "linzhi-bayi", "region_name": "林芝市巴宜区", "subject_type": "行政村集体", "cattle_count": 1135, "sheep_count": 0, "grassland_mu": 120000, "credit_amount": "500 万元", "credit_value": 500, "score": 91, "insurance_coverage": "待核验", "status": "待人工核验", "loan_use": "牦牛养殖扩产（资产登记参考）", "data_source": "asset_register_reference"},
]

_SAMPLE_FINANCE = [
    {"subject_name": "扎西高原牧业合作社", "credit_line": 350, "used_credit": 280, "interest_rate": "4.35%", "term_months": 36, "repayment_status": "正常", "overdue_times": 0, "data_source": "sample", "policies": [{"type": "牦牛养殖保险", "insured_qty": 1260, "coverage": "82%"}, {"type": "雪灾指数保险", "insured_qty": 85000, "coverage": "100%"}]},
    {"subject_name": "德吉牦牛养殖联合体", "credit_line": 250, "used_credit": 180, "interest_rate": "4.50%", "term_months": 24, "repayment_status": "关注", "overdue_times": 1, "data_source": "sample", "policies": [{"type": "牦牛养殖保险", "insured_qty": 910, "coverage": "71%"}]},
    {"subject_name": "央金家庭牧场", "credit_line": 80, "used_credit": 65, "interest_rate": "4.60%", "term_months": 12, "repayment_status": "正常", "overdue_times": 0, "data_source": "sample", "policies": [{"type": "牦牛养殖保险", "insured_qty": 380, "coverage": "58%"}]},
    {"subject_name": "仁青冷链供草中心", "credit_line": 150, "used_credit": 120, "interest_rate": "4.35%", "term_months": 18, "repayment_status": "正常", "overdue_times": 0, "data_source": "sample", "policies": [{"type": "仓储财产保险", "insured_qty": 0, "coverage": "75%"}]},
    {"subject_name": "百巴村牦牛养殖合作社", "credit_line": 600, "used_credit": 500, "interest_rate": "待核验", "term_months": None, "repayment_status": "待核验", "overdue_times": None, "data_source": "asset_register_reference", "policies": []},
]

# ============================================================================
# 数据访问函数
# ============================================================================

def get_weather(region_id: str | None = None) -> list[dict[str, Any]]:
    rows = _read("weather_data", "SELECT * FROM weather_data ORDER BY observed_at DESC", _SAMPLE_WEATHER)
    for r in rows:
        if "region_name" not in r or not r.get("region_name"):
            r["region_name"] = _REGION_NAMES.get(r.get("region_id", ""), r.get("region_id", ""))
    # 确保林芝数据始终可用（资产登记参考，不代表保险合同或授信记录）
    _ensure_linzhi_data(rows, "weather")
    if region_id:
        return [r for r in rows if r.get("region_id") == region_id]
    return rows


def get_remote_sensing(region_id: str | None = None) -> list[dict[str, Any]]:
    rows = _read("remote_sensing_data", "SELECT * FROM remote_sensing_data ORDER BY scene_date DESC", _SAMPLE_REMOTE)
    for r in rows:
        if "region_name" not in r or not r.get("region_name"):
            r["region_name"] = _REGION_NAMES.get(r.get("region_id", ""), r.get("region_id", ""))
    _ensure_linzhi_data(rows, "remote")
    if region_id:
        return [r for r in rows if r.get("region_id") == region_id]
    return rows


def get_subjects() -> list[dict[str, Any]]:
    rows = _read("business_subjects", "SELECT * FROM business_subjects ORDER BY id", _SAMPLE_SUBJECTS)
    # 统一字段名
    for r in rows:
        if "cattle_count" in r and "cattle" not in r:
            r["cattle"] = r["cattle_count"]
        if "sheep_count" in r and "sheep" not in r:
            r["sheep"] = r["sheep_count"]
        if "subject_type" in r and "type" not in r:
            r["type"] = r["subject_type"]
        if "region_name" in r and "region" not in r:
            r["region"] = r["region_name"]
        if "credit_amount" in r and "credit" not in r:
            r["credit"] = r["credit_amount"]
    return rows


def get_finance() -> list[dict[str, Any]]:
    rows = _read("finance_credit", "SELECT * FROM finance_credit ORDER BY id", _SAMPLE_FINANCE)
    for r in rows:
        if "interest_rate" in r and "rate" not in r:
            r["rate"] = r["interest_rate"]
    return rows


def get_closed_loop_table(table: str) -> list[dict[str, Any]]:
    """读取闭环业务补充表。

    这些表承接保险理赔、产业链资金、客户经理工作流和绿色绩效页面。
    当前数据多为比赛演示脱敏样例，不作为真实生产客户数据。
    """
    try:
        from .store import read_table
    except Exception:
        try:
            from store import read_table
        except Exception:
            return []
    return read_table(table)


def get_closed_loop_data() -> dict[str, list[dict[str, Any]]]:
    return {
        "insurance_claims": get_closed_loop_table("insurance_claims"),
        "supply_chain_orders": get_closed_loop_table("supply_chain_orders"),
        "supply_chain_payments": get_closed_loop_table("supply_chain_payments"),
        "post_loan_workflow": get_closed_loop_table("post_loan_workflow"),
        "green_performance_metrics": get_closed_loop_table("green_performance_metrics"),
    }


def get_alerts() -> list[dict[str, Any]]:
    return [
        {"id": "ALT-001", "level": "高风险", "title": "班戈县暴雪风险升高", "description": "未来 72 小时寒潮叠加降雪。", "action": "补饲预案、保单核验", "time": "2026-05-21 08:00"},
        {"id": "ALT-002", "level": "中风险", "title": "德吉联合体回款周期延长", "description": "最近两笔回款天数升至 31 天。", "action": "核查订单、提示展期", "time": "2026-05-20 16:30"},
        {"id": "ALT-003", "level": "中风险", "title": "央金牧场防疫记录缺失", "description": "近一个月未同步防疫记录。", "action": "补录防疫、限制提额", "time": "2026-05-19 10:15"},
        {"id": "ALT-004", "level": "低风险", "title": "谢通门供草订单履约正常", "description": "订单与回款闭环完整。", "action": "纳入绿色绩效样板", "time": "2026-05-21 09:00"},
    ]


def get_score_model() -> list[dict[str, Any]]:
    return [
        {"name": "主体信用", "weight": 20, "detail": "历史还款、合作年限、履约记录"},
        {"name": "产业经营", "weight": 20, "detail": "存栏规模、订单稳定性、回款周期"},
        {"name": "活体资产", "weight": 15, "detail": "耳标覆盖、防疫记录、出栏记录"},
        {"name": "生态约束", "weight": 15, "detail": "草畜平衡、草场退化程度、轮牧休牧"},
        {"name": "气候风险", "weight": 15, "detail": "暴雪、寒潮、干旱、积雪、NDVI"},
        {"name": "保险保障", "weight": 15, "detail": "投保覆盖率、保额匹配度、险种适配"},
    ]


def get_modules() -> list[dict[str, Any]]:
    return [
        {"code": "eco-monitor", "name": "高原生态与气候风险监测", "value": "为工行绿色信贷准入、额度管理和保险协同提供环境风险底座。", "icon": "cloud-sun", "features": ["草场 NDVI、植被覆盖、积雪覆盖、退化程度监测", "温度、降水、风速、寒潮、暴雪、干旱风险监测", "县域、乡镇、草场片区风险热力图", "灾害风险等级评估和预警推送"]},
        {"code": "grass-balance", "name": "草畜平衡与绿色养殖管理", "value": "把生态约束转化为工行绿色金融可识别、可核验、可跟踪的经营指标。", "icon": "leaf", "features": ["草场面积、类型、可利用草量估算", "牦牛、藏羊存栏规模与载畜量匹配分析", "过牧风险、休牧轮牧、冬季补饲建议", "绿色养殖档案和生态友好型经营评价"]},
        {"code": "supply-chain", "name": "畜牧产业链数字化协同", "value": "围绕工行贷款资金用途，连接饲草采购、活体交易、物流、回款和授信台账。", "icon": "link", "features": ["牧户、合作社、核心企业、饲草供应商和加工企业数字档案", "饲草采购、活体交易、屠宰加工、物流冷链、回款记录管理", "产品溯源和品牌价值展示", "贷款资金定向支付和用途核验"]},
        {"code": "green-finance", "name": "银行绿色金融风控", "value": "帮助工行从看抵押物转向看产业数据、生态数据、保险保障和经营现金流。", "icon": "shield", "features": ["牧户和合作社信用画像", "活体资产确权和经营能力评估", "草场生态风险、气候风险、交易履约和保险覆盖纳入授信评分", "贷款用途绑定、贷中资金流向监控", "贷后动态预警和续贷、展期、减额建议"]},
        {"code": "insurance", "name": "保险风险减量与理赔协同", "value": "把保险作为工行贷前增信、贷中保障和贷后减损的风险缓释工具。", "icon": "umbrella", "features": ["牦牛保险、藏羊保险、雪灾指数保险、草场灾害保险推荐", "承保时校验养殖数量、草场承载能力和历史灾害风险", "出险后结合气象、遥感、耳标、照片视频辅助定损", "理赔结果同步给工行贷后策略"]},
        {"code": "green-perf", "name": "生态价值与绿色绩效评价", "value": "沉淀绿色信贷、生态改善、风险减量和普惠覆盖成效，为工行杯作品形成可汇报指标。", "icon": "trending-up", "features": ["绿色信贷投放与风险分层统计", "高原生态改善趋势评价", "绿色养殖积分或碳账户雏形", "草场保护、轮牧休牧、减灾减损成效展示", "为碳汇、生态补偿、GEP 核算预留接口"]},
        {"code": "livelihood", "name": "边疆民生与治理辅助", "value": "体现项目对边疆地区稳定、牧民增收、乡村振兴和民族团结的支撑作用。", "icon": "users", "features": ["重点区域产业风险监测", "牧户收入和产业稳定性趋势分析", "灾害前预警、灾害中处置、灾害后金融保险支持跟踪", "为政府、银行、保险、合作社提供协同工作台"]},
    ]


def get_data_connections() -> list[dict[str, Any]]:
    return [
        {"name": "气象数据", "source": "区域气象站 / 气象开放 API", "status": "样例可用", "fields": ["温度", "降水", "风速", "寒潮", "暴雪", "干旱"], "source_type": "sample", "api_endpoint": ""},
        {"name": "遥感数据", "source": "卫星影像 / NDVI 栅格计算", "status": "样例可用", "fields": ["NDVI", "积雪覆盖", "植被覆盖", "草地类型", "退化等级"], "source_type": "sample", "api_endpoint": ""},
        {"name": "产业经营数据", "source": "合作社、牧户、供应商管理端导入", "status": "样例可用", "fields": ["存栏", "饲草采购", "活体交易", "物流", "回款"], "source_type": "sample", "api_endpoint": ""},
        {"name": "工行金融数据", "source": "工行授信台账 / 贷后检查 / 还款记录", "status": "样例可用", "fields": ["授信", "用信", "还款", "逾期", "贷后动作"], "source_type": "sample", "api_endpoint": ""},
        {"name": "保险协同数据", "source": "保险保单 / 出险 / 查勘 / 理赔记录", "status": "样例可用", "fields": ["保单", "承保", "出险", "查勘", "理赔"], "source_type": "sample", "api_endpoint": ""},
    ]


_RAW_OUTLINE = {
    "recommended_theme": "工行高原畜牧绿色金融风险评估与贷后管理平台",
    "packaged_name": "牧融绿链",
    "one_sentence": "面向高原牧区，构建以气象遥感、产业经营、工行授信、产业链资金和保险协同为基础的绿色金融风控平台。",
    "core_positioning": "以工行为绿色金融服务主体，把高原畜牧环境风险、经营风险、产业链资金风险和信用风险转化为可审批、可贷后、可处置的业务流程。",
    "logic_chain": ["数据采集", "风险评估", "工行授信", "产业链闭环", "贷后监测", "银保协同", "绿色绩效"],
    "goals": [
        {"name": "生态可监测", "desc": "通过遥感、气象、NDVI、积雪、草场类型和载畜量数据，动态评估高原生态状态。"},
        {"name": "产业可增值", "desc": "通过养殖、交易、物流、加工和溯源数据，推动高原畜牧产业数字化转型。"},
        {"name": "工行可准入", "desc": "为牧户、合作社、供应商形成可解释的授信准入、额度和复核建议。"},
        {"name": "贷后可预警", "desc": "通过灾害预警、草畜平衡提示、回款异常和保险联动，前移贷后风险管理。"},
        {"name": "绿色可评价", "desc": "沉淀绿色信贷、生态改善、普惠覆盖和风险减量指标，服务工行绿色金融管理。"},
    ],
    "pain_points": [
        {"title": "生态痛点", "items": ["草场退化、沙化、过牧、积雪灾害、干旱和寒潮频发。", "传统管理难以及时判断草场承载力和灾害风险。"]},
        {"title": "产业痛点", "items": ["牦牛、藏羊养殖分散、数字化程度低。", "交易链条短、产品溢价不足、草料调配效率低。"]},
        {"title": "工行风控痛点", "items": ["牧户和合作社缺少传统抵押物，传统授信材料不足。", "客户经理难以同时核验活体资产、草场环境、经营现金流和灾害风险。"]},
        {"title": "保险痛点", "items": ["承保验标难、定损理赔慢、骗保风险高。", "传统保险模式难适应高寒、分散的牧区场景。"]},
        {"title": "民生与治理痛点", "items": ["高原牧区与边疆地区高度重合。", "产业稳定关系牧民收入、乡村振兴和边疆稳定。"]},
    ],
    "benefits": {
        "eco": ["构建气象遥感灾害风险管理体系，降低灾害损失。", "通过草畜平衡测算指导科学轮牧休牧。", "推动高原生态与产业发展深度融合。"],
        "economic": ["实现高原畜牧产业精细化、智能化管理。", "构建普惠化金融保险服务体系。", "挖掘高原畜牧碳汇价值。"],
        "social": ["推动高原畜牧产业数字化转型。", "提升高原地区居民收入与生活质量。", "保障高原特色畜产品质量安全。"],
    },
    "roadmap": [
        {"step": "阶段 1", "title": "工行授信场景建模", "outputs": ["授信对象池", "准入规则", "贷后动作字典"]},
        {"step": "阶段 2", "title": "多源数据资产接入", "outputs": ["气象遥感数据表", "经营主体台账", "工行授信/还款/逾期样例表"]},
        {"step": "阶段 3", "title": "风险评估工作台上线", "outputs": ["风险对象池", "评估报告", "证据链", "处置队列"]},
        {"step": "阶段 4", "title": "银保协同与绿色绩效", "outputs": ["保险缓释记录", "贷后闭环", "绿色金融绩效指标"]},
    ],
    "demo_story": {
        "title": "某边疆牧区冬季补饲闭环",
        "steps": ["系统识别 NDVI 下降与积雪风险。", "平台识别合作社冬季补饲资金需求。", "工行客户经理查看信用、存栏、草场、订单和保险证据链后给出绿色补饲贷款建议。", "贷款资金定向支付给备案饲草供应商。", "同步推荐雪灾指数保险和牦牛养殖保险。", "暴雪预警后系统推送补饲、防寒和贷后核查建议。", "若发生损失，理赔结果同步工行贷后策略。"],
    },
    "innovation_points": ["把高原气象遥感数据纳入工行授信准入", "把草畜平衡变成可量化的贷后预警指标", "把保险从理赔工具变成工行贷前增信和贷后减损工具", "把客户经理评估动作沉淀为可追溯证据链", "把绿色金融绩效从口径汇报变成系统指标"],
    "why_upgrade": [
        {"title": "提高项目高度", "desc": "从单一金融科技工具升级为服务生态、产业、金融、民生的综合方案。"},
        {"title": "补齐数据底座", "desc": "把气象、遥感、产业、金融和保险数据纳入统一接口。"},
        {"title": "强化落地能力", "desc": "围绕监测、预警、授信、保险和治理协同搭建系统能力。"},
    ],
    "data_scheme": {
        "public_data": ["气象数据", "遥感数据", "统计数据", "市场数据", "地理数据"],
        "sample_data": ["牧户和合作社档案", "存栏/出栏/防疫记录", "饲草/交易/回款记录", "授信/还款/逾期记录", "保单/查勘/理赔记录"],
        "principles": ["比赛版采用公开区域数据 + 典型主体样例数据 + 业务规则模型", "金融和保险明细优先使用脱敏模拟数据", "平台先搭建数据闭环再接入真实后端接口"],
    },
    "tech_layers": [
        {"name": "物联网感知层", "desc": "气象站、传感器、电子耳标、视频监控。"},
        {"name": "云计算平台层", "desc": "计算、存储、网络，支撑产业数据集中存储处理。"},
        {"name": "AI 算法层", "desc": "灾害预警、草畜平衡、保险定损、信用评价算法。"},
        {"name": "数据安全保障", "desc": "脱敏、加密传输、访问控制。"},
    ],
}


def get_outline() -> dict[str, Any]:
    return dict(_RAW_OUTLINE)


_REGION_LIST_PATH = Path(__file__).resolve().parents[1] / "public_data" / "region_list.csv"


def _load_regions_from_csv() -> list[dict[str, Any]]:
    """从 public_data/region_list.csv 动态加载区域清单。"""
    import csv
    if not _REGION_LIST_PATH.exists():
        return _FALLBACK_REGIONS
    rows = []
    with open(_REGION_LIST_PATH, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({
                "id": r.get("region_id", ""),
                "name": r.get("region_name", r.get("county", "")),
                "province": r.get("province", ""),
                "city": r.get("city", ""),
                "longitude": r.get("longitude", ""),
                "latitude": r.get("latitude", ""),
                "altitude": r.get("altitude", ""),
                "pasture_type": r.get("pasture_type", ""),
                "is_demo": r.get("is_demo", "0") == "1",
                "type": "示范县" if r.get("is_demo", "0") == "1" else "",
                "risk_level": "中",
                "metrics": {},
                "suggestion": "样例数据，待导入真实气象和遥感数据。",
            })
    return rows if rows else _FALLBACK_REGIONS


_FALLBACK_REGIONS = [
    {"id": "naqu-bange", "name": "那曲市班戈县", "type": "冬春补饲重点区", "risk_level": "高", "metrics": {"生态风险指数": "72", "草畜平衡压力": "偏高", "NDVI较常年": "-8.6%", "积雪覆盖": "31%", "授信余额": "1,860 万元", "保险覆盖率": "78%"}, "suggestion": "样例数据，仅用于演示。"},
    {"id": "changdu-luolong", "name": "昌都市洛隆县", "type": "产业链协同提升区", "risk_level": "中", "metrics": {"生态风险指数": "64", "草畜平衡压力": "可控", "NDVI较常年": "-3.2%", "积雪覆盖": "18%", "授信余额": "1,220 万元", "保险覆盖率": "69%"}, "suggestion": "样例数据，仅用于演示。"},
    {"id": "rikaze-xietongmen", "name": "日喀则市谢通门县", "type": "绿色绩效观察区", "risk_level": "低", "metrics": {"生态风险指数": "58", "草畜平衡压力": "较低", "NDVI较常年": "+1.4%", "积雪覆盖": "11%", "授信余额": "930 万元", "保险覆盖率": "62%"}, "suggestion": "样例数据，仅用于演示。"},
    {"id": "linzhi-bayi", "name": "林芝市巴宜区", "type": "绿色金融示范区", "risk_level": "低", "metrics": {"生态风险指数": "42", "草畜平衡压力": "低", "NDVI较常年": "+2.1%", "积雪覆盖": "8%", "授信余额": "3,200 万元", "保险覆盖率": "待核验"}, "suggestion": "含1135条牲畜资产登记参考记录；保险合同与授信信息待人工核验。"},
]

_REGION_NAMES: dict[str, str] = {}


def _init_region_names() -> dict[str, str]:
    regions = _load_regions_from_csv()
    return {r["id"]: r["name"] for r in regions}


def get_regions() -> list[dict[str, Any]]:
    return _load_regions_from_csv()


# ============================================================================
# 风险评估（每次调用时基于最新数据动态重算）
# 四类驱动因素：气象风险 + 遥感生态 + 主体经营 + 金融保险
# ============================================================================

def get_risk_assessment() -> list[dict[str, Any]]:
    """基于当前最新数据动态计算风险评估。

    四维驱动:
      1. 气象风险 (30%) — 寒潮/暴雪/干旱等级
      2. 遥感生态 (25%) — NDVI变化 + 退化等级
      3. 主体经营 (20%) — 平均信用评分 + 保险覆盖率
      4. 金融保险 (25%) — 还款状态 + 逾期次数
      区域基准分占 0%（由四维完全决定）
    """
    regions = get_regions()
    weather_list = get_weather()
    remote_list = get_remote_sensing()
    subjects_list = get_subjects()
    finance_list = get_finance()

    # 按 region_id 索引
    weather_by: dict[str, dict[str, Any]] = {}
    for w in weather_list:
        rid = w.get("region_id", "")
        if rid not in weather_by:
            weather_by[rid] = w  # 取第一条

    remote_by: dict[str, dict[str, Any]] = {}
    for r in remote_list:
        rid = r.get("region_id", "")
        if rid not in remote_by:
            remote_by[rid] = r

    # 按区域聚合主体数据
    subj_by_region: dict[str, list[dict[str, Any]]] = {}
    for s in subjects_list:
        rid = s.get("region_id", "")
        if rid not in subj_by_region:
            subj_by_region[rid] = []
        subj_by_region[rid].append(s)

    # 按主体名聚合金融数据
    fin_by_name: dict[str, dict[str, Any]] = {}
    for f in finance_list:
        fin_by_name[f.get("subject_name", "")] = f

    # --- 评分映射 ---
    risk_level_score = {"低": 20, "中": 45, "高": 70}
    degradation_score = {"基本稳定": 20, "轻度退化": 45, "中度退化": 70, "重度退化": 90}
    repayment_penalty = {"正常": 0, "关注": 20, "逾期": 45, "异常": 60}

    assessments = []
    for region in regions:
        rid = region["id"]
        w = weather_by.get(rid)
        r = remote_by.get(rid)
        subjs = subj_by_region.get(rid, [])
        drivers: list[str] = []
        detail: dict[str, Any] = {}

        # ----- 1. 气象风险 (0-100) -----
        if w:
            wx_score = max(
                risk_level_score.get(w.get("cold_wave_risk", "中"), 45),
                risk_level_score.get(w.get("snowstorm_risk", "中"), 45),
                risk_level_score.get(w.get("drought_risk", "中"), 45),
            )
            drivers.append(
                f"气象风险：寒潮{w.get('cold_wave_risk','-')}、暴雪{w.get('snowstorm_risk','-')}、干旱{w.get('drought_risk','-')}（得分 {wx_score}）"
            )
        else:
            wx_score = 50
            drivers.append("气象风险：无数据，默认 50 分")
        detail["weather_score"] = wx_score

        # ----- 2. 遥感生态 (0-100) -----
        if r:
            rs_score = degradation_score.get(r.get("degradation_level", "轻度退化"), 45)
            ndvi_val = r.get("ndvi", None)
            ndvi_change = r.get("ndvi_change", "")
            # NDVI 偏低加重
            if ndvi_val is not None and isinstance(ndvi_val, (int, float)) and ndvi_val < 0.4:
                rs_score = min(100, rs_score + 10)
            if ndvi_change.startswith("-"):
                try:
                    pct = float(ndvi_change.replace("%", "").replace("-", ""))
                    if pct > 5:
                        rs_score = min(100, rs_score + 10)
                except ValueError:
                    pass
            drivers.append(
                f"遥感生态：NDVI {r.get('ndvi','-')}（{r.get('ndvi_change','-')}），{r.get('degradation_level','-')}，积雪覆盖 {r.get('snow_cover','-')}（得分 {rs_score}）"
            )
        else:
            rs_score = 50
            drivers.append("遥感生态：无数据，默认 50 分")
        detail["remote_score"] = rs_score

        # ----- 3. 主体经营 (0-100) -----
        if subjs:
            avg_score = sum(s.get("score", 70) for s in subjs) / len(subjs)
            # score 越高 → 经营风险越低
            biz_risk = max(0, min(100, 100 - avg_score))

            # 保险覆盖率低加重风险
            coverages = []
            for s in subjs:
                cov_str = str(s.get("insurance_coverage", "0%")).replace("%", "")
                try:
                    coverages.append(float(cov_str))
                except ValueError:
                    coverages.append(0)
            avg_coverage = sum(coverages) / len(coverages) if coverages else 0
            if avg_coverage < 60:
                biz_risk = min(100, biz_risk + 15)
            elif avg_coverage < 75:
                biz_risk = min(100, biz_risk + 5)

            drivers.append(
                f"主体经营：{len(subjs)} 户主体，平均评分 {avg_score:.0f}，平均保险覆盖率 {avg_coverage:.0f}%（得分 {round(biz_risk)}）"
            )
        else:
            biz_risk = 50
            drivers.append("主体经营：无数据，默认 50 分")
        detail["business_score"] = round(biz_risk)

        # ----- 4. 金融保险 (0-100) -----
        fin_risk = 50
        if subjs and fin_by_name:
            fin_scores = []
            for s in subjs:
                fn = s.get("name", "")
                fdata = fin_by_name.get(fn)
                if fdata:
                    overdue = int(fdata.get("overdue_times", 0))
                    status = str(fdata.get("repayment_status", "正常"))
                    # 还款状态惩罚
                    base_fin = repayment_penalty.get(status, 0)
                    # 逾期加重
                    base_fin = min(100, base_fin + overdue * 15)
                    fin_scores.append(base_fin)

            if fin_scores:
                fin_risk = sum(fin_scores) / len(fin_scores)

            # 统计
            overdue_total = sum(
                int(fin_by_name.get(s.get("name", ""), {}).get("overdue_times", 0))
                for s in subjs if s.get("name", "") in fin_by_name
            )
            abnormal_count = sum(
                1 for s in subjs
                if fin_by_name.get(s.get("name", ""), {}).get("repayment_status", "正常") != "正常"
            )
            drivers.append(
                f"金融保险：{len(subjs)} 户中 {abnormal_count} 户还款异常，累计逾期 {overdue_total} 次（得分 {round(fin_risk)}）"
            )
        else:
            drivers.append("金融保险：无数据，默认 50 分")
        detail["finance_score"] = round(fin_risk)

        # ----- 综合评分 -----
        total = round(
            wx_score * 0.30 +
            rs_score * 0.25 +
            biz_risk * 0.20 +
            fin_risk * 0.25
        )
        level = "高" if total >= 70 else "中" if total >= 50 else "低"

        assessments.append({
            "region_id": rid,
            "region_name": region["name"],
            "score": total,
            "level": level,
            "drivers": drivers,
            "detail": detail,
            "recommendation": region.get("suggestion", ""),
        })
    return assessments


# ============================================================================
# 全量平台数据
# ============================================================================

def build_platform_data() -> dict[str, Any]:
    outline = get_outline()

    # 尝试加载模型预测结果
    model_pred = None
    try:
        from .models import get_model
        model_pred = get_model().predict()
    except Exception:
        try:
            from models import get_model
            model_pred = get_model().predict()
        except Exception:
            pass

    risk_data = get_risk_assessment()
    # 如果有模型预测，用模型输出增强风险评估
    if model_pred and "predictions" in model_pred:
        for r in risk_data:
            for mp in model_pred["predictions"]:
                if mp["region_id"] == r["region_id"]:
                    r["model_score"] = mp["predicted_score"]
                    r["model_level"] = mp["predicted_level"]
                    r["model_confidence"] = model_pred.get("confidence", 0)
                    r["model_type"] = model_pred.get("model_type", "rule")
                    r["model_drivers"] = mp.get("drivers", {})
                    break

    return {
        "brand": {
            "name": "牧融绿链",
            "title": "工行高原畜牧绿色金融风险评估、产业链闭环与贷后管理平台",
            "summary": "面向高原牧区，汇聚气象遥感、产业经营、工行授信、产业链资金、还款逾期和保险理赔数据，服务工行绿色信贷准入、产业链资金闭环、贷后预警、银保协同和绿色金融绩效评价。",
            "logic": outline["logic_chain"],
            "goals": [g["name"] for g in outline["goals"]],
        },
        "data_sources": outline["data_scheme"]["public_data"],
        "regions": get_regions(),
        "modules": get_modules(),
        "score_model": get_score_model(),
        "subjects": get_subjects(),
        "finance": get_finance(),
        "closed_loop": get_closed_loop_data(),
        "alerts": get_alerts(),
        "weather": get_weather(),
        "remote_sensing": get_remote_sensing(),
        "risk_assessment": risk_data,
        "data_connections": get_data_connections(),
        "outline": outline,
        "digital_solution": outline,
        "model_status": model_pred.get("model_type", "rule") if model_pred else "rule",
        "model_confidence": model_pred.get("confidence", 0) if model_pred else 0,
    }


# 兼容旧代码
PLATFORM_DATA = build_platform_data()
