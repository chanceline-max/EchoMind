# EchoMind 数据模型

## 1. 通用约定

- 主键使用 UUID4 字符串，避免依赖数据库自增和 SQLite 专有类型。
- API 和领域层只接受带时区 datetime。持久层使用统一 `UTCDateTime` 类型：拒绝 naive datetime、写入前转换 UTC、SQLite 读取时恢复 UTC tzinfo，并通过迁移测试验证。
- JSON 扩展字段命名为数据库列 `metadata`；SQLAlchemy Python 属性使用 `metadata_json`。
- 核心枚举在数据库中保存稳定小写字符串，并由 Pydantic/领域枚举校验。
- MVP 不提供不可逆物理删除 API；归档、排除分析和状态标记不得改变原始文件、`raw_content` 或 `file_hash`。
- 核心证据链外键禁止使用无提示 `ON DELETE CASCADE`；默认 `RESTRICT`，由应用服务维护状态传播。
- 所有外键和唯一约束都通过 Alembic 管理。

## 2. 阶段 2 最小模型边界

阶段 2 只实现完成 `SourceFile → Conversation → Message → Evidence ↔ Insight → ProfileSnapshot` 证据链所需的八个模型：

1. SourceFile
2. Conversation
3. Participant
4. Message
5. Evidence
6. Insight
7. InsightEvidence
8. ProfileSnapshot

ImportJob、ExtractionRun、InsightRevision、InsightRelation 和 ProfileSnapshotInsight 不在阶段 2 创建：

- ImportJob：阶段 5 采用同步请求且没有恢复需求；仅在后续出现真实异步/恢复用例时再评估。
- ExtractionRun：阶段 7 通过确定性窗口、精确指纹和窗口级事务满足同步恢复，不创建运行表；仅在后续出现持久任务状态需求时再评估。
- InsightRevision、InsightRelation：阶段 9 审核和 supersede 需要时加入。
- ProfileSnapshotInsight：阶段 10 生成快照并验证追溯时加入。

不得为这些后续模型提前创建空表或伪实现。阶段 2 使用普通 SQLAlchemy association table `conversation_participants` 表达 Conversation 与 Participant 的多对多关系；它没有独立 ORM 领域类或业务层，不算第九个模型。

## 3. 阶段 2 实体关系

```text
SourceFile 1 ── * Conversation
Conversation * ── * Participant (conversation_participants)
Conversation 1 ── * Message
Participant 1 ── * Message
Message 1 ── * Evidence
Insight * ── * Evidence (InsightEvidence)
ProfileSnapshot stores versioned output (links added in stage 10)
```

## 4. 核心表

### SourceFile

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| id | UUID string | PK |
| filename | string | 仅原文件名，不保存客户端绝对路径 |
| file_type | string | json/csv/text/weflow/unknown |
| file_hash | string | SHA-256，全局唯一 |
| storage_path | nullable string | 预留受控相对路径；阶段 5 默认为 null，不长期保存原上传文件 |
| byte_size | integer | 非负 |
| imported_at | datetime | UTC |
| parser_name | string | 解析器稳定 ID |
| parser_version | string | 幂等和重跑依据 |
| status | enum | pending/ready/failed/archived |
| archived_at | datetime nullable | 归档时间；不删除原文件 |
| metadata_json | JSON | Python 属性；数据库列名为 metadata |

唯一约束：`file_hash`。相同原始字节不会因 Parser 名称或版本不同而重复创建 SourceFile；未来重跑解析的版本信息不通过复制源文件记录表达。

应用接收上传后先对临时原始字节计算 `file_hash`，再解析和清洗。阶段 5 在请求结束时删除上传临时副本；`SourceFile` 保留哈希、字节数、版本和统计，消息级 `raw_content` 原样入库。如未来允许保留原文件，必须由用户显式启用并使用受控相对路径。

### Conversation

id、source_file_id、platform、source_conversation_id、title、started_at、ended_at、archived_at、metadata_json。`(source_file_id, source_conversation_id)` 唯一；`ended_at >= started_at`；`source_file_id` 使用 `ON DELETE RESTRICT` 并建立索引。

### Participant

id、canonical_name、aliases(JSON array)、is_profile_owner、created_at、metadata_json。MVP 允许每个本地档案只有一个 owner，但阶段 2 不建立跨 workspace 的全局唯一约束，也不实现身份合并或联系人推断。

`conversation_participants` 使用 `(conversation_id, participant_id)` 联合主键，两个外键都是 `ON DELETE RESTRICT`。阶段 2 的 ORM 多对多 relationship 为只读视图，避免 SQLAlchemy 在删除已加载 Conversation/Participant 时自动先删关联行而绕过 RESTRICT；后续写入由明确的 Service 语句完成。

### Message

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID string | PK |
| conversation_id | UUID | FK |
| source_message_id | string | 源 ID；缺失时生成确定性 ID |
| sender_id | UUID | FK Participant |
| timestamp | datetime nullable | 无法解析时保留错误元数据 |
| sequence_index | integer | 同会话稳定顺序 |
| source_order | integer | Parser 原始记录顺序，不因跳过记录重编号 |
| source_location | string nullable | 安全结构位置，不得包含绝对路径 |
| message_type | enum | text/image/file/audio/video/system/recalled/other/unknown |
| raw_content | text | 永不被清洗覆盖 |
| normalized_content | text | 可从 raw + pipeline 版本重建 |
| reply_to_message_id | UUID nullable | 自引用 FK |
| duplicate_of_message_id | UUID nullable | 指向同会话更早消息的自引用 FK |
| is_system_message | boolean | Cleaner 分类结果 |
| is_recalled_message | boolean | Cleaner 分类结果 |
| is_deleted | boolean | 源数据标记，不代表物理删除 |
| excluded_from_analysis | boolean | 用户控制 |
| exclusion_reason | string nullable | 不保存多余敏感正文 |
| exclusion_reasons_json | JSON array | 完整可解释排除原因 |
| archived_at | datetime nullable | 应用归档状态；原文仍保留 |
| normalization_version | string | 清洗版本 |
| cleaning_operations_json | JSON array | 规范化操作追溯，不保存额外正文 |
| metadata_json | JSON | Python 属性；数据库列名为 metadata |

唯一约束：`(conversation_id, source_message_id)`；若源无 ID，使用 `conversation + sender + timestamp + sequence + content hash` 的确定性 ID。Conversation、Participant 外键使用 `ON DELETE RESTRICT`。

### Evidence

id、message_id、excerpt、excerpt_start、excerpt_end、excerpt_hash、evidence_type、stance、relevance_score、is_valid、invalidated_at、invalidation_reason、created_at、evidence_fingerprint。

- `stance`: supports/contradicts/context。
- excerpt 是有边界的证据快照；偏移必须构成正区间，SHA-256 hash 用于检测原文变化。
- `relevance_score` 在 0 到 1 之间。
- `is_valid=false` 时必须有 `invalidated_at`；完整的状态传播原因由后续 Service 决定。
- `message_id` 非空且建立索引；Message 被排除或归档时，Evidence 仍保留，不得级联删除。
- 阶段 7 新 Evidence 要求 64 位 `evidence_fingerprint`。它由消息 ID、受控 evidence type、excerpt SHA-256 和 `evidence-1.0` 版本生成并建立唯一索引；旧数据允许 NULL，SQLite 中多个 NULL 不冲突。
- excerpt 只从本地完整 `normalized_content` 生成，最多 500 字符；超长时使用确定性前缀加 `[TRUNCATED]`。模型不能提供 excerpt。

### Insight

当前字段为：id、category、insight_type、title、statement、confidence、status、evidence_state、valid_from、valid_to、created_at、updated_at、model_name、provider_name、provider_request_id、extraction_version、insight_fingerprint、model_confidence、explicit_self_report、confidence_version、confidence_input_fingerprint、confidence_factors_json、confidence_explanation、confidence_as_of、confidence_calculated_at、reasoning_basis、alternative_explanations(JSON)、metadata_json。

`insight_type`: fact/preference/pattern/inference/hypothesis/contradiction/change。

`status`: proposed/confirmed/rejected/superseded。

`evidence_state`: valid/partial/invalid。`confidence` 在 0 到 1 之间，`valid_to >= valid_from`。insight_type、status、confidence 均有当前查询所需索引。

阶段 7 对新候选强制 64 位唯一 `insight_fingerprint`，由抽取版本、类型、受控类别、仅裁边/折叠空白后的 statement 和 UTC 有效期生成；旧数据允许 NULL，多个 NULL 不冲突。它只做精确幂等，不做大小写折叠、语义相似度、embedding 或用户内容覆盖。

`model_confidence` 是 Provider 的 0–1 自评，与最终 `confidence` 分离；`confidence-1.0` 中其权重为 0，也不进入评分输入指纹。阶段 7 新候选固定 `confidence=0.0` 和 `confidence_version=unscored`；该组合表示尚未评分，不表示科学计算结果为零。`explicit_self_report` 保存阶段 7 已验证的 Candidate 布尔值，旧记录经第四条迁移安全默认 false，不根据正文反推。

阶段 8 新增评分持久化字段：

- `confidence_input_fingerprint`：可空 64 位 SHA-256，普通索引；相同结构化输入、版本和 `as_of` 的幂等键，不全局唯一。
- `confidence_factors_json`：数值因子、Evidence/时间点/会话计数、类型 cap、版本、`as_of` 和安全规则码；禁止正文、excerpt、姓名、文件名、路径、Prompt 或响应。
- `confidence_explanation`：最长 4000 字符的本地固定模板解释，不调用模型。
- `confidence_as_of`：recency 的 aware UTC 基准；`confidence_calculated_at`：实际写入的 aware UTC 时间，不参与指纹。

每次评分会重算 evidence_state：有关联且全部有效为 valid，有效/无效混合为 partial，无关联或全部无效为 invalid。invalid 的 confidence 固定 0。评分只更新上述评分字段和 evidence_state，不修改 title、statement、status、model_confidence、Evidence 或 InsightEvidence。

### InsightEvidence

insight_id、evidence_id、created_at；联合主键 `(insight_id, evidence_id)`，因此相同组合不能重复。

两个外键均使用限制删除语义。Evidence 失效通过状态传播，不通过删除关联行实现。

### ProfileSnapshot

id、generated_at、profile_version、schema_version、markdown_content、json_content、source_range_start、source_range_end、statistics、limitations、evidence_state、invalidated_at、metadata_json。JSON 和时间范围均使用可移植类型；`generated_at` 建立索引。

阶段 2 仅建立快照容器。阶段 10 增加 ProfileSnapshotInsight 关联，冻结生成时的 Insight revision 和 Evidence ID。Evidence 后续失效时，不改写历史内容，但将快照标记 stale/invalid，并在查看或再次导出时显示“证据已失效”。

## 5. 删除、归档与证据失效

- MVP UI/API 不提供 SourceFile、Conversation、Message、Evidence 或 AI Insight 的不可逆物理删除。
- SourceFile/Conversation/Message 使用 archived 状态；Message 另有 excluded_from_analysis。归档和排除不修改 raw_content、normalized_content 或 file_hash。
- 后续归档/排除 Service 应在同一事务中把相关 Evidence 标记无效，重新计算 `Insight.evidence_state`，并把受影响 ProfileSnapshot 标记 invalid；该传播逻辑尚未在阶段 2 实现。
- 数据库外键对核心证据链使用 `RESTRICT`，禁止由 ORM cascade 或数据库 cascade 无提示破坏链路。
- 如果未来增加物理删除，必须先提供影响预览：SourceFile、Conversation、Message、Evidence、Insight、ProfileSnapshot 数量及 ID；用户二次确认后由专用服务在事务内执行，并保留不含正文的结果统计。
- ProfileSnapshot 含敏感正文，采用与聊天数据相同的本地保护。证据失效的历史快照可以作为历史记录查看，但必须醒目标记，不能作为当前有效档案导出。
- MVP 不承诺 SSD 物理安全擦除；文档明确操作系统、同步目录和备份层限制。

## 6. Insight 类型数据库约束与后续 Service 验证

数据库只能约束枚举、范围和关联存在，语义边界由可测试 Service 执行：

- fact：用户明确陈述且有明确自述 Evidence；没有明确自述证据不能生成。
- preference：用户明确表达，或在多个独立选择场景中稳定表现。
- pattern：至少两个独立事件或时间点；单条消息不能直接生成。
- inference：记录 reasoning_basis 和其他可能解释，原文没有直接表述该结论。
- hypothesis：证据不足的暂定解释；`confidence-1.0` 上限为 0.60。
- change：同一主题至少覆盖两个不同时间点。
- contradiction：双方 Evidence 必须同时保留。

阶段 7 的候选 Service 已执行上述最低机械约束，并始终创建 `proposed`；阶段 8 在重算时再次检查数据库当前最低条件，失败则 confidence=0 且保存安全规则码，不自动改类型、确认或驳回。这些规则不能证明心理学真实性或完整独立事件语义，后续编辑、确认和 Profile 入口也必须重复验证，不能只依赖前端。

## 7. 待确认问题

- 是否需要应用层加密；如果需要，密钥恢复和跨平台密钥链方案需单独设计。
