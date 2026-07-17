export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ImportDetail {
  source_file_id: string;
  filename: string;
  file_hash: string;
  file_type: string;
  byte_size: number;
  parser_name: string;
  parser_version: string;
  cleaning_pipeline_version: string;
  imported_at: string;
  conversation_count: number;
  participant_count: number;
  message_count: number;
  excluded_message_count: number;
  analysis_unit_count: number;
  parser_warning_count: number;
  cleaning_warning_count: number;
  warnings: Array<{ error_code: string; message: string; location?: string }>;
  links: { self: string; conversations: string };
}

export type ImportResponse = ImportDetail;

export interface ConversationSummary {
  id: string;
  source_file_id: string;
  platform: string;
  title: string | null;
  started_at: string | null;
  ended_at: string | null;
  participant_count: number;
  message_count: number;
  excluded_message_count: number;
}

export interface ConversationDetail extends ConversationSummary {
  source_conversation_id: string | null;
  participants: Array<{
    id: string;
    display_name: string;
    aliases: string[];
    is_profile_owner: boolean;
  }>;
}

export interface MessageSummary {
  id: string;
  conversation_id: string;
  source_message_id: string;
  sender_id: string;
  sender_display_name: string;
  timestamp: string | null;
  message_type: string;
  raw_content: string;
  normalized_content: string;
  reply_to_message_id: string | null;
  source_order: number;
  is_system_message: boolean;
  is_recalled_message: boolean;
  duplicate_of_message_id: string | null;
  excluded_from_analysis: boolean;
  exclusion_reasons: string[];
}

export interface APIErrorBody {
  error_code: string;
  message: string;
  recoverable?: boolean;
  safe_filename?: string;
  location?: string;
}

export class APIError extends Error {
  constructor(
    readonly status: number,
    readonly body: APIErrorBody,
  ) {
    super(body.message);
    this.name = "APIError";
  }
}
