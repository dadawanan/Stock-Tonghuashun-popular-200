from __future__ import annotations

import logging

from fastapi import FastAPI

from stock_service.api.dependencies import lifespan
from stock_service.api.routes.analysis import router as analysis_router
from stock_service.api.routes.health import router as health_router
from stock_service.api.routes.popularity import router as popularity_router
from stock_service.api.routes.query import router as query_router


logger = logging.getLogger("stock-api")


app = FastAPI(title="Stock Analysis API", lifespan=lifespan)
app.include_router(health_router)
app.include_router(popularity_router)
app.include_router(analysis_router)
app.include_router(query_router)
