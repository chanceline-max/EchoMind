import type { EvidenceState, InsightType } from "./insights";

export type ProfileSourceStatus = "current" | "stale" | "source_unavailable";
export type EvidenceMode = "references" | "excerpts";

export interface ProfileEvidenceItem {
  profile_evidence_ref: string;
  evidence_id: string;
  message_id: string;
  conversation_id: string;
  evidence_type: string;
  role: "supports" | "contradicts" | "context";
  relevance_score: number;
  is_valid: boolean;
  invalidation_reasons: string[];
  message_timestamp: string | null;
  sender_role: "PROFILE_OWNER" | "OTHER";
  excerpt: string | null;
}

export interface ProfileInsightItem {
  profile_insight_ref: string;
  insight_id: string;
  insight_revision_number: number;
  insight_type: InsightType;
  category: string;
  title: string;
  statement: string;
  confidence: number;
  confidence_version: string;
  confidence_explanation: string;
  evidence_state: EvidenceState;
  explicit_self_report: boolean;
  valid_from: string | null;
  valid_to: string | null;
  reasoning_basis: string | null;
  alternative_explanations: string[];
  evidence_refs: string[];
  warnings: string[];
  minimum_rule_code: string | null;
  source_status_at_generation: "current";
  valid_evidence_count: number;
  invalid_evidence_count: number;
}

export interface ProfileSection {
  section_key: string;
  title: string;
  description: string;
  items: ProfileInsightItem[];
}

export interface ProfileDocument {
  metadata: {
    profile_id: string;
    profile_version: string;
    schema_version: string;
    generated_at: string;
    generated_as_of: string;
    selection_policy: "confirmed-only-1.0";
    scope: "all_confirmed" | "selected_confirmed";
    evidence_mode: EvidenceMode;
    source_fingerprint: string;
    generation_fingerprint: string;
    document_hash: string;
    confirmed_insight_count: number;
    included_valid_count: number;
    included_partial_count: number;
    invalidated_count: number;
    excluded_count: number;
    evidence_count: number;
    conversation_count: number;
    source_file_count: number;
    limitations: string[];
  };
  sections: ProfileSection[];
  evidence_index: ProfileEvidenceItem[];
}

export interface ProfileSummary {
  id: string;
  generated_at: string;
  profile_version: string;
  schema_version: string;
  insight_count: number;
  evidence_count: number;
  evidence_mode: EvidenceMode;
  document_hash: string;
  current_source_status: ProfileSourceStatus;
  stale_reason_codes: string[];
}

export interface ProfilePage {
  items: ProfileSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface ProfileDetail extends ProfileSummary {
  document: ProfileDocument;
  links: { self: string; markdown: string; json: string };
}

export interface ProfileGenerationResponse {
  profile_snapshot_id: string;
  profile_version: string;
  schema_version: string;
  generated_at: string;
  source_fingerprint: string;
  generation_fingerprint: string;
  document_hash: string;
  insight_count: number;
  evidence_count: number;
  source_status: "current";
  created: boolean;
  reused: boolean;
  links: { self: string; markdown: string; json: string };
}

export interface ProfileGenerationOptions {
  includePartialEvidence: boolean;
  includeInvalidated: boolean;
  evidenceMode: EvidenceMode;
  includeReasoning: boolean;
  generatedAsOf: string;
}
