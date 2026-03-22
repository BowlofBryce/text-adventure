from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

MemoryType = Literal["fact", "event", "state", "relationship", "rule", "signal"]
MemoryState = Literal["active", "superseded", "contradicted", "archived"]
EntityType = Literal["player", "npc", "location", "item", "faction"]


@dataclass
class Entity:
    id: str
    name: str
    type: EntityType
    attributes: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    relationships: dict[str, Any] = field(default_factory=dict)
    memory_links: list[str] = field(default_factory=list)


@dataclass
class MemoryObject:
    id: str
    content: str
    type: MemoryType
    confidence: float
    importance: float
    durability: float
    scope: float
    state: MemoryState
    entity_ids: list[str] = field(default_factory=list)
    location_id: str | None = None
    created_at: int = 0
    updated_at: int = 0
    last_accessed_at: int | None = None
    activation_count: int = 0
    user_facing: bool = True


@dataclass
class WorldState:
    turn: int
    current_location_id: str
    player_entity_id: str
    inventory_item_ids: list[str] = field(default_factory=list)
    npc_positions: dict[str, str] = field(default_factory=dict)
    active_conditions: dict[str, Any] = field(default_factory=dict)


@dataclass
class Intent:
    raw: str
    action: str
    target: str | None = None
    tool: str | None = None
    destination: str | None = None
    dialogue: str | None = None
    modifiers: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    success: bool
    narrative: str
    world_updates: dict[str, Any] = field(default_factory=dict)
    entity_updates: list[dict[str, Any]] = field(default_factory=list)
    memory_candidates: list[dict[str, Any]] = field(default_factory=list)
    resolution_meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Scenario:
    id: str
    name: str
    description: str
    world_seed: dict[str, Any]
