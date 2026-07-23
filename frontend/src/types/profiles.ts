import type { EvidenceState, InsightType } from "./insights";

export type ProfileSourceStatus = "current" | "stale" | "source_unavailable";
export type EvidenceMode = "references" | "excerpts";
export type PersonalityTendency = "low" | "moderately_low" | "balanced" | "moderately_high" | "high" | "insufficient";
export type AssessmentConfidence = "low" | "medium" | "high" | "insufficient";

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

export interface PersonalityDimension {
  dimension_key: string;
  label: string;
  tendency: PersonalityTendency;
  summary: string;
}

export interface PersonalityFrameworkAssessment {
  framework: "big_five" | "mbti";
  display_name: string;
  result: string;
  confidence: AssessmentConfidence;
  summary: string;
  dimensions: PersonalityDimension[];
  caveats: string[];
}

export interface PersonalitySynthesis {
  synthesis_version: "personality-synthesis-1.0";
  headline: string;
  overall_summary: string;
  core_traits: string[];
  thinking_style: string;
  decision_style: string;
  motivation_and_values: string;
  social_and_relationship_style: string;
  emotional_and_stress_patterns: string;
  strengths: string[];
  growth_edges: string[];
  tensions_and_changes: string[];
  framework_assessments: PersonalityFrameworkAssessment[];
  uncertainty_note: string;
  provider_name: string;
  model_name: string;
  input_insight_count: number;
  omitted_insight_count: number;
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
  personality_synthesis: PersonalitySynthesis | null;
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
  includePersonalitySynthesis: boolean;
  remoteConsent: boolean;
  generatedAsOf: string;
}
