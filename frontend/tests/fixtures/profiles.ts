import type { ProfileDetail, ProfileSummary } from "../../src/types/profiles";

export const profileSummary: ProfileSummary = {
  id: "profile-1", generated_at: "2026-07-21T12:00:00Z", profile_version: "echo-profile-1.0",
  schema_version: "echo-profile-document-1.0", insight_count: 4, evidence_count: 2,
  evidence_mode: "references", document_hash: "a".repeat(64), current_source_status: "current",
  stale_reason_codes: [],
};

export const profileDetail: ProfileDetail = {
  ...profileSummary,
  links: { self: "/api/v1/profiles/profile-1", markdown: "/api/v1/profiles/profile-1/markdown", json: "/api/v1/profiles/profile-1/json" },
  document: {
    metadata: {
      profile_id: "profile-1", profile_version: "echo-profile-1.0", schema_version: "echo-profile-document-1.0",
      generated_at: "2026-07-21T12:00:00Z", generated_as_of: "2026-07-21T11:59:00Z",
      selection_policy: "confirmed-only-1.0", scope: "all_confirmed", evidence_mode: "references",
      source_fingerprint: "b".repeat(64), generation_fingerprint: "c".repeat(64), document_hash: "a".repeat(64),
      confirmed_insight_count: 4, included_valid_count: 3, included_partial_count: 1, invalidated_count: 0,
      excluded_count: 0, evidence_count: 2, conversation_count: 1, source_file_count: 1,
      limitations: ["Synthetic limitation; not a diagnosis."],
    },
    personality_synthesis: null,
    sections: [{ section_key: "hypotheses", title: "待验证假设", description: "Synthetic section.", items: [{
      profile_insight_ref: "I001", insight_id: "insight-1", insight_revision_number: 2,
      insight_type: "hypothesis", category: "thinking_pattern", title: "Synthetic profile insight",
      statement: "Synthetic profile statement.", confidence: 0.4, confidence_version: "confidence-1.0",
      confidence_explanation: "Mechanical support only; not probability.", evidence_state: "partial",
      explicit_self_report: false, valid_from: null, valid_to: null, reasoning_basis: "Synthetic reasoning.",
      alternative_explanations: ["Synthetic alternative."], evidence_refs: ["E001"],
      warnings: ["部分证据已失效。", "待验证假设。"], minimum_rule_code: "passed",
      source_status_at_generation: "current", valid_evidence_count: 1, invalid_evidence_count: 1,
    }] }],
    evidence_index: [{ profile_evidence_ref: "E001", evidence_id: "evidence-1", message_id: "message-1",
      conversation_id: "conversation-1", evidence_type: "supporting", role: "supports", relevance_score: .8,
      is_valid: true, invalidation_reasons: [], message_timestamp: "2026-07-20T00:00:00Z",
      sender_role: "PROFILE_OWNER", excerpt: null }],
  },
};

export const synthesizedProfileDetail: ProfileDetail = {
  ...profileDetail,
  profile_version: "echo-profile-2.0",
  schema_version: "echo-profile-document-2.0",
  document: {
    ...profileDetail.document,
    metadata: {
      ...profileDetail.document.metadata,
      profile_version: "echo-profile-2.0",
      schema_version: "echo-profile-document-2.0",
      limitations: ["综合分析只用于自我理解，不是正式测评或诊断。"],
    },
    personality_synthesis: {
      synthesis_version: "personality-synthesis-1.0",
      headline: "审慎探索型的长期建构者",
      overall_summary: "这个人倾向先理解系统，再持续推进值得长期投入的目标；开放探索与现实校验通常同时存在。",
      core_traits: ["好奇", "审慎", "长期主义", "重视真实反馈"],
      thinking_style: "习惯从结构和因果关系理解问题，也愿意在新信息出现后修正原有判断。",
      decision_style: "重要决定通常经过比较和验证，确定方向后会以小步迭代的方式推进。",
      motivation_and_values: "更容易被成长、创造和真实影响驱动，而不是短期的外部评价。",
      social_and_relationship_style: "关系中重视真诚与信息密度，熟悉之后会主动分享资源和方法。",
      emotional_and_stress_patterns: "压力增加时可能反复检查方案；恢复感通常来自重新获得清晰边界和可执行步骤。",
      strengths: ["能把零散信息组织成结构", "愿意根据证据修正观点"],
      growth_edges: ["在低风险决定上减少过度分析", "给情绪恢复预留明确空间"],
      tensions_and_changes: ["探索欲与确定性需求同时存在，需要用小实验连接两者。"],
      framework_assessments: [
        {
          framework: "big_five",
          display_name: "Big Five",
          result: "开放性偏高，尽责性中等偏高",
          confidence: "medium",
          summary: "用于描述长期行为倾向，不是正式量表得分。",
          dimensions: [
            { dimension_key: "openness", label: "开放性", tendency: "high", summary: "乐于探索新概念与复杂问题。" },
            { dimension_key: "conscientiousness", label: "尽责性", tendency: "moderately_high", summary: "重要目标上倾向持续推进。" },
            { dimension_key: "extraversion", label: "外向性", tendency: "balanced", summary: "社交能量表现依情境而变。" },
            { dimension_key: "agreeableness", label: "宜人性", tendency: "moderately_high", summary: "重视合作，但会保留独立判断。" },
            { dimension_key: "emotional_stability", label: "情绪稳定性", tendency: "balanced", summary: "压力下会谨慎复核，恢复后能够继续行动。" },
          ],
          caveats: ["不是正式 Big Five 测评。"],
        },
        {
          framework: "mbti",
          display_name: "MBTI",
          result: "偏向 INxJ，仅作描述参考",
          confidence: "low",
          summary: "字母偏好用于辅助表达，不能定义身份或能力。",
          dimensions: [
            { dimension_key: "energy", label: "能量方向", tendency: "moderately_low", summary: "更常通过独处整理复杂想法。" },
            { dimension_key: "information", label: "信息方式", tendency: "high", summary: "偏好模式、可能性与长期联系。" },
            { dimension_key: "decisions", label: "决策依据", tendency: "balanced", summary: "逻辑和价值考虑会共同参与。" },
            { dimension_key: "lifestyle", label: "生活方式", tendency: "moderately_high", summary: "倾向建立方向，同时保留调整空间。" },
          ],
          caveats: ["没有进行标准化问卷。", "类型可能随情境呈现不同侧面。"],
        },
      ],
      uncertainty_note: "样本仍可能集中于少数对话场景，因此结果应视为可修订的工作模型。",
      provider_name: "mock",
      model_name: "mock-structured-1",
      input_insight_count: 12,
      omitted_insight_count: 0,
    },
    evidence_index: [],
    sections: profileDetail.document.sections.map((section) => ({
      ...section,
      items: section.items.map((item) => ({ ...item, evidence_refs: [] })),
    })),
  },
};
