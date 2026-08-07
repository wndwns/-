# 工银牧融

工行高原畜牧绿色金融风险评估与贷后管理平台。

面向高原牧区，围绕气象遥感监测、经营主体台账、工行授信准入、贷后预警、保险协同和绿色金融绩效建设。

## 目录结构

```text
backend/
  server.py              FastAPI 后端服务 + 全量 API
  data.py                数据访问层（JSON Store > MySQL > 内置样例）
  models.py              模型层（规则 + sklearn 混合预测）
  store.py               JSON 文件存储层（backend/data_store/*.json）
  db.py                  MySQL 连接池（可选）
  credit_decision.py     授信与贷后唯一金额纯计算模块
  test_credit_decision.py  授信测算黄金样例与边界回归检查
  schema.sql / seed_data.sql   MySQL 建表 + 种子数据（可选）
frontend/
  index.html             前台 SPA 主页（默认进入授信与贷后工作台）
  app.js                 前台 Vue 3 + ECharts 应用逻辑
  styles.css             前台样式
  admin.html             管理端独立页面
  styles-admin.css       管理端样式
public_data/
  README.md              公开数据来源说明
  sources.json           5 个公开数据源详细清单
  samples/               可导入系统的样例 CSV（4 类）
  scripts/               CSV 生成/清洗脚本
```

## 启动方式

```powershell
cd D:\工行杯\yak-risk-platform
python -m pip install -r requirements.txt
python .\backend\server.py
```

- 前台主页：http://127.0.0.1:8000（默认进入授信与贷后工作台）
- 管理端：http://127.0.0.1:8000/admin
- API 文档：http://127.0.0.1:8000/docs

## 授信与贷后测算接口

前端“授信与贷后工作台”通过以下接口完成主体选择与唯一金额测算：

```text
GET  /api/credit-cases                        案例列表（主案例 + 百巴村控制案例）
POST /api/credit-decision/evaluate            唯一授信测算
```

- `feasible / infeasible / blocked` 均返回 HTTP 200，业务状态在响应 `status` 字段。
- 输入分组或字段非法返回 422。
- 案例文件缺失、为空或损坏返回 500（`credit_case_unavailable`），不回退到伪造结果。
- 测算逻辑集中在 `backend/credit_decision.py`，金额以元计算、仅最后向下取整到 1 万元；
  保险、RF/Ridge、四维综合分与旧风险乘数不进入金额主链。
- 案例数据为比赛样例（`backend/data_store/credit_cases.json`），不是真实工行客户资料。

## 外部天气与地图 API

系统已经预留高德地图、高德天气和 Open-Meteo 开放天气接入，不在代码里写死 Key。你可以在管理端 `外部 API 配置` 区填写，也可以写入 `.env`。配置优先级为：管理端保存的 `backend/content-store.json` 非空值优先；为空时读取 `.env` 环境变量。

| 能力 | 申请位置 | 本地配置 |
|------|----------|----------|
| 高德天气 Web服务 | https://lbs.amap.com/api/webservice/guide/api/weatherinfo | `AMAP_WEB_SERVICE_KEY` |
| 高德地图 JS API 2.0 | https://lbs.amap.com/api/javascript-api-v2/guide/abc/load | `AMAP_JS_API_KEY`、`AMAP_SECURITY_JS_CODE` |
| Open-Meteo 开放天气 | https://open-meteo.com/en/docs | `OPEN_METEO_ENDPOINT`，无需 Key |

相关接口：

```text
GET /api/integrations/status
GET /api/integrations/amap/weather?city=那曲市
GET /api/integrations/amap/map-config
GET /api/integrations/open-meteo/now?latitude=31.36&longitude=90.01
```

## 数据存储模式

**默认模式（无需 MySQL）**：数据写入 `backend/data_store/*.json`，启动时自动生成样例数据。

**可选 MySQL 模式**：
```powershell
$env:MYSQL_HOST="127.0.0.1"
$env:MYSQL_PORT="3306"
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="yourpassword"
$env:MYSQL_DATABASE="yak_green_chain"
python .\backend\server.py
```

## 数据闭环

```
管理端 /admin
  └─ 上传 CSV → 前端预览 → 确认导入
       ↓ POST /api/import/csv
后端 server.py
  └─ store.import_csv_to_table() → 写入 JSON 文件
       ↓
data.py 数据层
  └─ get_xxx() 读取最新数据 → get_risk_assessment() 动态重算
       ↓                              ↓
前端 SPA                          models.py 模型层
  └─ /api/platform                   └─ 特征提取 → 训练 → 预测 → 特征重要性
```

## 模型层

### 架构

- 模型代码：`backend/models.py`
- 策略：样本 < 20 条 → 规则加权模型；样本 ≥ 20 条 → sklearn RandomForest + Ridge 混合
- 特征：16 维（气象 7 + 遥感 6 + 经营 2 + 金融 1）
- 集成方式：模型预测通过 `/api/model/predict` 输出，同时注入 `/api/risk-assessment` 和 `/api/platform`

### 模型 API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/model/status` | GET | 训练状态、样本数、特征数、置信度、模型类型 |
| `/api/model/train` | POST | 基于最新 store 数据重新训练 |
| `/api/model/predict` | POST | 所有区域预测结果 + 各维度贡献分解 |
| `/api/model/importance` | GET | 16 维特征重要性排序 |
| `/api/model/forecast?region_id=&days=` | GET | 未来 N 天风险趋势预测 + 置信区间 |

### 预测输出字段

每个区域的预测结果包含：
- `predicted_score` — 预测风险评分 (0-100)
- `predicted_level` — 预测风险等级 (高/中/低)
- `drivers` — 四维贡献分解（气象/遥感/经营/金融各自得分和详情）
- `feature_vector` — 16 维特征向量（可追溯）

### 训练数据规模说明

- 当前真实数据：CMFD 气象 300 行 + MODIS NDVI 300 行 = 600 行真实数据
- 25 县 × 25 月 = 300+ 训练样本，模型类型 `ml_hybrid`
- 样本数 >= 300，置信度较高
- 模型明确标注数据来源 (`data_source_counts`)：tpdc=300, modis=300, sample=8

## 遥感数据接入

### 当前状态

| 数据表 | 数据来源 | 行数 | is_sample | 状态 |
|--------|----------|------|-----------|------|
| weather_data | CMFD 2.0 (TPDC) | 300 | false | 真实气象（待扩展多年）|
| remote_sensing_data | MODIS NDVI + Snow | 300 | false | NDVI+积雪（待扩展多年）|
| business_subjects | 脱敏模拟 | 4 | true | sample |
| finance_credit | 脱敏模拟 | 4 | true | sample |

### 当前数据缺口

| 缺口 | 说明 |
|------|------|
| 真实 NDVI | 现有 remote_sensing_data 为 sample，待 GEE 导出真实 MODIS NDVI |
| 真实 snow_cover | 已接入 GEE MODIS MOD10A1（通过 ingest_public_data.py 合并） |
| 真实 FVC | 未接入 GLASS FVC 或 MOD44B 植被覆盖度 |
| 真实 degradation_level | 接入口已就绪（--remote-degradation），待 TPDC 下载草地退化数据 |
| 真实 carrying_capacity | 接入口已就绪（--remote-capacity），待 TPDC 下载草地生产力数据 |
| 真实金融保险 | 仍为脱敏模拟数据 |

### NDVI 接入（GEE 导出真实数据）

**步骤 1**: 打开 https://code.earthengine.google.com/，粘贴 `public_data/scripts/gee_export_ndvi_template.js`，点击 Run

**步骤 2**: 在右侧 Tasks 标签页点击 Run 执行导出，任务完成后从 Google Drive 下载 CSV

**步骤 3**: 放到 `public_data/raw/modis/ndvi/ndvi_modis_real_2024.csv`

**步骤 4**: 运行转换（注意 `--mark-real`）：

```powershell
python public_data/scripts/ingest_public_data.py --source modis --dataset ndvi \
    --remote-ndvi public_data/raw/modis/ndvi/ndvi_modis_real_2024.csv \
    --start-year 2024 --end-year 2024 \
    --mark-real --remote-source-id modis-ndvi-mod13q1 --dataset-name MODIS_MOD13Q1_NDVI \
    --output public_data/processed/remote_sensing_modis_ndvi_2024.csv
```

**步骤 5**: 上传并训练：

```powershell
curl -X POST http://127.0.0.1:8000/api/import/csv \
    -F "file=@public_data/processed/remote_sensing_modis_ndvi_2024.csv" \
    -F "table=remote_sensing_data" -F "mode=replace"
curl -X POST http://127.0.0.1:8000/api/model/train
```

## 积雪数据接入

### GEE 导出 MODIS Snow Cover

**步骤 1**: 打开 https://code.earthengine.google.com/，粘贴 `public_data/scripts/gee_export_snow_template.js`，点击 Run

**步骤 2**: Tasks → Run 执行导出，从 Google Drive 下载 CSV

**步骤 3**: 放到 `public_data/raw/modis/snow/snow_modis_real_2024.csv`

**步骤 4**: 合并 NDVI + snow：

```powershell
python public_data/scripts/ingest_public_data.py --source modis --dataset ndvi \
    --remote-ndvi public_data/raw/modis/ndvi/ndvi_modis_real_2024.csv \
    --remote-snow public_data/raw/modis/snow/snow_modis_real_2024.csv \
    --start-year 2024 --end-year 2024 --mark-real \
    --remote-source-id modis-ndvi-snow-2024 \
    --dataset-name MODIS_MOD13Q1_MOD10A1_2024 \
    --output public_data/processed/remote_sensing_modis_ndvi_snow_2024.csv
```

**步骤 5**: 上传并训练：

```powershell
curl -X POST http://127.0.0.1:8000/api/import/csv \
    -F "file=@public_data/processed/remote_sensing_modis_ndvi_snow_2024.csv" \
    -F "table=remote_sensing_data" -F "mode=replace"
curl -X POST http://127.0.0.1:8000/api/model/train
```

## 草地退化与载畜量数据接入

### 用户需要从 TPDC 下载

1. **青藏高原草地退化等级数据集** — 搜索"青藏高原草地退化" → 下载到 `public_data/raw/tpdc/degradation/`
2. **青藏高原草地类型图** — 搜索"青藏高原草地类型" → 下载到 `public_data/raw/tpdc/`
3. **青藏高原 NPP / 植被生产力** — 搜索"青藏高原 NPP"或"植被净初级生产力" → 下载到 `public_data/raw/tpdc/carrying_capacity/`
4. **草地生产力 / 载畜量** — 搜索"载畜量"或"草畜平衡" → 下载到 `public_data/raw/tpdc/carrying_capacity/`

### degradation CSV 字段要求

```csv
region_id, degradation_level
naqu-bange, 中度退化
changdu-luolong, 轻度退化
rikaze-xietongmen, 基本稳定
```

允许值: `基本稳定`, `轻度退化`, `中度退化`, `重度退化`

### carrying_capacity CSV 字段要求

```csv
region_id, carrying_capacity_sheep_unit
naqu-bange, 18000
changdu-luolong, 23600
```

或通过 NPP 估算（标记 derived）:

```csv
region_id, npp
naqu-bange, 350.5
```

### 合并完整遥感 CSV

```powershell
python public_data/scripts/ingest_public_data.py --source tpdc --dataset remote_merge `
    --remote-ndvi public_data/raw/modis/ndvi/ndvi_modis_real_2020_2024.csv `
    --remote-snow public_data/raw/modis/snow/snow_modis_real_2020_2024.csv `
    --remote-degradation public_data/raw/tpdc/degradation/degradation_static.csv `
    --remote-capacity public_data/raw/tpdc/carrying_capacity/capacity_static.csv `
    --start-year 2020 --end-year 2024 --mark-real `
    --remote-source-id modis-tpdc-remote-2020-2024 `
    --dataset-name MODIS_TPDC_REMOTE_2020_2024 `
    --output public_data/processed/remote_sensing_full_2020_2024.csv
```

### 临时样例载畜量数据说明

当前载畜量使用样例文件 `public_data/samples/carrying_capacity_npp_sample.csv`：
- 数据来源: demo/sample, 不是真实 TPDC 数据
- 载畜量由 NPP 衍生估算, 标记 `capacity_is_sample=true, capacity_derived=true`
- 仅用于跑通导入→训练→评估流程, 不应宣称已接入真实载畜量
- 主表 `is_sample=false`（NDVI/Snow/Degradation 真实），但载畜量字段携带独立来源标记
- 真实 TPDC NPP 数据审批通过后替换此文件, 重新运行 merge 命令并重新训练模型

## 宏观参考数据

### 全国饲草供需 (Geodoi)

已接入公开数据集：Yearly Dataset on Forage Production and Demand in China (2000-2020)
DOI: 10.3974/geodb.2024.07.07.V1

- 数据表: `forage_supply_demand` (126 行, 6 大区域 × 21 年)
- API: `GET /api/forage-supply-demand` / `GET /api/forage-supply-demand/summary`
- 不是县域载畜量，不参与模型训练，仅作为宏观背景参考
- 与 remote_sensing_data.carrying_capacity_sheep_unit 没有直接映射关系

### 风险事件标签表

已设计 `risk_event_labels` 表结构（字段: region_id, event_month, event_type, severity, loss_amount, claim_amount, overdue_flag, is_real_label），但当前为空。不伪造标签。

## 模型标签说明

当前模型是**"真实环境数据 + 规则风险标签"的弱监督评分模型**：
- `GET /api/model/label-info` 返回标签类型说明
- `GET /api/model/macro-background` 返回宏观背景数据状态
- `label_type=rule_label`, 无真实灾害/理赔/逾期标签
- 标签来源: 规则风险分（气象+遥感+经营+金融加权），不是真实灾害/损失/逾期标签
- `label_type=rule_label`
- `GET /api/model/label-info` 返回标签详细说明
- 不应宣称已经完成真实灾害预测或贷款逾期预测

### 样例 vs 真实数据的区别

- 文件名含 `sample/demo/mock` 的输入自动标记为 `is_sample=true`，不会被当成真实数据
- 只有加 `--mark-real` 且输入文件不含 sample/demo/mock 关键词，才会输出 `is_sample=false`
- 当前 `remote_sensing_sample_2024.csv` 是链路验证样例，不表示真实遥感数据

详细下载清单见 `public_data/download_manifest.json`。

## 公开数据集合

### 数据来源

| 数据源 | 用途 | 访问方式 |
|--------|------|----------|
| 国家青藏高原科学数据中心 | 草地退化、积雪、植被、气候 | 注册后申请下载 |
| NASA MODIS MOD13Q1 (NDVI) | 植被指数，16天/250m | Google Earth Engine 免费 |
| NASA MODIS MOD10A1 (Snow) | 积雪覆盖，逐日/500m | Google Earth Engine 免费 |
| 中国气象数据网 | 气象站温度、降水、风速 | 注册后申请 |
| 国家统计局 | 县域畜牧存栏、产值统计 | 公开年鉴 |

详细字段映射见 `public_data/sources.json`。

### 生成和上传样例数据

```powershell
python public_data/scripts/build_public_samples.py
```

然后打开 `http://127.0.0.1:8000/admin`，在"公开样例数据包"下载 CSV → "CSV 数据导入"上传。

### 样例数据 vs 真实数据

- **样例数据**：基于公开数据源字段体系构造的合理模拟值，供演示和开发
- **真实数据**：需注册对应数据源、下载后通过管理端导入或替换 `backend/data_store/*.json`
- 系统中所有样例数据均标记 `data_source: "sample"` 或 `"csv"`
- 风险评估中的模型置信度会随数据量增加而提升

## 四类 CSV 导入

管理端为每类数据提供 CSV 模板下载按钮。

### 1. 气象监测 (weather_data)
`region_id, station, observed_at, temperature_c, precipitation_mm_24h, wind_speed_mps, snow_depth_cm, cold_wave_risk, snowstorm_risk, drought_risk`

### 2. 遥感生态 (remote_sensing_data)
`region_id, scene_date, ndvi, ndvi_change, vegetation_cover, snow_cover, grassland_type, degradation_level, carrying_capacity_sheep_unit`

### 3. 经营主体 (business_subjects)
`name, region_id, region_name, subject_type, cattle_count, sheep_count, grassland_mu, credit_amount, credit_value, score, insurance_coverage, status, loan_use`

### 4. 金融保险 (finance_credit)
`subject_name, credit_line, used_credit, interest_rate, term_months, repayment_status, overdue_times`

## 主要 API

```text
# 平台数据
GET  /api/platform             平台全量数据（含模型输出）
GET  /api/risk-assessment      综合风险评估（规则 + 模型混合）

# 模型
GET  /api/model/status         训练状态
POST /api/model/train          重新训练
POST /api/model/predict        预测所有区域
GET  /api/model/importance     特征重要性
GET  /api/model/forecast       趋势预测

# 公开数据
GET  /api/public-data/sources  数据源清单
GET  /api/public-data/samples  样例 CSV 列表

# 数据管理
GET  /api/store/status         存储状态
POST /api/import/csv           导入 CSV
```

## 推荐数据规模

| 级别 | 县域数 | 月数 | 样本量 | 模型能力 |
|------|--------|------|--------|----------|
| 最低 | 10 | 24 | 240 | 基础 ML，低置信度 |
| 推荐 | 25 | 36 | 900 | 较稳定 ML 训练和评估 |
| 更强 | 40+ | 36-60 | 1440+ | 稳定 ML，可靠评估 |

当前系统内置 25 个高原牧区示范县（`public_data/region_list.csv`）。

## 真实数据接入流程 (TPDC)

1. 登录 [国家青藏高原科学数据中心](https://data.tpdc.ac.cn/)，搜索 NDVI/积雪/气象数据集
2. 下载到 `public_data/raw/tpdc/`
3. 运行转换脚本：
   ```powershell
   python public_data/scripts/ingest_public_data.py --source tpdc --dataset ndvi --input public_data/raw/tpdc/xxx.csv --output public_data/processed/remote_sensing.csv --table remote_sensing_data
   ```
4. 在管理端 `http://127.0.0.1:8000/admin` 上传 `public_data/processed/*.csv`
5. 在前台风险评估工作台点击"重新训练模型"
6. 访问 `/api/model/evaluation` 查看 MAE/RMSE/R2

## 用户需要下载的数据

- NDVI 植被指数产品（如 MOD13Q1，16天/250m）
- 积雪覆盖 / 雪深数据（如 MOD10A1，逐日/500m）
- 气象数据：温度、降水、风速（中国气象数据网或 TPDC 气象数据集）
- 高原畜牧/县域统计数据：存栏、草地面积、产值等（统计年鉴）

## 数据来源标注

系统区分三种数据类型：
- **sample** — 样例数据，仅用于演示字段结构
- **simulated** — 脱敏模拟数据，基于真实参数生成但不涉及真实隐私（金融和保险明细）
- **real / tpdc / modis / cma** — 从公开数据源导入的真实数据

当前不能声称已经接入实时生产数据。金融和保险明细没有公开真实数据，比赛版只能使用脱敏模拟数据。

## 当前状态

- 比赛演示版，内置 25 个高原牧区示范县 + 3 县样例数据
- JSON 文件存储模式可用，无需 MySQL
- CSV 导入闭环已打通
- 模型层：region_id+month 训练样本，规则 + sklearn 混合
- 真实气象 API / 遥感 API 尚未接入
- 前端使用 Vue 3 CDN + ECharts，无需构建工具
