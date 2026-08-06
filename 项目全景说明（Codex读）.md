# 工银牧融项目全景说明（Codex 维护档案）

> 最后核验：2026-08-07
> 核验基线：<code>main</code> 分支，提交 <code>f5ed234</code>
> 仓库：<code>https://github.com/wndwns/-.git</code>
> 用途：供后续 AI、Codex 和项目成员快速恢复完整上下文。本文记录的是“当前仓库实际状态”，不是宣传稿。

## 0. 阅读规则

### 0.1 信息优先级

遇到冲突时，按以下顺序判断：

1. 当前 <code>main</code> 的代码与实际数据文件。
2. 本文最近一次核验后的说明。
3. <code>README.md</code>、<code>项目架构分析报告.md</code>。
4. <code>项目介绍（ai读）.txt</code>、答辩文档、历史报告和旧截图。

旧文档保留了设计意图和演进历史，但存在过时或夸大的数据口径。修改项目之前必须重新核对代码，不能直接复制旧文档结论。

### 0.2 项目版本

- 当前正式运行版本：<code>backend/server.py</code> + <code>frontend/</code>。
- <code>backend/server_v2.py</code>、<code>backend/server_v3.py</code>、<code>frontend_v2/</code>、<code>frontend_v3/</code> 是历史版本和视觉迭代参考，不是当前入口。
- <code>demo/</code> 是早期演示页，不是当前业务系统。
- 旧版保护分支：<code>codex/backup/pre-deepening-20260807</code>，指向提交 <code>2d40dec</code>。

### 0.3 后续修改的硬约束

- 任何删减、隐藏或砍掉现有功能，都必须先问用户。
- 任何会实质改变功能、数据、交互、成本、权限、安全或验收标准的方案，都必须先让用户确认。
- 方案确认后仍需用户明确批准，才能开始实现。
- 正常改动完成后应提交并推送 GitHub；不得覆盖旧版保护分支。
- 不得把样例、派生、弱标签或待核验数据宣传成真实工行业务数据。
- 不得在文档、日志、截图或回答中暴露姓名、手机号、地址、耳标明细、API Key、会话文件或数据库密码。
- 不得回退用户已有的未提交修改。

## 1. 项目身份

### 1.1 名称

- 参赛项目名：**工银牧融**。
- 当前前端品牌名：**牧融绿链**。
- 完整定位：**工行高原畜牧绿色金融风险评估与贷后管理平台**。

### 1.2 一句话定义

项目把高原牧区的气象、遥感、草场、载畜、经营主体、授信还款、产业链、保险和绿色绩效数据组织为一条可追溯的工行业务链，帮助客户经理回答：

1. 能不能贷。
2. 贷多少。
3. 贷后有没有风险。
4. 出风险怎么处置。

### 1.3 核心方向

项目不是单一“灾害预测工具”，也不是单一“保险画像工具”。它的主线是：

**气候与遥感 → 灾害和生态风险 → 草场承载与饲草成本 → 主体经营压力 → 保险与信用缓释 → 贷前准入和额度 → 贷后预警与处置。**

贷款金额评估是项目核心的一部分，不能在后续聚焦时被误删。当前实现仍是规则型额度调整，后续可以深化，但必须保留“贷多少”这一业务问题。

### 1.4 当前不是以下系统

- 不是工行生产信贷系统。
- 不是可自动审批、自动拒贷或自动定价的模型。
- 不是经过真实逾期、理赔和损失标签验证的信用评分卡。
- 不是全部数据实时更新的生产平台。
- 不是保险合同管理系统；当前百巴村资料主要是牲畜资产/耳标登记参考。
- 不是县域载畜量实测系统；当前载畜量全部为派生值，其中大部分来自样例 NPP。

## 2. 服务对象与角色

### 2.1 主要用户

- 工行客户经理：查主体、看证据、判断准入、测算额度、生成核查动作。
- 工行风险管理人员：看县域风险池、模型边界、数据质量和预警分布。
- 平台管理员：导入 CSV、查看数据状态、配置外部 API、管理首页内容。

### 2.2 协同角色

- 牧户与合作社：提供经营、存栏、草场、订单和还款资料。
- 保险机构：补充合同、责任范围、保额、理赔和查勘数据。
- 饲草供应商、加工企业、物流主体：形成贷款用途和回款闭环。
- 政府及科研数据提供方：提供气象、遥感、生态、灾害和宏观产业数据。

### 2.3 关键痛点

- 高原牧户和合作社传统抵押物不足，活体资产和经营能力难核验。
- 暴雪、寒潮、干旱、草地退化会同时影响牲畜存活、饲草成本和还款能力。
- 银行、保险、产业和生态数据分散，客户经理难以形成一份可追溯结论。
- 牧区地域广、现场成本高，贷后风险发现和处置滞后。
- 绿色信贷成效缺少可复核、可汇报的证据链。

## 3. 端到端业务闭环

~~~text
公开/导入数据
  气象 + 遥感 + NPP/物候 + 主体 + 授信 + 保险 + 订单/支付
        ↓
数据质量与来源标记
  real / public / derived / sample / unverified
        ↓
区域筛查
  四维规则风险 + 16维弱监督模型 + 灾害/退化/载畜预警
        ↓
主体评估
  主体评分 + 用信率 + 逾期 + 区域风险 + 保险覆盖
        ↓
工行决策提示
  能不能贷 → 贷多少 → 贷后监测 → 风险处置
        ↓
人工核验
  客户经理核对资产、合同、还款、用途和现场资料
        ↓
闭环数据回流
  订单/支付、理赔、核查任务、绿色绩效
~~~

系统输出是筛查和辅助决策材料，最终授信与贷后动作由人工完成。

## 4. 当前贷款金额评估

这是当前代码的真实规则，位于 <code>frontend/app.js</code> 的 <code>creditDecisionBrief</code>。

### 4.1 县域额度策略

县域只输出额度池调整系数，不直接给单户贷款金额：

| 县域风险分 | 准入提示 | 区域系数 |
|---|---|---:|
| 低于 55 | 正常准入 | 1.00 |
| 55 至 69.99 | 审慎准入 | 0.90 |
| 70 及以上 | 区域收紧 | 0.80 |

前端会用演示性“参考敞口 × 区域系数”展示调整效果。参考敞口本身是根据当前样例授信池分摊得到的，不是真实县域额度池。

### 4.2 主体额度规则

输入：

- 当前授信额度 <code>line</code>，页面单位为万元。
- 已用额度 <code>used</code>。
- 主体风险分 <code>riskScore</code>。
- 逾期次数 <code>overdue</code>。
- 保险覆盖率 <code>insurance</code>。
- 用信率 <code>usage = used / line</code>。

规则：

| 条件 | 准入提示 | 调整系数 |
|---|---|---:|
| 保险覆盖率不低于 80%，且用信率低于 75% | 建议准入 | 1.10 |
| 其他低风险主体 | 建议准入 | 1.05 |
| 风险分 55 至 59.99 | 复核后准入 | 1.00 |
| 风险分 60 至 69.99 | 审慎准入 | 0.95 |
| 存在逾期，或风险分不低于 70 | 暂缓新增 | 0.85 |

输出：

**建议额度 = max（已用额度，当前授信额度 × 调整系数后取整）**

这保证建议额度不会低于已经使用的额度，但它只是对既有授信的规则调整，不是从牲畜价值、现金流、偿债覆盖率、贷款期限和风险资本独立推导出的完整贷款金额模型。

### 4.3 主体风险分

对正常样例主体，前端使用：

**主体风险分 = clamp（100 - 主体评分 + 用信率 × 35 + 逾期次数 × 12 + 区域风险分 × 0.12，0，100）**

### 4.4 未核验资料拦截

当主体或金融记录的 <code>data_source</code> 为 <code>real_insurance</code> 或 <code>asset_register_reference</code> 时：

- <code>needsVerification = true</code>。
- 主体风险分置为 <code>null</code>。
- 页面显示“资料待核验”和“人工核验”。
- 不生成贷款额度建议。
- 不把资产登记直接解释为保险合同、授信记录或还款记录。

### 4.5 额度模型还缺什么

要升级为可验证的贷款金额评估，至少需要真实且合规的：

- 可核验牲畜数量、权属、价值和处置折扣。
- 历史销售、订单、回款、成本、毛利和现金流。
- 当前负债、授信、用信、期限、利率和还款计划。
- 保险公司、保单号、责任范围、保额、免赔、期限和理赔记录。
- 灾害损失、逾期、违约、核销及处置结果。

在这些数据接入前，当前额度结果只能称为“比赛演示规则建议”。

## 5. 风险评估与模型

### 5.1 四维区域规则风险

<code>backend/data.py:get_risk_assessment()</code> 按县域计算：

- 气象风险 30%：寒潮、暴雪、干旱取最严重等级。
- 遥感生态 25%：退化等级、NDVI 低值和 NDVI 下降。
- 主体经营 20%：主体平均评分和保险覆盖率。
- 金融保险 25%：还款状态和逾期次数。

综合分：

**总风险 = 气象 × 0.30 + 遥感 × 0.25 + 主体经营 × 0.20 + 金融保险 × 0.25**

分级：低于 50 为低，50 至 69.99 为中，70 及以上为高。

注意：页面和 <code>get_score_model()</code> 还展示“主体信用、产业经营、活体资产、生态约束、气候风险、保险保障”六维设计稿。当前后端真实计算是上述四维，六维与四维尚未统一。

### 5.2 16 维月度特征

<code>backend/models.py</code> 按 <code>region_id + month</code> 生成 16 维特征：

1. 平均温度。
2. 月累计降水。
3. 平均风速。
4. 最大雪深。
5. 最严重寒潮等级。
6. 最严重暴雪等级。
7. 最严重干旱等级。
8. 平均 NDVI。
9. 平均 NDVI 变化率。
10. 平均植被覆盖率。
11. 最大积雪覆盖率。
12. 最严重退化等级。
13. 平均载畜量。
14. 区域主体平均评分。
15. 区域平均保险覆盖率。
16. 区域金融风险分。

### 5.3 标签与训练

- 基础标签是与四维规则相同的规则风险分。
- <code>real_labels_1500.json</code> 有 1500 行，但训练只使用其中 42 条带 <code>source_url</code> 的公开事件覆盖对应月份的规则标签。
- 其余 1458 个月份是“未确认”，不是“真实无灾”。
- 来源支持事件在训练时权重为普通样本的 5 倍。
- 样本少于 50：只用规则模型。
- 样本不少于 50 且 sklearn 可用：标准化后训练随机森林分类器和 Ridge 回归。
- 实际连续风险预测来自 Ridge；随机森林主要用于风险类别训练和特征重要性混合。

### 5.4 当前运行统计

2026-08-07 在现有 Python 环境中直接调用模型模块得到：

| 指标 | 当前值 |
|---|---:|
| 县月样本 | 3262 |
| 县域 | 26 |
| 月份 | 137 |
| 特征 | 16 |
| 模型类型 | ml_hybrid |
| 规则统计中的“真实数据占比” | 0.97 |
| 来源支持事件 | 42 |
| 未确认月份 | 1458 |

一次随机切分评估为 MAE 3.06、RMSE 4.09、R² 0.79、测试样本 653。**这些指标评估的是规则弱标签，不代表真实灾害、损失、理赔、逾期或违约预测能力。**

“真实数据占比 0.97”是按 <code>data_source</code> 字符串分类得出的数据行占比，不是监督标签真实率，也不是生产可用率。

### 5.5 预测与解释

- <code>predict()</code> 输出每个县月的风险分、等级和四维驱动说明。
- <code>feature_importance()</code> 混合预设规则权重与随机森林特征重要性。
- <code>explain_prediction()</code> 和批量解释可在 SHAP 可用时增强，否则使用规则解释。
- <code>forecast()</code> 以当前风险分、NDVI 趋势、季节正弦项和固定随机种子噪声外推，不是经过校准的时间序列预测。
- 预测区间固定为风险分上下 10 分，不能解释为统计置信区间。

### 5.6 历史回测的真实含义

<code>backtest_report.json</code> 是历史实验材料。原始文件仍写有“1500 条真实标签、总体通过”，但其中：

- 平均时间序列 R² 为 -0.645。
- 事件验证精确率为 0.049。
- F1 为 0.093。
- 误报率为 0.951。
- 1458 个无来源月份曾被错误当成负样本。

当前 <code>GET /api/model/backtest</code> 会强制返回：

- <code>overall_pass = false</code>。
- <code>report_status = not_valid_for_business_decision</code>。

不得引用原始回测文件中的“通过”结论。

## 6. 生态、饲草和灾害算法

### 6.1 载畜量

<code>backend/carrying_capacity.py</code> 的月度精细载畜量：

**NPP 基准 × NDVI 修正 × 季节系数 × 退化系数 × 积雪系数 × 物候系数**

其中 NPP 基准约为 <code>NPP × 15000 + 5000</code>。日度预测继续加入逐日 NDVI 插值、逐日季节系数、Open-Meteo 雪深和物候窗口。

当前所有 <code>carrying_capacity_sheep_unit</code> 都是派生值；2392 行遥感中，2300 行标记为样例载畜量，92 行为参考区域派生值。不能称为实测载畜量。

### 6.2 饲草成本

<code>backend/feed_calculator.py</code>：

- 按坐标匹配县域和最近气象数据。
- 用正弦模型拟合并预测逐日温度。
- NDVI 低于 0.15 时提高补饲比例，NDVI 高于 0.25 时降低补饲比例。
- 5 至 6 月接羔季上调精料需求。
- 叠加存栏规模、牲畜类型和价格参数，输出日/月饲草量与成本。
- 四季牧场自动模式以县城中心坐标和启发式海拔差模拟转场，不是实际牧场轨迹。

### 6.3 草地退化与综合预警

<code>backend/early_warning.py</code> 综合：

- 简化版 GDI。
- 气候修正 NPP。
- NDVI 异常监测。
- SPI 干旱风险。
- 雪灾风险。
- SAR 融合接入状态。

当前 GDI 并未完整复现论文 PCA、K-means 和曲率流程；实现是 NPP、NDVI、折算草产量归一化后的等权简化，并用草产量阈值分级。输出中的论文方法名称必须配合“简化版”说明。

### 6.4 五灾种 90 天预测

<code>backend/disaster_forecast.py</code> 支持寒潮、雪灾、干旱、暴雪和生态风险：

- 0 至 16 天：Open-Meteo 实时预报，代码标记为高置信。
- 17 至 30 天：季节性外推和历史同期均值，代码标记为中置信。
- 31 至 90 天：气候态和历史概率分布，代码标记为低置信。

它是规则外推和气候背景预测，不是经过当地灾害损失样本校准的商业预报产品。

### 6.5 时空网格

<code>backend/spatio_temporal_grid.py</code> 按：

- 3 种草地类型。
- 4 个季节。
- 5 个牲畜年龄组。

构成理论上的 60 个网格单元，计算生态、天气、经营和综合风险。草地比例和多项系数含经验设定，主要用于细分展示与情景分析。

### 6.6 合作社排序

<code>backend/cooperative_ranking.py</code> 权重为：

- 工商维度 40%。
- 生态维度 30%。
- 气象维度 20%。
- 经营维度 10%。

排序对象包含生成的合作社数据和少量公开记录匹配。单源/双源校验只反映名称和来源匹配程度，不等于工行尽调、征信查询或正式授信评级。

## 7. 保险资料与百巴村案例

### 7.1 当前数据

<code>backend/data_store/insurance_policies.json</code> 当前包含：

- 百巴村 21 户主体。
- 1135 条牦牛资产/耳标登记记录。
- 1135 头登记牦牛。
- 聚合的规模、批次和资料完整度信息。

文件历史上由“保单模板”导入，但字段不足以证明每条记录都是有效保险合同。文件名、<code>total_policies</code> 字段和部分历史 <code>data_source=real_insurance</code> 属于旧命名，不应按字面宣传。

### 7.2 当前系统允许说什么

- 可以说存在 21 户主体与 1135 头牦牛的登记关系。
- 可以展示聚合规模、资料完整度和人工核验清单。
- 可以把环境风险用于核查排序。

### 7.3 当前系统不能说什么

- 不能说已核验 1135 份有效保险合同。
- 不能推导保险责任、保额、保费、期限或赔付能力。
- 不能计算保险使贷款风险下降了多少。
- 不能根据这些记录自动生成授信额度。
- 不能返回或展示个人姓名、电话、地址和耳标明细。

### 7.4 尽调案例

<code>GET /api/insurance-portfolio/due-diligence</code> 只返回聚合事实和四类证据状态：

- 资产登记：已观察。
- 环境筛查：仅筛查。
- 保险合同：缺失。
- 授信记录：缺失或样例。

建议动作是核验身份和资产、合同和责任范围、真实授信和还款、资金用途，最终由客户经理决定。

## 8. 数据资产快照

以下为 2026-08-07 的当前文件状态。

### 8.1 主业务表

| 文件 | 行数 | 当前含义 |
|---|---:|---|
| <code>weather_data.json</code> | 2820 | 26 县气象；TPDC 2748，Open-Meteo 72；2015-01 至 2024-12 |
| <code>remote_sensing_data.json</code> | 2392 | 26 县 NDVI、雪盖、退化、载畜；MODIS 及派生数据；2020-01 至 2026-05 |
| <code>business_subjects.json</code> | 76 | 75 条样例主体 + 1 条历史资产登记映射 |
| <code>finance_credit.json</code> | 76 | 75 条样例授信 + 1 条历史资产登记映射 |
| <code>insurance_claims.json</code> | 8 | 全部样例 |
| <code>supply_chain_orders.json</code> | 12 | 全部样例 |
| <code>supply_chain_payments.json</code> | 12 | 全部样例 |
| <code>post_loan_workflow.json</code> | 12 | 全部样例 |
| <code>green_performance_metrics.json</code> | 75 | 全部样例 |
| <code>forage_supply_demand.json</code> | 126 | Geodoi 全国六区域 2000 至 2020 宏观数据，不直接代表项目县域 |

### 8.2 环境辅助数据

| 文件 | 规模 | 当前含义 |
|---|---:|---|
| <code>npp_by_region.json</code> | 26 县 | 2001 至 2025，区域框平均提取结果 |
| <code>phenology_by_region.json</code> | 26 县 | 2003 至 2024 物候统计 |
| <code>climate_era5.json</code> | 26 县键 | ERA5/气候序列辅助 |
| <code>climate_era5_regional.json</code> | 26 县键 | 区域版本气候序列 |
| <code>snow_depth_openmeteo.json</code> | 26 县及来源说明 | Open-Meteo 雪深辅助 |
| <code>forage_supply_demand.json</code> | 126 行 | 全国宏观背景，不进入县域载畜模型 |

历史对比文件 <code>npp_by_region_old_30x30.json</code> 和 <code>npp_by_region_regional.json</code> 用于方法比较，不是主读取入口。

### 8.3 标签与实验

| 文件 | 行数 | 当前含义 |
|---|---:|---|
| <code>risk_event_labels.json</code> | 117 | 92 条带来源 URL 的公开事件材料 + 25 条样例；当前模型训练不直接读取此表 |
| <code>real_labels_1500.json</code> | 1500 | 42 条带来源 URL 的公开事件 + 1458 条未确认月份；模型直接读取 |
| <code>risk_event_labels_demo_backup.json</code> | 25 | 样例备份 |
| <code>backtest_report.json</code> | 1 份报告 | 历史无效回测材料，API 已强制标为不可用于业务决策 |
| <code>prediction_risk.json</code> | 26 | 历史预测/分析结果，不是主风险接口来源 |

<code>real_labels_1500.json</code> 的 <code>is_real_label=true</code> 不能单独作为真实性依据；训练代码使用“是否存在来源 URL”进行过滤。

### 8.4 数据来源分级

- **公开观测**：TPDC、MODIS、Open-Meteo、Geodoi 等可追溯来源。
- **派生数据**：由公开观测经规则、插值或公式计算，如退化等级、载畜量、风险分。
- **来源支持事件**：有公开 URL，但通常只是事件发生证据，不等于银行损失、理赔或逾期标签。
- **样例/模拟**：经营主体、授信、理赔、产业链和绿色绩效的比赛演示数据。
- **待核验登记**：百巴村资产/耳标记录，不能自动视为保险合同或授信数据。
- **历史实验**：旧预测、旧回测、旧版本和下载探索产物。

### 8.5 当前数据逻辑的一个重要漏洞

模型的数据来源统计把不属于 <code>sample</code>、<code>simulated</code>、<code>csv</code> 的未知来源字符串计入“真实数据”。因此历史 <code>real_insurance</code> 标记会被计入真实行，且区域经营/金融特征聚合没有像前端一样排除待核验记录。

前端已经阻止这类记录生成单户风险分和额度建议，但区域模型仍可能读取其字段。修复会改变模型输入和结果，实施前必须先让用户确认方案。

## 9. 技术架构

### 9.1 运行结构

~~~text
浏览器
  frontend/index.html + app.js + styles.css
  本地 vendor/vue.global.prod.js + vendor/echarts.min.js
        ↓ /api/*
FastAPI
  backend/server.py
        ↓
业务模块
  data.py / models.py / early_warning.py / carrying_capacity.py
  feed_calculator.py / cooperative_ranking.py / insurance_portfolio.py
  spatio_temporal_grid.py / disaster_forecast.py
        ↓
数据层
  JSON Store（默认） → MySQL（可选） → 内置样例回退
~~~

### 9.2 后端模块

| 文件 | 责任 |
|---|---|
| <code>server.py</code> | FastAPI 应用、78 个路由、静态文件、导入导出、外部集成 |
| <code>data.py</code> | 数据访问、区域/主体/金融/闭环读取、四维风险、平台聚合 |
| <code>store.py</code> | 11 类 JSON 表、CSV 解析、替换/追加、导入元数据 |
| <code>db.py</code> | 可选 MySQL 连接池和初始化 |
| <code>models.py</code> | 16 维特征、规则弱标签、RF + Ridge、解释和趋势外推 |
| <code>early_warning.py</code> | GDI、气候 NPP、NDVI、SPI、雪灾和综合预警 |
| <code>carrying_capacity.py</code> | NPP/NDVI/季节/退化/雪/物候载畜量 |
| <code>feed_calculator.py</code> | 气温、NDVI、规模、接羔季和迁徙饲草成本 |
| <code>cooperative_ranking.py</code> | 合作社生成/公开记录匹配、多维排序和来源核验 |
| <code>insurance_portfolio.py</code> | 百巴村资产登记画像、资料完整度、尽调清单 |
| <code>spatio_temporal_grid.py</code> | 草地 × 季节 × 年龄时空风险网格 |
| <code>disaster_forecast.py</code> | Open-Meteo 五灾种 90 天规则预测 |
| <code>extract_npp.py</code> | NPP 提取工具 |
| <code>extract_phenology.py</code> | 物候提取工具 |
| <code>test_truthful_outputs.py</code> | 真实性边界的最小回归检查 |
| <code>schema.sql</code>、<code>seed_data.sql</code> | 可选 MySQL 建表和种子数据 |

### 9.3 存储优先级

<code>data.py</code> 的读取意图是：

1. <code>backend/data_store/*.json</code>。
2. 可用的 MySQL。
3. 内置样例。

JSON 是当前主要运行方式。MySQL 不是必需条件，也没有成为当前比赛演示的主数据源。

### 9.4 前端

- Vue 3 全局版，无 npm 构建步骤。
- ECharts 本地 vendor 文件。
- 主入口 <code>frontend/index.html</code>。
- 主逻辑 <code>frontend/app.js</code>。
- 样式 <code>frontend/styles.css</code>。
- 独立管理端 <code>frontend/admin.html</code>。
- <code>overview.html</code>、<code>modules.html</code>、<code>module.html</code>、<code>data.html</code>、<code>roadmap.html</code> 是可直接访问的页面壳或历史兼容入口。

### 9.5 当前页面

主 SPA 有 14 个逻辑页面：

1. 首页。
2. 风险评估。
3. 平台概览。
4. 业务模块。
5. 模块详情。
6. 数据底座。
7. 实施路线。
8. 保险协同。
9. 产业链。
10. 绿色绩效。
11. 边疆民生。
12. 合作社排序。
13. 保单/资产画像。
14. 灾害预测。

风险评估页已经形成“对象池 → 证据 → 四个业务问题 → 客户经理工作流”的主交互。

### 9.6 管理端

管理端支持：

- CSV 数据导入、预览、替换或追加。
- 下载表模板。
- 查看公开样例和已处理文件。
- 查看当前数据状态。
- 配置外部 API。
- 管理首页轮播图和平台内容。

当前没有登录、角色权限、审计日志和操作审批，不可直接暴露到生产网络。

### 9.7 部署

- 本地 FastAPI 同时提供前端静态文件和 API。
- <code>vercel.json</code> 只指定 <code>frontend</code> 为静态输出目录，不会部署 FastAPI。
- 因此前端若直接发布到 Vercel，必须另有可访问的后端并处理 API 地址，否则 <code>/api/*</code> 不会完整工作。

## 10. API 总览

<code>backend/server.py</code> 当前有 78 个路由装饰器。

### 10.1 平台与基础数据

- GET <code>/api/health</code>
- GET <code>/api/platform</code>
- GET <code>/api/outline</code>
- GET <code>/api/brand</code>
- GET <code>/api/regions</code>
- GET <code>/api/modules</code>
- GET <code>/api/score-model</code>
- GET <code>/api/subjects</code>
- GET <code>/api/finance</code>
- GET <code>/api/closed-loop</code>
- GET <code>/api/closed-loop/{table}</code>
- GET <code>/api/alerts</code>
- GET <code>/api/weather</code>
- GET <code>/api/remote-sensing</code>
- GET <code>/api/risk-assessment</code>
- GET <code>/api/data-connections</code>
- GET <code>/api/data-sources</code>

### 10.2 数据源、外部集成和存储

- POST <code>/api/data-sources/{source_key}/config</code>
- POST <code>/api/data-sources/{source_key}/refresh</code>
- GET <code>/api/integrations/status</code>
- GET <code>/api/integrations/open-meteo/now</code>
- GET <code>/api/integrations/amap/weather</code>
- GET <code>/api/integrations/amap/map-config</code>
- POST <code>/api/import/csv</code>
- GET <code>/api/store/status</code>
- GET <code>/api/store/table/{table}/download</code>
- GET <code>/api/store/table/{table}/template</code>

### 10.3 管理与公开数据

- GET <code>/api/admin/content</code>
- GET <code>/api/admin/slides</code>
- POST <code>/api/admin/slides</code>
- POST <code>/api/admin/upload-image</code>
- POST <code>/api/admin/platform</code>
- GET <code>/api/public-data/sources</code>
- GET <code>/api/public-data/samples</code>
- GET <code>/api/public-data/processed</code>

### 10.4 模型

- GET <code>/api/model/status</code>
- POST <code>/api/model/train</code>
- POST <code>/api/model/predict</code>
- GET <code>/api/model/importance</code>
- GET <code>/api/model/forecast</code>
- GET <code>/api/model/evaluation</code>
- GET <code>/api/model/label-info</code>
- GET <code>/api/model/macro-background</code>
- GET <code>/api/model/explain/{region_id}</code>
- GET <code>/api/model/explain-all</code>
- GET <code>/api/model/backtest</code>

### 10.5 保险/资产资料

- GET <code>/api/insurance-portfolio/profile</code>
- GET <code>/api/insurance-portfolio/farmers</code>
- GET <code>/api/insurance-portfolio/farmer/{farmer_id}</code>
- GET <code>/api/insurance-portfolio/synergy</code>
- GET <code>/api/insurance-portfolio/comprehensive-risk</code>
- GET <code>/api/insurance-portfolio/due-diligence</code>

农户详情接口会返回敏感字段，生产化前必须增加鉴权、脱敏和最小权限控制。

### 10.6 饲草、质量和载畜

- POST <code>/api/feed/estimate</code>
- GET <code>/api/feed/pasture-info/{region_id}</code>
- POST <code>/api/feed/estimate-migration-auto</code>
- POST <code>/api/feed/estimate-migration-manual</code>
- GET <code>/api/data-quality</code>
- GET <code>/api/import/metadata</code>
- GET <code>/api/forage-supply-demand</code>
- GET <code>/api/forage-supply-demand/summary</code>
- GET <code>/api/carrying-capacity/daily</code>

### 10.7 排序、预警、网格和灾害

- GET <code>/api/cooperative-ranking/{region_id}</code>
- GET <code>/api/cooperative-ranking</code>
- GET <code>/api/cooperative-verify/{region_id}</code>
- GET <code>/api/cooperative-cross-source/{coop_name:path}</code>
- GET <code>/api/cooperative-cross-source-all/{region_id}</code>
- GET <code>/api/warning/comprehensive/{region_id}</code>
- GET <code>/api/warning/comprehensive-all</code>
- GET <code>/api/warning/gdi</code>
- GET <code>/api/warning/ndvi</code>
- GET <code>/api/warning/disaster/{region_id}</code>
- GET <code>/api/grid/status</code>
- GET <code>/api/grid/all</code>
- GET <code>/api/grid/{region_id}</code>
- GET <code>/api/disaster-forecast</code>
- GET <code>/api/disaster-forecast/regions</code>

### 10.8 页面

- GET <code>/admin</code>
- GET <code>/{path:path}</code>

## 11. 数据导入与研究脚本

### 11.1 主要数据管道

- <code>public_data/scripts/ingest_public_data.py</code>：统一清洗、合并和标记公开数据。
- <code>extract_cmfd_v0106.py</code>、<code>extract_cmfd_regional.py</code>：CMFD 气象提取。
- <code>extract_npp_regional.py</code>、<code>backend/extract_npp.py</code>：NPP 提取。
- <code>fetch_boundaries.py</code>：26 县边界。
- <code>fetch_snow_depth.py</code>：Open-Meteo 雪深。
- <code>gee_export_*.js</code>、<code>generate_gee_script.py</code>：GEE 导出模板。
- <code>import_cmfd_to_backend.py</code>：气象导入。
- <code>import_insurance_policies.py</code>：历史资产/耳标数据导入。
- <code>mark_derived_data.py</code>：派生字段标记。

### 11.2 标签和模型实验

- <code>build_real_labels.py</code>、<code>append_real_events.py</code>：来源事件材料。
- <code>backtest.py</code>：历史回测脚本。
- <code>compare_models.py</code>、<code>compare_predictions.py</code>：实验比较。
- <code>audit_data_gaps.py</code>：数据缺口检查。
- <code>test_real_label_train.py</code>、<code>test_shap.py</code>：模型实验检查。

<code>add_insurance_labels*.py</code> 是旧的保险标签扩充脚本，相关产物不能再直接当真实负标签或真实保险效果。

### 11.3 探索性下载脚本

<code>download_grassland_data*.py</code>、<code>explore_imap*.py</code>、<code>tpdc_browser*.py</code> 等大量版本是下载探索过程，不属于运行时。以后维护时应先找最终有效脚本，不要把每个历史版本接入主链。

### 11.4 文档和演示工具

- <code>tools/create_defense_doc.py</code>
- <code>tools/generate_defense_doc.py</code>
- <code>tools/generate_team_dev_doc.py</code>
- <code>tools/import_linzhi_data.py</code>
- 根目录的截图脚本和 API 检查脚本。

### 11.5 案例库

<code>案例库/B站案例库.md</code> 和 <code>案例库/抖音案例库.md</code> 是竞品/场景研究材料：

- B站案例来自视频转录，可能有语音识别错误。
- 抖音案例实际未成功提取抖音视频，主要是公开新闻二次整理。
- 案例数据只能做方向参考，关键金额、赔付、产品和政策必须回到一手权威来源核验。

## 12. 配置、依赖与启动

### 12.1 Python 依赖

<code>requirements.txt</code> 包括：

- FastAPI、Uvicorn、Pydantic。
- NumPy、scikit-learn。
- PyMySQL、DBUtils。
- xarray、netCDF4、rasterio、Pillow。

### 12.2 环境变量

只参考 <code>.env.example</code>：

- <code>MYSQL_HOST</code>
- <code>MYSQL_PORT</code>
- <code>MYSQL_USER</code>
- <code>MYSQL_PASSWORD</code>
- <code>MYSQL_DATABASE</code>
- <code>AMAP_WEB_SERVICE_KEY</code>
- <code>AMAP_JS_API_KEY</code>
- <code>AMAP_SECURITY_JS_CODE</code>
- <code>OPEN_METEO_ENDPOINT</code>

不得读取、记录或提交真实 <code>.env</code> 值。

### 12.3 本地启动

~~~powershell
Set-Location "C:\Users\WH\Desktop\gonghangbei - 副本"
python -m pip install -r requirements.txt
python .\backend\server.py
~~~

访问：

- 前台：<code>http://127.0.0.1:8000</code>
- 管理端：<code>http://127.0.0.1:8000/admin</code>
- API 文档：<code>http://127.0.0.1:8000/docs</code>

2026-08-07 当前被调用的 Python 环境缺少 <code>uvicorn</code>，直接导入 <code>backend.server</code> 会失败。模型模块和数据模块可以运行。首次启动前应安装 <code>requirements.txt</code>。

### 12.4 可选 MySQL

<code>schema.sql</code> 包含区域、区域指标、气象、遥感、主体、金融、保险、预警、评分、模块、数据源配置和平台配置表。当前 JSON Store 已足够跑比赛版，不应为了“看起来企业级”强行增加 Redis、微服务或新数据库。

## 13. 测试与验证

### 13.1 当前正式回归检查

<code>backend/test_truthful_outputs.py</code> 检查：

- 未核验资产登记不能产生保险风险下降比例。
- 未核验资料不能产生综合授信风险分。
- 尽调接口不输出个人敏感字段。
- 标签说明必须承认 42 条来源事件和 1458 个未知月份。

### 13.2 其他检查脚本

- <code>check_all_api.py</code>、<code>check_api.py</code>、<code>check_platform.py</code>。
- <code>validate_v3.py</code>。
- <code>public_data/scripts/test_portfolio.py</code>。
- 截图脚本用于视觉回归和答辩材料。

这些多数是脚本式检查，不是完整自动化测试套件。没有 CI 配置、权限测试、并发写入测试、端到端浏览器测试和生产安全测试。

### 13.3 每次改动后的最低验证

~~~powershell
python -m compileall backend
python backend\test_truthful_outputs.py
node --check frontend\app.js
git diff --check
~~~

改动 API 或页面时，再启动服务检查 <code>/api/health</code>、<code>/api/platform</code>、<code>/api/model/status</code> 和相关业务页面。

## 14. 当前已完成、演示中和未完成

| 能力 | 状态 | 说明 |
|---|---|---|
| 26 县气象/遥感底座 | 已接入公开/派生数据 | 数据日期和来源不完全同步 |
| 四维县域风险评分 | 可运行 | 规则评分 |
| 16 维混合模型 | 可运行 | 训练目标仍是规则弱标签 |
| 县域与主体风险工作台 | 可运行 | 主体金融数据主要为样例 |
| 贷款金额建议 | 可演示 | 既有额度规则调整，不是完整定额模型 |
| 贷后任务和处置 | 可演示 | 工作流数据为样例 |
| 百巴村资产尽调 | 可演示 | 仅资产/耳标登记，合同和授信待核验 |
| 产业链订单和支付 | 可演示 | 数据为样例 |
| 绿色绩效 | 可演示 | 数据为样例 |
| 灾害预测 | 可运行 | 规则和气候外推，未做损失校准 |
| 载畜量和饲草成本 | 可运行 | 载畜量派生，迁徙位置为启发式 |
| 合作社排序 | 可演示 | 含生成数据，不能当正式评级 |
| MySQL | 预留 | 非当前主存储 |
| 外部 API 配置 | 部分可用 | Open-Meteo/高德；刷新接口多为预留 |
| 用户、权限和审计 | 未实现 | 生产化硬缺口 |
| 真实工行授信/逾期数据 | 未接入 | 不得暗示已接入 |
| 真实保险合同/理赔闭环 | 未接入 | 不得从资产登记推导 |

## 15. 已知不一致与风险

### 15.1 文档口径

- <code>README.md</code> 曾写“样本不少于 20 即 ML”，当前代码阈值是 50。
- <code>README.md</code> 的训练规模、真实标签和遥感缺口说明有历史残留。
- <code>项目架构分析报告.md</code> 把随机森林回归器列为当前模型，实际连续预测使用 Ridge。
- <code>项目介绍（ai读）.txt</code> 曾把 1135 条登记记录写成真实保单，把 1458 个未报道月份写成真实负标签，并引用旧回测“通过”结论；这些均已过时。

### 15.2 页面和后端

- 页面存在六维评分展示，后端主风险实际是四维。
- 前端标签披露仍可能把 <code>risk_event_labels</code> 笼统写成 demo/sample，而当前表含 92 条带 URL 的公开事件材料和 25 条样例。
- 页面把来源未核验主体挡在单户决策之外，但区域模型仍可能聚合其字段。
- <code>business_subjects.json</code> 和 <code>finance_credit.json</code> 的一条历史记录仍使用 <code>real_insurance</code> 旧标记。

### 15.3 数据与模型

- 环境观测真实不等于监督标签真实。
- 来源 URL 证明有公开事件材料，不等于损失、理赔或逾期事实完整。
- 训练/测试随机切分可能混入相邻月份和相同县域，不能替代严格时间外验证。
- 经营和金融特征是区域静态聚合，会被复制到多个县月样本。
- 载畜量全部派生，2300 行来自样例基准。
- 预测区间、置信度等级和 90 天灾害外推是启发式，不是概率校准。

### 15.4 安全与隐私

- API 和管理端没有身份认证。
- CORS 当前允许任意来源。
- 数据源配置可把 API Key 明文持久化到 <code>content-store.json</code>。
- 农户详情接口可能返回个人字段。
- JSON 文件写入没有数据库级事务和并发控制。
- 本地存在 <code>.env</code>、TPDC 会话/状态文件和浏览器配置目录；当前检查显示它们未被 Git 跟踪，但不得提交或分享。

### 15.5 运行和部署

- 当前 Python 环境缺少 Uvicorn，后端尚未在本次核验中启动。
- Vercel 配置只发布静态前端。
- 项目没有 CI/CD 和生产健康监控。

## 16. 当前深化方向

已确认的方向不是把项目改成另一个主题，而是沿原主线做深：

1. **把证据链做实**：每个风险、额度和处置结论都能追到数据来源、时间、状态和限制。
2. **把贷款金额做深**：保留当前额度规则，逐步补齐资产价值、现金流、偿债能力、保险责任和情景压力，而不是删掉“贷多少”。
3. **把贷前贷后串起来**：同一主体从准入、额度、提款、用途、监测、核查到处置有连续记录。
4. **把保险从口号变成核验项**：先验证合同和责任，再讨论风险缓释；不再从耳标登记直接计算保险增信。
5. **把比赛表达做可信**：强调高原畜牧场景、工行客户经理工作流、公开环境数据和人工尽调闭环。

这些是方向，不代表所有功能已批准实施。每一步具体改法仍需用户确认。

## 17. 比赛表达

### 17.1 推荐的一句话

**工银牧融不是替银行自动审批，而是把高原牧区难核验的生态、活体资产、经营、保险和贷后信号，变成工行客户经理可追溯、可复核、可处置的绿色金融证据链。**

### 17.2 推荐演示顺序

1. 选择一个县域，看公开气象和遥感证据。
2. 展示区域风险、主要驱动和数据质量。
3. 切换到一个脱敏样例主体，回答“能不能贷、贷多少”。
4. 展示额度规则和其使用的数据，不把结果说成自动审批。
5. 触发贷后核查、保险协同或暂停增额动作。
6. 切换到百巴村，展示系统如何对资料不足主动停止计算并生成尽调清单。
7. 最后展示产业链和绿色绩效如何回流。

可信的“不会算”是项目亮点之一：当保险合同和授信数据不足时，系统明确要求人工核验，而不是生成看似精确的分数。

## 18. Git 与工作区

- 当前分支：<code>main</code>。
- 远端：<code>origin = https://github.com/wndwns/-.git</code>。
- 当前基线提交：<code>f5ed234 fix: prevent unverified records from driving credit outputs</code>。
- 前一深化提交：<code>94902dc feat: focus on traceable due diligence flow</code>。
- 旧版保护分支：<code>codex/backup/pre-deepening-20260807</code>。

编写本文时，工作区已有用户修改或未跟踪内容：

- <code>.gitignore</code>
- <code>code-knowledge-graph.json</code>
- <code>项目介绍（ai读）.txt</code>
- <code>.serena/</code>
- <code>案例库/</code>

未来 AI 不得为“清理工作区”而回退这些内容。

## 19. 后续 AI 的维护流程

每次开始工作：

1. 激活 Serena 项目 <code>C:\Users\WH\Desktop\gonghangbei - 副本</code>。
2. 查看 <code>git status</code>、当前分支和最近提交。
3. 先读本文，再核对将要修改的实际代码。
4. 确认当前正式入口仍是 <code>backend/server.py</code> 和 <code>frontend/</code>。
5. 对照数据来源状态，禁止把字段名当成真实性证明。
6. 涉及删功能或重大方案，先问用户。
7. 获批后做最小、可验证的改动。
8. 运行与改动风险相匹配的检查。
9. 只暂存本次改动，不混入用户已有文件。
10. 提交并推送 GitHub，保留旧版。

## 20. 术语

- **公开观测数据**：从公开数据源获得的环境或宏观数据。
- **派生数据**：通过公式、映射、插值或模型生成的数据。
- **规则弱标签**：用现有特征按业务规则计算的训练目标，不是真实结果标签。
- **来源支持事件**：有公开 URL 支撑的事件材料。
- **未确认月份**：没有足够来源确认事件状态，不能当无事件。
- **资产登记参考**：主体与牲畜/耳标关系资料，不等于保险合同。
- **额度建议**：基于现有授信的演示规则调整，不是审批决定。
- **尽调**：客户经理对身份、资产、合同、还款、用途和现场资料的人工核验。
- **草畜平衡**：草场供给和牲畜负荷之间的匹配。
- **NPP**：净初级生产力，用于估算草地生产能力。
- **NDVI**：归一化植被指数，用于反映植被状态。
- **GDI**：草地退化指数；本项目为简化实现。

---

本文应随主流程、数据口径、额度规则或真实性边界的变化同步更新。只改页面文案而不更新本文，会再次造成项目认知偏差。
