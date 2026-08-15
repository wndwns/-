# 完成检查

- 后端变更：先执行 `python -m compileall backend`，再用 `python backend/server.py` 启动并检查受影响 API 或 `http://127.0.0.1:8000/docs`。
- 前端变更：在后端运行时打开受影响页面；确认 `frontend/app.js` 的 API 路径与 `backend/server.py` 路由一致。
- 数据或模型变更：验证相关 JSON 可加载、模型端点可返回；涉及训练时调用 `POST /api/model/train` 并检查对应状态或结果 API。
- 只运行与改动范围匹配的脚本；项目没有定义统一全量测试、lint 或格式化命令。