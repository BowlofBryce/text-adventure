from __future__ import annotations

from .models import Scenario


PREBUILT_SCENARIOS: list[Scenario] = [
    Scenario(
        id="fallen-city",
        name="Fallen City",
        description="A once-great city collapsed into faction warfare and hidden relic markets.",
        world_seed={
            "start_location": "old-gate",
            "locations": [
                {"id": "old-gate", "name": "Old Gate", "desc": "A cracked gate watched by suspicious guards."},
                {"id": "bazaar", "name": "Ember Bazaar", "desc": "Trade stalls and rumor brokers."},
            ],
            "npcs": [
                {"id": "captain-iora", "name": "Captain Iora", "location": "old-gate", "faction": "wardens"},
                {"id": "merchant-vel", "name": "Vel", "location": "bazaar", "faction": "traders"},
            ],
            "items": [
                {"id": "rust-key", "name": "Rust Key", "location": "old-gate"},
            ],
            "factions": [
                {"id": "wardens", "name": "Wardens"},
                {"id": "traders", "name": "Caravan Traders"},
            ],
        },
    ),
    Scenario(
        id="orbit-station",
        name="Orbit Station Blackout",
        description="A deep-space station has gone dark and everyone suspects sabotage.",
        world_seed={
            "start_location": "dock-alpha",
            "locations": [
                {"id": "dock-alpha", "name": "Dock Alpha", "desc": "Dim emergency lights flicker."},
                {"id": "reactor-core", "name": "Reactor Core", "desc": "A humming chamber in unstable mode."},
            ],
            "npcs": [
                {"id": "chief-nara", "name": "Chief Nara", "location": "reactor-core", "faction": "crew"},
            ],
            "items": [
                {"id": "plasma-cutter", "name": "Plasma Cutter", "location": "dock-alpha"},
            ],
            "factions": [
                {"id": "crew", "name": "Station Crew"},
            ],
        },
    ),
]


def get_scenario(scenario_id: str) -> Scenario | None:
    return next((s for s in PREBUILT_SCENARIOS if s.id == scenario_id), None)
