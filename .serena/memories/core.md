# 项目地图

- 工银牧融：青藏高原牧区的绿色金融、畜牧保险、生态遥感风险评估与贷后管理演示平台。
- 运行主线：`backend/server.py` 提供 FastAPI API 并静态服务 `frontend/`；入口 URL 为 `/`，管理端为 `/admin`。
- 数据默认使用 `backend/data_store/*.json`，由 `backend/store.py` 读写；MySQL 是可选后端，封装在 `backend/db.py`。
- 数据访问集中在 `backend/data.py`，风险模型集中在 `backend/models.py`；修改数据或模型时优先追踪这两个边界。
- 当前维护的前端是 `frontend/`。 `frontend_v2/`、`frontend_v3/` 是不再同步维护的历史试验版；`demo/` 是独立演示页。
- 主要业务扩展模块：`early_warning.py`（预警）、`carrying_capacity.py`（载畜量）、`feed_calculator.py`（饲料需求）、`spatio_temporal_grid.py`（时空网格）、`cooperative_ranking.py`（合作社）、`insurance_portfolio.py`（保单画像）。
- 区域及公共数据、导入和提取脚本在 `public_data/`；项目介绍强调所有衍生数据必须保留 `is_derived`、来源和警告标识。
- 进一步的技术、命令和约定见 `mem:tech_stack`、`mem:suggested_commands`、`mem:conventions`、`mem:task_completion`.

## 2026-08-11 现状（Serena 接入后补记）

- 数据基线：训练网格 `real_labels_1500.json` 107 条带来源事件 / 1393 未确认；风险库 `risk_event_labels.json` 198 条（173 real + 25 demo）；历史集 10 条；重复键已清零。
- 授信主链：`credit_decision.py` 已实施（黄金案例建议金额 900000 元、DSCR 1.2416、infeasible/blocked 语义）。
- Open-Meteo 默认直连、失败回退代理；灾害预测在实时预报不可用时降级为历史同期数据。
- 本地服务：`python backend/server.py`（默认 8000；沙箱演示实例 8001）。

## 2026-08-13 更新

- 高德 API Key 已配置生效（Web 服务 + JS 地图，.env 中 AMAP_WEB_SERVICE_KEY / AMAP_JS_API_KEY）。
- 草地退化图集（TPDC，2010-2019 NDVI 变化趋势率，草甸分级）已接入：remote_sensing_data.json 全部 2392 行的 degradation_level 按 26 县更新（基本稳定 2024 / 轻度退化 368 / 重度退化 92-巴宜），新增字段 degradation_ndvi_trend_2010_2019、degradation_source、degradation_derived；模型已重训（3262 样本，16 特征），测试 28 passed。原始文件在 _data_collection/degradation_atlas/。
- CMFD 2.0 月度气象（8 变量，1951-2024）正在后台下载（_data_collection/cmfd2/，8 路并行断点续传），下完提取 26 县 2020-2024 月度要素重建 weather_data。

## 2026-08-13 CMFD 2.0 天气接入

- weather_data.json 重建为 3120 行（26 县 × 2015-2024 共 120 个月，全部 data_source=tpdc / CMFD V0200）；补齐 300 个缺失月份、替换 72 个 Open-Meteo 补丁行；新增行 snow_depth 与三个风险标签为同县同月邻近年份季节复制（risk_snow_fill=seasonal_copy）。
- 模型已重训：n_samples 3262→3562，month_count 137，real_rows 5512；测试 28 passed；README/全景/项目书气象行数已同步为 3120。
- 原始 8 个 CMFD 月度 NetCDF（约 8GB）在 _data_collection/cmfd2/，转换完成后可删除。

## 2026-08-13 免费官方渠道扩充（26 县 2020-2022）
- 候选 20 条全部来自免费官方源（青海/四川/甘肃/西藏气象局、应急局、地震局、县政府），已开页核验；合入 risk_event_labels 198→218，real_labels 来源事件 107→127、未确认 1393→1373。
- 4 条月份模糊（称多 2021-01 风灾、刚察 2022-06 雷击、玛沁 2022-09 连阴雨、称多 2022-09 连阴雨）已入库并标记 month_source=fuzzy，不参与严格月份匹配验证。
- 测试 28 passed；README/全景/项目书/app.js 计数已同步；模型已通过 8001 POST /api/model/train 重训。
- 候选表与脚本：_data_collection/candidates_official_20260813.json、merge_official_20260813.py、sync_counts_20260813.py；备份在 _data_collection/backups/。

## 2026-08-13 XGBoost 对比（未替换生产模型）
- XGB vs 当前 RF+Ridge：时间前向 MAE 2.641 vs 6.124（R² 0.43 vs -0.51）；跨县 GroupKFold MAE 2.40±0.12 vs 3.82±0.34；XGB 全面占优且方差更小。
- SHAP 统一口径（贡献份额%）：两模型都看重温度/降水/NDVI；XGB 温度 23.05%，RF 分布更平均；修复 XGB pred_contribs 维度切片 bug。
- 结果在 _data_collection/model_compare_xgb/；生产模型仍为 RF+Ridge，是否替换待用户决策。

## 2026-08-13 XGB 调参实验（补充，127 事件数据）
- 两阶段调参（阶段1 学习率×深度 lr∈{0.03,0.05,0.1,0.2}；阶段2 结构参数），时间序 3 折内层 CV + 早停 60 轮，选参后全量重训。
- 结论：默认 XGB（depth6/lr0.1/100棵）时间前向 MAE 2.459、跨县 2.367±0.143，均优于调参 XGB（3.580 / 2.677±0.673）；两者都优于当前 RF+Ridge（6.022 / 3.891±0.365）。
- 调参负收益原因：验证集（2022 下半年）上 lr=0.03 验证 MAE 最低但轮数多、样本外泛化差；小数据+弱标签下默认配置本身就是正则化。
- 生产建议：换 XGB 用默认档即可；脚本与报告在 _data_collection/model_compare_xgb/compare_xgb_tuned.py、compare_tuned_report.md。

## 2026-08-13 生产模型切换 XGBoost
- models.py 默认引擎改为 XGBoost（depth6/lr0.1/100棵，XGBClassifier+XGBRegressor），无 xgboost 时回退 RF+Ridge；status 新增 ml_engine / xgboost_available。
- 修复：模型评估改用临时副本，不再把生产模型覆盖成 80% 训练；XGB 解释用 booster pred_contribs。
- 测试 28 passed；8001 服务已用 _data_collection venv Python 重启（系统 Python310 缺 uvicorn），status.ml_engine=xgboost。
- requirements.txt 已加 xgboost>=2.0.0；README/全景/项目书已同步为 XGBoost 口径。

## 2026-08-15 前端裁剪（走本地 Serena MCP 流程）
- 首页砍 3 区块：工行业务闭环（4 预警卡，dashboard 已有实时预警）、工行风控能力（7 卡，与 modules 页重复）、工行主体角色（5 痛点卡，项目书内容）；保留 Hero → 工行角色时间线(4步) → 工行数据底账 → 平台核心能力一图概览 → Footer。
- 导航 13 → 9 项：删除 overview/modules/module-detail/roadmap 四个 SPA 页面（v-show 区块 + pageTitle + hash 白名单 + navigate 分支 + 引用全部清理）；民生移出主导航，入口改为保险页头部按钮；合作社排序移入核心业务组；组名改为 核心业务/数据与证据/平台。
- module-detail 因失去入口一并删除；renderOverviewChartsSoon 等守卫函数保留（page!==overview 直接 return）。
- 验证：无残留引用、导航目标完整、node --check 通过、8001 线上页面确认；备份在 _data_collection/backups/frontend_trim_20260815_*。

## 2026-08-15 首屏加载优化（缓存 + gzip）
- 根因：get_active_platform 每次请求调用 build_platform_data 3~4 遍（含 XGB 全量预测 3562 行 + 数据聚合），/api/platform 实测 12.7s。
- 修复：data.py 的 build_platform_data 加内存缓存（键 = data_store 文件最新 mtime + 模型 trained_at，重训/合入数据自动失效）；server.py 加 GZipMiddleware（3.3MB→11KB）并按 trained_at 缓存 /api/model/predict。
- 前端 app.js init 不再 await loadModelData，首页先渲染、模型数据后台加载。
- 实测：/api/platform 12.7s → 20~64ms；/api/model/predict 2.95s → 缓存后约 37ms（首调 ~1.9s 构建）；gzip 均生效。
- 测试 28 passed；8001 已重启生效。

## 2026-08-15 年鉴纸质凭证合入

- 5 条年鉴候选按 `(region_id, month)` 与现有来源事件去重，4 条重复、1 条净新增：`yushu-zaduo / 2021-06 / lightning`，来源《中国气象灾害年鉴2022 第173页》，杂多县结多乡巴麻村一社牧民采挖虫草遭雷击，2 人死亡，`loss_amount=0`，高风险分 80。
- 已在 `backend/models.py` 顶层增加 `_is_source_event(rl)`：有 `source_url`，或 `source_kind == "yearbook"` 且 `verified is True`。`train()` 的 real_map、`label_info()` 的 real_count、`event_similarity_topk()` 的 events 三处统一使用该判定；相关文案改为支持公开 URL 或年鉴页码凭证。
- 已合入 `real_labels_1500.json` 对应 2021-06 县月（label=1、risk_score=80、severity=高、event_type=lightning、loss_amount=0、source_kind=yearbook、verified=true 等字段），并新增同字段事件到 `risk_event_labels.json`（总条目 219）。2022 年缺页码事件未处理。
- 来源事件计数由 127/1373 更新为 128/1372。`backend/test_truthful_outputs.py` 已同步断言；README、`项目全景说明（Codex读）.md`、`工银牧融项目书（用户阅读版）.md`、`frontend/app.js` 已同步本次计数与凭证口径。
- 使用指定 `_data_collection/.venv` 执行 `pytest backend -q`：28 passed；8083 服务重启后 POST `/api/model/train` 成功，GET `/api/model/label-info` 返回 `real_disaster_label_count=128`、`unknown_month_count=1372`。

