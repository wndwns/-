"""
保单数据导入脚本
============================================================================
读取 C:\\Users\\WH\\Desktop\\保单模板.xlsx → 生成 insurance_policies.json

数据结构：
  原始: 1135条保单（每头牦牛一条）
  导出: 农户级聚合（21户） + 完整保单明细
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl


def main():
    xlsx_path = Path(r"C:\Users\WH\Desktop\保单模板.xlsx")
    if not xlsx_path.exists():
        # 尝试项目内副本
        xlsx_path = Path(__file__).resolve().parents[2] / "保单模板.xlsx"
    if not xlsx_path.exists():
        print(f"[ERROR] 找不到保单文件: {xlsx_path}")
        return

    print(f"[INFO] 读取: {xlsx_path}")
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb["Sheet1"]

    # ---- 读取原始保单 ----
    headers = [c.value for c in ws[1]]
    print(f"[INFO] 表头: {headers}")

    policies = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[0]:
            continue
        policies.append({
            "ear_tag": str(row[0]).strip(),
            "livestock_type": str(row[1] or "").strip(),
            "farm_location": str(row[2] or "").strip(),
            "farmer_name": str(row[3] or "").strip(),
            "id_number": str(row[4] or "").strip(),
            "address": str(row[5] or "").strip() if row[5] else "",
            "phone": str(row[6] or "").strip() if row[6] else "",
            "bank_card": str(row[7] or "").strip() if row[7] else "",
            "bank_name": str(row[8] or "").strip(),
        })

    print(f"[INFO] 原始保单数: {len(policies)}")

    # ---- 按证件号聚合农户 ----
    farmers_map = defaultdict(lambda: {
        "farmer_name": "",
        "id_number": "",
        "farm_location": "",
        "address": "",
        "phone": "",
        "bank_name": "",
        "policies": [],
        "ear_tags": [],
        "ear_tag_prefixes": set(),
    })

    for p in policies:
        key = p["id_number"]
        f = farmers_map[key]
        f["farmer_name"] = p["farmer_name"]
        f["id_number"] = p["id_number"]
        f["farm_location"] = p["farm_location"]
        if p["address"] and not f["address"]:
            f["address"] = p["address"]
        if p["phone"] and not f["phone"]:
            f["phone"] = p["phone"]
        f["bank_name"] = p["bank_name"]
        f["policies"].append(p)
        f["ear_tags"].append(p["ear_tag"])
        # 耳标前缀（前3位，可能对应投保批次）
        prefix = p["ear_tag"][:3] if len(p["ear_tag"]) >= 3 else ""
        if prefix:
            f["ear_tag_prefixes"].add(prefix)

    # ---- 生成农户列表 ----
    farmers = []
    for i, (id_num, f) in enumerate(farmers_map.items(), 1):
        farmer_id = f"farmer_{i:03d}"
        herd_size = len(f["policies"])
        farmers.append({
            "farmer_id": farmer_id,
            "farmer_name": f["farmer_name"],
            "id_number_masked": f["id_number"],  # 已脱敏
            "farm_location": f["farm_location"],
            "address": f["address"],
            "phone_masked": f["phone"],
            "bank_name": f["bank_name"],
            "herd_size": herd_size,
            "ear_tag_count": len(f["ear_tags"]),
            "ear_tag_prefixes": sorted(f["ear_tag_prefixes"]),
            "ear_tag_batch_count": len(f["ear_tag_prefixes"]),
            "has_address": bool(f["address"]),
            "has_phone": bool(f["phone"]),
        })

    # 按规模降序
    farmers.sort(key=lambda x: x["herd_size"], reverse=True)

    # ---- 画像统计 ----
    herd_sizes = [f["herd_size"] for f in farmers]
    total_cattle = sum(herd_sizes)

    # 规模分布
    scale_dist = {
        "1-4头": sum(1 for s in herd_sizes if s <= 4),
        "5-9头": sum(1 for s in herd_sizes if 5 <= s <= 9),
        "10-49头": sum(1 for s in herd_sizes if 10 <= s <= 49),
        "50-99头": sum(1 for s in herd_sizes if 50 <= s <= 99),
        "100+头": sum(1 for s in herd_sizes if s >= 100),
    }

    # 耳标批次统计
    prefix_counter = Counter()
    for p in policies:
        prefix = p["ear_tag"][:3] if len(p["ear_tag"]) >= 3 else ""
        if prefix:
            prefix_counter[prefix] += 1

    profile = {
        "village": "百巴村",
        "location": "西藏自治区林芝市巴宜区百巴镇百巴村",
        "region_id": "linzhi-bayi",
        "total_policies": len(policies),
        "total_cattle": total_cattle,
        "farmer_count": len(farmers),
        "avg_herd_size": round(total_cattle / len(farmers), 1) if farmers else 0,
        "max_herd_size": max(herd_sizes) if herd_sizes else 0,
        "min_herd_size": min(herd_sizes) if herd_sizes else 0,
        "livestock_type": "藏系牦牛",
        "insurance_bank": "中国农业银行",
        "scale_distribution": scale_dist,
        "ear_tag_batches": dict(prefix_counter.most_common()),
        "address_completeness": round(
            sum(1 for f in farmers if f["has_address"]) / len(farmers) * 100, 1
        ) if farmers else 0,
        "phone_completeness": round(
            sum(1 for f in farmers if f["has_phone"]) / len(farmers) * 100, 1
        ) if farmers else 0,
    }

    # ---- 输出 ----
    output = {
        "profile": profile,
        "farmers": farmers,
        "policies": policies,
        "imported_at": str(Path(xlsx_path).stat().st_mtime),
        "source_file": str(xlsx_path),
    }

    out_path = Path(__file__).resolve().parents[2] / "backend" / "data_store" / "insurance_policies.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 导出: {out_path}")
    print(f"[OK] 农户数: {len(farmers)}, 保单数: {len(policies)}")
    print(f"[OK] 规模分布: {scale_dist}")


if __name__ == "__main__":
    main()
