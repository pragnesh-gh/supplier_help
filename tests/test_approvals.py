"""Submission boundaries and immutable evidence, without external services."""
import copy
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from research_agent.app_adapter import ResearchService, Store
from supplier_app.approvals import Approvals
from supplier_app.core import catalog
from supplier_app.server import make_handler


class ApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = catalog()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.approvals = Approvals(self.temp.name, self.data, self.store)
        self.payload = {'requester': 'Buyer', 'reviewer': 'Manager', 'project': 'Door sourcing',
                        'rationale': 'Preserve alternatives while negotiating delivery and guarantees.',
                        'candidates': [{'supplier_id': f'SUPP_{i:05}', 'tradeoffs': 'Check capacity against risk.',
                                        'negotiation_questions': 'What delivery commitment can you provide?'} for i in range(1, 4)]}

    def tearDown(self):
        self.temp.cleanup()

    def test_candidate_and_required_field_validation(self):
        for count in [0, 1, 2, 6]:
            value = copy.deepcopy(self.payload)
            value['candidates'] = [dict(self.payload['candidates'][0], supplier_id=f'SUPP_{i:05}') for i in range(1, count + 1)]
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.approvals.submit(value)
        for key in ['requester', 'reviewer', 'project', 'rationale']:
            value = copy.deepcopy(self.payload)
            value.pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.approvals.submit(value)
        for mutation in [{'supplier_id': 'absent'}, {'supplier_id': 'SUPP_00002'}, {'tradeoffs': ''}, {'negotiation_questions': '   '}]:
            value = copy.deepcopy(self.payload)
            value['candidates'][0].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.approvals.submit(value)
        self.assertFalse(self.approvals.path.exists())

    def test_cart_one_click_defaults_satisfy_validation(self):
        # Contract test: the payload the shortlist cart sends (web/approval.js quickRequest)
        # must pass unchanged backend validation.
        import pathlib, shutil, subprocess
        node = shutil.which('node')
        if not node:
            self.skipTest('node is not installed')
        module = (pathlib.Path(__file__).resolve().parent.parent / 'web' / 'approval.js').as_uri()
        script = (f"import({json.dumps(module)}).then(m => process.stdout.write(JSON.stringify("
                  "m.quickRequest({ids:['SUPP_00001','SUPP_00002','SUPP_00003'], scope:'Doors', project:'Shortlist · Doors'}))))")
        out = subprocess.run([node, '--input-type=module', '-e', script], capture_output=True, text=True, check=True, timeout=30)
        saved = self.approvals.submit(json.loads(out.stdout))
        self.assertEqual(saved['requester'], 'Demo buyer')
        self.assertEqual(saved['status'], 'awaiting_approval')
        self.assertEqual([c['supplier_id'] for c in saved['candidates']], ['SUPP_00001', 'SUPP_00002', 'SUPP_00003'])
        self.assertTrue(all(c['snapshot']['kind'] == 'dataset' for c in saved['candidates']))

    def test_snapshot_persisted_and_server_controls_status(self):
        self.payload.update(status='approved', id='fake')
        self.payload['candidates'][0]['snapshot'] = {'values': {'Total_Risk_Index': -1}}
        saved = self.approvals.submit(self.payload)
        self.assertEqual(saved['status'], 'awaiting_approval')
        self.assertNotEqual(saved['id'], 'fake')
        self.assertEqual(saved['purpose'], 'approval_to_negotiate')
        snapshot = saved['candidates'][0]['snapshot']
        self.assertEqual(snapshot['values'], self.approvals.rows['SUPP_00001'])
        self.assertEqual(snapshot['sha256'], self.data['sha256'])
        self.approvals.rows['SUPP_00001']['Total_Risk_Index'] = -999
        saved['rationale'] = 'mutated return value'
        reloaded = Approvals(self.temp.name, self.data, self.store).list()[0]
        self.assertNotEqual(reloaded['candidates'][0]['snapshot']['values']['Total_Risk_Index'], -999)
        self.assertEqual(reloaded['rationale'], self.payload['rationale'])

    def test_research_snapshot_remains_separate_and_append_preserves_previous(self):
        self.store.data['suppliers']['saved'] = {'id': 'saved', 'company': 'Example Ltd', 'run_id': 'run', 'numeric_scores': {'total': None}}
        self.store.data['runs']['run'] = {'id': 'run', 'status': 'completed', 'sources': [{'url': 'https://example.com'}]}
        first = self.approvals.submit(self.payload)
        self.payload['candidates'][0]['supplier_id'] = 'research:saved'
        second = self.approvals.submit(self.payload)
        snapshot = second['candidates'][0]['snapshot']
        self.assertEqual(snapshot['kind'], 'research')
        self.assertIsNone(snapshot['record']['numeric_scores']['total'])
        self.assertEqual(snapshot['dossier']['sources'][0]['url'], 'https://example.com')
        self.assertEqual(self.approvals.list(), [second, first])

    def test_http_submission_readback_and_cross_origin(self):
        service = ResearchService(self.store, {})
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(service, data=self.data))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
        try:
            body = json.dumps(self.payload)
            conn.request('POST', '/api/approvals', body, {'Content-Type': 'application/json', 'Origin': 'https://other.example'})
            response = conn.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
            conn.request('POST', '/api/approvals', body, {'Content-Type': 'application/json'})
            response = conn.getresponse()
            self.assertEqual(response.status, 201)
            created = json.loads(response.read())
            conn.request('GET', '/api/approvals')
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read()), {'requests': [created]})
            conn.request('PUT', '/api/approvals', body, {'Content-Type': 'application/json'})
            response = conn.getresponse()
            self.assertEqual(response.status, 405)
            response.read()
        finally:
            conn.close()
            server.shutdown()
            server.server_close()
            thread.join()
            service.executor.shutdown(wait=True)

    def test_missing_research_evidence_does_not_save_request(self):
        self.store.data['suppliers']['saved'] = {'id': 'saved', 'company': 'Example Ltd', 'run_id': 'missing'}
        self.payload['candidates'][0]['supplier_id'] = 'research:saved'
        with self.assertRaisesRegex(ValueError, 'research:saved'):
            self.approvals.submit(self.payload)
        self.assertEqual(self.approvals.list(), [])
