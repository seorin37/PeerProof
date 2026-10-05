"""Local, single-user profile editor; run only on the loopback interface."""
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

from .builder import build_business_profile
from .schema import GROUPS, OBSERVATION_FIELDS


class ProfileStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()

    def path(self, identifier):
        if not re.fullmatch(r"[0-9a-f]{32}", identifier):
            raise ValueError("프로필 ID가 올바르지 않습니다.")
        return self.directory / f"{identifier}.json"

    def get(self, identifier):
        return json.loads(self.path(identifier).read_text(encoding="utf-8"))

    def list(self):
        return [self.get(path.stem) for path in sorted(self.directory.glob("*.json"))
                if re.fullmatch(r"[0-9a-f]{32}", path.stem)]

    def save(self, payload, identifier=None):
        profile = build_business_profile(payload)
        with self.lock:
            if identifier is not None:
                self.get(identifier)  # An update must refer to an existing file.
            identifier = identifier or uuid.uuid4().hex
            profile["id"] = identifier
            profile["updated_at"] = datetime.now(timezone.utc).isoformat()
            descriptor, temporary = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                    json.dump(profile, output, ensure_ascii=False, indent=2, allow_nan=False)
                os.replace(temporary, self.path(identifier))
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return profile


def create_server(directory, port=8501):
    store = ProfileStore(directory)
    page = Path(__file__).with_name("editor.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, data, html=False):
            raw = data if html else json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8" if html else "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            try:
                if self.path == "/":
                    self.reply(200, page, html=True)
                elif self.path == "/api/schema":
                    self.reply(200, {"groups": GROUPS, "observation_fields": OBSERVATION_FIELDS})
                elif self.path == "/api/profiles":
                    self.reply(200, store.list())
                elif self.path.startswith("/api/profiles/"):
                    self.reply(200, store.get(self.path.removeprefix("/api/profiles/")))
                else:
                    self.reply(404, {"error": "페이지를 찾을 수 없습니다."})
            except FileNotFoundError:
                self.reply(404, {"error": "저장된 프로필을 찾을 수 없습니다."})
            except ValueError as error:
                self.reply(400, {"error": str(error)})

        def do_POST(self):
            self.write_profile()

        def do_PUT(self):
            self.write_profile()

        def write_profile(self):
            # Reject cross-site writes to the local editor.
            origin = self.headers.get("Origin")
            expected = f"http://127.0.0.1:{self.server.server_port}"
            if origin and origin not in (expected, f"http://localhost:{self.server.server_port}"):
                self.reply(403, {"error": "다른 사이트의 저장 요청은 허용되지 않습니다."})
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.reply(415, {"error": "JSON 요청만 지원합니다."})
                return
            try:
                identifier = None
                if self.command == "POST" and self.path == "/api/profiles":
                    pass
                elif self.command == "PUT" and self.path.startswith("/api/profiles/"):
                    identifier = self.path.removeprefix("/api/profiles/")
                else:
                    self.reply(404, {"error": "저장 경로가 올바르지 않습니다."})
                    return
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1048576:
                    raise ValueError("입력 데이터는 1MB 이하여야 합니다.")
                payload = json.loads(self.rfile.read(length))
                self.reply(201 if identifier is None else 200, store.save(payload, identifier))
            except FileNotFoundError:
                self.reply(404, {"error": "수정할 프로필을 찾을 수 없습니다."})
            except (ValueError, UnicodeError) as error:
                self.reply(400, {"error": str(error)})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
