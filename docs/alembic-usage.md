# Alembic 数据库迁移使用指南

## 基本概念

Alembic 是 SQLAlchemy 的数据库迁移工具。ORM 模型变更后，自动生成 SQL 迁移脚本，保证所有环境（本地/测试/生产）的数据库结构一致。

## 常用命令

```bash
# 修改 ORM 模型后，自动生成迁移脚本
alembic revision --autogenerate -m "描述变更内容"

# 应用所有未执行的迁移
alembic upgrade head

# 回滚一步
alembic downgrade -1

# 回滚到指定版本
alembic downgrade <revision_id>

# 查看当前数据库版本
alembic current

# 查看迁移历史
alembic history

# 检查 ORM 和数据库是否有差异
alembic check
```

## 工作流程

### 1. 修改 ORM 模型

在 `src/stock_service/db/models/` 下修改模型，例如添加字段：

```python
# v2_models.py
class StockMaster(Base):
    # ... 现有字段 ...
    new_field: Mapped[str | None] = mapped_column(VARCHAR(64))  # 新增
```

### 2. 生成迁移

```bash
alembic revision --autogenerate -m "add new_field to stock_master"
```

Alembic 会对比 ORM 模型和数据库现状，自动生成迁移脚本到 `alembic/versions/`。

### 3. 检查生成的迁移

```bash
# 查看最新生成的迁移文件
ls -t alembic/versions/ | head -1
```

确认迁移内容正确，特别是：
- 新增表/列是否正确
- 删除操作是否安全
- 数据迁移逻辑是否需要手动补充

### 4. 应用迁移

```bash
alembic upgrade head
```

### 5. 提交迁移文件

迁移文件应提交到 Git，保证团队成员和 CI 能同步。

## 数据库连接

Alembic 自动从项目的 `settings.py` 读取数据库连接（通过 `alembic/env.py`）。

- `APP_ENV=dev` → 连接本地测试库（`TEST_DB_*`）
- `APP_ENV=prod` → 连接生产库（`DB_*`）

## 注意事项

- **不要手动修改已提交的迁移文件**，应生成新的迁移来修正
- **生产环境执行前先在测试库验证**
- **包含数据迁移的脚本**需要手动编写 `op.execute()` 语句
- **autogenerate 不检测**：表重命名、列重命名（会当作删旧建新处理）
