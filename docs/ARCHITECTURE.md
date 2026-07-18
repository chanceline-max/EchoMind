# EchoMind 系统架构

## 1. 架构目标

MVP 使用模块化单体 monorepo。核心目标是本地运行、领域边界清晰、处理任务可恢复、模型可替换，以及 SQLite 到 PostgreSQL 的可迁移性。当前不采用微服务、消息队列集群或图数据库。

## 2. 推荐目录结构

```text
EchoMind/
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── migrations/
│   ├── src/echomind/
│   │   ├── main.py
│   │   ├── api/                 # FastAPI 路由、依赖和 API schema
│   │   ├── core/                # 配置、日志、安全路径、错误类型
│   │   ├── db/                  # SQLAlchemy session 和具体数据访问
│   │   ├── models/              # SQLAlchemy 模型
│   │   ├── schemas/             # Pydantic 请求、响应和领域传输对象
│   │   ├── parsers/             # Parser 协议及 JSON/CSV/Text/WeFlow
│   │   ├── cleaning/            # 可组合、可统计、可配置的清洗步骤
│   │   ├── extraction/          # 分段、窗口、候选、Evidence 与精确幂等
│   │   ├── confidence/          # 确定性因子、公式、解释和幂等重算
│   │   ├── providers/           # LLMProvider 及 Mock/兼容/本地骨架
│   │   ├── profiling/           # Markdown/JSON 档案生成与校验
│   │   └── services/            # 导入、抽取、审阅和档案用例
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── contract/
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── app/                 # Router、QueryClient、全局错误边界
│   │   ├── api/                 # 类型化 API client
│   │   ├── features/            # imports、conversations、insights、profiles
│   │   ├── components/          # 可复用基础组件
│   │   ├── pages/
│   │   ├── styles/
│   │   └── types/
│   └── tests/
├── docs/
├── samples/
│   ├── synthetic/
│   └── schemas/
├── scripts/
└── tests/
    ├── e2e/
    └── contracts/
```

## 3. 运行时组件

```text
React UI
   │ HTTP /api/v1
FastAPI API
   ├── Application services
   │    ├── Import pipeline ── Parser registry ── Cleaning pipeline
   │    ├── Extraction pipeline ── LLMProvider
   │    └── Profile generator
   ├── Concrete services/repositories (按后续真实用例加入)
   ├── SQLAlchemy / SQLite
   └── Private local file store
```

- FastAPI 只负责传输、校验和调用应用服务，不承载业务流程。
- 业务服务通过按聚合划分的具体数据访问函数/类操作数据库，不直接在路由中写 SQL。MVP 不建立通用 Repository 框架。
- 阶段 5 不长期保存原上传文件；数据库保存 SHA-256、处理版本、统计和消息级不可变原文。预留的 `storage_path` 默认为 null。
- 阶段 3 的 Parser 与阶段 4 的 Cleaner 保持独立于 ORM；阶段 5 的 service/repository 将两者编排进同步、单事务写入。当前没有 ImportJob、审计或复杂调度模型。
- 数据库层使用同步 SQLAlchemy 2.x；主键由应用生成 UUID4 字符串。统一 `UTCDateTime` 拒绝 naive datetime、写前转 UTC，并为 SQLite 读取结果恢复 UTC 时区。
- Alembic 是正式建表路径；应用导入和 FastAPI 启动均不自动执行迁移。测试数据库是隔离的临时 SQLite 文件。
- MVP 后续任务处理使用数据库状态和进程内单 worker；单进程重启后从检查点恢复。暂不引入 Celery/Redis。

## 4. 关键流程

### 4.1 导入

```text
Upload → hash/size gate → Parser selection → parse/validate
       → canonical messages → cleaning pipeline → transaction commit
       → import summary
```

上图是阶段 5 已实现的同步链路。Parser/Cleaner 的独立处理边界为：

```text
explicit local Path → extension/signature selection → raw-byte SHA-256
→ format parse → Canonical Schema → cross-record validation
→ deep-copy cleaning state → fixed Cleaner Pipeline → CleanedChatFile
→ derived-reference validation → cleaning statistics/errors
```

- Registry 先按扩展名筛选，再最多读取 8192 字节做可靠签名识别；无匹配和多匹配都明确失败，显式 Parser 名称可覆盖自动选择。
- Parser/Cleaner 本身与 ORM 解耦；阶段 5 ImportService 负责重复查询和事务提交。
- JSON、CSV 和固定纯文本使用同一集中跨记录验证：会话/参与者/消息唯一性、sender/reply 引用、profile owner 数量、aware 时间、范围和统计一致性。
- 输出消息按 `(timestamp, source_order)` 稳定排序；`source_order` 保留文件原始位置。strict 立即失败；lenient 跳过可恢复记录后，统一 validation 继续级联移除引用已缺失目标的消息，直到结果不存在悬空 reply，且绝不通过清空 reply 引用保留消息。
- 错误仅返回安全 basename 和 JSON Pointer/行号等结构位置；Parser 不记录正文。WeFlow 在取得授权脱敏样本前始终不可用。
- Cleaning 每次从 `raw_content` 初始化派生 `normalized_content`；Parser 输入、raw、原消息数量、source_order 和 reply 引用保持不变。固定顺序为保守空白、附件占位、系统分类、撤回分类、精确重复、URL、可选脱敏、排除、AnalysisUnit，再执行最终验证和统计。
- 重复判定键为同一会话内的发送者、消息类型、空白处理后正文、精确时间和 reply 目标。第一条保留，后续只设置 `duplicate_of_source_message_id`。URL/脱敏在其后运行，不能制造伪重复。
- 系统分类只认 `message_type=system`、显式布尔 metadata 和固定 `[SYSTEM]`；撤回分类使用严格完整匹配的中英文占位规则。分类和排除分离，系统/撤回/重复默认排除但始终保留原消息和引用。
- 脱敏默认关闭；显式开启时只处理确定性 email、带 `+` 的国际 phone_like、IPv4 和受限简单自定义正则。它不是完整 PII 检测，不推断敏感属性，不把原值写入操作、统计、错误或日志。
- AnalysisUnit 不是 Message，只按有序原消息 ID 派生。同会话、同发送者、相邻未排除 text 在 120 秒/8 条/2000 字符默认上限内合并；发送者、类型、排除、时间、source_order、数量、字符或新 reply 上下文都会切断。ID 使用 Pipeline 版本、会话和有序消息 ID 的 SHA-256 稳定派生。
- CleaningOperation 只保存 cleaner/version、操作类型、受控变更字段及计数/规则/类别；Cleaning Statistics 从最终标记、操作和 AnalysisUnit 重算。任何 Cleaner 异常、消息数量变化、悬空派生引用或统计漂移都会使整次清洗失败，不返回部分结果。

- 上传按块写入随机命名的请求级临时目录；成功、失败或取消均清理，不移动到长期原文件目录。
- 原始文件 SHA-256 是 SourceFile 的全局幂等键；Parser 名称和版本作为解析追溯元数据保存。阶段 3/5 若需要同一源文件的多次解析运行，再引入单独的运行记录，不复制 SourceFile。
- 单个文件的 SourceFile、Conversation、Participant、关联和 Message 在一个事务内原子提交；当前同步 MVP 不分批提交，也不伪造检查点恢复。

### 4.2 抽取

```text
eligible messages → deterministic chunks → overlapping context windows
→ provider candidate schema → minimum evidence validation
→ local Evidence binding → exact fingerprint reuse → proposed insights
```

- 阶段 7 的内部 `ExtractionRequest` 必须显式给出 1–100 个会话，空集合不代表全库；时间范围必须带时区。会话按去重后的请求顺序处理，消息按 `source_order, id` 排序。
- 每个会话必须未归档且恰好有一个 Profile Owner。只选择时间范围内 `excluded_from_analysis=false`、未归档、未删除且时间有效的 Message；不会读取 SourceFile 原文、`raw_content`、路径、metadata 或 cleaning operations。
- 每窗只含一个会话，默认 40 条/12000 字符，单条上下文最多 4000 字符并在限额内追加 `[TRUNCATED]`，相邻窗口最多重叠 4 条。窗口 ID 是抽取版本、会话数据库 ID、有序消息数据库 ID 和窗口参数版本的 SHA-256，不含正文。
- Provider 只接收 `m001...` 消息别名、`c001` 会话别名、`PROFILE_OWNER/OTHER_n` 匿名角色、时间、类型、截断后的 `normalized_content` 和同窗回复别名。数据库/源 ID、参与者姓名、文件名和路径不进入 payload。
- Prompt 固定为 `candidate-extraction-1.0`；禁止诊断、MBTI、单消息 pattern、窗外引用和 confirmed 输出。Provider 使用独立 Candidate Schema，最多返回请求允许的候选数。
- 候选先执行七类最低机械规则；无效候选单独拒绝，合法候选继续。模型只提供局部 Evidence 引用；本地从完整 `normalized_content` 生成最多 500 字符 excerpt，不使用模型 excerpt。
- Insight 指纹由抽取版本、类型、受控类别、保守空白规范化 statement 和有效期生成；Evidence 指纹由消息 ID、Evidence 类型、excerpt SHA-256 和指纹版本生成。第一版不做 embedding、语义相似度或跨窗口自动合并。
- Provider 调用前关闭读取 Session，不在网络期间持有数据库事务。每窗合法候选在一个短事务内整体提交或回滚；前序成功窗口保留。`stop_on_window_error` 决定失败后停止或继续，重复运行通过唯一指纹恢复。
- 新候选固定 `proposed/valid`，`confidence=0.0`、`confidence_version=unscored` 表示阶段 8 尚未评分；`model_confidence` 单独保存。复用既有 Insight 时不覆盖 title/statement/status，可补充未关联 Evidence。
- `ExtractionReport` 仅含 ID、计数、状态和受控错误，不含正文、excerpt、Prompt、Provider 响应或路径。阶段 7 没有 ExtractionRun、分析 HTTP API、前端页面、最终置信度或 Profile。

### 4.3 置信度重算

```text
explicit Insight IDs + as_of → content-free database snapshot
→ evidence_state → six evidence factors + contradiction factors
→ type minimum rule → confidence-1.0 formula/cap
→ fixed explanation → one-Insight short transaction
```

- `ConfidenceCalculationRequest` 必须明确给出 1–1000 个 Insight UUID 和 aware `as_of`，去重后保持顺序；不支持空列表代表全库。默认只处理 proposed/confirmed，rejected/superseded 只有显式 include 才评分。
- 读取层只把 Insight 类型、自述标记、有效期、抽取版本和评分字段，以及 Evidence 有效性/role/相关度、Message 时间/会话/sender、Participant Owner 标记转换为不可变特征。数学层不读取 raw/normalized content、excerpt、title、statement、姓名、文件名或路径。
- `evidence_state` 在每次计算前由关联 Evidence 重算。invalid 固定 0；partial 只用有效 Evidence 计算主要因子并通过 `valid_ratio` 降低 quality。最低规则失败同样固定 0，但不改变类型或 status。
- 普通类型使用 explicitness、quantity、temporal span、跨会话分布、quality、recency 六个正向因子和 contradiction penalty；contradiction 使用 bilateral balance 代替 explicitness 且不应用该惩罚。七类 base、depth penalty 和 cap 固定在 `confidence-1.0`，Decimal 中间值按 ROUND_HALF_UP 四位小数持久化。
- `model_confidence` 只作来源审计，公式权重为 0 且不进入输入指纹。指纹包含版本、`as_of` 和全部结构化评分输入；相同指纹、版本、`as_of` 且 evidence_state 一致时不执行 UPDATE。
- 每个 Insight 单独读取、纯计算并在短写事务内只更新评分字段与 evidence_state；不修改 title、statement、status、model_confidence、Evidence 或关联。`force_recalculate` 可以刷新计算时间但不创建 History/Run 记录。
- `ConfidenceReport/Error` 只含 ID、状态、计数、规则码和安全值；解释由固定本地模板生成，明确它是机械支撑强度而非科学概率。阶段 8 没有独立评分 API、用户 override、ConfidenceHistory 或 Profile。

### 4.4 Insight 审核与证据传播

- `GET /api/v1/insights` 使用 Evidence 聚合子查询和 EXISTS 筛选，保证多条 Evidence 不复制 Insight；详情匿名返回 PROFILE_OWNER/OTHER、受限 excerpt、失效原因和原消息链接。
- PATCH/confirm/reject/restore/supersede 先比较 `expected_revision`，再验证状态；条件 UPDATE 只允许一个并发写成功。成功操作与一条 append-only `InsightRevision` 在同一事务提交，409 不修改 Insight 或历史。
- 普通 PATCH 不能修改 status、confidence、Evidence 或抽取来源。title/statement/category/review_note 不重算；insight_type/有效期、restore 和活动 Insight 的 Evidence 变化调用 caller-owned Confidence 事务入口。
- Message 的最终排除状态决定 `source_message_excluded` 是否存在。只有全部 Evidence 失效原因清空时才恢复 valid；活动 Insight 重算 confidence，rejected/superseded 只更新 evidence_state。传播失败整体回滚。

### 4.4 Profile 生成

只读取允许进入档案的 Insight。正式导出默认仅包含 confirmed；用户显式启用后可纳入达到阈值的 proposed，但必须逐条标记为未确认。系统按 schema 生成中间结构，再由两个 renderer 分别输出 Markdown 和 JSON，避免语义漂移。

## 5. LLMProvider 边界

```python
class LLMProvider(Protocol):
    provider_name: ClassVar[str]
    provider_version: ClassVar[str]
    supports_remote_calls: ClassVar[bool]
    supports_structured_output: ClassVar[bool]

    def generate_structured(
        self,
        request: LLMRequest,
        response_schema: type[ResponseModelT],
    ) -> LLMResult[ResponseModelT]: ...
```

- `LLMRequest` 只允许独立 system instruction 和 `user` 消息；不支持 assistant history、tool/function、stream 或自由文本返回。`LLMResult[T]` 的 output 已经由调用方 Pydantic Schema 以 strict 模式验证。
- `MockLLMProvider` 是默认值：固定 fixture/scenario、确定性、离线，不读取 API Key，用于测试和演示。
- `OpenAICompatibleProvider` 使用项目已有 httpx 的最小 Chat Completions JSON Schema 请求，不引入厂商 SDK。Factory 只构造对象、不探测连接；Transport 禁止重定向，测试注入 `httpx.MockTransport`。
- 远程调用在 Provider 内再次要求 `remote_enabled=true` 和逐请求 `remote_consent=true`，任一缺失都在预算与网络调用前失败。endpoint/model/Key 只来自服务端 Settings，调用方不能覆盖 endpoint。
- endpoint 默认 HTTPS；HTTP 只允许显式开启的 localhost/127.0.0.1/::1。禁止非 HTTP(S)、相对 URL、URL 凭据、fragment 和超长 URL。当前不声称防御 HTTPS DNS 重绑定。
- 预算按 system/user 字符、消息数、单条字符、Schema 字符和输出 token 上限确定性预检；字符数不等于 token 数。远程响应按 httpx 解压后的字节数在 JSON 解析前限制为集中配置值。
- 只重试 408、429、500、502、503、504、超时和临时连接错误；0.1/0.2/... 秒指数退避无 jitter 且可注入 Sleeper。授权、其他 4xx、重定向、预算、响应过大、JSON 和 Schema 错误不重试。
- 结构化输出严格要求纯 JSON，不剥离 Markdown code fence，不修复或执行模型输出。错误只保留代码、请求 ID、次数、状态和受控计数/位置，不保留 prompt、响应、Header、Key、endpoint 或本机路径。
- `LocalModelProvider` 当前 `available=False` 并返回 `local_provider_not_configured`；不会下载权重、扫描端口、启动线程或子进程。
- Provider 包不得自行读数据库、ORM、Repository、上传文件或聊天文件；阶段 6 没有 Provider HTTP API、Insight/Evidence/Profile 业务和前端模型页面。

## 6. API 设计原则

- 前缀 `/api/v1`；OpenAPI 是前后端契约来源。
- 阶段 1 已实现 `GET /api/v1/health`，固定返回 `status`、`service`、`version` 三个公开字段；响应由 Pydantic Schema 校验，不包含环境配置。
- 阶段 5 提供导入、会话和消息接口；阶段 9 增加 Insight 列表/详情/Revision、审核动作及消息定位。没有 Insight、Evidence 或 Revision DELETE 路由。
- 列表 API 使用稳定排序和 limit/offset 分页，避免一次返回全部消息。
- 错误使用统一安全结构：`error_code`、`message`、`recoverable`、可选安全文件名/结构位置和 `details`。
- 修改 Insight 使用乐观并发版本号，防止覆盖用户刚完成的编辑。
- 导出和远程模型调用是显式用户动作，不通过页面加载隐式触发。

开发模式下前后端跨端口通信只允许配置中的精确 origin（默认 `http://127.0.0.1:5173` 和 `http://localhost:5173`），不得使用通配 CORS。生产式本地构建优先由同一 origin 提供前端和 API。

当前前端使用 React Router 和仅内存的 TanStack Query；聊天 query 的 `staleTime=0` 且短期 GC，不使用持久化插件、浏览器本地存储或 Service Worker。上传进度由 XHR 原生 progress 提供，服务端解析/清洗不伪造百分比。

## 7. 可恢复与幂等

- 阶段 5 没有 ImportJob；请求失败整体回滚，刷新后只读取已成功的 SourceFile。异步恢复有真实需求时再设计任务模型。
- 输入先计算原始字节哈希；全局唯一约束和事务共同阻止重复数据。
- 错误摘要不得包含消息正文、文件原文或 API Key。

## 8. 可观测性

MVP 使用结构化本地日志，只记录：时间、级别、request/job ID、阶段、计数、耗时、错误类型。禁止记录聊天正文、证据 excerpt、完整路径、prompt、响应正文、密钥和身份信息。

## 9. 安全边界

- 默认监听 `127.0.0.1`，不自动开放局域网。
- 限制文件大小、扩展名和解析深度；不执行导入文件中的内容。
- 防止 ZIP bomb、CSV 公式注入和路径穿越；MVP 若不支持压缩包则明确拒绝。
- 前端展示原文时默认文本转义；不渲染导入 HTML。
- 远程 Provider 配置仅从环境变量/本地密钥配置读取，不入库明文、不写日志。
- 浏览器端不得把聊天正文、Evidence、Insight 或 Profile 写入 localStorage、IndexedDB、Service Worker cache 或持久化查询缓存。

## 10. 已知架构权衡

- SQLite 适合本地单用户，但并发写有限；MVP 通过单 worker 和短事务控制。
- 进程内任务简单但不适合多进程部署；在需要云化前再评估外部队列。
- 原始文件与数据库分开保存增加备份复杂度，但避免数据库膨胀并利于删除策略。
- 不引入向量库会限制语义检索规模；MVP 先用确定性分段和结构化索引验证闭环。

## 11. 删除与证据有效性传播

```text
archive/exclude Message
→ mark linked Evidence invalid
→ recompute Insight.evidence_state
→ mark affected ProfileSnapshot stale/invalid
→ prevent invalid conclusion from current export
```

- MVP 没有证据链实体的物理删除 API。
- SourceFile、Conversation、Message、Evidence、Insight 之间使用限制删除语义，不使用数据库级联删除。
- 阶段 9 已实现 Message 排除/恢复的事务性 Evidence 与 Insight 传播；ProfileSnapshot 失效传播属于阶段 10。原始文件、raw_content、normalized_content、reply 和 file_hash 不得改变。
- 历史 Profile 内容不被静默改写；后续查看必须展示证据失效状态，新的正式导出排除 `evidence_state=invalid` 的结论。
- 未来物理删除必须先计算依赖图和数量、向用户展示、二次确认，再由专用 Service 执行。
