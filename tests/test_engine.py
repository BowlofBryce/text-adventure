import tempfile
import unittest
from pathlib import Path

from adventure.engine import GameEngine
from adventure.storage import Storage


class EngineTest(unittest.TestCase):
    def test_new_game_and_turn_updates_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            storage = Storage(str(db))
            engine = GameEngine(storage)

            state = engine.new_game("fallen-city", "I seek the old relic")
            self.assertIn("world_state", state)

            turn1 = engine.process_turn("look")
            self.assertIn("narrative", turn1)

            turn2 = engine.process_turn("take rust key")
            self.assertIn("Rust Key", turn2["world_state"]["inventory"])

            all_memories = storage.list_memories()
            self.assertGreaterEqual(len(all_memories), 3)
            storage.close()


if __name__ == "__main__":
    unittest.main()
