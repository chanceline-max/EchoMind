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

- 状态：Superseded by ADR-024
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

## ADR-021：阶段 7 使用单会话窗口、本地 Evidence 与精确指纹

- 状态：已接受。
- 决策：抽取只接受显式会话列表和可选 aware 时间范围；每个会话必须恰好一个 Profile Owner。只选未排除、未归档、未删除且时间有效消息，按请求会话顺序及 `source_order, id` 构造单会话窗口。默认窗口 40 条/12000 字符，单条 4000 字符、重叠最多 4 条，确定性前缀截断使用 `[TRUNCATED]`。
- 决策：Provider 仅看到 `mNNN`/`c001` 局部别名、`PROFILE_OWNER/OTHER_n` 匿名角色及受限 `normalized_content`。Prompt 与抽取版本固定为 `candidate-extraction-1.0`；Candidate Schema 与 ORM 分离，并执行七类最低机械证据约束。模型不能提供 Evidence excerpt，本地 excerpt 上限为 500 字符。
- 决策：Insight 指纹按版本、类型、类别、仅折叠空白的 statement 和有效期计算；Evidence 指纹按消息 ID、Evidence 类型、excerpt SHA-256 和版本计算。第一版不做大小写折叠、embedding 或语义合并。旧记录 fingerprint 可为 NULL；新对象由 Service 强制提供，唯一索引允许 SQLite 多个 NULL。
- 决策：新候选固定 `proposed/valid`、`confidence=0.0`、`confidence_version=unscored`，模型自评分离保存。Provider 调用期间不持有数据库事务；每个窗口最多一次成功提交，失败整窗回滚，前序窗口保留。同步恢复依靠指纹，不创建 ExtractionRun。
- 原因：单会话窗口降低误归因并简化局部 Evidence 白名单；本地 excerpt 防止模型伪造证据；精确指纹可解释、可测试且不会覆盖用户编辑；窗口短事务适配 SQLite，并保持阶段 7 无队列、无长期运行模型。
- 后果：当前不能跨窗口/跨会话做语义聚合，机械规则不能证明独立事件或心理学真实性；远程 Provider 经授权后仍会收到当前窗口 `normalized_content`；没有分析 API、UI、最终置信度或 Profile。

## ADR-022：阶段 8 使用 content-free、版本化的 confidence-1.0

- 状态：Accepted
- 日期：2026-07-19
- 决策：最终 confidence 只由本地结构化 Evidence 特征确定性计算。普通类型使用固定 base，加 explicitness、quantity、temporal span、跨会话分布、quality、recency 六个正向因子，再减类型 depth penalty 和相反证据惩罚；contradiction 用 bilateral balance 代替 explicitness 且不应用相反证据惩罚。七类 cap 固定为 fact 0.95、preference 0.90、pattern 0.85、inference 0.80、hypothesis 0.60、contradiction 0.90、change 0.85。
- 决策：中间标准化因子先按 Decimal `ROUND_HALF_UP` 固定到四位，再进入公式；最终值同样固定四位。该策略使持久化因子可以直接复算最终值，避免平台浮点显示差异。原 `PRODUCT_SPEC.md` 的“初始公式建议”由本 ADR 的精确 `confidence-1.0` 取代。
- 决策：`model_confidence` 权重为 0，不进入输入指纹。评分层不读取正文、excerpt、title、statement 或姓名；输入指纹只覆盖版本、`as_of`、Insight 的结构字段和 Evidence/Message/Owner 特征。reasoning/alternative 文本不进入指纹，仅用“是否存在”布尔值复核旧 inference/hypothesis 数据。
- 决策：评分前重算 evidence_state；invalid 或类型最低规则失败时 confidence=0，保留 Insight 且不修改 status。contradiction 单侧 Evidence 使用 `contradiction_roles_incomplete`，仍持久化 0 分和解释，不自动改类型。
- 决策：每个 Insight 单独短事务；相同 fingerprint、版本、`as_of` 和 evidence_state 默认不 UPDATE。`force_recalculate` 只覆盖同一行，不创建 ConfidenceRun/History。阶段 8 不提供 HTTP API、审核 UI、Profile 或用户 override。
- 原因：Evidence 驱动的机械分数比模型自评更可追溯、可测试、可版本化；content-free 数学层减少正文泄露面，也使 title/statement 的用户编辑不会意外改变分数。
- 后果：权重是第一版产品规则，不是经过统计校准的科学概率；跨会话数量只是证据分布，不代表真实社会关系多样性。未来若调整权重必须新增 confidence 版本，不能无痕改写 1.0。

## ADR-023：阶段 9 使用乐观并发、追加式审核历史与原因集合传播

- 状态：Accepted
- 日期：2026-07-20
- 决策：Insight 当前行保存单调 `revision_number`、最近审核字段和可空 supersede 目标；每次用户或系统审核写入必须以条件 UPDATE 领取下一个 revision，并在同一事务追加不可更新/删除的 `InsightRevision`。旧 `expected_revision` 返回 409，不自动重放或覆盖。
- 决策：普通编辑只开放 title、statement、category、insight_type、有效期和 review_note；status 使用显式动作。title/statement/category/note 不触发 confidence，类型/有效期、restore 和活动 Insight 的 Evidence 变化通过 caller-owned 事务入口重算。model_confidence、抽取指纹和 Evidence 不可由审核 PATCH 修改。
- 决策：Evidence 使用 `invalidation_reasons_json` 组合原因。Message 最终不可分析时加入 `source_message_excluded`；恢复时仅移除该原因，全部原因清空后才恢复 valid。传播同时更新相关 Insight 并追加 system Revision，任一步失败整体回滚。
- 决策：审核 API/UI 默认本地、敏感响应 no-store、浏览器查询仅内存；Evidence 参与者只显示匿名角色。rejected/superseded 不删除 Insight、Evidence 或历史，不提供物理删除 API。
- 原因：单用户本地 SQLite 仍可能有两个标签页并发编辑；条件 revision 比最后写入获胜更可解释。原因集合避免消息恢复错误覆盖其他失效来源，append-only 历史让用户和系统传播都可追溯。
- 后果：当前没有批量审核、多用户 actor 身份、用户 confidence override、直接 Evidence 编辑或 Profile。SQLite 写入仍应保持短事务；Profile 对 Evidence 失效的处理留给阶段 10。

## ADR-024：阶段 10 使用 confirmed-only 单一文档与不可变指纹快照

- 状态：Accepted
- 日期：2026-07-21
- 决策：阶段 10 只支持 `confirmed-only-1.0`；proposed、rejected、superseded 不进入 Profile，confidence 不作纳入门槛。ADR-008 中 proposed 预览/导出的例外不再属于 MVP。
- 决策：一个严格 `EchoProfileDocument` 同时驱动 Markdown 和 JSON；正文排序后分配 I 编号，去重 Evidence 稳定分配 E 编号。references 默认不复制 excerpt，excerpts 必须显式选择并二次提醒。
- 决策：`profile-source-1.0` 覆盖当前审核与证据来源，`profile-generation-1.0` 覆盖来源、选项和 renderer 版本并建立唯一索引，`profile-document-sha256` 校验规范化 JSON。Document Hash 计算时将自身字段规范为空字符串，避免自引用。
- 决策：ProfileSnapshot 原子保存双渲染、选项、安全 manifest、指纹和计数，ORM 拒绝 update/delete。历史来源变化只在读取时动态返回 current/stale/source unavailable 和安全 reason code，不回写正文或 Hash。
- 决策：Profile 生成不调用 Provider、不访问网络、不读取 raw_content/Participant 姓名/文件名/路径。API 只提供生成、分页读取、详情及显式 Markdown/JSON 下载，不提供 PATCH/DELETE。
- 原因：用户审核状态必须是档案入口的唯一真值；共享结构和三层指纹使语义一致、幂等、完整性和 stale 都可测试；不可变历史避免证据变化静默重写过去。
- 后果：`generated_as_of` 是 generation options 的一部分；相同来源但不同该值可形成不同历史快照。当前没有 proposed Profile、Profile 编辑、Snapshot 删除、PDF/Word、云分享或公开链接；这些都需新的产品和隐私决策。

## ADR-025：阶段 11 以薄同步分析入口闭合用户流程

- 状态：Accepted
- 日期：2026-07-18
- 决策：把“已存在内部 Extraction/Confidence，但普通用户无法触发”定为 MVP BLOCKER。新增 `GET /analysis/capabilities`、`POST /analysis` 和 `/analysis` 页面；入口只接受明确 Conversation ID、可选带时区范围、停止策略和逐请求 remote consent。
- 决策：Provider 名称、模型、endpoint、Key、Prompt、窗口参数、抽取版本和 Confidence 权重全部由服务端固定；生产默认 Mock 仍返回空候选。应用工厂只为自动测试提供显式 Provider Factory 注入，不把 fixture 变成运行时设置。
- 决策：分析层不创建 AnalysisRun/ExtractionRun。Provider 调用仍在事务外；Extraction 保持窗口短事务，Confidence 保持单 Insight 短事务。抽取成功而评分部分失败时保留 Insight，并返回失败计数和受控错误。
- 原因：这是闭合导入→分析→审核→Profile 的最小改动，同时保持 local-first、可追溯和既有版本化算法边界。
- 后果：分析是同步请求，没有后台恢复、进度百分比、跨窗口语义聚合或独立评分 API；大范围或远程调用的延迟由当前 HTTP 请求承担。

## 尚未决策

1. 获得授权脱敏 WeFlow 样本后的真实字段映射。
2. 项目开源许可证。
