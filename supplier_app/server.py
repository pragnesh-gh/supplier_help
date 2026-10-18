"""Loopback HTTP entry for the unified supplier web application."""
import argparse
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import urllib.parse
from research_agent.core import ROOT, ResearchService, Store, OpenRouter, read_environment
from research_agent.server import make_handler as research_handler
from .core import Assistant, Workspace, catalog
from .approvals import Approvals


def make_handler(service, web=None, data=None, workspace=None):
    data = data or catalog()
    assistant = Assistant(service, data)
    workspace = workspace or Workspace(service.store.path, assistant.rows, lambda: ['research:' + r['id'] for r in service.store.suppliers()])
    approvals = Approvals(service.store.path, data, service.store)
    base = research_handler(service, web or ROOT / 'web')

    class Handler(base):
        def dispatch(self, method):
            path = urllib.parse.urlsplit(self.path).path
            custom = path in {'/health', '/api/catalog', '/api/workspace', '/api/assistant', '/api/approvals'} or (method == 'POST' and path == '/api/research')
            if not custom:
                return super().dispatch(method)
            if not self.validate_host():
                return
            try:
                if method == 'GET' and path == '/health':
                    return self.respond(200, {'status': 'ok', 'catalog_rows': len(data['rows'])})
                if method == 'GET' and path == '/api/catalog':
                    return self.respond(200, data)
                if method == 'GET' and path == '/api/approvals':
                    return self.respond(200, {'requests': approvals.list()})
                if method == 'POST' and path == '/api/approvals':
                    return self.respond(201, approvals.submit(self.workspace_body()))
                if method == 'GET' and path == '/api/workspace':
                    return self.respond(200, workspace.get())
                if method == 'PUT' and path == '/api/workspace':
                    # Reuse origin/content-type checks while permitting bounded conversation history.
                    # Do not change the legacy module's request limit globally.
                    return self.respond(200, workspace.put(self.workspace_body()))
                if method == 'POST' and path == '/api/assistant':
                    return self.respond(200, assistant.answer(self.body()))
                if method == 'POST' and path == '/api/research':
                    values = self.body()
                    if 'example' in values:
                        values['demo'] = values.pop('example')
                    run_id = service.start(values)
                    return self.respond(202, {'id': run_id, 'run_id': run_id})
                return self.respond(405, {'error': 'Method not allowed'})
            except PermissionError as error:
                self.respond(403, {'error': str(error)})
            except (ValueError, TypeError) as error:
                self.respond(400, {'error': str(error)[:500]})
            except KeyError:
                self.respond(404, {'error': 'Record not found'})
            except Exception:
                self.respond(502, {'error': 'Request could not complete; no fallback answer was fabricated.'})

        def workspace_body(self):
            allowed = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
            if self.headers.get('Origin') and self.headers['Origin'] not in allowed or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                raise PermissionError('Cross-origin writes are not allowed')
            if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json' or self.headers.get('Transfer-Encoding'):
                raise ValueError('A JSON request with Content-Length is required')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 400000:
                raise ValueError('Workspace body must be at most 400000 bytes')
            return json.loads(self.rfile.read(length))

        def do_PUT(self):
            self.dispatch('PUT')
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8878)
    parser.add_argument('--env-file', help='Optional server-side environment file')
    parser.add_argument('--data-dir', type=Path, default=ROOT / '.local/supplier-app')
    args = parser.parse_args()
    service = ResearchService(Store(args.data_dir), OpenRouter(read_environment(args.env_file)))
    data = catalog()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(service, data=data, workspace=Workspace(args.data_dir, [r[0] for r in data['rows']], lambda: ['research:' + r['id'] for r in service.store.suppliers()])))
    print(f'Supplier workbench: http://127.0.0.1:{server.server_port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.executor.shutdown(wait=False, cancel_futures=True)


if __name__ == '__main__':
    main()
