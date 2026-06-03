"""Celery application configuration."""

from celery import Celery

from stock_service.infrastructure.config.settings import settings

celery = Celery("stock_service")

celery.config_from_object(
    {
        "broker_url": settings.redis_url,
        "result_backend": settings.redis_url,
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "timezone": "Asia/Shanghai",
        "task_track_started": True,
        "task_acks_late": True,
        "worker_prefetch_multiplier": 1,
    }
)

celery.autodiscover_tasks(["stock_service.quant"])
