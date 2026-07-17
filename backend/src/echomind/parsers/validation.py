"""Central time parsing and Canonical cross-record validation."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from echomind.parsers.errors import ErrorCode, ParserError, safe_display_name
from echomind.parsers.options import ErrorMode
from echomind.parsers.schemas import (
    CanonicalConversation,
    CanonicalMessage,
    ParsedChatFile,
    ParseStatistics,
    ParseWarning,
)


def parse_timestamp(value: object, default_timezone: str | None = None) -> datetime:
    """Parse deterministic ISO/RFC3339 time and reject implicit local time."""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        candidate = value.strip()
        if candidate.endswith(("Z", "z")):
            candidate = f"{candidate[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as error:
            raise ValueError("timestamp is not valid ISO 8601/RFC 3339") from error
    else:
        raise ValueError("timestamp must be a non-empty string or datetime")

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        if default_timezone is None:
            raise ValueError("timestamp has no timezone")
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(default_timezone))
        except (ValueError, ZoneInfoNotFoundError) as error:
            raise ValueError("default timezone is invalid") from error
    return parsed


def parse_optional_timestamp(value: object, default_timezone: str | None = None) -> datetime | None:
    if value is None or value == "":
        return None
    return parse_timestamp(value, default_timezone)


def parse_optional_bool(value: object) -> bool | None:
    if value is None or value == "":
        return None
    if value is True or value == "true":
        return True
    if value is False or value == "false":
        return False
    raise ValueError("boolean must be true, false, or empty")


def _error(
    code: ErrorCode,
    *,
    filename: str,
    parser_name: str,
    message: str,
    location: str | None = None,
    recoverable: bool = False,
    details: dict[str, object] | None = None,
) -> ParserError:
    return ParserError(
        code,
        safe_filename=filename,
        parser_name=parser_name,
        message=message,
        location=location,
        recoverable=recoverable,
        details=details,
    )


def _record_problem(
    error: ParserError,
    *,
    error_mode: ErrorMode,
    warnings: list[ParseWarning],
) -> bool:
    """Return True when lenient mode skipped the record."""

    if error_mode is ErrorMode.STRICT or not error.recoverable:
        raise error
    warnings.append(
        ParseWarning(
            error_code=error.error_code,
            message=error.message,
            location=error.location,
            recoverable=True,
            details=error.details,
        )
    )
    return True


def _validate_participants(
    conversation: CanonicalConversation,
    *,
    filename: str,
    parser_name: str,
) -> set[str]:
    if not conversation.participants:
        raise _error(
            ErrorCode.INVALID_STRUCTURE,
            filename=filename,
            parser_name=parser_name,
            message="A conversation must declare at least one participant.",
            location=f"conversation:{conversation.source_conversation_id}",
        )

    identifiers: set[str] = set()
    owner_count = 0
    for participant in conversation.participants:
        owner_count += participant.is_profile_owner is True
        identifier = participant.source_participant_id
        if identifier is None:
            continue
        if identifier in identifiers:
            raise _error(
                ErrorCode.DUPLICATE_PARTICIPANT,
                filename=filename,
                parser_name=parser_name,
                message="A participant identifier is duplicated within a conversation.",
                location=f"conversation:{conversation.source_conversation_id}",
                details={"participant_id": identifier},
            )
        identifiers.add(identifier)

    if owner_count > 1:
        raise _error(
            ErrorCode.MULTIPLE_PROFILE_OWNERS,
            filename=filename,
            parser_name=parser_name,
            message="A conversation declares more than one profile owner.",
            location=f"conversation:{conversation.source_conversation_id}",
        )
    return identifiers


def _filter_messages(
    conversation: CanonicalConversation,
    participant_ids: set[str],
    *,
    filename: str,
    parser_name: str,
    error_mode: ErrorMode,
    warnings: list[ParseWarning],
) -> tuple[list[CanonicalMessage], int]:
    accepted: list[CanonicalMessage] = []
    accepted_ids: set[str] = set()
    skipped = 0

    for message in conversation.messages:
        problem: ParserError | None = None
        if message.source_message_id in accepted_ids:
            problem = _error(
                ErrorCode.DUPLICATE_MESSAGE,
                filename=filename,
                parser_name=parser_name,
                message="A message identifier is duplicated within a conversation.",
                location=message.source_location,
                recoverable=True,
                details={"message_id": message.source_message_id},
            )
        elif message.sender_source_id not in participant_ids:
            problem = _error(
                ErrorCode.UNKNOWN_SENDER,
                filename=filename,
                parser_name=parser_name,
                message="A message references an undeclared participant.",
                location=message.source_location,
                recoverable=True,
                details={"sender_id": message.sender_source_id},
            )

        if problem is not None and _record_problem(
            problem,
            error_mode=error_mode,
            warnings=warnings,
        ):
            skipped += 1
            continue
        accepted.append(message)
        accepted_ids.add(message.source_message_id)

    while True:
        current_ids = {message.source_message_id for message in accepted}
        dangling = next(
            (
                message
                for message in accepted
                if message.reply_to_source_message_id is not None
                and message.reply_to_source_message_id not in current_ids
            ),
            None,
        )
        if dangling is None:
            break
        problem = _error(
            ErrorCode.UNKNOWN_REPLY,
            filename=filename,
            parser_name=parser_name,
            message="A reply references a message outside the current conversation.",
            location=dangling.source_location,
            recoverable=True,
            details={"reply_to_message_id": dangling.reply_to_source_message_id},
        )
        if _record_problem(problem, error_mode=error_mode, warnings=warnings):
            accepted.remove(dangling)
            skipped += 1

    return accepted, skipped


def finalize_parsed_chat(
    *,
    source_filename: str,
    file_hash: str,
    parser_name: str,
    parser_version: str,
    conversations: list[CanonicalConversation],
    warnings: list[ParseWarning],
    skipped_record_count: int,
    error_mode: ErrorMode,
) -> ParsedChatFile:
    """Validate references, derive ranges, sort stably, and calculate statistics."""

    filename = safe_display_name(source_filename)
    if not conversations:
        code = (
            ErrorCode.NO_VALID_MESSAGES
            if skipped_record_count > 0
            else ErrorCode.NO_VALID_CONVERSATIONS
        )
        raise _error(
            code,
            filename=filename,
            parser_name=parser_name,
            message="The file contains no valid conversations.",
        )

    conversation_ids: set[str] = set()
    finalized: list[CanonicalConversation] = []
    all_warnings = list(warnings)
    cross_record_skips = 0

    for conversation in conversations:
        if conversation.source_conversation_id in conversation_ids:
            raise _error(
                ErrorCode.DUPLICATE_CONVERSATION,
                filename=filename,
                parser_name=parser_name,
                message="A conversation identifier is duplicated.",
                location=f"conversation:{conversation.source_conversation_id}",
            )
        conversation_ids.add(conversation.source_conversation_id)
        participant_ids = _validate_participants(
            conversation,
            filename=filename,
            parser_name=parser_name,
        )
        messages, skipped = _filter_messages(
            conversation,
            participant_ids,
            filename=filename,
            parser_name=parser_name,
            error_mode=error_mode,
            warnings=all_warnings,
        )
        cross_record_skips += skipped
        if not messages:
            if error_mode is ErrorMode.STRICT:
                raise _error(
                    ErrorCode.NO_VALID_MESSAGES,
                    filename=filename,
                    parser_name=parser_name,
                    message="A conversation contains no valid messages.",
                    location=f"conversation:{conversation.source_conversation_id}",
                )
            continue

        ordered = sorted(messages, key=lambda item: (item.timestamp, item.source_order))
        derived = (
            conversation.time_range_derived
            or conversation.started_at is None
            or conversation.ended_at is None
        )
        started_at = conversation.started_at or min(item.timestamp for item in ordered)
        ended_at = conversation.ended_at or max(item.timestamp for item in ordered)
        if ended_at < started_at:
            raise _error(
                ErrorCode.INVALID_TIME_RANGE,
                filename=filename,
                parser_name=parser_name,
                message="A conversation time range is invalid.",
                location=f"conversation:{conversation.source_conversation_id}",
            )
        finalized.append(
            conversation.model_copy(
                update={
                    "messages": ordered,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "time_range_derived": derived,
                }
            )
        )

    message_count = sum(len(item.messages) for item in finalized)
    if not finalized:
        raise _error(
            ErrorCode.NO_VALID_MESSAGES,
            filename=filename,
            parser_name=parser_name,
            message="The file contains no valid conversations.",
        )
    if message_count == 0:
        raise _error(
            ErrorCode.NO_VALID_MESSAGES,
            filename=filename,
            parser_name=parser_name,
            message="The file contains no valid messages.",
        )

    statistics = ParseStatistics(
        conversation_count=len(finalized),
        participant_count=sum(len(item.participants) for item in finalized),
        message_count=message_count,
        accepted_record_count=message_count,
        skipped_record_count=skipped_record_count + cross_record_skips,
        warning_count=len(all_warnings),
    )
    return ParsedChatFile(
        source_filename=filename,
        file_hash=file_hash,
        parser_name=parser_name,
        parser_version=parser_version,
        conversations=finalized,
        warnings=all_warnings,
        statistics=statistics,
    )


def validate_parsed_chat(result: ParsedChatFile) -> ParsedChatFile:
    """Revalidate an existing result and reject stale statistics or ordering."""

    rebuilt = finalize_parsed_chat(
        source_filename=result.source_filename,
        file_hash=result.file_hash,
        parser_name=result.parser_name,
        parser_version=result.parser_version,
        conversations=result.conversations,
        warnings=result.warnings,
        skipped_record_count=result.statistics.skipped_record_count,
        error_mode=ErrorMode.STRICT,
    )
    if rebuilt.model_dump() != result.model_dump():
        raise _error(
            ErrorCode.STATISTICS_MISMATCH,
            filename=result.source_filename,
            parser_name=result.parser_name,
            message="Parser statistics or canonical ordering are inconsistent.",
        )
    return result
