"""Проверка OpenAI API key и лимитов из HTTP headers."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
RATE_LIMIT_HEADER_MAP = {
    "x-ratelimit-limit-requests": "limit_requests",
    "x-ratelimit-limit-tokens": "limit_tokens",
    "x-ratelimit-remaining-requests": "remaining_requests",
    "x-ratelimit-remaining-tokens": "remaining_tokens",
    "x-ratelimit-reset-requests": "reset_requests",
    "x-ratelimit-reset-tokens": "reset_tokens",
    "x-request-id": "request_id",
}


@dataclass
class OpenAIKeyCheckResult:
    success: bool
    message: str
    model: str
    status_code: Optional[int] = None
    request_id: Optional[str] = None
    rate_limits: dict[str, str] = field(default_factory=dict)
    billing_note: str = (
        "Баланс и месячный spend обычным robot API key не видно. "
        "Для этого нужен OpenAI admin key или dashboard."
    )


Requester = Callable[[urllib.request.Request, float], object]


def check_openai_api_key(
    api_key: str,
    model: str,
    requester: Requester = urllib.request.urlopen,
    timeout: float = 20.0,
) -> OpenAIKeyCheckResult:
    api_key = api_key.strip()
    if not api_key:
        return OpenAIKeyCheckResult(
            success=False,
            message="OpenAI API key еще не сохранен.",
            model=model,
        )

    body = {
        "model": model,
        "input": "Reply with OK only.",
        "max_output_tokens": 8,
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        response = requester(request, timeout)
        status_code = int(response.getcode())
        response.read()
        headers = _headers_to_dict(response.headers)
        rate_limits = extract_rate_limit_headers(headers)
        return OpenAIKeyCheckResult(
            success=200 <= status_code < 300,
            message="Ключ работает. Облачный мозг отвечает.",
            model=model,
            status_code=status_code,
            request_id=rate_limits.get("request_id"),
            rate_limits=rate_limits,
        )
    except urllib.error.HTTPError as exc:
        headers = _headers_to_dict(exc.headers)
        rate_limits = extract_rate_limit_headers(headers)
        return OpenAIKeyCheckResult(
            success=False,
            message=_http_error_message(exc),
            model=model,
            status_code=exc.code,
            request_id=rate_limits.get("request_id"),
            rate_limits=rate_limits,
        )
    except Exception as exc:
        return OpenAIKeyCheckResult(
            success=False,
            message=f"Не получилось проверить ключ: {exc}",
            model=model,
        )


def extract_rate_limit_headers(headers: Mapping[str, str]) -> dict[str, str]:
    normalized = {str(key).lower(): str(value) for key, value in headers.items()}
    result: dict[str, str] = {}
    for header_name, result_name in RATE_LIMIT_HEADER_MAP.items():
        value = normalized.get(header_name)
        if value:
            result[result_name] = value
    return result


def _headers_to_dict(headers: object) -> dict[str, str]:
    if hasattr(headers, "items"):
        return {str(key): str(value) for key, value in headers.items()}
    return {}


def _http_error_message(exc: urllib.error.HTTPError) -> str:
    if exc.code == 401:
        return "Ключ не работает: OpenAI вернул 401. Проверь, что key скопирован полностью."
    if exc.code == 429:
        return "Ключ правильный, но лимит сейчас закончился или слишком много запросов."
    return f"OpenAI вернул ошибку {exc.code}."

