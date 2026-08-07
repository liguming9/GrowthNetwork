"""Local GrowthNetwork web server with visitor-session persistence.

The browser experience remains a static HTML Canvas application.  This small
standard-library server adds one deliberately narrow endpoint so a completed
pre-exhibition study can be recorded without introducing a framework or
changing the existing CSV/JSON pipeline.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest


PROJECT_ROOT = Path(__file__).resolve().parent
SESSION_LOG = PROJECT_ROOT / "web" / "data" / "visitor_sessions.jsonl"
MAX_REQUEST_BYTES = 256_000
EXHIBIT_IDS = {"Brain", "Eye", "Heart", "Lung"}
WRITE_LOCK = threading.Lock()
GITHUB_API_VERSION = "2022-11-28"
GITHUB_TIMEOUT_SECONDS = 15


class GitHubStorageError(RuntimeError):
    """Raised when a validated session cannot be stored in GitHub."""


@dataclass(frozen=True)
class GitHubStorageConfig:
    """Private-repository settings supplied only through server environment variables."""

    token: str
    owner: str
    repository: str
    branch: str = "main"


GITHUB_STORAGE: GitHubStorageConfig | None = None


def load_github_storage_config() -> GitHubStorageConfig | None:
    """Load optional remote storage without ever embedding the token in browser code."""

    values = {
        "token": os.environ.get("GITHUB_TOKEN", "").strip(),
        "owner": os.environ.get("GITHUB_OWNER", "").strip(),
        "repository": os.environ.get("GITHUB_DATA_REPO", "").strip(),
        "branch": os.environ.get("GITHUB_DATA_BRANCH", "main").strip() or "main",
    }
    configured_values = [values["token"], values["owner"], values["repository"]]
    if not any(configured_values):
        return None
    missing = [
        name
        for name in ("token", "owner", "repository")
        if not values[name]
    ]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Incomplete GitHub storage configuration: {joined}")
    safe_name = re.compile(r"^[A-Za-z0-9_.-]+$")
    if not safe_name.fullmatch(values["owner"]):
        raise ValueError("GITHUB_OWNER contains unsupported characters.")
    if not safe_name.fullmatch(values["repository"]):
        raise ValueError("GITHUB_DATA_REPO contains unsupported characters.")
    if not re.fullmatch(r"^[A-Za-z0-9_./-]+$", values["branch"]):
        raise ValueError("GITHUB_DATA_BRANCH contains unsupported characters.")
    return GitHubStorageConfig(**values)


def parse_browser_timestamp(value: Any, field_name: str) -> datetime:
    """Parse the browser's ISO-8601 timestamps and normalize them to UTC."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is missing or invalid.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field_name} is not a valid ISO-8601 timestamp.") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone.")
    return parsed.astimezone(timezone.utc)


def validate_session(payload: Any) -> dict[str, Any]:
    """Return a safe visitor-session object or raise ``ValueError``."""

    if not isinstance(payload, dict):
        raise ValueError("The request body must be a JSON object.")
    visitor_id = payload.get("visitorId")
    order = payload.get("order")
    dwell_by_node = payload.get("dwellByNode")
    events = payload.get("viewEvents")
    if not isinstance(visitor_id, str) or not re.fullmatch(r"V-[A-Z0-9]{6,64}", visitor_id):
        raise ValueError("visitorId is missing or invalid.")
    started_at = parse_browser_timestamp(payload.get("startedAt"), "startedAt")
    completed_at = parse_browser_timestamp(payload.get("completedAt"), "completedAt")
    if completed_at < started_at:
        raise ValueError("completedAt cannot precede startedAt.")
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


def serialize_session(payload: dict[str, Any]) -> str:
    """Create one stable representation for local and remote research records."""

    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def session_repository_path(payload: dict[str, Any], record: str) -> str:
    """Place each session in its own dated file to avoid concurrent-write conflicts."""

    completed_at = parse_browser_timestamp(payload["completedAt"], "completedAt")
    day = completed_at.strftime("%Y-%m-%d")
    timestamp = completed_at.strftime("%Y%m%dT%H%M%S%fZ")
    digest = hashlib.sha256(record.encode("utf-8")).hexdigest()[:12]
    return f"sessions/{day}/{timestamp}-{payload['visitorId']}-{digest}.json"


def github_headers(config: GitHubStorageConfig) -> dict[str, str]:
    """Return the minimum headers needed by the repository Contents API."""

    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {config.token}",
        "User-Agent": "GrowthNetwork-visitor-recorder/2.3.4",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }


def github_contents_url(config: GitHubStorageConfig, repository_path: str) -> str:
    owner = urlparse.quote(config.owner, safe="")
    repository = urlparse.quote(config.repository, safe="")
    path = urlparse.quote(repository_path, safe="/")
    return f"https://api.github.com/repos/{owner}/{repository}/contents/{path}"


def github_file_exists(config: GitHubStorageConfig, repository_path: str) -> bool:
    """Check only after a duplicate response, making browser retries idempotent."""

    url = github_contents_url(config, repository_path)
    branch = urlparse.quote(config.branch, safe="")
    request = urlrequest.Request(
        f"{url}?ref={branch}",
        headers=github_headers(config),
        method="GET",
    )
    try:
        with urlrequest.urlopen(request, timeout=GITHUB_TIMEOUT_SECONDS) as response:
            return response.status == HTTPStatus.OK
    except urlerror.HTTPError as error:
        if error.code == HTTPStatus.NOT_FOUND:
            return False
        raise GitHubStorageError(
            f"GitHub existence check returned HTTP {error.code}."
        ) from error
    except urlerror.URLError as error:
        raise GitHubStorageError("GitHub could not be reached for a duplicate check.") from error


def upload_session_to_github(
    config: GitHubStorageConfig,
    payload: dict[str, Any],
    record: str,
) -> str:
    """Upload a validated session to a private repository as an independent JSON file."""

    repository_path = session_repository_path(payload, record)
    body = json.dumps(
        {
            "message": f"Record visitor session {payload['visitorId']}",
            "content": base64.b64encode(record.encode("utf-8")).decode("ascii"),
            "branch": config.branch,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    request = urlrequest.Request(
        github_contents_url(config, repository_path),
        data=body,
        headers={**github_headers(config), "Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urlrequest.urlopen(request, timeout=GITHUB_TIMEOUT_SECONDS) as response:
            if response.status not in (HTTPStatus.OK, HTTPStatus.CREATED):
                raise GitHubStorageError(
                    f"GitHub upload returned unexpected HTTP {response.status}."
                )
    except urlerror.HTTPError as error:
        # A browser may retry after the first request succeeded. The content hash
        # in the filename makes an existing path proof of an identical record.
        if error.code == HTTPStatus.UNPROCESSABLE_ENTITY and github_file_exists(
            config, repository_path
        ):
            return repository_path
        raise GitHubStorageError(f"GitHub upload returned HTTP {error.code}.") from error
    except urlerror.URLError as error:
        raise GitHubStorageError("GitHub could not be reached.") from error
    return repository_path


class GrowthNetworkHandler(SimpleHTTPRequestHandler):
    """Serve the project and accept completed visitor-study records."""

    server_version = "GrowthNetworkHTTP/1.0"

    def do_GET(self) -> None:  # noqa: N802 - HTTP handler API name
        if self.path == "/api/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "remoteStorage": "github" if GITHUB_STORAGE else "local",
                },
            )
            return
        super().do_GET()

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
        record = serialize_session(payload)
        with WRITE_LOCK:
            with SESSION_LOG.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(record)
                stream.write("\n")

        if GITHUB_STORAGE is None:
            self._send_json(
                HTTPStatus.CREATED,
                {"ok": True, "storage": "local"},
            )
            return

        try:
            upload_session_to_github(GITHUB_STORAGE, payload, record)
        except GitHubStorageError as error:
            # The local append above provides a best-effort backup. Render's
            # application logs retain this message without revealing the token.
            print(f"GitHub visitor storage failed: {error}")
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {
                    "ok": False,
                    "localBackup": True,
                    "error": "The private visitor-data repository was unavailable.",
                },
            )
            return

        self._send_json(
            HTTPStatus.CREATED,
            {"ok": True, "storage": "github"},
        )

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
    global GITHUB_STORAGE

    arguments = parse_arguments()
    try:
        GITHUB_STORAGE = load_github_storage_config()
    except ValueError as error:
        raise SystemExit(f"Configuration error: {error}") from error
    handler = partial(GrowthNetworkHandler, directory=str(PROJECT_ROOT))
    server = ThreadingHTTPServer((arguments.host, arguments.port), handler)
    print(f"GrowthNetwork: http://{arguments.host}:{arguments.port}/web/")
    print(f"Visitor records: {SESSION_LOG}")
    storage_label = (
        f"GitHub private repository {GITHUB_STORAGE.owner}/{GITHUB_STORAGE.repository}"
        if GITHUB_STORAGE
        else "local JSONL only (GitHub environment variables are not configured)"
    )
    print(f"Remote storage: {storage_label}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
