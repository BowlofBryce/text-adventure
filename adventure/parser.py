from __future__ import annotations

import re

from .models import Intent


VERBS = {
    "go": "move",
    "move": "move",
    "walk": "move",
    "travel": "move",
    "look": "observe",
    "inspect": "observe",
    "talk": "talk",
    "speak": "talk",
    "attack": "attack",
    "take": "take",
    "grab": "take",
    "drop": "drop",
    "use": "use",
    "help": "help",
}


def parse_intent(raw: str) -> Intent:
    text = raw.strip().lower()
    if not text:
        return Intent(raw=raw, action="wait")

    words = re.findall(r"[a-zA-Z']+", text)
    if not words:
        return Intent(raw=raw, action="wait")

    action = VERBS.get(words[0], "custom")

    destination = None
    target = None
    tool = None

    if action == "move":
        m = re.search(r"(?:to|toward|into)\s+([a-zA-Z\s']+)$", text)
        destination = (m.group(1).strip() if m else " ".join(words[1:]).strip()) or None
    else:
        if len(words) > 1:
            target = words[1]
        m = re.search(r"with\s+([a-zA-Z\s']+)$", text)
        if m:
            tool = m.group(1).strip()

    dialogue = None
    if action == "talk":
        m = re.search(r"(?:to|with)\s+([a-zA-Z']+)", text)
        target = m.group(1) if m else target
        dialogue = raw

    return Intent(
        raw=raw,
        action=action,
        target=target,
        tool=tool,
        destination=destination,
        dialogue=dialogue,
    )
