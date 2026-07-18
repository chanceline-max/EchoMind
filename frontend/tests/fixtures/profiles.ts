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
