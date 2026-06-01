from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "牧融绿链_答辩项目说明书_公网功能融合版.docx"


def set_font(run, size=10.5, bold=False, color=None):
    run.bold = bold
    run.font.name = "微软雅黑"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    run.font.size = Pt(size)
    if color:
        run.font.color.rgb = color


def shade_cell(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def add_heading(doc, text, level=1):
    paragraph = doc.add_heading("", level=level)
    run = paragraph.add_run(text)
    set_font(
        run,
        size=16 if level == 1 else 13,
        bold=True,
        color=RGBColor(31, 78, 121) if level == 1 else RGBColor(47, 84, 150),
    )
    return paragraph


def add_para(doc, text):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.line_spacing = 1.25
    paragraph.paragraph_format.space_after = Pt(6)
    run = paragraph.add_run(text)
    set_font(run)
    return paragraph


def add_bullets(doc, items):
    for item in items:
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.left_indent = Inches(0.24)
        paragraph.paragraph_format.first_line_indent = Inches(-0.12)
        paragraph.paragraph_format.line_spacing = 1.2
        paragraph.paragraph_format.space_after = Pt(4)
        run = paragraph.add_run("• " + item)
        set_font(run)


def cell_text(cell, text, bold=False):
    cell.text = ""
    paragraph = cell.paragraphs[0]
    run = paragraph.add_run(str(text))
    set_font(run, bold=bold)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell_text(cell, header, bold=True)
        shade_cell(cell, "D9EAF7")
        if widths:
            cell.width = Inches(widths[index])

    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cell_text(cells[index], value)
            if widths:
                cells[index].width = Inches(widths[index])
    doc.add_paragraph()
    return table


def build_doc():
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.78)
    section.right_margin = Inches(0.78)

    doc.styles["Normal"].font.name = "微软雅黑"
    doc.styles["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    doc.styles["Normal"].font.size = Pt(10.5)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("牧融绿链")
    set_font(run, size=24, bold=True, color=RGBColor(31, 78, 121))

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("工行高原畜牧绿色金融风险评估、产业链闭环与贷后管理平台")
    set_font(run, size=14, color=RGBColor(89, 89, 89))

    helper = doc.add_paragraph()
    helper.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = helper.add_run("答辩项目说明书 / 演示辅助稿")
    set_font(run, size=12, color=RGBColor(89, 89, 89))

    doc.add_paragraph()
    add_para(doc, "一句话介绍：面向高原牧区，融合气象遥感、经营主体、工行授信、产业链订单、资金流向、还款逾期和保险协同数据，为工行绿色信贷提供可解释的风险评估、产业链资金闭环、贷后预警和处置建议。")
    add_para(doc, "项目定位：这不是普通的高原畜牧展示平台，而是突出工行作为绿色金融服务主体的业务系统，覆盖授信准入、产业链资金闭环、风险评估、保险协同、绿色绩效和边疆民生治理协同。")

    add_heading(doc, "一、项目背景与痛点")
    add_para(doc, "高原牧区畜牧业具有明显的金融服务难点：牧户和合作社缺少传统抵押物，银行授信材料不足；草场退化、寒潮、积雪、干旱等自然风险会影响经营稳定性；活体资产、草场承载能力、保险覆盖和还款能力难以被传统信贷流程及时核验。")
    add_para(doc, "因此，本项目围绕工行绿色信贷业务流程，把高原牧区的环境风险、经营风险、产业链资金流风险和信用风险转化为客户经理可查看、可解释、可追踪、可处置的评估结果。")
    add_bullets(
        doc,
        [
            "贷前：辅助工行客户经理完成授信准入和额度判断。",
            "贷中：核验贷款资金用途、饲草采购、物流配送、牧场入库和产品回款。",
            "贷后：联动气象遥感、逾期还款和保险数据，形成贷后预警与处置建议。",
            "绿色金融：沉淀绿色信贷投放、生态风险识别、绿色绩效和普惠牧区服务绩效。",
        ],
    )

    add_heading(doc, "二、我具体做了什么")
    add_para(doc, "我完成了一套可运行的前后端平台，包括首页、平台概览、业务模块、数据底座、实施路线、风险评估、保险协同、产业链、绿色绩效、边疆民生等前台页面，以及管理端、模型接口和 JSON Store 数据闭环。系统可以本地启动，也可以部署到公网服务器。")
    add_table(
        doc,
        ["模块", "已实现内容"],
        [
            ["前台工作台", "工行绿色信贷风险评估工作台，包含对象池、评估报告、证据链、处置动作和评估明细。"],
            ["产业链资金闭环", "展示工行放款、饲草采购、物流配送、牧场入库、产品回款、贷后核销的资金闭环设计。"],
            ["绿色绩效评价", "展示 NDVI 改善趋势、县域风险分布、绿色估值指标框架和碳账户/GEP 接口预留。"],
            ["边疆民生协同", "展示边境重点县风险状态和地方政府、工商银行、保险机构、牧户合作社四方协同工作台。"],
            ["管理端", "支持 CSV 上传、数据表选择、样例数据包、导入状态、字段校验和图片轮播管理。"],
            ["后端 API", "FastAPI 提供平台数据、模型训练、预测、数据质量、公开数据、外部 API 配置等接口。"],
            ["数据底座", "使用 JSON Store 管理气象、遥感、经营主体、授信、风险标签和宏观饲草供需数据。"],
            ["模型层", "规则模型 + sklearn RandomForest/Ridge 混合模型，输出风险分、等级、因子贡献和趋势。"],
            ["客户经理流程", "准入申请、评估报告、人工复核、贷后核查、处置记录。"],
        ],
        widths=[1.4, 5.4],
    )

    add_heading(doc, "三、系统功能设计")
    add_heading(doc, "1. 工行风险评估工作台", level=2)
    add_para(doc, "核心页面是 /#dashboard，页面不是 PPT 看板，而是风控终端式工作台。")
    add_bullets(
        doc,
        [
            "左侧：工行评估对象池，支持县域风险与工行授信主体切换。",
            "中间：工行风险评估报告，展示综合风险分、风险等级、建议动作、风险因子贡献和风险走势。",
            "右侧：工行证据链与处置，展示气象证据、遥感证据、授信/用信/还款证据、保险覆盖、数据缺口和贷后处置动作。",
            "底部：工行评估明细，汇总对象、类型、风险分、敞口/用信、主因子和建议动作。",
        ],
    )

    add_heading(doc, "2. 工行客户经理工作流", level=2)
    add_table(
        doc,
        ["流程节点", "系统作用"],
        [
            ["准入申请", "选择县域或主体，查看基础画像和所在县域环境风险。"],
            ["评估报告", "生成综合风险分、等级、主风险因子和证据链。"],
            ["人工复核", "中高风险对象进入人工复核，核查数据来源和异常月份。"],
            ["贷后核查", "对逾期、用信率高、保险不足或环境风险高的主体生成核查建议。"],
            ["处置记录", "输出持续监测、额度复核、贷后核查、暂停增额等建议动作。"],
        ],
        widths=[1.4, 5.4],
    )

    add_heading(doc, "3. 产业链资金闭环", level=2)
    add_para(doc, "公网展示版本中单独设置了“产业链”页面，核心是把工行贷款资金流向和畜牧产业链经营动作串起来。页面展示“工行放款 → 饲草采购 → 物流配送 → 牧场入库 → 产品回款 → 贷后核销”的闭环，并预留订单表 supply_chain_orders 与资金流向表 supply_chain_payments。")
    add_table(
        doc,
        ["表/字段", "含义"],
        [
            ["supply_chain_orders", "记录订单号、采购主体、订单类型、供应商、金额、关联授信等。"],
            ["supply_chain_payments", "记录流水号、关联订单、付款方、收款方、金额、支付渠道和到账状态。"],
            ["业务价值", "证明工行贷款资金不是空转，而是定向进入饲草采购、物流配送和牧场经营闭环。"],
        ],
        widths=[2.0, 4.8],
    )

    add_heading(doc, "4. 绿色绩效与边疆民生", level=2)
    add_para(doc, "公网展示版本还包含绿色绩效评价和边疆民生与治理协同页面。绿色绩效页面展示 25 个县域、NDVI 2020-2024 改善趋势、风险分布、绿色估值指标框架，并预留碳账户、GEP 核算、可持续评分等接口。边疆民生页面展示边境重点县、平均风险、重点监测名单，以及地方政府、工商银行、保险机构、牧户合作社四方协同工作台。")

    add_heading(doc, "5. 主体详情能力", level=2)
    add_para(doc, "点击工行授信主体后，可以看到主体画像、授信历史、用信率、逾期、保险、贷款用途和所在县域环境风险。系统明确标注这些主体和授信数据是 sample/demo，避免把样例说成真实客户数据。")

    add_heading(doc, "四、数据底座")
    add_para(doc, "当前系统使用 JSON Store 保存数据，方便比赛演示，不依赖 MySQL；同时后端保留 MySQL 接口，后续可以替换为真实数据库。")
    add_table(
        doc,
        ["数据表", "当前规模", "来源/属性", "用途"],
        [
            ["weather_data", "1500 行", "TPDC CMFD，25 县 × 2020-2024 共 60 个月", "气象风险特征：温度、降水、风速、雪深、寒潮、暴雪、干旱。"],
            ["remote_sensing_data", "1500 行", "MODIS/TPDC 遥感，含 NDVI、积雪、退化、载畜量字段", "生态风险特征：NDVI、积雪覆盖、退化等级、载畜量。"],
            ["business_subjects", "75 行", "25 县 × 3 类样例主体，sample/demo", "经营主体画像和经营风险特征。"],
            ["finance_credit", "75 行", "工行授信/用信/还款/保险样例，sample/demo", "金融风险、逾期、用信率和保险覆盖。"],
            ["forage_supply_demand", "126 行", "Geodoi 宏观饲草供需数据", "宏观背景参考，不参与县域月度模型训练。"],
            ["risk_event_labels", "25 行", "demo 风险标签", "仅用于跑通标签链路，不是真实监督标签。"],
            ["产业链订单/资金流", "接口预留", "公网展示为待上传 CSV", "用于证明工行贷款资金闭环和贷后核销路径。"],
        ],
        widths=[1.45, 0.9, 2.4, 2.35],
    )
    add_para(doc, "重要说明：真实环境数据已经接入，但经营主体、工行授信和风险事件标签仍是比赛演示样例。系统在页面和接口中明确标注 sample/demo，避免伪造真实生产数据。")

    add_heading(doc, "五、模型与算法说明")
    add_para(doc, "模型训练单位是 region_id + month，即每个县每个月形成一个风险评估样本。当前模型使用 25 个县、60 个月，共 1500 个训练样本。")
    add_table(
        doc,
        ["项目", "当前状态"],
        [
            ["模型类型", "ml_hybrid：sklearn RandomForest + Ridge，与规则模型结合。"],
            ["样本数", "1500 个县域月度样本。"],
            ["特征数", "16 维特征。"],
            ["县域数", "25 个高原牧区示范县。"],
            ["月份数", "60 个月，覆盖 2020-2024。"],
            ["真实数据占比", "约 95%，主要来自 TPDC CMFD 和 MODIS/TPDC。"],
            ["标签类型", "rule_label，规则弱标签。"],
        ],
        widths=[1.5, 5.3],
    )
    add_para(doc, "模型特征分为四类：")
    add_bullets(
        doc,
        [
            "气象特征：温度、降水、风速、雪深、寒潮、暴雪、干旱。",
            "遥感特征：NDVI、NDVI 变化、植被覆盖、积雪覆盖、退化等级、载畜量。",
            "经营特征：主体评分、保险覆盖率。",
            "金融特征：还款状态、逾期次数、用信情况。",
        ],
    )
    add_para(doc, "模型输出包括综合风险分、风险等级、主风险因子、因子贡献、风险走势和处置建议。")
    add_para(doc, "必须强调：当前不是严格意义上的真实灾害预测或真实贷款逾期预测。因为真实灾害、理赔、逾期标签还不够，当前属于“真实环境数据 + 规则弱标签”的风险评分模型。")

    add_heading(doc, "六、技术路线")
    add_table(
        doc,
        ["层级", "技术/实现"],
        [
            ["前端", "Vue 3 + ECharts + 原生 CSS，无需构建工具，适合比赛快速演示。"],
            ["后端", "Python FastAPI，提供平台数据、模型、导入、数据质量、外部 API 等接口。"],
            ["数据存储", "JSON Store 为主，backend/data_store/*.json；预留 MySQL。"],
            ["模型层", "规则模型 + sklearn RandomForest/Ridge 混合模型。"],
            ["数据处理", "public_data/scripts/ingest_public_data.py 转换 TPDC、MODIS、CMFD 等公开数据。"],
            ["部署", "本地 uvicorn 启动，也可部署到公网 VPS。"],
        ],
        widths=[1.4, 5.4],
    )
    add_para(doc, "启动命令：cd D:\\工行杯\\yak-risk-platform")
    add_para(doc, "python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000")

    add_heading(doc, "七、项目创新点")
    add_bullets(
        doc,
        [
            "把高原气象遥感数据纳入工行授信准入，不再只依赖传统抵押和人工材料。",
            "把草场 NDVI、积雪、退化和载畜量转化为可解释的绿色信贷风险因子。",
            "把工行授信、用信、还款逾期和保险覆盖放进同一条风险证据链。",
            "把工行贷款资金流向与饲草采购、物流配送、牧场入库、产品回款和贷后核销串成闭环。",
            "把绿色绩效评价从口号变为指标框架，预留碳账户、GEP 和可持续评分接口。",
            "把边疆民生治理协同纳入平台，展示政府、银行、保险、合作社四方联动。",
            "把模型输出转化为客户经理可执行的业务动作，例如人工复核、贷后核查、暂停增额。",
            "明确区分真实数据、样例数据和弱标签，符合比赛演示的可信边界。",
        ],
    )

    add_heading(doc, "八、明天答辩可以怎么讲")
    add_para(doc, "建议开场 1 分钟：")
    add_para(doc, "我们做的是“牧融绿链”，一个面向高原牧区的工行绿色金融风险评估、产业链闭环与贷后管理平台。它不是普通的数据展示页面，而是围绕工行客户经理的真实业务动作设计：贷前准入、产业链资金闭环、额度判断、贷后预警、风险处置、保险协同、绿色绩效和边疆民生治理协同。系统把气象遥感、经营主体、工行授信、产业链订单、资金流向、逾期还款和保险覆盖数据融合起来，输出可解释的风险分、证据链和处置建议。")
    add_para(doc, "建议介绍系统 2-3 分钟：")
    add_bullets(
        doc,
        [
            "先讲业务痛点：高原牧区缺抵押、风险高、数据难核验、贷后管理滞后。",
            "再讲系统方案：用真实环境数据和经营/金融台账构建风险评估工作台。",
            "补充公网展示功能：产业链资金闭环、绿色绩效评价、边疆民生与四方治理协同。",
            "然后讲数据：1500 行气象、1500 行遥感、75 个样例主体、75 条授信样例、25 条 demo 标签。",
            "再讲模型：25 县 × 60 月 = 1500 个样本，规则 + sklearn 混合模型，输出风险分和因子贡献。",
            "最后讲边界：真实环境数据已接入，但金融主体和标签是样例，当前是弱监督评分，不夸大成真实预测。",
        ],
    )
    add_para(doc, "建议演示顺序：")
    add_bullets(
        doc,
        [
            "打开首页，说明项目定位是服务工行绿色金融。",
            "进入 /#dashboard，展示工行风险评估工作台。",
            "左侧先看县域风险对象池，点击一个县，展示气象、遥感、模型证据链。",
            "切换到工行授信主体，点击高风险主体，展示主体详情、用信率、逾期次数、保险状态。",
            "展示客户经理工作流：准入申请、评估报告、人工复核、贷后核查、处置记录。",
            "进入数据底座，说明哪些是真实数据，哪些是 sample/demo。",
            "进入产业链页面，说明工行放款、饲草采购、物流配送、牧场入库、产品回款、贷后核销闭环。",
            "进入绿色绩效和边疆民生页面，说明生态改善、绿色估值接口预留和四方协同。",
            "打开管理端，说明 CSV 导入、数据更新、模型重训闭环。",
        ],
    )

    add_heading(doc, "九、评委可能会问的问题与回答")
    qa = [
        ("问：你们的数据真实吗？", "答：气象和遥感环境数据是真实公开数据，主要来自 TPDC CMFD 和 MODIS/TPDC；经营主体和工行授信数据涉及真实客户隐私，当前比赛版使用脱敏样例；风险事件标签是 demo，用于跑通链路，不宣称为真实监督标签。"),
        ("问：模型是不是能预测真实逾期？", "答：目前不能这样夸大。当前模型是“真实环境数据 + 规则弱标签”的风险评分模型，可以用于辅助识别风险和解释风险因子。要做真实逾期预测，需要接入银行历史逾期、理赔和灾害损失标签。"),
        ("问：项目和普通农业大屏有什么区别？", "答：普通大屏偏展示，而我们的系统围绕工行业务动作设计，输出的是授信准入、额度判断、人工复核、贷后核查、暂停增额、银保协同等具体动作。"),
        ("问：产业链页面的意义是什么？", "答：它证明工行贷款资金可以被纳入闭环管理。贷款不是简单发放出去，而是绑定饲草采购、物流配送、牧场入库、产品回款和贷后核销，帮助工行核验资金用途和贷后风险。"),
        ("问：绿色绩效和边疆民生为什么放进系统？", "答：工行杯项目不只看金融科技工具，也看绿色金融和社会价值。绿色绩效用于展示生态改善、绿色信贷和碳/GEP接口预留；边疆民生用于体现高原边境地区产业稳定、普惠金融和多方治理协同。"),
        ("问：为什么要用遥感和气象？", "答：高原牧区的经营风险高度受草场、积雪、寒潮、干旱影响。传统授信很难核验这些风险，遥感和气象可以补充银行风控的信息缺口。"),
        ("问：系统怎么扩展到真实生产？", "答：一是把 JSON Store 替换为 MySQL 或银行数据仓库；二是接入真实经营台账、授信台账、保单和理赔数据；三是积累真实灾害和逾期标签后训练监督模型；四是把处置记录回流为模型样本。"),
    ]
    for question, answer in qa:
        add_para(doc, question)
        add_para(doc, answer)

    add_heading(doc, "十、当前边界与后续计划")
    add_bullets(
        doc,
        [
            "经营主体和工行授信数据是 sample/demo，不是真实客户数据。",
            "risk_event_labels 是 demo 标签，不是真实监督标签。",
            "载畜量字段部分使用样例 NPP 派生数据，后续需替换为真实 TPDC NPP 或草地生产力数据。",
            "MySQL 已预留，当前演示默认使用 JSON Store。",
        ],
    )
    add_para(doc, "后续计划：接入真实灾害、理赔、逾期标签；完善客户经理处置记录闭环；接入真实银行授信台账或脱敏批量数据；补齐产业链订单与资金流水 CSV 导入；完善银保协同记录；把绿色绩效中的碳账户、GEP 和可持续评分从接口预留逐步落到真实数据。")

    add_heading(doc, "十一、答辩时的最后总结")
    add_para(doc, "牧融绿链的价值在于，把高原牧区难以量化的生态、经营、产业链资金和信用风险，转化为工行绿色信贷可以使用的风险分、证据链和处置动作。它用真实环境数据支撑风险识别，用样例经营和授信台账跑通业务流程，用产业链页面呈现资金闭环，用绿色绩效和边疆民生页面体现社会价值，最终服务工行授信准入、贷后预警、银保协同、绿色金融绩效评价和边疆治理协同。")

    for section in doc.sections:
        footer = section.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer.add_run("牧融绿链 - 工行高原畜牧绿色金融风险评估、产业链闭环与贷后管理平台")
        set_font(run, size=9, color=RGBColor(128, 128, 128))

    doc.save(OUT)


if __name__ == "__main__":
    build_doc()
    print(OUT)
