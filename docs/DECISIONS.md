# EchoMind 架构决策记录

状态：Accepted / Proposed / Superseded。重要方向变化新增记录，不无痕改写历史。

## ADR-001：建立独立 EchoMind 仓库

- 状态：Accepted
- 日期：2026-07-16
- 决策：在 `E:\开源项目小测试\EchoMind` 新建独立仓库，保留现有 `mind-map` Flask 星图原型不动。
- 原因：旧原型的数据模型、Flask 架构和星图交互均不满足正式产品的导入—证据—Insight—Profile 闭环。独立仓库可避免混淆，也保留原型供视觉参考。
- 后果：不迁移旧业务代码；未来可选择迁移纯视觉资产，但必须重新审查隐私和产品适配性。

## ADR-002：模块化单体 monorepo

- 状态：Accepted
- 决策：后端、前端、文档和测试放在一个仓库；后端为模块化单体。
- 原因：MVP 单用户本地运行，微服务会增加部署、隐私和一致性成本，没有当前收益。

## ADR-003：SQLite + SQLAlchemy + Alembic

- 状态：Accepted
- 决策：MVP 使用 SQLite，所有访问通过 SQLAlchemy 2.x 风格和 Alembic 迁移；避免 SQLite 专有 SQL。
- 原因：降低本地启动门槛，同时保留 PostgreSQL 迁移路径。

## ADR-004：原始文件与数据库分离

- 状态：Accepted
- 决策：原始文件保存在私有 data 目录，数据库保存相对路径、哈希和解析元数据。
- 原因：避免数据库 BLOB 膨胀、支持文件级删除和隔离。代价是备份需同时覆盖 DB 和 data。

## ADR-005：共享 Profile 中间模型

- 状态：Accepted
- 决策：先生成一个 Pydantic `EchoProfileDocument`，Markdown 和 JSON 都由它渲染。
- 原因：防止两种输出格式在章节、证据引用和版本上漂移。

## ADR-006：置信度是版本化启发式分数

- 状态：Accepted
- 决策：置信度保存系统分数、计算因子、公式版本和用户覆盖值；不得描述为概率或模型真值。
- 原因：模型自报数字不可解释，用户需要知道分数来源并可修订。

## ADR-007：MVP 任务使用数据库检查点和进程内 worker

- 状态：Proposed
- 决策：不引入 Redis/Celery；使用 ImportJob/ExtractionRun 持久化状态，单 worker 分批处理。
- 原因：满足本地可恢复需求并避免大型依赖。Phase 1/2 实测 SQLite 并发行为后确认。

## ADR-008：默认 confirmed-only Profile

- 状态：Proposed
- 决策：默认只有 confirmed Insight 进入正式 Profile；用户可在预览中临时包含 proposed，但导出需明确标记。
- 原因：符合人机协作和避免把 AI 候选当真相的原则。需用户确认产品体验。

## ADR-009：真实 WeFlow 格式暂不声称支持

- 状态：Accepted
- 决策：MVP 只建立 Parser 接口、示例适配器和脱敏契约测试；获得真实脱敏样本后再完善。
- 原因：没有样本时猜测格式会制造虚假兼容性。

## 尚未决策

1. 单数据库是否允许多个 profile owner。
2. 是否在 MVP 内加入应用层静态加密。
3. 远程模型调用是否必须逐次确认，还是允许会话级授权。
4. 成功解析后是否默认保留原始文件副本。
5. confirmed-only Profile 默认策略是否符合用户预期。
6. 项目开源许可证。
