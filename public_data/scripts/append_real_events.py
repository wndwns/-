"""
追加真实灾害事件到 risk_event_labels.json
================================================================
来源：应急管理部/青海民政厅/中国西藏新闻网/央广网/农民日报
新增 2020-2024 年的事件，去重后追加
"""
import json
from pathlib import Path
from datetime import datetime

PATH = Path(r"c:\Users\WH\Desktop\gonghangbei - 副本\backend\data_store\risk_event_labels.json")

# 新增事件清单（基于公开报道）
NEW_EVENTS = [
    # 1. 2019年2月 海西州雪灾（都兰/乌兰县）— 牲畜24140头只死亡
    {
        "region_id": "haibei-gangcha",  # 海西藏族自治州邻近，使用最近区域
        "event_month": "2019-02",
        "event_type": "snowstorm",
        "severity": "高",
        "loss_amount": 24140,
        "claim_amount": 0,
        "overdue_flag": False,
        "source": "青海民政厅/应急管理部",
        "source_url": "https://mzt.qinghai.gov.cn/xxgk/show-4938.html",
        "is_real_label": True,
        "note": "2019年2月海西州都兰县、乌兰县雪灾，6乡镇3665户受灾，24140头只牲畜死亡(牦牛315头/羊23825只)，直接经济损失1061万元",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat() + "+00:00",
    },
    # 2. 2021年12月-2022年1月 那曲尼玛县雪灾
    {
        "region_id": "naqu-shenzha",  # 尼玛县不在26县内，用同市那曲申扎县代表
        "event_month": "2022-01",
        "event_type": "snowstorm",
        "severity": "高",
        "loss_amount": 7496,
        "claim_amount": 0,
        "overdue_flag": False,
        "source": "尼玛县网信办/中国西藏新闻网",
        "source_url": "http://www.xznmx.gov.cn/tt/202201/t20220119_4039481.html",
        "is_real_label": True,
        "note": "2021年12月-2022年1月那曲尼玛县11乡镇持续降雪，最低气温-26°C，积雪最深10cm，受灾面积90%以上，7496头只牲畜死亡(牦牛146头/羊7350只)，死亡数同比增长183%",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat() + "+00:00",
    },
    # 3. 2023年1-2月 玉树州雪灾
    {
        "region_id": "yushu-chengduo",  # 称多县受影响
        "event_month": "2023-02",
        "event_type": "snowstorm",
        "severity": "高",
        "loss_amount": 13960,
        "claim_amount": 0,
        "overdue_flag": False,
        "source": "青海省畜牧业雪灾风险研究/应急管理部",
        "source_url": "https://m.book118.com/html/2025/1211/5243001000013032.shtm",
        "is_real_label": True,
        "note": "2023年1月中旬至2月11日玉树州1市5县雪灾，13960头只牲畜死亡",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat() + "+00:00",
    },
    # 4. 2023年3月 红原县大雪
    {
        "region_id": "aba-hongyuan",
        "event_month": "2023-03",
        "event_type": "snowstorm",
        "severity": "中",
        "loss_amount": 0,
        "claim_amount": 0,
        "overdue_flag": False,
        "source": "农民日报/全国畜牧总站",
        "source_url": "https://www.nahs.org.cn/xxcm/sccy/202401/t20240126_437311.htm",
        "is_real_label": True,
        "note": "2023年3月红原县大雪，积雪十几厘米，牦牛死亡(具体数字未公布)。春季大雪被牧民称为'压死骆驼的最后一根稻草'",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat() + "+00:00",
    },
    # 5. 2023年4月 青海南部雪灾（称多/曲麻莱/治多/果洛）
    {
        "region_id": "yushu-chengduo",
        "event_month": "2023-04",
        "event_type": "snowstorm",
        "severity": "中",
        "loss_amount": 0,
        "claim_amount": 0,
        "overdue_flag": False,
        "source": "青海省气象台",
        "source_url": "http://m.toutiao.com/group/7359054693156274729/",
        "is_real_label": True,
        "note": "2023年4月17-18日青南地区大到暴雪，称多/曲麻莱/治多/黄南南部/果洛中南部积雪1-7cm，牛羊采食困难",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat() + "+00:00",
    },
    # 6. 2023年11月 果洛州甘德县雪灾（牦牛被困）
    {
        "region_id": "guoluo-maqin",  # 玛沁县代表果洛州
        "event_month": "2023-11",
        "event_type": "snowstorm",
        "severity": "中",
        "loss_amount": 0,
        "claim_amount": 0,
        "overdue_flag": False,
        "source": "西海都市报/光明网",
        "source_url": "https://m.gmw.cn/2023-11/13/content_1303569268.htm",
        "is_real_label": True,
        "note": "2023年11月果洛州甘德县降雪，70余头牦牛被困黄河孤岛，消防紧急救援，间接反映积雪融化导致次生灾害",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat() + "+00:00",
    },
    # 7. 2024年4月 那曲色尼区罗玛镇牦牛疫病（理赔事件）
    {
        "region_id": "naqu-seni",  # 色尼区
        "event_month": "2024-04",
        "event_type": "disease",
        "severity": "中",
        "loss_amount": 138,
        "claim_amount": 690000,
        "overdue_flag": False,
        "source": "中国西藏新闻网",
        "source_url": "https://www.chinatibetnews.com/xw/xzyw/2026-07/01/content_6931056.html",
        "is_real_label": True,
        "note": "2024年4月那曲色尼区罗玛镇牦牛群感染病毒性肠胃炎，138头牦牛死亡，中国人寿财险赔付69万元到26户牧民，平均每户2.65万元",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat() + "+00:00",
    },
    # 8. 2024年9月 海北刚察县暴雨（羊群溺亡）
    {
        "region_id": "haibei-gangcha",
        "event_month": "2024-09",
        "event_type": "rainstorm",
        "severity": "中",
        "loss_amount": 656,
        "claim_amount": 0,
        "overdue_flag": False,
        "source": "央广网",
        "source_url": "http://www.cnr.cn/qhfw/cxfz/20240903/t20240903_526886053.shtml",
        "is_real_label": True,
        "note": "2024年9月青海海北州刚察县泉吉乡暴雨，695只羊被困草场，656只溺亡，39只存活，消防救援12小时",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat() + "+00:00",
    },
    # 9. 2024年 林芝雪崩
    {
        "region_id": "linzhi-bayi",
        "event_month": "2024-01",
        "event_type": "snowstorm",
        "severity": "高",
        "loss_amount": 0,
        "claim_amount": 0,
        "overdue_flag": False,
        "source": "应急管理部",
        "source_url": "https://www.gov.cn/lianbo/bumen/202501/content_6999765.htm",
        "is_real_label": True,
        "note": "2024年雪崩灾害造成新疆阿勒泰、西藏林芝等地10人死亡(具体月份未公布，归入2024-01)",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat() + "+00:00",
    },
    # 10. 2019年1月 玉树杂多雪灾（之前已收录，这里补充量级数据）
    # 注：如果已存在则跳过
]

def main():
    print("=" * 70)
    print("追加真实灾害事件到 risk_event_labels.json")
    print("=" * 70)

    # 读取现有
    with open(PATH, encoding="utf-8") as f:
        events = json.load(f)
    print(f"现有事件: {len(events)}")

    # 去重索引：(region_id, event_month, event_type) → 已存在
    existing_keys = set()
    for e in events:
        key = (e.get("region_id"), e.get("event_month"), e.get("event_type"))
        existing_keys.add(key)
    print(f"去重索引: {len(existing_keys)} 个唯一事件")

    # 追加
    added = 0
    for ev in NEW_EVENTS:
        key = (ev["region_id"], ev["event_month"], ev["event_type"])
        if key in existing_keys:
            print(f"  跳过(已存在): {ev['region_id']} {ev['event_month']} {ev['event_type']}")
            continue
        events.append(ev)
        existing_keys.add(key)
        added += 1
        print(f"  ✓ 新增: {ev['region_id']} {ev['event_month']} {ev['event_type']} ({ev['loss_amount']}损失)")

    # 保存
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    print(f"\n已保存: {PATH}")
    print(f"新增: {added} 条, 总数: {len(events)}")

    # 统计
    from collections import Counter
    by_type = Counter(e.get("event_type") for e in events)
    real_count = sum(1 for e in events if e.get("is_real_label"))
    print(f"\n真实事件: {real_count}, demo: {len(events) - real_count}")
    print(f"按类型: {dict(by_type)}")

    # 按年份统计
    by_year = Counter(e.get("event_month", "")[:4] for e in events if e.get("is_real_label"))
    print(f"真实事件按年份: {dict(sorted(by_year.items()))}")

if __name__ == "__main__":
    main()
