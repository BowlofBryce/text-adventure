from __future__ import annotations

import time

from .gm import GameMaster
from .memory import MemoryEngine
from .models import ActionResult, Entity, Intent, WorldState
from .parser import parse_intent
from .scenarios import get_scenario
from .storage import Storage


class GameEngine:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage
        self.memory = MemoryEngine(storage)
        self.gm = GameMaster()

    def new_game(self, scenario_id: str, initial_prompt: str) -> dict:
        scenario = get_scenario(scenario_id)
        if scenario is None:
            raise ValueError(f"Unknown scenario: {scenario_id}")

        self.storage.clear_all()

        player = Entity(
            id="player-1",
            name="Player",
            type="player",
            attributes={"health": 100},
            state={"backstory_seed": initial_prompt.strip() if initial_prompt else "", "status": "alive"},
        )

        entities: list[Entity] = [player]
        for loc in scenario.world_seed.get("locations", []):
            entities.append(Entity(id=loc["id"], name=loc["name"], type="location", attributes={"description": loc["desc"]}))
        for npc in scenario.world_seed.get("npcs", []):
            entities.append(
                Entity(
                    id=npc["id"],
                    name=npc["name"],
                    type="npc",
                    attributes={"faction": npc.get("faction")},
                    state={"location_id": npc.get("location"), "attitude": "neutral", "status": "active"},
                )
            )
        for item in scenario.world_seed.get("items", []):
            entities.append(
                Entity(
                    id=item["id"],
                    name=item["name"],
                    type="item",
                    state={"location_id": item.get("location"), "holder_id": None},
                )
            )
        for faction in scenario.world_seed.get("factions", []):
            entities.append(Entity(id=faction["id"], name=faction["name"], type="faction"))

        self.storage.upsert_entities(entities)

        ws = WorldState(
            turn=1,
            current_location_id=scenario.world_seed["start_location"],
            player_entity_id=player.id,
            inventory_item_ids=[],
            npc_positions={n["id"]: n["location"] for n in scenario.world_seed.get("npcs", [])},
            active_conditions={
                "scenario_id": scenario.id,
                "scenario_name": scenario.name,
                "scenario_description": scenario.description,
                "fallback_reason": None,
            },
        )
        self.storage.save_world_state(ws)

        start_memories = [
            {
                "content": f"Scenario premise: {scenario.description}",
                "type": "rule",
                "importance": 0.95,
                "durability": 0.98,
                "scope": 0.9,
                "entity_ids": [player.id],
                "location_id": ws.current_location_id,
            },
            {
                "content": f"The player begins at {self._location_name(ws.current_location_id)}.",
                "type": "state",
                "importance": 0.82,
                "durability": 0.85,
                "scope": 0.7,
                "entity_ids": [player.id, ws.current_location_id],
                "location_id": ws.current_location_id,
            },
        ]
        if initial_prompt.strip():
            start_memories.append(
                {
                    "content": f"Opening world seed from player: {initial_prompt.strip()}",
                    "type": "fact",
                    "importance": 0.78,
                    "durability": 0.8,
                    "scope": 0.7,
                    "entity_ids": [player.id],
                    "location_id": ws.current_location_id,
                }
            )

        self.memory.consolidate_after_action(
            Intent(raw="start", action="start"),
            ActionResult(success=True, narrative=f"{scenario.name} begins.", memory_candidates=start_memories),
            ws,
        )

        return self.snapshot(f"{scenario.name} begins. {scenario.description}")

    def process_turn(self, raw_input: str) -> dict:
        ws = self._require_world_state()
        intent = parse_intent(raw_input)

        involved_entities = self._find_involved_entities(intent, ws)
        active_memory = self.memory.retrieve_active_memories(
            ws=ws,
            involved_entity_ids=[e.id for e in involved_entities] + [ws.player_entity_id],
            query=raw_input,
        )

        result = self._resolve_action(intent, ws, involved_entities, active_memory)
        self._apply_world_updates(ws, intent, result)
        self._apply_entity_updates(result.entity_updates, ws)
        ws.turn += 1
        self.storage.save_world_state(ws)

        consolidated = self.memory.consolidate_after_action(intent, result, ws)
        self._link_memories_to_entities(consolidated)

        return self.snapshot(result.narrative, intent=intent.action, active_memory=active_memory, resolution=result.resolution_meta)

    def snapshot(
        self,
        narrative: str,
        intent: str | None = None,
        active_memory: list | None = None,
        resolution: dict | None = None,
    ) -> dict:
        ws = self._require_world_state()
        entities = self.storage.list_entities()
        location = self.storage.get_entity(ws.current_location_id)
        inventory = [e for e in entities if e.id in ws.inventory_item_ids]
        npcs_here = [e for e in entities if e.type == "npc" and e.state.get("location_id") == ws.current_location_id]

        return {
            "narrative": narrative,
            "turn": ws.turn,
            "intent": intent,
            "world_state": {
                "current_location": location.name if location else ws.current_location_id,
                "inventory": [item.name for item in inventory],
                "active_conditions": ws.active_conditions,
                "npcs_here": [npc.name for npc in npcs_here],
            },
            "known_entities": [
                {"id": e.id, "name": e.name, "type": e.type, "state": e.state, "attributes": e.attributes}
                for e in entities
                if e.type in {"npc", "location", "item", "faction"}
            ],
            "ai_status": self.gm.get_status(),
            "resolution": resolution or {},
            "debug": {
                "ai": self.gm.get_status(),
                "memory": self.memory.debug_dump(),
                "active_memory": [m.content for m in (active_memory or [])],
                "world_state": {
                    "turn": ws.turn,
                    "location_id": ws.current_location_id,
                    "inventory_item_ids": ws.inventory_item_ids,
                    "npc_positions": ws.npc_positions,
                },
            },
        }

    def _resolve_action(self, intent: Intent, ws: WorldState, entities: list[Entity], active_memory: list) -> ActionResult:
        if intent.action == "move":
            return self._resolve_move(intent, ws)
        if intent.action == "take":
            return self._resolve_take(intent, ws)
        if intent.action == "observe":
            loc = self.storage.get_entity(ws.current_location_id)
            desc = (loc.attributes or {}).get("description", "No notable details.") if loc else "Unknown place"
            return ActionResult(
                success=True,
                narrative=f"You study {loc.name if loc else 'the area'}: {desc}",
                memory_candidates=[
                    {
                        "content": f"{loc.name if loc else ws.current_location_id} contains: {desc}",
                        "type": "fact",
                        "importance": 0.62,
                        "durability": 0.74,
                        "scope": 0.5,
                        "entity_ids": [ws.player_entity_id, ws.current_location_id],
                        "location_id": ws.current_location_id,
                    }
                ],
                resolution_meta={"source": "rules", "fallback_used": False},
            )

        scenario = get_scenario(str(ws.active_conditions.get("scenario_id", "")))
        return self.gm.resolve_complex_action(intent, ws, entities, active_memory, scenario)

    def _resolve_move(self, intent: Intent, ws: WorldState) -> ActionResult:
        if not intent.destination:
            return ActionResult(success=False, narrative="Move where?", resolution_meta={"source": "rules", "fallback_used": False})

        normalized = intent.destination.lower().replace(" ", "-")
        locations = [e for e in self.storage.list_entities() if e.type == "location"]
        match = next((loc for loc in locations if normalized in {loc.id.lower(), loc.name.lower().replace(" ", "-")}), None)

        if match is None:
            return ActionResult(success=False, narrative=f"No reachable location named '{intent.destination}'.", resolution_meta={"source": "rules", "fallback_used": False})

        ws.current_location_id = match.id
        return ActionResult(
            success=True,
            narrative=f"You travel to {match.name}.",
            memory_candidates=[
                {
                    "content": f"The player's current location is now {match.name}.",
                    "type": "state",
                    "importance": 0.8,
                    "durability": 0.82,
                    "scope": 0.7,
                    "entity_ids": [ws.player_entity_id, match.id],
                    "location_id": match.id,
                }
            ],
            resolution_meta={"source": "rules", "fallback_used": False},
        )

    def _resolve_take(self, intent: Intent, ws: WorldState) -> ActionResult:
        if not intent.target:
            return ActionResult(success=False, narrative="Take what?", resolution_meta={"source": "rules", "fallback_used": False})

        items = [e for e in self.storage.list_entities() if e.type == "item"]
        item = next((i for i in items if intent.target in i.name.lower() or intent.target == i.id.lower()), None)
        if item is None:
            return ActionResult(success=False, narrative=f"No item matches '{intent.target}'.", resolution_meta={"source": "rules", "fallback_used": False})

        item_loc = item.state.get("location_id")
        if item_loc != ws.current_location_id:
            return ActionResult(success=False, narrative=f"{item.name} is not here.", resolution_meta={"source": "rules", "fallback_used": False})

        ws.inventory_item_ids.append(item.id)
        item.state["holder_id"] = ws.player_entity_id
        item.state["location_id"] = None
        self.storage.upsert_entity(item)

        return ActionResult(
            success=True,
            narrative=f"You take the {item.name}.",
            memory_candidates=[
                {
                    "content": f"The player acquired {item.name} and now carries it.",
                    "type": "state",
                    "importance": 0.78,
                    "durability": 0.85,
                    "scope": 0.7,
                    "entity_ids": [ws.player_entity_id, item.id],
                    "location_id": ws.current_location_id,
                }
            ],
            resolution_meta={"source": "rules", "fallback_used": False},
        )

    def _apply_world_updates(self, ws: WorldState, intent: Intent, result: ActionResult) -> None:
        for key, value in result.world_updates.items():
            ws.active_conditions[key] = value
        ws.active_conditions["last_action"] = intent.raw
        ws.active_conditions["last_updated_at"] = int(time.time())

    def _apply_entity_updates(self, updates: list[dict], ws: WorldState) -> None:
        for update in updates:
            entity_id = update.get("entity_id")
            if not entity_id:
                continue
            entity = self.storage.get_entity(entity_id)
            if entity is None:
                continue

            for key, value in (update.get("state_updates") or {}).items():
                entity.state[key] = value

            for key, value in (update.get("relationship_updates") or {}).items():
                entity.relationships[key] = value

            new_position = update.get("position")
            if entity.type == "npc" and new_position:
                entity.state["location_id"] = new_position
                ws.npc_positions[entity.id] = new_position

            self.storage.upsert_entity(entity)

    def _find_involved_entities(self, intent: Intent, ws: WorldState) -> list[Entity]:
        entities = self.storage.list_entities()
        involved = []
        for e in entities:
            if intent.target and intent.target in e.name.lower():
                involved.append(e)
            if e.id == ws.current_location_id:
                involved.append(e)
            if e.type == "npc" and e.state.get("location_id") == ws.current_location_id:
                involved.append(e)
        return involved

    def _link_memories_to_entities(self, memories) -> None:
        for memory in memories:
            for entity_id in memory.entity_ids:
                entity = self.storage.get_entity(entity_id)
                if entity is None:
                    continue
                if memory.id not in entity.memory_links:
                    entity.memory_links.append(memory.id)
                    self.storage.upsert_entity(entity)

    def _require_world_state(self) -> WorldState:
        ws = self.storage.load_world_state()
        if ws is None:
            raise RuntimeError("No active world state")
        return ws

    def _location_name(self, location_id: str) -> str:
        loc = self.storage.get_entity(location_id)
        return loc.name if loc else location_id
