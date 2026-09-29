"""A deliberately small Markdown storyboard contract."""
from __future__ import annotations

import re


def parse_storyboard_value(value: dict, frames: int) -> dict:
    """Validate the structured storyboard emitted by the joint plan/key stage."""
    if not isinstance(value, dict):
        raise ValueError("storyboard must be an object")
    action = value.get("action")
    notes = value.get("notes")
    beats_value = value.get("beats")
    if not isinstance(action, str) or not action.strip():
        raise ValueError("storyboard.action must be a nonempty string")
    if (not isinstance(notes, list) or not notes or
            not all(isinstance(note, str) and note.strip() for note in notes)):
        raise ValueError("storyboard.notes must be a nonempty string array")
    if not isinstance(beats_value, list) or not beats_value:
        raise ValueError("storyboard.beats must be a nonempty array")
    beats = []
    cursor = 1
    for value in beats_value:
        if not isinstance(value, dict):
            raise ValueError("each storyboard beat must be an object")
        start, end = value.get("start"), value.get("end")
        event, exit_state = value.get("event"), value.get("exit")
        # Models often describe motion intervals with the preceding key shared by
        # both beats (1-9, 9-18). Internally each rendered frame belongs to one
        # beat, so normalize that equivalent boundary notation to 1-9, 10-18.
        if beats and type(start) is int and start == cursor - 1:
            start = cursor
        if (type(start) is not int or type(end) is not int or start != cursor or
                end < start or end > frames):
            raise ValueError(f"non-contiguous or invalid beat range: {start}-{end}")
        if not all(isinstance(text, str) and text.strip() for text in (event, exit_state)):
            raise ValueError("beat event and exit must be nonempty strings")
        beats.append({"start": start, "end": end, "event": event.strip(),
                      "exit": exit_state.strip()})
        cursor = end + 1
    if cursor != frames + 1:
        raise ValueError(f"storyboard must cover frames 1-{frames}, ends at {cursor - 1}")
    return {"action": action.strip(), "notes": [note.strip() for note in notes],
            "beats": beats, "key_indices": sorted({1, *[beat["end"] for beat in beats]})}


def storyboard_markdown(story: dict) -> str:
    """Render either parsed storyboard representation as the human-readable artifact."""
    notes = story["notes"]
    if isinstance(notes, str):
        notes_text = notes
    else:
        notes_text = "\n".join(f"- {note}" for note in notes)
    rows = ["| frames | event | exit |", "|---|---|---|"]
    for beat in story["beats"]:
        clean = lambda text: str(text).replace("|", "\\|").replace("\n", " ")
        rows.append(f'| {beat["start"]}-{beat["end"]} | {clean(beat["event"])} | {clean(beat["exit"])} |')
    rows_text = "\n".join(rows)
    return (f'## Action\n\n{story["action"]}\n\n## Notes\n\n{notes_text}\n\n'
            f'## Beats\n\n{rows_text}\n')


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
    if "intervals" in story:
        return story["intervals"]
    indices = story["key_indices"]
    return [{"from": a, "to": b, "indices": list(range(a + 1, b)),
             "beat": next(beat for beat in story["beats"] if beat["end"] == b)}
            for a, b in zip(indices, indices[1:])]
