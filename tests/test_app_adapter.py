"""The research adapter, chat triggers and HTTP routes, fully offline (fake search and model)."""
import http.client
import json
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from research_agent.app_adapter import ROOT, ResearchService, Store, safe_url
from research_agent.models import ClarificationRequest, ConfirmedEntity, ResearchResult
from supplier_app.core import Assistant, catalog
from supplier_app.server import make_handler


def wait(service, run_id, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        run = service.store.get(run_id)
        if run['status'] not in {'queued', 'researching'}:
            return run
        time.sleep(0.05)
    raise AssertionError('run did not finish')


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = catalog()
        cls.temp_class = tempfile.TemporaryDirectory()
        service = ResearchService(Store(cls.temp_class.name), {}, offline_fixture=True)
        cls.sample = wait(service, service.start({'company': 'Anything AG'}))
        cls.class_service = service

    @classmethod
    def tearDownClass(cls):
        cls.class_service.executor.shutdown(wait=True)
        cls.temp_class.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def service(self, **kwargs):
        service = ResearchService(Store(self.temp.name), {}, **kwargs)
        self.addCleanup(service.executor.shutdown, wait=True)
        return service

    # -- run object ---------------------------------------------------------
    def test_offline_run_carries_scores_tldr_citations_and_report(self):
        run = self.sample
        self.assertEqual(run['status'], 'completed')
        self.assertTrue(run['demo'])
        self.assertIn('fictional', run['notice'])
        self.assertEqual(run['schema_version'], 'research-run-v2')
        scores = run['scores']
        self.assertEqual([a['area'] for a in scores['areas']],
                         ['financial', 'legal', 'country', 'people', 'operations', 'reputation'])
        for area in scores['areas']:
            if area['coverage'] == 'not_assessed':
                self.assertIsNone(area['score'])  # Not assessed is null, never 0
                self.assertIsNone(area['level'])
            else:
                self.assertIsInstance(area['score'], int)
        self.assertIn('not comparable', scores['label'])
        points = run['tldr']['points']
        self.assertTrue(3 <= len(points) <= 5)
        order = {'red': 0, 'amber': 1, 'green': 2}
        self.assertEqual([p['colour'] for p in points], sorted((p['colour'] for p in points), key=order.get))
        numbers = {c['n'] for c in run['citations']}
        for p in points:
            self.assertTrue(p['citations'])
            self.assertTrue(set(p['citations']) <= numbers)
        for c in run['citations']:
            self.assertIn(c['trust'], {'trusted', 'company_stated', 'unverified'})
            self.assertTrue(c['trust_label'])
            if c['url']:
                self.assertTrue(c['url'].startswith('https://'))
            if c['quote']:
                self.assertIn('#:~:text=', c['link'])
        self.assertTrue(any(c['trust'] == 'unverified' and c['trust_label'].startswith('🟨') for c in run['citations']))
        for area in run['scoring']['areas']:
            for sub in area['sub_scores']:
                for line in sub['lines']:
                    self.assertTrue(set(line['citations']) <= numbers)
        self.assertNotIn('docs/', run['scoring']['method'])
        self.assertTrue(run['flags'] and run['timeline'])
        self.assertTrue(all(p['questions'] is not None for p in run['plan']))
        self.assertTrue(any(e.get('area') for e in run['events']))
        self.assertTrue(run['report']['html'])
        html = self.class_service.store.file(run['id'], 'report.html')
        self.assertNotIn('<script', html.lower())

    def test_chat_over_run_is_deterministic_and_cites(self):
        service = self.class_service
        answer = service.chat(self.sample['id'], 'Tell me about the recall')
        self.assertIn('recall', answer['answer'].lower())
        self.assertTrue(answer['citations'] and answer['citations'][0]['quote'])
        self.assertIn('Not assessed', service.chat(self.sample['id'], 'What is still unknown?')['answer'])
        self.assertIn('not comparable', service.chat(self.sample['id'], 'How was this scored?')['answer'])
        self.assertIn('does not answer', service.chat(self.sample['id'], 'xylophone quantum banana')['answer'])

    def test_needs_clarification_partial_and_error_mapping(self):
        def clarify(company, country, website, **kw):
            return ResearchResult(status='needs_clarification', company_input=company, researched_at='2026-10-18T00:00:00+00:00',
                                  clarification=ClarificationRequest(question='Which Acme?', candidates=[
                                      ConfirmedEntity(legal_name='Acme AG', country_code='DE'),
                                      ConfirmedEntity(legal_name='Acme Ltd', country_code='GB')]))
        service = self.service(runner=clarify)
        run = wait(service, service.start({'company': 'Acme'}))
        self.assertEqual(run['status'], 'needs_clarification')
        self.assertEqual([c['legal_name'] for c in run['clarification']['candidates']], ['Acme AG', 'Acme Ltd'])
        with self.assertRaises(ValueError):
            service.store.save_supplier(run['id'])

        def failing(company, country, website, **kw):
            return ResearchResult(status='error', company_input=company, researched_at='2026-10-18T00:00:00+00:00',
                                  warnings=['TAVILY_API_KEY missing'])
        service.runner = failing
        run = wait(service, service.start({'company': 'Acme'}))
        self.assertEqual(run['status'], 'failed')
        self.assertIn('TAVILY_API_KEY', run['error'])

    def test_live_requires_keys_and_basic_mode_validation(self):
        service = self.service()
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            service.start({'company': 'Acme'})
        with self.assertRaises(ValueError):
            self.service(offline_fixture=True).start({'company': 'Acme', 'mode': 'fast'})
        self.assertEqual(safe_url('javascript:alert(1)'), '')
        self.assertEqual(safe_url('http://127.0.0.1/x'), '')

    def test_store_supplier_dedupe_and_restart_recovery(self):
        store = self.class_service.store
        record, created = store.save_supplier(self.sample['id'])
        again, created_again = store.save_supplier(self.sample['id'])
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(record['id'], again['id'])
        self.assertIsNone(record['numeric_scores']['total'])  # dataset columns stay empty
        self.assertEqual(record['agent_scores']['total'], self.sample['scores']['total'])
        temp = Store(self.temp.name)
        temp.put({'id': 'b' * 32, 'status': 'researching'})
        self.assertEqual(Store(self.temp.name).get('b' * 32)['status'], 'failed')

    # -- chat triggers ---------------------------------------------------------
    def test_hybrid_research_triggers(self):
        service = self.service()
        calls = []
        service.start = lambda values: calls.append(values) or 'a' * 32
        assistant = Assistant(service, self.data)
        self.assertEqual(assistant.answer({'message': 'Tell me about Knorr-Bremse AG'})['kind'], 'offer')
        soft = assistant.answer({'message': 'knorr-bremse'})
        self.assertEqual(soft['kind'], 'offer')
        self.assertIn('Did you mean', soft['answer'])
        self.assertEqual(calls, [])  # an offer spends nothing
        self.assertEqual(assistant.answer({'message': 'Research Knorr-Bremse'})['kind'], 'research')
        self.assertEqual(calls[-1]['company'], 'Knorr-Bremse')
        self.assertEqual(assistant.answer({'message': 'Knorr-Bremse', 'company': 'Knorr-Bremse', 'trigger': 'button', 'mode': 'deep'})['kind'], 'research')
        for message in ['Why is SUPP_00012 high risk?', 'Compare risk SUPP_00012 SUPP_00450', 'How many suppliers?']:
            self.assertNotIn(assistant.answer({'message': message})['kind'], {'offer', 'research'}, message)
        name = assistant.rows['SUPP_00012']['Supplier Name']
        self.assertNotEqual(assistant.answer({'message': 'Compare risk for ' + name})['kind'], 'offer')
        self.assertEqual(assistant.answer({'message': 'Research it', 'company': name})['kind'], 'clarify')
        before = len(calls)
        self.assertNotEqual(assistant.answer({'message': 'Show suppliers', 'mode': 'deep'})['kind'], 'research')
        self.assertEqual(len(calls), before)  # Deep mode alone no longer starts research

    def test_follow_up_on_open_run_stays_in_chat(self):
        assistant = Assistant(self.class_service, self.data)
        answer = assistant.answer({'message': 'What about the recall?', 'run_id': self.sample['id']})
        self.assertEqual(answer['kind'], 'answer')
        self.assertTrue(answer['citations'] and answer['citations'][0]['kind'] == 'web')
        offer = assistant.answer({'message': 'Tell me about Stadler Rail AG', 'run_id': self.sample['id']})
        self.assertEqual(offer['kind'], 'offer')

    # -- HTTP -------------------------------------------------------------------
    def test_http_routes_and_boundaries(self):
        service = self.class_service
        web = Path(self.temp.name) / 'web'
        web.mkdir()
        (web / 'index.html').write_text('<h1>App</h1>')
        (Path(self.temp.name) / '.env').write_text('SECRET=do-not-serve')
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(service, web=web, data=self.data))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(method, path, body=None, headers=None):
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            data = response.read()
            result = response.status, data, dict(response.getheaders())
            conn.close()
            return result
        try:
            rid = self.sample['id']
            self.assertEqual(request('GET', '/')[0], 200)
            for path in ('/../.env', '/%2e%2e/.env', '/.env', '/docs/supplier_risk_dataset.csv'):
                self.assertEqual(request('GET', path)[0], 404, path)
            status, data, _ = request('GET', '/api/config')
            self.assertEqual(status, 200)
            self.assertNotIn(b'SECRET', data)
            status, data, _ = request('GET', '/api/research/' + rid)
            run = json.loads(data)
            self.assertIn('<html', run['report_html'].lower())
            self.assertIn('scores', run)
            status, data, headers = request('GET', f'/api/research/{rid}/report.html')
            self.assertEqual(status, 200)
            self.assertIn("frame-ancestors 'self'", headers['Content-Security-Policy'])
            self.assertIn('text/html', headers['Content-Type'])
            for fmt in ('markdown', 'json', 'html'):
                status, _, headers = request('GET', f'/api/research/{rid}/export?format={fmt}')
                self.assertEqual(status, 200, fmt)
                self.assertIn('attachment', headers['Content-Disposition'])
            status, data, _ = request('GET', f'/api/research/{rid}/scoring')
            self.assertTrue(json.loads(data)['scoring']['areas'])
            rows = json.loads(request('GET', '/api/research')[1])['runs']
            self.assertEqual(rows[0]['score']['total'], self.sample['scores']['total'])
            body = json.dumps({'company': 'Acme'})
            self.assertEqual(request('POST', '/api/research', body, {'Content-Type': 'application/json', 'Origin': 'https://evil.example'})[0], 403)
            self.assertEqual(request('GET', '/api/config', headers={'Host': 'evil.example'})[0], 403)
            self.assertEqual(request('POST', '/api/research', body, {'Content-Type': 'text/plain'})[0], 400)
            self.assertEqual(request('POST', '/api/research', '[]', {'Content-Type': 'application/json'})[0], 400)
            self.assertEqual(request('POST', '/api/research', '{' * 17000, {'Content-Type': 'application/json'})[0], 400)
            # An older (pre-migration) run is still served.
            service.store.put({'id': 'c' * 32, 'schema_version': 'research-dossier-v1', 'status': 'completed', 'company': 'Old', 'summary': 'x'})
            self.assertEqual(request('GET', '/api/research/' + 'c' * 32)[0], 200)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_removed_providers_are_gone(self):
        out = subprocess.run(['git', 'grep', '--untracked', '-il', '-E', r'openrouter|nemotron|\bexa\b', '--', 'supplier_app',
                              'web', 'tests', 'config', '.env.example', ':!tests/test_app_adapter.py'],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), '')
        for module in ('core', 'server', 'demo'):
            self.assertFalse((ROOT / 'research_agent' / f'{module}.py').exists())


if __name__ == '__main__':
    unittest.main()
