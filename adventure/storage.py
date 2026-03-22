from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .models import Entity, MemoryObject, WorldState


class Storage:
    def __init__(self, db_path: str = "game.db") -> None:
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                attributes_json TEXT NOT NULL,
                state_json TEXT NOT NULL,
                relationships_json TEXT NOT NULL,
                memory_links_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                type TEXT NOT NULL,
                confidence REAL NOT NULL,
                importance REAL NOT NULL,
                durability REAL NOT NULL,
                scope REAL NOT NULL,
                state TEXT NOT NULL,
                entity_ids_json TEXT NOT NULL,
                location_id TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                last_accessed_at INTEGER,
                activation_count INTEGER NOT NULL,
                user_facing INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS world_state (
                singleton_key INTEGER PRIMARY KEY CHECK (singleton_key = 1),
                turn INTEGER NOT NULL,
                current_location_id TEXT NOT NULL,
                player_entity_id TEXT NOT NULL,
                inventory_item_ids_json TEXT NOT NULL,
                npc_positions_json TEXT NOT NULL,
                active_conditions_json TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def clear_all(self) -> None:
        self.conn.executescript(
            "DELETE FROM entities; DELETE FROM memories; DELETE FROM world_state;"
        )
        self.conn.commit()

    def upsert_entity(self, entity: Entity) -> None:
        self.conn.execute(
            """
            INSERT INTO entities (id, name, type, attributes_json, state_json, relationships_json, memory_links_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                type = excluded.type,
                attributes_json = excluded.attributes_json,
                state_json = excluded.state_json,
                relationships_json = excluded.relationships_json,
                memory_links_json = excluded.memory_links_json
            """,
            (
                entity.id,
                entity.name,
                entity.type,
                json.dumps(entity.attributes),
                json.dumps(entity.state),
                json.dumps(entity.relationships),
                json.dumps(entity.memory_links),
            ),
        )
        self.conn.commit()

    def upsert_entities(self, entities: Iterable[Entity]) -> None:
        for entity in entities:
            self.upsert_entity(entity)

    def list_entities(self) -> list[Entity]:
        rows = self.conn.execute("SELECT * FROM entities").fetchall()
        return [
            Entity(
                id=row["id"],
                name=row["name"],
                type=row["type"],
                attributes=json.loads(row["attributes_json"]),
                state=json.loads(row["state_json"]),
                relationships=json.loads(row["relationships_json"]),
                memory_links=json.loads(row["memory_links_json"]),
            )
            for row in rows
        ]

    def get_entity(self, entity_id: str) -> Entity | None:
        row = self.conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
        if row is None:
            return None
        return Entity(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            attributes=json.loads(row["attributes_json"]),
            state=json.loads(row["state_json"]),
            relationships=json.loads(row["relationships_json"]),
            memory_links=json.loads(row["memory_links_json"]),
        )

    def upsert_memory(self, memory: MemoryObject) -> None:
        self.conn.execute(
            """
            INSERT INTO memories (
                id, content, type, confidence, importance, durability, scope, state,
                entity_ids_json, location_id, created_at, updated_at, last_accessed_at,
                activation_count, user_facing
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                content = excluded.content,
                type = excluded.type,
                confidence = excluded.confidence,
                importance = excluded.importance,
                durability = excluded.durability,
                scope = excluded.scope,
                state = excluded.state,
                entity_ids_json = excluded.entity_ids_json,
                location_id = excluded.location_id,
                updated_at = excluded.updated_at,
                last_accessed_at = excluded.last_accessed_at,
                activation_count = excluded.activation_count,
                user_facing = excluded.user_facing
            """,
            (
                memory.id,
                memory.content,
                memory.type,
                memory.confidence,
                memory.importance,
                memory.durability,
                memory.scope,
                memory.state,
                json.dumps(memory.entity_ids),
                memory.location_id,
                memory.created_at,
                memory.updated_at,
                memory.last_accessed_at,
                memory.activation_count,
                int(memory.user_facing),
            ),
        )
        self.conn.commit()

    def list_memories(self) -> list[MemoryObject]:
        rows = self.conn.execute("SELECT * FROM memories").fetchall()
        return [self._row_to_memory(row) for row in rows]

    def find_memories_by_entity(self, entity_id: str) -> list[MemoryObject]:
        rows = self.conn.execute("SELECT * FROM memories WHERE entity_ids_json LIKE ?", (f'%"{entity_id}"%',)).fetchall()
        return [self._row_to_memory(row) for row in rows]

    def find_memories_by_location(self, location_id: str) -> list[MemoryObject]:
        rows = self.conn.execute("SELECT * FROM memories WHERE location_id = ?", (location_id,)).fetchall()
        return [self._row_to_memory(row) for row in rows]

    def _row_to_memory(self, row: sqlite3.Row) -> MemoryObject:
        return MemoryObject(
            id=row["id"],
            content=row["content"],
            type=row["type"],
            confidence=row["confidence"],
            importance=row["importance"],
            durability=row["durability"],
            scope=row["scope"],
            state=row["state"],
            entity_ids=json.loads(row["entity_ids_json"]),
            location_id=row["location_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_accessed_at=row["last_accessed_at"],
            activation_count=row["activation_count"],
            user_facing=bool(row["user_facing"]),
        )

    def save_world_state(self, ws: WorldState) -> None:
        self.conn.execute(
            """
            INSERT INTO world_state (
                singleton_key, turn, current_location_id, player_entity_id,
                inventory_item_ids_json, npc_positions_json, active_conditions_json
            )
            VALUES (1, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(singleton_key) DO UPDATE SET
                turn = excluded.turn,
                current_location_id = excluded.current_location_id,
                player_entity_id = excluded.player_entity_id,
                inventory_item_ids_json = excluded.inventory_item_ids_json,
                npc_positions_json = excluded.npc_positions_json,
                active_conditions_json = excluded.active_conditions_json
            """,
            (
                ws.turn,
                ws.current_location_id,
                ws.player_entity_id,
                json.dumps(ws.inventory_item_ids),
                json.dumps(ws.npc_positions),
                json.dumps(ws.active_conditions),
            ),
        )
        self.conn.commit()

    def load_world_state(self) -> WorldState | None:
        row = self.conn.execute("SELECT * FROM world_state WHERE singleton_key = 1").fetchone()
        if row is None:
            return None
        return WorldState(
            turn=row["turn"],
            current_location_id=row["current_location_id"],
            player_entity_id=row["player_entity_id"],
            inventory_item_ids=json.loads(row["inventory_item_ids_json"]),
            npc_positions=json.loads(row["npc_positions_json"]),
            active_conditions=json.loads(row["active_conditions_json"]),
        )
