"""
工银牧融 - FastAPI 后端服务
============================================================================
提供 REST API 和前端静态页面服务。

启动:
    python backend/server.py
    或: uvicorn backend.server:app --host 0.0.0.0 --port 8000

管理端: http://127.0.0.1:8000/admin
API 文档: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from io import BytesIO
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
CONTENT_FILE = ROOT / "backend" / "content-store.json"
MEDIA_DIR = ROOT / "backend" / "media"
SLIDE_UPLOAD_DIR = MEDIA_DIR / "slides"
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 25 * 1024 * 1024
SLIDE_ASPECT_RATIO = 16 / 9

# 允许的静态前端页面
ADMIN_PAGES = {
    "",
    "index.html",
    "overview.html",
    "modules.html",
    "module.html",
    "data.html",
    "roadmap.html",
    "admin.html",
}

# ---------------------------------------------------------------------------
# 请求体模型
# ---------------------------------------------------------------------------


class SlidesPayload(BaseModel):
    slides: list[dict[str, Any]] = Field(default_factory=list)


class PlatformPayload(BaseModel):
    platform: dict[str, Any]


class DataSourceConfigPayload(BaseModel):
    source_type: str = "sample"
    api_endpoint: str = ""
    api_key: str = ""
    extra_config: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# data 模块导入（兼容直接运行和模块运行）
# ---------------------------------------------------------------------------

def _import_data():
    """延迟导入 data 模块（兼容多种运行方式）。"""
    import sys
    _here = str(Path(__file__).resolve().parent)
    if _here not in sys.path:
        sys.path.insert(0, _here)

    # 直接 import data（因为 backend 目录已在 sys.path 或作为包导入）
    try:
        from data import (  # type: ignore[import-not-found]
            build_platform_data,
            get_outline,
            get_regions,
            get_modules,
            get_score_model,
            get_subjects,
            get_finance,
            get_closed_loop_data,
            get_closed_loop_table,
            get_alerts,
            get_weather,
            get_remote_sensing,
            get_risk_assessment,
            get_data_connections,
            db_available,
            ensure_initialized,
        )
    except ImportError:
        from backend.data import (  # type: ignore[no-redef,import-not-found]
            build_platform_data,
            get_outline,
            get_regions,
            get_modules,
            get_score_model,
            get_subjects,
            get_finance,
            get_closed_loop_data,
            get_closed_loop_table,
            get_alerts,
            get_weather,
            get_remote_sensing,
            get_risk_assessment,
            get_data_connections,
            db_available,
            ensure_initialized,
        )
        # 重新绑定函数名为无 db_available 的版本
        def db_available(): return False
        def ensure_initialized(): return False
        DataSourceConfig = type("DataSourceConfig", (), {"__init__": lambda self, k: None, "update": lambda self, **kw: None})
    return {
        "build_platform_data": build_platform_data,
        "get_outline": get_outline,
        "get_regions": get_regions,
        "get_modules": get_modules,
        "get_score_model": get_score_model,
        "get_subjects": get_subjects,
        "get_finance": get_finance,
        "get_closed_loop_data": get_closed_loop_data,
        "get_closed_loop_table": get_closed_loop_table,
        "get_alerts": get_alerts,
        "get_weather": get_weather,
        "get_remote_sensing": get_remote_sensing,
        "get_risk_assessment": get_risk_assessment,
        "get_data_connections": get_data_connections,
        "db_available": db_available,
        "ensure_initialized": ensure_initialized,
        "DATA_SOURCE_KEYS": {"气象数据": "weather", "遥感数据": "remote_sensing", "产业经营数据": "business", "金融保险数据": "finance"},
    }


_data = _import_data()

# CSV 模板辅助：数值列和风险等级列的关键词
_NUMERIC_COLS = {"temperature_c", "precipitation_mm_24h", "wind_speed_mps", "snow_depth_cm", "ndvi", "carrying_capacity_sheep_unit", "cattle_count", "sheep_count", "grassland_mu", "credit_value", "credit_line", "used_credit", "score", "term_months", "overdue_times"}
_RISK_COLS = {"cold_wave_risk", "snowstorm_risk", "drought_risk"}


# ---------------------------------------------------------------------------
# 启动事件
# ---------------------------------------------------------------------------


def on_startup() -> None:
    """应用启动时初始化数据库。"""
    try:
        if _data["db_available"]():
            _data["ensure_initialized"]()
    except Exception as exc:
        print(f"[server] 数据库初始化跳过: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 应用工厂
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(
        title="牧融绿链 API",
        description="工行高原畜牧绿色金融风险评估与贷后管理平台",
        version="1.0.0",
        on_startup=[on_startup],
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ======================================================================
    # 健康检查
    # ======================================================================

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "yak-risk-platform",
            "db": "mysql" if _data["db_available"]() else "sample",
        }

    # ======================================================================
    # 平台核心数据 API
    # ======================================================================

    @app.get("/api/platform")
    def platform() -> dict[str, Any]:
        return get_active_platform()

    @app.get("/api/outline")
    def outline() -> dict[str, Any]:
        return _data["get_outline"]()

    @app.get("/api/brand")
    def brand() -> dict[str, Any]:
        return get_active_platform().get("brand", {})

    @app.get("/api/regions")
    def regions() -> list[dict[str, Any]]:
        return _data["get_regions"]()

    @app.get("/api/modules")
    def modules() -> list[dict[str, Any]]:
        return _data["get_modules"]()

    @app.get("/api/score-model")
    def score_model() -> list[dict[str, Any]]:
        return _data["get_score_model"]()

    @app.get("/api/subjects")
    def subjects() -> list[dict[str, Any]]:
        return _data["get_subjects"]()

    @app.get("/api/finance")
    def finance() -> list[dict[str, Any]]:
        return _data["get_finance"]()

    @app.get("/api/closed-loop")
    def closed_loop() -> dict[str, list[dict[str, Any]]]:
        return _data["get_closed_loop_data"]()

    @app.get("/api/closed-loop/{table}")
    def closed_loop_table(table: str) -> list[dict[str, Any]]:
        allowed = {
            "insurance_claims",
            "supply_chain_orders",
            "supply_chain_payments",
            "post_loan_workflow",
            "green_performance_metrics",
        }
        if table not in allowed:
            raise HTTPException(status_code=404, detail=f"Closed-loop table not found: {table}")
        return _data["get_closed_loop_table"](table)

    @app.get("/api/alerts")
    def alerts() -> list[dict[str, Any]]:
        return _data["get_alerts"]()

    @app.get("/api/weather")
    def weather(region_id: str | None = None) -> list[dict[str, Any]] | dict[str, Any]:
        return _filter_by_region(_data["get_weather"](), region_id)

    @app.get("/api/remote-sensing")
    def remote_sensing(region_id: str | None = None) -> list[dict[str, Any]] | dict[str, Any]:
        return _filter_by_region(_data["get_remote_sensing"](), region_id)

    @app.get("/api/risk-assessment")
    def risk_assessment(region_id: str | None = None) -> list[dict[str, Any]] | dict[str, Any]:
        return _filter_by_region(_data["get_risk_assessment"](), region_id)

    @app.get("/api/data-connections")
    def data_connections() -> list[dict[str, Any]]:
        return _data["get_data_connections"]()

    # ======================================================================
    # 数据源管理 API
    # ======================================================================

    @app.get("/api/data-sources")
    def list_data_sources() -> list[dict[str, Any]]:
        connections = _data["get_data_connections"]()
        result = []
        for conn in connections:
            key = _data["DATA_SOURCE_KEYS"].get(conn.get("name", ""), "")
            result.append({
                "name": conn.get("name", ""),
                "source_key": key,
                "source_type": conn.get("source_type", "sample"),
                "status": conn.get("status", "待接入"),
                "source": conn.get("source", ""),
                "api_endpoint": conn.get("api_endpoint", ""),
                "fields": conn.get("fields", []),
                "db_connected": _data["db_available"](),
            })
        return result

    @app.post("/api/data-sources/{source_key}/config")
    def configure_data_source(source_key: str, payload: DataSourceConfigPayload) -> dict[str, Any]:
        """配置数据源（预留接口——当前写入 content-store.json）。

        后续接入真实 API 时，这里会把 api_endpoint/api_key 写入 data_source_config 表或 store。
        """
        store = load_content_store()
        ds_configs = store.get("data_source_configs", {})
        ds_configs[source_key] = {
            "source_type": payload.source_type,
            "api_endpoint": payload.api_endpoint,
            "api_key": payload.api_key,
            "extra_config": payload.extra_config,
        }
        store["data_source_configs"] = ds_configs
        save_content_store({"slides": store.get("slides", []), "platform": store.get("platform", {}), "data_source_configs": ds_configs})
        return {"ok": True, "source_key": source_key, "message": "配置已保存（预留接口，当前仅持久化配置）"}

    @app.post("/api/data-sources/{source_key}/refresh")
    def refresh_data_source(source_key: str) -> dict[str, Any]:
        if not _data["db_available"]():
            return {"ok": True, "message": "MySQL 不可用，当前使用内存样例数据", "source": "sample"}
        return {"ok": True, "message": f"数据源 {source_key} 已刷新", "source": "mysql"}

    # ======================================================================
    # CSV 导入 —— 数据闭环核心
    # ======================================================================

    @app.get("/api/integrations/status")
    def integrations_status() -> dict[str, Any]:
        store = load_content_store()
        configs = store.get("data_source_configs", {})
        amap_key = _get_config_value(configs, "amap", "api_key") or os.environ.get("AMAP_WEB_SERVICE_KEY", "")
        amap_js_key = _get_config_value(configs, "amap_map", "api_key") or os.environ.get("AMAP_JS_API_KEY", "")
        amap_js_code = _get_config_value(configs, "amap_map", "security_js_code") or os.environ.get("AMAP_SECURITY_JS_CODE", "")
        return {
            "open_meteo": {
                "configured": True,
                "provider": "Open-Meteo 开放天气 API",
                "apply_url": "https://open-meteo.com/en/docs",
                "env_key": "",
                "usage": "/api/integrations/open-meteo/now?latitude=31.36&longitude=90.01",
                "config_source_key": "open_meteo",
                "note": "无需 API Key，按经纬度返回当前温度、湿度、降水、风速和天气代码。",
            },
            "amap_weather": {
                "configured": bool(amap_key),
                "provider": "高德开放平台 Web服务 API",
                "apply_url": "https://lbs.amap.com/api/webservice/guide/api/weatherinfo",
                "env_key": "AMAP_WEB_SERVICE_KEY",
                "usage": "/api/integrations/amap/weather?city=那曲市",
                "config_source_key": "amap",
            },
            "amap_map": {
                "configured": bool(amap_js_key),
                "security_code_configured": bool(amap_js_code),
                "provider": "高德开放平台 JS API 2.0",
                "apply_url": "https://lbs.amap.com/api/javascript-api-v2/guide/abc/load",
                "env_key": "AMAP_JS_API_KEY",
                "security_env_key": "AMAP_SECURITY_JS_CODE",
                "runtime_config": "/api/integrations/amap/map-config",
                "config_source_key": "amap_map",
            },
        }

    def _open_meteo_weather_text(code: Any) -> str:
        mapping = {
            0: "晴",
            1: "基本晴朗",
            2: "局部多云",
            3: "阴",
            45: "雾",
            48: "雾凇",
            51: "小毛毛雨",
            53: "中等毛毛雨",
            55: "强毛毛雨",
            61: "小雨",
            63: "中雨",
            65: "大雨",
            71: "小雪",
            73: "中雪",
            75: "大雪",
            80: "阵雨",
            81: "强阵雨",
            82: "暴雨",
            85: "阵雪",
            86: "强阵雪",
            95: "雷暴",
            96: "雷暴伴小冰雹",
            99: "雷暴伴强冰雹",
        }
        try:
            return mapping.get(int(code), f"天气代码 {code}")
        except (TypeError, ValueError):
            return "实时天气"

    @app.get("/api/integrations/open-meteo/now")
    def open_meteo_now(latitude: float = 31.36, longitude: float = 90.01) -> dict[str, Any]:
        """Open-Meteo 开放天气接口，无需 Key，按经纬度返回实时天气。"""
        endpoint = "https://api.open-meteo.com/v1/forecast"
        params = urlencode({
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code",
            "timezone": "auto",
        })
        req = Request(f"{endpoint}?{params}", headers={"User-Agent": "yak-risk-platform/1.0"})
        try:
            with urlopen(req, timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return {"ok": False, "configured": True, "provider": "open_meteo", "message": f"Open-Meteo 请求失败: {exc}"}

        current = payload.get("current") or {}
        weather_code = current.get("weather_code")
        normalized = {
            "weather": _open_meteo_weather_text(weather_code),
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "precipitation": current.get("precipitation"),
            "wind_speed": current.get("wind_speed_10m"),
            "weather_code": weather_code,
            "obsTime": current.get("time"),
        }
        return {
            "ok": bool(current),
            "configured": True,
            "provider": "open_meteo",
            "location": {"latitude": latitude, "longitude": longitude},
            "current": normalized,
            "raw": payload,
        }

    @app.get("/api/integrations/amap/weather")
    def amap_weather(city: str = "那曲市", extensions: str = "base") -> dict[str, Any]:
        store = load_content_store()
        configs = store.get("data_source_configs", {})
        key = _get_config_value(configs, "amap", "api_key") or os.environ.get("AMAP_WEB_SERVICE_KEY", "")
        endpoint = _get_config_value(configs, "amap", "api_endpoint") or "https://restapi.amap.com/v3/weather/weatherInfo"
        if not key:
            return {
                "ok": False,
                "configured": False,
                "message": "未配置高德 Web服务 Key。请在环境变量 AMAP_WEB_SERVICE_KEY 或管理端 data_source_configs.amap.api_key 中填写。",
                "apply_url": "https://lbs.amap.com/api/webservice/guide/api/weatherinfo",
            }
        params = urlencode({"key": key, "city": city, "extensions": extensions, "output": "JSON"})
        req = Request(f"{endpoint}?{params}", headers={"User-Agent": "yak-risk-platform/1.0"})
        try:
            with urlopen(req, timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return {"ok": False, "configured": True, "message": f"高德天气请求失败: {exc}"}
        return {
            "ok": payload.get("status") == "1",
            "configured": True,
            "provider": "amap",
            "city": city,
            "extensions": extensions,
            "raw": payload,
        }

    @app.get("/api/integrations/amap/map-config")
    def amap_map_config() -> dict[str, Any]:
        """返回前端加载高德 JS API 所需的公开配置。

        JS API key 本身会暴露给浏览器，必须在高德控制台配置安全密钥、HTTP Referer
        或代理策略；Web 服务 key 不会通过此接口返回。
        """
        store = load_content_store()
        configs = store.get("data_source_configs", {})
        key = _get_config_value(configs, "amap_map", "api_key") or os.environ.get("AMAP_JS_API_KEY", "")
        security_js_code = _get_config_value(configs, "amap_map", "security_js_code") or os.environ.get("AMAP_SECURITY_JS_CODE", "")
        regions = _data["get_regions"]()
        points = []
        for region in regions:
            try:
                lng = float(region.get("longitude", 0))
                lat = float(region.get("latitude", 0))
            except (TypeError, ValueError):
                continue
            if lng and lat:
                points.append({
                    "region_id": region.get("id", ""),
                    "region_name": region.get("name", ""),
                    "longitude": lng,
                    "latitude": lat,
                    "risk_level": region.get("risk_level", ""),
                })
        return {
            "ok": bool(key),
            "configured": bool(key),
            "key": key if key else "",
            "security_js_code": security_js_code if key else "",
            "center": [91.1, 31.6],
            "zoom": 5,
            "points": points,
            "message": "" if key else "未配置高德 JS API Key。请在管理端或环境变量 AMAP_JS_API_KEY 中填写。",
        }

    @app.post("/api/import/csv")
    async def import_csv(
        file: UploadFile = File(...),
        table: str = Form("weather_data"),
        mode: str = Form("replace"),
    ) -> dict[str, Any]:
        """导入 CSV 数据到指定表。

        Args:
            file: CSV 文件
            table: 目标表 (weather_data / remote_sensing_data / business_subjects / finance_credit)
            mode: "replace" 替换全表 / "append" 追加数据
        """
        try:
            from store import import_csv_to_table, TABLES
        except ImportError:
            from backend.store import import_csv_to_table, TABLES  # type: ignore[no-redef]

        if table not in TABLES:
            return {"ok": False, "message": f"未知数据表: {table}，可选: {list(TABLES.keys())}"}

        content = await file.read()
        csv_text = content.decode("utf-8-sig")

        result = import_csv_to_table(csv_text, table, mode=mode)

        # 导入成功后，重建风险评估
        if result.get("ok"):
            result["risk_updated"] = True
            result["next_step"] = "请刷新前台数据查看更新后的风险评估结果"

        return result

    @app.get("/api/store/status")
    def store_status() -> dict[str, Any]:
        """获取数据存储状态（各表行数 + 数据来源）。"""
        try:
            from store import all_tables_info
        except ImportError:
            from backend.store import all_tables_info  # type: ignore[no-redef]

        tables = all_tables_info()
        return {
            "store_type": "json_files",
            "tables": tables,
            "total_rows": sum(t["row_count"] for t in tables),
        }

    @app.get("/api/store/table/{table}/download")
    def download_table_csv(table: str) -> dict[str, Any]:
        """导出表数据为 CSV 格式（方便下载备份）。"""
        import csv
        import io

        try:
            from store import read_table, TABLES
        except ImportError:
            from backend.store import read_table, TABLES  # type: ignore[no-redef]

        if table not in TABLES:
            return {"ok": False, "message": f"未知表: {table}"}

        rows = read_table(table)
        cols = TABLES[table]["columns"]

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in cols})

        return {
            "ok": True,
            "table": table,
            "row_count": len(rows),
            "csv": buf.getvalue(),
        }

    @app.get("/api/store/table/{table}/template")
    def download_table_template(table: str) -> dict[str, Any]:
        """生成 CSV 模板（仅包含表头）。"""
        try:
            from store import TABLES
        except ImportError:
            from backend.store import TABLES  # type: ignore[no-redef]

        if table not in TABLES:
            return {"ok": False, "message": f"未知表: {table}，可选: {list(TABLES.keys())}"}

        cols = TABLES[table]["columns"]
        required = TABLES[table].get("required", [])
        header = ",".join(cols)
        # 生成一行示例数据，必需列标红提示
        example_vals = []
        for c in cols:
            if c == "region_id":
                example_vals.append("naqu-bange")
            elif c == "station":
                example_vals.append("某某气象站")
            elif c == "name" or c == "subject_name":
                example_vals.append("某合作社")
            elif c == "region_name":
                example_vals.append("那曲市班戈县")
            elif c in ("observed_at", "scene_date"):
                example_vals.append("2026-01-01")
            elif c in _NUMERIC_COLS:
                example_vals.append("0")
            elif c in _RISK_COLS:
                example_vals.append("中")
            else:
                example_vals.append("示例")

        return {
            "ok": True,
            "table": table,
            "label": TABLES[table]["label"],
            "columns": cols,
            "required": required,
            "csv_header": header,
            "csv_example": ",".join(example_vals),
        }

    # ======================================================================
    # 管理端 API
    # ======================================================================

    @app.get("/api/admin/content")
    def admin_content() -> dict[str, Any]:
        return load_content_store()

    @app.get("/api/admin/slides")
    def admin_slides() -> list[dict[str, Any]]:
        return load_content_store().get("slides", [])

    @app.post("/api/admin/slides")
    def save_slides(payload: SlidesPayload) -> dict[str, Any]:
        store = load_content_store()
        store["slides"] = payload.slides
        save_content_store(store)
        return {"ok": True, "slides": payload.slides}

    @app.post("/api/admin/upload-image")
    async def upload_admin_image(file: UploadFile = File(...)) -> dict[str, Any]:
        suffix = Path(file.filename or "").suffix.lower()
        content_type = (file.content_type or "").lower()
        if suffix not in ALLOWED_IMAGE_SUFFIXES or content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="仅支持 jpg、png、webp、gif 图片")

        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="图片文件为空")
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="图片不能超过 8MB")

        SLIDE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        stem = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:10]}"
        original_name = f"{stem}-original{suffix}"
        original_target = SLIDE_UPLOAD_DIR / original_name
        original_target.write_bytes(data)

        banner_name = f"{stem}-banner.jpg"
        banner_target = SLIDE_UPLOAD_DIR / banner_name
        width, height = build_slide_banner(data, banner_target)

        url = f"/media/slides/{banner_name}"
        return {
            "ok": True,
            "url": url,
            "original_url": f"/media/slides/{original_name}",
            "filename": banner_name,
            "original_filename": original_name,
            "content_type": "image/jpeg",
            "size_bytes": banner_target.stat().st_size,
            "original_size_bytes": len(data),
            "width": width,
            "height": height,
            "message": "已生成 16:9 横版轮播图，并保留原图",
        }

    @app.post("/api/admin/platform")
    def save_platform(payload: PlatformPayload) -> dict[str, Any]:
        store = load_content_store()
        store["platform"] = payload.platform
        save_content_store(store)
        return {"ok": True, "platform": payload.platform}

    # ======================================================================
    # 公开数据集合 API
    # ======================================================================

    PUBLIC_DATA_DIR = ROOT / "public_data"
    SAMPLES_DIR = PUBLIC_DATA_DIR / "samples"

    @app.get("/api/public-data/sources")
    def public_data_sources() -> dict[str, Any]:
        """返回公开数据源清单。"""
        sources_file = PUBLIC_DATA_DIR / "sources.json"
        if sources_file.exists():
            return json.loads(sources_file.read_text(encoding="utf-8"))
        return {"error": "sources.json not found"}

    @app.get("/api/public-data/samples")
    def public_data_samples() -> list[dict[str, Any]]:
        """返回可用的样例 CSV 文件列表。"""
        table_map = {
            "weather_data_public_sample.csv": "weather_data",
            "remote_sensing_public_sample.csv": "remote_sensing_data",
            "remote_sensing_capacity_demo.csv": "remote_sensing_data",
            "business_subjects_demo.csv": "business_subjects",
            "business_subjects_risk_demo.csv": "business_subjects",
            "finance_credit_demo.csv": "finance_credit",
            "finance_credit_risk_demo.csv": "finance_credit",
            "risk_event_labels_demo.csv": "risk_event_labels",
        }
        descriptions = {
            "weather_data_public_sample.csv": "气象监测样例数据，3个区域×3个时段",
            "remote_sensing_public_sample.csv": "遥感生态样例数据，3个区域×4个时段",
            "remote_sensing_capacity_demo.csv": "遥感补充样例，包含退化等级、载畜量、积雪等字段",
            "business_subjects_demo.csv": "经营主体样例数据，8户典型主体",
            "business_subjects_risk_demo.csv": "风控终端经营主体样例，10户主体画像和授信评分",
            "finance_credit_demo.csv": "金融保险样例数据，8条授信记录",
            "finance_credit_risk_demo.csv": "风控终端授信样例，10条额度、用信、逾期状态",
            "risk_event_labels_demo.csv": "风险事件标签样例，覆盖灾害、理赔、逾期等弱监督标签",
        }
        result = []
        if SAMPLES_DIR.exists():
            for f in sorted(SAMPLES_DIR.glob("*.csv")):
                result.append({
                    "filename": f.name,
                    "table": table_map.get(f.name, ""),
                    "description": descriptions.get(f.name, ""),
                    "size_bytes": f.stat().st_size,
                    "download_url": f"/public_data/samples/{f.name}",
                })
        return result

    PROCESSED_DIR = PUBLIC_DATA_DIR / "processed"

    @app.get("/api/public-data/processed")
    def public_data_processed() -> list[dict[str, Any]]:
        """返回 processed 目录下已处理的 CSV 文件列表。"""
        table_hint = {
            "weather": "weather_data", "remote": "remote_sensing_data",
            "ndvi": "remote_sensing_data", "snow": "remote_sensing_data",
            "fvc": "remote_sensing_data", "degradation": "remote_sensing_data",
            "business": "business_subjects", "finance": "finance_credit",
        }
        result = []
        if PROCESSED_DIR.exists():
            for f in sorted(PROCESSED_DIR.glob("*.csv")):
                hint = "weather_data"
                for k, v in table_hint.items():
                    if k in f.name.lower():
                        hint = v
                        break
                result.append({
                    "filename": f.name,
                    "table": hint,
                    "description": f"已处理数据 ({f.stat().st_size} bytes)",
                    "size_bytes": f.stat().st_size,
                    "download_url": f"/public_data/processed/{f.name}",
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })
        return result

    # ======================================================================
    # 模型 API
    # ======================================================================

    @app.get("/api/model/status")
    def model_status() -> dict[str, Any]:
        """返回模型训练状态。"""
        try:
            from models import get_model
        except ImportError:
            from backend.models import get_model  # type: ignore[no-redef]
        return get_model().status()

    @app.post("/api/model/train")
    def model_train() -> dict[str, Any]:
        """重新训练模型。"""
        try:
            from models import reset_model
        except ImportError:
            from backend.models import reset_model  # type: ignore[no-redef]
        return reset_model().status()

    @app.post("/api/model/predict")
    def model_predict() -> dict[str, Any]:
        """返回当前模型的所有区域预测结果。"""
        try:
            from models import get_model
        except ImportError:
            from backend.models import get_model  # type: ignore[no-redef]
        return get_model().predict()

    @app.get("/api/model/importance")
    def model_importance() -> list[dict[str, Any]]:
        """返回特征重要性排序。"""
        try:
            from models import get_model
        except ImportError:
            from backend.models import get_model  # type: ignore[no-redef]
        return get_model().feature_importance()

    @app.get("/api/model/forecast")
    def model_forecast(region_id: str = "naqu-bange", days: int = 30) -> dict[str, Any]:
        """返回指定区域的风险趋势预测。"""
        try:
            from models import get_model
        except ImportError:
            from backend.models import get_model  # type: ignore[no-redef]
        return get_model().forecast(region_id, days=days)

    @app.get("/api/model/evaluation")
    def model_evaluation() -> dict[str, Any]:
        """返回模型评估指标和数据质量报告。"""
        try:
            from models import get_model
        except ImportError:
            from backend.models import get_model  # type: ignore[no-redef]
        return get_model().evaluation()

    @app.get("/api/model/label-info")
    def model_label_info() -> dict[str, Any]:
        """返回模型标签来源说明（规则标签/弱标签/真实标签）。"""
        try:
            from models import get_model
        except ImportError:
            from backend.models import get_model  # type: ignore[no-redef]
        return get_model().label_info()

    @app.get("/api/model/macro-background")
    def model_macro_background() -> dict[str, Any]:
        """宏观背景数据摘要（不参与训练）。"""
        try:
            from models import get_model
        except ImportError:
            from backend.models import get_model  # type: ignore[no-redef]
        return get_model().macro_background()

    # ======================================================================
    # 数据质量 API
    # ======================================================================

    @app.get("/api/data-quality")
    def data_quality() -> dict[str, Any]:
        """返回各表数据质量报告。"""
        try:
            from store import read_table, TABLES
        except ImportError:
            from backend.store import read_table, TABLES  # type: ignore[no-redef]

        report: dict[str, Any] = {"tables": {}, "total": {}}
        total_rows = 0
        total_sample = 0
        total_real = 0
        total_simulated = 0

        for table_name, table_def in TABLES.items():
            rows = read_table(table_name)
            n = len(rows)
            sample_count = sum(1 for r in rows if str(r.get("data_source", "")).lower() == "sample")
            simulated_count = sum(1 for r in rows if str(r.get("data_source", "")).lower() == "simulated")
            real_count = n - sample_count - simulated_count
            if table_name in {
                "insurance_claims", "supply_chain_orders", "supply_chain_payments",
                "post_loan_workflow", "green_performance_metrics",
            }:
                sample_count = sum(
                    1 for r in rows
                    if str(r.get("data_source", "")).lower() == "sample"
                    or str(r.get("is_sample", "")).lower() in ("true", "1", "yes", "t")
                )
                simulated_count = sum(1 for r in rows if str(r.get("data_source", "")).lower() == "simulated")
                real_count = n - sample_count - simulated_count

            # 日期范围
            dates = []
            for r in rows:
                d = r.get("observed_at") or r.get("scene_date") or r.get("imported_at")
                if d:
                    dates.append(str(d)[:10])
            dates = sorted(set(dates))

            # 缺失率：整表字段缺失行占比。部分表包含规划字段，下面会给出字段级提示。
            missing_count = sum(1 for r in rows if any(v is None or v == "" for v in r.values()))
            missing_rate = round(missing_count / max(1, n), 3)

            # 区域数和月份数
            regions = sorted(set(r.get("region_id", "") for r in rows if r.get("region_id")))
            months = set()
            for r in rows:
                d = r.get("observed_at") or r.get("scene_date") or ""
                if len(str(d)) >= 7:
                    months.add(str(d)[:7])

            # 构建 quality_warnings
            qw: list[str] = []
            if sample_count > n * 0.5:
                qw.append(f"样例数据占比 {sample_count}/{n}")
            if real_count == 0:
                qw.append("无真实数据")
            if missing_rate > 0.2 and table_name != "remote_sensing_data":
                qw.append(f"缺失率 {missing_rate:.0%}，部分字段为空")

            # 遥感表专项检查
            field_missing: dict[str, float] = {}
            if table_name == "remote_sensing_data" and n > 0:
                snow_zero = sum(1 for r in rows if str(r.get("snow_cover", "0%")).replace("%","").strip() in ("0", "0%", ""))
                deg_empty = sum(1 for r in rows if str(r.get("degradation_level", "")).strip() in ("", "待评估"))
                cap_empty = sum(1 for r in rows if str(r.get("carrying_capacity_sheep_unit", "")).strip() == "")
                veg_estimated = sum(1 for r in rows if str(r.get("vegetation_cover", "50%")).strip() == "50%")
                for field in ("ndvi", "snow_cover", "degradation_level", "carrying_capacity_sheep_unit", "vegetation_cover"):
                    empty = sum(1 for r in rows if str(r.get(field, "")).strip() in ("", "None", "null"))
                    field_missing[field] = round(empty / max(1, n), 3)

                if snow_zero == n:
                    qw.append("积雪数据尚未接入，snow_cover 全部为默认值 0%")
                elif snow_zero > n * 0.5:
                    qw.append(f"积雪数据覆盖不足，{snow_zero}/{n} 行为默认值")
                if deg_empty == n:
                    qw.append("草地退化等级尚未接入，degradation_level 全部为待评估")
                if cap_empty == n:
                    qw.append("载畜量数据尚未接入，carrying_capacity_sheep_unit 全部为空")
                if veg_estimated > n * 0.5:
                    qw.append("植被覆盖度可能由 NDVI 估算，建议接入独立 FVC 数据")
                # 载畜量来源检查
                cap_demo = sum(1 for r in rows if str(r.get("capacity_is_sample", "false")).lower() in ("true", "1", "yes", "t"))
                cap_derived = sum(1 for r in rows if str(r.get("capacity_derived", "false")).lower() in ("true", "1", "yes", "t"))
                if cap_demo > 0:
                    qw.append("载畜量当前使用样例 NPP 派生数据，仅用于流程演示，待 TPDC NPP 数据审批通过后替换")
                elif cap_derived > 0:
                    qw.append("载畜量由 NPP 衍生估算，非实测值")
                if missing_rate > 0.2 and cap_empty < n:
                    qw.append(f"遥感表存在字段缺失，字段级缺失率见 field_missing_rate")

            report["tables"][table_name] = {
                "label": table_def.get("label", table_name),
                "row_count": n,
                "sample_rows": sample_count,
                "real_rows": real_count,
                "simulated_rows": simulated_count,
                "date_range": [dates[0], dates[-1]] if dates else [],
                "region_count": len(regions),
                "month_count": len(months),
                "missing_rate": missing_rate,
                "field_missing_rate": field_missing,
                "quality_warnings": qw,
            }
            total_rows += n
            total_sample += sample_count
            total_real += real_count
            total_simulated += simulated_count

        report["total"] = {
            "total_rows": total_rows,
            "sample_rows": total_sample,
            "real_rows": total_real,
            "simulated_rows": total_simulated,
            "real_data_ratio": round(total_real / max(1, total_rows), 2),
        }
        return report

    @app.get("/api/import/metadata")
    def import_metadata() -> list[dict[str, Any]]:
        """返回 CSV 导入历史元数据。"""
        meta_file = ROOT / "backend" / "data_store" / "import_metadata.json"
        if meta_file.exists():
            return json.loads(meta_file.read_text(encoding="utf-8"))
        return []

    # ======================================================================
    # 饲草供需宏观参考数据
    # ======================================================================

    @app.get("/api/forage-supply-demand")
    def forage_supply_demand(
        region_cn: str = "", year: int | None = None,
    ) -> list[dict[str, Any]]:
        """返回全国饲草供需宏观数据 (Geodoi DOI: 10.3974/geodb.2024.07.07.V1)。

        此为全国/区域年度宏观统计，不是县域载畜量。
        """
        try:
            from store import read_table
        except ImportError:
            from backend.store import read_table  # type: ignore[no-redef]
        rows = read_table("forage_supply_demand")
        if not rows:
            return rows
        if region_cn:
            rows = [r for r in rows if region_cn in str(r.get("region_cn", ""))]
        if year is not None:
            rows = [r for r in rows if int(r.get("year", 0)) == year]
        return rows

    @app.get("/api/forage-supply-demand/summary")
    def forage_summary() -> dict[str, Any]:
        """饲草供需数据概览。"""
        try:
            from store import read_table
        except ImportError:
            from backend.store import read_table  # type: ignore[no-redef]
        rows = read_table("forage_supply_demand")
        if not rows:
            return {"available": False, "message": "饲草供需数据未导入"}
        regions = sorted(set(r.get("region_cn", "") for r in rows if r.get("region_cn")))
        years = sorted(set(int(r.get("year", 0)) for r in rows if r.get("year")))
        return {
            "available": True,
            "row_count": len(rows),
            "regions": regions,
            "year_range": [min(years), max(years)] if years else [],
            "data_source": "geodoi",
            "doi": "10.3974/geodb.2024.07.07.V1",
            "note": "此为全国/区域年度宏观饲草供需统计，不是县域月度载畜量数据。不参与模型训练，仅作为宏观背景参考。",
        }

    # ======================================================================
    # 管理端独立页面
    # ======================================================================

    @app.get("/admin")
    def admin_page() -> FileResponse:
        target = FRONTEND_DIR / "admin.html"
        return FileResponse(target, headers={"Cache-Control": "no-store"})

    # ======================================================================
    # 404 兜底
    # ======================================================================

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def api_not_found(path: str) -> None:
        raise HTTPException(status_code=404, detail=f"API not found: {path}")

    # ======================================================================
    # 前端静态页面
    # ======================================================================

    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="frontend-assets")
    SLIDE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
    if PUBLIC_DATA_DIR.exists():
        app.mount("/public_data", StaticFiles(directory=PUBLIC_DATA_DIR), name="public-data")

    @app.get("/{path:path}")
    def frontend(path: str = "") -> FileResponse:
        return serve_frontend(path)

    return app


# ============================================================================
# 辅助函数
# ============================================================================


def _filter_by_region(items: list[dict[str, Any]], region_id: str | None) -> list[dict[str, Any]] | dict[str, Any]:
    if not region_id:
        return items
    for item in items:
        if item.get("region_id") == region_id:
            return item
    raise HTTPException(status_code=404, detail="region_id not found")


def load_content_store() -> dict[str, Any]:
    if CONTENT_FILE.exists():
        try:
            store = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
            return {
                "slides": store.get("slides", []),
                "platform": _merge_platform_defaults(store.get("platform")),
                "data_source_configs": store.get("data_source_configs", {}),
            }
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return {"slides": [], "platform": _data["build_platform_data"](), "data_source_configs": {}}


def save_content_store(payload: dict[str, Any]) -> None:
    CONTENT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_active_platform() -> dict[str, Any]:
    store = load_content_store()
    platform = _merge_platform_defaults(store.get("platform"))
    platform["slides"] = store.get("slides", [])
    live = _data["build_platform_data"]()
    for key in (
        "regions", "subjects", "finance", "alerts", "weather", "remote_sensing",
        "risk_assessment", "data_connections", "closed_loop", "model_status", "model_confidence"
    ):
        platform[key] = live.get(key, platform.get(key))
    return platform


def _merge_platform_defaults(platform: Any) -> dict[str, Any]:
    if not isinstance(platform, dict):
        return _data["build_platform_data"]()
    merged = _data["build_platform_data"]()
    merged.update(platform)
    latest = _data["build_platform_data"]()
    for key in ("brand", "modules", "outline", "digital_solution", "data_sources"):
        merged[key] = latest.get(key, merged.get(key))
    return merged


def _get_config_value(configs: dict[str, Any], source_key: str, field: str, default: str = "") -> str:
    cfg = configs.get(source_key, {})
    if not isinstance(cfg, dict):
        return default
    if field in cfg and cfg.get(field) not in (None, ""):
        return str(cfg.get(field))
    extra = cfg.get("extra_config", {})
    if isinstance(extra, dict) and extra.get(field) not in (None, ""):
        return str(extra.get(field))
    return default


def build_slide_banner(data: bytes, target: Path) -> tuple[int, int]:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        target.write_bytes(data)
        return (0, 0)

    with Image.open(BytesIO(data)) as src:
        src = ImageOps.exif_transpose(src).convert("RGB")
        width, height = src.size
        target_ratio = SLIDE_ASPECT_RATIO
        current_ratio = width / height

        if current_ratio >= target_ratio:
            out_h = height
            out_w = round(height * target_ratio)
        else:
            out_w = width
            out_h = round(width / target_ratio)

        banner = ImageOps.fit(src, (out_w, out_h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.55))
        banner.save(target, format="JPEG", quality=97, subsampling=0, optimize=True)
        return out_w, out_h


def serve_frontend(path: str) -> FileResponse:
    requested = path or "index.html"
    if requested not in ADMIN_PAGES and not requested.endswith(
        (".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".json")
    ):
        requested = "index.html"

    target = (FRONTEND_DIR / requested).resolve()
    if FRONTEND_DIR.resolve() not in target.parents and target != FRONTEND_DIR.resolve():
        target = FRONTEND_DIR / "index.html"
    if not target.exists() or target.is_dir():
        target = FRONTEND_DIR / "index.html"

    return FileResponse(target, headers={"Cache-Control": "no-store"})


# ============================================================================
# 应用实例与启动入口
# ============================================================================

app = create_app()


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    run(port=int(os.environ.get("PORT", "8000")))
