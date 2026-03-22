from __future__ import annotations

import time
import uuid
from dataclasses import asdict

from .models import ActionResult, Intent, MemoryObject, WorldState
from .storage import Storage


class MemoryEngine:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def retrieve_active_memories(self, ws: WorldState, involved_entity_ids: list[str], query: str, limit: int = 14) -> list[MemoryObject]:
        all_memories = self.storage.list_memories()
        now = int(time.time())

        scored: list[tuple[float, MemoryObject]] = []
        query_tokens = set(query.lower().split())

        for mem in all_memories:
            if mem.state != "active":
                continue
            location_boost = 1.2 if mem.location_id == ws.current_location_id else 0.0
            entity_overlap = len(set(mem.entity_ids) & set(involved_entity_ids)) * 0.8
            importance = mem.importance * 1.5
            recency = max(0.0, 1.0 - ((now - mem.updated_at) / 86400.0))
            sem = self._semantic_overlap(query_tokens, set(mem.content.lower().split()))
            score = importance + location_boost + entity_overlap + recency + sem
            scored.append((score, mem))

        top = [m for _, m in sorted(scored, key=lambda x: x[0], reverse=True)[:limit]]
        for mem in top:
            mem.last_accessed_at = now
            mem.activation_count += 1
            self.storage.upsert_memory(mem)
        return top

    def consolidate_after_action(self, intent: Intent, result: ActionResult, ws: WorldState) -> list[MemoryObject]:
        now = int(time.time())
        candidates = self._build_candidates(intent, result, ws, now)
        merged: list[MemoryObject] = []
        all_existing = self.storage.list_memories()

        for candidate in candidates:
            duplicate = self._find_duplicate(candidate, all_existing)
            if duplicate is None:
                self.storage.upsert_memory(candidate)
                merged.append(candidate)
                continue

            duplicate.importance = min(1.0, duplicate.importance + 0.05)
            duplicate.confidence = min(1.0, duplicate.confidence + 0.1)
            duplicate.updated_at = now
            duplicate.activation_count += 1
            duplicate.content = candidate.content
            self.storage.upsert_memory(duplicate)
            merged.append(duplicate)

        return merged

    def _build_candidates(self, intent: Intent, result: ActionResult, ws: WorldState, now: int) -> list[MemoryObject]:
        seeds: list[dict] = [
            {
                "content": f"Turn {ws.turn}: Player action '{intent.raw}' resolved with success={result.success}.",
                "type": "event",
                "importance": 0.4,
                "durability": 0.4,
                "scope": 0.3,
                "entity_ids": [ws.player_entity_id],
                "location_id": ws.current_location_id,
            }
        ]

        for mc in result.memory_candidates:
            seeds.append(mc)

        objects: list[MemoryObject] = []
        for item in seeds:
            objects.append(
                MemoryObject(
                    id=str(uuid.uuid4()),
                    content=item.get("content", "Unknown memory"),
                    type=item.get("type", "event"),
                    confidence=float(item.get("confidence", 0.7)),
                    importance=float(item.get("importance", 0.5)),
                    durability=float(item.get("durability", 0.5)),
                    scope=float(item.get("scope", 0.3)),
                    state=item.get("state", "active"),
                    entity_ids=item.get("entity_ids", [ws.player_entity_id]),
                    location_id=item.get("location_id", ws.current_location_id),
                    created_at=now,
                    updated_at=now,
                    activation_count=0,
                    user_facing=bool(item.get("user_facing", True)),
                )
            )
        return objects

    def _find_duplicate(self, candidate: MemoryObject, existing: list[MemoryObject]) -> MemoryObject | None:
        c = candidate.content.lower()
        for mem in existing:
            if mem.type != candidate.type or mem.location_id != candidate.location_id:
                continue
            distance = self._text_distance(c, mem.content.lower())
            overlap = len(set(mem.entity_ids) & set(candidate.entity_ids)) > 0
            if distance < 0.26 and overlap:
                return mem
        return None

    @staticmethod
    def _semantic_overlap(a: set[str], b: set[str]) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / max(len(a | b), 1)

    @staticmethod
    def _text_distance(a: str, b: str) -> float:
        tokens_a = set(a.split())
        tokens_b = set(b.split())
        if not tokens_a and not tokens_b:
            return 0.0
        return 1.0 - (len(tokens_a & tokens_b) / max(len(tokens_a | tokens_b), 1))

    def debug_dump(self) -> dict:
        return {
            "memory_count": len(self.storage.list_memories()),
            "memories": [asdict(m) for m in self.storage.list_memories()],
        }
