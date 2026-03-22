from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .engine import GameEngine
from .storage import Storage

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

storage = Storage(db_path=str(ROOT.parent / "game.db"))
engine = GameEngine(storage)


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else b"{}"
        return json.loads(body.decode("utf-8"))

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            html = (STATIC / "index.html").read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return
        if self.path == "/app.js":
            js = (STATIC / "app.js").read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(js)))
            self.end_headers()
            self.wfile.write(js)
            return
        if self.path == "/state":
            try:
                snapshot = engine.snapshot("State loaded.")
            except RuntimeError:
                snapshot = {"narrative": "No active game. Start a scenario.", "world_state": {}, "known_entities": [], "debug": {}}
            self._send_json(snapshot)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        if self.path == "/new-game":
            body = self._read_json()
            scenario_id = body.get("scenarioId", "fallen-city")
            initial_prompt = body.get("initialPrompt", "")
            try:
                snapshot = engine.new_game(scenario_id=scenario_id, initial_prompt=initial_prompt)
                self._send_json(snapshot)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)
            return
        if self.path == "/action":
            body = self._read_json()
            action = body.get("action", "")
            try:
                snapshot = engine.process_turn(action)
                self._send_json(snapshot)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("Text adventure engine running at http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        storage.close()


if __name__ == "__main__":
    main()
