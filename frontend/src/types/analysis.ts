export interface AnalysisCapabilities {
  configured_provider: string;
  provider_available: boolean;
  remote_provider: boolean;
  remote_consent_required: boolean;
  extraction_version: string;
  confidence_version: string;
  max_conversations_per_request: number;
}

export interface AnalysisErrorRecord {
  error_code: string;
  message: string;
  recoverable: boolean;
  insight_id?: string;
  conversation_id?: string;
  window_id?: string;
}

export interface AnalysisResponse {
  request_id: string;
  provider_name: string;
  conversation_count: number;
  selected_message_count: number;
  window_count: number;
  successful_window_count: number;
  failed_window_count: number;
  candidates_received: number;
  candidates_accepted: number;
  insights_created: number;
  insights_reused: number;
  insight_ids: string[];
  confidence_scored_count: number;
  confidence_failed_count: number;
  stopped_early: boolean;
  errors: AnalysisErrorRecord[];
  insights_link: string;
}

export interface StartAnalysisInput {
  conversationIds: string[];
  remoteConsent: boolean;
}
