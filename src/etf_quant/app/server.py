from __future__ import annotations

import argparse
import json
import mimetypes
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from etf_quant.app.service import LocalAppService


STATIC_DIR = Path(__file__).with_name("static")


class AppRequestHandler(BaseHTTPRequestHandler):
    service: LocalAppService

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        parsed = urlparse(self.path)
        if parsed.path == "/api/bootstrap":
            self._send_json(self.service.bootstrap())
            return
        if parsed.path == "/api/positions":
            config_path = self._query_param(parsed.query, "config")
            self._send_json(self.service.get_positions(config_path))
            return
        self._send_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802 - stdlib API
        try:
            payload = self._read_json()
            if self.path == "/api/positions":
                self._send_json(self.service.save_positions(payload))
                return
            if self.path == "/api/state":
                self._send_json(self.service.save_state(payload))
                return
            if self.path == "/api/plan":
                self._send_json(self.service.generate_plan(payload))
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
        except Exception as exc:  # noqa: BLE001 - keep local app errors visible.
            self._send_json({"error": str(exc), "traceback": traceback.format_exc()}, status=500)

    def log_message(self, fmt: str, *args: object) -> None:
        print("[etf-app] " + fmt % args)

    def _send_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in ("", "/") else request_path.lstrip("/")
        path = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in path.parents and path != STATIC_DIR.resolve():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        payload = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, data: dict | list, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    @staticmethod
    def _query_param(query: str, key: str) -> str | None:
        for item in query.split("&"):
            if not item:
                continue
            name, _, value = item.partition("=")
            if name == key:
                from urllib.parse import unquote_plus

                return unquote_plus(value)
        return None


def run_server(host: str, port: int, root: Path, open_browser: bool = False) -> None:
    AppRequestHandler.service = LocalAppService(root=root)
    httpd = ThreadingHTTPServer((host, port), AppRequestHandler)
    url = f"http://{host}:{port}"
    print(f"ETF Quant local app: {url}")
    if open_browser:
        webbrowser.open(url)
    httpd.serve_forever()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the ETF Quant personal local app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--root", default=".")
    parser.add_argument("--open", action="store_true", help="open the app in the default browser")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_server(args.host, args.port, Path(args.root).resolve(), open_browser=args.open)


if __name__ == "__main__":
    main()

