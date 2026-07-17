"""Synchronous upload, parse, clean, validate, and transactionally persist workflow."""

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from echomind.api.errors import ApiError
from echomind.cleaning import CleaningError, CleaningOptions, clean_chat
from echomind.cleaning.schemas import CleanedChatFile, CleanedConversation, CleanedMessage
from echomind.core.config import Settings
from echomind.db.types import utc_now
from echomind.models import (
    Conversation,
    Message,
    Participant,
    SourceFile,
    conversation_participants,
)
from echomind.models.enums import (
    FileType,
    MessageType,
    SourceFileStatus,
)
from echomind.parsers import ErrorMode, ParserError, ParserOptions, create_default_registry
from echomind.parsers.errors import safe_display_name
from echomind.parsers.schemas import ParsedChatFile
from echomind.repositories.import_repository import find_source_by_hash
from echomind.schemas.imports import ImportDetail, ImportLinks, SafeWarning

SUPPORTED_EXTENSIONS = {".json": FileType.JSON, ".csv": FileType.CSV, ".txt": FileType.TEXT}
LIMITS_VERSION = "stage5-v1"
MAX_SOURCE_ID_CHARACTERS = 255
MAX_TITLE_CHARACTERS = 500
MULTIPART_OVERHEAD_ALLOWANCE = 1_048_576


def _raise_limit(name: str, allowed: int, actual: int) -> None:
    raise ApiError(
        "import_limit_exceeded",
        status_code=422,
        message="The parsed chat exceeds a configured import limit.",
        details={"limit": name, "allowed": allowed, "actual": actual},
    )


def _json_size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _check_metadata(value: object, settings: Settings) -> None:
    size = _json_size(value)
    if size > settings.import_max_metadata_bytes:
        _raise_limit("metadata_bytes", settings.import_max_metadata_bytes, size)


def _validate_canonical_limits(parsed: ParsedChatFile, settings: Settings) -> None:
    conversations = parsed.conversations
    participant_count = sum(len(item.participants) for item in conversations)
    message_count = sum(len(item.messages) for item in conversations)
    if len(conversations) > settings.import_max_conversations:
        _raise_limit("conversations", settings.import_max_conversations, len(conversations))
    if participant_count > settings.import_max_participants:
        _raise_limit("participants", settings.import_max_participants, participant_count)
    if message_count > settings.import_max_messages:
        _raise_limit("messages", settings.import_max_messages, message_count)
    for conversation in conversations:
        if len(conversation.source_conversation_id) > MAX_SOURCE_ID_CHARACTERS:
            _raise_limit(
                "source_id_characters",
                MAX_SOURCE_ID_CHARACTERS,
                len(conversation.source_conversation_id),
            )
        if conversation.title is not None and len(conversation.title) > MAX_TITLE_CHARACTERS:
            _raise_limit("title_characters", MAX_TITLE_CHARACTERS, len(conversation.title))
        _check_metadata(conversation.metadata_json, settings)
        for participant in conversation.participants:
            if (
                participant.source_participant_id is not None
                and len(participant.source_participant_id) > MAX_SOURCE_ID_CHARACTERS
            ):
                _raise_limit(
                    "source_id_characters",
                    MAX_SOURCE_ID_CHARACTERS,
                    len(participant.source_participant_id),
                )
            _check_metadata(participant.metadata_json, settings)
        for message in conversation.messages:
            if len(message.source_message_id) > MAX_SOURCE_ID_CHARACTERS:
                _raise_limit(
                    "source_id_characters",
                    MAX_SOURCE_ID_CHARACTERS,
                    len(message.source_message_id),
                )
            if len(message.raw_content) > settings.import_max_message_characters:
                _raise_limit(
                    "message_characters",
                    settings.import_max_message_characters,
                    len(message.raw_content),
                )
            _check_metadata(message.metadata_json, settings)


def _validate_cleaned_limits(cleaned: CleanedChatFile, settings: Settings) -> None:
    for conversation in cleaned.conversations:
        for message in conversation.cleaned_messages:
            if len(message.normalized_content) > settings.import_max_message_characters:
                _raise_limit(
                    "message_characters",
                    settings.import_max_message_characters,
                    len(message.normalized_content),
                )


def _safe_source_location(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) > 500 or "\\" in value or value.lower().startswith("file:"):
        raise ApiError(
            "import_failed",
            status_code=500,
            message="The import could not be saved safely.",
        )
    return value


def _source_metadata(cleaned: CleanedChatFile) -> dict[str, Any]:
    return {
        "cleaning_pipeline_version": cleaned.cleaning_pipeline_version,
        "parser_statistics": {
            "conversation_count": cleaned.statistics.conversation_count,
            "participant_count": sum(len(item.participants) for item in cleaned.conversations),
            "message_count": cleaned.statistics.input_message_count,
            "warning_count": len(cleaned.parser_warnings),
        },
        "cleaning_statistics": cleaned.statistics.model_dump(mode="json"),
        "parser_warning_count": len(cleaned.parser_warnings),
        "cleaning_warning_count": len(cleaned.cleaning_warnings),
        "import_limits_version": LIMITS_VERSION,
    }


def _persist_cleaned_chat(
    session: Session,
    *,
    cleaned: CleanedChatFile,
    file_type: FileType,
    byte_size: int,
) -> SourceFile:
    source = SourceFile(
        filename=cleaned.source_filename,
        file_type=file_type,
        file_hash=cleaned.file_hash,
        storage_path=None,
        byte_size=byte_size,
        imported_at=utc_now(),
        parser_name=cleaned.parser_name,
        parser_version=cleaned.parser_version,
        status=SourceFileStatus.READY,
        metadata_json=_source_metadata(cleaned),
    )
    session.add(source)
    session.flush()

    for cleaned_conversation in cleaned.conversations:
        _persist_conversation(session, source, cleaned_conversation, cleaned)
    session.flush()
    return source


def _persist_conversation(
    session: Session,
    source: SourceFile,
    cleaned_conversation: CleanedConversation,
    cleaned_file: CleanedChatFile,
) -> None:
    conversation = Conversation(
        source_file_id=source.id,
        source_conversation_id=cleaned_conversation.source_conversation_id,
        platform=cleaned_conversation.platform,
        title=cleaned_conversation.title,
        started_at=cleaned_conversation.started_at,
        ended_at=cleaned_conversation.ended_at,
        metadata_json=dict(cleaned_conversation.metadata_json),
    )
    session.add(conversation)
    session.flush()

    participant_by_source: dict[str, Participant] = {}
    for index, canonical in enumerate(cleaned_conversation.participants):
        source_id = canonical.source_participant_id or f"participant-{index}"
        participant = Participant(
            canonical_name=canonical.display_name,
            aliases=list(canonical.aliases),
            is_profile_owner=canonical.is_profile_owner is True,
            metadata_json={
                **canonical.metadata_json,
                "source_participant_id": canonical.source_participant_id,
            },
        )
        session.add(participant)
        session.flush()
        session.execute(
            conversation_participants.insert().values(
                conversation_id=conversation.id,
                participant_id=participant.id,
            )
        )
        participant_by_source[source_id] = participant

    message_by_source: dict[str, Message] = {}
    cleaned_by_source: dict[str, CleanedMessage] = {}
    for message in cleaned_conversation.cleaned_messages:
        sender = participant_by_source[message.sender_source_id]
        database_message = Message(
            conversation_id=conversation.id,
            source_message_id=message.source_message_id,
            sender_id=sender.id,
            timestamp=message.timestamp,
            sequence_index=message.source_order,
            source_order=message.source_order,
            source_location=_safe_source_location(message.source_location),
            message_type=MessageType(message.message_type.value),
            raw_content=message.raw_content,
            normalized_content=message.normalized_content,
            is_system_message=message.is_system_message,
            is_recalled_message=message.is_recalled_message,
            excluded_from_analysis=message.excluded_from_analysis,
            exclusion_reason=(
                message.exclusion_reasons[0].value if message.exclusion_reasons else None
            ),
            exclusion_reasons_json=[item.value for item in message.exclusion_reasons],
            normalization_version=cleaned_file.cleaning_pipeline_version,
            cleaning_operations_json=[
                item.model_dump(mode="json") for item in message.cleaning_operations
            ],
            metadata_json=dict(message.metadata_json),
        )
        session.add(database_message)
        session.flush()
        message_by_source[message.source_message_id] = database_message
        cleaned_by_source[message.source_message_id] = message

    for source_id, database_message in message_by_source.items():
        cleaned_message = cleaned_by_source[source_id]
        reply_id = cleaned_message.reply_to_source_message_id
        duplicate_id = cleaned_message.duplicate_of_source_message_id
        if reply_id is not None:
            database_message.reply_to_message_id = message_by_source[reply_id].id
        if duplicate_id is not None:
            duplicate_target = message_by_source[duplicate_id]
            if duplicate_target.source_order >= database_message.source_order:
                raise ApiError(
                    "import_failed",
                    status_code=500,
                    message="The import could not be saved safely.",
                )
            database_message.duplicate_of_message_id = duplicate_target.id


def _warning_summaries(cleaned: CleanedChatFile) -> list[SafeWarning]:
    warnings = [
        SafeWarning(
            error_code=item.error_code.value,
            message=item.message,
            location=item.location,
        )
        for item in cleaned.parser_warnings
    ]
    warnings.extend(
        SafeWarning(
            error_code=item.error_code.value,
            message=item.message,
            location=None,
        )
        for item in cleaned.cleaning_warnings
    )
    return warnings[:50]


def build_import_detail(
    source: SourceFile, *, warnings: list[SafeWarning] | None = None
) -> ImportDetail:
    metadata = source.metadata_json if isinstance(source.metadata_json, dict) else {}
    parser_stats = metadata.get("parser_statistics", {})
    cleaning_stats = metadata.get("cleaning_statistics", {})
    pipeline_version = str(metadata.get("cleaning_pipeline_version", "unknown"))
    return ImportDetail(
        source_file_id=source.id,
        filename=source.filename,
        file_hash=source.file_hash,
        file_type=source.file_type.value,
        byte_size=source.byte_size,
        parser_name=source.parser_name,
        parser_version=source.parser_version,
        cleaning_pipeline_version=pipeline_version,
        imported_at=source.imported_at,
        conversation_count=int(parser_stats.get("conversation_count", 0)),
        participant_count=int(parser_stats.get("participant_count", 0)),
        message_count=int(parser_stats.get("message_count", 0)),
        excluded_message_count=int(cleaning_stats.get("excluded_message_count", 0)),
        analysis_unit_count=int(cleaning_stats.get("analysis_unit_count", 0)),
        parser_warning_count=int(metadata.get("parser_warning_count", 0)),
        cleaning_warning_count=int(metadata.get("cleaning_warning_count", 0)),
        warnings=warnings or [],
        links=ImportLinks(
            self=f"/api/v1/imports/{source.id}",
            conversations=f"/api/v1/conversations?source_file_id={source.id}",
        ),
    )


def _duplicate_error(source: SourceFile) -> ApiError:
    return ApiError(
        "duplicate_file",
        status_code=409,
        message="This file has already been imported.",
        recoverable=True,
        safe_filename=source.filename,
        details={"source_file_id": source.id},
    )


def _parser_api_error(error: ParserError) -> ApiError:
    code = error.error_code.value
    if code == "unsupported_extension":
        status_code = 415
        public_code = code
    elif code in {"unsupported_format", "unknown_parser", "ambiguous_format"}:
        status_code = 422
        public_code = code
    else:
        status_code = 422
        public_code = "parser_error"
    return ApiError(
        public_code,
        status_code=status_code,
        message=error.message,
        recoverable=error.recoverable,
        safe_filename=error.safe_filename,
        location=error.location,
        details={"parser_error_code": code, **error.details},
    )


async def import_upload(
    session: Session,
    *,
    upload: UploadFile,
    parser_name: str | None,
    error_mode: ErrorMode,
    default_timezone: str | None,
    cleaning_options: CleaningOptions,
    settings: Settings,
    content_length: int | None,
) -> ImportDetail:
    safe_filename = safe_display_name(upload.filename or "upload")
    extension = Path(safe_filename).suffix.lower()
    file_type = SUPPORTED_EXTENSIONS.get(extension)
    if file_type is None:
        raise ApiError(
            "unsupported_extension",
            status_code=415,
            message="Only JSON, CSV, and TXT files are supported.",
            safe_filename=safe_filename,
            details={"extension": extension or "<none>"},
        )
    if (
        content_length is not None
        and content_length > settings.import_max_file_bytes + MULTIPART_OVERHEAD_ALLOWANCE
    ):
        raise ApiError(
            "upload_too_large",
            status_code=413,
            message="The uploaded file exceeds the configured size limit.",
            safe_filename=safe_filename,
            details={"allowed": settings.import_max_file_bytes},
        )

    temp_root = settings.import_temp_root
    with tempfile.TemporaryDirectory(prefix="echomind-import-", dir=temp_root) as directory:
        temporary_path = Path(directory) / f"{uuid4().hex}{extension}"
        digest = hashlib.sha256()
        byte_size = 0
        try:
            with temporary_path.open("wb") as destination:
                while chunk := await upload.read(settings.import_chunk_size_bytes):
                    byte_size += len(chunk)
                    if byte_size > settings.import_max_file_bytes:
                        raise ApiError(
                            "upload_too_large",
                            status_code=413,
                            message="The uploaded file exceeds the configured size limit.",
                            safe_filename=safe_filename,
                            details={"allowed": settings.import_max_file_bytes},
                        )
                    digest.update(chunk)
                    destination.write(chunk)
        finally:
            await upload.close()
        if byte_size == 0:
            raise ApiError(
                "unsupported_format",
                status_code=422,
                message="The uploaded file is empty.",
                safe_filename=safe_filename,
            )

        uploaded_hash = digest.hexdigest()
        existing = find_source_by_hash(session, uploaded_hash)
        session.rollback()
        if existing is not None:
            raise _duplicate_error(existing)

        registry = create_default_registry()
        try:
            parsed = registry.parse(
                temporary_path,
                parser_name=parser_name,
                options=ParserOptions(
                    error_mode=error_mode,
                    default_timezone=default_timezone,
                ),
            )
        except ParserError as error:
            raise _parser_api_error(error) from None
        if parsed.file_hash != uploaded_hash:
            raise ApiError(
                "import_failed",
                status_code=500,
                message="The uploaded bytes could not be verified.",
                safe_filename=safe_filename,
            )
        parsed = parsed.model_copy(update={"source_filename": safe_filename})
        _validate_canonical_limits(parsed, settings)
        try:
            cleaned = clean_chat(parsed, cleaning_options)
        except CleaningError as error:
            raise ApiError(
                "cleaning_error",
                status_code=422,
                message=error.message,
                recoverable=error.recoverable,
                safe_filename=error.safe_filename,
                details={"cleaning_error_code": error.error_code.value},
            ) from None
        _validate_cleaned_limits(cleaned, settings)

        try:
            with session.begin():
                source = _persist_cleaned_chat(
                    session,
                    cleaned=cleaned,
                    file_type=file_type,
                    byte_size=byte_size,
                )
        except ApiError:
            session.rollback()
            raise
        except IntegrityError:
            session.rollback()
            existing = find_source_by_hash(session, uploaded_hash)
            session.rollback()
            if existing is not None:
                raise _duplicate_error(existing) from None
            raise ApiError(
                "import_failed",
                status_code=500,
                message="The import could not be saved.",
                safe_filename=safe_filename,
            ) from None
        except Exception:
            session.rollback()
            raise ApiError(
                "import_failed",
                status_code=500,
                message="The import could not be saved.",
                safe_filename=safe_filename,
            ) from None
        return build_import_detail(source, warnings=_warning_summaries(cleaned))
