"""Local GrowthNetwork web server with visitor-session persistence.

The browser experience remains a static HTML Canvas application.  This small
standard-library server adds one deliberately narrow endpoint so a completed
pre-exhibition study can be recorded without introducing a framework or
changing the existing CSV/JSON pipeline.
"""

from __future__ import annotations

import argparse
import json
import threading
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
SESSION_LOG = PROJECT_ROOT / "web" / "data" / "visitor_sessions.jsonl"
MAX_REQUEST_BYTES = 256_000
EXHIBIT_IDS = {"Brain", "Eye", "Heart", "Lung"}
WRITE_LOCK = threading.Lock()


def validate_session(payload: Any) -> dict[str, Any]:
    """Return a safe visitor-session object or raise ``ValueError``."""

    if not isinstance(payload, dict):
        raise ValueError("The request body must be a JSON object.")
    visitor_id = payload.get("visitorId")
    order = payload.get("order")
    dwell_by_node = payload.get("dwellByNode")
    events = payload.get("viewEvents")
    if not isinstance(visitor_id, str) or not visitor_id.startswith("V-"):
        raise ValueError("visitorId is missing or invalid.")
    if not isinstance(order, list) or len(order) != 4 or set(order) != EXHIBIT_IDS:
        raise ValueError("order must contain each exhibit exactly once.")
    if not isinstance(dwell_by_node, dict) or set(dwell_by_node) != EXHIBIT_IDS:
        raise ValueError("dwellByNode must contain all four exhibits.")
    for node_id, seconds in dwell_by_node.items():
        if node_id not in EXHIBIT_IDS or not isinstance(seconds, (int, float)):
            raise ValueError("Every dwell value must be numeric.")
        if not 0 <= float(seconds) <= 86_400:
            raise ValueError("A dwell value is outside the accepted range.")
    if not isinstance(events, list) or len(events) < 4:
        raise ValueError("At least four view events are required.")
    return payload


class GrowthNetworkHandler(SimpleHTTPRequestHandler):
    """Serve the project and accept completed visitor-study records."""

    server_version = "GrowthNetworkHTTP/1.0"

    def do_POST(self) -> None:  # noqa: N802 - HTTP handler API name
        if self.path != "/api/visitor-session":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown API endpoint")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid Content-Length")
            return
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Invalid request size")
            return

        try:
            raw_body = self.rfile.read(length)
            payload = validate_session(json.loads(raw_body.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(error)})
            return

        SESSION_LOG.parent.mkdir(parents=True, exist_ok=True)
        record = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with WRITE_LOCK:
            with SESSION_LOG.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(record)
                stream.write("\n")
        self._send_json(HTTPStatus.CREATED, {"ok": True})

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Interface to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    handler = partial(GrowthNetworkHandler, directory=str(PROJECT_ROOT))
    server = ThreadingHTTPServer((arguments.host, arguments.port), handler)
    print(f"GrowthNetwork: http://{arguments.host}:{arguments.port}/web/")
    print(f"Visitor records: {SESSION_LOG}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
