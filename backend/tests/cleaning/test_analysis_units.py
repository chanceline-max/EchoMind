"""Deterministic analysis unit construction tests."""

from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.pipeline import clean_chat
from echomind.cleaning.schemas import AnalysisUnit
from echomind.parsers.schemas import CanonicalMessage, MessageType

from .factories import conversation, message, parsed_chat


def units(
    messages: list[CanonicalMessage],
    options: CleaningOptions | None = None,
    *,
    conversation_id: str = "conversation-1",
) -> list[AnalysisUnit]:
    source = parsed_chat([conversation(messages, identifier=conversation_id)])
    return clean_chat(source, options).conversations[0].analysis_units


def test_single_eligible_message_forms_single_unit() -> None:
    result = units([message("one", content="Alpha")])

    assert len(result) == 1
    assert result[0].message_source_ids == ["one"]
    assert result[0].combined_content == "Alpha"
    assert result[0].message_count == 1


def test_adjacent_short_messages_from_same_sender_are_combined_in_order() -> None:
    result = units(
        [
            message("one", content="Alpha", source_order=0, seconds=0),
            message("two", content="Beta", source_order=1, seconds=30),
        ]
    )

    assert len(result) == 1
    assert result[0].message_source_ids == ["one", "two"]
    assert result[0].combined_content == "Alpha\nBeta"
    assert result[0].source_order_start == 0
    assert result[0].source_order_end == 1


def test_sender_change_breaks_unit() -> None:
    result = units(
        [
            message("one", sender="person-a", source_order=0),
            message("two", sender="person-b", source_order=1),
        ]
    )

    assert len(result) == 2


def test_time_gap_over_limit_breaks_unit() -> None:
    result = units([message("one", source_order=0), message("two", source_order=1, seconds=121)])

    assert len(result) == 2


def test_non_text_message_breaks_and_does_not_form_unit() -> None:
    result = units(
        [
            message("one", content="One", source_order=0),
            message("image", content="", message_type=MessageType.IMAGE, source_order=1),
            message("two", content="Two", source_order=2),
        ]
    )

    assert [item.message_source_ids for item in result] == [["one"], ["two"]]


def test_excluded_message_breaks_and_does_not_form_unit() -> None:
    options = CleaningOptions(excluded_source_message_ids={"excluded"})
    result = units(
        [
            message("one", content="One", source_order=0),
            message("excluded", content="Excluded", source_order=1),
            message("two", content="Two", source_order=2),
        ],
        options,
    )

    assert [item.message_source_ids for item in result] == [["one"], ["two"]]


def test_source_order_gap_breaks_unit() -> None:
    result = units(
        [
            message("one", content="One", source_order=1),
            message("two", content="Two", source_order=3),
        ]
    )

    assert len(result) == 2


def test_message_count_limit_starts_new_unit() -> None:
    options = CleaningOptions(analysis_unit_max_messages=2)
    result = units(
        [
            message("one", content="One", source_order=0),
            message("two", content="Two", source_order=1),
            message("three", content="Three", source_order=2),
        ],
        options,
    )

    assert [item.message_count for item in result] == [2, 1]


def test_character_limit_includes_join_delimiter() -> None:
    options = CleaningOptions(analysis_unit_max_characters=10)
    result = units(
        [
            message("one", content="12345", source_order=0),
            message("two", content="67890", source_order=1),
        ],
        options,
    )

    assert len(result) == 2


def test_message_larger_than_character_limit_still_forms_single_unit() -> None:
    options = CleaningOptions(analysis_unit_max_characters=4)
    result = units([message("one", content="12345")], options)

    assert len(result) == 1
    assert result[0].combined_content == "12345"


def test_reply_message_always_starts_new_context_unit() -> None:
    result = units(
        [
            message("root", content="Root", source_order=0),
            message("reply", content="Reply", source_order=1, reply="root"),
            message("follow-up", content="Follow up", source_order=2),
        ]
    )

    assert [item.message_source_ids for item in result] == [
        ["root"],
        ["reply", "follow-up"],
    ]


def test_analysis_unit_id_is_sha256_derived_and_stable() -> None:
    first = units([message("one")])[0]
    second = units([message("one")])[0]

    assert first.analysis_unit_id == second.analysis_unit_id
    assert first.analysis_unit_id.startswith("analysis-unit-")
    assert len(first.analysis_unit_id) == len("analysis-unit-") + 32


def test_analysis_units_can_be_disabled_and_do_not_modify_messages() -> None:
    source = parsed_chat()
    original = source.model_dump_json()

    result = clean_chat(source, CleaningOptions(build_analysis_units=False))

    assert result.conversations[0].analysis_units == []
    assert source.model_dump_json() == original


def test_analysis_units_never_cross_conversations() -> None:
    source = parsed_chat(
        [
            conversation([message("one")], identifier="conversation-a"),
            conversation([message("two")], identifier="conversation-b"),
        ]
    )

    result = clean_chat(source)

    assert [item.analysis_units[0].conversation_source_id for item in result.conversations] == [
        "conversation-a",
        "conversation-b",
    ]
