"""Source file provenance model."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, Enum, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomind.db.base import Base
from echomind.db.types import UUID_LENGTH, UTCDateTime, new_uuid, utc_now
from echomind.models.enums import FileType, SourceFileStatus, enum_values

if TYPE_CHECKING:
    from echomind.models.conversation import Conversation


class SourceFile(Base):
    """Metadata and immutable provenance for a future imported source file."""

    __tablename__ = "source_files"
    __table_args__ = (
        CheckConstraint("length(trim(filename)) > 0", name="filename_not_empty"),
        CheckConstraint("length(file_hash) = 64", name="file_hash_sha256_length"),
        CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
        CheckConstraint("length(trim(parser_name)) > 0", name="parser_name_not_empty"),
        CheckConstraint("length(trim(parser_version)) > 0", name="parser_version_not_empty"),
        UniqueConstraint("file_hash", name="uq_source_files_file_hash"),
    )

    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=new_uuid)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[FileType] = mapped_column(
        Enum(
            FileType,
            name="file_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(500))
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    parser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[SourceFileStatus] = mapped_column(
        Enum(
            SourceFileStatus,
            name="source_file_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        default=SourceFileStatus.PENDING,
    )
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="source_file",
        passive_deletes="all",
    )
