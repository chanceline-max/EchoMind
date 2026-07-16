"""Portable database value types and application-side identifiers."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

UUID_LENGTH = 36


def new_uuid() -> str:
    """Generate a database-portable UUID4 string."""
    return str(uuid4())


def utc_now() -> datetime:
    """Return an aware UTC timestamp for defaults."""
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Reject naive values, normalize to UTC, and restore UTC tzinfo on read."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("naive datetime values are not allowed")

        normalized = value.astimezone(UTC)
        if dialect.name == "sqlite":
            return normalized.replace(tzinfo=None)
        return normalized

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        del dialect
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
