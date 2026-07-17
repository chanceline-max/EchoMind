"""Synthetic parser input builders."""

import csv
import io
import json
from pathlib import Path
from typing import Any

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


def synthetic_message(
    message_id: str = "message-1",
    sender_id: str = "person-a",
    timestamp: str = "2026-07-16T10:20:00+08:00",
    content: str = "Synthetic message one",
    **overrides: Any,
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "id": message_id,
        "sender_id": sender_id,
        "timestamp": timestamp,
        "type": "text",
        "content": content,
        "reply_to_message_id": None,
        "metadata_json": {},
    }
    message.update(overrides)
    return message


def synthetic_conversation(
    conversation_id: str = "conversation-1",
    messages: list[dict[str, Any]] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    conversation: dict[str, Any] = {
        "id": conversation_id,
        "title": "Synthetic conversation",
        "participants": [
            {
                "id": "person-a",
                "name": "Person A",
                "aliases": [],
                "is_profile_owner": True,
                "metadata_json": {},
            },
            {
                "id": "person-b",
                "name": "Person B",
                "aliases": [],
                "is_profile_owner": False,
                "metadata_json": {},
            },
        ],
        "messages": messages if messages is not None else [synthetic_message()],
        "metadata_json": {},
    }
    conversation.update(overrides)
    return conversation


def synthetic_json_payload(
    conversations: list[dict[str, Any]] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "format": "echomind-generic-chat",
        "version": "1.0",
        "platform": "generic",
        "conversations": conversations or [synthetic_conversation()],
    }
    payload.update(overrides)
    return payload


def write_json(path: Path, payload: dict[str, Any], *, bom: bool = False) -> Path:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)
    return path


def csv_row(**overrides: str) -> dict[str, str]:
    row = {
        "conversation_id": "conversation-1",
        "conversation_title": "Synthetic conversation",
        "platform": "generic",
        "message_id": "message-1",
        "sender_id": "person-a",
        "sender_name": "Person A",
        "is_profile_owner": "true",
        "timestamp": "2026-07-16T10:20:00+08:00",
        "message_type": "text",
        "content": "Synthetic message one",
        "reply_to_message_id": "",
    }
    row.update(overrides)
    return row


def write_csv(
    path: Path,
    rows: list[dict[str, str]],
    *,
    headers: list[str] | None = None,
    bom: bool = False,
) -> Path:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers or CSV_HEADERS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    data = output.getvalue().encode("utf-8")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)
    return path


def valid_text(*message_lines: str, timezone: str | None = "Asia/Shanghai") -> str:
    headers = [
        "# conversation: conversation-1",
        "# title: Synthetic conversation",
        "# platform: generic",
    ]
    if timezone is not None:
        headers.append(f"# timezone: {timezone}")
    headers.extend(
        [
            "# participant: person-a|Person A|owner",
            "# participant: person-b|Person B|other",
        ]
    )
    lines = list(message_lines) or [
        "[message-1][2026-07-16 10:20:00] <person-a> Synthetic message one"
    ]
    return "\n".join([*headers, *lines, ""])
