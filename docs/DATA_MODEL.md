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

- ImportJob：阶段 5 导入状态真正需要时加入。
- ExtractionRun：阶段 7 抽取恢复与幂等需要时加入。
- InsightRevision、InsightRelation：阶段 9 审核和 supersede 需要时加入。
- ProfileSnapshotInsight：阶段 10 生成快照并验证追溯时加入。

不得为这些后续模型提前创建空表或伪实现。Conversation 的参与者集合在 MVP 可从 Message.sender_id 查询得到，不提前增加 ConversationParticipant 模型。

## 3. 阶段 2 实体关系

```text
SourceFile 1 ── * Conversation
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
| file_hash | string | SHA-256，索引 |
| storage_path | string | data 目录内的受控相对路径 |
| byte_size | integer | 非负 |
| imported_at | datetime | UTC |
| parser_name | string | 解析器稳定 ID |
| parser_version | string | 幂等和重跑依据 |
| status | enum | pending/ready/failed/archived |
| archived_at | datetime nullable | 归档时间；不删除原文件 |
| metadata | JSON | 非敏感扩展信息 |

唯一约束建议：`(file_hash, parser_name, parser_version)`。

应用接收上传后先对原始字节计算 file_hash，再进行编码检测或解析。进入 ready 状态的 SourceFile 必须保留原始字节；任何 Parser/Cleaner 不得就地修改该文件。

### Conversation

id、source_file_id、platform、source_conversation_id、title、started_at、ended_at、archived_at、metadata。`(source_file_id, source_conversation_id)` 唯一。`source_file_id` 使用 `ON DELETE RESTRICT`。

### Participant

id、canonical_name、aliases(JSON array)、is_profile_owner、metadata。MVP 允许每个本地档案只有一个 owner，但不通过全局数据库约束假设未来永远单档案。

### Message

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID string | PK |
| conversation_id | UUID | FK |
| source_message_id | string | 源 ID；缺失时生成确定性 ID |
| sender_id | UUID | FK Participant |
| timestamp | datetime nullable | 无法解析时保留错误元数据 |
| sequence_index | integer | 同会话稳定顺序 |
| message_type | enum | text/image/file/system/recalled/unknown |
| raw_content | text | 永不被清洗覆盖 |
| normalized_content | text | 可从 raw + pipeline 版本重建 |
| reply_to_message_id | UUID nullable | 自引用 FK |
| is_deleted | boolean | 源数据标记，不代表物理删除 |
| excluded_from_analysis | boolean | 用户控制 |
| exclusion_reason | string nullable | 不保存多余敏感正文 |
| archived_at | datetime nullable | 应用归档状态；原文仍保留 |
| normalization_version | string | 清洗版本 |
| metadata | JSON | 附件占位、源字段等 |

唯一约束：`(conversation_id, source_message_id)`；若源无 ID，使用 `conversation + sender + timestamp + sequence + content hash` 的确定性 ID。Conversation、Participant 外键使用 `ON DELETE RESTRICT`。

### Evidence

id、message_id、excerpt、excerpt_start、excerpt_end、excerpt_hash、evidence_type、stance、relevance_score、validity_status、invalidated_at、invalidation_reason、created_at。

- `stance`: supports/contradicts/context。
- excerpt 是生成当时的证据快照；偏移和 hash 用于检测原文变化。
- `validity_status`: valid/excluded/archived/missing_source。
- Message 被排除或归档时，Evidence 保留但变为无效；不得级联删除。

### Insight

id、category、insight_type、title、statement、reasoning_basis、alternative_explanations(JSON)、system_confidence、user_confidence_override、confidence_factors(JSON)、confidence_version、status、evidence_status、valid_from、valid_to、created_at、updated_at、model_name、provider_id、extraction_version、row_version。

`insight_type`: fact/preference/pattern/inference/hypothesis/contradiction/change。

`status`: proposed/confirmed/rejected/superseded。

`evidence_status`: valid/partial/invalid。没有有效 Evidence 的 AI 候选不得创建；已存在 Insight 的 Evidence 后续全部失效时，Insight 必须转为 invalid，不得继续作为有效 Profile 结论。

最终显示置信度优先使用 user override，但必须同时保留系统分数和因子。

### InsightEvidence

insight_id、evidence_id、weight、created_at；联合主键 `(insight_id, evidence_id)`。

两个外键均使用限制删除语义。Evidence 失效通过状态传播，不通过删除关联行实现。

### ProfileSnapshot

id、generated_at、profile_version、schema_version、markdown_content、json_content、source_range、statistics、limitations、evidence_status、invalidated_at、metadata。

阶段 2 仅建立快照容器。阶段 10 增加 ProfileSnapshotInsight 关联，冻结生成时的 Insight revision 和 Evidence ID。Evidence 后续失效时，不改写历史内容，但将快照标记 stale/invalid，并在查看或再次导出时显示“证据已失效”。

## 5. 删除、归档与证据失效

- MVP UI/API 不提供 SourceFile、Conversation、Message、Evidence 或 AI Insight 的不可逆物理删除。
- SourceFile/Conversation/Message 使用 archived 状态；Message 另有 excluded_from_analysis。归档和排除不修改 raw_content、normalized_content 或 file_hash。
- 归档/排除 Message 时，应用服务在同一事务中把相关 Evidence 标记无效，重新计算 Insight.evidence_status，并把受影响 ProfileSnapshot 标记 stale/invalid。
- 数据库外键对核心证据链使用 `RESTRICT`，禁止由 ORM cascade 或数据库 cascade 无提示破坏链路。
- 如果未来增加物理删除，必须先提供影响预览：SourceFile、Conversation、Message、Evidence、Insight、ProfileSnapshot 数量及 ID；用户二次确认后由专用服务在事务内执行，并保留不含正文的结果统计。
- ProfileSnapshot 含敏感正文，采用与聊天数据相同的本地保护。证据失效的历史快照可以作为历史记录查看，但必须醒目标记，不能作为当前有效档案导出。
- MVP 不承诺 SSD 物理安全擦除；文档明确操作系统、同步目录和备份层限制。

## 6. Insight 类型数据库约束与 Service 验证

数据库只能约束枚举、范围和关联存在，语义边界由可测试 Service 执行：

- fact：至少一条 `explicit_self_report` Evidence。
- pattern：至少两个不同 event_group/timepoint 的 Evidence。
- inference：`reasoning_basis` 非空且 alternative_explanations 至少一个。
- hypothesis：system_confidence 不超过当前 confidence_version 的 hypothesis cap。
- change：Evidence 覆盖至少两个不同 timestamp。
- contradiction：同时存在两个对立 stance/event side 的 Evidence。

这些规则必须在创建、编辑、确认和 Profile 生成入口重复校验，不能只依赖前端。

## 7. 待确认问题

- 是否需要应用层加密；如果需要，密钥恢复和跨平台密钥链方案需单独设计。
