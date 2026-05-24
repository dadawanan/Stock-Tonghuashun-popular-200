from __future__ import annotations

import logging

from fastapi import FastAPI

from stock_service.api.dependencies import lifespan
from stock_service.api.routes.analysis import router as analysis_router
from stock_service.api.routes.auth import router as auth_router
from stock_service.api.routes.health import router as health_router
from stock_service.api.routes.popularity import router as popularity_router
from stock_service.api.routes.query import router as query_router
from stock_service.quant.api.routes import strategies, backtest, sim_trading, feedback, pending_orders


logger = logging.getLogger("stock-api")


app = FastAPI(title="Stock Analysis API", lifespan=lifespan)


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
