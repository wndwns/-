from __future__ import annotations

import html
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "工银牧融_新版答辩说明书.docx"


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def p(text: str = "", style: str | None = None, bold: bool = False) -> str:
    rpr = "<w:rPr><w:b/><w:bCs/></w:rPr>" if bold else ""
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{esc(text)}</w:t></w:r></w:p>'


def bullet(text: str) -> str:
    return (
        '<w:p><w:pPr><w:pStyle w:val="ListParagraph"/>'
        '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'
        f"<w:r><w:t>{esc(text)}</w:t></w:r></w:p>"
    )


def table(rows: list[list[str]]) -> str:
    xml = [
        '<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/>'
        '<w:tblW w:w="0" w:type="auto"/><w:tblLook w:val="04A0"/></w:tblPr>'
    ]
    for ridx, row in enumerate(rows):
        xml.append("<w:tr>")
        for cell in row:
            shade = '<w:shd w:fill="EAF4EE"/>' if ridx == 0 else ""
            xml.append(
                f'<w:tc><w:tcPr>{shade}<w:tcW w:w="2400" w:type="dxa"/></w:tcPr>'
                f"{p(cell, bold=(ridx == 0))}</w:tc>"
            )
        xml.append("</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml)


def build_document() -> str:
    doc: list[str] = []

    doc.append(p("工银牧融", "Title"))
    doc.append(p("高原畜牧绿色金融风险评估与贷后管理平台", "Subtitle"))
    doc.append(p("新版答辩说明书", "Subtitle"))
    doc.append(p("面向工行杯比赛场景，融合气象遥感、经营主体、工行授信、还款逾期、保险协同和绿色绩效数据，为工行绿色信贷提供可解释的风险评估、贷后预警和处置建议。"))
    doc.append(p(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"))
    doc.append(p("说明：本文档依据当前本地 yak-risk-platform 系统功能与数据状态整理；其中经营主体、授信、保险、产业链、处置流程为脱敏样例数据，风险标签为 demo/规则弱标签，不表述为真实生产监督学习结论。"))

    doc.append(p("一、项目一句话定位", "Heading1"))
    doc.append(p("工银牧融不是普通的高原畜牧展示平台，而是以工商银行绿色金融服务为主体，面向高原牧区客户经理、风控人员和管理人员的绿色信贷风险评估与贷后管理系统。"))
    doc.append(p("系统围绕“贷前准入、额度判断、贷后监测、风险处置、银保协同、绿色绩效评价”构建闭环，让公开环境数据和银行业务数据能够进入同一个风险工作台。"))

    doc.append(p("二、为什么做这个项目", "Heading1"))
    for item in [
        "高原牧区金融服务面临信息不对称：气象灾害、草地退化、饲草供需、主体经营和还款行为分散在不同系统中。",
        "传统信贷流程依赖材料和人工经验，难以及时把寒潮、积雪、NDVI 变化、逾期苗头等证据转化为贷后动作。",
        "绿色金融不仅要放款，还要证明资金支持了绿色生产、生态改善、普惠覆盖和风险减量。",
        "比赛答辩需要突出工行角色，因此系统把页面从展示看板改成工行绿色信贷风险评估工作台。",
    ]:
        doc.append(bullet(item))

    doc.append(p("三、系统总体架构", "Heading1"))
    doc.append(table([
        ["层级", "技术与内容", "作用"],
        ["前端展示层", "Vue 3 + ECharts + 原生 CSS", "构建首页、风险评估工作台、数据底座、绿色绩效、边疆民生、管理端等页面"],
        ["后端服务层", "Python FastAPI", "提供平台数据、模型预测、CSV 导入、图片上传、地图天气配置、闭环业务接口"],
        ["数据存储层", "JSON Store 为主，预留 MySQL", "当前演示稳定运行在 JSON Store；MySQL 连接失败时自动回退，不影响答辩"],
        ["模型层", "规则模型 + sklearn RandomForest/Ridge 混合模型", "小样本用规则模型，样本足够时切换混合模型，并输出因子贡献和解释"],
        ["外部能力", "高德地图 JS API、Open-Meteo 开放天气、可选高德天气 Web 服务", "绘制县域点位、卫星遥感/标准地图/海拔态势图层，获取实时天气"],
    ]))

    doc.append(p("四、核心业务闭环", "Heading1"))
    for item in [
        "1. 数据接入：接入 TPDC CMFD 气象、MODIS/TPDC 遥感、主体经营、工行授信、还款、保险、产业链和绿色绩效数据。",
        "2. 风险评估：对县域和授信主体计算综合风险分，给出风险等级、主风险因子和建议动作。",
        "3. 工行准入与额度判断：结合生态环境风险、经营能力和授信敞口，支撑客户经理准入申请和额度复核。",
        "4. 贷后监测：通过风险走势、逾期苗头、气象遥感异常和用信率变化触发人工复核或贷后核查。",
        "5. 银保协同：展示保险覆盖和理赔样例链路，将灾害风险转化为风险缓释证据。",
        "6. 处置回流：把核查、展期、压降、暂停增额、保险协同等处置动作沉淀为后续模型和管理依据。",
        "7. 绿色绩效：统计绿色信贷余额、生态改善、普惠覆盖和风险减量，服务工行绿色金融绩效评价。",
    ]:
        doc.append(p(item))

    doc.append(p("五、当前主要功能", "Heading1"))
    doc.append(table([
        ["模块", "已经实现的能力", "答辩时强调点"],
        ["首页", "金融信贷官网风格首页，突出工行绿色金融主体、业务模块和能力入口", "不是 PPT 展示，而是可进入业务工作台的系统入口"],
        ["风险评估 / #dashboard", "工行绿色信贷风险评估工作台：对象池、评估报告、因子贡献、风险走势、证据链、处置建议", "客户经理能看到对象、风险分、主因子和下一步动作"],
        ["数据底座", "数据资产目录、质量结构、气象/遥感/金融/业务/闭环数据表", "明确哪些是真实环境数据，哪些是脱敏样例，哪些是弱标签"],
        ["高德地理证据图层", "已有县域点位，支持卫星遥感、海拔态势、标准地图，右侧展示气象、遥感、风险评分证据", "把地理位置、海拔、遥感和贷后预警联系起来"],
        ["实时天气", "Open-Meteo 开放天气自动刷新，切换县域立即更新，标签页回到前台自动刷新；高德天气作为可选增强", "无需付费天气 Key，适合后续部署演示"],
        ["管理端 /admin", "CSV 导入、数据质量、外部 API 配置、轮播图片管理", "配置入口放管理端，不破坏前台业务界面"],
        ["绿色绩效", "绿色信贷、生态改善、普惠覆盖、风险减量等绩效指标", "对应工行绿色金融评价，而非泛泛展示畜牧数字化"],
        ["边疆民生", "展示牧区民生改善、普惠金融覆盖、产业稳定和风险保障", "体现工行金融服务对边疆牧区的社会价值"],
    ]))

    doc.append(p("六、数据底座现状", "Heading1"))
    doc.append(table([
        ["数据表", "当前规模", "来源与用途"],
        ["weather_data.json", "1500 行", "TPDC CMFD，25 县 × 2020-2024 共 60 个月，用于气象风险证据"],
        ["remote_sensing_data.json", "1500 行", "MODIS/TPDC 遥感，NDVI、积雪、退化、载畜量字段，用于生态与草地风险"],
        ["business_subjects.json", "75 行", "脱敏样例主体，支撑授信主体画像和经营维度评分"],
        ["finance_credit.json", "75 行", "脱敏样例授信、用信和还款数据，支撑工行额度与逾期风险判断"],
        ["forage_supply_demand.json", "126 行", "Geodoi 宏观饲草供需，只做宏观背景，不参与县域月度模型训练"],
        ["insurance_claims.json", "8 行", "保险协同与理赔样例，用于展示风险缓释链路"],
        ["supply_chain_orders/payments", "各 12 行", "产业链订单和回款样例，用于展示贷款用途和回款闭环"],
        ["post_loan_workflow.json", "12 行", "贷后核查、复核、处置记录样例"],
        ["green_performance_metrics.json", "75 行", "绿色金融绩效样例，用于绿色信贷评价"],
        ["import_metadata.json", "20 条", "记录导入来源、时间和数据质量追踪"],
    ]))
    doc.append(p("重要说明：当前系统是“真实环境数据 + 脱敏样例业务数据 + 规则弱标签”的演示系统。真实灾害、真实理赔、真实逾期标签仍不足，因此模型输出用于辅助评估和流程展示，不能夸大为已经完成真实生产监督学习。"))

    doc.append(p("七、模型与可解释性", "Heading1"))
    for item in [
        "模型端点包括 /api/model/status、/train、/predict、/importance、/forecast、/evaluation、/label-info。",
        "小样本或标签不足时使用规则模型，保证系统可解释和可演示。",
        "样本足够时使用 sklearn RandomForest + Ridge 混合模型，兼顾非线性风险识别和线性解释。",
        "特征覆盖气象、遥感、经营主体、工行授信、还款、保险等维度。",
        "前端展示综合风险分、等级、主风险因子、因子贡献、风险走势和建议动作，避免只给一个黑箱分数。",
    ]:
        doc.append(bullet(item))

    doc.append(p("八、地图与实时天气方案", "Heading1"))
    for item in [
        "高德地图 JS API：用于地图底图、县域点位、标准地图、卫星遥感和交互控件。",
        "海拔态势：在标准地图上叠加县域中心海拔点位和地形色带，避免误称为真实 DEM 三维地形。",
        "Open-Meteo 开放天气：无需 API Key，按经纬度获取实时温度、湿度、降水、风速和天气代码。",
        "实时刷新机制：页面加载立即请求；每 10 分钟轮询；切换县域立即刷新；浏览器标签页重新可见时刷新。",
        "回退机制：外部实时天气不可用时，自动回退本地 CMFD 月度气象数据，保证答辩演示不断链。",
    ]:
        doc.append(bullet(item))

    doc.append(p("九、答辩演示建议流程", "Heading1"))
    for item in [
        "1. 先打开首页，说明项目定位：工行绿色金融服务主体，不是普通牧区展示平台。",
        "2. 进入 /#dashboard，演示工行评估对象池，选择县域或授信主体，查看综合风险分、等级、主因子和建议动作。",
        "3. 展示右侧证据链：气象、遥感、授信/用信/还款、保险覆盖、数据缺口和处置动作。",
        "4. 进入数据底座，说明数据资产来源、样例/真实/弱标签边界和数据质量结构。",
        "5. 演示高德地理证据图层，切换卫星遥感、海拔态势和标准地图，点击县域列表查看证据更新。",
        "6. 展示实时天气自动刷新，说明 Open-Meteo 无需付费 Key，后续可部署到云端。",
        "7. 打开管理端，说明 CSV 导入、字段校验、API 配置和图片管理由管理端维护，不影响前台业务界面。",
        "8. 最后强调闭环：准入申请、风险评估、人工复核、贷后核查、处置记录、银保协同、绿色绩效回流。",
    ]:
        doc.append(p(item))

    doc.append(p("十、部署与后续扩展", "Heading1"))
    doc.append(table([
        ["方向", "当前状态", "后续做法"],
        ["本地演示", "FastAPI 同时服务 API 和前端静态页面", "使用 python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000 启动"],
        ["Vercel 前端部署", "前端可静态化部署", "建议将 Open-Meteo 改为前端直连；高德地图 Key 用环境变量或配置接口管理"],
        ["后端云部署", "FastAPI 需单独运行", "可放 Render、Railway、腾讯云、阿里云或自有服务器；Vercel 前端请求后端 API"],
        ["数据库", "当前 JSON Store 稳定演示，预留 MySQL", "正式环境接 MySQL/PostgreSQL，导入记录和数据质量追踪继续保留"],
        ["模型标签", "当前 rule_label/弱标签", "后续接入真实灾害、理赔、逾期、核查结果，形成真实监督训练样本"],
    ]))

    doc.append(p("十一、答辩可用总结话术", "Heading1"))
    doc.append(p("本项目以工商银行绿色金融服务为核心，把高原牧区的气象遥感数据、经营主体数据、授信用信还款数据、保险协同数据和绿色绩效数据放入同一个风险评估与贷后管理闭环。系统既能给客户经理看清“是否准入、额度是否合理、贷后是否需要核查”，也能给风控管理人员看清“风险来自哪里、证据是否充分、处置动作如何回流”。当前模型没有夸大为真实生产预测，而是明确采用真实环境数据、脱敏样例业务数据和规则弱标签构建可解释演示系统，为后续接入真实灾害、理赔和逾期标签预留了完整链路。"))

    return "".join(doc)


def write_docx() -> None:
    body = build_document()
    now = datetime.now(timezone.utc).isoformat()

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    {body}
    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1260" w:bottom="1440" w:left="1260" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>
  </w:body>
</w:document>'''

    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei" w:hAnsi="Microsoft YaHei"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:pPr><w:spacing w:after="120" w:line="360" w:lineRule="auto"/></w:pPr><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei" w:hAnsi="Microsoft YaHei"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/><w:spacing w:before="480" w:after="240"/></w:pPr><w:rPr><w:b/><w:bCs/><w:color w:val="B20D18"/><w:sz w:val="44"/><w:szCs w:val="44"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/><w:spacing w:after="180"/></w:pPr><w:rPr><w:color w:val="1F6B43"/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="360" w:after="160"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:bCs/><w:color w:val="1F6B43"/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:style>
  <w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="D9E6DD"/><w:left w:val="single" w:sz="4" w:space="0" w:color="D9E6DD"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="D9E6DD"/><w:right w:val="single" w:sz="4" w:space="0" w:color="D9E6DD"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="D9E6DD"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="D9E6DD"/></w:tblBorders></w:tblPr></w:style>
</w:styles>'''

    numbering_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>'''

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>'''

    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''

    doc_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/></Relationships>'''

    core = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>工银牧融新版答辩说明书</dc:title><dc:creator>Codex</dc:creator><cp:lastModifiedBy>Codex</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>'''

    app = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Codex</Application></Properties>'''

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document_xml)
        z.writestr("word/styles.xml", styles_xml)
        z.writestr("word/numbering.xml", numbering_xml)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", app)

    print(str(OUT))
    print(OUT.stat().st_size)


if __name__ == "__main__":
    write_docx()
