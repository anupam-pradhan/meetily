"""Local control API for the voice engine.

Listens on 127.0.0.1 only. Every request must carry the token the desktop app
generated at launch (header X-Engine-Token), so web pages or other local
programs can't drive the microphone.
"""

import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .engine import ACCENT_VOICES, VoiceEngine
from .presets import BUILTIN_PRESETS

MAX_BODY = 64 * 1024


def make_handler(engine: VoiceEngine, token: str, stop):
    class Handler(BaseHTTPRequestHandler):
        server_version = "VoiceEngine/1.0"

        def log_message(self, fmt, *args):  # keep stdout quiet
            pass

        def _send(self, code, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _authorised(self):
            given = self.headers.get("X-Engine-Token", "")
            if not hmac.compare_digest(given.encode(), token.encode()):
                self._send(401, {"error": "unauthorised"})
                return False
            return True

        def _body(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ValueError("request too large")
            if length == 0:
                return {}
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("body must be a JSON object")
            return data

        def do_GET(self):
            if not self._authorised():
                return
            path = self.path.split("?", 1)[0]
            if path == "/status":
                return self._send(200, engine.status())
            if path == "/devices":
                return self._send(200, engine.list_devices())
            if path == "/options":
                return self._send(
                    200,
                    {
                        "presets": [
                            {"id": p["id"], "name": p["name"], "emoji": p["emoji"], "description": p["description"]}
                            for p in BUILTIN_PRESETS
                        ],
                        "accent_voices": [{"id": k, "label": v["label"]} for k, v in ACCENT_VOICES.items()],
                    },
                )
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._authorised():
                return
            path = self.path.split("?", 1)[0]
            try:
                body = self._body()
                if path == "/config":
                    return self._send(200, {"config": engine.update_config(body)})
                if path == "/setup":
                    engine.start_setup(str(body.get("what", "")))
                    return self._send(202, {"started": True})
                if path == "/say":
                    engine.say(str(body.get("text", ""))[:600])
                    return self._send(200, {"ok": True})
                if path == "/shutdown":
                    self._send(200, {"ok": True})
                    threading.Thread(target=stop, daemon=True).start()
                    return None
            except (ValueError, RuntimeError) as exc:
                return self._send(400, {"error": str(exc)})
            except Exception as exc:  # pragma: no cover
                return self._send(500, {"error": str(exc)})
            return self._send(404, {"error": "not found"})

    return Handler


def serve(engine: VoiceEngine, port: int, token: str):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), None)

    def stop():
        engine.shutdown()
        httpd.shutdown()

    httpd.RequestHandlerClass = make_handler(engine, token, stop)
    engine.start()
    try:
        httpd.serve_forever(poll_interval=0.5)
    finally:
        engine.shutdown()
        httpd.server_close()
