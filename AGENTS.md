# AGENTS.md — 工银牧融

> 本文件是 AI 与协作者的**入口速查**。项目唯一权威现状档案是 `项目全景说明（Codex读）.md`（51KB），改代码前必读。
> 本文件随项目状态**实时更新**，更新规则见文末。

## 1. 项目身份

- 参赛名：**工银牧融**；前端品牌名：**牧融绿链**。
- 定位：工行高原畜牧绿色金融风险评估与贷后管理平台。
- 服务对象：工行（不是政府）。
- 当前阶段：**银行版一期已落地**（2026-09-23，`8a0bedf`：活体抵押上限 / 两级 bottleneck / 银行版控制台 `/bank` / 25 项回归测试 + 8 个 `/api/bank/*` 路由），**二期（资产侧）未开始**。
- 文档入口：方案稿 `银行视角改造方案探讨_20260923.md`（六步探讨全文 + §19.7 分期）；一期实施记录见本文件第 10 节；答辩排练看 `答辩演示脚本_银行版_20260923.md`。

## 2. 开工流程（每次接手都走一遍）

1. Serena 激活项目 → `C:\Users\WH\Desktop\项目\gonghangbei - 副本`
   （桌面已重定向，Serena 实际解析到 `D:\DesktopData\项目\gonghangbei - 副本`，属正常）

   **本机走「本地 HTTP 端口」模式**（用户指定，不经 WorkBuddy 的 MCP 层）：
   ```bash
   cd <项目目录> && env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
     "C:/Users/WH/.local/bin/serena.exe" start-mcp-server \
     --transport streamable-http --host 127.0.0.1 --port 24282 \
     --project "<项目绝对路径>" --context=codex \
     --enable-web-dashboard False --open-web-dashboard False
   ```
   客户端：`_原型/serena_http.py`（零依赖）
   ```bash
   python _原型/serena_http.py list
   python _原型/serena_http.py call get_symbols_overview '{"relative_path":"backend/credit_decision.py"}'
   python _原型/serena_http.py call find_symbol '{"name_path_pattern":"evaluate_credit_case","relative_path":"backend/credit_decision.py","include_body":true}'
   ```
   > 前提（2026-09-23 已配好）：`.serena/project.local.yml` 的 `ls_specific_settings.python.ls_path`
   > 指向 `~/.local/bin/pyright-langserver.exe`；且 `~/.serena/serena_config.yml` 的
   > `trusted_project_path_patterns` 必须包含本项目路径（**项目不被信任时，项目级 LS 设置会被整段跳过**）。
   > 排障见 `~/.workbuddy/env-pitfalls.md` 第 16 节。
2. 读 Serena 记忆：`mem:core`、`mem:tech_stack`、`mem:conventions`、`mem:suggested_commands`、`mem:task_completion`
3. 读 `项目全景说明（Codex读）.md`
4. `git status` + 当前分支 + 最近提交
5. 读本文件 + 当前方案稿

## 3. 代码改动规则

- 改代码走 Serena MCP（`find_symbol` / `replace_symbol_body` / `replace_in_files` 等）。
- 改动前查连锁引用（`find_referencing_symbols`），四条关键边界：
  | 文件 | 角色 |
  |---|---|
  | `backend/server.py` | FastAPI 应用、84 路由、静态服务 |
  | `backend/data.py` | 数据访问与聚合、四维风险、平台输出 |
  | `backend/store.py` | JSON 持久化边界 |
  | `backend/models.py` | 16 维特征、XGBoost 风险模型 |
  | `backend/credit_decision.py` | 唯一授信金额主链 |
  | `frontend/app.js` | 单一 Vue 应用，159KB |
- 双导入路径（`python backend/server.py` 与模块方式）保持兼容。
- 前端主线只改 `frontend/`；`frontend_v2/`、`frontend_v3/` 是历史试验版，不同步。

## 4. 最低验证（每次改完）

```powershell
python -m compileall backend
python backend/test_truthful_outputs.py
node --check frontend/app.js
git diff --check
```

涉及授信金额时另跑 `backend/test_credit_decision.py`、`backend/test_credit_decision_extended.py`。
改动 Python 后用 Serena `get_diagnostics_for_file` 过一遍改动文件。
改动 API 或页面时启动服务检查 `/api/health`、`/api/platform`、`/api/model/status`。

## 5. 数据事实边界（陈述）

- 数据分级：公开观测 / 派生 / 来源支持事件 / 样例 / 待核验登记 / 历史实验。
- 样例数据在页面与文档中标注 `data_source=sample`。
- 派生数据保留 `is_derived=true` 与推导说明。
- 来源事件：**128 条**有公开 URL 或年鉴页码凭证；其余 **1372** 个月份状态为「未确认」，不等同无灾。
- 资产/耳标登记（百巴村 21 户 / 1135 头）：可陈述为登记关系；保险合同、责任范围、保额、理赔均未核验。
- 训练标签为**规则弱标签**，模型定位是核查优先级排序，不产出违约概率。
- `backtest_report.json` 为历史无效材料，`GET /api/model/backtest` 已强制 `overall_pass=false`、`report_status=not_valid_for_business_decision`。
- 个人敏感字段（姓名、电话、地址、耳标明细）不进入接口输出。
- 来源未核验的记录不参与单户风险分与额度建议。

## 6. 运行

- 入口：`backend/server.py`（FastAPI，同时静态服务 `frontend/`）；前台 `/`，管理端 `/admin`。
- 本地启动：`python backend/server.py`，默认端口 8000，`PORT` 环境变量可覆盖。
- 数据默认 `backend/data_store/*.json`，MySQL 为可选后端。
- 外部集成：Open-Meteo、高德；配置参考 `.env.example`，真实 `.env` 不入库。

## 7. 文档同步规则

| 改动内容 | 需同步文件 |
|---|---|
| 主流程 / 数据规模 / 额度规则 / 事实边界 | `项目全景说明（Codex读）.md` + 本文件 |
| 改造方向决策（D 系列） | `银行视角改造方案探讨_20260923.md` + 本文件第 8 节 |
| 页面结构 / 接口清单 | `README.md` |
| 授信口径 / 答辩表述 | `答辩口径.md` |

## 8. 当前状态（滚动更新）

### 已定决策

| # | 议题 | 结论 | 日期 |
|---|---|---|---|
| D1 | 外部数据来源 | 银政合作 / 数据专线为主；客户授权上传为补充 | 2026-09-23 |
| D2 | 改造范围 | 在现有 Vue 单页上重构，保留后端与环境数据 | 2026-09-23 |
| D3 | 保险口径 | 进**抵押折扣**，不做乘系数、不单列增信额度 | 2026-09-23 |
| D4 | 离线能力 | 不做 | 2026-09-23 |
| D5 | 客户端形态 | 答辩用 H5 移动网页，不做微信小程序 | 2026-09-23 |
| D6 | 系统视角 | **客户优先，县域降级**为「客户的外部环境输入 + 区域集中度管理」 | 2026-09-23 |
| D7 | 活体资产抵押 | **推翻** `credit_cases.json` 的 `limits.no_live_stock_collateral: true`；抵押上限改为按耳标/保险分档**计算** | 2026-09-23 |
| D8 | 抵押折扣四档 | 有耳标+有保险 70% / 有耳标+无保险 40% / 无耳标+有保险 30% / 都没有 → 不适用不计入 | 2026-09-23 |
| D9 | `bottleneck` 结构 | 改为两级（final / supply_side / demand_side_yuan / supply_side_yuan） | 2026-09-23 |
| D10 | 导航形态 | **左侧边栏**（3 组 7 项），替代现有顶部 8 项 + 「更多」下拉 | 2026-09-23 |
| D11 | 新页面数 | **7 页**（原 8 页，原型 v2 后删「数据接入中心」并下沉为「资料」Tab） | 2026-09-23 |

### 探讨进度

探讨顺序：① 主线客户旅程 → ② 风控口径 → ③ 额度引擎 → ④ 数据接入 → ⑤ 页面导航与删除清单 → ⑥ 角色与答辩演示脚本。
详见方案稿第 10 节「探讨记录」。

- 第 1 步**已完成**：牧户信贷全旅程（环节 0 客户来源 → 1 初筛 → 2 定额 → 3 审批放款 → 4 贷后监控 → 5 处置收回 → 6 结清回流 → 7 续贷）；视角定为**客户优先（D6）**。
- 贷后五类信号已对齐（`资产 / 健康 / 经营 / 环境 / 还款`），"疫情"的银行定位＝抵押物灭失风险 + 经营真实性验证 + 区域集中风险（方案稿 10.6）。
- 客户数据方案：合成，总量对标统计年鉴、个体按分布生成；**优先级＝证据链完整 > 户数多**（方案稿 10.7）。
- 第 2 步**已完成**：风控口径三段（贷前准入+定额 / 贷中用途 + 资金回流降级 / 贷后接任务表），含三个待钉死口径（方案稿第 11 节）。
- 第 3 步**已完成**：额度引擎落地（方案稿第 14 节）。实跑确认只需改 `_affordable_limits()` 一处；**承载修正因子已撤销**（重复扣减）；黄金案例 90 万预期不变。
- 第 4 步**已完成**：数据接入清单 E1–E11 + 接入三档 + 降级原则 + 优先级（方案稿第 16 节）。P0 只有耳标台账与保单两项。
- 补充核实（第 17 节）：活体抵押有大量真实先例（江西吉安「数字畜牧贷」1.75 亿 / 四川广元第三方监管 / 河北丰宁 / 广西兴农易贷 / 江苏盐城苏州），政策依据是 **2025 年中央一号文件**首次提出推广畜禽活体抵押融资贷款。
- 第 5 步**已完成**：页面与导航结构（方案稿第 19 节）。**新页面 7 项**（原型 v2 反馈后从 8 减到 7，删「数据接入中心」并下沉为「资料」Tab），现有 14 页 → 7 页；A1–A9 裁定完成；实施分三期，一期零外部依赖。
- 可点原型：`_原型/银行版原型预览.html`（单文件零依赖，**v3 已获 WH 验收**）。左侧边栏 3 组 7 项 + 7 个页面，客户档案含 6 Tab（概览/资料/资产/授信/贷后/依据）+ 顶部客户切换器；数据驱动，3 户分别演示「可贷 / 暂缓 / 待补资料」。
- 第 6 步**已完成**：角色与答辩演示脚本 → 独立文件 `答辩演示脚本_银行版_20260923.md`（六幕动线 / 讲什么藏什么 / 10 问必答预案 / 演示前检查清单 / 时长控制）。
- **六步探讨全部完成**，并已**进入实施**（2026-09-23，一期落地，见第 10 节）。

## 10. 银行版一期实施记录（2026-09-23）

### 已落地的代码

| 文件 | 改动 |
|---|---|
| `backend/credit_decision.py` | 新增 `_PLEDGE_DISCOUNT`（四档折扣常量）、`_live_stock_pledge_limit()`（活体抵押上限，D7/D8）；`_affordable_limits()` 接入抵押上限；`evaluate_credit_case()` 返回顶层两级 `bottleneck`（D9）；旧字段 `limits.bottleneck`（供给侧）/`collateral_applicable` 语义保留 |
| `backend/bank_view.py` | **新增**。银行视角聚合：`overview / customer_pool / customer_profile / customer_documents / ledger_board / post_loan_board / insurance_board / region_board`。只读、无随机（md5 稳定派生）、派生层逐条标 `is_derived` |
| `backend/server.py` | 新增 8 个 `/api/bank/*` 路由；新增 `/bank` 路由（必须显式注册，否则 `serve_frontend()` 会兜底返回 index.html）；`ADMIN_PAGES` 移除 3 个壳页、加入 `bank.html` |
| `frontend/bank.html` `bank.css` `bank.js` | **新增**。银行版控制台：左侧边栏 3 组 7 项 + 客户档案 6 Tab（概览/资料/资产/授信/贷后/依据）+ 顶部客户切换器（下拉 + 上一户/下一户） |
| `frontend/app.js` | `navMore` 移除 3 个壳页；删除死方法 `moduleHref`（2026-08-15 删 module-detail 时的孤儿） |
| `_原型/_removed/` | 存放下线的 `overview.html` / `modules.html` / `module.html`（**移动而非删除，可回退**） |

### 测试

| 测试 | 结果 |
|---|---|
| `backend/test_credit_decision.py` | 16/16 |
| `backend/test_credit_decision_extended.py` | 10/10 |
| `backend/test_credit_decision_pledge.py`（**新增**，11 项） | 11/11 |
| `backend/test_bank_api.py`（**新增**，14 项） | 14/14 |
| `backend/test_truthful_outputs.py` / `test_event_similarity.py` | 通过 |
| Playwright 前端验证 | 7 页全通、切客户数据真变、资料 28 项/6 组、零 JS 报错 |

### 重要约束（下次改这块务必遵守）

1. **黄金案例 900000 元必须不变**。抵押上限数据缺失时要标「不适用」并排除出 min 比较，**绝不能按 0 处理**，否则所有客户额度会被压到 0。
2. **派生数据必须标注**。`bank_view.py` 里凡无源数据支撑的项（无票出栏、出栏构成、资料填写情况、承保头数）一律带 `is_derived` 与 `derived_note`。
3. **源码是字符串数值**：`business_subjects.insurance_coverage` 是 `"80%"`，`finance_credit.interest_rate` 是 `"4.20%"`。一律走 `bank_view._num()`，不要直接 `float()`。
4. **改 Python 走 Serena**（本地 HTTP 模式，见第 2 节）；HTML 无语言服务器，用锚定编辑。
5. **旧 SPA 保留在 `/`**，银行版在 `/bank`。两侧共用同一后端与 `/api`。

### 已知遗留

- ⏸ **【待办·口径】银行版「建议金额」不是算出来的（2026-09-25 定位，未修）**
  `backend/bank_view.py` 的 `_conclusion()` 第 424 行原为
  `"amount_yuan": int(_num(fin.get("credit_line")) * 10000)` —— 取**行内授信额度**回显，
  并不是需求侧/供给侧取小的唯一金额链输出。而 `frontend/bank.html:226` 把它标成
  「**建议 X 万**」，位置正是客户档案 L1 大字（答辩最显眼处）。
  - 证据：黄金案例唯一链实跑 = **900000 元**；76 户 `credit_line` 是 271 / 255 / 233 万…
  - 与 `答辩口径.md` 第 56 行「唯一建议金额（模型不乘额度、不掺保险）」直接冲突。
  - `test_bank_api` 14/14 全绿也没拦住 —— 它只断言结构，**不断言金额来源**。
  - **已定方向（用户 2026-09-25 选「先止血：不显示金额」）**：① `_conclusion` 三个分支
    不再输出 `amount_yuan`；② `customer_pool` 的 `amount_yuan` 改名 `credit_line_yuan`
    并按其排序；③ 前端同步 6 处（`bank.html` 117 / 120–126 / 172–183 / 195 / 226 / 测算入口按钮）。
  - 半成品补丁已存：`D:\DesktopData\项目\.workbuddy\todo-银行版建议金额口径-20260925.diff`（108 行，`git apply` 即恢复）。
  - 让金额「真由算出来」属二期：需要「主体 → case」构造器（案例文件只有 2 个，银行版有 76 户）。
- ✅ `ci.yml` 与 §10/§11 的未提交项已于 2026-09-24 入库并推送（`95b2a30` / `a456d7c` / `f93cac2` / `11e2dbb`）。
- `frontend/data.html` 里指向 3 个已下线壳页的链接成为死链（该页当前无导航入口，影响有限）。
- 授信 Tab 只展示现有授信要素，**未接** `/api/credit-decision/evaluate`（界面留了入口按钮）。

### 二期（资产侧）清单 —— 2026-09-25 逐条在代码里核实过，未开始

| 项 | 现状（代码事实） | 二期要做 |
|---|---|---|
| 盘库管理 | ❌ **全仓不存在**，仅 `bank_view.py:59` 一处文档串提到「最近盘库」 | 盘库任务表（新 `ledger_audits.json`）+ 发起盘库 + 实盘登记 + 差异原因 + 处置 + 留痕 |
| 单户耳标明细 | ❌ `_derive_ledger` 只出聚合数字 | 耳标级台账（耳标号 / 品种 / 状态 / 是否投保） |
| 单户抵押上限展示 | ❌ `bank_view.py` 无 pledge 字段；`credit_decision._live_stock_pledge_limit()`（391–481 行）**已算好**但只在 evaluate 链内 | 四档折扣 + 上限金额接到「资产」/「授信」Tab |
| 逐笔出栏流水 | ❌ 只有构成汇总 | 有票/无票、日期、头数、凭证号 |
| 「去测算」接线 | ❌ 死按钮（无 `@click`） | 见上方口径待办 |


### 运行

```powershell
# 银行版（左侧边栏 7 页）
$env:PORT=8100; C:\Users\WH\.workbuddy\binaries\python\envs\default\Scripts\python.exe backend\server.py
# 前台 http://127.0.0.1:8100/bank   旧版 http://127.0.0.1:8100/
```
依赖装在隔离 venv：`C:\Users\WH\.workbuddy\binaries\python\envs\default`（pytest / fastapi / uvicorn / numpy / scikit-learn / httpx / python-multipart）。

## 11. Git 与推送（2026-09-24 更新）

| 项 | 值 |
|---|---|
| 远端 | `https://github.com/wndwns/-.git`（owner: wndwns）|
| **默认分支** | **`main`**（同组人打开仓库直接看到）|
| 当前工作分支 | `feature/demo-guide` |
| 两者关系 | `origin/main` == `origin/feature/demo-guide` == `a456d7c`，内容完全一致 |
| 其他分支 | `master`（92f6977，历史遗留，与 main 分叉，勿动）、`feature/npp`、`codex/*` 系列 |
| 保护分支 | `codex/backup/pre-deepening-20260807`（勿覆盖）|

**推主支的正确姿势**（不切分支、不碰工作区）：

```bash
git push origin feature/demo-guide            # 先备份工作分支
git push origin feature/demo-guide:main       # 快进推到 main
git fetch origin && git branch -f main origin/main   # 同步本地引用
```

### ⚠️ 改动 `.github/workflows/*` 时必须走 SSH（HTTPS 一定被拒）

HTTPS 推含 workflow 改动的提交会被 GitHub 拒：

```
refusing to allow an OAuth App to create or update workflow `.github/workflows/ci.yml` without `workflow` scope
```

本机**两个 HTTPS 凭据都没有 `workflow`**，且无法在非交互环境里补：
GCM（`credential.helper=helper-selector`）不报 scope；`gh auth status` 显示
`gho_…` 只有 `gist` / `read:org` / `repo`。

**可行解：SSH over 443 + 本地 SOCKS5 桥**（2026-09-24 实测推成）。SSH 认证不受 OAuth scope 限制，
但本机直连不通（`git@github.com:22` 与 `ssh.github.com:443` 都超时），且 Git Bash 没有
`nc / ncat / connect / socat`。所以写了单文件工具 **`_原型/push_via_ssh.py`**（仅用标准库，
自带 SOCKS5 隧道，把自己同时当作 ssh 的 ProxyCommand）：

```bash
cd "C:/Users/WH/Desktop/项目/gonghangbei - 副本"
PY="C:/Users/WH/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

$PY _原型/push_via_ssh.py --check                    # 只验认证，不动远端（回 Hi wndwns!）
$PY _原型/push_via_ssh.py feature/demo-guide         # 推工作分支
$PY _原型/push_via_ssh.py feature/demo-guide:main    # 快进推 main
# 推完自动 fetch + 把本地 main / feature/demo-guide 对齐到远端
```

- 走的是**仓库 owner `wndwns` 本人**的身份（`ssh -T` 回 `Hi wndwns!`），有写权限。
- 前提：**Clash 在跑**（默认 `127.0.0.1:7897`，混合端口，支持 SOCKS5；已实测握手 `05 00`）。
  换端口用 `--proxy 127.0.0.1:PORT`。
- 脚本会往 `%TEMP%\gh_push_ssh_config` 写一份 ssh config（**UTF-8**——本路径含中文，
  用 ASCII 写会直接 `UnicodeEncodeError`），ProxyCommand 指回自身 `--bridge` 模式。
- 备选（需人工）：`gh auth refresh -h github.com -s workflow`，或建 classic PAT 勾 `repo` + `workflow`。

### 其他两个已踩的坑

1. **本机网络（Clash 7897）间歇性可用**。push 失败先 `git ls-remote origin` 试水，
   报 `TLS connect error / unexpected eof` 是网络，不是权限；mihomo 的 REST 控制接口是关的
   （`external-controller: ''`），**命令行换不了节点，只能在 Clash Verge GUI 里换**。
2. **历史上推 main 时该 workflow 报错曾「自己消失」**（换梯子后凭据重新授权带上了 scope），
   但 2026-09-24 复现，说明**不可依赖**——按上面的 SSH 路子走最稳。

**CI 补充已入库**：`95b2a30`（2026-09-24）新增 3 个测试步骤（`test_credit_decision_extended` / `test_credit_decision_pledge` / `test_bank_api`）+ `node --check frontend/bank.js`。

### 已核实的信贷骨架现状（改这块前先看）

**字段层基本齐备，缺的是引擎、阈值、界面。**

| 层次 | 位置 | 状态 |
|---|---|---|
| 客户表 | `backend/data_store/business_subjects.json` | ✅ `admission_stage`（准入监测/人工复核/存量贷后）、`cattle_count`、`grassland_mu`、`insurance_coverage`、`customer_manager` 等 |
| 授信表 | `backend/data_store/finance_credit.json` | ✅ `credit_line`/`used_credit`/`term_months`/`repayment_status`/`overdue_times`/`loan_purpose` |
| **贷中用途核验字段** | `backend/data_store/supply_chain_orders.json` | ✅ `fund_usage_status`、`risk_note`、`payment_id`、`linked_credit_id` |
| **贷后任务表** | `backend/data_store/post_loan_workflow.json` | ✅ **结构完整**：`task_id`/`workflow_stage`/`trigger_type`/`assigned_to`/`due_date`/`task_status`/`action_result`/`next_action` |
| 理赔链 | `backend/data_store/insurance_claims.json` | ✅ 保单/险种/查勘/保额/赔付/贷后回流 |
| 环境预警 | `backend/early_warning.py` | ✅ 县域级，可运行 |
| 触发引擎 | — | ❌ 12 条任务是手工样例，不是算出来的 |
| 阈值定义 | — | ❌ 有"保险低覆盖"触发类型但没写阈值 |
| 操作界面 | — | ❌ 任务表只当"闭环数据"表格展示 |
| 留痕写入 | — | ❌ `action_result` 有字段但无写入路径 |

**另外两处必须知道的现状**：
- `GET /api/alerts` 返回 **`backend/data.py` 里 4 条硬编码假数据**，不是算出来的。
- 前端 `frontend/app.js` 第 04 步的贷后核查判断**写在前端**，靠 `score>=65 或 hasOverdue` 推。



## 9. 本文件的维护

- 每次完成实质改动（改代码、定决策、改口径、增删页面）后，同步更新第 8 节「当前状态」。
- 第 5 节「数据事实边界」中的计数（128 / 1372 / 21 户 / 1135 头等）变化时，与 `项目全景说明（Codex读）.md` 一并核对。
- 修改前先读全文，避免覆盖他人改动。
