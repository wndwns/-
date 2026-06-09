"""
MCD12Q2 物候数据提取 — 返青期 / 枯黄期 / 生长季长度
================================================================
输入：MCD12Q2.061 TIF 文件（2003-2024），位于 TIF_DIR 目录
输出：data_store/phenology_by_region.json

MCD12Q2 v6.1 数据格式说明：
  - 编码："自 1970-01-01 起的天数"（Metadata 声称 2000 但实际是 1970）
  - 填充值：32767
  - 波段 0：主要生长周期 (cycle 0)，西藏高原只需用 cycle 0
  - Greenup: EVI 首次超过 15% 振幅的日期
  - Dormancy: EVI 最后一次超过 15% 振幅的日期
  - 生长季长度 = Dormancy - Greenup
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import rowcol

# ── 配置 ──
ROOT = Path(__file__).resolve().parent
TIF_DIR = Path(r"C:\Users\WH\Desktop\123")
CSV_PATH = ROOT.parent / "public_data" / "region_list.csv"
OUT_PATH = ROOT / "data_store" / "phenology_by_region.json"
WINDOW = 30  # 30×30 像素窗口
FILL_VALUE = 32767
EPOCH = datetime(1970, 1, 1)
START_YEAR = 2003
END_YEAR = 2024


def days_to_date(days: float) -> datetime:
    """自 1970-01-01 的天数 → datetime。"""
    return EPOCH + timedelta(days=float(days))


def days_to_doy(days: float) -> int:
    """自 1970-01-01 的天数 → 当年第几天 (1-366)。"""
    dt = days_to_date(days)
    return dt.timetuple().tm_yday


def extract_cycle0_mean(data: np.ndarray, r: int, c: int) -> float | None:
    """提取以 (r, c) 为中心 WINDOW×WINDOW 窗口的有效像素均值。"""
    sub = data[max(0, r - WINDOW):r + WINDOW, max(0, c - WINDOW):c + WINDOW]
    valid = sub[(sub != FILL_VALUE) & (sub > 0)]
    if len(valid) == 0:
        return None
    return float(np.mean(valid))


def extract_all() -> list[dict]:
    """对所有 25 个县提取 2003-2024 物候时间序列。"""
    # 读取县列表
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        counties = list(csv.DictReader(f))

    results = []

    for row in counties:
        rid = row["region_id"]
        lon = float(row["longitude"])
        lat = float(row["latitude"])
        name = row["region_name"]
        print(f"\n{'='*60}")
        print(f"  提取 {rid} ({name}) @ lon={lon}, lat={lat}")

        # 先用一个 TIF 确定像素坐标（所有文件相同投影和分辨率）
        sample_file = TIF_DIR / "MCD12Q2.061_Greenup_0_doy2024001000000_aid0001.tif"
        with rasterio.open(str(sample_file)) as src:
            r, c = rowcol(src.transform, lon, lat)
        print(f"  像素坐标: row={r}, col={c}")

        # 逐 year / layer 读取
        pheno = {"greenup": {}, "dormancy": {}, "growing_season": {}}
        total_pixels = 0
        year_count = 0

        for year in range(START_YEAR, END_YEAR + 1):
            greenup_file = TIF_DIR / f"MCD12Q2.061_Greenup_0_doy{year}001000000_aid0001.tif"
            dormancy_file = TIF_DIR / f"MCD12Q2.061_Dormancy_0_doy{year}001000000_aid0001.tif"

            if not greenup_file.exists() or not dormancy_file.exists():
                print(f"    {year}: 文件缺失，跳过")
                continue

            with rasterio.open(str(greenup_file)) as gsrc:
                g_data = gsrc.read(1)
                greenup_val = extract_cycle0_mean(g_data, r, c)

            with rasterio.open(str(dormancy_file)) as dsrc:
                d_data = dsrc.read(1)
                dormancy_val = extract_cycle0_mean(d_data, r, c)

            if greenup_val is None or dormancy_val is None:
                print(f"    {year}: 无有效像素，跳过")
                continue

            greenup_doy = days_to_doy(greenup_val)
            dormancy_doy = days_to_doy(dormancy_val)
            gs_length = dormancy_val - greenup_val  # 天数差

            pheno["greenup"][str(year)] = {
                "days_since_epoch": round(greenup_val, 1),
                "doy": greenup_doy,
            }
            pheno["dormancy"][str(year)] = {
                "days_since_epoch": round(dormancy_val, 1),
                "doy": dormancy_doy,
            }
            pheno["growing_season"][str(year)] = round(gs_length, 1)

            total_pixels += 1
            year_count += 1
            print(f"    {year}: 返青 DOY={greenup_doy}, 枯黄 DOY={dormancy_doy}, 生长季={gs_length:.0f}天")

        if year_count == 0:
            print(f"  ⚠️ 无有效数据！")
            continue

        # 统计
        gs_years = sorted(int(y) for y in pheno["growing_season"].keys())
        gs_values = [pheno["growing_season"][str(y)] for y in gs_years]
        greenup_doys = [pheno["greenup"][str(y)]["doy"] for y in gs_years]
        dormancy_doys = [pheno["dormancy"][str(y)]["doy"] for y in gs_years]

        # 趋势分析：线性回归斜率
        if len(gs_values) >= 5:
            x = np.array(gs_years)
            y_gs = np.array(gs_values)
            slope_gs = np.polyfit(x, y_gs, 1)[0]

            y_gu = np.array(greenup_doys)
            slope_gu = np.polyfit(x, y_gu, 1)[0]

            y_do = np.array(dormancy_doys)
            slope_do = np.polyfit(x, y_do, 1)[0]
        else:
            slope_gs = slope_gu = slope_do = None

        entry = {
            "region_id": rid,
            "region_name": name,
            "longitude": lon,
            "latitude": lat,
            "pixel_row": int(r),
            "pixel_col": int(c),
            "window_size": WINDOW * 2,
            "years": gs_years,
            "data": pheno,
            "statistics": {
                "greenup_mean_doy": round(float(np.mean(greenup_doys)), 1),
                "greenup_min_doy": int(np.min(greenup_doys)),
                "greenup_max_doy": int(np.max(greenup_doys)),
                "dormancy_mean_doy": round(float(np.mean(dormancy_doys)), 1),
                "dormancy_min_doy": int(np.min(dormancy_doys)),
                "dormancy_max_doy": int(np.max(dormancy_doys)),
                "growing_season_mean_days": round(float(np.mean(gs_values)), 1),
                "growing_season_min_days": round(float(np.min(gs_values)), 1),
                "growing_season_max_days": round(float(np.max(gs_values)), 1),
                "growing_season_std_days": round(float(np.std(gs_values)), 1),
                "greenup_trend_days_per_year": round(slope_gu, 3) if slope_gu else None,
                "dormancy_trend_days_per_year": round(slope_do, 3) if slope_do else None,
                "growing_season_trend_days_per_year": round(slope_gs, 3) if slope_gs else None,
            },
            "interpretation": _interpret(slope_gs, slope_gu, slope_do),
        }
        results.append(entry)

        # 打印摘要
        s = entry["statistics"]
        i = entry["interpretation"]
        print(f"\n  摘要:")
        print(f"    返青期: 均值 DOY={s['greenup_mean_doy']}, 趋势={s['greenup_trend_days_per_year']}天/年 ({i['greenup']})")
        print(f"    枯黄期: 均值 DOY={s['dormancy_mean_doy']}, 趋势={s['dormancy_trend_days_per_year']}天/年 ({i['dormancy']})")
        print(f"    生长季: 均值={s['growing_season_mean_days']}天, 趋势={s['growing_season_trend_days_per_year']}天/年 ({i['growing_season']})")

    return results


def _interpret(slope_gs: float | None, slope_gu: float | None, slope_do: float | None) -> dict:
    """将趋势斜率翻译为人类可读的解读。"""
    def _label(slope, pos_word="延长", neg_word="缩短", neu_word="稳定"):
        if slope is None:
            return "数据不足"
        if slope > 0.3:
            return f"逐年{pos_word} (趋势明显)"
        if slope > 0.1:
            return f"略{pos_word}"
        if slope < -0.3:
            return f"逐年{neg_word} (趋势明显)"
        if slope < -0.1:
            return f"略{neg_word}"
        return f"基本{neu_word}"

    return {
        "greenup": _label(slope_gu, pos_word="推迟", neg_word="提前"),
        "dormancy": _label(slope_do, pos_word="推迟", neg_word="提前"),
        "growing_season": _label(slope_gs, pos_word="延长", neg_word="缩短"),
    }


def main():
    print("=" * 60)
    print("  MCD12Q2 物候数据提取 — 返青期/枯黄期/生长季长度")
    print("=" * 60)

    results = extract_all()

    # 保存
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"  已保存 {len(results)} 个县的物候数据到 {OUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()