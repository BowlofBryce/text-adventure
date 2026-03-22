from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .engine import GameEngine
from .storage import Storage


class AdventureDesktopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Memory Adventure Engine")
        self.root.geometry("1200x760")

        db_path = Path.cwd() / "game.db"
        self.storage = Storage(str(db_path))
        self.engine = GameEngine(self.storage)

        self._build_ui()
        self._render_state({
            "narrative": "Welcome. Start a scenario to begin.",
            "world_state": {"current_location": "N/A", "inventory": []},
            "known_entities": [],
            "debug": {},
        })

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.rowconfigure(1, weight=1)

        ttk.Label(left, text="AI Text Adventure Engine", font=("TkDefaultFont", 14, "bold")).grid(row=0, column=0, sticky="w")

        self.log = tk.Text(left, wrap="word", state="disabled", height=25)
        self.log.grid(row=1, column=0, sticky="nsew", pady=(8, 8))

        controls = ttk.LabelFrame(left, text="Scenario Setup", padding=8)
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Scenario:").grid(row=0, column=0, sticky="w")
        self.scenario = ttk.Combobox(controls, values=["fallen-city", "orbit-station"], state="readonly")
        self.scenario.set("fallen-city")
        self.scenario.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(controls, text="Initial prompt:").grid(row=1, column=0, sticky="nw", pady=(8, 0))
        self.initial_prompt = tk.Text(controls, height=4, wrap="word")
        self.initial_prompt.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        ttk.Button(controls, text="Start New Game", command=self._new_game).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        actions = ttk.LabelFrame(left, text="Action", padding=8)
        actions.grid(row=3, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)

        self.action_var = tk.StringVar()
        self.action_entry = ttk.Entry(actions, textvariable=self.action_var)
        self.action_entry.grid(row=0, column=0, sticky="ew")
        self.action_entry.bind("<Return>", lambda _e: self._submit_action())
        ttk.Button(actions, text="Submit", command=self._submit_action).grid(row=0, column=1, padx=(8, 0))

        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(3, weight=1)

        ws = ttk.LabelFrame(right, text="World", padding=8)
        ws.grid(row=0, column=0, sticky="ew")
        self.location_var = tk.StringVar(value="Location: N/A")
        self.inventory_var = tk.StringVar(value="Inventory: (empty)")
        ttk.Label(ws, textvariable=self.location_var).pack(anchor="w")
        ttk.Label(ws, textvariable=self.inventory_var).pack(anchor="w")

        entities_frame = ttk.LabelFrame(right, text="Known Entities", padding=8)
        entities_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 8))
        entities_frame.rowconfigure(0, weight=1)
        self.entities_list = tk.Listbox(entities_frame, height=10)
        self.entities_list.grid(row=0, column=0, sticky="nsew")

        debug_frame = ttk.LabelFrame(right, text="Debug", padding=8)
        debug_frame.grid(row=3, column=0, sticky="nsew")
        debug_frame.rowconfigure(0, weight=1)
        self.debug_text = tk.Text(debug_frame, wrap="word", state="disabled")
        self.debug_text.grid(row=0, column=0, sticky="nsew")

    def _append_log(self, label: str, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("1.0", f"{label}: {text}\n\n")
        self.log.configure(state="disabled")

    def _new_game(self) -> None:
        scenario_id = self.scenario.get()
        initial_prompt = self.initial_prompt.get("1.0", "end").strip()
        state = self.engine.new_game(scenario_id, initial_prompt)
        self._render_state(state)

    def _submit_action(self) -> None:
        action = self.action_var.get().strip()
        if not action:
            return
        self._append_log("Player", action)
        self.action_var.set("")
        try:
            state = self.engine.process_turn(action)
            self._render_state(state)
        except Exception as exc:
            self._append_log("Error", str(exc))

    def _render_state(self, state: dict) -> None:
        narrative = state.get("narrative")
        if narrative:
            self._append_log("Engine", narrative)

        world_state = state.get("world_state", {})
        self.location_var.set(f"Location: {world_state.get('current_location', 'Unknown')}")
        inv = world_state.get("inventory", [])
        self.inventory_var.set(f"Inventory: {', '.join(inv) if inv else '(empty)'}")

        self.entities_list.delete(0, tk.END)
        for entity in state.get("known_entities", []):
            self.entities_list.insert(tk.END, f"{entity['name']} ({entity['type']})")

        self.debug_text.configure(state="normal")
        self.debug_text.delete("1.0", tk.END)
        self.debug_text.insert("1.0", json.dumps(state.get("debug", {}), indent=2))
        self.debug_text.configure(state="disabled")

    def _on_close(self) -> None:
        self.storage.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    AdventureDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
