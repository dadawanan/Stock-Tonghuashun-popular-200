from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stock_service.api.dependencies import lifespan
from stock_service.api.routes.analysis import router as analysis_router
from stock_service.api.routes.auth import router as auth_router
from stock_service.api.routes.health import router as health_router
from stock_service.api.routes.popularity import router as popularity_router
from stock_service.api.routes.query import router as query_router
from stock_service.quant.api.routes import strategies, backtest, sim_trading, feedback, pending_orders, market, optimizer


logger = logging.getLogger("stock-api")


# 从环境变量读取允许的前端域名，支持多个域名（逗号分隔）
# 示例: ALLOWED_ORIGINS=http://localhost:8001,http://101.35.255.200:8001
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:8001,http://101.35.255.200:8001")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]

logger.info(f"允许的前端域名: {allowed_origins}")


app = FastAPI(title="Stock Analysis API", lifespan=lifespan)

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # 允许的来源
    allow_credentials=True,          # 允许携带凭证（cookies）
    allow_methods=["*"],             # 允许所有 HTTP 方法
    allow_headers=["*"],             # 允许所有请求头
)


@app.get("/")
async def root() -> dict[str, str]:
    """浏览器直接打开 / 时给出指引（否则默认 404 易被误认为服务未启动）。"""
    return {
        "service": "Stock Analysis API",
        "docs": "/docs",
        "health": "/api/health",
    }


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(popularity_router)
app.include_router(analysis_router)
app.include_router(query_router)
app.include_router(strategies.router)
app.include_router(backtest.router)
app.include_router(sim_trading.router)
app.include_router(feedback.router)
app.include_router(pending_orders.router)
app.include_router(market.router)
app.include_router(optimizer.router)
