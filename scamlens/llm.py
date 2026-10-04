"""LLM client: OpenAI-compatible chat completions via the stored connector.

Auth: dynamic-credential surrogate from the connector named "custom.nvidia",
applied by add_surrogate_to_request(). No key is ever hardcoded, read from
the environment, or logged here.
"""
from __future__ import annotations

import json
import sys
import urllib.request

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response  # noqa: E402

BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = "nvidia/nemotron-3-super-120b-a12b"
_ALLOWED_HOSTS = ("integrate.api.nvidia.com",)


def configured() -> bool:
    return True  # connector-backed; auth is supplied at request time


def backend_label() -> str:
    return MODEL


def complete(messages: list[dict], model: str | None = None,
             temperature: float = 0.2, max_tokens: int = 8192,
             timeout: float = 300.0, response_format: dict | None = None) -> str:
    """Chat completion. Falls back to reasoning_content when content is null.

    Nemotron-3-super is a reasoning model: keep max_tokens generous, since
    tiny budgets come back with content:null or finish:length.
    response_format (e.g. {"type": "json_object"}) is passed through when set.
    """
    payload = {"model": model or MODEL, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    if response_format:
        payload["response_format"] = response_format
    req = urllib.request.Request(
        BASE_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST")
    add_surrogate_to_request(req, "custom.nvidia", allowed_hosts=_ALLOWED_HOSTS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = read_json_response(resp)
    message = data["choices"][0]["message"]
    content = message.get("content")
    if content:
        return content
    reasoning = message.get("reasoning_content")
    if reasoning:
        return reasoning
    raise RuntimeError("LLM returned empty content (content and reasoning_content both null)")
