from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    pass


# 触发 model 注册到 Base.metadata
from . import v2_models
from . import quant_models


__all__ = ["Base", "v2_models", "quant_models"]
