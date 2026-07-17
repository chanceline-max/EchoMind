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
│   │   ├── extraction/          # 分段、窗口、候选、合并、冲突、置信度
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
- 原始文件存储在本地私有 data 目录；数据库保存受控相对路径、哈希和元数据。
- 阶段 2 已建立八个核心证据链模型和一个普通 `conversation_participants` 关联表，不创建 Service/Repository、任务、审计或复杂调度模型。阶段 3 在 `parsers/` 内建立独立 Canonical Schema、确定性 Registry 及 JSON/CSV/固定文本 Parser；阶段 4 在 `cleaning/` 内建立 `ParsedChatFile → CleanedChatFile` 的可组合纯内存 Pipeline。两个模块均不依赖 ORM 或 Session。ImportJob 在阶段 5、ExtractionRun 在阶段 7 按真实用例加入。
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

上图是后续阶段 5 的完整目标链路。阶段 4 当前实际边界为：

```text
explicit local Path → extension/signature selection → raw-byte SHA-256
→ format parse → Canonical Schema → cross-record validation
→ deep-copy cleaning state → fixed Cleaner Pipeline → CleanedChatFile
→ derived-reference validation → cleaning statistics/errors
```

- Registry 先按扩展名筛选，再最多读取 8192 字节做可靠签名识别；无匹配和多匹配都明确失败，显式 Parser 名称可覆盖自动选择。
- Parser 输出与 ORM 解耦；不创建 SourceFile/Conversation/Message，不查询重复文件，不提交事务。
- JSON、CSV 和固定纯文本使用同一集中跨记录验证：会话/参与者/消息唯一性、sender/reply 引用、profile owner 数量、aware 时间、范围和统计一致性。
- 输出消息按 `(timestamp, source_order)` 稳定排序；`source_order` 保留文件原始位置。strict 立即失败；lenient 跳过可恢复记录后，统一 validation 继续级联移除引用已缺失目标的消息，直到结果不存在悬空 reply，且绝不通过清空 reply 引用保留消息。
- 错误仅返回安全 basename 和 JSON Pointer/行号等结构位置；Parser 不记录正文。WeFlow 在取得授权脱敏样本前始终不可用。
- Cleaning 每次从 `raw_content` 初始化派生 `normalized_content`；Parser 输入、raw、原消息数量、source_order 和 reply 引用保持不变。固定顺序为保守空白、附件占位、系统分类、撤回分类、精确重复、URL、可选脱敏、排除、AnalysisUnit，再执行最终验证和统计。
- 重复判定键为同一会话内的发送者、消息类型、空白处理后正文、精确时间和 reply 目标。第一条保留，后续只设置 `duplicate_of_source_message_id`。URL/脱敏在其后运行，不能制造伪重复。
- 系统分类只认 `message_type=system`、显式布尔 metadata 和固定 `[SYSTEM]`；撤回分类使用严格完整匹配的中英文占位规则。分类和排除分离，系统/撤回/重复默认排除但始终保留原消息和引用。
- 脱敏默认关闭；显式开启时只处理确定性 email、带 `+` 的国际 phone_like、IPv4 和受限简单自定义正则。它不是完整 PII 检测，不推断敏感属性，不把原值写入操作、统计、错误或日志。
- AnalysisUnit 不是 Message，只按有序原消息 ID 派生。同会话、同发送者、相邻未排除 text 在 120 秒/8 条/2000 字符默认上限内合并；发送者、类型、排除、时间、source_order、数量、字符或新 reply 上下文都会切断。ID 使用 Pipeline 版本、会话和有序消息 ID 的 SHA-256 稳定派生。
- CleaningOperation 只保存 cleaner/version、操作类型、受控变更字段及计数/规则/类别；Cleaning Statistics 从最终标记、操作和 AnalysisUnit 重算。任何 Cleaner 异常、消息数量变化、悬空派生引用或统计漂移都会使整次清洗失败，不返回部分结果。

- 先写入临时隔离区，验证通过后再移动到正式私有目录。
- 原始文件 SHA-256 是 SourceFile 的全局幂等键；Parser 名称和版本作为解析追溯元数据保存。阶段 3/5 若需要同一源文件的多次解析运行，再引入单独的运行记录，不复制 SourceFile。
- 单个文件导入在数据库事务边界内提交；大文件按会话分批并记录检查点。

### 4.2 抽取

```text
eligible messages → deterministic chunks → overlapping context windows
→ provider candidate schema → evidence validation → merge/deduplicate
→ contradiction links → confidence factors → proposed insights
```

- 不将完整聊天记录一次性交给模型。
- Provider 只接收显式构造的窗口和结构化输出 schema。
- 模型返回的 message ID 必须在当前窗口内，否则候选无效。
- `extraction_version + provider + prompt_version + input_hash` 构成幂等键。

### 4.3 Profile 生成

只读取允许进入档案的 Insight。正式导出默认仅包含 confirmed；用户显式启用后可纳入达到阈值的 proposed，但必须逐条标记为未确认。系统按 schema 生成中间结构，再由两个 renderer 分别输出 Markdown 和 JSON，避免语义漂移。

## 5. LLMProvider 边界

```python
class LLMProvider(Protocol):
    provider_id: str

    async def extract_insights(
        self,
        request: ExtractionRequest,
    ) -> ExtractionResponse: ...
```

- `MockLLMProvider`：固定、确定性、离线，用于测试和演示。
- `OpenAICompatibleProvider`：只定义配置和 HTTP 适配边界；用户主动启用后使用。
- `LocalModelProvider`：定义本地模型进程/HTTP 边界，不绑定某个运行时。
- Provider 不得自行读数据库或文件；不得记录 prompt 正文。

## 6. API 设计原则

- 前缀 `/api/v1`；OpenAPI 是前后端契约来源。
- 阶段 1 已实现 `GET /api/v1/health`，固定返回 `status`、`service`、`version` 三个公开字段；响应由 Pydantic Schema 校验，不包含环境配置。
- 列表 API 使用稳定排序和游标/分页，避免一次返回全部消息。
- 错误使用统一 problem detail：`code`、`message`、`request_id`、安全的 `details`。
- 修改 Insight 使用乐观并发版本号，防止覆盖用户刚完成的编辑。
- 导出和远程模型调用是显式用户动作，不通过页面加载隐式触发。

开发模式下前后端跨端口通信只允许配置中的精确 origin（默认 `http://127.0.0.1:5173` 和 `http://localhost:5173`），不得使用通配 CORS。生产式本地构建优先由同一 origin 提供前端和 API。

当前前端仍只使用 `VITE_API_BASE_URL` 请求健康接口，不使用持久化请求缓存、浏览器本地存储、Service Worker、Router 或 Query Client。阶段 3 没有新增前端业务界面。

## 7. 可恢复与幂等

- 阶段 5/7 引入的 ImportJob/ExtractionRun 保存阶段、游标、版本、错误代码和统计。
- 每个批次先计算输入哈希；完成后提交检查点。
- 重试从最后成功批次继续，并通过唯一约束阻止重复数据。
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
- 阶段 2 只提供归档、排除和有效性字段；归档和排除的事务性状态传播属于后续服务，尚未实现。原始文件、raw_content 和 file_hash 不得改变。
- 历史 Profile 内容不被静默改写；后续查看必须展示证据失效状态，新的正式导出排除 `evidence_state=invalid` 的结论。
- 未来物理删除必须先计算依赖图和数量、向用户展示、二次确认，再由专用 Service 执行。
