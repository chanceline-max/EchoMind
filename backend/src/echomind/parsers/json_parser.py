"""Parser for the explicit EchoMind generic JSON v1 format."""

import json
from pathlib import Path
from typing import Any, ClassVar

from pydantic import ValidationError

from echomind.parsers.base import (
    ParseState,
    read_signature,
    read_source_text,
    reject_unknown_fields,
    require_fields,
    validation_fields,
)
from echomind.parsers.errors import ErrorCode, ParserError, safe_display_name
from echomind.parsers.hashing import hash_file
from echomind.parsers.options import ParserOptions
from echomind.parsers.schemas import (
    CanonicalConversation,
    CanonicalMessage,
    CanonicalParticipant,
    MessageType,
    ParsedChatFile,
)
from echomind.parsers.validation import (
    finalize_parsed_chat,
    parse_optional_bool,
    parse_optional_timestamp,
    parse_timestamp,
    validate_parsed_chat,
)


class GenericJsonParser:
    parser_name = "generic-json"
    parser_version = "1.0"
    supported_extensions: frozenset[str] = frozenset({".json"})
    available = True

    _top_fields: ClassVar[set[str]] = {"format", "version", "platform", "conversations"}
    _conversation_fields: ClassVar[set[str]] = {
        "id",
        "title",
        "platform",
        "started_at",
        "ended_at",
        "participants",
        "messages",
        "metadata_json",
    }
    _participant_fields: ClassVar[set[str]] = {
        "id",
        "name",
        "aliases",
        "is_profile_owner",
        "metadata_json",
    }
    _message_fields: ClassVar[set[str]] = {
        "id",
        "sender_id",
        "timestamp",
        "type",
        "content",
        "reply_to_message_id",
        "metadata_json",
    }

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() not in self.supported_extensions:
            return False
        signature = read_signature(path).lstrip(b"\xef\xbb\xbf\x20\t\r\n")
        return b'"format"' in signature and b'"echomind-generic-chat"' in signature

    def parse(self, path: Path, options: ParserOptions | None = None) -> ParsedChatFile:
        parse_options = options or ParserOptions()
        filename = safe_display_name(path)
        file_hash = hash_file(path)
        text = read_source_text(path, parse_options, self.parser_name)
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, RecursionError):
            raise ParserError(
                ErrorCode.INVALID_JSON,
                safe_filename=filename,
                parser_name=self.parser_name,
                message="The file is not valid JSON.",
                recoverable=False,
            ) from None

        if not isinstance(payload, dict):
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "The JSON root must be an object.",
                location="/",
            )
        reject_unknown_fields(
            payload,
            self._top_fields,
            safe_filename=filename,
            parser_name=self.parser_name,
            location="/",
            recoverable=False,
        )
        if "format" not in payload:
            raise self._error(
                ErrorCode.INVALID_FORMAT,
                filename,
                "The JSON format identifier is required.",
                location="/format",
            )
        require_fields(
            payload,
            self._top_fields,
            safe_filename=filename,
            parser_name=self.parser_name,
            location="/",
            recoverable=False,
        )
        if payload["format"] != "echomind-generic-chat":
            raise self._error(
                ErrorCode.INVALID_FORMAT,
                filename,
                "The JSON format identifier is not supported.",
                location="/format",
            )
        if payload["version"] != "1.0":
            raise self._error(
                ErrorCode.UNSUPPORTED_VERSION,
                filename,
                "The JSON format version is not supported.",
                location="/version",
                details={"supported_versions": ["1.0"]},
            )
        platform = payload["platform"]
        raw_conversations = payload["conversations"]
        if not isinstance(platform, str) or not platform.strip():
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "The top-level platform must be a non-empty string.",
                location="/platform",
            )
        if not isinstance(raw_conversations, list):
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "The conversations field must be an array.",
                location="/conversations",
            )

        state = ParseState(parse_options)
        conversations = [
            self._parse_conversation(item, index, platform, filename, state)
            for index, item in enumerate(raw_conversations)
        ]
        result = finalize_parsed_chat(
            source_filename=filename,
            file_hash=file_hash,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            conversations=conversations,
            warnings=state.warnings,
            skipped_record_count=state.skipped_record_count,
            error_mode=parse_options.error_mode,
        )
        return self.validate(result)

    def validate(self, result: ParsedChatFile) -> ParsedChatFile:
        return validate_parsed_chat(result)

    def _parse_conversation(
        self,
        raw: object,
        index: int,
        default_platform: str,
        filename: str,
        state: ParseState,
    ) -> CanonicalConversation:
        location = f"/conversations/{index}"
        if not isinstance(raw, dict):
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "Each conversation must be an object.",
                location=location,
            )
        reject_unknown_fields(
            raw,
            self._conversation_fields,
            safe_filename=filename,
            parser_name=self.parser_name,
            location=location,
            recoverable=False,
        )
        require_fields(
            raw,
            {"id", "participants", "messages"},
            safe_filename=filename,
            parser_name=self.parser_name,
            location=location,
            recoverable=False,
        )
        if not isinstance(raw["participants"], list) or not isinstance(raw["messages"], list):
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "Conversation participants and messages must be arrays.",
                location=location,
            )
        participants = [
            self._parse_participant(item, f"{location}/participants/{participant_index}", filename)
            for participant_index, item in enumerate(raw["participants"])
        ]
        messages: list[CanonicalMessage] = []
        for message_index, item in enumerate(raw["messages"]):
            message_location = f"{location}/messages/{message_index}"
            try:
                messages.append(
                    self._parse_message(
                        item,
                        message_index,
                        message_location,
                        filename,
                        state.options,
                    )
                )
            except ParserError as error:
                state.reject_record(error)

        try:
            started_at = parse_optional_timestamp(
                raw.get("started_at"),
                state.options.default_timezone,
            )
            ended_at = parse_optional_timestamp(
                raw.get("ended_at"),
                state.options.default_timezone,
            )
        except ValueError:
            raise self._error(
                ErrorCode.INVALID_TIMESTAMP,
                filename,
                "A conversation time is invalid or lacks a timezone.",
                location=location,
            ) from None
        try:
            return CanonicalConversation(
                source_conversation_id=raw["id"],
                platform=raw.get("platform", default_platform),
                title=raw.get("title"),
                started_at=started_at,
                ended_at=ended_at,
                participants=participants,
                messages=messages,
                metadata_json=raw.get("metadata_json", {}),
            )
        except ValidationError as error:
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "A conversation does not match the canonical schema.",
                location=location,
                details={"fields": validation_fields(error)},
            ) from None

    def _parse_participant(
        self,
        raw: object,
        location: str,
        filename: str,
    ) -> CanonicalParticipant:
        if not isinstance(raw, dict):
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "Each participant must be an object.",
                location=location,
            )
        reject_unknown_fields(
            raw,
            self._participant_fields,
            safe_filename=filename,
            parser_name=self.parser_name,
            location=location,
            recoverable=False,
        )
        require_fields(
            raw,
            {"id", "name"},
            safe_filename=filename,
            parser_name=self.parser_name,
            location=location,
            recoverable=False,
        )
        try:
            owner = parse_optional_bool(raw.get("is_profile_owner"))
            return CanonicalParticipant(
                source_participant_id=raw["id"],
                display_name=raw["name"],
                aliases=raw.get("aliases", []),
                is_profile_owner=owner,
                metadata_json=raw.get("metadata_json", {}),
            )
        except (ValueError, ValidationError) as error:
            fields = validation_fields(error) if isinstance(error, ValidationError) else []
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "A participant does not match the canonical schema.",
                location=location,
                details={"fields": fields},
            ) from None

    def _parse_message(
        self,
        raw: object,
        source_order: int,
        location: str,
        filename: str,
        options: ParserOptions,
    ) -> CanonicalMessage:
        if not isinstance(raw, dict):
            raise self._error(
                ErrorCode.INVALID_RECORD,
                filename,
                "A message record must be an object.",
                location=location,
                recoverable=True,
            )
        reject_unknown_fields(
            raw,
            self._message_fields,
            safe_filename=filename,
            parser_name=self.parser_name,
            location=location,
            recoverable=True,
        )
        require_fields(
            raw,
            {"id", "sender_id", "timestamp", "type", "content"},
            safe_filename=filename,
            parser_name=self.parser_name,
            location=location,
            recoverable=True,
        )
        try:
            timestamp = parse_timestamp(raw["timestamp"], options.default_timezone)
        except ValueError:
            raise self._error(
                ErrorCode.INVALID_TIMESTAMP,
                filename,
                "A message timestamp is invalid or lacks a timezone.",
                location=location,
                recoverable=True,
            ) from None
        try:
            message_type = MessageType(raw["type"])
        except (ValueError, TypeError):
            raise self._error(
                ErrorCode.UNSUPPORTED_MESSAGE_TYPE,
                filename,
                "The message type is not supported.",
                location=location,
                recoverable=True,
            ) from None
        try:
            return CanonicalMessage(
                source_message_id=raw["id"],
                sender_source_id=raw["sender_id"],
                timestamp=timestamp,
                message_type=message_type,
                raw_content=raw["content"],
                normalized_content=raw["content"],
                reply_to_source_message_id=raw.get("reply_to_message_id"),
                source_order=source_order,
                source_location=location,
                metadata_json=raw.get("metadata_json", {}),
            )
        except ValidationError as error:
            raise self._error(
                ErrorCode.INVALID_RECORD,
                filename,
                "A message does not match the canonical schema.",
                location=location,
                recoverable=True,
                details={"fields": validation_fields(error)},
            ) from None

    def _error(
        self,
        code: ErrorCode,
        filename: str,
        message: str,
        *,
        location: str | None = None,
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> ParserError:
        return ParserError(
            code,
            safe_filename=filename,
            parser_name=self.parser_name,
            message=message,
            location=location,
            recoverable=recoverable,
            details=details,
        )
