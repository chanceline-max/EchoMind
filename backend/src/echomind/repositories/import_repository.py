"""Source-file queries used by the synchronous import workflow."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from echomind.models import SourceFile


def find_source_by_hash(session: Session, file_hash: str) -> SourceFile | None:
    return session.scalar(select(SourceFile).where(SourceFile.file_hash == file_hash))


def get_source(session: Session, source_file_id: str) -> SourceFile | None:
    return session.get(SourceFile, source_file_id)


def list_sources(
    session: Session,
    *,
    limit: int,
    offset: int,
) -> tuple[list[SourceFile], int]:
    total = session.scalar(select(func.count()).select_from(SourceFile)) or 0
    items = list(
        session.scalars(
            select(SourceFile)
            .order_by(SourceFile.imported_at.desc(), SourceFile.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total
