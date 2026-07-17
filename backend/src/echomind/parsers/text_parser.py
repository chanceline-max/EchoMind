"""Parser for one fixed, documented synthetic-friendly text format."""

import re
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
from echomind.parsers.validation import finalize_parsed_chat, parse_timestamp, validate_parsed_chat

_MESSAGE_PATTERN = re.compile(
    r"^\[(?P<message_id>[^\[\]]+)\]"
    r"\[(?P<timestamp>[^\[\]]+)\] "
    r"<(?P<sender_id>[^<>]+)> (?P<content>.*)$"
)


class GenericTextParser:
    parser_name = "generic-text"
    parser_version = "1.0"
    supported_extensions: frozenset[str] = frozenset({".txt"})
    available = True

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() not in self.supported_extensions:
            return False
        signature = read_signature(path).lstrip(b"\xef\xbb\xbf\x20\t\r\n")
        return signature.startswith(b"# conversation:")

    def parse(self, path: Path, options: ParserOptions | None = None) -> ParsedChatFile:
        parse_options = options or ParserOptions()
        filename = safe_display_name(path)
        file_hash = hash_file(path)
        text = read_source_text(path, parse_options, self.parser_name)
        if not text.strip():
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "The text file is empty.",
            )

        state = ParseState(parse_options)
        scalar_headers: dict[str, str] = {}
        participants: list[CanonicalParticipant] = []
        messages: list[CanonicalMessage] = []
        message_section_started = False

        for line_number, line in enumerate(text.splitlines(), start=1):
            location = f"line:{line_number}"
            if not line.strip() or line.startswith("##"):
                continue
            if line.startswith("# participant:"):
                if message_section_started:
                    raise self._error(
                        ErrorCode.INVALID_STRUCTURE,
                        filename,
                        "Participant declarations must appear before messages.",
                        location=location,
                    )
                participants.append(self._parse_participant(line, location, filename))
                continue
            if line.startswith("#"):
                if message_section_started:
                    raise self._error(
                        ErrorCode.INVALID_STRUCTURE,
                        filename,
                        "Text headers must appear before messages.",
                        location=location,
                    )
                self._parse_scalar_header(line, location, filename, scalar_headers)
                continue

            message_section_started = True
            try:
                messages.append(
                    self._parse_message(
                        line,
                        line_number,
                        location,
                        filename,
                        scalar_headers.get("timezone") or parse_options.default_timezone,
                    )
                )
            except ParserError as error:
                state.reject_record(error)

        missing_headers = sorted(
            header for header in {"conversation", "platform"} if not scalar_headers.get(header)
        )
        if missing_headers:
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "The text file is missing required headers.",
                details={"headers": missing_headers},
            )
        if not participants:
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "The text file must declare at least one participant.",
            )

        try:
            conversation = CanonicalConversation(
                source_conversation_id=scalar_headers["conversation"],
                title=scalar_headers.get("title") or None,
                platform=scalar_headers["platform"],
                participants=participants,
                messages=messages,
            )
        except ValidationError as error:
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "The text headers do not match the canonical schema.",
                details={"fields": validation_fields(error)},
            ) from None

        result = finalize_parsed_chat(
            source_filename=filename,
            file_hash=file_hash,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            conversations=[conversation],
            warnings=state.warnings,
            skipped_record_count=state.skipped_record_count,
            error_mode=parse_options.error_mode,
        )
        return self.validate(result)

    def validate(self, result: ParsedChatFile) -> ParsedChatFile:
        return validate_parsed_chat(result)

    def _parse_scalar_header(
        self,
        line: str,
        location: str,
        filename: str,
        headers: dict[str, str],
    ) -> None:
        match = re.fullmatch(r"# (conversation|title|platform|timezone):\s*(.*)", line)
        if match is None:
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "The text header is not recognized.",
                location=location,
            )
        name, value = match.groups()
        value = value.strip()
        if name in headers:
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "A text header is declared more than once.",
                location=location,
                details={"header": name},
            )
        if name != "title" and not value:
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "A required text header is empty.",
                location=location,
                details={"header": name},
            )
        headers[name] = value

    def _parse_participant(
        self,
        line: str,
        location: str,
        filename: str,
    ) -> CanonicalParticipant:
        raw = line.removeprefix("# participant:").strip()
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) != 3 or parts[2] not in {"owner", "other"}:
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "A participant declaration is invalid.",
                location=location,
            )
        try:
            return CanonicalParticipant(
                source_participant_id=parts[0],
                display_name=parts[1],
                is_profile_owner=parts[2] == "owner",
            )
        except ValidationError as error:
            raise self._error(
                ErrorCode.INVALID_STRUCTURE,
                filename,
                "A participant declaration does not match the canonical schema.",
                location=location,
                details={"fields": validation_fields(error)},
            ) from None

    def _parse_message(
        self,
        line: str,
        line_number: int,
        location: str,
        filename: str,
        timezone_name: str | None,
    ) -> CanonicalMessage:
        match = _MESSAGE_PATTERN.fullmatch(line)
        if match is None:
            raise self._error(
                ErrorCode.INVALID_RECORD,
                filename,
                "The text line does not match the message format.",
                location=location,
                recoverable=True,
            )
        if timezone_name is None:
            raise self._error(
                ErrorCode.MISSING_TIMEZONE,
                filename,
                "The text format requires a timezone header or explicit option.",
                location=location,
            )
        groups = match.groupdict()
        try:
            timestamp = parse_timestamp(groups["timestamp"], timezone_name)
        except ValueError:
            raise self._error(
                ErrorCode.INVALID_TIMESTAMP,
                filename,
                "A text message timestamp is invalid.",
                location=location,
                recoverable=True,
            ) from None
        try:
            return CanonicalMessage(
                source_message_id=groups["message_id"],
                sender_source_id=groups["sender_id"],
                timestamp=timestamp,
                message_type=MessageType.TEXT,
                raw_content=groups["content"],
                normalized_content=groups["content"],
                source_order=line_number - 1,
                source_location=location,
            )
        except ValidationError as error:
            raise self._error(
                ErrorCode.INVALID_RECORD,
                filename,
                "A text message does not match the canonical schema.",
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
