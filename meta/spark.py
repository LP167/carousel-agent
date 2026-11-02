"""Muse Spark 1.3 — the agent's brain, the claim checker, and the visual checker."""
from __future__ import annotations

import json
import re

from .client import Transport, image_data_url


def chat(t: Transport, messages: list, tools: list | None = None, schema: dict | None = None,
         schema_name: str = "result", temperature: float = 0.2, kind: str = "spark") -> dict:
    """Returns the assistant message as a plain dict: {content, tool_calls}."""
    model = t.cfg["models"]["brain"]
    kwargs = {"model": model, "messages": messages, "temperature": temperature}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if schema:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": schema, "strict": True},
        }

    def live():
        r = t.openai.chat.completions.create(**kwargs)
        d = r.model_dump()
        msg = d["choices"][0]["message"]
        return {"content": msg.get("content"), "tool_calls": msg.get("tool_calls") or [], "usage": d.get("usage")}

    return t.call(kind, live, {"model": model, "n_messages": len(messages), "tools": bool(tools), "schema": schema_name if schema else None})


def parse_json(text: str | None) -> dict:
    """Structured output should already be JSON; tolerate ```json fences just in case."""
    if not text:
        raise ValueError("empty model output")
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=0)
    return json.loads(text[start:])


def ask_json(t: Transport, system: str, user_parts: list, schema: dict, schema_name: str, kind: str) -> dict:
    """One structured-output call. user_parts = OpenAI content parts (text / image_url)."""
    msg = chat(
        t,
        [{"role": "system", "content": system}, {"role": "user", "content": user_parts}],
        schema=schema,
        schema_name=schema_name,
        temperature=0,
        kind=kind,
    )
    return parse_json(msg["content"])


def image_part(path, max_side: int | None = None) -> dict:
    return {"type": "image_url", "image_url": {"url": image_data_url(path, max_side)}}


def text_part(s: str) -> dict:
    return {"type": "text", "text": s}
