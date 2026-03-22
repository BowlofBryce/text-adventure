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
            state={"known_info": [initial_prompt] if initial_prompt else []},
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
                    state={"location_id": npc.get("location"), "attitude": "neutral"},
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
            active_conditions={"scenario_id": scenario.id},
        )
        self.storage.save_world_state(ws)

        self.memory.consolidate_after_action(
            Intent(raw="start", action="start"),
            ActionResult(
                success=True,
                narrative=f"Scenario '{scenario.name}' begins. {scenario.description}",
                memory_candidates=[
                    {
                        "content": f"Scenario initialized: {scenario.name}",
                        "type": "fact",
                        "importance": 0.9,
                        "durability": 0.95,
                        "scope": 0.9,
                        "entity_ids": [player.id],
                        "location_id": ws.current_location_id,
                    },
                    {
                        "content": f"Initial player scenario prompt: {initial_prompt}" if initial_prompt else "Player started with no explicit scenario prompt.",
                        "type": "signal",
                        "importance": 0.7,
                        "durability": 0.8,
                        "scope": 0.7,
                        "entity_ids": [player.id],
                        "location_id": ws.current_location_id,
                    },
                ],
            ),
            ws,
        )

        return self.snapshot("Game initialized.")

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
        ws.turn += 1
        self.storage.save_world_state(ws)

        consolidated = self.memory.consolidate_after_action(intent, result, ws)
        self._link_memories_to_entities(consolidated)

        return self.snapshot(result.narrative, intent=intent.action, active_memory=active_memory)

    def snapshot(self, narrative: str, intent: str | None = None, active_memory: list | None = None) -> dict:
        ws = self._require_world_state()
        entities = self.storage.list_entities()
        location = self.storage.get_entity(ws.current_location_id)
        inventory = [e for e in entities if e.id in ws.inventory_item_ids]

        return {
            "narrative": narrative,
            "turn": ws.turn,
            "intent": intent,
            "world_state": {
                "current_location": location.name if location else ws.current_location_id,
                "inventory": [item.name for item in inventory],
                "active_conditions": ws.active_conditions,
            },
            "known_entities": [
                {"id": e.id, "name": e.name, "type": e.type}
                for e in entities
                if e.type in {"npc", "location", "item", "faction"}
            ],
            "debug": {
                "memory": self.memory.debug_dump(),
                "active_memory": [m.content for m in (active_memory or [])],
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
                narrative=f"You observe {loc.name if loc else 'the area'}: {desc}",
                memory_candidates=[
                    {
                        "content": f"Player examined location {ws.current_location_id}.",
                        "type": "event",
                        "importance": 0.35,
                        "durability": 0.4,
                        "scope": 0.2,
                        "entity_ids": [ws.player_entity_id, ws.current_location_id],
                        "location_id": ws.current_location_id,
                    }
                ],
            )
        return self.gm.resolve_complex_action(intent, ws, entities, active_memory)

    def _resolve_move(self, intent: Intent, ws: WorldState) -> ActionResult:
        if not intent.destination:
            return ActionResult(success=False, narrative="Move where?")

        normalized = intent.destination.lower().replace(" ", "-")
        locations = [e for e in self.storage.list_entities() if e.type == "location"]
        match = next((loc for loc in locations if normalized in {loc.id.lower(), loc.name.lower().replace(" ", "-")}), None)

        if match is None:
            return ActionResult(success=False, narrative=f"No reachable location named '{intent.destination}'.")

        ws.current_location_id = match.id
        return ActionResult(
            success=True,
            narrative=f"You travel to {match.name}.",
            memory_candidates=[
                {
                    "content": f"Player moved to {match.name}.",
                    "type": "state",
                    "importance": 0.65,
                    "durability": 0.7,
                    "scope": 0.4,
                    "entity_ids": [ws.player_entity_id, match.id],
                    "location_id": match.id,
                }
            ],
        )

    def _resolve_take(self, intent: Intent, ws: WorldState) -> ActionResult:
        if not intent.target:
            return ActionResult(success=False, narrative="Take what?")

        items = [e for e in self.storage.list_entities() if e.type == "item"]
        item = next((i for i in items if intent.target in i.name.lower() or intent.target == i.id.lower()), None)
        if item is None:
            return ActionResult(success=False, narrative=f"No item matches '{intent.target}'.")

        item_loc = item.state.get("location_id")
        if item_loc != ws.current_location_id:
            return ActionResult(success=False, narrative=f"{item.name} is not here.")

        ws.inventory_item_ids.append(item.id)
        item.state["holder_id"] = ws.player_entity_id
        item.state["location_id"] = None
        self.storage.upsert_entity(item)

        return ActionResult(
            success=True,
            narrative=f"You take the {item.name}.",
            memory_candidates=[
                {
                    "content": f"Player acquired {item.name}.",
                    "type": "event",
                    "importance": 0.7,
                    "durability": 0.75,
                    "scope": 0.5,
                    "entity_ids": [ws.player_entity_id, item.id],
                    "location_id": ws.current_location_id,
                }
            ],
        )

    def _apply_world_updates(self, ws: WorldState, intent: Intent, result: ActionResult) -> None:
        for key, value in result.world_updates.items():
            ws.active_conditions[key] = value
        ws.active_conditions["last_action"] = intent.raw
        ws.active_conditions["last_updated_at"] = int(time.time())

    def _find_involved_entities(self, intent: Intent, ws: WorldState) -> list[Entity]:
        entities = self.storage.list_entities()
        involved = []
        for e in entities:
            if intent.target and intent.target in e.name.lower():
                involved.append(e)
            if e.id == ws.current_location_id:
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
            raise RuntimeError("No world state exists. Start a new game first.")
        return ws
