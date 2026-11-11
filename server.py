"""
coolrack server - runs the engine and shows it in your browser.

Run it:   python3 server.py
Then open http://localhost:8000

Uses only Python's standard library, so there is nothing to pip install.

Three jobs:
  1. A background thread steps the engine forward in real time.
  2. GET /stream sends the rack's state to the page four times a second.
  3. POST /action lets the page's buttons change things (start a job,
     fail the pump...).
"""

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from engine import Rack

PORT = 8000
HERE = os.path.dirname(os.path.abspath(__file__))

rack = Rack()
speed = {"value": 1.0}  # 1 = real time, 4 = four times faster


def run_engine():
    """Step the simulation forward to keep up with the clock."""
    tick = 0.05  # seconds of real time between updates
    while True:
        time.sleep(tick)
        with rack.lock:
            remaining = tick * speed["value"]
            while remaining > 1e-9:
                dt = min(0.05, remaining)  # small steps keep the maths stable
                rack.step(dt)
                remaining -= dt


def apply_action(action):
    kind = action.get("type")
    with rack.lock:
        if kind == "job":
            rack.set_job(action["server"], bool(action["on"]))
        elif kind == "block":
            rack.set_blocked(int(action["server"]), bool(action["on"]))
        elif kind == "pump_fail":
            rack.set_pump_failed(bool(action["on"]))
        elif kind == "pump_speed":
            rack.set_pump_speed(action["value"])
        elif kind == "auto":
            rack.set_auto(bool(action["on"]))
        elif kind == "target":
            rack.set_target(action["value"])
        elif kind == "speed":
            speed["value"] = max(1.0, min(8.0, float(action["value"])))
        elif kind == "reset":
            rack.reset()
        else:
            return False
    return True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # keep the terminal quiet

    def do_GET(self):
        if self.path == "/":
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                while True:
                    with rack.lock:
                        state = rack.snapshot()
                    state["speed"] = speed["value"]
                    self.wfile.write(("data: %s\n\n" % json.dumps(state)).encode())
                    self.wfile.flush()
                    time.sleep(0.25)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the browser tab was closed
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/action":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            ok = apply_action(json.loads(self.rfile.read(length) or b"{}"))
        except (ValueError, KeyError, TypeError):
            ok = False
        self.send_response(200 if ok else 400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": ok}).encode())


if __name__ == "__main__":
    threading.Thread(target=run_engine, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    print("coolrack running at http://localhost:%d  (Ctrl+C to stop)" % PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
