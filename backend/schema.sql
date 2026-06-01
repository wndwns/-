-- ============================================================================
-- 牧融绿链 - MySQL 数据库 Schema
-- ============================================================================
-- 使用方式:
--   mysql -u root -p < backend/schema.sql
--   mysql -u root -p < backend/seed_data.sql
-- ============================================================================

CREATE DATABASE IF NOT EXISTS yak_green_chain
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE yak_green_chain;

-- ============================================================================
-- 1. 监测区域
-- ============================================================================

CREATE TABLE IF NOT EXISTS regions (
  id          VARCHAR(50)   PRIMARY KEY COMMENT '区域ID，如 naqu-bange',
  name        VARCHAR(100)  NOT NULL COMMENT '区域名称',
  type        VARCHAR(50)   COMMENT '区域类型，如 冬春补饲重点区',
  risk_level  VARCHAR(10)   COMMENT '风险等级：高/中/低',
  suggestion  TEXT          COMMENT '区域建议',
  created_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='监测区域';

-- 区域指标（1:N）
CREATE TABLE IF NOT EXISTS region_metrics (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  region_id    VARCHAR(50)  NOT NULL,
  metric_name  VARCHAR(50)  NOT NULL COMMENT '指标名',
  metric_value VARCHAR(50)  NOT NULL COMMENT '指标值',
  FOREIGN KEY (region_id) REFERENCES regions(id) ON DELETE CASCADE,
  UNIQUE KEY uk_region_metric (region_id, metric_name)
) ENGINE=InnoDB COMMENT='区域指标';

-- ============================================================================
-- 2. 气象监测数据
-- ============================================================================

CREATE TABLE IF NOT EXISTS weather_data (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  region_id           VARCHAR(50)   NOT NULL,
  station             VARCHAR(100)  COMMENT '气象站名称',
  observed_at         DATETIME      COMMENT '观测时间',
  temperature_c       DECIMAL(5,1)  COMMENT '温度(℃)',
  precipitation_mm_24h DECIMAL(5,1) COMMENT '24h降水(mm)',
  wind_speed_mps      DECIMAL(4,1)  COMMENT '风速(m/s)',
  snow_depth_cm       INT           COMMENT '积雪深度(cm)',
  cold_wave_risk      VARCHAR(10)   COMMENT '寒潮风险',
  snowstorm_risk      VARCHAR(10)   COMMENT '暴雪风险',
  drought_risk        VARCHAR(10)   COMMENT '干旱风险',
  data_source         VARCHAR(100)  DEFAULT 'sample' COMMENT '数据来源: sample / api / csv',
  created_at          TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_weather_region (region_id),
  INDEX idx_weather_observed (observed_at)
) ENGINE=InnoDB COMMENT='气象监测数据';

-- ============================================================================
-- 3. 遥感生态指标
-- ============================================================================

CREATE TABLE IF NOT EXISTS remote_sensing_data (
  id                         INT AUTO_INCREMENT PRIMARY KEY,
  region_id                  VARCHAR(50)  NOT NULL,
  scene_date                 DATE         COMMENT '影像日期',
  ndvi                       DECIMAL(4,2) COMMENT 'NDVI值',
  ndvi_change                VARCHAR(10)  COMMENT 'NDVI同比变化',
  vegetation_cover           VARCHAR(10)  COMMENT '植被覆盖度',
  snow_cover                 VARCHAR(10)  COMMENT '积雪覆盖度',
  grassland_type             VARCHAR(50)  COMMENT '草地类型',
  degradation_level          VARCHAR(50)  COMMENT '退化等级',
  carrying_capacity_sheep_unit INT        COMMENT '载畜量(羊单位)',
  data_source                VARCHAR(100) DEFAULT 'sample' COMMENT '数据来源',
  created_at                 TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_remote_region (region_id),
  INDEX idx_remote_date (scene_date)
) ENGINE=InnoDB COMMENT='遥感生态指标';

-- ============================================================================
-- 4. 产业经营主体
-- ============================================================================

CREATE TABLE IF NOT EXISTS business_subjects (
  id                 INT AUTO_INCREMENT PRIMARY KEY,
  name               VARCHAR(100)  NOT NULL COMMENT '主体名称',
  region_id          VARCHAR(50)   COMMENT '所属区域ID',
  region_name        VARCHAR(50)   COMMENT '所属区域名称',
  subject_type       VARCHAR(20)   COMMENT '类型：合作社/联合体/家庭牧场/供应商',
  cattle_count       INT           DEFAULT 0 COMMENT '牦牛存栏(头)',
  sheep_count        INT           DEFAULT 0 COMMENT '藏羊存栏(只)',
  grassland_mu       INT           DEFAULT 0 COMMENT '草场面积(亩)',
  credit_amount      VARCHAR(20)   COMMENT '授信额度(万元)',
  credit_value       DECIMAL(10,2) COMMENT '授信数值',
  score              INT           COMMENT '信用评分',
  insurance_coverage VARCHAR(10)   COMMENT '保险覆盖率',
  status             VARCHAR(20)   COMMENT '状态',
  loan_use           VARCHAR(200)  COMMENT '贷款用途',
  data_source        VARCHAR(100)  DEFAULT 'sample',
  created_at         TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  updated_at         TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_subject_region (region_id),
  INDEX idx_subject_status (status)
) ENGINE=InnoDB COMMENT='产业经营主体';

-- ============================================================================
-- 5. 金融保险数据
-- ============================================================================

-- 授信记录
CREATE TABLE IF NOT EXISTS finance_credit (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  subject_name      VARCHAR(100)  NOT NULL COMMENT '主体名称',
  credit_line       DECIMAL(10,2) COMMENT '授信总额(万元)',
  used_credit       DECIMAL(10,2) COMMENT '已用额度(万元)',
  interest_rate     VARCHAR(10)   COMMENT '利率',
  term_months       INT           COMMENT '贷款期限(月)',
  repayment_status  VARCHAR(20)   COMMENT '还款状态',
  overdue_times     INT           DEFAULT 0 COMMENT '逾期次数',
  data_source       VARCHAR(100)  DEFAULT 'sample',
  created_at        TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_finance_subject (subject_name)
) ENGINE=InnoDB COMMENT='银行授信记录';

-- 保险保单
CREATE TABLE IF NOT EXISTS insurance_policy (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  credit_id    INT           COMMENT '关联授信记录ID',
  subject_name VARCHAR(100)  COMMENT '主体名称',
  policy_type  VARCHAR(50)   COMMENT '险种：牦牛养殖保险/雪灾指数保险/仓储财产保险',
  insured_qty  INT           COMMENT '投保数量',
  coverage     VARCHAR(10)   COMMENT '覆盖率',
  data_source  VARCHAR(100)  DEFAULT 'sample',
  created_at   TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (credit_id) REFERENCES finance_credit(id) ON DELETE CASCADE,
  INDEX idx_policy_subject (subject_name)
) ENGINE=InnoDB COMMENT='保险保单';

-- ============================================================================
-- 6. 预警信息
-- ============================================================================

CREATE TABLE IF NOT EXISTS alerts (
  id          VARCHAR(20)   PRIMARY KEY COMMENT '预警ID',
  alert_level VARCHAR(10)   COMMENT '风险等级',
  title       VARCHAR(200)  COMMENT '预警标题',
  description TEXT          COMMENT '预警描述',
  action      VARCHAR(200)  COMMENT '建议措施',
  alert_time  DATETIME      COMMENT '预警时间',
  is_active   TINYINT(1)    DEFAULT 1 COMMENT '是否活跃',
  created_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_alert_level (alert_level),
  INDEX idx_alert_active (is_active)
) ENGINE=InnoDB COMMENT='预警信息';

-- ============================================================================
-- 7. 评分模型
-- ============================================================================

CREATE TABLE IF NOT EXISTS score_model (
  id      INT AUTO_INCREMENT PRIMARY KEY,
  name    VARCHAR(50)  NOT NULL COMMENT '评分维度',
  weight  INT          NOT NULL COMMENT '权重',
  detail  VARCHAR(200) COMMENT '详情说明'
) ENGINE=InnoDB COMMENT='授信评分模型';

-- ============================================================================
-- 8. 业务模块定义
-- ============================================================================

CREATE TABLE IF NOT EXISTS modules (
  code     VARCHAR(30)  PRIMARY KEY COMMENT '模块编码',
  name     VARCHAR(100) NOT NULL COMMENT '模块名称',
  summary  TEXT         COMMENT '模块简介',
  icon     VARCHAR(30)  COMMENT '图标标识',
  features JSON         COMMENT '功能特性列表',
  sort_order INT        DEFAULT 0
) ENGINE=InnoDB COMMENT='业务模块定义';

-- ============================================================================
-- 9. 数据源配置（预留外部API/URL接入）
-- ============================================================================

CREATE TABLE IF NOT EXISTS data_source_config (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  source_name  VARCHAR(50)  NOT NULL COMMENT '数据源名称',
  source_key   VARCHAR(30)  NOT NULL UNIQUE COMMENT '数据源标识 weather/remote_sensing/business/finance',
  source_type  VARCHAR(30)  DEFAULT 'sample' COMMENT '接入类型: sample / api / csv / mqtt / database',
  status       VARCHAR(50)  DEFAULT '待接入' COMMENT '状态描述',
  source_desc  VARCHAR(200) COMMENT '来源描述',
  api_endpoint VARCHAR(300) COMMENT 'API端点URL（预留）',
  api_key      VARCHAR(200) COMMENT 'API密钥（预留）',
  api_config   JSON         COMMENT '额外API配置（预留）',
  fields       JSON         COMMENT '数据字段列表',
  created_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
  updated_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='数据源配置（预留外部接入）';

-- ============================================================================
-- 10. 平台大纲与品牌配置
-- ============================================================================

CREATE TABLE IF NOT EXISTS platform_config (
  config_key   VARCHAR(50)  PRIMARY KEY,
  config_value JSON         NOT NULL,
  updated_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='平台配置（大纲、品牌等静态内容）';
