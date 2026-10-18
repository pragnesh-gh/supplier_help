"""Loopback-only HTTP API and static UI; no repository or secret file serving."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import urllib.parse

from .core import ROOT, OpenRouter, ResearchService, Store, markdown_report, read_environment

MAX_BODY = 16 * 1024
WEB = ROOT / "research_agent/web"


def make_handler(service, web=WEB):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SupplierResearch/1.0"

        def log_message(self, format, *args):
            # Do not log chat text, query strings, provider data, or credentials.
            return

        def respond(self, status, body, content_type="application/json; charset=utf-8", attachment=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if attachment:
                self.send_header("Content-Disposition", 'attachment; filename="' + attachment + '"')
            self.end_headers()
            self.wfile.write(body)

        def validate_host(self):
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host", "") not in allowed:
                self.respond(403, {"error": "Invalid local Host header"})
                return False
            return True

        def body(self):
            allowed = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
            if self.headers.get("Origin") and self.headers["Origin"] not in allowed:
                raise PermissionError("Cross-origin writes are not allowed")
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                raise PermissionError("Cross-site writes are not allowed")
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                raise ValueError("Content-Type must be application/json")
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("Chunked request bodies are not supported")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ValueError("Invalid Content-Length") from None
            if not 0 < length <= MAX_BODY:
                raise ValueError("Request body must be between 1 and 16384 bytes")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object")
            return payload

        def dispatch(self, method):
            if not self.validate_host():
                return
            parsed = urllib.parse.urlsplit(self.path)
            path = parsed.path
            try:
                if method == "GET":
                    if path == "/api/config":
                        return self.respond(200, service.config())
                    if path == "/api/research":
                        return self.respond(200, {"runs": service.store.runs()})
                    if path == "/api/suppliers":
                        return self.respond(200, {"suppliers": service.store.suppliers()})
                    match = re.fullmatch(r"/api/research/([a-f0-9]{32})(/export)?", path)
                    if match:
                        run = service.store.get(match[1])
                        if not match[2]:
                            return self.respond(200, run)
                        format = urllib.parse.parse_qs(parsed.query).get("format", ["markdown"])[0]
                        if format == "json":
                            return self.respond(200, run, attachment=f"supplier-research-{run['id']}.json")
                        if format == "markdown":
                            return self.respond(200, markdown_report(run), "text/markdown; charset=utf-8", f"supplier-research-{run['id']}.md")
                        raise ValueError("Export format must be markdown or json")
                    if path.startswith("/api/"):
                        return self.respond(404, {"error": "API route not found"})
                    relative = urllib.parse.unquote(path).lstrip("/") or "index.html"
                    candidate = (Path(web) / relative).resolve()
                    if not candidate.is_relative_to(Path(web).resolve()) or any(part.startswith(".") for part in Path(relative).parts):
                        return self.respond(404, {"error": "File not found"})
                    if not candidate.is_file():
                        return self.respond(404, {"error": "File not found"})
                    mime = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
                    return self.respond(200, candidate.read_bytes(), mime + ("; charset=utf-8" if mime.startswith("text/") or mime == "application/javascript" else ""))
                values = self.body()
                if method == "POST" and path == "/api/research":
                    return self.respond(202, {"id": service.start(values)})
                match = re.fullmatch(r"/api/research/([a-f0-9]{32})/chat", path)
                if method == "POST" and match:
                    return self.respond(200, service.chat(match[1], values.get("message")))
                if method == "POST" and path == "/api/suppliers":
                    record, created = service.store.save_supplier(values.get("run_id"))
                    return self.respond(201 if created else 200, {**record, "created": created})
                match = re.fullmatch(r"/api/suppliers/([a-f0-9]{20})/actions/(A\d+)", path)
                if method == "PATCH" and match:
                    return self.respond(200, service.store.action(match[1], match[2], values))
                self.respond(404, {"error": "API route not found"})
            except PermissionError as error:
                self.respond(403, {"error": str(error)})
            except (ValueError, TypeError) as error:
                self.respond(400, {"error": str(error)[:500]})
            except KeyError:
                self.respond(404, {"error": "Record not found"})
            except Exception:
                self.respond(502, {"error": "The request could not complete. Check provider connectivity or retry; no fallback answer was fabricated."})

        def do_GET(self):
            self.dispatch("GET")

        def do_POST(self):
            self.dispatch("POST")

        def do_PATCH(self):
            self.dispatch("PATCH")

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8877)
    parser.add_argument("--env-file", help="Read an existing server-side environment file; never copied into the worktree")
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".local/research-agent")
    args = parser.parse_args()
    service = ResearchService(Store(args.data_dir), OpenRouter(read_environment(args.env_file)))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(service))
    print(f"Supplier research workbench: http://127.0.0.1:{server.server_port}")
    print(f"Live research: {'configured' if service.client.key else 'unavailable (no key)'}; model: {service.client.model}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.executor.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    main()
