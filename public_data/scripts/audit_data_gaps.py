"""一次性审计所有数据文件的缺口."""
import json
from collections import defaultdict, Counter
from pathlib import Path

DATA = Path(r"c:\Users\WH\Desktop\gonghangbei - 副本\backend\data_store")

print("=" * 70)
print("数据缺口审计报告")
print("=" * 70)

# ---------- 1. weather_data.json ----------
print("\n[1] weather_data.json — 气象数据")
with open(DATA / "weather_data.json", encoding="utf-8") as f:
    weather = json.load(f)
print(f"  总记录: {len(weather)}")
by_region = defaultdict(list)
for r in weather:
    by_region[r["region_id"]].append(r)
print(f"  区域数: {len(by_region)}")
snow_zero = sum(1 for r in weather if r.get("snow_depth_cm", 0) == 0)
print(f"  积雪深度为0: {snow_zero}/{len(weather)} ({snow_zero*100//len(weather)}%)")
# 时间范围
all_years = set()
for r in weather:
    all_years.add(r["observed_at"][:4])
print(f"  年份范围: {min(all_years)} ~ {max(all_years)}")
# 林芝
linzhi = [r for r in weather if "linzhi" in r["region_id"] or "bayi" in r["region_id"]]
print(f"  林芝相关记录: {len(linzhi)}")
# 每区域月份统计
counts = {rid: len(rs) for rid, rs in by_region.items()}
print(f"  每区域月份: min={min(counts.values())}, max={max(counts.values())}, 中位数={sorted(counts.values())[len(counts)//2]}")

# ---------- 2. remote_sensing_data.json ----------
print("\n[2] remote_sensing_data.json — 遥感数据")
with open(DATA / "remote_sensing_data.json", encoding="utf-8") as f:
    rs = json.load(f)
print(f"  总记录: {len(rs)}")
fields = ["ndvi", "ndvi_change_pct", "vegetation_cover_pct", "snow_cover_pct",
          "degradation_level", "carrying_capacity"]
for fld in fields:
    if fld == "degradation_level":
        missing = sum(1 for r in rs if r.get(fld) in (None, "", "未知"))
    else:
        missing = sum(1 for r in rs if r.get(fld) in (None, "", 0))
    print(f"    {fld}: {missing}/{len(rs)} ({missing*100//len(rs)}%) 缺失/0值")

# ---------- 3. climate_era5.json ----------
print("\n[3] climate_era5.json — ERA5逐日气候")
with open(DATA / "climate_era5.json", encoding="utf-8") as f:
    era5 = json.load(f)
print(f"  区域数: {len(era5)} (注：项目目标26县)")
total_days = sum(len(v) for v in era5.values())
print(f"  总天数: {total_days}")
sample_rid = list(era5.keys())[0]
sample_dates = sorted(era5[sample_rid], key=lambda x: x.get("date", ""))
if sample_dates:
    print(f"  样例 {sample_rid}: {sample_dates[0].get('date')} ~ {sample_dates[-1].get('date')} ({len(sample_dates)}天)")

# ---------- 4. climate_era5_regional.json ----------
print("\n[4] climate_era5_regional.json — CMFD区域气候")
with open(DATA / "climate_era5_regional.json", encoding="utf-8") as f:
    era5_reg = json.load(f)
print(f"  区域数: {len(era5_reg)}")
total_m = sum(len(v) for v in era5_reg.values())
print(f"  总月数: {total_m}")
sample_rid = list(era5_reg.keys())[0]
sample_dates = sorted(era5_reg[sample_rid], key=lambda x: x.get("date", ""))
if sample_dates:
    print(f"  样例 {sample_rid}: {sample_dates[0].get('date')} ~ {sample_dates[-1].get('date')} ({len(sample_dates)}月)")
    no_prec = sum(1 for d in era5_reg[sample_rid] if d.get("precip_mm", 0) == 0)
    print(f"    降水=0的月数: {no_prec}/{len(sample_dates)}")

# ---------- 5. npp_by_region.json ----------
print("\n[5] npp_by_region.json — NPP数据")
with open(DATA / "npp_by_region.json", encoding="utf-8") as f:
    npp = json.load(f)
print(f"  区域数: {len(npp)}")
all_years = set()
for r in npp:
    all_years.update(r.get("npp_annual", {}).keys())
print(f"  年份范围: {min(all_years)} ~ {max(all_years)} ({len(all_years)}年)")
# 检查每个区域是否都有数据
npp_years_count = [len(r.get("npp_annual", {})) for r in npp]
print(f"  每区域年数: min={min(npp_years_count)}, max={max(npp_years_count)}")

# ---------- 6. phenology_by_region.json ----------
print("\n[6] phenology_by_region.json — 物候数据")
with open(DATA / "phenology_by_region.json", encoding="utf-8") as f:
    phen = json.load(f)
print(f"  区域数: {len(phen)} (注：项目目标26县)")
all_years = set()
for r in phen:
    all_years.update(r.get("years", []))
print(f"  年份范围: {min(all_years)} ~ {max(all_years)} ({len(all_years)}年)")

# ---------- 7. real_labels_1500.json ----------
print("\n[7] real_labels_1500.json — 真实标签")
with open(DATA / "real_labels_1500.json", encoding="utf-8") as f:
    labels = json.load(f)
print(f"  总样本: {len(labels)}")
pos = sum(1 for r in labels if r.get("label") == 1 or r.get("risk_label") == 1)
neg = sum(1 for r in labels if r.get("label") == 0 or r.get("risk_label") == 0)
print(f"  正样本: {pos}, 负样本: {neg} (不平衡比 1:{neg//max(pos,1)})")

# ---------- 8. risk_event_labels.json ----------
print("\n[8] risk_event_labels.json — 灾害事件标签")
with open(DATA / "risk_event_labels.json", encoding="utf-8") as f:
    events = json.load(f)
print(f"  事件总数: {len(events)}")
by_type = Counter(e.get("event_type", "unknown") for e in events)
print(f"  按类型: {dict(by_type)}")
real_count = sum(1 for e in events if e.get("is_real_label"))
print(f"  真实事件: {real_count}, demo: {len(events)-real_count}")

# ---------- 9. business_subjects.json ----------
print("\n[9] business_subjects.json — 经营主体")
with open(DATA / "business_subjects.json", encoding="utf-8") as f:
    bs = json.load(f)
print(f"  主体数: {len(bs)}")
linzhi_count = sum(1 for r in bs if "林芝" in r.get("region_name", "") or "linzhi" in r.get("region_id", "") or "bayi" in r.get("region_id", ""))
print(f"  林芝主体数: {linzhi_count}")

# ---------- 10. insurance_policies.json ----------
print("\n[10] insurance_policies.json — 保单数据")
with open(DATA / "insurance_policies.json", encoding="utf-8") as f:
    pol = json.load(f)
print(f"  保单数: {len(pol)}")

# ---------- 11. finance_credit.json ----------
print("\n[11] finance_credit.json — 金融保险")
with open(DATA / "finance_credit.json", encoding="utf-8") as f:
    fc = json.load(f)
print(f"  记录数: {len(fc)}")
has_repay = sum(1 for r in fc if r.get("repayment_status") or r.get("repay_status"))
print(f"  有还款状态: {has_repay}")
has_overdue = sum(1 for r in fc if r.get("overdue_count", 0) > 0)
print(f"  有逾期记录: {has_overdue}")

# ---------- 12. 缺失区域检查 ----------
print("\n[12] 跨文件区域一致性")
# 26县清单
import csv
region_ids = set()
with open(r"c:\Users\WH\Desktop\gonghangbei - 副本\public_data\region_list.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        region_ids.add(r["region_id"].strip())
print(f"  目标 26县: {len(region_ids)}")
# 各数据文件覆盖区域
weather_rids = set(by_region.keys())
era5_rids = set(era5.keys())
era5_reg_rids = set(era5_reg.keys())
npp_rids = set(r["region_id"] for r in npp)
phen_rids = set(r["region_id"] for r in phen)
print(f"  weather_data 缺失: {region_ids - weather_rids}")
print(f"  climate_era5 缺失: {region_ids - era5_rids}")
print(f"  climate_era5_regional 缺失: {region_ids - era5_reg_rids}")
print(f"  npp 缺失: {region_ids - npp_rids}")
print(f"  phenology 缺失: {region_ids - phen_rids}")

print("\n" + "=" * 70)
print("审计完成")
