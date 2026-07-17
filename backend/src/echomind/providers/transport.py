"""Minimal HTTP transport boundary with injectable httpx MockTransport."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    headers: dict[str, str]
    content: bytes


class HTTPTransport(Protocol):
    def post_json(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: float,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
        verify_tls: bool,
    ) -> TransportResponse: ...


class HttpxTransport:
    """One-request client that never follows redirects and returns only safe headers."""

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport

    def post_json(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: float,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
        verify_tls: bool,
    ) -> TransportResponse:
        timeout = httpx.Timeout(
            timeout_seconds,
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
        )
        with httpx.Client(
            verify=verify_tls,
            follow_redirects=False,
            transport=self._transport,
            timeout=timeout,
        ) as client:
            response = client.post(url, json=payload, headers=headers)
        safe_headers = {
            name: value[:256]
            for name in ("content-type", "x-request-id", "openai-version")
            if (value := response.headers.get(name)) is not None
        }
        return TransportResponse(
            status_code=response.status_code,
            headers=safe_headers,
            content=response.content,
        )
