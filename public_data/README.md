# 公开数据集合

牧融绿链平台的数据来源说明和样例数据包。

## 数据来源

系统不是凭空制造数据。比赛版基于以下公开数据源的字段体系和区域特征，构造合理、可解释的样例 CSV：

| 数据源 | 用途 | 访问方式 |
|--------|------|----------|
| 国家青藏高原科学数据中心 | 草地退化、积雪、植被、气象 | 注册后申请下载 |
| NASA MODIS MOD13Q1 (NDVI) | 植被指数，16天/250m | Google Earth Engine 免费 |
| NASA MODIS MOD10A1 (Snow) | 积雪覆盖，逐日/500m | Google Earth Engine 免费 |
| 中国气象数据网 | 气象站温度、降水、风速 | 注册后申请 |
| 国家统计局 | 县域畜牧存栏、产值统计 | 公开年鉴 |

详细字段映射和接入方式见 `sources.json`。

## 样例 CSV 文件

`samples/` 目录包含四类可直接上传到系统的 CSV 文件：

| 文件 | 对应表 | 行数 | 说明 |
|------|--------|------|------|
| weather_data_public_sample.csv | weather_data | 9 | 3 区域 × 3 时段气象数据 |
| remote_sensing_public_sample.csv | remote_sensing_data | 12 | 3 区域 × 4 时段遥感数据 |
| business_subjects_demo.csv | business_subjects | 8 | 8 个典型经营主体 |
| finance_credit_demo.csv | finance_credit | 8 | 8 条金融授信记录 |
| business_subjects_risk_demo.csv | business_subjects | 10 | 风控终端主体画像样例 |
| finance_credit_risk_demo.csv | finance_credit | 10 | 风控终端授信/用信/逾期样例 |
| risk_event_labels_demo.csv | risk_event_labels | 8 | 灾害、理赔、逾期事件标签样例 |
| remote_sensing_capacity_demo.csv | remote_sensing_data | 10 | 退化等级、载畜量、积雪补充样例 |

`*_demo.csv` 均为演示样本，用于跑通完整系统链路，不代表真实生产数据。

## 完整作品演示建议导入顺序

1. `business_subjects_risk_demo.csv` → `business_subjects`，模式选 `replace`
2. `finance_credit_risk_demo.csv` → `finance_credit`，模式选 `replace`
3. `risk_event_labels_demo.csv` → `risk_event_labels`，模式选 `replace`
4. `remote_sensing_capacity_demo.csv` → `remote_sensing_data`，如果已经导入多年 MODIS/CMFD 数据，模式选 `append`
5. 回到前台运营台，点击 `重训模型`

## 使用方法

### 生成样例 CSV

```powershell
cd D:\工行杯\yak-risk-platform
python public_data/scripts/build_public_samples.py
```

### 上传到系统

1. 启动服务器：`python .\backend\server.py`
2. 打开管理端：`http://127.0.0.1:8000/admin`
3. 在"公开样例数据包"区域下载 CSV
4. 在"CSV 数据导入"区域选择对应表 → 上传 CSV → 确认导入
5. 前台刷新即可看到更新后的数据

### 后续接入真实数据

1. 注册数据源账号（见 `sources.json` 各源 `requires_registration` 字段）
2. 下载真实数据集（NetCDF / GeoTIFF / CSV）
3. 在 `scripts/` 下新增清洗脚本，将原始数据处理为系统 CSV 格式
4. 通过管理端上传或直接替换 `backend/data_store/*.json`

## 数据使用原则

- 公开数据源的字段体系和区域划分是真实的，样例数值是合理的模拟值
- 金融和保险数据为脱敏模拟数据，不涉及真实隐私
- 比赛演示版的目标是展示"数据闭环"，而非声称已接入实时生产数据
