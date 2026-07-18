# EchoMind 分阶段开发路线

以下阶段与仓库采用的 Codex 任务顺序一致。一次只执行一个阶段；本阶段验收未通过，不进入下一阶段。阶段编号表示依赖关系，不是发布日期。

## 阶段 0：审查设计文档（已完成）

范围：审查 README、AGENTS、产品、架构、数据、隐私和路线文档；修正范围、追溯、隐私、过度设计、离线运行和验收可测性问题。

验收：文档形成一致的单用户、本地优先 MVP；明确类型规则、删除规则、离线 Mock 闭环、自动化验收矩阵和下一任务；不编写业务代码。

## 阶段 1：初始化工程骨架（已完成）

范围：backend/frontend 基础工程、依赖与配置、健康检查、最简单首页、测试与静态检查、`.env.example`、本地启动说明。前端调用后端健康检查。

明确不做：数据库业务表、迁移、Parser、模型调用、身份认证、Docker、复杂 UI 库。

验收：后端和前端可本地启动；健康检查端到端可见；后端测试/Ruff/mypy、前端测试/类型检查/构建实际通过。

## 阶段 2：实现核心数据库模型（已完成）

范围：SourceFile、Conversation、Participant、Message、Evidence、Insight、InsightEvidence、ProfileSnapshot；普通 Conversation/Participant 关联表；同步 SQLAlchemy、Pydantic、Alembic 和 Session 工厂。本阶段没有真实用例，因此不创建 Service/Repository。

验收：迁移可在空 SQLite 上升级并回滚；约束、索引、UTC 时间、metadata 命名、Evidence 追溯和受控删除测试通过。不建立通用 Repository 框架。

## 阶段 3：实现通用聊天导入器（已完成）

范围：插件式 Parser、canonical schema、JSON/CSV/纯文本、文件 hash、导入统计、合成样本；WeFlow 只返回明确未支持。

验收：每个 Parser 的正常、空、编码异常、字段缺失、无效时间、重复、不支持类型和基本大文件测试通过；Parser 不写数据库和日志正文。

## 阶段 4：实现数据清洗 Pipeline（已完成）

范围：独立可配置 Cleaner、统计、幂等、raw 不变性；连续短消息使用派生分析单元/分组，不删除原消息。

验收：每步启用/禁用、边界、幂等和 raw 不变性测试通过；统计和日志不含正文。

## 阶段 5：实现导入 API 和前端导入页面（已完成）

范围：上传、识别、解析、清洗、入库、任务状态、错误、统计、重复提示、会话/消息分页和排除操作；至少一个 E2E。

验收：文件类型/大小限制、路径安全、错误脱敏、失败恢复、重复导入、分页和排除流程测试通过。不实现 Insight。

## 阶段 6：实现 LLM Provider 抽象（已完成）

范围：Base/Protocol、确定性 Mock、可配置 OpenAI-compatible、LocalModel 接口骨架；结构化输出、Pydantic 校验、超时和有限重试。

验收：默认 Mock；远程双重授权、endpoint 基础安全、预算、响应大小、纯 JSON/Pydantic 验证、有限重试和安全错误均由断网测试覆盖；Key 仅从服务端环境读取；无 Key/prompt/响应泄露；SDK 类型不进入业务层。

## 阶段 7：实现候选 Insight 抽取（已完成）

已实现：显式会话/时间选择、Profile Owner 约束、单会话有限窗口、匿名局部别名、固定 Prompt、严格 Candidate Schema、七类最低机械规则、本地 Evidence、Insight/Evidence 精确指纹、窗口级事务、安全报告和重复运行恢复。未引入 ExtractionRun、HTTP API、前端页面、最终置信度、语义合并或 Profile。

验收：AI 候选只能 proposed；无 Evidence、窗口外 message ID 或无效输出不能进入正式 Insight；Mock 重跑幂等。

## 阶段 8：实现可解释置信度算法（已完成）

已实现：`confidence-1.0` 精确公式、六个正向 Evidence 因子、普通类型相反证据惩罚、contradiction bilateral balance、七类 base/depth/cap、最低规则、evidence_state 重算、content-free 输入指纹、固定解释、逐 Insight 短事务和幂等重算。阶段 7 同步持久化 `explicit_self_report`；旧数据安全默认 false。

验收：因子边界、公式、类型 cap、最低规则、Evidence 状态、指纹、隐私、持久化和重算测试通过；model_confidence 不参与；单条弱证据不能越过最低规则；分数明确是机械支撑强度而非心理学概率。

## 阶段 9：实现 Insight 审核界面（已完成）

已实现：列表/筛选/详情、匿名 Evidence、原消息跳转和高亮、受限编辑、确认/驳回/恢复/supersede、乐观并发、追加式 Revision，以及 Message 排除对 Evidence/Insight/Confidence 的事务传播。

验收：迁移回环、状态转换、并发 409、Revision 不可更新、Evidence 传播、Confidence 集成、前端运行时验证及阶段 5/9 E2E 通过；没有物理删除、Profile 或模型调用 API。

## 阶段 10：生成 EchoProfile（已完成）

已实现：confirmed-only 选择、共享 `EchoProfileDocument`、稳定 I/E 引用、确定性 Markdown/JSON、安全转义、Source/Generation Fingerprint、Document Hash、不可变 ProfileSnapshot、动态 stale、Profile API/UI 与显式导出。

验收：只纳入 confirmed；valid/partial/invalid 分区明确；两种格式语义一致、可追溯、稳定并通过 schema；相同来源/选项复用快照；阶段 5/9/10 E2E 通过。当前无 proposed Profile、编辑、删除、PDF/Word 或云分享。

## 阶段 11：端到端 MVP 验收（已完成）

范围：按照 `PRODUCT_SPEC.md` 验收矩阵执行完整离线闭环，生成 `MVP_AUDIT.md`。只修复阻断闭环或涉及数据安全的问题。

验收：后端、前端、E2E、类型、格式、构建和迁移检查有真实结果；重复流程幂等；所有失败项和风险被记录。

已实现：确认并修复普通用户无法触发分析的 BLOCKER，新增受限同步分析 API/UI、空库完整闭环 E2E、路由与追溯审计测试、代表性负载测量及 `MVP_AUDIT.md`。未引入后台任务、新模型、新评分算法或阶段 12 质量重构。

## 阶段 12：代码质量审查

范围：按 Critical/High/Medium/Low 审查数据、隐私、安全、时区、级联、模型验证、Evidence、幂等、模块边界、前端状态和文档一致性；只修复 Critical/High。

验收：审查报告更新，相关测试重新通过，没有借机重写项目。

## MVP 之后（未承诺）

- 使用真实授权且脱敏的 WeFlow 样本完善适配器。
- 评估本地模型运行时和应用层静态加密。
- 更完整的时间演化与矛盾工作流。
- 证据证明需要后再评估全文或向量检索。
- 云化、多用户、移动端必须重新做威胁模型和产品验证。

## 当前下一单一任务

执行 **阶段 12：代码质量审查**。先由项目所有者决定是否开始；不得把阶段 11 的发布限制或许可证选择自动视为已解决。
