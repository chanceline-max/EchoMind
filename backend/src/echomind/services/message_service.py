"""User-controlled, non-destructive message analysis exclusion."""

from sqlalchemy.orm import Session

from echomind.schemas.messages import MessageSummary
from echomind.services.evidence_validity_service import set_message_analysis_exclusion


def set_analysis_exclusion(
    session: Session,
    *,
    message_id: str,
    excluded: bool,
) -> MessageSummary:
    return set_message_analysis_exclusion(
        session,
        message_id=message_id,
        excluded=excluded,
    )
