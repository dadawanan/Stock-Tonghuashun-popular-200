# Prompt — 新增 / 修改 SQLAlchemy 表模型

目标：在 `app/db/` 下新增 / 修改 ORM 模型，保持 utf8mb4、明确主键、与既有命名一致。

## 你必须遵守

- 位置：`app/db/<entity>.py`；一个文件一张表（除非语义上确实是一对一关联）。
- 文件顶部：`from app.db.database import Base`，**禁止**直接 `from sqlalchemy.ext.declarative import declarative_base` 自建 `Base`。
- 表设置：

  ```python
  __table_args__ = {
      'mysql_charset': 'utf8mb4',
      'mysql_collate': 'utf8mb4_unicode_ci',
  }
  ```

- 主键：
  - 业务键（`wafer_id / template_id`）作主键时长度 ≥ `String(100)`，`nullable=False`
  - 没有合适业务键时，使用 `id = Column(Integer, primary_key=True, autoincrement=True)`
- 字段约定：
  - 状态 `'Y'/'N'`：`Column(String(1), comment="...")`
  - 时间：`Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)`（`update_time`）或 `default=datetime.now`（`create_time`）
  - 浮点：`Column(Float, ...)`；金额 / 高精度数值用 `Numeric` 而非 `Float`
  - 路径 / URL：`Column(String(1024), comment="...")`
  - **必须** `comment=` 用中文描述每一列
- **禁止**在 ORM 类上写业务方法（保持纯结构）。

## 你必须产出

1. 新模型文件
2. 如表会被路由直接命中，对应的 Pydantic Out 模型加 `from_attributes = True`
3. 如老库已存在数据，提供一份 `web/migrations/<NNNN>_<desc>.py` 迁移脚本（参考 `migrations/` 既有文件）
4. 在 `architecture.md` 第 1 节图示中加上新表，并在 `api_spec/<module>.md` 注明「数据来源」

## 强校验

- [ ] 表名 snake_case
- [ ] 主键字段 `nullable=False`
- [ ] 所有字段都带 `comment`
- [ ] `__table_args__` 含 utf8mb4 charset / collate
- [ ] 没有跨表外键约束（本仓库刻意避开 FK 以兼容历史数据）
