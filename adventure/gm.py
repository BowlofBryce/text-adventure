from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import asdict

from .models import ActionResult, Entity, Intent, MemoryObject, WorldState


class GameMaster:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    def resolve_complex_action(
        self,
        intent: Intent,
        ws: WorldState,
        entities: list[Entity],
        active_memories: list[MemoryObject],
    ) -> ActionResult:
        if not self.api_key:
            return self._fallback(intent, ws)

        prompt = {
            "intent": asdict(intent),
            "world_state": asdict(ws),
            "entities": [asdict(e) for e in entities],
            "active_memory": [asdict(m) for m in active_memories],
            "instructions": [
                "You are an AI game master for a simulation.",
                "Do not contradict world state or memory.",
                "Return strict JSON with keys: success, narrative, world_updates, memory_candidates.",
            ],
        }

        body = {
            "model": self.model,
            "input": json.dumps(prompt),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "gm_output",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "narrative": {"type": "string"},
                            "world_updates": {"type": "object"},
                            "memory_candidates": {"type": "array", "items": {"type": "object"}},
                        },
                        "required": ["success", "narrative", "world_updates", "memory_candidates"],
                        "additionalProperties": False,
                    },
                }
            },
        }

        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            text = payload.get("output", [{}])[0].get("content", [{}])[0].get("text", "{}")
            parsed = json.loads(text)
            return ActionResult(
                success=bool(parsed.get("success", False)),
                narrative=str(parsed.get("narrative", "Nothing happens.")),
                world_updates=dict(parsed.get("world_updates", {})),
                memory_candidates=list(parsed.get("memory_candidates", [])),
            )
        except Exception:
            return self._fallback(intent, ws)

    def _fallback(self, intent: Intent, ws: WorldState) -> ActionResult:
        narrative = f"You attempt to {intent.raw}. The world resists certainty, but consequences ripple outward."
        candidates = [
            {
                "content": f"Player attempted complex action: {intent.raw}",
                "type": "signal",
                "importance": 0.55,
                "durability": 0.6,
                "scope": 0.5,
                "entity_ids": [ws.player_entity_id],
                "location_id": ws.current_location_id,
            }
        ]
        return ActionResult(success=True, narrative=narrative, memory_candidates=candidates)
