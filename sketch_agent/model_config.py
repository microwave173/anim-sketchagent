from __future__ import annotations

import os


VALID_REASONING_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh"}


def get_reasoning_effort(value: str | None = None) -> str:
    effort = (value or os.getenv("REASONING_EFFORT", "medium")).strip().lower()
    if effort not in VALID_REASONING_EFFORTS:
        allowed = ", ".join(sorted(VALID_REASONING_EFFORTS))
        raise ValueError(f"invalid reasoning effort {effort!r}; expected one of: {allowed}")
    return effort


def reasoning_options(value: str | None = None) -> dict[str, dict[str, str]]:
    return {"reasoning": {"effort": get_reasoning_effort(value)}}
