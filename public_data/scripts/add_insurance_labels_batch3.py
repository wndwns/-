"""
补充更多牦牛险理赔数据 - 第三批
数据来源：四川甘肃青海西藏政府公报、新闻报道
"""

import json
from pathlib import Path
from datetime import datetime

LABELS_FILE = Path(r"C:\Users\WH\Desktop\gonghangbei - 副本\backend\data_store\risk_event_labels.json")

NEW_LABELS_BATCH3 = [
    # === 四川省 ===
    # 1. 2022年甘孜州牦牛保险数据
    {
        "region_id": "ganzi-shiqu",
        "event_month": "2022-12",
        "event_type": "insurance_coverage",
        "severity": "低",
        "loss_amount": 770300,
        "claim_amount": 4839.57,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "甘孜银保监分局",
        "source_url": "https://www.gzz.gov.cn/gzzrmzf/c100044/202301/85e48659c23a4aba855f2cd7cc754bae.shtml",
        "is_real_label": True,
        "note": "2022年甘孜州承保牦牛77.03万头，同比增长181.25%，保费收入10013.62万元，赔付支出4839.57万元，赔付率48.33%。人保37.39万头、中华联合29.43万头、中航安盟4.43万头、平安3.21万头、太平2.56万头",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 2. 2022年阿坝州中华财险牦牛险
    {
        "region_id": "aba-hongyuan",
        "event_month": "2022-12",
        "event_type": "insurance_coverage",
        "severity": "低",
        "loss_amount": 836000,
        "claim_amount": 6760,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "中国金融新闻网/中华财险四川分公司",
        "source_url": "https://www.financialnews.com.cn/bx/jg/cx/202305/t20230518_271065.html",
        "is_real_label": True,
        "note": "2022年中华财险在阿坝州承保牦牛83.6万头，提供风险保障16.7亿元，支付保险赔款6760万元，受益农户16973户次。打破夏饱秋肥冬瘦春亡恶性循环",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 3. 2023年中华财险阿坝累计数据
    {
        "region_id": "aba-hongyuan",
        "event_month": "2023-10",
        "event_type": "insurance_coverage",
        "severity": "低",
        "loss_amount": 3925600,
        "claim_amount": 34100,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "新华网/中华财险四川分公司",
        "source_url": "http://www.xinhuanet.com/money/20231101/6c85db37b4b749c0bf9335c2d47a2b6e/c.html",
        "is_real_label": True,
        "note": "截至2023年10月，中华财险四川分公司在阿坝累计承保牦牛392.56万头，为2.92万户次牧民提供风险保障78.51亿元，为10.27万余户次牧民挽回直接经济损失3.41亿元",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 4. 2022年松潘县牦牛保险
    {
        "region_id": "aba-hongyuan",
        "event_month": "2022-10",
        "event_type": "insurance_coverage",
        "severity": "低",
        "loss_amount": 6003,
        "claim_amount": 1200.6,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "松潘县政府办公室",
        "source_url": "https://www.abazhou.gov.cn/abazhou/c101960/202210/2ded1a3aa7174ee8834cdde7d5759dfd.shtml",
        "is_real_label": True,
        "note": "2022年1-10月松潘县牦牛参保634户132404头，总保费1721万元，政府补贴80%。牦牛理赔6003头，理赔金额1200.6万元。牦牛赔款2000元/头",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 5. 2020年红原县麦洼牦牛保险
    {
        "region_id": "aba-hongyuan",
        "event_month": "2020-09",
        "event_type": "insurance_coverage",
        "severity": "低",
        "loss_amount": 2558800,
        "claim_amount": 11251,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "四川农村日报/红原县",
        "source_url": "https://cbgc.scol.com.cn/news/389187",
        "is_real_label": True,
        "note": "红原县首创麦洼牦牛吉祥三保模式，累计承保适龄牦牛255.88万头，牦牛保险赔付11251万元，受益牧民6.32万户次，户均赔款4113元。防返贫保覆盖2181头牦牛",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # === 甘肃省 ===
    # 6. 2023年合作市牦牛保险
    {
        "region_id": "gannan-luqu",
        "event_month": "2023-12",
        "event_type": "insurance_coverage",
        "severity": "低",
        "loss_amount": 1835,
        "claim_amount": 550.5,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "甘南州农业农村局",
        "source_url": "http://nync.gnzrmzf.gov.cn/info/1178/12235.htm",
        "is_real_label": True,
        "note": "2023年合作市参保牦牛5.56万头，参保率100%。牦牛死损1835头，理赔550.5万元。牦牛保额从2000元提高到3000元。藏系羊理赔262.7万元，共计813.2万元",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 7. 2023年玛曲县牦牛保险
    {
        "region_id": "gannan-luqu",
        "event_month": "2023-12",
        "event_type": "insurance_coverage",
        "severity": "低",
        "loss_amount": 567938,
        "claim_amount": 636.8,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "甘南广播电视台/玛曲县",
        "source_url": "http://nync.gnzrmzf.gov.cn/info/1251/11664.htm",
        "is_real_label": True,
        "note": "2023年玛曲县投保牦牛567938头，理赔636.8万元。出栏牦牛96638头，产值4.35亿元，同比增长11.4%。活体抵押贷款118户1976万元",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 8. 2020年玛曲县牦牛保险
    {
        "region_id": "gannan-luqu",
        "event_month": "2020-11",
        "event_type": "insurance_coverage",
        "severity": "低",
        "loss_amount": 516075,
        "claim_amount": 231.208,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "玛曲县政府",
        "source_url": "http://www.maqu.gov.cn/info/1040/11029.htm",
        "is_real_label": True,
        "note": "2020年玛曲县投保牦牛51.6075万头、藏羊33.4557万只，保费7092.6万元。截至11月保险报案1221次，理赔231.208万元，受益1221户",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 9. 2023年碌曲县牦牛保险
    {
        "region_id": "gannan-luqu",
        "event_month": "2023-06",
        "event_type": "insurance_coverage",
        "severity": "低",
        "loss_amount": 63000,
        "claim_amount": 0,
        "claim_unit": "头",
        "overdue_flag": False,
        "source": "碌曲县农业农村局",
        "source_url": "http://nync.gnzrmzf.gov.cn/info/1111/9946.htm",
        "is_real_label": True,
        "note": "2023年碌曲县牦牛保险已承保6.3万头，存栏牦牛23.7万头占牲畜总数46.7%。牛羊保险理赔资金近3000万元。十户联产贷款42户2686万元",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 10. 2023年甘南州牦牛保险
    {
        "region_id": "gannan-luqu",
        "event_month": "2023-11",
        "event_type": "insurance_coverage",
        "severity": "低",
        "loss_amount": 1123100,
        "claim_amount": 336800,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "甘南州政府办公室",
        "source_url": "http://www.gnzrmzf.gov.cn/info/1937/68118.htm",
        "is_real_label": True,
        "note": "2023年甘南州6家财险公司为112.31万头牦牛提供33.68亿元风险保障。全州牦牛产业贷款27.90亿元，13款牦牛特色贷款累计4.21亿元，全产业链贷款28.73亿元",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # === 青海省补充 ===
    # 11. 2018年玉树雪灾
    {
        "region_id": "yushu-zaduo",
        "event_month": "2018-11",
        "event_type": "snowstorm",
        "severity": "高",
        "loss_amount": 0,
        "claim_amount": 0,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "人民网/人保财险玉树分公司",
        "source_url": "http://m.toutiao.com/group/6859154561337131534/",
        "is_real_label": True,
        "note": "2018年11月玉树遭遇60年一遇大雪灾，一口气下了三个月。雪灾前全州藏系牛羊保险覆盖四个县，牧民一周内得到赔偿。未参保两县特事特办后补保费也获赔",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 12. 2015年玉树牦牛险推广
    {
        "region_id": "yushu-chengduo",
        "event_month": "2015-06",
        "event_type": "insurance_coverage",
        "severity": "低",
        "loss_amount": 0,
        "claim_amount": 0,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "人民网",
        "source_url": "http://m.toutiao.com/group/6859154561337131534/",
        "is_real_label": True,
        "note": "2015年玉树州在两个县推广藏系牛羊保险，招募200个协赔协保员下到村里。牦牛总保费120元，牧户承担18元，县级财政10%，省级35%，中央40%。保额2000元封顶",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # === 西藏补充 ===
    # 13. 2024年昌都丁青类乌齐牦牛险
    {
        "region_id": "changdu-leiwuqi",
        "event_month": "2024-12",
        "event_type": "insurance_coverage",
        "severity": "低",
        "loss_amount": 0,
        "claim_amount": 8600,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "中国金融新闻网/中国太保",
        "source_url": "https://www.financialnews.com.cn/m/2025-08/25/content_432142.html",
        "is_real_label": True,
        "note": "2024年中国太保承保昌都丁青县、类乌齐县2023-2024年政策性农业保险，高效应对雪灾疫病，赔付8600余万元，惠及2.4万户农牧家庭",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 14. 2024年日喀则江孜县牦牛险
    {
        "region_id": "rikaze-jiangzi",
        "event_month": "2024-06",
        "event_type": "insurance_coverage",
        "severity": "低",
        "loss_amount": 0,
        "claim_amount": 0,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "中国金融新闻网/中国太保",
        "source_url": "https://www.financialnews.com.cn/m/2025-08-25/content_432142.html",
        "is_real_label": True,
        "note": "2024年中国太保承保日喀则市江孜县2024-2026年政策性农业保险及特色农险项目",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 15. 2024年贡嘎县猪饲料保险期货
    {
        "region_id": "linzhi-bayi",
        "event_month": "2024-12",
        "event_type": "insurance_futures",
        "severity": "低",
        "loss_amount": 7550,
        "claim_amount": 2208.79,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "中国金融新闻网/中国太保",
        "source_url": "https://www.financialnews.com.cn/m/2025-08/25/content_432142.html",
        "is_real_label": True,
        "note": "2024年中国太保在贡嘎县、曲水县推出猪饲料成本保险+期货项目，覆盖饲料7550吨，风险保障2208.79万元，对冲养殖企业饲料成本波动风险",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 16. 2022年阿里防贫保
    {
        "region_id": "ali-gaize",
        "event_month": "2022-12",
        "event_type": "insurance_coverage",
        "severity": "低",
        "loss_amount": 24819,
        "claim_amount": 583200,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "中国金融新闻网/中国太保",
        "source_url": "https://www.financialnews.com.cn/m/2025-08/25/content_432142.html",
        "is_real_label": True,
        "note": "2022年中国太保为阿里地区7个县持续承保防贫保产品，为24819人提供58.32亿元保障，覆盖因病因灾致贫风险",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 17. 2024年拉孜县地震电站理赔
    {
        "region_id": "rikaze-jiangzi",
        "event_month": "2024-04",
        "event_type": "earthquake",
        "severity": "中",
        "loss_amount": 0,
        "claim_amount": 317,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "中国金融新闻网/中国太保",
        "source_url": "https://www.financialnews.com.cn/m/2025-08/25/content_432142.html",
        "is_real_label": True,
        "note": "2024年4月25日日喀则拉孜县查务乡500KVA电站因地震财产受损，中国太保快速赔付317万元，助力企业快速恢复生产",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 18. 2026年那曲牦牛险改革
    {
        "region_id": "naqu-seni",
        "event_month": "2026-04",
        "event_type": "insurance_reform",
        "severity": "低",
        "loss_amount": 0,
        "claim_amount": 5000,
        "claim_unit": "元/头",
        "overdue_flag": False,
        "source": "西藏日报/那曲市财政局",
        "source_url": "https://www.xizang.gov.cn/xwzx_406/dsdt/202605/t20260525_541671.html",
        "is_real_label": True,
        "note": "2026年4月那曲市政策性农业保险改革落地，牦牛因疫病、风雪灾害、野生动物袭击致死均可获5000元赔偿，解决同命不同价问题。那曲牦牛存栏量超200万头",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 19. 2017-2019年果洛气象指数保险累计
    {
        "region_id": "guoluo-maqin",
        "event_month": "2019-12",
        "event_type": "insurance_coverage",
        "severity": "低",
        "loss_amount": 0,
        "claim_amount": 1124,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "经济参考报/中国太保",
        "source_url": "http://jjckb.xinhuanet.com/2020-08/31/c_139330140.htm",
        "is_real_label": True,
        "note": "2017-2019年中国太保在果洛州藏系羊牦牛降雪量气象指数保险累计赔付1124万元。保费95%由上海援青资金支持，牧户自缴5%，贫困户免缴",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 20. 2019年果洛州草料捐赠
    {
        "region_id": "guoluo-jiuzhi",
        "event_month": "2019-03",
        "event_type": "snowstorm",
        "severity": "中",
        "loss_amount": 500,
        "claim_amount": 62,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "经济参考报/中国太保",
        "source_url": "http://jjckb.xinhuanet.com/2020-08/31/c_139330140.htm",
        "is_real_label": True,
        "note": "2019年3月果洛州暴雪造成牦牛草料紧缺，中国太保产寿险青海分公司共同出资62万元购买500余吨草料，送到玛多县、达日县、甘德县牧民手中",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 21. 2020年果洛州玛多县雪灾
    {
        "region_id": "guoluo-maqin",
        "event_month": "2020-02",
        "event_type": "snowstorm",
        "severity": "高",
        "loss_amount": 0,
        "claim_amount": 0,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "经济参考报/中国太保",
        "source_url": "http://jjckb.xinhuanet.com/2020-08/31/c_139330140.htm",
        "is_real_label": True,
        "note": "2020年2月中国太保产寿险青海分公司再次出资购买草料送到果洛州玛多县、达日县、甘德县牧民手中，缓解暴雪造成的牦牛草料紧缺",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
    # 22. 2018年共和县防贫保案例
    {
        "region_id": "haibei-gangcha",
        "event_month": "2018-06",
        "event_type": "insurance_coverage",
        "severity": "中",
        "loss_amount": 0,
        "claim_amount": 5.3,
        "claim_unit": "万元",
        "overdue_flag": False,
        "source": "经济参考报/中国太保",
        "source_url": "http://jjckb.xinhuanet.com/2020-08/31/c_139330140.htm",
        "is_real_label": True,
        "note": "2018年青海共和县铁盖乡熊有平患肝癌，自付近10万元。中国太保通过医疗费大数据监测启动核查，最终赔付5.3万元，挽救濒临贫困边缘家庭",
        "data_source": "real",
        "is_sample": False,
        "imported_at": datetime.now().isoformat()
    },
]

def update_labels():
    with open(LABELS_FILE, 'r', encoding='utf-8') as f:
        existing_labels = json.load(f)

    print(f"现有标签数: {len(existing_labels)}")
    print(f"现有真实标签数: {sum(1 for l in existing_labels if l.get('is_real_label'))}")

    existing_labels.extend(NEW_LABELS_BATCH3)

    print(f"\n新增标签数: {len(NEW_LABELS_BATCH3)}")
    print(f"更新后总标签数: {len(existing_labels)}")
    print(f"更新后真实标签数: {sum(1 for l in existing_labels if l.get('is_real_label'))}")

    with open(LABELS_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing_labels, f, ensure_ascii=False, indent=2)

    print(f"\n已写入: {LABELS_FILE}")

    real_labels = [l for l in existing_labels if l.get('is_real_label')]
    regions = set(l['region_id'] for l in real_labels)
    print(f"\n真实标签覆盖县数: {len(regions)}")
    print(f"覆盖县: {sorted(regions)}")

    from collections import Counter
    years = Counter(l['event_month'][:4] for l in real_labels)
    print(f"\n按年份统计:")
    for year, count in sorted(years.items()):
        print(f"  {year}: {count} 条")

if __name__ == "__main__":
    update_labels()
