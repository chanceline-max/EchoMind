# EchoProfile 输出规范

## 1. 设计原则

- Markdown 与 JSON 来自同一个版本化中间模型。
- Profile 是某一时刻的快照，不是永久真相。
- 重要条目包含 Insight ID、类型、状态、时间、置信度和 Evidence 引用。
- 条目和快照包含 evidence_status；Evidence 后续失效时，历史内容保留但必须标记为 stale/invalid。
- 不把 hypothesis/inference 伪装成 fact。
- 默认正式导出只包含 confirmed Insight；其他策略必须在档案说明中显式声明。

## 2. Markdown 章节

```text
# EchoProfile
## 0. 档案说明
## 1. 基础背景
## 2. 稳定偏好
## 3. 思维模式
## 4. 行为与执行模式
## 5. 情绪模式
## 6. 人际关系模式
## 7. 价值观与核心驱动力
## 8. 内部冲突与张力
## 9. 时间演化
## 10. 待验证假设
## 11. 矛盾信息
## 12. 证据索引
```

每个条目的建议呈现：

```markdown
### 在陌生环境中先观察再参与

- 类型：pattern
- 状态：confirmed
- 置信度：0.73（启发式分数，不是概率）
- 有效时间：2025-02 至 2026-06
- 判断：……
- 适用条件：……
- 其他可能解释：……
- 支持证据：[E-001] [E-014]
- 相反证据：[E-021]
- 最近更新：2026-07-16
- 证据状态：valid
```

## 3. JSON 顶层结构

```json
{
  "schema_version": "echoprofile-1.0",
  "profile_version": "1",
  "generated_at": "2026-07-16T10:20:00Z",
  "generation_policy": "confirmed_only",
  "evidence_status": "valid",
  "scope": {
    "from": "2025-01-01T00:00:00Z",
    "to": "2026-07-15T23:59:59Z",
    "source_file_count": 1,
    "conversation_count": 8,
    "message_count": 1200,
    "participant_count": 5
  },
  "limitations": [
    "档案仅基于用户选择导入且未排除的消息。",
    "置信度是版本化启发式分数，不是统计概率。",
    "本档案不构成医疗或心理诊断。"
  ],
  "sections": {
    "background": [],
    "preferences": [],
    "thinking_patterns": [],
    "behavior_patterns": [],
    "emotional_patterns": [],
    "relationship_patterns": [],
    "values_and_drives": [],
    "internal_tensions": [],
    "temporal_changes": [],
    "hypotheses": [],
    "contradictions": []
  },
  "evidence_index": {}
}
```

## 4. Profile 条目

```json
{
  "insight_id": "uuid",
  "revision": 2,
  "type": "pattern",
  "status": "confirmed",
  "evidence_status": "valid",
  "title": "在陌生环境中先观察再参与",
  "statement": "……",
  "conditions": ["陌生人较多", "缺少明确角色"],
  "alternative_explanations": ["当时处于短期疲劳状态"],
  "confidence": {
    "display": 0.73,
    "system": 0.68,
    "user_override": 0.73,
    "version": "confidence-v1",
    "factors": {
      "explicit_self_report": 0.6,
      "repetition": 0.8,
      "temporal_span": 0.7,
      "relationship_diversity": 0.5,
      "evidence_quality": 0.8,
      "recency": 0.9,
      "contradiction_strength": 0.2
    }
  },
  "valid_from": "2025-02-01T00:00:00Z",
  "valid_to": null,
  "evidence_ids": ["E-001", "E-014"],
  "contradicting_evidence_ids": ["E-021"],
  "updated_at": "2026-07-16T10:00:00Z"
}
```

## 5. 证据索引

Evidence 索引提供安全、可追溯的引用：evidence_id、message_id、conversation_id、timestamp、participant display label、excerpt、stance、relevance_score。JSON 导出默认包含 excerpt，因此本身属于高敏感数据。

## 6. 生成规则

- fact 只能进入“基础背景”，并要求明确自述或等价高质量证据。
- hypothesis 只进入“待验证假设”。
- contradiction 不被合并成单一答案，进入“矛盾信息”。
- change 必须包含时间前后关系和至少两个阶段的证据。
- 内部冲突、价值观和情绪模式需要更高证据阈值，具体阈值在抽取阶段版本化。
- 无 Evidence、Evidence 已删除、Insight 被 rejected/superseded 时不得进入正式 Profile。
- Evidence 因消息归档或排除而失效时，相关 Insight 不得继续作为有效结论；历史 ProfileSnapshot 标记 stale/invalid，新导出必须排除或置于独立的“证据已失效”区域。

## 7. Schema 验证

- Pydantic 模型和导出的 JSON Schema 是机器契约。
- Markdown snapshot 测试验证章节、Insight ID 和 Evidence ID 覆盖。
- 一致性测试要求 JSON 中的每个导出 Insight 和 Evidence 都在 Markdown 中可定位。
- 有效性传播测试要求任一 Evidence 失效后，Insight、ProfileSnapshot 和新导出的 evidence_status 一致。
- Schema 的破坏性变化提升主版本；兼容字段增加提升次版本。
