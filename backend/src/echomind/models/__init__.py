"""Core stage-two ORM models.

Importing this module registers every table on :class:`echomind.db.base.Base`.
"""

from echomind.models.conversation import Conversation, conversation_participants
from echomind.models.evidence import Evidence
from echomind.models.insight import Insight, InsightEvidence
from echomind.models.insight_revision import InsightRevision
from echomind.models.message import Message
from echomind.models.participant import Participant
from echomind.models.profile_snapshot import ProfileSnapshot
from echomind.models.source_file import SourceFile

__all__ = [
    "Conversation",
    "Evidence",
    "Insight",
    "InsightEvidence",
    "InsightRevision",
    "Message",
    "Participant",
    "ProfileSnapshot",
    "SourceFile",
    "conversation_participants",
]
