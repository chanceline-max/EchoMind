export type InsightStatus = "proposed" | "confirmed" | "rejected" | "superseded";
export type InsightType =
  | "fact"
  | "preference"
  | "pattern"
  | "inference"
  | "hypothesis"
  | "contradiction"
  | "change";
export type EvidenceState = "valid" | "partial" | "invalid";

export interface InsightSummary {
  id: string;
  title: string;
  statement_summary: string;
  category: string;
  insight_type: InsightType;
  status: InsightStatus;
  confidence: number;
  confidence_version: string;
  model_confidence: number | null;
  evidence_state: EvidenceState;
  evidence_count: number;
  valid_evidence_count: number;
  contradicting_evidence_count: number;
  valid_from: string | null;
  valid_to: string | null;
  revision_number: number;
  reviewed_at: string | null;
  superseded_by_insight_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvidenceDetail {
  evidence_id: string;
  evidence_type: string;
  stance: string;
  relevance_score: number;
  is_valid: boolean;
  invalidation_reasons: string[];
  invalidated_at: string | null;
  excerpt: string;
  message_id: string;
  conversation_id: string;
  message_timestamp: string | null;
  sender_role: "PROFILE_OWNER" | "OTHER";
  message_excluded_from_analysis: boolean;
  message_link: string;
}

export interface InsightDetail extends InsightSummary {
  statement: string;
  reasoning_basis: string | null;
  alternative_explanations: string[];
  explicit_self_report: boolean;
  extraction_version: string;
  provider_name: string | null;
  confidence_explanation: string | null;
  confidence_factors: Record<string, unknown> | null;
  review_note: string | null;
  evidence: EvidenceDetail[];
  allowed_actions: string[];
}

export interface InsightRevision {
  id: string;
  insight_id: string;
  revision_number: number;
  action: string;
  actor_type: "local_user" | "system";
  created_at: string;
  expected_previous_revision: number;
  changed_fields_json: Record<string, unknown>;
  snapshot_json: Record<string, unknown>;
  note: string | null;
}

export interface InsightPage {
  items: InsightSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface RevisionPage {
  items: InsightRevision[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReviewMutationResponse {
  insight: InsightDetail;
  revision: InsightRevision;
}

export interface InsightFilters {
  status: string;
  insightType: string;
  category: string;
  evidenceState: string;
  minConfidence: string;
  maxConfidence: string;
  sort: string;
  offset: number;
}
