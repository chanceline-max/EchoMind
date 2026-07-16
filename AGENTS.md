# EchoMind Agent Guide

本文件约束所有参与 EchoMind 的人和编码代理。若任务说明与本文件冲突，以用户当前明确要求为最高优先级，并在 `docs/DECISIONS.md` 记录重要偏离。

## 每次任务的固定流程

1. 完整阅读 `README.md`、本文件和与任务相关的 `docs/`。
2. 运行 `git status -sb`，检查现有代码、测试和未提交改动。
3. 用一段话说明任务理解、范围与明确不做的内容。
4. 列出计划修改的文件；发现用户改动时不得覆盖或丢弃。
5. 实现最小充分、容易撤销的方案。
6. 运行相关测试、类型检查和静态检查。
7. 汇报实际修改、实际执行的验证及其结果。
8. 明确遗留风险和下一步最合适的单一任务。

## 产品不可违背的约束

- 证据优先：重要 Insight 必须关联 Evidence；Evidence 必须能回到 Message。
- 类型诚实：fact、preference、pattern、inference、hypothesis、contradiction、change 不得混用。
- 用户主权：用户可确认、编辑、驳回、删除 Insight，也可排除 Message。
- 非诊断：不得生成或暗示医疗、精神健康诊断。
- 隐私默认：本地运行、无默认遥测、无默认远程模型调用。
- 原始数据不可逆保护：清洗不得覆盖 `raw_content` 或原始导入文件。
- 不记录敏感正文：日志只包含任务 ID、计数、耗时、状态和安全的错误摘要。
- 模型可替换：业务逻辑不得直接依赖具体模型 SDK。
- 测试离线：默认测试只使用 `MockLLMProvider`，不得要求 API Key 或网络。

## 工程约束

- 后端：Python 3.12、FastAPI、Pydantic、SQLAlchemy、Alembic、pytest、Ruff、mypy。
- 前端：React、TypeScript、Vite、React Router、TanStack Query、Vitest、Playwright。
- SQLite 是 MVP 默认数据库，但数据层不得依赖 SQLite 专有行为。
- 所有持久化时间使用带时区的 UTC；展示层再转换本地时区。
- API、数据库和导出格式都必须有显式版本。
- 不把全部逻辑放入路由、React 页面或单个服务文件。
- 不新增大型依赖，除非任务明确需要并记录原因。
- 不提交真实聊天样本、生成档案、数据库、密钥或用户路径。
- 不用占位实现、吞异常或伪造测试结果冒充完成。

## 测试最低要求

- 新增清洗步骤：单元测试覆盖启用、禁用、边界输入与统计输出。
- 新增 Parser：契约测试、有效样本、无效样本、幂等导入测试。
- 新增 API：成功、校验失败、未找到及隐私相关行为测试。
- 新增抽取流程：使用 Mock provider 验证证据绑定、去重、冲突和幂等。
- 新增前端流程：组件/页面测试；关键用户闭环增加 Playwright 测试。
- 无法运行检查时，必须说明命令、阻塞原因和未验证范围。

## 数据与迁移

- 模型改动必须通过 Alembic 迁移，不直接手改已有数据库。
- 删除敏感数据时，优先真实级联删除；不得用软删除无限期保留正文。
- `metadata` 在 SQLAlchemy 声明式模型中有特殊含义，Python 属性使用 `metadata_json`，数据库列可映射为 `metadata`。
- Schema 变更同步更新 `docs/DATA_MODEL.md`、API 类型和导出 schema。

## 文档同步规则

- 产品范围变化：更新 `PRODUCT_SPEC.md` 和 `ROADMAP.md`。
- 架构边界变化：更新 `ARCHITECTURE.md` 和 `DECISIONS.md`。
- 数据结构变化：更新 `DATA_MODEL.md` 和 `PROFILE_SCHEMA.md`。
- 导入规则变化：更新 `IMPORT_FORMAT.md`。
- 外发数据、日志或保留策略变化：更新 `PRIVACY.md`。
