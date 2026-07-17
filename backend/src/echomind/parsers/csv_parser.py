"""Parser for the fixed EchoMind generic CSV v1 format."""

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from echomind.parsers.base import ParseState, read_signature, read_source_text, validation_fields
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
    parse_timestamp,
    validate_parsed_chat,
)

CSV_HEADERS = [
    "conversation_id",
    "conversation_title",
    "platform",
    "message_id",
    "sender_id",
    "sender_name",
    "is_profile_owner",
    "timestamp",
    "message_type",
    "content",
    "reply_to_message_id",
]


@dataclass
class _ConversationBuilder:
    identifier: str
    title: str
    platform: str
    participants: dict[str, CanonicalParticipant] = field(default_factory=dict)
    messages: list[CanonicalMessage] = field(default_factory=list)


class GenericCsvParser:
    parser_name = "generic-csv"
    parser_version = "1.0"
    supported_extensions: frozenset[str] = frozenset({".csv"})
    available = True

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() not in self.supported_extensions:
            return False
        first_line = read_signature(path).lstrip(b"\xef\xbb\xbf").splitlines()[:1]
        if not first_line:
            return False
        try:
            header = next(csv.reader([first_line[0].decode("utf-8")]))
        except (UnicodeError, csv.Error):
            return False
        return header == CSV_HEADERS

    def parse(self, path: Path, options: ParserOptions | None = None) -> ParsedChatFile:
        parse_options = options or ParserOptions()
        filename = safe_display_name(path)
        file_hash = hash_file(path)
        text = read_source_text(path, parse_options, self.parser_name)
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if reader.fieldnames != CSV_HEADERS:
            actual = reader.fieldnames or []
            raise self._error(
                ErrorCode.INVALID_HEADERS,
                filename,
                "The CSV header does not match the generic CSV v1 contract.",
                location="line:1",
                details={
                    "missing_headers": sorted(set(CSV_HEADERS) - set(actual)),
                    "extra_headers": sorted(set(actual) - set(CSV_HEADERS)),
                },
            )

        state = ParseState(parse_options)
        builders: dict[str, _ConversationBuilder] = {}
        try:
            for source_order, row in enumerate(reader):
                location = f"line:{reader.line_num}"
                try:
                    self._parse_row(
                        row,
                        source_order,
                        location,
                        filename,
                        parse_options,
                        builders,
                    )
                except ParserError as error:
                    state.reject_record(error)
        except csv.Error:
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "The CSV file could not be parsed as a complete table.",
            ) from None

        conversations = [
            CanonicalConversation(
                source_conversation_id=builder.identifier,
                title=builder.title or None,
                platform=builder.platform,
                participants=list(builder.participants.values()),
                messages=builder.messages,
            )
            for builder in builders.values()
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

    def _parse_row(
        self,
        row: dict[str | None, str | list[str] | None],
        source_order: int,
        location: str,
        filename: str,
        options: ParserOptions,
        builders: dict[str, _ConversationBuilder],
    ) -> None:
        if None in row or any(value is None for value in row.values()):
            raise self._error(
                ErrorCode.INVALID_RECORD,
                filename,
                "The CSV row has an invalid number of columns.",
                location=location,
                recoverable=True,
            )
        values = {key: str(value) for key, value in row.items() if key is not None}
        required_non_empty = {
            "conversation_id",
            "platform",
            "message_id",
            "sender_id",
            "sender_name",
            "timestamp",
            "message_type",
        }
        missing = sorted(field for field in required_non_empty if not values[field].strip())
        if missing:
            raise self._error(
                ErrorCode.MISSING_REQUIRED_FIELD,
                filename,
                "A required CSV value is missing.",
                location=location,
                recoverable=True,
                details={"fields": missing},
            )
        try:
            owner = parse_optional_bool(values["is_profile_owner"].strip().lower())
        except ValueError:
            raise self._error(
                ErrorCode.INVALID_BOOLEAN,
                filename,
                "The profile-owner value must be true, false, or empty.",
                location=location,
                recoverable=True,
            ) from None
        try:
            timestamp = parse_timestamp(values["timestamp"], options.default_timezone)
        except ValueError:
            raise self._error(
                ErrorCode.INVALID_TIMESTAMP,
                filename,
                "A message timestamp is invalid or lacks a timezone.",
                location=location,
                recoverable=True,
            ) from None
        try:
            message_type = MessageType(values["message_type"].strip())
        except ValueError:
            raise self._error(
                ErrorCode.UNSUPPORTED_MESSAGE_TYPE,
                filename,
                "The message type is not supported.",
                location=location,
                recoverable=True,
            ) from None

        try:
            participant = CanonicalParticipant(
                source_participant_id=values["sender_id"],
                display_name=values["sender_name"],
                is_profile_owner=owner,
            )
            message = CanonicalMessage(
                source_message_id=values["message_id"],
                sender_source_id=values["sender_id"],
                timestamp=timestamp,
                message_type=message_type,
                raw_content=values["content"],
                normalized_content=values["content"],
                reply_to_source_message_id=values["reply_to_message_id"] or None,
                source_order=source_order,
                source_location=location,
            )
        except ValidationError as error:
            raise self._error(
                ErrorCode.INVALID_RECORD,
                filename,
                "A CSV row does not match the canonical schema.",
                location=location,
                recoverable=True,
                details={"fields": validation_fields(error)},
            ) from None

        conversation_id = values["conversation_id"]
        title = values["conversation_title"]
        platform = values["platform"]
        builder = builders.get(conversation_id)
        if builder is None:
            builder = _ConversationBuilder(conversation_id, title, platform)
            builders[conversation_id] = builder
        elif (builder.title and title and builder.title != title) or builder.platform != platform:
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "Conversation metadata conflicts across CSV rows.",
                location=location,
            )

        existing = builder.participants.get(values["sender_id"])
        if existing is not None and (
            existing.display_name != participant.display_name
            or existing.is_profile_owner != participant.is_profile_owner
        ):
            raise self._error(
                ErrorCode.PARTICIPANT_CONFLICT,
                filename,
                "A participant identifier has conflicting CSV values.",
                location=location,
                details={"participant_id": values["sender_id"]},
            )
        builder.participants.setdefault(values["sender_id"], participant)
        builder.messages.append(message)

    def _error(
        self,
        code: ErrorCode,
        filename: str,
        message: str,
        *,
        location: str | None = None,
        recoverable: bool = False,
        details: dict[str, object] | None = None,
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
