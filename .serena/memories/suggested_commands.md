# 常用命令

- 安装依赖：`python -m pip install -r requirements.txt`
- 启动开发服务：`python backend/server.py`；默认监听 `http://127.0.0.1:8000`，文档为 `/docs`，管理端为 `/admin`。
- 等效 Uvicorn 启动：`uvicorn backend.server:app --host 0.0.0.0 --port 8000`。
- Python 入口脚本同时兼容直接执行与模块导入；保持从项目根目录启动。
- Windows PowerShell 环境变量示例：`$env:MYSQL_HOST="127.0.0.1"`；不配 MySQL 时使用 JSON store。
- 项目未发现统一的 lint、formatter 或 test runner 配置。