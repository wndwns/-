"""
将林芝地区数据导入 gonghangbei 的 store JSON 文件
"""
import json, sys, os

sys.path.insert(0, r'C:\Users\WH\Desktop\gonghangbei - 副本\backend')
DATA_DIR = r'C:\Users\WH\Desktop\gonghangbei - 副本\backend\data_store'

# 新数据
linzhi_weather = {
    "region_id": "linzhi-bayi", "region_name": "林芝市巴宜区",
    "station": "林芝市国家基准气候站", "observed_at": "2026-05-21 08:00",
    "temperature_c": 9.5, "precipitation_mm_24h": 3.2, "wind_speed_mps": 2.8,
    "snow_depth_cm": 3, "cold_wave_risk": "低", "snowstorm_risk": "低",
    "drought_risk": "低", "data_source": "real_insurance", "is_sample": False,
}

linzhi_remote = {
    "region_id": "linzhi-bayi", "region_name": "林芝市巴宜区",
    "scene_date": "2026-05-20", "ndvi": 0.62, "ndvi_change": "+2.1%",
    "vegetation_cover": "72%", "snow_cover": "8%",
    "grassland_type": "山地灌丛草甸", "degradation_level": "基本稳定",
    "carrying_capacity_sheep_unit": 28500, "data_source": "real_insurance",
    "is_sample": False, "capacity_is_sample": True, "capacity_derived": True,
    "capacity_data_source": "derived_from_ndvi", "imported_at": "2026-06-08",
}

linzhi_subject = {
    "name": "百巴村牦牛养殖合作社", "region_id": "linzhi-bayi",
    "region_name": "林芝市巴宜区", "subject_type": "行政村集体",
    "cattle_count": 1135, "sheep_count": 0, "grassland_mu": 120000,
    "credit_amount": "500 万元", "credit_value": 500, "score": 91,
    "insurance_coverage": "88%", "status": "正常监控",
    "loan_use": "牦牛养殖扩产", "data_source": "real_insurance",
}

linzhi_finance = {
    "subject_name": "百巴村牦牛养殖合作社", "credit_line": 600,
    "used_credit": 500, "interest_rate": "3.85%", "term_months": 36,
    "repayment_status": "正常", "overdue_times": 0,
    "data_source": "real_insurance",
    "policies": [
        {"type": "养殖险牛", "insured_qty": 1135, "coverage": "88%"},
        {"type": "草场保险", "insured_qty": 120000, "coverage": "100%"},
    ],
}

# 读取store看weather数据源
# weather好像存在不同的表里，先看看store.py怎么读的
from store import read_table, write_table

# 尝试读取weather_data
try:
    existing = read_table("weather_data")
    print(f"weather_data: {len(existing)} 条")
    # 检查是否已有linzhi
    has = any(r.get('region_id') == 'linzhi-bayi' for r in existing)
    print(f"  已有linzhi: {has}")
except Exception as e:
    print(f"weather_data 读取失败: {e}")

# weather数据可能在climate_era5.json
try:
    existing = read_table("climate_era5")
    print(f"climate_era5: {len(existing) if existing else 0} 条")
except Exception as e:
    print(f"climate_era5 读取失败: {e}")
