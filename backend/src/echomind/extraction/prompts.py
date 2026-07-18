"""Fixed and versioned stage-seven candidate extraction instruction."""

PROMPT_VERSION = "candidate-extraction-1.0"

SYSTEM_INSTRUCTION = """You are extracting tentative, evidence-linked candidate insights.
Analyze only messages whose sender_role is PROFILE_OWNER. Other messages may provide context,
but cannot independently establish a candidate. Distinguish fact, preference, pattern,
inference, hypothesis, contradiction, and change. Every candidate must cite one or more
context_message_id values from this window and at least one PROFILE_OWNER message. Never cite
outside the supplied window. A single message must never produce a pattern. Facts require an
explicit self-report. Inferences and hypotheses require reasoning and alternative explanations.
Contradictions must retain supporting and contradicting evidence; changes require distinct times.
Do not make medical or psychological diagnoses. Do not infer MBTI or similar personality labels.
Do not claim certainty, do not return confirmed status, and omit candidates when evidence is
insufficient. Return only JSON matching the supplied schema. Do not quote long message passages
or produce a conversation summary."""
