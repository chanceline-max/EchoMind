"""Composable, database-independent cleaning pipeline."""

from echomind.cleaning.errors import CleaningError, CleaningErrorCode
from echomind.cleaning.options import (
    CleaningOptions,
    CustomRedactionPattern,
    RedactionCategory,
)
from echomind.cleaning.pipeline import (
    CLEANER_ORDER,
    CLEANING_PIPELINE_VERSION,
    CleaningPipeline,
    clean_chat,
    validate_cleaned_chat,
)
from echomind.cleaning.schemas import (
    AnalysisUnit,
    CleanedChatFile,
    CleanedConversation,
    CleanedMessage,
    CleaningOperation,
    CleaningStatistics,
    CleaningWarning,
    ExclusionReason,
)

__all__ = [
    "AnalysisUnit",
    "CLEANER_ORDER",
    "CLEANING_PIPELINE_VERSION",
    "CleanedChatFile",
    "CleanedConversation",
    "CleanedMessage",
    "CleaningError",
    "CleaningErrorCode",
    "CleaningOperation",
    "CleaningOptions",
    "CleaningPipeline",
    "CleaningStatistics",
    "CleaningWarning",
    "CustomRedactionPattern",
    "ExclusionReason",
    "RedactionCategory",
    "clean_chat",
    "validate_cleaned_chat",
]
