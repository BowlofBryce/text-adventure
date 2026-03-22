from __future__ import annotations

import time
import uuid
from dataclasses import asdict

from .models import ActionResult, Intent, MemoryObject, WorldState
from .storage import Storage


class MemoryEngine:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def retrieve_active_memories(self, ws: WorldState, involved_entity_ids: list[str], query: str, limit: int = 10) -> list[MemoryObject]:
        all_memories = self.storage.list_memories()
        now = int(time.time())

        scored: list[tuple[float, MemoryObject]] = []
        query_tokens = set(query.lower().split())

        for mem in all_memories:
            if mem.state != "active" or not mem.user_facing:
                continue
            location_boost = 1.0 if mem.location_id == ws.current_location_id else 0.0
            entity_overlap = len(set(mem.entity_ids) & set(involved_entity_ids)) * 0.8
            importance = mem.importance * 1.7
            recency = max(0.0, 1.0 - ((now - mem.updated_at) / 172800.0))
            semantic = self._semantic_overlap(query_tokens, set(mem.content.lower().split()))
            score = importance + location_boost + entity_overlap + recency + semantic
            scored.append((score, mem))

        top = [m for _, m in sorted(scored, key=lambda x: x[0], reverse=True)[:limit]]
        for mem in top:
            mem.last_accessed_at = now
            mem.activation_count += 1
            self.storage.upsert_memory(mem)
        return top

    def consolidate_after_action(self, intent: Intent, result: ActionResult, ws: WorldState) -> list[MemoryObject]:
        now = int(time.time())
        candidates = self._build_candidates(result, ws, now)
        merged: list[MemoryObject] = []
        all_existing = self.storage.list_memories()

        for candidate in candidates:
            duplicate = self._find_duplicate(candidate, all_existing)
            if duplicate is None:
                self.storage.upsert_memory(candidate)
                merged.append(candidate)
                all_existing.append(candidate)
                continue

            duplicate.importance = max(duplicate.importance, candidate.importance)
            duplicate.confidence = max(duplicate.confidence, candidate.confidence)
            duplicate.updated_at = now
            duplicate.activation_count += 1
            duplicate.content = candidate.content
            duplicate.entity_ids = sorted(set(duplicate.entity_ids + candidate.entity_ids))
            duplicate.location_id = candidate.location_id or duplicate.location_id
            self.storage.upsert_memory(duplicate)
            merged.append(duplicate)

        return merged

    def _build_candidates(self, result: ActionResult, ws: WorldState, now: int) -> list[MemoryObject]:
        objects: list[MemoryObject] = []

        for item in result.memory_candidates:
            if not self._is_meaningful(item):
                continue
            objects.append(
                MemoryObject(
                    id=str(uuid.uuid4()),
                    content=item.get("content", "Unknown world fact"),
                    type=item.get("type", "fact"),
                    confidence=float(item.get("confidence", 0.82)),
                    importance=float(item.get("importance", 0.65)),
                    durability=float(item.get("durability", 0.7)),
                    scope=float(item.get("scope", 0.5)),
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

    def _is_meaningful(self, candidate: dict) -> bool:
        content = str(candidate.get("content", "")).strip().lower()
        if not content or len(content) < 18:
            return False
        low_value_tokens = ["player action", "turn ", "attempted", "input", "resolved with success"]
        if any(token in content for token in low_value_tokens):
            return False
        return float(candidate.get("importance", 0.5)) >= 0.55

    def _find_duplicate(self, candidate: MemoryObject, existing: list[MemoryObject]) -> MemoryObject | None:
        c = candidate.content.lower()
        for mem in existing:
            if mem.type != candidate.type:
                continue
            overlap = len(set(mem.entity_ids) & set(candidate.entity_ids)) > 0
            if not overlap:
                continue
            if self._text_similarity(c, mem.content.lower()) >= 0.72:
                return mem
        return None

    @staticmethod
    def _semantic_overlap(a: set[str], b: set[str]) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / max(len(a | b), 1)

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        tokens_a = set(a.split())
        tokens_b = set(b.split())
        if not tokens_a and not tokens_b:
            return 1.0
        return len(tokens_a & tokens_b) / max(len(tokens_a | tokens_b), 1)

    def debug_dump(self) -> dict:
        all_memories = self.storage.list_memories()
        meaningful = [m for m in all_memories if m.user_facing]
        return {
            "memory_count": len(all_memories),
            "active_meaningful_count": len([m for m in meaningful if m.state == "active"]),
            "memories": [asdict(m) for m in sorted(meaningful, key=lambda m: m.importance, reverse=True)[:25]],
        }
