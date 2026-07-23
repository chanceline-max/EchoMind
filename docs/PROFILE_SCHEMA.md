# EchoProfile 输出规范

## 1. 版本与定位

- `echo-profile-1.0` / `echo-profile-document-1.0` 是已发布的可追溯 Insight 快照格式，继续只读兼容。
- `echo-profile-2.0` / `echo-profile-document-2.0` 是当前综合人格档案格式。
- 2.0 把已确认 Insight 综合为连贯的人物分析，不把 Insight 或 Evidence 列表当作最终档案正文。
- 2.0 必须同时包含 Big Five 与 MBTI 两种参考框架；它们不是标准化测评、诊断或决定性结论。
- `EchoProfileDocument` 仍是 Markdown 与 JSON 的唯一语义源，两种输出不得分别拼装。
- ProfileSnapshot 创建后不可更新或删除；旧快照不会因版本升级或来源变化被回写。

## 2. 生成请求

`ProfileGenerationRequest` 严格拒绝额外字段。两个版本只接受以下配对：

| Profile | Schema | 综合人格分析 |
|---|---|---|
| `echo-profile-1.0` | `echo-profile-document-1.0` | 禁止 |
| `echo-profile-2.0` | `echo-profile-document-2.0` | 必须 |

共有选项包括：

- `request_id`
- `scope=all_confirmed|selected_confirmed`
- `selected_insight_ids`
- `include_partial_evidence`
- `include_invalidated`
- `evidence_mode=references|excerpts`
- `include_reasoning`
- `generated_as_of`

2.0 还包含：

- `include_personality_synthesis=true`
- `remote_consent`
- 服务端写入的 `synthesis_provider_name` 与 `synthesis_model_name`

`remote_consent` 只用于当前调用授权，不写入 Snapshot，也不参与可复用选项。Provider、模型、端点和 Key 由服务端配置决定，浏览器不能覆盖。

## 3. 选择与内部来源

- 只读取 `status=confirmed` 的 Insight；confidence 不是纳入门槛。
- `partial` 是否纳入由请求决定；`invalid` 只能作为历史变化或不确定性输入，不能被表述为当前有效事实。
- 生成前仍加载本地 Evidence 结构并建立 `profile-source-1.0` manifest。
- manifest、source fingerprint 与 generation fingerprint 用于幂等复用、完整性检查和动态 stale 检测。
- 2.0 的公开 Document、Markdown 与 JSON 不含 Evidence 索引、Evidence 引用、Message ID 或 Conversation ID；这不代表内部证据链被删除。

## 4. 2.0 综合上下文边界

Provider 只接收已确认 Insight 的以下派生字段：

- `insight_type`
- `category`
- `title`
- `statement`
- 最终 `confidence`
- `evidence_state`
- `explicit_self_report`
- `valid_from` / `valid_to`
- `reasoning_basis`
- `alternative_explanations`

不发送：

- `raw_content` 或 `normalized_content`
- Evidence excerpt、Evidence/Message/Conversation/SourceFile ID
- 参与者姓名、会话标题、文件名、本机路径或 metadata
- API Key、数据库 URL、Prompt 历史或审核备注

输入按确定性顺序构造，单个内容块最多 18,000 字符，总上下文最多 80,000 字符。超出预算的 Insight 数量记录为 `omitted_insight_count`，不能被静默忽略。

默认 Mock Provider 完全离线，只返回“信息不足”的确定性结构，用于验证闭环，不伪造个性化分析。远程 Provider 必须同时满足服务端启用与当前请求显式 consent。

## 5. EchoProfileDocument

顶层字段：

- `metadata: ProfileDocumentMetadata`
- `personality_synthesis: PersonalitySynthesis | null`
- `sections: ProfileSection[]`
- `evidence_index: ProfileEvidenceItem[]`

1.0 的 `personality_synthesis=null`，保留 sections 与 evidence_index。

2.0 的 `personality_synthesis` 必须存在；sections 仍作为内部来源快照保存，但每个 `evidence_refs=[]`，`evidence_index=[]`。前端和 Markdown 只呈现综合分析，不呈现这些内部条目。

## 6. PersonalitySynthesis

固定版本为 `personality-synthesis-1.0`，字段包括：

- `headline`
- `overall_summary`
- `core_traits`
- `thinking_style`
- `decision_style`
- `motivation_and_values`
- `social_and_relationship_style`
- `emotional_and_stress_patterns`
- `strengths`
- `growth_edges`
- `tensions_and_changes`
- `framework_assessments`
- `uncertainty_note`
- `provider_name` / `model_name`
- `input_insight_count` / `omitted_insight_count`

输出必须使用克制的简体中文，不得逐条复述输入，不得使用医疗、心理诊断或病理化语言。稳定特征、场景表现、变化和矛盾应被区分；信息不足时必须明确说明。

## 7. Big Five 与 MBTI 契约

`framework_assessments` 必须恰好两项并保持以下顺序：

1. `big_five`
2. `mbti`

Big Five 必须包含：

- openness
- conscientiousness
- extraversion
- agreeableness
- emotional_stability

MBTI 必须包含：

- energy（E / I）
- information（S / N）
- decisions（T / F）
- lifestyle（J / P）

每个维度只能使用 `low|moderately_low|balanced|moderately_high|high|insufficient`。框架整体参考强度只能使用 `low|medium|high|insufficient`。

MBTI 可以给出倾向或类型区间，但不得声称完成正式 MBTI 测评。两种框架都不能覆盖完整人物分析，也不能用于决定职业、关系、能力或人生选择。

## 8. 渲染与完整性

- Markdown 和 JSON 只从通过 Pydantic 校验的同一 Document 渲染。
- 2.0 Markdown 依次呈现人格题名、综合摘要、思维/决策/价值/关系/压力模式、优势、成长方向、矛盾变化、Big Five、MBTI 和不确定性。
- 2.0 Markdown 和 JSON 不生成证据编号、消息链接或 Evidence 索引。
- JSON 使用稳定键排序、UTF-8、RFC 3339 时间和结尾 LF。
- `profile-generation-1.0` 覆盖来源、请求选项、Profile/Schema 和 renderer 版本，并由唯一索引复用。
- `profile-document-sha256` 对规范化 JSON 计算 SHA-256；计算时把自身 hash 字段置空。
- 读取 Snapshot 时先验证 document hash，再按相应 1.0/2.0 Schema 恢复。

## 9. stale、隐私与导出

- 来源变化只动态返回 `current|stale|source_unavailable` 及安全 reason code，历史正文和 hash 永不回写。
- 2.0 即使不显示证据引用，也必须继续通过内部 manifest 检测 Insight 修订、状态、confidence 和 Evidence 有效性变化。
- Profile API、Markdown 和 JSON 导出使用 `no-store/no-cache`；只有用户显式点击才请求导出。
- 前端不得把 Profile 写入 localStorage、sessionStorage、IndexedDB、Service Worker cache、URL 或 console。
- EchoProfile 是高敏感派生数据，不是永久真相、正式人格测评或诊断。

## 10. 已知限制

- 默认 Mock 不执行真实人格推断。
- 真实远程 Provider 的结构化输出兼容性尚未广泛验证。
- 聊天样本可能集中于少数关系或情境，框架映射可能随上下文变化。
- 当前没有正式问卷导入、用户逐段修订、PDF/Word、云分享或公开链接。
- 1.0 与 2.0 Snapshot 都保持不可变；升级不会自动重写旧档案。
