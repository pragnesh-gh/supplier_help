"""Unified API contracts; no external requests or paid inference."""
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from supplier_app.core import Assistant, Workspace, catalog
from supplier_app.server import make_handler
from research_agent.app_adapter import ResearchService, Store


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = catalog()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = ResearchService(Store(self.temp.name), {})
        self.assistant = Assistant(self.service, self.data)

    def tearDown(self):
        self.service.executor.shutdown(wait=True)
        self.temp.cleanup()

    def test_catalog_types_and_all_rows(self):
        self.assertEqual(len(self.data['rows']), 10000)
        self.assertEqual(len(self.data['columns']), 60)
        self.assertIsInstance(self.data['rows'][0][2], int)
        self.assertIsInstance(self.data['rows'][0][48], bool)

    def test_source_metric_chart_and_unsupported(self):
        answer = self.assistant.answer({'message': 'Compare financial SUPP_00001 SUPP_00002'})
        self.assertEqual(answer['chart']['metric'], 'Financial_Health_Score')
        self.assertEqual(answer['citations'][0]['value'], self.assistant.rows['SUPP_00001']['Financial_Health_Score'])
        self.assertEqual(self.assistant.answer({'message': 'Who is its CEO?', 'selected_ids': ['SUPP_00001']})['kind'], 'clarify')
        self.assertEqual(self.assistant.answer({'message': 'Research SUPP_00001', 'mode': 'deep'})['kind'], 'clarify')
        self.assertNotIn('chart', self.assistant.answer({'message': 'Show trends', 'selected_ids': ['SUPP_00001']}))

    def test_recovery_preserves_original_and_valid_fields(self):
        workspace = Workspace(self.temp.name, self.assistant.rows)
        original = {'favorites': ['SUPP_00012', 'research:missing'], 'compare': ['missing'], 'drafts': [{'kind': 'approval', 'memo': {'text': 'retain'}}]}
        workspace.path.write_text(json.dumps(original), encoding='utf-8')
        restored = workspace.get()
        self.assertEqual(restored['favorites'], ['SUPP_00012'])
        self.assertEqual(restored['compare'], [])
        self.assertEqual(restored['drafts'], original['drafts'])
        self.assertEqual(json.loads(workspace.path.with_suffix('.recovery.json').read_text()), original)
        workspace.path.write_text('{corrupt', encoding='utf-8')
        self.assertIsNone(workspace.get()['favorites'])

    def test_count_missing_numeric_and_conflicting_direction(self):
        answer = self.assistant.answer({'message': 'How many suppliers?', 'selected_ids': ['SUPP_00012']})
        self.assertIn('10,000', answer['answer'])
        answer = self.assistant.answer({'message': 'How many selected suppliers?', 'selected_ids': ['SUPP_00012']})
        self.assertIn('1 explicitly selected', answer['answer'])
        answer = self.assistant.answer({'message': 'Rank risk highest lowest', 'selected_ids': ['SUPP_00012']})
        self.assertEqual(answer['kind'], 'clarify')
        self.assistant.rows['SUPP_00012']['Supplier Delivery Rating'] = None
        answer = self.assistant.answer({'message': 'Rank best delivery', 'selected_ids': ['SUPP_00012', 'SUPP_00450']})
        self.assertEqual(len(answer['chart']['points']), 1)
        self.assertEqual(answer['chart']['points'][0]['label'], 'SUPP_00450')

    def test_ranking_direction_matches_metric_meaning(self):
        ids = ['SUPP_00012', 'SUPP_00450', 'SUPP_00731']
        def values(question):
            return [p['value'] for p in self.assistant.answer({'message': question, 'selected_ids': ids})['chart']['points']]
        delivery = values('Rank best delivery')
        self.assertEqual(delivery, sorted(delivery, reverse=True))
        confirmation = values('Rank worst confirmation')
        self.assertEqual(confirmation, sorted(confirmation))
        risk = values('Rank best risk')
        self.assertEqual(risk, sorted(risk))
        lowest_delivery = values('Rank lowest delivery')
        self.assertEqual(lowest_delivery, sorted(lowest_delivery))
        highest_risk = values('Rank highest risk')
        self.assertEqual(highest_risk, sorted(highest_risk, reverse=True))
        self.assertEqual(self.assistant.answer({'message': 'Rank best purchase volume', 'selected_ids': ids})['kind'], 'clarify')

    def test_explicit_identity_overrides_selected_context(self):
        result = self.assistant.answer({'message': 'Why is total risk high for SUPP_00018?', 'selected_ids': ['SUPP_00012']})
        self.assertEqual({c['supplier_id'] for c in result['citations']}, {'SUPP_00018'})
        name = self.assistant.rows['SUPP_00018']['Supplier Name']
        result = self.assistant.answer({'message': 'Compare risk for ' + name, 'selected_ids': ['SUPP_00012']})
        self.assertEqual({c['supplier_id'] for c in result['citations']}, {'SUPP_00018'})

    def test_numbered_names_require_word_boundaries(self):
        self.assistant.names = {'test supplier 12': [self.assistant.rows['SUPP_00012']], 'test supplier 123': [self.assistant.rows['SUPP_00123']]}
        result = self.assistant.answer({'message': 'Compare risk for Test Supplier 123', 'selected_ids': ['SUPP_00018']})
        self.assertEqual({c['supplier_id'] for c in result['citations']}, {'SUPP_00123'})

    def test_deep_data_identity_and_total_explanation(self):
        answer = self.assistant.answer({'message': 'Compare financial SUPP_00001', 'mode': 'deep'})
        self.assertEqual(answer['kind'], 'answer')
        self.assertEqual(answer['chart']['metric'], 'Financial_Health_Score')
        answer = self.assistant.answer({'message': 'Why is total risk high for SUPP_00001?'})
        self.assertIn('does not disclose', answer['answer'])
        self.assertEqual(len(answer['citations']), 4)
        self.assertEqual(self.assistant.answer({'message': 'Compare SUPP_00001 SUPP_99999'})['kind'], 'clarify')

    def test_research_immediate_and_context_separate(self):
        calls = []
        self.service.start = lambda values: calls.append(values) or 'a' * 32
        result = self.assistant.answer({'message': 'Research company', 'company': 'Acme GmbH', 'mode': 'deep', 'selected_ids': ['SUPP_00001']})
        self.assertEqual(result['run_id'], 'a' * 32)
        self.assertNotIn('SUPP_', calls[0]['scope'])
        self.assertEqual(calls[0]['dataset_context'][0]['supplier_id'], 'SUPP_00001')

    def test_workspace_bounds_and_persistence(self):
        workspace = Workspace(self.temp.name, self.assistant.rows)
        self.assertIsNone(workspace.get()['favorites'])
        value = workspace.put({'favorites': [], 'compare': ['SUPP_00001'], 'chat': [{'role': 'user', 'text': 'hi'}], 'drafts': [{'kind': 'approval', 'memo': {}}]})
        self.assertEqual(Workspace(self.temp.name, self.assistant.rows).get(), value)
        with self.assertRaises(ValueError):
            workspace.put({'compare': list(self.assistant.rows)[:21]})

    def test_recents_preserve_mru_order_and_validate_identity(self):
        workspace = Workspace(self.temp.name, self.assistant.rows)
        self.assertEqual(workspace.get()['recents'], [])
        workspace.put({'recents': ['SUPP_00450', 'SUPP_00012', 'SUPP_00450']})
        self.assertEqual(workspace.get()['recents'], ['SUPP_00450', 'SUPP_00012'])
        with self.assertRaises(ValueError):
            workspace.put({'recents': ['unknown']})
        with self.assertRaises(ValueError):
            workspace.put({'recents': list(self.assistant.rows)[:51]})

    def test_every_augmented_part_belongs_to_its_system(self):
        columns = self.data['columns']
        region_index = columns.index('train_region_id')
        part_index = columns.index('train_part_id')
        allowed = {region['id']: {part['id'] for part in region['parts']}
                   for region in self.data['manifest']['regions']}
        for row in self.data['rows']:
            self.assertIn(row[part_index], allowed[row[region_index]])

    def test_http_contract_and_boundaries(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.service, data=self.data))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
            conn.request('GET', '/health')
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())['catalog_rows'], 10000)
            conn.request('GET', '/../.env')
            response = conn.getresponse(); self.assertEqual(response.status, 404); response.read()
            body = json.dumps({'favorites': [], 'chat': [{'text': 'x' * 20000}]})
            conn.request('PUT', '/api/workspace', body, {'Content-Type': 'application/json'})
            response = conn.getresponse(); self.assertEqual(response.status, 200); response.read()
            rich = [{'role': 'assistant', 'answer': 'value', 'citations': [{'id': 'D1', 'kind': 'dataset', 'supplier_id': 'SUPP_00012', 'column': 'Total_Risk_Index', 'value': 50}]} for _ in range(190)]
            compact_size = len(json.dumps(rich, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
            rich[0]['answer'] += 'x' * (95000 - compact_size)
            self.assertEqual(len(json.dumps(rich, ensure_ascii=False, separators=(',', ':')).encode('utf-8')), 95000)
            body = json.dumps({'chat': rich}, ensure_ascii=False, separators=(',', ':'))
            conn.request('PUT', '/api/workspace', body.encode('utf-8'), {'Content-Type': 'application/json'})
            response = conn.getresponse(); self.assertEqual(response.status, 200); response.read()
            conn.request('POST', '/api/assistant', json.dumps({'message': 'Research Acme', 'company': 'Acme'}), {'Content-Type': 'application/json'})
            response = conn.getresponse(); self.assertEqual(response.status, 400)
            self.assertIn('unavailable', json.loads(response.read())['error'])
            conn.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()


def test_read_environment_defaults_to_root_then_research_agent_env(tmp_path, monkeypatch):
    from supplier_app import env as env_mod

    root, ra = tmp_path / '.env', tmp_path / 'research_agent.env'
    root.write_text('A=root\nB=\n')
    ra.write_text('A=ra\nB=ra\nexport C="ra"\n')
    monkeypatch.setattr(env_mod, 'DEFAULT_ENV_FILES', (root, ra))
    for k in ('A', 'B', 'C'):
        monkeypatch.delenv(k, raising=False)
    values = env_mod.read_environment()
    assert (values['A'], values['B'], values['C']) == ('root', 'ra', 'ra')
    monkeypatch.setenv('A', 'os')
    assert env_mod.read_environment()['A'] == 'os'
    assert 'B' not in env_mod.read_environment(str(root)) or env_mod.read_environment(str(root))['B'] == ''
