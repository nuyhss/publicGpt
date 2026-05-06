"""
OpenAI-only LLM client.
"""

from __future__ import annotations

import logging
import time
from threading import BoundedSemaphore
from typing import Any, Dict, Optional

import requests
from fastapi import HTTPException

from app.config import (
    DEFAULT_MODEL,
    LLM_MAX_CONCURRENT_REQUESTS,
    LLM_MAX_TOKENS,
    LLM_QUEUE_TIMEOUT,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_ORGANIZATION,
    OPENAI_PROJECT,
)

logger = logging.getLogger("publicgpt.llm")

MAX_RETRIES = 2
_LLM_GATE = BoundedSemaphore(value=LLM_MAX_CONCURRENT_REQUESTS)


def _acquire_llm_slot(model: str) -> None:
    started = time.monotonic()
    acquired = _LLM_GATE.acquire(timeout=LLM_QUEUE_TIMEOUT)
    waited = time.monotonic() - started

    if not acquired:
        raise HTTPException(
            status_code=503,
            detail=(
                f"OpenAI is busy (queue timeout after {LLM_QUEUE_TIMEOUT}s). "
                "Please retry shortly."
            ),
        )

    if waited >= 0.25:
        logger.info("OpenAI queue wait %.2fs (model=%s)", waited, model)


def _openai_headers() -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    if OPENAI_ORGANIZATION:
        headers["OpenAI-Organization"] = OPENAI_ORGANIZATION
    if OPENAI_PROJECT:
        headers["OpenAI-Project"] = OPENAI_PROJECT
    return headers


def _raise_openai_config_error() -> None:
    if OPENAI_API_KEY:
        return
    raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured.")


def _extract_openai_error_text(response: requests.Response) -> str:
    try:
        data = response.json()
        error = data.get("error") if isinstance(data, dict) else None
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
    except Exception:
        pass
    return (response.text or "").strip()


def _raise_openai_http_error(response: requests.Response, model: str) -> None:
    error_text = _extract_openai_error_text(response)
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="OpenAI API key is invalid or missing.")
    if response.status_code == 429:
        raise HTTPException(status_code=429, detail="OpenAI rate limit exceeded or quota unavailable.")
    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail=f"OpenAI model '{model}' is not available for this API key.",
        )
    raise HTTPException(
        status_code=500,
        detail=f"OpenAI error while calling model '{model}': {error_text[:500]}",
    )


def _extract_openai_text(payload: Dict[str, Any]) -> str:
    output_items = payload.get("output")
    if not isinstance(output_items, list):
        return ""

    chunks: list[str] = []
    for item in output_items:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(str(content["text"]))
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def call_llm(
    prompt: str,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    model = model or DEFAULT_MODEL
    temperature = temperature if temperature is not None else LLM_TEMPERATURE
    max_tokens = max_tokens or LLM_MAX_TOKENS

    payload: Dict[str, Any] = {
        "model": model,
        "input": prompt,
        "max_output_tokens": max_tokens,
    }
    if not str(model).startswith("gpt-5"):
        payload["temperature"] = temperature

    return _call_openai_responses(payload, model)


def call_llm_with_image(
    prompt: str,
    image_url: str,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    model = model or DEFAULT_MODEL
    max_tokens = max_tokens or LLM_MAX_TOKENS
    payload: Dict[str, Any] = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_url, "detail": "high"},
                ],
            }
        ],
        "max_output_tokens": max_tokens,
    }
    return _call_openai_responses(payload, model)


def _call_openai_responses(payload: Dict[str, Any], model: str) -> Dict[str, Any]:
    _raise_openai_config_error()

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            _acquire_llm_slot(model)
            try:
                logger.debug("OpenAI request (attempt %d) -> model=%s", attempt, model)
                response = requests.post(
                    f"{OPENAI_BASE_URL}/responses",
                    headers=_openai_headers(),
                    json=payload,
                    timeout=LLM_TIMEOUT,
                )
            finally:
                _LLM_GATE.release()

            if response.status_code != 200:
                detail = _extract_openai_error_text(response)
                if response.status_code in {408, 429, 500, 502, 503, 504} and attempt < MAX_RETRIES:
                    last_error = detail
                    logger.warning("OpenAI transient error (attempt %d): %s", attempt, detail)
                    time.sleep(min(3.0, 1.5 * attempt))
                    continue
                _raise_openai_http_error(response, model)

            return response.json()
        except requests.exceptions.Timeout:
            last_error = f"OpenAI timeout after {LLM_TIMEOUT}s (attempt {attempt})"
            logger.warning(last_error)
        except requests.exceptions.ConnectionError as exc:
            last_error = f"Cannot connect to OpenAI at {OPENAI_BASE_URL}: {exc}"
            logger.error(last_error)
            break
        except HTTPException:
            raise
        except Exception as exc:
            last_error = str(exc)
            logger.error("OpenAI unexpected error: %s", exc)
            break

    raise HTTPException(status_code=500, detail=f"OpenAI request failed: {last_error}")


def check_llm_health() -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        return {"status": "disconnected", "provider": "openai", "error": "OPENAI_API_KEY missing"}
    try:
        response = requests.get(
            f"{OPENAI_BASE_URL}/models",
            headers=_openai_headers(),
            timeout=10,
        )
        response.raise_for_status()
        return {"status": "connected", "provider": "openai"}
    except Exception as exc:
        return {"status": "disconnected", "provider": "openai", "error": str(exc)}


def get_response_text(result: Dict[str, Any]) -> str:
    return _extract_openai_text(result)
