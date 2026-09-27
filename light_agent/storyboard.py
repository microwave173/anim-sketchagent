"""A deliberately small Markdown storyboard contract."""
from __future__ import annotations

import re


def parse_storyboard(text: str, frames: int) -> dict:
    blocks = {}
    matches = list(re.finditer(r"^## (Action|Notes|Beats)\s*$", text, re.M))
    if [m.group(1) for m in matches] != ["Action", "Notes", "Beats"]:
        raise ValueError("Expected exactly ## Action, ## Notes, ## Beats in that order")
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks[match.group(1)] = text[match.end():end].strip()
    if not blocks["Action"] or not blocks["Notes"]:
        raise ValueError("Action and Notes must be nonempty")
    beats = []
    cursor = 1
    for line in blocks["Beats"].splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0].lower() == "frames" or re.fullmatch(r":?-+:?", cells[0]):
            continue
        if len(cells) != 3:
            raise ValueError("Beat table requires exactly frames | event | exit")
        span = re.fullmatch(r"(\d+)\s*-\s*(\d+)", cells[0])
        if not span:
            raise ValueError(f"Invalid beat frame range: {cells[0]}")
        start, end = map(int, span.groups())
        if start != cursor or end < start or end > frames or not all(cells[1:]):
            raise ValueError(f"Non-contiguous, empty or invalid beat: {cells}")
        beats.append({"start": start, "end": end, "event": cells[1], "exit": cells[2]})
        cursor = end + 1
    if not beats or cursor != frames + 1:
        raise ValueError(f"Story must cover 1-{frames}, ends at {cursor - 1}")
    return {"action": blocks["Action"], "notes": blocks["Notes"], "beats": beats,
            "key_indices": sorted({1, *[beat['end'] for beat in beats]})}


def gaps(story: dict) -> list[dict]:
    indices = story["key_indices"]
    return [{"from": a, "to": b, "indices": list(range(a + 1, b)),
             "beat": next(beat for beat in story["beats"] if beat["end"] == b)}
            for a, b in zip(indices, indices[1:])]
