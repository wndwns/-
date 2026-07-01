"""
为推导数据加显眼标注
================================================================
- phenology_by_region.json 林芝记录: 加 is_derived + derivation_note
- remote_sensing_data.json 林芝 92 条: 加 is_derived + derivation_note
- weather_data.json 林芝 2019-2024 72 条: 加 source 标注（真实ERA5但需注明）
"""
import json
from pathlib import Path

ROOT = Path(r"c:\Users\WH\Desktop\gonghangbei - 副本")
DATA = ROOT / "backend" / "data_store"

WARNING_PHENOLOGY = "⚠️ 此处数据为预测/推导：基于 Open-Meteo ERA5 日均温用温度阈值法(>=5°C连续5天为greenup, <0°C连续5天为dormancy)推导，非 MODIS MCD12Q2 真实物候观测。请勿用于物候精度分析。"
WARNING_REMOTE_SENSING = "⚠️ 此处数据为预测/推导：NDVI/vegetation_cover/snow_cover/carrying_capacity 基于山地草甸4县(昌都4县)月均模式+林芝温度修正推导，非 MODIS 真实遥感观测。请勿用于遥感精度分析。"

def mark_phenology():
    """标注 phenology 林芝记录"""
    path = DATA / "phenology_by_region.json"
    with open(path, encoding="utf-8") as f:
        phen = json.load(f)

    count = 0
    for r in phen:
        if r.get("region_id") == "linzhi-bayi":
            r["is_derived"] = True
            r["derivation_method"] = "temperature_threshold_from_openmeteo_era5"
            r["derivation_note"] = WARNING_PHENOLOGY
            r["derivation_warning"] = "此处数据为预测/推导，非真实物候观测"
            r["note"] = WARNING_PHENOLOGY
            # 顶层也加
            r["⚠️ WARNING"] = "此处数据为预测/推导，非真实物候观测"
            count += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(phen, f, ensure_ascii=False, indent=2)
    print(f"[1] phenology_by_region.json: 标注 {count} 条林芝记录")

def mark_remote_sensing():
    """标注 remote_sensing_data 林芝 92 条"""
    path = DATA / "remote_sensing_data.json"
    with open(path, encoding="utf-8") as f:
        rs = json.load(f)

    count = 0
    for r in rs:
        if r.get("region_id") == "linzhi-bayi":
            r["is_derived"] = True
            r["derivation_method"] = "shandi_caodian_4ref_regions_temp_adjusted"
            r["derivation_note"] = WARNING_REMOTE_SENSING
            r["derivation_warning"] = "此处数据为预测/推导，非真实遥感观测"
            r["⚠️ WARNING"] = "此处数据为预测/推导，非真实遥感观测"
            count += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(rs, f, ensure_ascii=False, indent=2)
    print(f"[2] remote_sensing_data.json: 标注 {count} 条林芝记录")

def mark_weather_linzhi_2019_2024():
    """weather_data 林芝 2019-2024 72 条标注数据源（ERA5 真实数据，但加 source 说明）"""
    path = DATA / "weather_data.json"
    with open(path, encoding="utf-8") as f:
        weather = json.load(f)

    count = 0
    for r in weather:
        if (r.get("region_id") == "linzhi-bayi"
            and r.get("source_id") == "openmeteo-archive-linzhi"):
            # ERA5 真实数据，但标注来源
            r["data_provenance"] = "Open-Meteo ERA5 再分析数据（真实科学数据，非推导）"
            count += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(weather, f, ensure_ascii=False, indent=2)
    print(f"[3] weather_data.json: 标注 {count} 条林芝 ERA5 记录（真实数据，注明来源）")

def mark_snow_depth():
    """snow_depth_openmeteo.json 和 weather_data 中的雪深字段标注数据源"""
    path = DATA / "snow_depth_openmeteo.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            snow = json.load(f)
        # 加顶层说明
        if isinstance(snow, dict):
            snow["_⚠️_DATA_PROVENANCE"] = "Open-Meteo ERA5 再分析雪深数据（真实科学数据，非推导）。snow_depth_max 来自 ERA5 Land reanalysis。"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snow, f, ensure_ascii=False, indent=2)
        print(f"[4] snow_depth_openmeteo.json: 加数据来源标注")

def main():
    print("=" * 70)
    print("为推导数据加显眼标注")
    print("=" * 70)
    mark_phenology()
    mark_remote_sensing()
    mark_weather_linzhi_2019_2024()
    mark_snow_depth()
    print("\n完成。所有推导数据已标注 is_derived=true 和 derivation_note")

if __name__ == "__main__":
    main()
