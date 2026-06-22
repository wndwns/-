"""
Vercel Serverless 入口 — 工银牧融 API
将所有 /api/* 请求转发到 FastAPI app
"""
import sys, os

# 将项目根目录和 backend 目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from backend.server_v3 import app
