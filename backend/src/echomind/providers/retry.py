"""Small deterministic retry helpers with no random jitter."""

from collections.abc import Callable
from time import sleep

Sleeper = Callable[[float], None]


def default_sleeper(seconds: float) -> None:
    sleep(seconds)


def backoff_seconds(completed_attempts: int) -> float:
    """Return 0.1, 0.2, 0.4... after attempts one, two, three..."""
    return 0.1 * float(2 ** (completed_attempts - 1))
