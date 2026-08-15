# 技术栈

- Python 3，FastAPI + Uvicorn；依赖见根目录 `requirements.txt`。
- 可选 ML：numpy、scikit-learn、xgboost；`backend/models.py` 的 `RiskModel` 默认使用 XGBoost（depth6/lr0.1/100棵，分类+回归，数值类别标签），无 xgboost 时回退 RandomForest+Ridge；XGB 解释走 booster pred_contribs（不依赖 shap），RF/Ridge 可选 SHAP。
- 前端：无构建步骤的 Vue 3 CDN Options API + ECharts，HTML/CSS/JS 位于 `frontend/`，通过同源 `/api/*` 调用后端。
- 数据：默认 JSON 文件存储；可选 MySQL（PyMySQL + DBUtils）。配置从 `.env` 或 `backend/content-store.json` 加载。
- 遥感处理相关依赖：xarray、netCDF4、rasterio、Pillow；仅在对应数据处理脚本需要时使用。
- 可选外部集成：高德天气/地图和 Open-Meteo；API key 不写入源码，环境变量模板在 `.env.example`。
