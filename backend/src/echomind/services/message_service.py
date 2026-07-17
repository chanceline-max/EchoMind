"""User-controlled, non-destructive message analysis exclusion."""

from sqlalchemy.orm import Session

from echomind.api.errors import ApiError
from echomind.models import Message
from echomind.repositories.conversation_repository import get_message_with_sender
from echomind.schemas.messages import MessageSummary
from echomind.services.conversation_service import message_summary

USER_EXCLUDED = "user_excluded"


def set_analysis_exclusion(
    session: Session,
    *,
    message_id: str,
    excluded: bool,
) -> MessageSummary:
    message = session.get(Message, message_id)
    if message is None:
        raise ApiError(
            "resource_not_found",
            status_code=404,
            message="The requested message does not exist.",
        )
    reasons = list(dict.fromkeys(message.exclusion_reasons_json))
    if excluded and USER_EXCLUDED not in reasons:
        reasons.append(USER_EXCLUDED)
    if not excluded:
        reasons = [item for item in reasons if item != USER_EXCLUDED]
    message.exclusion_reasons_json = reasons
    message.exclusion_reason = reasons[0] if reasons else None
    message.excluded_from_analysis = bool(reasons)
    session.commit()

    row = get_message_with_sender(session, message.id)
    if row is None:
        raise ApiError(
            "resource_not_found",
            status_code=404,
            message="The requested message does not exist.",
        )
    return message_summary(*row)
