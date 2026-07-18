"""Run the documented 10-conversation/5,000-message synthetic MVP load audit."""

import asyncio
import io
import json
import tempfile
import tracemalloc
from pathlib import Path
from time import perf_counter
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import func, select

from echomind.cleaning import CleaningOptions, clean_chat
from echomind.core.config import Settings
from echomind.db.base import Base
from echomind.db.session import create_db_engine, create_session_factory
from echomind.models import Conversation, Message
from echomind.parsers import ErrorMode, ParserOptions, create_default_registry
from echomind.schemas.analysis import AnalysisRequest
from echomind.services.analysis_service import run_analysis
from echomind.services.import_service import import_upload


def synthetic_payload() -> bytes:
    conversations = []
    for conversation_index in range(10):
        owner_id = f"owner-{conversation_index}"
        other_id = f"other-{conversation_index}"
        conversations.append(
            {
                "id": f"conversation-{conversation_index}",
                "title": f"Synthetic load conversation {conversation_index}",
                "participants": [
                    {
                        "id": owner_id,
                        "name": f"Synthetic Owner {conversation_index}",
                        "is_profile_owner": True,
                    },
                    {"id": other_id, "name": f"Synthetic Other {conversation_index}"},
                ],
                "messages": [
                    {
                        "id": f"message-{message_index}",
                        "sender_id": owner_id if message_index % 2 == 0 else other_id,
                        "timestamp": (
                            f"2026-07-{1 + message_index % 18:02d}"
                            f"T08:{message_index % 60:02d}:00+08:00"
                        ),
                        "type": "text",
                        "content": f"Synthetic bounded load message {message_index}.",
                    }
                    for message_index in range(500)
                ],
            }
        )
    return json.dumps(
        {
            "format": "echomind-generic-chat",
            "version": "1.0",
            "platform": "synthetic-load-audit",
            "conversations": conversations,
        }
    ).encode()


async def audit() -> dict[str, int | float | str]:
    raw = synthetic_payload()
    with tempfile.TemporaryDirectory(prefix="echomind-stage11-load-") as directory:
        root = Path(directory)
        settings = Settings(
            environment="audit",
            database_url=f"sqlite:///{(root / 'load.db').as_posix()}",
            import_temp_root=str(root),
        )
        engine = create_db_engine(settings.database_url)
        Base.metadata.create_all(engine)
        factory = create_session_factory(engine)
        source_path = root / "synthetic-load.json"
        source_path.write_bytes(raw)
        tracemalloc.start()
        parser_started = perf_counter()
        parsed = create_default_registry().parse(
            source_path,
            options=ParserOptions(error_mode=ErrorMode.STRICT),
        )
        parser_seconds = perf_counter() - parser_started
        cleaning_started = perf_counter()
        cleaned = clean_chat(parsed, CleaningOptions())
        cleaning_seconds = perf_counter() - cleaning_started
        if cleaned.statistics.output_message_count != 5_000:
            engine.dispose()
            raise RuntimeError("synthetic cleaning audit changed the message count")
        started = perf_counter()
        with factory() as session:
            imported = await import_upload(
                session,
                upload=UploadFile(io.BytesIO(raw), filename="synthetic-load.json"),
                parser_name=None,
                error_mode=ErrorMode.STRICT,
                default_timezone=None,
                cleaning_options=CleaningOptions(),
                settings=settings,
                content_length=len(raw),
            )
        import_seconds = perf_counter() - started
        with factory() as session:
            conversation_ids = list(
                session.scalars(select(Conversation.id).order_by(Conversation.id))
            )
        analysis_started = perf_counter()
        analysis = run_analysis(
            factory,
            AnalysisRequest(
                conversation_ids=[UUID(value) for value in conversation_ids],
                remote_consent=False,
            ),
            settings=settings,
        )
        analysis_seconds = perf_counter() - analysis_started
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        with factory() as session:
            stored_messages = session.scalar(select(func.count()).select_from(Message)) or 0
        database_bytes = (root / "load.db").stat().st_size
        engine.dispose()
        return {
            "result": "pass",
            "input_bytes": len(raw),
            "conversation_count": imported.conversation_count,
            "message_count": imported.message_count,
            "stored_message_count": stored_messages,
            "parser_seconds": round(parser_seconds, 3),
            "cleaning_seconds": round(cleaning_seconds, 3),
            "import_seconds": round(import_seconds, 3),
            "analysis_seconds": round(analysis_seconds, 3),
            "analysis_window_count": analysis.window_count,
            "analysis_failed_window_count": analysis.failed_window_count,
            "peak_traced_mebibytes": round(peak_bytes / 1024 / 1024, 2),
            "database_bytes": database_bytes,
        }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(audit()), sort_keys=True))
