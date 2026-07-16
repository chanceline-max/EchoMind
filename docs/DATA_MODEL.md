# EchoMind 数据模型

## 1. 通用约定

- 主键使用 UUID4 字符串，避免依赖数据库自增和 SQLite 专有类型。
- 所有时间在持久层使用 UTC ISO 8601/带时区 datetime。
- JSON 扩展字段命名为数据库列 `metadata`；SQLAlchemy Python 属性使用 `metadata_json`。
- 核心枚举在数据库中保存稳定小写字符串，并由 Pydantic/领域枚举校验。
- 原文删除应真实级联删除；不使用软删除无限保留敏感内容。
- 所有外键和唯一约束都通过 Alembic 管理。

## 2. 实体关系

```text
SourceFile 1 ── * Conversation
Conversation * ── * Participant (ConversationParticipant)
Conversation 1 ── * Message
Participant 1 ── * Message
Message 1 ── * Evidence
Insight * ── * Evidence (InsightEvidence)
Insight 1 ── * InsightRevision
Insight * ── * Insight (InsightRelation)
ProfileSnapshot * ── * Insight (ProfileSnapshotInsight)
ImportJob 1 ── 0..1 SourceFile
ExtractionRun 1 ── * Insight
```

## 3. 核心表

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
| status | enum | pending/ready/failed/deleted |
| metadata | JSON | 非敏感扩展信息 |

唯一约束建议：`(file_hash, parser_name, parser_version)`。

### ImportJob

用于状态页和可恢复导入：id、state、stage、source_file_id、input_hash、checkpoint、safe_error_code、statistics、created_at、started_at、finished_at。`statistics` 只保存计数，不保存正文。

### Conversation

id、source_file_id、platform、source_conversation_id、title、started_at、ended_at、metadata。`(source_file_id, source_conversation_id)` 唯一。

### Participant

id、canonical_name、aliases(JSON array)、is_profile_owner、metadata。MVP 允许每个本地档案只有一个 owner，但不通过全局数据库约束假设未来永远单档案。

### ConversationParticipant

conversation_id、participant_id、source_display_name、role。用于规范化同一参与者在不同会话中的别名。

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
| normalization_version | string | 清洗版本 |
| metadata | JSON | 附件占位、源字段等 |

唯一约束：`(conversation_id, source_message_id)`；若源无 ID，使用 `conversation + sender + timestamp + sequence + content hash` 的确定性 ID。

### Evidence

id、message_id、excerpt、excerpt_start、excerpt_end、excerpt_hash、evidence_type、stance、relevance_score、created_at。

- `stance`: supports/contradicts/context。
- excerpt 是生成当时的证据快照；偏移和 hash 用于检测原文变化。
- Evidence 不脱离 Message 存在，Message 物理删除时级联删除。

### Insight

id、category、insight_type、title、statement、alternative_explanations(JSON)、system_confidence、user_confidence_override、confidence_factors(JSON)、confidence_version、status、valid_from、valid_to、created_at、updated_at、model_name、provider_id、extraction_version、extraction_run_id、row_version。

`insight_type`: fact/preference/pattern/inference/hypothesis/contradiction/change。

`status`: proposed/confirmed/rejected/superseded。

最终显示置信度优先使用 user override，但必须同时保留系统分数和因子。

### InsightEvidence

insight_id、evidence_id、weight、created_at；联合主键 `(insight_id, evidence_id)`。

### InsightRevision

保存用户或系统对 Insight 的可审阅修订：id、insight_id、revision_number、actor_type、change_reason、before_json、after_json、created_at。不得在日志中复制这些正文。

### InsightRelation

source_insight_id、target_insight_id、relation_type、created_at。MVP 只需要 `contradicts` 和 `supersedes`，避免提前构造复杂图谱。

### ExtractionRun

id、state、provider_id、model_name、prompt_version、extraction_version、input_hash、window_config、checkpoint、statistics、safe_error_code、created_at、finished_at。

### ProfileSnapshot

id、generated_at、profile_version、schema_version、markdown_content、json_content、source_range、statistics、limitations、metadata。

### ProfileSnapshotInsight

profile_snapshot_id、insight_id、insight_revision_number。它冻结生成时使用的 Insight 版本，保证历史 Profile 可重现。

## 4. 删除与保留

- 删除 SourceFile 时，默认提示将删除的会话、消息、证据、受影响 Insight 和 Profile 可重现性。
- 用户可选择删除派生数据；默认采用级联删除，任务日志只留下无正文的安全事件。
- ProfileSnapshot 含敏感正文，必须和聊天数据采用同等保护和删除策略。
- MVP 不承诺安全擦除 SSD 物理块；文档应明确操作系统和备份层限制。

## 5. 待确认问题

- MVP 是否只允许一个 profile owner，还是允许同一数据库存在多个独立档案。
- 原始文件是否必须保留；可否在成功解析后由用户选择删除原文件副本。
- 是否需要应用层加密；如果需要，密钥恢复和跨平台密钥链方案需单独设计。
