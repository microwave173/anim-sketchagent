#!/usr/bin/env python3
"""Shared Terra (gpt-5.6-terra) chat client for task gen, plans, and judging."""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path


def load_env() -> dict[str, str]:
    env = {}
    for candidate in (
        Path("/Users/lalala/Desktop/sketch/.env"),
        Path(__file__).resolve().parents[2] / ".env",
        Path("/root/autodl-tmp/grpo_sa_pilot/.env"),
    ):
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
            break
    for k in ("OPENAI_API_KEY", "BASE_URL", "MODEL", "REASONING_EFFORT", "ZHIPU_API_KEY", "ZHIPU_BASE_URL", "ZHIPU_MODEL"):
        if k in os.environ:
            env[k] = os.environ[k]
    return env


def parse_json_value(raw: str):
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    dec = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch in "{[":
            try:
                val, _ = dec.raw_decode(text[i:])
                return val
            except json.JSONDecodeError:
                continue
    raise ValueError("no JSON object/array in model output")


def parse_json_obj(raw: str) -> dict:
    val = parse_json_value(raw)
    if not isinstance(val, dict):
        raise ValueError("expected JSON object")
    return val


def parse_json_array(raw: str) -> list:
    val = parse_json_value(raw)
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        for key in ("tasks", "items", "strokes", "plans"):
            if isinstance(val.get(key), list):
                return val[key]
    raise ValueError("expected JSON array")


def call_chat(
    messages: list[dict],
    *,
    base_url: str,
    api_key: str,
    model: str,
    extra: dict | None = None,
    max_tokens: int = 4000,
    temperature: float = 0.3,
    timeout: int = 180,
    label: str = "llm",
) -> str:
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if extra:
        payload.update(extra)
    last = None
    attempts = 10
    for attempt in range(attempts):
        req = urllib.request.Request(
            base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode())
            msg = body["choices"][0]["message"]
            content = msg.get("content") or msg.get("reasoning_content") or ""
            if not str(content).strip():
                raise ValueError(f"empty {label} content")
            return str(content)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            last = e
            code = getattr(e, "code", None)
            wait = 8 * (attempt + 1)
            if isinstance(e, urllib.error.HTTPError) and code in (429, 502, 503, 504):
                wait = min(90, 15 * (2 ** attempt))
            print(f"{label} attempt {attempt+1} failed: {type(e).__name__}: {e}; sleep {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"{label} failed after {attempts} attempts") from last


def call_terra(
    messages: list[dict],
    *,
    max_tokens: int = 4000,
    temperature: float = 0.3,
    reasoning_effort: str = "medium",
    timeout: int = 180,
    env: dict[str, str] | None = None,
) -> str:
    cfg = env or load_env()
    return call_chat(
        messages,
        base_url=cfg["BASE_URL"],
        api_key=cfg["OPENAI_API_KEY"],
        model=cfg.get("MODEL", "gpt-5.6-terra"),
        extra={"reasoning_effort": reasoning_effort, "reasoning": {"effort": reasoning_effort}},
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
        label="terra",
    )


def call_deepseek(
    messages: list[dict],
    *,
    max_tokens: int = 2048,
    temperature: float = 0.2,
    timeout: int = 180,
    env: dict[str, str] | None = None,
    model: str | None = None,
    extra: dict | None = None,
) -> str:
    """DeepSeek chat. Default vision model is deepseek-v4-flash-vision-exp."""
    cfg = env or load_env()
    if extra is None:
        extra = {"thinking": {"type": "disabled"}}
    return call_chat(
        messages,
        base_url=cfg.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        api_key=cfg["DEEPSEEK_API_KEY"],
        model=model
        or cfg.get("DEEPSEEK_VISION_MODEL")
        or "deepseek-v4-flash-vision-exp",
        extra=extra,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
        label="deepseek",
    )


def call_glm_vision(
    messages: list[dict],
    *,
    max_tokens: int = 2048,
    temperature: float = 0.2,
    timeout: int = 180,
    env: dict[str, str] | None = None,
    model: str | None = None,
) -> str:
    """glm-4.5v (or ZHIPU_VISION_MODEL). glm-5.3 is text-only."""
    cfg = env or load_env()
    return call_chat(
        messages,
        base_url=cfg["ZHIPU_BASE_URL"],
        api_key=cfg["ZHIPU_API_KEY"],
        model=model or cfg.get("ZHIPU_VISION_MODEL", "glm-4.5v"),
        extra=None,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
        label="glm-vision",
    )


def data_url(path: Path) -> str:
    import base64

    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def call_glm(
    messages: list[dict],
    *,
    max_tokens: int = 4096,
    temperature: float = 0.4,
    reasoning_effort: str = "low",
    timeout: int = 180,
    env: dict[str, str] | None = None,
) -> str:
    cfg = env or load_env()
    return call_chat(
        messages,
        base_url=cfg["ZHIPU_BASE_URL"],
        api_key=cfg["ZHIPU_API_KEY"],
        model=cfg.get("ZHIPU_MODEL", "glm-5.3"),
        extra={"thinking": {"type": "enabled"}, "reasoning_effort": reasoning_effort},
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
        label="glm",
    )
