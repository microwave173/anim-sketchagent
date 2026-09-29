"""Small text provider, bounded retries and per-request measurements."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def load_env():
    from dotenv import dotenv_values
    import os
    config = {k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}
    for key in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"):
        if key in os.environ:
            config[key] = os.environ[key]
    return config


class OutputLimitError(ValueError):
    def __init__(self, message, content):
        super().__init__(message)
        self.content = content


class Provider:
    def __init__(self, profile="official", effort="high", timeout=600, max_tokens=393216):
        self.config = load_env()
        if profile == "official":
            self.config.update(DEEPSEEK_BASE_URL="https://api.deepseek.com", DEEPSEEK_MODEL="deepseek-flash")
            if not self.config.get("DEEPSEEK_API_KEY") and (ROOT / "old_key.txt").exists():
                self.config["DEEPSEEK_API_KEY"] = (ROOT / "old_key.txt").read_text().strip()
        if not self.config.get("DEEPSEEK_API_KEY"):
            raise ValueError("No DeepSeek API credential configured")
        self.base = self.config.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = self.config.get("DEEPSEEK_MODEL", "deepseek-flash")
        self.effort, self.timeout, self.calls = effort, timeout, []
        self.max_tokens = max_tokens
        self._reasoning, self._reasoning_lock = {}, threading.RLock()

    def pop_reasoning(self, stage: str) -> str:
        """Return and release reasoning text from the most recent successful call for a stage."""
        with self._reasoning_lock:
            return self._reasoning.pop(stage, "")

    def call(self, stage: str, system: str, user: str, max_tokens: int | None = 393216) -> str:
        payload = {"model": self.model, "messages": [{"role": "system", "content": system},
                   {"role": "user", "content": user}], "stream": False}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if "token-plan.cn-beijing.maas.aliyuncs.com" in self.base:
            payload["enable_thinking"] = True
        else:
            payload.update(thinking={"type": "enabled"}, reasoning_effort=self.effort)
        for attempt in range(1, 3):
            started = time.perf_counter()
            row = {"stage": stage, "attempt": attempt, "model": self.model,
                   "input_chars": len(system) + len(user), "max_tokens": max_tokens,
                   "output_budget_policy": "omitted" if max_tokens is None else "explicit"}
            try:
                request = urllib.request.Request(self.base.rstrip("/") + "/chat/completions",
                    data=json.dumps(payload).encode(), headers={"Authorization": f"Bearer {self.config['DEEPSEEK_API_KEY']}",
                                                               "Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = json.loads(response.read().decode())
                choice = body["choices"][0]
                message = choice["message"]
                content = message.get("content") or ""
                reasoning = message.get("reasoning_content") or ""
                with self._reasoning_lock:
                    self._reasoning[stage] = reasoning
                row.update(ok=True, usage=body.get("usage"), finish_reason=choice.get("finish_reason"),
                           output_chars=len(content), reasoning_chars=len(reasoning))
                if choice.get("finish_reason") == "length":
                    raise OutputLimitError(f"Incomplete model output: finish_reason=length, chars={len(content)}", content)
                if not content.strip():
                    raise ValueError("Empty model output")
                return content
            except Exception as exc:
                row.update(ok=False, error_type=type(exc).__name__, error=str(exc))
                retry = attempt == 1 and (isinstance(exc, (TimeoutError, urllib.error.URLError)) and
                    (not isinstance(exc, urllib.error.HTTPError) or exc.code in (429, 500, 502, 503, 504)))
                if not retry:
                    raise
            finally:
                row["seconds"] = round(time.perf_counter() - started, 3)
                self.calls.append(row)
            time.sleep(3)
        raise RuntimeError("Provider retry budget exhausted")


def json_object(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Expected one JSON object")
    return value
