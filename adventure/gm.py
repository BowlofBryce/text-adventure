from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict

from .models import ActionResult, Entity, Intent, MemoryObject, Scenario, WorldState


class GameMaster:
    def __init__(self) -> None:
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.status = {
            "connected": False,
            "model": self.model,
            "last_call_success": False,
            "fallback_active": True,
            "last_error": "No local model call attempted yet.",
            "last_latency_ms": None,
            "last_response_source": "fallback",
            "checked_at": None,
        }

    def get_status(self) -> dict:
        return dict(self.status)

    def resolve_complex_action(
        self,
        intent: Intent,
        ws: WorldState,
        entities: list[Entity],
        active_memories: list[MemoryObject],
        scenario: Scenario | None,
    ) -> ActionResult:
        prompt = self._build_prompt(intent, ws, entities, active_memories, scenario)
        started = time.time()

        try:
            self._check_connectivity()
            body = {
                "model": self.model,
                "prompt": json.dumps(prompt, indent=2),
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.5},
            }
            req = urllib.request.Request(
                f"{self.ollama_host}/api/generate",
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))

            raw = payload.get("response", "{}")
            parsed = self._parse_json_object(raw)
            result = ActionResult(
                success=bool(parsed.get("success", True)),
                narrative=str(parsed.get("narration", "The scene shifts, but details are unclear.")),
                world_updates=dict(parsed.get("world_state_changes", {})),
                entity_updates=list(parsed.get("entity_state_changes", [])),
                memory_candidates=list(parsed.get("candidate_memories", [])),
                resolution_meta={
                    "source": "local_ai",
                    "fallback_used": False,
                    "raw_model": self.model,
                },
            )

            self.status.update(
                {
                    "connected": True,
                    "last_call_success": True,
                    "fallback_active": False,
                    "last_error": None,
                    "last_latency_ms": int((time.time() - started) * 1000),
                    "last_response_source": "local_ai",
                    "checked_at": int(time.time()),
                }
            )
            return result
        except Exception as exc:
            self.status.update(
                {
                    "last_call_success": False,
                    "fallback_active": True,
                    "last_error": str(exc),
                    "last_latency_ms": int((time.time() - started) * 1000),
                    "last_response_source": "fallback",
                    "checked_at": int(time.time()),
                }
            )
            return self._fallback(intent, ws, str(exc))

    def _build_prompt(
        self,
        intent: Intent,
        ws: WorldState,
        entities: list[Entity],
        active_memories: list[MemoryObject],
        scenario: Scenario | None,
    ) -> dict:
        nearby = [
            asdict(e)
            for e in entities
            if e.id == ws.current_location_id or e.state.get("location_id") == ws.current_location_id
        ]
        player = next((e for e in entities if e.id == ws.player_entity_id), None)

        return {
            "role": "You are the simulation game master of a high-stakes text adventure.",
            "scenario_premise": {
                "id": scenario.id if scenario else ws.active_conditions.get("scenario_id"),
                "name": scenario.name if scenario else "Unknown",
                "description": scenario.description if scenario else ws.active_conditions.get("scenario_description", ""),
                "world_seed": scenario.world_seed if scenario else {},
            },
            "world_state": {
                "turn": ws.turn,
                "current_location_id": ws.current_location_id,
                "inventory_item_ids": ws.inventory_item_ids,
                "npc_positions": ws.npc_positions,
                "active_conditions": ws.active_conditions,
            },
            "player": asdict(player) if player else {"id": ws.player_entity_id},
            "nearby_entities": nearby,
            "active_memories": [asdict(m) for m in active_memories],
            "player_action": asdict(intent),
            "resolution_instructions": [
                "Resolve the action against world state and constraints.",
                "Narration must be specific to this scenario, not generic.",
                "Only include memory candidates that are consequential truths.",
                "Do not output meta commentary.",
                "Return strict JSON with keys: success, narration, world_state_changes, entity_state_changes, candidate_memories, follow_up_hooks.",
            ],
            "output_contract": {
                "success": "boolean",
                "narration": "string",
                "world_state_changes": "object where keys are world condition fields to set",
                "entity_state_changes": "array of {entity_id, state_updates(optional), relationship_updates(optional), position(optional)}",
                "candidate_memories": "array of {content, type, importance, durability, scope, entity_ids, location_id}",
                "follow_up_hooks": "array of strings",
            },
        }

    def _check_connectivity(self) -> None:
        req = urllib.request.Request(f"{self.ollama_host}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        available = [m.get("name") for m in payload.get("models", [])]
        self.status["connected"] = True
        if self.model not in available:
            raise RuntimeError(f"Model '{self.model}' not found in Ollama. Available: {available}")

    @staticmethod
    def _parse_json_object(text: str) -> dict:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            if stripped.startswith("json"):
                stripped = stripped[4:]
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model response did not contain a JSON object.")
        return json.loads(stripped[start : end + 1])

    def _fallback(self, intent: Intent, ws: WorldState, reason: str) -> ActionResult:
        narrative = (
            f"Fallback narration: you attempt '{intent.raw}', but local AI generation is currently unavailable. "
            "The world remains stable until AI connectivity is restored."
        )
        return ActionResult(
            success=True,
            narrative=narrative,
            world_updates={"fallback_reason": reason},
            memory_candidates=[],
            resolution_meta={"source": "fallback", "fallback_used": True, "reason": reason},
        )
