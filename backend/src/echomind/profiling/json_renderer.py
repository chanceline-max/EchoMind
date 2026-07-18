"""Stable UTF-8 JSON rendering for EchoProfileDocument."""

import json

from echomind.profiling.schemas import EchoProfileDocument


def render_json(document: EchoProfileDocument) -> str:
    value = document.model_dump(mode="json")
    return (
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
