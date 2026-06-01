"""
牧融绿链 - JSON 文件数据存储层
============================================================================
无 MySQL 时的持久化方案。每个"表"对应一个 JSON 文件，存放在 backend/data/ 目录。

数据流:
  管理端 CSV 上传 → store.import_rows() 写入 JSON → data.py 读取 → 前端刷新
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 数据存储目录
STORE_DIR = Path(__file__).resolve().parent / "data_store"
STORE_DIR.mkdir(parents=True, exist_ok=True)

# 表定义：表名 → { 文件名, CSV 列映射 }
TABLES: dict[str, dict[str, Any]] = {
    "weather_data": {
        "file": "weather_data.json",
        "label": "气象监测数据",
        "columns": [
            "region_id", "station", "observed_at",
            "temperature_c", "precipitation_mm_24h", "wind_speed_mps",
            "snow_depth_cm", "cold_wave_risk", "snowstorm_risk", "drought_risk",
        ],
        "required": ["region_id", "station"],
    },
    "remote_sensing_data": {
        "file": "remote_sensing_data.json",
        "label": "遥感生态指标",
        "columns": [
            "region_id", "scene_date", "ndvi", "ndvi_change",
            "vegetation_cover", "snow_cover", "grassland_type",
            "degradation_level", "carrying_capacity_sheep_unit",
            "capacity_data_source", "capacity_is_sample", "capacity_derived",
        ],
        "required": ["region_id"],
    },
    "business_subjects": {
        "file": "business_subjects.json",
        "label": "经营主体",
        "columns": [
            "name", "region_id", "region_name", "subject_type",
            "cattle_count", "sheep_count", "grassland_mu",
            "credit_amount", "credit_value", "score",
            "insurance_coverage", "status", "loan_use",
        ],
        "required": ["name", "region_id"],
    },
    "finance_credit": {
        "file": "finance_credit.json",
        "label": "金融保险",
        "columns": [
            "subject_name", "credit_line", "used_credit",
            "interest_rate", "term_months", "repayment_status", "overdue_times",
        ],
        "required": ["subject_name"],
    },
    "forage_supply_demand": {
        "file": "forage_supply_demand.json",
        "label": "全国饲草供需宏观数据",
        "columns": [
            "region_cn", "region_en", "year",
            "natural_grassland_forage_10e7kg",
            "crop_straw_forage_10e7kg",
            "forage_demand_10e7kg",
            "total_forage_supply_10e7kg",
            "supply_demand_gap_10e7kg",
            "supply_demand_ratio",
            "data_source", "source_id", "dataset_name", "is_sample",
        ],
        "required": ["region_cn", "year"],
    },
    "risk_event_labels": {
        "file": "risk_event_labels.json",
        "label": "风险事件标签（真实灾害/理赔/逾期）",
        "columns": [
            "region_id", "event_month", "event_type",
            "severity", "loss_amount", "claim_amount",
            "overdue_flag", "source", "source_url",
            "is_real_label", "note",
        ],
        "required": ["region_id", "event_type"],
    },
    "insurance_claims": {
        "file": "insurance_claims.json",
        "label": "银保协同理赔与查勘",
        "columns": [
            "claim_id", "policy_id", "subject_name", "region_id", "event_month",
            "insurance_type", "claim_status", "survey_status", "insured_amount",
            "claim_amount", "linked_credit_id", "post_loan_feedback",
        ],
        "required": ["claim_id", "subject_name"],
    },
    "supply_chain_orders": {
        "file": "supply_chain_orders.json",
        "label": "产业链订单台账",
        "columns": [
            "order_id", "subject_name", "region_id", "order_type", "supplier",
            "amount", "order_date", "delivery_status", "linked_credit_id",
            "payment_id", "fund_usage_status", "risk_note",
        ],
        "required": ["order_id", "subject_name"],
    },
    "supply_chain_payments": {
        "file": "supply_chain_payments.json",
        "label": "工行贷款资金流向",
        "columns": [
            "payment_id", "order_id", "from_account", "to_account", "amount",
            "channel", "status", "payment_date", "verification_status",
        ],
        "required": ["payment_id", "order_id"],
    },
    "post_loan_workflow": {
        "file": "post_loan_workflow.json",
        "label": "客户经理贷后工作流",
        "columns": [
            "task_id", "subject_name", "region_id", "workflow_stage", "trigger_type",
            "risk_score", "assigned_to", "due_date", "task_status",
            "action_result", "next_action",
        ],
        "required": ["task_id", "subject_name"],
    },
    "green_performance_metrics": {
        "file": "green_performance_metrics.json",
        "label": "绿色绩效与民生指标",
        "columns": [
            "metric_id", "region_id", "metric_month", "metric_type", "metric_name",
            "metric_value", "unit", "evidence_source", "business_stage", "note",
        ],
        "required": ["metric_id", "metric_type"],
    },
}

# 类型转换
_COLUMN_TYPES: dict[str, type] = {
    "temperature_c": float,
    "precipitation_mm_24h": float,
    "wind_speed_mps": float,
    "snow_depth_cm": int,
    "ndvi": float,
    "carrying_capacity_sheep_unit": int,
    "cattle_count": int,
    "sheep_count": int,
    "grassland_mu": int,
    "credit_value": float,
    "credit_line": float,
    "used_credit": float,
    "score": int,
    "term_months": int,
    "overdue_times": int,
    "insured_amount": float,
    "claim_amount": float,
    "amount": float,
    "risk_score": float,
    "metric_value": float,
}


# ---------------------------------------------------------------------------
# 读写操作
# ---------------------------------------------------------------------------

def _file_path(table: str) -> Path:
    """获取表的 JSON 文件路径。"""
    info = TABLES.get(table, {})
    filename = info.get("file", f"{table}.json")
    return STORE_DIR / filename


def read_table(table: str) -> list[dict[str, Any]]:
    """读取整张表。"""
    path = _file_path(table)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, OSError):
        return []


def write_table(table: str, rows: list[dict[str, Any]]) -> int:
    """覆盖写入整张表，返回行数。"""
    path = _file_path(table)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(rows)


def append_rows(table: str, new_rows: list[dict[str, Any]]) -> int:
    """追加行到已有表。"""
    existing = read_table(table)
    existing.extend(new_rows)
    return write_table(table, existing)


def replace_table(table: str, new_rows: list[dict[str, Any]]) -> int:
    """替换整张表（清空后写入）。"""
    return write_table(table, new_rows)


def table_info(table: str) -> dict[str, Any]:
    """获取表信息。"""
    rows = read_table(table)
    return {
        "table": table,
        "label": TABLES.get(table, {}).get("label", table),
        "row_count": len(rows),
        "columns": TABLES.get(table, {}).get("columns", []),
        "file": str(_file_path(table)),
    }


def all_tables_info() -> list[dict[str, Any]]:
    """获取所有表信息。"""
    return [table_info(t) for t in TABLES]


# ---------------------------------------------------------------------------
# CSV 导入
# ---------------------------------------------------------------------------

def parse_csv_rows(csv_text: str, table: str) -> tuple[list[dict[str, Any]], list[str]]:
    """解析 CSV 文本为字典列表。

    Returns:
        (rows, warnings) - 解析成功的行列表 + 警告信息列表
    """
    import csv
    import io

    table_def = TABLES.get(table)
    if not table_def:
        return [], [f"未知数据表: {table}"]

    expected_columns = table_def["columns"]
    required_columns = table_def.get("required", [])

    reader = csv.DictReader(io.StringIO(csv_text))
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    # 检查 CSV 列名是否匹配
    csv_columns = reader.fieldnames or []
    missing = [c for c in required_columns if c not in csv_columns]
    if missing:
        warnings.append(f"CSV 缺少必需列: {', '.join(missing)}")

    for line_num, raw_row in enumerate(reader, start=2):
        row: dict[str, Any] = {}
        skip = False

        for col in expected_columns:
            val = raw_row.get(col, "").strip()
            if val == "":
                if col in required_columns:
                    warnings.append(f"第 {line_num} 行缺少必需字段: {col}")
                    skip = True
                    break
                row[col] = None
                continue

            # 类型转换
            py_type = _COLUMN_TYPES.get(col, str)
            try:
                if py_type is int:
                    row[col] = int(float(val))
                elif py_type is float:
                    row[col] = float(val)
                else:
                    row[col] = val
            except (ValueError, TypeError):
                warnings.append(f"第 {line_num} 行字段 {col} 类型错误: '{val}'")
                row[col] = val

        if not skip:
            # ---- 保留 CSV 中的来源字段，不强制覆盖 ----
            _PROVENANCE_FIELDS = [
                "data_source", "source_id", "dataset_name",
                "source_url", "license", "downloaded_at",
                "processed_at", "is_sample", "is_simulated",
            ]
            for pf in _PROVENANCE_FIELDS:
                if pf in raw_row and raw_row[pf].strip() != "":
                    val = raw_row[pf].strip()
                    # is_sample / is_simulated 字符串转布尔
                    if pf == "is_sample":
                        row[pf] = val.lower() in ("true", "1", "yes", "t")
                    elif pf == "is_simulated":
                        row[pf] = val.lower() in ("true", "1", "yes", "t")
                    else:
                        row[pf] = val
            # 如果 CSV 没有 data_source，才设为 csv
            if "data_source" not in row:
                row["data_source"] = "csv"
            # 时间戳
            if "imported_at" not in row:
                row["imported_at"] = datetime.now(timezone.utc).isoformat()
            rows.append(row)

    return rows, warnings


def import_csv_to_table(csv_text: str, table: str, mode: str = "replace") -> dict[str, Any]:
    """导入 CSV 数据到指定表。

    Args:
        csv_text: CSV 文件内容
        table: 目标表名
        mode: "replace"(替换) 或 "append"(追加)

    Returns:
        {ok, table, row_count, warnings, table_info}
    """
    rows, warnings = parse_csv_rows(csv_text, table)

    if not rows and warnings:
        return {
            "ok": False,
            "table": table,
            "row_count": 0,
            "warnings": warnings,
            "message": "CSV 解析失败，没有有效数据行",
        }

    if mode == "append":
        count = append_rows(table, rows)
    else:
        count = replace_table(table, rows)

    # 记录导入元数据（从第一行读取来源信息）
    provenance = {}
    if rows:
        first = rows[0]
        for pf in ("data_source", "source_id", "dataset_name", "source_url", "license", "downloaded_at", "processed_at", "is_sample"):
            if pf in first:
                provenance[pf] = first[pf]
    _log_import_metadata(table, count, mode, provenance)

    return {
        "ok": True,
        "table": table,
        "label": TABLES.get(table, {}).get("label", table),
        "row_count": count,
        "warnings": warnings,
        "message": f"成功导入 {count} 行数据到 {table}",
        "table_info": table_info(table),
    }


# ---------------------------------------------------------------------------
# 导入元数据
# ---------------------------------------------------------------------------

_META_FILE = STORE_DIR / "import_metadata.json"


def _log_import_metadata(table: str, row_count: int, mode: str, provenance: dict[str, Any] | None = None) -> None:
    """记录每次 CSV 导入的元数据。"""
    meta = []
    if _META_FILE.exists():
        try:
            meta = json.loads(_META_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            meta = []

    prov = provenance or {}
    is_sample_val = prov.get("is_sample", table.startswith("sample_"))
    if isinstance(is_sample_val, str):
        is_sample_val = is_sample_val.lower() in ("true", "1", "yes", "t")

    meta.append({
        "source_id": prov.get("source_id", "csv_upload"),
        "dataset_name": prov.get("dataset_name", table),
        "source_url": prov.get("source_url", ""),
        "license": prov.get("license", ""),
        "downloaded_at": prov.get("downloaded_at"),
        "processed_at": prov.get("processed_at"),
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "original_filename": prov.get("original_filename", ""),
        "row_count": row_count,
        "table": table,
        "import_mode": mode,
        "is_sample": is_sample_val,
        "data_source": prov.get("data_source", "csv"),
    })
    _META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# 初始化：首次运行时用样例数据填充
# ---------------------------------------------------------------------------

def _init_sample_data() -> None:
    """首次运行时，将样例数据写入 JSON 文件。"""
    # 只初始化还没有数据的表
    if _file_path("weather_data").exists():
        return

    print("[store] 首次运行，写入样例数据...")

    weather = [
        {"region_id": "naqu-bange", "station": "班戈县高原气象站", "observed_at": "2026-05-21 08:00", "temperature_c": -3.8, "precipitation_mm_24h": 11.6, "wind_speed_mps": 8.2, "snow_depth_cm": 18, "cold_wave_risk": "高", "snowstorm_risk": "高", "drought_risk": "低", "data_source": "sample"},
        {"region_id": "changdu-luolong", "station": "洛隆县牧区气象站", "observed_at": "2026-05-21 08:00", "temperature_c": 2.4, "precipitation_mm_24h": 4.8, "wind_speed_mps": 5.1, "snow_depth_cm": 7, "cold_wave_risk": "中", "snowstorm_risk": "中", "drought_risk": "低", "data_source": "sample"},
        {"region_id": "rikaze-xietongmen", "station": "谢通门县生态监测站", "observed_at": "2026-05-21 08:00", "temperature_c": 5.7, "precipitation_mm_24h": 1.2, "wind_speed_mps": 3.6, "snow_depth_cm": 2, "cold_wave_risk": "低", "snowstorm_risk": "低", "drought_risk": "中", "data_source": "sample"},
    ]
    remote = [
        {"region_id": "naqu-bange", "scene_date": "2026-05-20", "ndvi": 0.34, "ndvi_change": "-8.6%", "vegetation_cover": "42%", "snow_cover": "31%", "grassland_type": "高寒草甸", "degradation_level": "中度退化", "carrying_capacity_sheep_unit": 18200, "data_source": "sample"},
        {"region_id": "changdu-luolong", "scene_date": "2026-05-20", "ndvi": 0.47, "ndvi_change": "-3.2%", "vegetation_cover": "55%", "snow_cover": "18%", "grassland_type": "山地草甸", "degradation_level": "轻度退化", "carrying_capacity_sheep_unit": 23600, "data_source": "sample"},
        {"region_id": "rikaze-xietongmen", "scene_date": "2026-05-20", "ndvi": 0.52, "ndvi_change": "+1.4%", "vegetation_cover": "61%", "snow_cover": "11%", "grassland_type": "河谷草地", "degradation_level": "基本稳定", "carrying_capacity_sheep_unit": 19800, "data_source": "sample"},
    ]
    subjects = [
        {"name": "扎西高原牧业合作社", "region_id": "naqu-bange", "region_name": "那曲市班戈县", "subject_type": "合作社", "cattle_count": 1260, "sheep_count": 3200, "grassland_mu": 85000, "credit_amount": "280 万元", "credit_value": 280, "score": 83, "insurance_coverage": "82%", "status": "正常监控", "loan_use": "冬季补饲、牦牛防疫、饲草采购", "data_source": "sample"},
        {"name": "德吉牦牛养殖联合体", "region_id": "changdu-luolong", "region_name": "昌都市洛隆县", "subject_type": "联合体", "cattle_count": 910, "sheep_count": 1500, "grassland_mu": 62000, "credit_amount": "180 万元", "credit_value": 180, "score": 76, "insurance_coverage": "71%", "status": "关注回款", "loan_use": "活体交易、订单履约、冷链物流", "data_source": "sample"},
        {"name": "央金家庭牧场", "region_id": "naqu-bange", "region_name": "那曲市班戈县", "subject_type": "家庭牧场", "cattle_count": 380, "sheep_count": 600, "grassland_mu": 18000, "credit_amount": "65 万元", "credit_value": 65, "score": 68, "insurance_coverage": "58%", "status": "需补保险", "loan_use": "补饲、棚圈修缮、防疫服务", "data_source": "sample"},
        {"name": "仁青冷链供草中心", "region_id": "rikaze-xietongmen", "region_name": "日喀则市谢通门县", "subject_type": "供应商", "cattle_count": 0, "sheep_count": 0, "grassland_mu": 0, "credit_amount": "120 万元", "credit_value": 120, "score": 79, "insurance_coverage": "75%", "status": "正常监控", "loan_use": "饲草采购、仓储周转、运输结算", "data_source": "sample"},
    ]
    finance = [
        {"subject_name": "扎西高原牧业合作社", "credit_line": 350, "used_credit": 280, "interest_rate": "4.35%", "term_months": 36, "repayment_status": "正常", "overdue_times": 0, "data_source": "sample"},
        {"subject_name": "德吉牦牛养殖联合体", "credit_line": 250, "used_credit": 180, "interest_rate": "4.50%", "term_months": 24, "repayment_status": "关注", "overdue_times": 1, "data_source": "sample"},
        {"subject_name": "央金家庭牧场", "credit_line": 80, "used_credit": 65, "interest_rate": "4.60%", "term_months": 12, "repayment_status": "正常", "overdue_times": 0, "data_source": "sample"},
        {"subject_name": "仁青冷链供草中心", "credit_line": 150, "used_credit": 120, "interest_rate": "4.35%", "term_months": 18, "repayment_status": "正常", "overdue_times": 0, "data_source": "sample"},
    ]

    write_table("weather_data", weather)
    write_table("remote_sensing_data", remote)
    write_table("business_subjects", subjects)
    write_table("finance_credit", finance)
    print(f"[store] 样例数据已写入 {STORE_DIR}")


# 启动时自动初始化
_init_sample_data()
