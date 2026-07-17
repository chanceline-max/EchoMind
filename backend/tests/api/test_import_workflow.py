"""Stage-five import, query, and non-destructive exclusion API tests."""

import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select

from echomind.core.config import Settings
from echomind.db.session import create_db_engine, create_session_factory
from echomind.models import Conversation, Message, Participant, SourceFile
from echomind.services import import_service

pytestmark = pytest.mark.anyio


def payload(*, messages: list[dict[str, Any]] | None = None) -> bytes:
    records = messages or [
        {
            "id": "message-1",
            "sender_id": "person-a",
            "timestamp": "2026-07-16T10:20:00+08:00",
            "type": "text",
            "content": "Synthetic first message",
        },
        {
            "id": "message-2",
            "sender_id": "person-b",
            "timestamp": "2026-07-16T10:21:00+08:00",
            "type": "text",
            "content": "Synthetic reply",
            "reply_to_message_id": "message-1",
        },
    ]
    value = {
        "format": "echomind-generic-chat",
        "version": "1.0",
        "platform": "generic",
        "conversations": [
            {
                "id": "conversation-1",
                "title": "Synthetic conversation",
                "participants": [
                    {"id": "person-a", "name": "Person A", "is_profile_owner": True},
                    {"id": "person-b", "name": "Person B"},
                ],
                "messages": records,
            }
        ],
    }
    return json.dumps(value).encode()


async def import_json(
    client: AsyncClient,
    *,
    content: bytes | None = None,
    filename: str = "synthetic.json",
    data: dict[str, str] | None = None,
    origin: str | None = "http://localhost:5173",
) -> Response:
    headers = {} if origin is None else {"Origin": origin}
    return await client.post(
        "/api/v1/imports",
        files={"file": (filename, content if content is not None else payload())},
        data=data,
        headers=headers,
    )


async def test_import_persists_provenance_and_complete_message_fields(
    client: AsyncClient,
) -> None:
    response = await import_json(client)
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert result["filename"] == "synthetic.json"
    assert len(result["file_hash"]) == 64
    assert result["conversation_count"] == 1
    assert result["participant_count"] == 2
    assert result["message_count"] == 2
    assert result["parser_name"] == "generic-json"
    assert result["cleaning_pipeline_version"]

    conversations = await client.get(result["links"]["conversations"])
    conversation = conversations.json()["items"][0]
    messages = await client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    first, second = messages.json()["items"]
    assert first["raw_content"] == "Synthetic first message"
    assert first["normalized_content"] == "Synthetic first message"
    assert first["source_order"] == 0
    assert second["source_order"] == 1
    assert second["reply_to_message_id"] == first["id"]
    assert second["sender_display_name"] == "Person B"


@pytest.mark.parametrize(
    ("filename", "content", "parser_name"),
    [
        (
            "synthetic.csv",
            b"conversation_id,conversation_title,platform,message_id,sender_id,"
            b"sender_name,is_profile_owner,timestamp,message_type,content,"
            b"reply_to_message_id\r\nconversation-1,Synthetic,generic,message-1,"
            b"person-a,Person A,true,2026-07-16T10:20:00+08:00,text,"
            b"Synthetic CSV,\r\n",
            "generic-csv",
        ),
        (
            "synthetic.txt",
            b"# conversation: conversation-1\n# title: Synthetic\n"
            b"# platform: generic\n# timezone: Asia/Shanghai\n"
            b"# participant: person-a|Person A|owner\n"
            b"[message-1][2026-07-16 10:20:00] <person-a> Synthetic text\n",
            "generic-text",
        ),
    ],
)
async def test_all_supported_upload_formats_import(
    client: AsyncClient,
    filename: str,
    content: bytes,
    parser_name: str,
) -> None:
    response = await import_json(client, filename=filename, content=content)
    assert response.status_code == 201
    assert response.json()["parser_name"] == parser_name


async def test_duplicate_hash_is_rejected_without_duplicate_rows(
    client: AsyncClient,
) -> None:
    assert (await import_json(client)).status_code == 201
    duplicate = await import_json(client, filename="renamed.json")
    assert duplicate.status_code == 409
    assert duplicate.json()["error_code"] == "duplicate_file"
    imports = await client.get("/api/v1/imports")
    assert imports.json()["total"] == 1


async def test_import_list_detail_filter_and_pagination(client: AsyncClient) -> None:
    imported = (await import_json(client)).json()
    page = await client.get("/api/v1/imports?limit=1&offset=0")
    assert page.status_code == 200
    assert page.json()["total"] == 1
    detail = await client.get(f"/api/v1/imports/{imported['source_file_id']}")
    assert detail.json()["file_hash"] == imported["file_hash"]
    conversations = await client.get(
        "/api/v1/conversations",
        params={"source_file_id": imported["source_file_id"], "limit": 1},
    )
    assert conversations.json()["total"] == 1
    conversation_id = conversations.json()["items"][0]["id"]
    detail = await client.get(f"/api/v1/conversations/{conversation_id}")
    assert len(detail.json()["participants"]) == 2


async def test_message_pagination_and_analysis_exclusion_are_stable(
    client: AsyncClient,
) -> None:
    await import_json(client)
    conversation = (await client.get("/api/v1/conversations")).json()["items"][0]
    path = f"/api/v1/conversations/{conversation['id']}/messages"
    first_page = await client.get(path, params={"limit": 1, "offset": 0})
    second_page = await client.get(path, params={"limit": 1, "offset": 1})
    assert first_page.json()["items"][0]["source_order"] == 0
    assert second_page.json()["items"][0]["source_order"] == 1

    message_id = first_page.json()["items"][0]["id"]
    excluded = await client.patch(
        f"/api/v1/messages/{message_id}/analysis-exclusion",
        json={"excluded": True},
        headers={"Origin": "http://localhost:5173"},
    )
    assert excluded.status_code == 200
    assert excluded.json()["exclusion_reasons"] == ["user_excluded"]
    visible = await client.get(path, params={"include_excluded": "false"})
    assert visible.json()["total"] == 1

    restored = await client.patch(
        f"/api/v1/messages/{message_id}/analysis-exclusion",
        json={"excluded": False},
        headers={"Origin": "http://localhost:5173"},
    )
    assert restored.json()["excluded_from_analysis"] is False
    assert restored.json()["exclusion_reasons"] == []


@pytest.mark.parametrize("method,path", [("post", "/api/v1/imports"), ("patch", "/x")])
async def test_untrusted_origin_cannot_write(
    client: AsyncClient,
    method: str,
    path: str,
) -> None:
    if method == "post":
        response = await import_json(client, origin="https://untrusted.example")
    else:
        response = await client.patch(
            "/api/v1/messages/nonexistent/analysis-exclusion",
            json={"excluded": True},
            headers={"Origin": "https://untrusted.example"},
        )
    assert response.status_code == 403
    assert response.json()["error_code"] == "origin_not_allowed"


@pytest.mark.parametrize(
    ("filename", "content", "status", "code"),
    [
        ("synthetic.exe", b"not executable", 415, "unsupported_extension"),
        ("synthetic.json", b"", 422, "unsupported_format"),
        ("synthetic.json", b"not json", 422, "unsupported_format"),
    ],
)
async def test_invalid_uploads_are_safe_and_do_not_persist(
    client: AsyncClient,
    filename: str,
    content: bytes,
    status: int,
    code: str,
) -> None:
    response = await import_json(client, filename=filename, content=content)
    assert response.status_code == status
    assert response.json()["error_code"] == code
    assert "E:\\" not in response.text
    assert (await client.get("/api/v1/imports")).json()["total"] == 0


async def test_invalid_options_and_unknown_parser_are_rejected(client: AsyncClient) -> None:
    invalid_options = await import_json(
        client,
        data={"cleaning_options_json": '{"normalize_whitespace": false}'},
    )
    assert invalid_options.status_code == 422
    assert invalid_options.json()["error_code"] == "invalid_import_options"
    unknown_parser = await import_json(client, data={"parser_name": "missing"})
    assert unknown_parser.status_code == 422
    assert unknown_parser.json()["error_code"] == "unknown_parser"


async def test_lenient_mode_skips_recoverable_record_and_preserves_order(
    client: AsyncClient,
) -> None:
    messages = [
        {
            "id": "bad",
            "sender_id": "person-a",
            "timestamp": "not-a-time",
            "type": "text",
            "content": "Synthetic invalid record",
        },
        {
            "id": "good",
            "sender_id": "person-a",
            "timestamp": "2026-07-16T10:20:00+08:00",
            "type": "text",
            "content": "Synthetic valid record",
        },
    ]
    response = await import_json(
        client,
        content=payload(messages=messages),
        data={"error_mode": "lenient"},
    )
    assert response.status_code == 201
    conversation = (await client.get("/api/v1/conversations")).json()["items"][0]
    stored = await client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert stored.json()["items"][0]["source_order"] == 1


async def test_redaction_changes_only_normalized_content(client: AsyncClient) -> None:
    messages = [
        {
            "id": "message-1",
            "sender_id": "person-a",
            "timestamp": "2026-07-16T10:20:00+08:00",
            "type": "text",
            "content": "Synthetic address user@example.test",
        }
    ]
    response = await import_json(
        client,
        content=payload(messages=messages),
        data={"cleaning_options_json": '{"redact_sensitive_data": true}'},
    )
    assert response.status_code == 201
    conversation = (await client.get("/api/v1/conversations")).json()["items"][0]
    message = (await client.get(f"/api/v1/conversations/{conversation['id']}/messages")).json()[
        "items"
    ][0]
    assert message["raw_content"] == "Synthetic address user@example.test"
    assert message["normalized_content"] == "Synthetic address [EMAIL]"
    assert "cleaning_operations_json" not in message


async def test_duplicate_mapping_preserves_both_messages_and_reason(
    client: AsyncClient,
) -> None:
    messages = [
        {
            "id": f"message-{index}",
            "sender_id": "person-a",
            "timestamp": "2026-07-16T10:20:00+08:00",
            "type": "text",
            "content": "Synthetic duplicate",
        }
        for index in (1, 2)
    ]
    assert (await import_json(client, content=payload(messages=messages))).status_code == 201
    conversation = (await client.get("/api/v1/conversations")).json()["items"][0]
    stored = (await client.get(f"/api/v1/conversations/{conversation['id']}/messages")).json()[
        "items"
    ]
    assert len(stored) == 2
    assert stored[1]["duplicate_of_message_id"] == stored[0]["id"]
    assert stored[1]["exclusion_reasons"] == ["exact_duplicate"]


async def test_upload_limit_cleans_temporary_directory(
    client: AsyncClient,
    settings: Settings,
) -> None:
    settings.import_max_file_bytes = 32
    response = await import_json(client)
    assert response.status_code == 413
    assert response.json()["error_code"] == "upload_too_large"
    assert list(Path(settings.import_temp_root or "").iterdir()) == []


async def test_original_upload_is_not_retained_after_success(
    client: AsyncClient,
    settings: Settings,
) -> None:
    assert (await import_json(client)).status_code == 201
    engine = create_db_engine(settings.database_url)
    with create_session_factory(engine)() as session:
        source = session.scalar(select(SourceFile))
        assert source is not None
        assert source.storage_path is None
    engine.dispose()
    assert list(Path(settings.import_temp_root or "").iterdir()) == []


async def test_unexpected_persistence_failure_rolls_back_every_table(
    client: AsyncClient,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_after_source(*args: Any, **kwargs: Any) -> SourceFile:
        session = args[0]
        session.add(
            SourceFile(
                filename="synthetic.json",
                file_type="json",
                file_hash="a" * 64,
                byte_size=1,
                parser_name="synthetic",
                parser_version="1",
                status="ready",
            )
        )
        session.flush()
        raise RuntimeError("synthetic transaction failure")

    monkeypatch.setattr(import_service, "_persist_cleaned_chat", fail_after_source)
    response = await import_json(client)
    assert response.status_code == 500
    assert response.json()["error_code"] == "import_failed"
    engine = create_db_engine(settings.database_url)
    with create_session_factory(engine)() as session:
        for model in (SourceFile, Conversation, Participant, Message):
            assert session.scalar(select(func.count()).select_from(model)) == 0
    engine.dispose()


async def test_extension_content_mismatch_is_rejected(client: AsyncClient) -> None:
    response = await import_json(
        client,
        filename="spoofed.json",
        content=b"conversation_id,message_id\nconversation-1,message-1\n",
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "unsupported_format"


async def test_content_length_limit_runs_before_multipart_validation(
    client: AsyncClient,
    settings: Settings,
) -> None:
    response = await client.post(
        "/api/v1/imports",
        content=b"not multipart",
        headers={
            "Content-Length": str(settings.import_max_file_bytes + 1_048_577),
            "Content-Type": "application/octet-stream",
            "Origin": "http://localhost:5173",
        },
    )
    assert response.status_code == 413
    assert response.json()["error_code"] == "upload_too_large"
    assert response.headers["cache-control"] == "no-store"


async def test_validation_errors_use_safe_contract_and_no_store(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/imports",
        content=b"not multipart",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_request"
    assert response.headers["cache-control"] == "no-store"
    assert "not multipart" not in response.text


async def test_destructive_routes_do_not_exist(client: AsyncClient) -> None:
    imported = (await import_json(client)).json()
    conversation = (await client.get("/api/v1/conversations")).json()["items"][0]
    for path in (
        f"/api/v1/imports/{imported['source_file_id']}",
        f"/api/v1/conversations/{conversation['id']}",
    ):
        assert (await client.delete(path)).status_code == 405


async def test_read_endpoints_return_not_found_without_server_paths(
    client: AsyncClient,
) -> None:
    for path in ("/api/v1/imports/missing", "/api/v1/conversations/missing"):
        response = await client.get(path)
        assert response.status_code == 404
        assert response.json()["error_code"] == "resource_not_found"
        assert "E:\\" not in response.text
