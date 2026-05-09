# Prompt — 新增 / 修改 Pydantic 模型

目标：把一段「业务字段描述」转成符合本仓库规范的 Pydantic v2 模型组。

## 你必须遵守

- 文件位置：`app/schemas/<module>.py`，**不**与 ORM 模型放在一起。
- 命名：
  - 入参：`*Request`
  - 出参 / 单元：`*Response` / `*Data`
  - 列表项：`*ListData`
  - 严禁：把 In 与 Out 合成一个类，再用 `Optional` 模拟差异。
- 字段：
  - 必填字段使用 `Field(..., description="中文描述")`
  - 可选字段用 `Optional[T]` 与 `Field(default=None, description=...)`
  - 数值字段加 `ge / le`；字符串加 `min_length / max_length / pattern`；时间用 `datetime`
- 与 ORM 实体兼容时：
  ```python
  class XxxResponse(BaseModel):
      ...
      class Config:
          from_attributes = True
  ```
- `'Y'/'N'` 字段：`Field(..., min_length=1, max_length=1, pattern="^[YN]$", description="..." )`
- 接受字符串空值代替 `None`：用 `field_validator(..., mode="before")`，参考 `HistoryQueryRequest.validate_datetime`

## 你必须产出

1. 完整 `*.py` 文件 / 增量段落
2. 在 `app/schemas/__init__.py` 中**显式 re-export**新模型（参考现有写法）
3. 配套同步 `api_spec/<module>.md`：列出字段 / 类型 / 默认 / 校验

## 强校验

- [ ] 类名后缀符合 In/Out 规则
- [ ] 字段全部带 `description`
- [ ] 没有把同一个类既作请求又作响应
- [ ] 入参不暴露 DB 内部字段（如自增 id、created_by）
- [ ] 出参不带敏感字段（如 token、原始密码）
