"""
build_public_samples.py
============================================================================
根据 public_data/sources.json 的数据源定义，生成 samples/ 下的四类样例 CSV。

用法:
    cd D:\工行杯\yak-risk-platform
    python public_data/scripts/build_public_samples.py

生成文件:
    public_data/samples/weather_data_public_sample.csv
    public_data/samples/remote_sensing_public_sample.csv
    public_data/samples/business_subjects_demo.csv
    public_data/samples/finance_credit_demo.csv

后续扩展:
    - 可在此脚本中添加真实数据下载函数（GEE API、CMA API 等）
    - 可添加 NetCDF/GeoTIFF 裁剪和 CSV 转换逻辑
"""

import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "samples"

# 系统已有的三个示范区
REGIONS = [
    {"id": "naqu-bange", "name": "那曲市班戈县"},
    {"id": "changdu-luolong", "name": "昌都市洛隆县"},
    {"id": "rikaze-xietongmen", "name": "日喀则市谢通门县"},
]

# ============================================================================
# 数据生成函数
# ============================================================================


def build_weather_csv() -> list[dict]:
    """生成气象监测样例数据。"""
    rows = []
    # 为每个区域生成 3 个时间点的数据（冬/春/夏）
    timepoints = [
        ("2026-01-15 08:00", "冬季"),
        ("2026-03-20 08:00", "春季"),
        ("2026-05-21 08:00", "春末"),
    ]

    profiles = {
        "naqu-bange": {
            "station": "班戈县高原气象站",
            "winter": {"temp": -15.2, "precip": 2.1, "wind": 9.5, "snow": 24, "cold": "高", "snowstorm": "高", "drought": "低"},
            "spring": {"temp": -6.8, "precip": 8.3, "wind": 7.2, "snow": 18, "cold": "中", "snowstorm": "高", "drought": "低"},
            "late_spring": {"temp": -3.8, "precip": 11.6, "wind": 8.2, "snow": 18, "cold": "高", "snowstorm": "高", "drought": "低"},
        },
        "changdu-luolong": {
            "station": "洛隆县牧区气象站",
            "winter": {"temp": -8.5, "precip": 1.2, "wind": 6.8, "snow": 11, "cold": "中", "snowstorm": "中", "drought": "低"},
            "spring": {"temp": -2.1, "precip": 5.4, "wind": 4.8, "snow": 8, "cold": "低", "snowstorm": "中", "drought": "中"},
            "late_spring": {"temp": 2.4, "precip": 4.8, "wind": 5.1, "snow": 7, "cold": "中", "snowstorm": "中", "drought": "低"},
        },
        "rikaze-xietongmen": {
            "station": "谢通门县生态监测站",
            "winter": {"temp": -5.2, "precip": 0.3, "wind": 4.2, "snow": 3, "cold": "低", "snowstorm": "低", "drought": "中"},
            "spring": {"temp": 1.8, "precip": 2.1, "wind": 3.8, "snow": 1, "cold": "低", "snowstorm": "低", "drought": "低"},
            "late_spring": {"temp": 5.7, "precip": 1.2, "wind": 3.6, "snow": 2, "cold": "低", "snowstorm": "低", "drought": "中"},
        },
    }

    for tp_date, tp_key in timepoints:
        for region in REGIONS:
            rid = region["id"]
            p = profiles[rid]
            key = "late_spring" if tp_key == "春末" else ("winter" if tp_key == "冬季" else "spring")
            prof = p[key]
            rows.append({
                "region_id": rid,
                "station": p["station"],
                "observed_at": tp_date,
                "temperature_c": prof["temp"],
                "precipitation_mm_24h": prof["precip"],
                "wind_speed_mps": prof["wind"],
                "snow_depth_cm": prof["snow"],
                "cold_wave_risk": prof["cold"],
                "snowstorm_risk": prof["snowstorm"],
                "drought_risk": prof["drought"],
            })

    return rows


def build_remote_csv() -> list[dict]:
    """生成遥感生态样例数据。"""
    rows = []
    timepoints = [
        ("2026-01-15", "冬季"),
        ("2026-03-20", "春季"),
        ("2026-05-20", "春末"),
        ("2025-07-15", "夏季（去年丰草期参考）"),
    ]

    profiles = {
        "naqu-bange": {
            "grassland_type": "高寒草甸",
            "degradation_level": "中度退化",
            "seasons": {
                "冬季": {"ndvi": 0.18, "ndvi_change": "-12.5%", "veg": "18%", "snow": "68%", "cap": 9800},
                "春季": {"ndvi": 0.24, "ndvi_change": "-9.8%", "veg": "28%", "snow": "52%", "cap": 12400},
                "春末": {"ndvi": 0.34, "ndvi_change": "-8.6%", "veg": "42%", "snow": "31%", "cap": 18200},
                "夏季（去年丰草期参考）": {"ndvi": 0.52, "ndvi_change": "-4.2%", "veg": "68%", "snow": "2%", "cap": 32100},
            },
        },
        "changdu-luolong": {
            "grassland_type": "山地草甸",
            "degradation_level": "轻度退化",
            "seasons": {
                "冬季": {"ndvi": 0.25, "ndvi_change": "-7.1%", "veg": "30%", "snow": "42%", "cap": 15600},
                "春季": {"ndvi": 0.35, "ndvi_change": "-4.5%", "veg": "42%", "snow": "28%", "cap": 19200},
                "春末": {"ndvi": 0.47, "ndvi_change": "-3.2%", "veg": "55%", "snow": "18%", "cap": 23600},
                "夏季（去年丰草期参考）": {"ndvi": 0.61, "ndvi_change": "+1.8%", "veg": "72%", "snow": "0%", "cap": 35800},
            },
        },
        "rikaze-xietongmen": {
            "grassland_type": "河谷草地",
            "degradation_level": "基本稳定",
            "seasons": {
                "冬季": {"ndvi": 0.31, "ndvi_change": "-2.1%", "veg": "38%", "snow": "24%", "cap": 17200},
                "春季": {"ndvi": 0.41, "ndvi_change": "-0.5%", "veg": "48%", "snow": "15%", "cap": 18500},
                "春末": {"ndvi": 0.52, "ndvi_change": "+1.4%", "veg": "61%", "snow": "11%", "cap": 19800},
                "夏季（去年丰草期参考）": {"ndvi": 0.68, "ndvi_change": "+3.2%", "veg": "78%", "snow": "0%", "cap": 29600},
            },
        },
    }

    for tp_date, tp_key in timepoints:
        for region in REGIONS:
            rid = region["id"]
            p = profiles[rid]
            s = p["seasons"][tp_key]
            rows.append({
                "region_id": rid,
                "scene_date": tp_date,
                "ndvi": s["ndvi"],
                "ndvi_change": s["ndvi_change"],
                "vegetation_cover": s["veg"],
                "snow_cover": s["snow"],
                "grassland_type": p["grassland_type"],
                "degradation_level": p["degradation_level"],
                "carrying_capacity_sheep_unit": s["cap"],
            })

    return rows


def build_subjects_csv() -> list[dict]:
    """生成经营主体样例数据。"""
    return [
        {"name": "扎西高原牧业合作社", "region_id": "naqu-bange", "region_name": "那曲市班戈县", "subject_type": "合作社", "cattle_count": 1260, "sheep_count": 3200, "grassland_mu": 85000, "credit_amount": "280 万元", "credit_value": 280, "score": 83, "insurance_coverage": "82%", "status": "正常监控", "loan_use": "冬季补饲和牦牛防疫"},
        {"name": "格桑牧场联合体", "region_id": "naqu-bange", "region_name": "那曲市班戈县", "subject_type": "联合体", "cattle_count": 780, "sheep_count": 1800, "grassland_mu": 52000, "credit_amount": "150 万元", "credit_value": 150, "score": 74, "insurance_coverage": "68%", "status": "正常监控", "loan_use": "饲草采购和棚圈修缮"},
        {"name": "央金家庭牧场", "region_id": "naqu-bange", "region_name": "那曲市班戈县", "subject_type": "家庭牧场", "cattle_count": 380, "sheep_count": 600, "grassland_mu": 18000, "credit_amount": "65 万元", "credit_value": 65, "score": 68, "insurance_coverage": "58%", "status": "需补保险", "loan_use": "补饲和防疫服务"},
        {"name": "德吉牦牛养殖联合体", "region_id": "changdu-luolong", "region_name": "昌都市洛隆县", "subject_type": "联合体", "cattle_count": 910, "sheep_count": 1500, "grassland_mu": 62000, "credit_amount": "180 万元", "credit_value": 180, "score": 76, "insurance_coverage": "71%", "status": "关注回款", "loan_use": "活体交易和冷链物流"},
        {"name": "洛隆牧工商公司", "region_id": "changdu-luolong", "region_name": "昌都市洛隆县", "subject_type": "企业", "cattle_count": 2100, "sheep_count": 4500, "grassland_mu": 120000, "credit_amount": "450 万元", "credit_value": 450, "score": 86, "insurance_coverage": "85%", "status": "正常监控", "loan_use": "屠宰加工和品牌销售"},
        {"name": "次仁养殖合作社", "region_id": "changdu-luolong", "region_name": "昌都市洛隆县", "subject_type": "合作社", "cattle_count": 560, "sheep_count": 900, "grassland_mu": 34000, "credit_amount": "95 万元", "credit_value": 95, "score": 71, "insurance_coverage": "65%", "status": "正常监控", "loan_use": "牦牛育肥和饲草种植"},
        {"name": "仁青冷链供草中心", "region_id": "rikaze-xietongmen", "region_name": "日喀则市谢通门县", "subject_type": "供应商", "cattle_count": 0, "sheep_count": 0, "grassland_mu": 0, "credit_amount": "120 万元", "credit_value": 120, "score": 79, "insurance_coverage": "75%", "status": "正常监控", "loan_use": "饲草采购和仓储运输"},
        {"name": "白马草业公司", "region_id": "rikaze-xietongmen", "region_name": "日喀则市谢通门县", "subject_type": "企业", "cattle_count": 320, "sheep_count": 800, "grassland_mu": 28000, "credit_amount": "200 万元", "credit_value": 200, "score": 82, "insurance_coverage": "80%", "status": "正常监控", "loan_use": "饲草加工和订单农业"},
    ]


def build_finance_csv() -> list[dict]:
    """生成金融保险样例数据。"""
    return [
        {"subject_name": "扎西高原牧业合作社", "credit_line": 350, "used_credit": 280, "interest_rate": "4.35%", "term_months": 36, "repayment_status": "正常", "overdue_times": 0},
        {"subject_name": "格桑牧场联合体", "credit_line": 200, "used_credit": 150, "interest_rate": "4.50%", "term_months": 24, "repayment_status": "正常", "overdue_times": 0},
        {"subject_name": "央金家庭牧场", "credit_line": 80, "used_credit": 65, "interest_rate": "4.60%", "term_months": 12, "repayment_status": "正常", "overdue_times": 0},
        {"subject_name": "德吉牦牛养殖联合体", "credit_line": 250, "used_credit": 180, "interest_rate": "4.50%", "term_months": 24, "repayment_status": "关注", "overdue_times": 1},
        {"subject_name": "洛隆牧工商公司", "credit_line": 500, "used_credit": 450, "interest_rate": "4.20%", "term_months": 36, "repayment_status": "正常", "overdue_times": 0},
        {"subject_name": "次仁养殖合作社", "credit_line": 120, "used_credit": 95, "interest_rate": "4.50%", "term_months": 18, "repayment_status": "正常", "overdue_times": 0},
        {"subject_name": "仁青冷链供草中心", "credit_line": 150, "used_credit": 120, "interest_rate": "4.35%", "term_months": 18, "repayment_status": "正常", "overdue_times": 0},
        {"subject_name": "白马草业公司", "credit_line": 250, "used_credit": 200, "interest_rate": "4.35%", "term_months": 24, "repayment_status": "正常", "overdue_times": 0},
    ]


# ============================================================================
# CSV 写入
# ============================================================================

BUILDERS = {
    "weather_data_public_sample.csv": (build_weather_csv, [
        "region_id", "station", "observed_at", "temperature_c", "precipitation_mm_24h",
        "wind_speed_mps", "snow_depth_cm", "cold_wave_risk", "snowstorm_risk", "drought_risk",
    ]),
    "remote_sensing_public_sample.csv": (build_remote_csv, [
        "region_id", "scene_date", "ndvi", "ndvi_change", "vegetation_cover",
        "snow_cover", "grassland_type", "degradation_level", "carrying_capacity_sheep_unit",
    ]),
    "business_subjects_demo.csv": (build_subjects_csv, [
        "name", "region_id", "region_name", "subject_type", "cattle_count", "sheep_count",
        "grassland_mu", "credit_amount", "credit_value", "score",
        "insurance_coverage", "status", "loan_use",
    ]),
    "finance_credit_demo.csv": (build_finance_csv, [
        "subject_name", "credit_line", "used_credit", "interest_rate",
        "term_months", "repayment_status", "overdue_times",
    ]),
}


def write_csv(filename: str, rows: list[dict], columns: list[str]) -> Path:
    """写入 CSV 文件。"""
    path = SAMPLES_DIR / filename
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def main() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    # 验证 sources.json 存在
    sources_file = ROOT.parent / "sources.json"
    if sources_file.exists():
        with open(sources_file, "r", encoding="utf-8") as f:
            sources = json.load(f)
        print(f"[build] 已加载数据源定义: {len(sources.get('sources', []))} 个数据源")

    total = 0
    for filename, (builder, columns) in BUILDERS.items():
        rows = builder()
        path = write_csv(filename, rows, columns)
        print(f"[build] {path.name}: {len(rows)} 行 → {path}")
        total += len(rows)

    print(f"[build] 全部完成: {len(BUILDERS)} 个文件, 共 {total} 行数据")
    print("[build] 下一步: 打开 http://127.0.0.1:8000/admin 上传 CSV")


if __name__ == "__main__":
    main()
