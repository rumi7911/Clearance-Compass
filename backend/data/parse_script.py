"""Parses raw screenplay-style text into the {id, heading, text} scene shape
pipeline.py expects, plus the inverse formatter used to serve the canonical
demo script (backend/data/scenes.py) back to the frontend so the two can
never silently drift apart.
"""

from __future__ import annotations

import re

MAX_SCRIPT_CHARS = 6000
MAX_SCENES = 6
GENERIC_HEADING = "CUSTOM SCENE"

# Matches a screenplay slugline: a line starting with INT., EXT., INT./EXT.
# (either order), or I/E -- case-insensitive, followed by "." and/or
# whitespace and then more text. The alternation requires the next
# character after INT/EXT to be "." or whitespace, not another letter, so
# "Interior" or "Extra" never false-positive.
SLUGLINE_RE = re.compile(
    r"^\s*(?:INT\.?\s*/\s*EXT|EXT\.?\s*/\s*INT|I/E|INT|EXT)\.?\s+\S.*$",
    re.IGNORECASE,
)


class ScriptValidationError(ValueError):
    """Raised for guardrail failures; str(exc) is the user-facing message."""


def parse_script(raw: str) -> list[dict]:
    """Pure parse, no limits enforced. Splits on sluglines; if none are
    found, the whole input becomes one scene under GENERIC_HEADING."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    slugline_idxs = [i for i, line in enumerate(lines) if SLUGLINE_RE.match(line)]

    if not slugline_idxs:
        body = text.strip()
        if not body:
            return []
        return [{"id": "scene-1", "heading": GENERIC_HEADING, "text": body}]

    scenes: list[dict] = []
    for n, start in enumerate(slugline_idxs):
        end = slugline_idxs[n + 1] if n + 1 < len(slugline_idxs) else len(lines)
        heading = lines[start].strip()
        body = "\n".join(lines[start + 1 : end]).strip()
        scenes.append({"id": f"scene-{n + 1}", "heading": heading, "text": body})
    return scenes


def format_scenes_as_script(scenes: list[dict]) -> str:
    """Inverse of parse_script: heading, blank line, body, blank line
    between scenes."""
    return "\n\n".join(f"{s['heading']}\n\n{s['text']}" for s in scenes)


def parse_and_validate(raw: str) -> tuple[list[dict], str | None]:
    """Enforces guardrails for the public endpoint. Returns (scenes,
    warning); raises ScriptValidationError with a user-facing message on
    hard failure."""
    if not raw or not raw.strip():
        raise ScriptValidationError(
            "Script text is empty. Paste or type a scene before running analysis."
        )
    if len(raw) > MAX_SCRIPT_CHARS:
        raise ScriptValidationError(
            f"Script is too long ({len(raw):,} characters). Keep it under "
            f"{MAX_SCRIPT_CHARS:,} characters for this demo."
        )

    scenes = parse_script(raw)
    if not scenes:
        raise ScriptValidationError("Couldn't find any scene text to analyze.")

    warning = None
    if len(scenes) > MAX_SCENES:
        dropped = len(scenes) - MAX_SCENES
        warning = (
            f"This script had {len(scenes)} scenes; only the first "
            f"{MAX_SCENES} were analyzed ({dropped} dropped) to keep "
            "runtime reasonable for this demo."
        )
        scenes = scenes[:MAX_SCENES]

    return scenes, warning
