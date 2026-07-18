"""Deterministic one-conversation context windows and local aliases."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime

from echomind.extraction.context import ContextMessage
from echomind.extraction.options import WINDOW_PARAMETERS_VERSION, ExtractionRequest

TRUNCATION_MARKER = "[TRUNCATED]"


@dataclass(frozen=True)
class ContextWindowMessage:
    database_message_id: str
    sender_id: str
    is_profile_owner: bool
    timestamp: datetime
    message_type: str
    normalized_content: str
    evidence_content: str
    content_truncated: bool
    reply_to_message_id: str | None
    source_order: int
    context_message_id: str
    sender_role: str
    reply_to_context_message_id: str | None

    def provider_dict(self) -> dict[str, object]:
        value: dict[str, object] = {
            "context_message_id": self.context_message_id,
            "conversation_context_id": "c001",
            "sender_role": self.sender_role,
            "timestamp": self.timestamp.isoformat(),
            "message_type": self.message_type,
            "normalized_content": self.normalized_content,
            "content_truncated": self.content_truncated,
        }
        if self.reply_to_context_message_id is not None:
            value["reply_to_context_message_id"] = self.reply_to_context_message_id
        return value


@dataclass(frozen=True)
class ContextWindow:
    window_id: str
    conversation_id: str
    messages: list[ContextWindowMessage]

    @classmethod
    def from_messages(
        cls,
        *,
        conversation_id: str,
        messages: list[ContextMessage],
        extraction_version: str,
    ) -> ContextWindow:
        aliases = {
            item.database_message_id: f"m{index:03d}"
            for index, item in enumerate(messages, start=1)
        }
        other_aliases: dict[str, str] = {}
        converted: list[ContextWindowMessage] = []
        for item in messages:
            if item.is_profile_owner:
                sender_role = "PROFILE_OWNER"
            else:
                sender_role = other_aliases.setdefault(
                    item.sender_id, f"OTHER_{len(other_aliases) + 1}"
                )
            converted.append(
                ContextWindowMessage(
                    database_message_id=item.database_message_id,
                    sender_id=item.sender_id,
                    is_profile_owner=item.is_profile_owner,
                    timestamp=item.timestamp,
                    message_type=item.message_type,
                    normalized_content=item.normalized_content,
                    evidence_content=item.normalized_content,
                    content_truncated=False,
                    reply_to_message_id=item.reply_to_message_id,
                    source_order=item.source_order,
                    context_message_id=aliases[item.database_message_id],
                    sender_role=sender_role,
                    reply_to_context_message_id=aliases.get(item.reply_to_message_id or ""),
                )
            )
        return cls(
            window_id=_window_id(extraction_version, conversation_id, messages),
            conversation_id=conversation_id,
            messages=converted,
        )

    def provider_json(self) -> str:
        return json.dumps(
            {"messages": [item.provider_dict() for item in self.messages]},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @property
    def truncated_message_count(self) -> int:
        return sum(item.content_truncated for item in self.messages)

    def message_by_alias(self) -> dict[str, ContextWindowMessage]:
        return {item.context_message_id: item for item in self.messages}


def _window_id(
    extraction_version: str,
    conversation_id: str,
    messages: list[ContextMessage],
) -> str:
    payload = {
        "conversation_id": conversation_id,
        "extraction_version": extraction_version,
        "message_ids": [item.database_message_id for item in messages],
        "window_parameters_version": WINDOW_PARAMETERS_VERSION,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _truncate(message: ContextMessage, limit: int) -> ContextMessage:
    content = message.normalized_content
    if len(content) <= limit:
        return message
    prefix_length = limit - len(TRUNCATION_MARKER)
    return replace(
        message,
        normalized_content=f"{content[:prefix_length]}{TRUNCATION_MARKER}",
    )


def build_windows(
    messages: list[ContextMessage], request: ExtractionRequest
) -> list[ContextWindow]:
    """Build stable windows; overlap may shrink when its characters block progress."""
    if len({item.conversation_id for item in messages}) > 1:
        raise ValueError("a context window input must contain exactly one conversation")
    prepared = [_truncate(item, request.max_single_message_characters) for item in messages]
    result: list[ContextWindow] = []
    start = 0
    previous_end = 0
    while start < len(prepared):
        end = start
        characters = 0
        while end < len(prepared) and end - start < request.max_window_messages:
            candidate_size = len(prepared[end].normalized_content)
            if end > start and characters + candidate_size > request.max_window_characters:
                break
            characters += candidate_size
            end += 1
        if end == start:
            end += 1
        if end <= previous_end:
            start += 1
            continue
        source_items = prepared[start:end]
        window = ContextWindow.from_messages(
            conversation_id=source_items[0].conversation_id,
            messages=source_items,
            extraction_version=request.extraction_version,
        )
        # Preserve the full normalized value for local Evidence while sending only the truncation.
        originals = {item.database_message_id: item.normalized_content for item in messages}
        fixed_messages = [
            replace(
                item,
                evidence_content=originals[item.database_message_id],
                content_truncated=(item.normalized_content != originals[item.database_message_id]),
            )
            for item in window.messages
        ]
        result.append(replace(window, messages=fixed_messages))
        previous_end = end
        if end == len(prepared):
            break
        start = max(end - request.overlap_messages, start + 1)
    return result
