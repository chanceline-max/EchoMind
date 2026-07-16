# EchoMind 分阶段开发路线

每个阶段只在验收条件满足后进入下一阶段。阶段编号描述依赖关系，不是承诺日期。

## Phase 0：产品设计与工程约束（当前）

交付：README、AGENTS、产品/架构/数据/隐私/导入/Profile/决策文档、路线图、MVP 验收标准和基础目录。

验收：文档无明显冲突；范围、非目标、隐私边界、风险和下一任务明确；没有业务功能冒充完成。

## Phase 1：工程骨架与质量门禁

交付：

- FastAPI/Pydantic/SQLAlchemy/Alembic 后端骨架。
- React/TypeScript/Vite/Router/TanStack Query 前端骨架。
- pytest、Ruff、mypy、Vitest、Playwright 基础配置。
- `/api/v1/health`、统一错误结构、配置和安全日志适配器。
- SQLite 首个迁移、CI 或本地一键检查脚本。

验收：全新环境可启动；所有空骨架检查通过；无网络/API Key；日志测试证明敏感字段被过滤。

## Phase 2：导入、解析与标准化

交付：Parser 协议、注册表、JSON/CSV/Text Parser、WeFlow 框架、SourceFile/ImportJob/Conversation/Participant/Message 持久化、合成样本。

验收：三种格式有效/无效测试通过；重复导入幂等；错误可定位；原文件 hash 与 parser version 有记录。

## Phase 3：清洗 Pipeline 与消息审阅

交付：可配置清洗步骤、统计、会话/消息 API 和 UI、raw/normalized 对照、排除/恢复。

验收：每步独立测试；关闭步骤不改变输入；raw 永不覆盖；日志无正文；大样本分页稳定。

## Phase 4：Mock 抽取、证据与置信度

交付：LLMProvider 协议、Mock provider、远程/本地骨架、分段窗口、候选 schema、Evidence、去重、冲突、置信度 v1、可恢复 ExtractionRun。

验收：离线完成确定性抽取；无 Evidence 的候选被拒绝；重复运行幂等；分数因子可解释；故障重试不重复 Insight。

## Phase 5：Insight 人机审阅

交付：列表筛选、详情证据、确认、编辑、驳回、置信度覆盖、修订历史、排除相关消息后的影响提示。

验收：并发编辑有冲突保护；所有状态转换测试通过；驳回内容不进入 Profile；证据可回到原消息。

## Phase 6：EchoProfile 生成与 MVP 收口

交付：共享中间 schema、Markdown/JSON renderer、Profile 预览、快照与导出、设置页、关键 E2E 测试、隐私审查清单。

验收：满足 `PRODUCT_SPEC.md` 的全部 12 条 MVP 验收标准；README 在全新环境验证；仓库无敏感数据。

## MVP 之后（未承诺）

- 使用真实 WeFlow 脱敏样本完善适配器。
- 评估本地模型运行时和应用层加密。
- 时间演化和更完整的矛盾工作流。
- 在证据和规模确实需要后再评估全文/向量检索。
- 云化、多用户、移动端等必须重新做威胁模型和产品验证。

## 当前下一单一任务

执行 **Phase 1 的后端工程骨架**：只建立 FastAPI 配置、健康检查、统一错误、SQLAlchemy session、空数据库迁移及质量工具，不同时开始前端或导入器。
