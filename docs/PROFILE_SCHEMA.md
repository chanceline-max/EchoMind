# EchoProfile 输出规范

## 1. 版本和不变量

- Profile 版本：`echo-profile-1.0`。
- Schema 版本：`echo-profile-document-1.0`。
- 选择策略：`confirmed-only-1.0`，只允许 `status=confirmed`；confidence 不作为纳入门槛。
- `EchoProfileDocument` 是 Markdown 与 JSON 的唯一语义源，两种输出不得分别拼装。
- 生成过程离线、确定性，不调用 Provider，不创建或修改 Insight。
- ProfileSnapshot 创建后不可更新或删除；历史内容不因来源变化而回写。

## 2. 生成请求

`ProfileGenerationRequest` 严格拒绝额外字段，包含：

| 字段 | 契约 |
|---|---|
| `request_id` | 应用生成 UUID；不进入指纹 |
| `profile_version` | 只允许 `echo-profile-1.0` |
| `profile_schema_version` | 只允许 `echo-profile-document-1.0` |
| `scope` | `all_confirmed` 或 `selected_confirmed` |
| `selected_insight_ids` | selected scope 必填、至少一项、稳定去重、最多 1000；非 confirmed 或不存在均明确失败 |
| `include_partial_evidence` | 默认 true；false 时排除 partial 正文但保留统计/来源追溯 |
| `include_invalidated` | 默认 true；invalid 只进入“证据已失效”章节 |
| `evidence_mode` | 默认 `references`；显式选择 `excerpts` 才复制既有 Evidence excerpt |
| `include_reasoning` | 默认 true；只控制 reasoning_basis 和 alternative_explanations |
| `generated_as_of` | 必填 aware datetime，入模前转 UTC |

## 3. 固定章节和路由

正文按以下固定顺序输出：

1. `background` 基础背景
2. `preferences` 稳定偏好
3. `thinking_patterns` 思维模式
4. `behavior_execution` 行为与执行模式
5. `emotional_responses` 情绪反应模式
6. `relationship_patterns` 人际关系模式
7. `values_motivation` 价值观与核心驱动力
8. `internal_conflicts` 内部冲突与张力
9. `temporal_changes` 时间演化
10. `contradictions` 矛盾信息
11. `hypotheses` 待验证假设
12. `other_confirmed` 其他已确认判断
13. `invalidated` 证据已失效

路由优先级为 invalid → contradiction → hypothesis → change/temporal_change → background → preference →受控 category → other。一个 Insight 只进入一个正文章节。时间演化按有效期升序；矛盾/假设按 confidence、更新时间、ID；其他章节按 confidence、valid_from、ID，所有排序都有稳定 ID 兜底。

## 4. 唯一结构化文档

`EchoProfileDocument` 顶层仅含：

- `metadata: ProfileDocumentMetadata`
- `sections: ProfileSection[]`
- `evidence_index: ProfileEvidenceItem[]`

Metadata 保存 profile/schema 版本、生成时间、选择策略、scope、evidence mode、三类指纹/Hash、纳入/排除统计、会话/源文件统计和固定局限性。

`ProfileInsightItem` 保存 I 编号、本地 Insight ID、生成时 revision、类型/category、title/statement、最终 confidence 及版本/解释、evidence_state、自述标记、有效期、可选推理、E 引用、警告、最低规则码和有效/无效 Evidence 数量。它不包含 model confidence、Provider、Prompt、review note、抽取指纹或修订历史。

`ProfileEvidenceItem` 保存 E 编号、本地 Evidence/Message/Conversation ID、Evidence 类型和立场、相关度、有效性/原因、消息时间、匿名 `PROFILE_OWNER/OTHER` 角色；只有 excerpts 模式包含既有 excerpt。它不包含 raw/normalized content、姓名、源消息 ID、文件名、路径、cleaning operations 或 metadata。

## 5. I/E 引用

- 正文最终排序后依次分配 `I001...`。
- Evidence 按时间、Conversation、Message、Evidence ID 稳定排序后分配 `E001...`。
- 同一 Evidence 被多个 Insight 引用时只出现一次，所有 Insight 复用同一 E 编号。
- JSON 同时保留本地数据库 ID；Markdown 主要展示 I/E 编号。

## 6. valid、partial 和 invalid

- valid：进入正常章节。
- partial：默认进入正常章节，显示“部分证据已失效”及有效/无效数量；可由请求排除。
- invalid：永不作为当前有效结论进入正常章节；默认进入“证据已失效”，显示不能作为当前结论使用；可隐藏具体条目但仍计入统计。
- hypothesis 固定显示“待验证假设”。
- contradiction 固定说明分数支持的是冲突存在，不代表某一方正确。

## 7. Markdown 与 JSON

Markdown 使用 UTF-8、LF、单一末尾换行、固定 heading/章节/item 格式，不生成 HTML。用户派生文本对反斜杠、标题/列表/链接控制符、反引号、尖括号和 URL scheme 做安全处理；前端只用 `<pre>` 纯文本预览。

JSON 使用 `model_dump(mode="json")` 后 `json.dumps(sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)`，日期为 RFC 3339 UTC，输出以一个 LF 结束。两种 renderer 只接受同一个 `EchoProfileDocument`，契约测试核对章节、I/E 引用、数量、statement、confidence、状态和 evidence mode。

## 8. 指纹和 Hash

- `profile-source-1.0`：覆盖选定 Insight 当前 revision/status/content、最终 confidence、evidence_state 及 Evidence 的结构化追溯特征；不含正文副本、excerpt、姓名、文件名、路径、Provider 或 Key。正文只参与 SHA-256 计算，不写入 manifest。
- `profile-generation-1.0`：覆盖 source fingerprint、完整安全选项、Profile/Schema/section/renderer 版本；相同值由数据库唯一索引复用。
- `profile-document-sha256`：对规范化 JSON 计算 SHA-256。为解除自引用，计算时唯一将 `metadata.document_hash` 规范化为空字符串；读取/导出前用同一规则复核。

`source_manifest_json` 只保存 ID、revision、status、confidence、Evidence fingerprint/validity 及内容/组件 Hash，不保存正文。

## 9. Snapshot 与 stale

新 Snapshot 原子保存 Markdown、JSON、generation options、source manifest、三类指纹/Hash和计数，`source_status_at_generation=current`。ORM 拒绝 update/delete，API 不提供 PATCH/DELETE。

读取时用原选项重新计算当前来源：相同为 `current`；revision/status/content/confidence/evidence/confirmed 集合变化为 `stale`；来源实体缺失或无法重建为 `source_unavailable`。返回安全 reason code，不返回正文。该计算不修改历史 Snapshot、Markdown、JSON 或 document hash。

## 10. API 与导出

- `POST /api/v1/profiles`：新建 201；相同 generation fingerprint 复用 200。
- `GET /api/v1/profiles`：分页摘要，不返回正文、manifest 或 excerpt。
- `GET /api/v1/profiles/{id}`：结构化 Document、动态状态和导出链接。
- `GET /api/v1/profiles/{id}/markdown|json`：显式下载，安全通用文件名，`no-store`、`no-cache`、`nosniff`。

当前没有 PDF/Word、HTML renderer、Profile 编辑、Snapshot 删除、云发布或公开分享。
