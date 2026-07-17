# EchoMind 架构决策记录

状态：Accepted / Proposed / Superseded。重要方向变化新增记录，不无痕改写历史。

## ADR-001：建立独立 EchoMind 仓库

- 状态：Accepted
- 日期：2026-07-16
- 决策：建立独立的 `EchoMind/` 仓库，保留仓库外的历史 `mind-map` Flask 星图原型不动。
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
- 原因：避免数据库 BLOB 膨胀并支持存储隔离。代价是备份需同时覆盖 DB 和 data；MVP 仍不提供不可逆物理删除功能。

## ADR-005：共享 Profile 中间模型

- 状态：Accepted
- 决策：先生成一个 Pydantic `EchoProfileDocument`，Markdown 和 JSON 都由它渲染。
- 原因：防止两种输出格式在章节、证据引用和版本上漂移。

## ADR-006：置信度是版本化启发式分数

- 状态：Accepted
- 决策：置信度保存系统分数、计算因子、公式版本和用户覆盖值；不得描述为概率或模型真值。
- 原因：模型自报数字不可解释，用户需要知道分数来源并可修订。

## ADR-007：需要恢复的后续任务使用数据库检查点和进程内 worker

- 状态：Proposed（ImportJob 部分由 ADR-019 取代）
- 决策：不引入 Redis/Celery；阶段 7 若确有抽取恢复需求，再以 ExtractionRun 和进程内 worker 分批处理。阶段 5 同步导入不创建 ImportJob。
- 原因：只为已出现的恢复需求引入持久化任务，避免空模型和复杂调度。

## ADR-008：默认 confirmed-only Profile

- 状态：Accepted
- 决策：默认只有 confirmed Insight 进入正式 Profile；用户可在预览中临时包含 proposed，但导出需明确标记。
- 原因：符合人机协作和避免把 AI 候选当真相的原则。显式设置可纳入达到阈值的 proposed，但必须逐条标记未确认。

## ADR-009：真实 WeFlow 格式暂不声称支持

- 状态：Accepted
- 决策：MVP 只建立 Parser 接口、示例适配器和脱敏契约测试；获得真实脱敏样本后再完善。
- 原因：没有样本时猜测格式会制造虚假兼容性。

## ADR-010：后端统一采用 src layout

- 状态：Accepted
- 日期：2026-07-16
- 决策：后端代码路径统一为 `backend/src/echomind/`，测试位于 `backend/tests/`。
- 原因：避免 README、AGENTS 和架构文档出现两个包布局，也避免从仓库根目录意外导入未安装源码。

## ADR-011：MVP 不提供不可逆物理删除

- 状态：Accepted
- 日期：2026-07-16
- 决策：MVP 使用归档、排除分析和有效性状态；核心证据链外键使用限制删除语义，不使用无提示数据库级联删除。
- 原因：数据不丢失和证据可追溯优先于立即擦除。Evidence 失效必须传播到 Insight 和 Profile。
- 后果：应用内暂不提供“彻底删除”；未来实现前必须设计影响预览、二次确认、事务删除和备份提示。

## ADR-012：阶段 2 只实现八个核心数据模型

- 状态：Accepted
- 日期：2026-07-16
- 决策：阶段 2 只实现 SourceFile、Conversation、Participant、Message、Evidence、Insight、InsightEvidence、ProfileSnapshot。
- 原因：它们足以建立证据链。ImportJob、ExtractionRun、InsightRevision、InsightRelation、ProfileSnapshotInsight 分别推迟到实际使用它们的阶段。

## ADR-013：MVP 单 workspace 单 profile owner

- 状态：Accepted
- 日期：2026-07-16
- 决策：一个本地 workspace 只分析一个 profile owner；可以有多个聊天 Participant。
- 原因：避免在 MVP 中引入多档案隔离、权限和交叉证据语义。

## ADR-014：远程 Provider 按分析任务显式启用

- 状态：Accepted
- 日期：2026-07-16
- 决策：默认 Mock；每次创建使用远程 Provider 的分析任务时，界面显示 Provider 和发送范围并由用户确认。任务内部批次不重复弹窗。
- 原因：兼顾明确授权与批处理可用性。启用远程 Provider 不是离线 MVP 验收前提。

## ADR-015：应用层静态加密推迟到 MVP 后

- 状态：Accepted
- 日期：2026-07-16
- 决策：MVP 不实现应用层数据库/文件加密，明确建议整盘加密并显示限制。
- 原因：跨平台密钥存储、恢复和备份会显著扩大范围；在没有可靠密钥生命周期前，仓促加密可能造成不可恢复的数据丢失。

## ADR-016：阶段 2 数据库边界与可移植性

- 状态：Accepted
- 日期：2026-07-16
- 决策：阶段 2 使用同步 SQLAlchemy、应用侧 UUID4 字符串、统一 `UTCDateTime` 和 SQLite `PRAGMA foreign_keys=ON`；八个 ORM 模型之外仅增加普通 `conversation_participants` 关联表。
- 决策：`SourceFile.file_hash` 单列全局唯一；Parser 信息只作追溯元数据。Insight 当前只保存通用 `confidence`、`reasoning_basis` 和 `alternative_explanations`，不提前实现阶段 8 的分数因子、公式版本或 hypothesis 数值阈值。
- 原因：这些选择足以约束阶段 2 的证据链，同时避免数据库专用 UUID、重复源文件、虚假的语义保证和提前设计置信度算法。
- 后果：Conversation/Participant 的 ORM 多对多集合是只读关系，关联写入留给后续明确的 Service，避免 ORM 自动删除关联行绕过 RESTRICT。Message 回复目标是否属于同一 Conversation，以及 Insight 七类语义、证据状态传播和 Profile 失效传播，也必须由后续可测试 Service 实现；当前数据库不声称已保证这些业务规则。

## ADR-017：阶段 3 使用精确、数据库无关的 Parser 契约

- 状态：Accepted
- 日期：2026-07-17
- 决策：Parser 采用仓库内确定性 Registry 和独立 Pydantic Canonical Schema。只支持文档精确定义的通用 JSON、固定表头 CSV 和固定纯文本 1.0；格式识别使用扩展名与最多 8192 字节轻量签名，不使用注册顺序兜底或模糊日期/编码识别。
- 决策：原始字节 SHA-256 以 64 KiB 分块计算；消息输出按 `(timestamp, source_order)` 稳定排序，Parser 阶段的 `normalized_content` 必须等于 `raw_content`。strict/lenient 只影响可恢复的记录；lenient 对缺失 reply 目标执行级联跳过直到引用闭合，不清空引用伪造有效消息；整体结构和 Canonical 不一致始终失败。
- 决策：Windows 使用标准库 `zoneinfo` 时增加 `tzdata` 运行依赖，保证 IANA 时区在不同机器上有一致数据源。WeFlow 在获得授权且彻底脱敏样本前保持 `available=false` 并返回 `sample_required`。
- 原因：精确契约可测试、可解释且不会伪造第三方兼容性；独立 Canonical 层防止解析阶段绕过阶段 2 的证据链约束或产生数据库副作用。Windows Python 通常不内置 IANA 时区库，单靠标准库 API 无法可靠解析 `Asia/Shanghai`。
- 后果：阶段 3 不提供上传、数据库写入、清洗或真实 WeFlow 映射。新格式必须通过独立 Parser、可靠签名、完整文档和合成/脱敏契约测试加入。

## ADR-018：阶段 4 使用固定、非破坏性的内存 Cleaning Pipeline

- 状态：Accepted
- 日期：2026-07-17
- 决策：Cleaning 只接受阶段 3 `ParsedChatFile`，每次从 `raw_content` 创建独立 `CleanedChatFile`。固定顺序为保守空白、附件占位、系统/撤回分类、精确重复、URL、显式启用的脱敏、排除、AnalysisUnit，最后校验引用并重算统计。
- 决策：重复和排除只增加派生标记，不删除或合并 Message；AnalysisUnit 只引用原消息。重复检测必须先于 URL/脱敏。新 reply 开启新单元，随后同发送者相邻普通消息可在阈值内加入该单元。
- 决策：脱敏默认关闭，只提供 email、明确国际 phone_like、IPv4 与受限简单自定义正则；自定义规则限制数量/长度，禁止分组、回溯引用、无界重复、零长度匹配和超过 100 的有限量词，不声称完整 PII 检测。
- 原因：可重建 raw、确定顺序、操作追溯和保守规则优先于语义“聪明度”；固定内部 Pipeline 足以服务当前阶段，无需插件市场、数据库、网络或第三方 NLP 依赖。
- 后果：Cleaning 模块本身仍是纯内存；阶段 5 由 ImportService 显式编排并持久化输出。用户导入后的排除操作使用数据库 Message ID，不使用可能跨会话重复的 source ID。

## ADR-019：阶段 5 使用同步、临时文件、单事务导入

- 状态：Accepted
- 日期：2026-07-17
- 决策：`POST /api/v1/imports` 在一个请求中完成分块上传、原始字节 SHA-256、Parser、Cleaner 和单事务入库；不创建 ImportJob。原上传文件只存在于随机请求级临时目录，结束后清理，`SourceFile.storage_path` 默认为 null。
- 决策：写 API 在 CORS 之外校验精确 Origin；敏感响应 `no-store`。前端使用 React Router、仅内存 TanStack Query 和 XHR 上传进度，不使用持久化浏览器存储。
- 原因：当前限制下同步处理能够提供真实状态和原子失败语义；任务表或伪造服务端阶段进度没有当前恢复用例。
- 后果：刷新不能恢复失败请求；成功结果通过 SourceFile ID 重读。真正需要后台恢复时再设计 ImportJob。

## ADR-020：阶段 6 使用同步、严格结构化且双重授权的 Provider 边界

- 状态：Accepted
- 日期：2026-07-18
- 决策：业务层只依赖同步 `LLMProvider.generate_structured(LLMRequest, response_schema)` 和 EchoMind 自有 Schema。默认 Provider 是完全离线、确定性的 Mock；远程实现使用可注入 Transport 的最小 OpenAI-compatible HTTP，不引入厂商 SDK；Local 实现保持 `available=false`。
- 决策：远程调用必须同时满足服务端 `remote_enabled` 与逐请求 `remote_consent`。endpoint/model/SecretStr Key 只来自服务端 Settings；endpoint 默认 HTTPS、禁止 URL 凭据/fragment/重定向，本地 HTTP 必须显式开启且仅限 loopback。请求先经过字符/消息/Schema/输出预算，响应先经过解压后字节上限，再做纯 JSON 与 strict Pydantic 验证。
- 决策：只对 408、429、500、502、503、504、超时和临时连接错误执行无 jitter 的有限指数退避；测试注入 no-op Sleeper 和 `httpx.MockTransport`。Provider 不读 ORM、数据库、Repository、文件或全局聊天内容，不缓存或记录 prompt/响应。
- 原因：在阶段 7 构造真实分析窗口前，先把供应商耦合、默认离线、授权、SSRF 基础边界、资源上限和不可信输出验证做成独立、可测试的基础设施。
- 后果：字符预算不是 tokenizer；OpenAI-compatible 服务的 JSON Schema 能力仍可能不同；HTTPS DNS 重绑定未由应用层完全防御；阶段 6 没有模型调用 API、前端配置、Insight 或 Evidence。

## 尚未决策

1. hypothesis 的初始置信度上限及各类型阈值，需要阶段 8 用性质测试确定。
2. 获得授权脱敏 WeFlow 样本后的真实字段映射。
3. 项目开源许可证。
