# AI Text Adventure Engine (Memory-Driven)

A production-oriented, memory-driven text adventure engine that separates:

- **World State** (what is currently true)
- **Memory Objects** (what was observed, inferred, and learned over time)

It supports:

- Turn-based game engine loop
- Structured player intent parsing
- Dynamic memory extraction/consolidation
- Entity system (player, NPC, locations, items, factions)
- Hybrid action resolution (deterministic + AI GM)
- Targeted memory retrieval (not full-history prompts)
- SQLite persistence
- Standalone desktop UI (Tkinter)
- Initial scenario prompt and prebuilt scenarios

## Quickstart (desktop app)

```bash
python3 -m adventure.desktop
```

## Install dependencies

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## Build standalone executable

```bash
./scripts/build_executable.sh
```

Output executable:

- Linux/macOS: `dist/memory-adventure`
- Windows (if built on Windows): `dist/memory-adventure.exe`

## Optional web demo

```bash
python3 -m adventure.app
```

Open <http://127.0.0.1:8000>.

## Optional LLM integration

Set environment variables:

- `OPENAI_API_KEY`
- `OPENAI_MODEL` (optional, default `gpt-4.1-mini`)

Without an API key, the engine uses a deterministic fallback game master so the simulation still works.
