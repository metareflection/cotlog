"""LLM client for Bedrock via AnthropicBedrock."""

from __future__ import annotations

import os

from anthropic import AnthropicBedrock

_MODEL_MAP = {
    "sonnet": "global.anthropic.claude-sonnet-4-6",
    "haiku": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    "opus": "global.anthropic.claude-opus-4-6-v1",
}

_DEFAULT_MODEL = "sonnet"


def _get_client() -> AnthropicBedrock:
    kwargs: dict = {}
    region = os.environ.get("AWS_REGION")
    if region:
        kwargs["aws_region"] = region
    return AnthropicBedrock(**kwargs)


def _resolve_model(model: str | None = None) -> str:
    name = model or os.environ.get("CLAUDE_MODEL", _DEFAULT_MODEL)
    return _MODEL_MAP.get(name, name)


def generate(
    prompt: str,
    *,
    system: str = "",
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> str:
    """Send a prompt to Claude via Bedrock and return the text response."""
    client = _get_client()
    kwargs: dict = {
        "model": _resolve_model(model),
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    response = client.messages.create(**kwargs)
    return response.content[0].text
