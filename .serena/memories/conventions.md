# 约定

- 后端通过 `create_app()` 组装 FastAPI；`server.py` 使用延迟导入兼容 `python backend/server.py` 与模块方式，不要破坏这种双导入路径。
- `backend/data.py` 负责读取、聚合和平台输出；`backend/store.py` 是 JSON 持久化边界，避免在 API 路由直接访问数据文件。
- 可选功能按“导入失败则降级”处理；缺少可选 ML、外部 API 或灾害模块时应保留可用的退化路径。
- 前端逻辑都在 `frontend/app.js` 的单一 Vue 应用与 `api` 对象中；新增接口先加 API 方法，再接入响应式状态与页面。
- 当前主线仅改 `frontend/`，除非需求明确要求同步历史版本。
- 数据溯源是产品约束：真实、推导和演示数据不能混淆。推导数据必须保留 `is_derived=true` 及推导说明；保险数据是增信因素，不应当作无标签风险检测目标。