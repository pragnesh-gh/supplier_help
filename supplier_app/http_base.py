"""Loopback-only HTTP base handler: static UI from web/, research and saved-supplier routes.

No repository or secret file is ever served. Research logic lives in research_agent.app_adapter;
this module only speaks HTTP.
"""
from http.server import BaseHTTPRequestHandler
import json
import mimetypes
from pathlib import Path
import re
import urllib.parse

MAX_BODY = 16 * 1024
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
       "base-uri 'none'; form-action 'self'")
# The report is script-free HTML shown in a sandboxed iframe of this app only.
REPORT_CSP = ("default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; "
              "frame-ancestors 'self'")
RUN = r"/api/research/([a-f0-9]{32})"


def make_handler(service, web):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'SupplierWorkbench/2.0'

        def log_message(self, format, *args):
            # Do not log chat text, query strings, provider data or credentials.
            return

        def respond(self, status, body, content_type='application/json; charset=utf-8', attachment=None, csp=CSP):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            elif isinstance(body, str):
                body = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', csp)
            if attachment:
                self.send_header('Content-Disposition', 'attachment; filename="' + attachment + '"')
            self.end_headers()
            self.wfile.write(body)

        def validate_host(self):
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if self.headers.get('Host', '') not in allowed:
                self.respond(403, {'error': 'Invalid local Host header'})
                return False
            return True

        def body(self):
            allowed = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
            if self.headers.get('Origin') and self.headers['Origin'] not in allowed:
                raise PermissionError('Cross-origin writes are not allowed')
            if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                raise PermissionError('Cross-site writes are not allowed')
            if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
                raise ValueError('Content-Type must be application/json')
            if self.headers.get('Transfer-Encoding'):
                raise ValueError('Chunked request bodies are not supported')
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                raise ValueError('Invalid Content-Length') from None
            if not 0 < length <= MAX_BODY:
                raise ValueError('Request body must be between 1 and 16384 bytes')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Request body must be a JSON object')
            return payload

        def run_with_report(self, run_id):
            run = service.store.get(run_id)
            if (run.get('report') or {}).get('html'):
                try:
                    run['report_html'] = service.store.file(run_id, 'report.html')
                except KeyError:
                    pass
            return run

        def export(self, run_id, fmt):
            run = service.store.get(run_id)
            name = 'supplier-research-' + run_id
            if run.get('schema_version') != 'research-run-v2':
                if fmt != 'json':
                    raise ValueError('This older report can only be exported as JSON')
                return self.respond(200, run, attachment=name + '.json')
            if fmt == 'json':
                result = json.loads(service.store.file(run_id, 'result.json'))
                slim = {k: v for k, v in run.items() if k != 'events'}
                return self.respond(200, {'run': slim, 'result': result}, attachment=name + '.json')
            if fmt == 'markdown':
                return self.respond(200, service.store.file(run_id, 'report.md'), 'text/markdown; charset=utf-8', name + '.md')
            if fmt == 'html':
                return self.respond(200, service.store.file(run_id, 'report.html'), 'text/html; charset=utf-8', name + '.html', csp=REPORT_CSP)
            raise ValueError('Export format must be markdown, json or html')

        def static(self, path):
            relative = urllib.parse.unquote(path).lstrip('/') or 'index.html'
            candidate = (Path(web) / relative).resolve()
            if not candidate.is_relative_to(Path(web).resolve()) or any(part.startswith('.') for part in Path(relative).parts):
                return self.respond(404, {'error': 'File not found'})
            if not candidate.is_file():
                return self.respond(404, {'error': 'File not found'})
            mime = mimetypes.guess_type(str(candidate))[0] or 'application/octet-stream'
            text = mime.startswith('text/') or mime in {'application/javascript', 'text/javascript'}
            return self.respond(200, candidate.read_bytes(), mime + ('; charset=utf-8' if text else ''))

        def dispatch(self, method):
            if not self.validate_host():
                return
            parsed = urllib.parse.urlsplit(self.path)
            path = parsed.path
            try:
                if method == 'GET':
                    if path == '/api/config':
                        return self.respond(200, service.config())
                    if path == '/api/research':
                        return self.respond(200, {'runs': service.store.runs()})
                    if path == '/api/suppliers':
                        return self.respond(200, {'suppliers': service.store.suppliers()})
                    match = re.fullmatch(RUN + r'(/export|/report\.html|/scoring)?', path)
                    if match:
                        run_id, sub = match[1], match[2]
                        if not sub:
                            return self.respond(200, self.run_with_report(run_id))
                        if sub == '/report.html':
                            return self.respond(200, service.store.file(run_id, 'report.html'), 'text/html; charset=utf-8', csp=REPORT_CSP)
                        if sub == '/scoring':
                            run = service.store.get(run_id)
                            return self.respond(200, {'scoring': run.get('scoring'), 'scores': run.get('scores'), 'citations': run.get('citations', [])})
                        fmt = urllib.parse.parse_qs(parsed.query).get('format', ['markdown'])[0]
                        return self.export(run_id, fmt)
                    if path.startswith('/api/'):
                        return self.respond(404, {'error': 'API route not found'})
                    return self.static(path)
                values = self.body()
                if method == 'POST' and path == '/api/research':
                    run_id = service.start(values)
                    return self.respond(202, {'id': run_id, 'run_id': run_id})
                match = re.fullmatch(RUN + r'/chat', path)
                if method == 'POST' and match:
                    return self.respond(200, service.chat(match[1], values.get('message')))
                if method == 'POST' and path == '/api/suppliers':
                    record, created = service.store.save_supplier(values.get('run_id'))
                    return self.respond(201 if created else 200, {**record, 'created': created})
                match = re.fullmatch(r'/api/suppliers/([a-f0-9]{20})/actions/(A\d+)', path)
                if method == 'PATCH' and match:
                    return self.respond(200, service.store.action(match[1], match[2], values))
                self.respond(404, {'error': 'API route not found'})
            except PermissionError as error:
                self.respond(403, {'error': str(error)})
            except (ValueError, TypeError) as error:
                self.respond(400, {'error': str(error)[:500]})
            except KeyError:
                self.respond(404, {'error': 'Record not found'})
            except Exception:
                self.respond(502, {'error': 'The request could not complete. Please retry.'})

        def do_GET(self):
            self.dispatch('GET')

        def do_POST(self):
            self.dispatch('POST')

        def do_PATCH(self):
            self.dispatch('PATCH')

    return Handler
