"""CRUD 层共享工具函数"""


def _rows_to_dicts(rows) -> list[dict]:
    """将 SQLAlchemy ORM 对象列表转为 dict 列表"""
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]
