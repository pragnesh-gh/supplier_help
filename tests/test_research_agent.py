"""Contract and safety checks without network requests or paid inference."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

from research_agent.core import (CATEGORIES, OpenRouter, ProviderLengthError, ResearchService, Store,
    annotation_sources, ground_findings, markdown_report, safe_url)
from research_agent.server import make_handler


class FakeClient:
    key = "test-only-not-a-real-key"
    model = "test-model"

    def __init__(self):
        self.searches = []
        self.calls = 0

    def complete(self, system, prompt, search=False, deep=False, tokens=0):
        self.calls += 1
        quote = "Acme's latest report discloses potential supply chain disruption."
        if search:
            self.searches.append((prompt, deep))
            return {"content": "Source notes", "annotations": [{"type": "url_citation", "url_citation": {
                "url": "https://example.com/acme-report", "title": "Acme report", "content": quote}}]}, {}
        if "finding_ids" in system:
            return {"content": json.dumps({"finding_ids": ["F1"], "unknown": False})}, {}
        return {"content": json.dumps({"findings": [{"category": "operations", "title": "Disclosed supply exposure",
            "detail": quote, "severity": "unknown", "confidence": "high", "status": "confirmed",
            "evidence": [{"source_id": "S1", "quote": quote}], "follow_up": "Request current continuity evidence."}],
            "gaps": ["Component-specific performance is not established."]})}, {}


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.client = FakeClient()
        self.service = ResearchService(self.store, self.client)

    def tearDown(self):
        self.service.executor.shutdown(wait=True)
        self.temp.cleanup()

    def run_dossier(self, **values):
        run_id = self.service.start({"company": "Acme", **values})
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            run = self.store.get(run_id)
            if run["status"] in {"completed", "failed"}:
                self.assertEqual(run["status"], "completed", run.get("error"))
                return run
            time.sleep(.01)
        self.fail("Run did not finish")

    def test_provider_annotations_are_only_live_source_introduction(self):
        sources = []
        annotation_sources({"content": "Invented https://malicious.example/fact", "annotations": [
            {"type": "url_citation", "url_citation": {"url": "http://127.0.0.1/secret", "content": "secret"}},
            {"type": "url_citation", "url_citation": {"url": "https://example.com/report", "title": "Report", "content": "A sufficiently long excerpt from the report."}}]}, sources)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["kind"], "retrieved_excerpt")
        self.assertIsNone(sources[0]["published_at"])

    def test_unsupported_claims_rejected_and_snippets_never_confirmed(self):
        sources = [{"id": "S1", "excerpt": "A potential exposure is disclosed by the company."}]
        good = {"category": "operations", "status": "confirmed", "confidence": "high", "evidence": [
            {"source_id": "S1", "quote": "A potential exposure is disclosed by the company."}]}
        bad = {**good, "evidence": [{"source_id": "S2", "quote": "A potential exposure is disclosed by the company."}]}
        fake_quote = {**good, "evidence": [{"source_id": "S1", "quote": "The company has had a verified major recent accident."}]}
        findings, rejected = ground_findings([good, bad, fake_quote], sources)
        self.assertEqual((len(findings), rejected), (1, 2))
        self.assertEqual(findings[0]["status"], "unknown")
        self.assertEqual(findings[0]["confidence"], "medium")

    def test_basic_and_deep_search_budgets_and_no_fake_rating(self):
        basic = self.run_dossier(mode="basic")
        self.assertEqual(len(self.client.searches), 6)
        self.assertIsNone(basic["legacy_scores"])
        self.assertEqual(len(basic["categories"]), 6)
        self.assertEqual(basic["categories"][0]["assessment"], "unknown")
        self.assertEqual(basic["findings"][0]["severity"], "unknown")
        self.assertIn("No numeric company risk score", markdown_report(basic))
        self.client.searches.clear()
        deep = self.run_dossier(mode="deep")
        self.assertGreater(len(self.client.searches), 6)
        self.assertLessEqual(len(self.client.searches), 9)
        self.assertTrue(all(deep for _, deep in self.client.searches))
        self.assertTrue(any(e["stage"] == "follow_up" for e in deep["events"]))

    def test_save_duplicate_and_reload_actions(self):
        run = self.run_dossier()
        saved, created = self.store.save_supplier(run["id"])
        duplicate, again = self.store.save_supplier(run["id"])
        self.assertTrue(created)
        self.assertFalse(again)
        self.assertEqual(saved["id"], duplicate["id"])
        self.store.action(saved["id"], saved["actions"][0]["id"], {"status": "done", "owner": "Buyer"})
        restored = Store(self.temp.name).suppliers()
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0]["actions"][0]["status"], "done")
        self.assertIsNone(restored[0]["legacy_scores"])

    def test_failed_live_search_does_not_silently_load_fixture(self):
        def empty(*args, **kwargs):
            return {"content": "No citations", "annotations": []}, {}
        self.client.complete = empty
        run_id = self.service.start({"company": "Acme"})
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            run = self.store.get(run_id)
            if run["status"] == "failed":
                break
            time.sleep(.01)
        self.assertEqual(run["status"], "failed")
        self.assertFalse(run["demo"])
        self.assertEqual(run["findings"], [])

    def test_demo_is_explicit_and_siemens_only(self):
        with self.assertRaises(ValueError):
            self.service.start({"company": "Acme", "demo": True})
        run = self.run_dossier(company="Siemens AG", demo=True, mode="deep")
        self.assertTrue(run["demo"])
        self.assertFalse(self.client.searches)
        self.assertTrue(all(f["severity"] == "unknown" for f in run["findings"]))
        answer = self.service.chat(run["id"], "Has the company breached sanctions?")
        self.assertEqual(answer["finding_ids"], [])
        self.assertIn("does not establish", answer["answer"])
        self.assertNotIn("source-bound observations", run["summary"])
        self.assertNotIn("> Historical", markdown_report(run))

    def test_low_confidence_never_increased_at_category_level(self):
        run = self.run_dossier()
        run["findings"][0]["confidence"] = "low"
        self.service.finish_report(run)
        category = next(c for c in run["categories"] if c["id"] == "operations")
        self.assertEqual(category["confidence"], "low")

    def test_deep_reconciliation_failure_retains_usable_partial_dossier(self):
        original = self.client.complete
        extraction_calls = 0
        def fail_second_extract(system, *args, **kwargs):
            nonlocal extraction_calls
            if not kwargs.get("search", False):
                extraction_calls += 1
                if extraction_calls == 2:
                    raise RuntimeError("Controlled provider failure")
            return original(system, *args, **kwargs)
        self.client.complete = fail_second_extract
        run = self.run_dossier(mode="deep")
        self.assertEqual(len(run["findings"]), 1)
        self.assertEqual(len(run["categories"]), 6)
        self.assertEqual(len(run["actions"]), 6)
        self.assertTrue(any("reconciliation failed" in gap.lower() for gap in run["gaps"]))

    def test_failed_category_search_recorded_as_partial_coverage(self):
        original = self.client.complete
        def fail_legal(system, prompt, **kwargs):
            if "Category: legal." in prompt:
                raise RuntimeError("Controlled search failure")
            return original(system, prompt, **kwargs)
        self.client.complete = fail_legal
        run = self.run_dossier()
        self.assertEqual(run["coverage"]["state"], "partial")
        self.assertIn("legal", run["coverage"]["failed_search_categories"])
        legal = next(c for c in run["categories"] if c["id"] == "legal")
        self.assertTrue(any("search failed" in gap for gap in legal["gaps"]))

    def test_chat_only_returns_selected_dossier_observations(self):
        run = self.run_dossier()
        answer = self.service.chat(run["id"], "What is supply exposure?")
        self.assertFalse(answer["new_research"])
        self.assertEqual(answer["source_ids"], ["S1"])
        self.assertIn(run["findings"][0]["detail"], answer["answer"])

    def test_action_partial_updates_do_not_overwrite_other_fields(self):
        run = self.run_dossier()
        supplier, _ = self.store.save_supplier(run["id"])
        action_id = supplier["actions"][0]["id"]
        self.store.action(supplier["id"], action_id, {"owner": "Buyer"})
        updated = self.store.action(supplier["id"], action_id, {"status": "done"})
        self.assertEqual(updated["owner"], "Buyer")
        updated = self.store.action(supplier["id"], action_id, {"owner": "Reviewer"})
        self.assertEqual(updated["status"], "done")

    def test_chat_preserves_evidence_status_and_answers_gaps_without_inference(self):
        run = self.run_dossier()
        run["findings"][0]["status"] = "alleged"
        self.store.put(run)
        answer = self.service.chat(run["id"], "What is supply exposure?")
        self.assertIn("Reported allegation; not established", answer["answer"])
        before = self.client.calls
        gaps = self.service.chat(run["id"], "What remains unknown?")
        self.assertIn(run["gaps"][0], gaps["answer"])
        self.assertEqual(self.client.calls, before)
        score = self.service.chat(run["id"], "What is the risk score?")
        self.assertIn("remain unknown", score["answer"])

    def test_extraction_retries_once_without_repeating_search(self):
        original = self.client.complete
        for failure in (ProviderLengthError({}), json.JSONDecodeError("truncated", "{", 1)):
            with self.subTest(failure=type(failure).__name__):
                extraction_calls = []
                before = len(self.client.searches)
                def limited(system, prompt, **kwargs):
                    if not kwargs.get("search", False):
                        extraction_calls.append(kwargs["tokens"])
                        if len(extraction_calls) == 1:
                            raise failure
                    return original(system, prompt, **kwargs)
                self.client.complete = limited
                run = self.run_dossier()
                self.assertEqual(extraction_calls, [10000, 14000])
                self.assertEqual(len(self.client.searches) - before, 6)
                self.assertEqual(run["schema_version"], "research-dossier-v1")
                self.assertTrue(any(event["stage"] == "extract_retry" for event in run["events"]))


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "state")
        self.service = ResearchService(self.store, FakeClient())
        web = Path(self.temp.name) / "web"
        web.mkdir()
        (web / "index.html").write_text("<h1>Workbench</h1>")
        (Path(self.temp.name) / ".env").write_text("SECRET=do-not-serve")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.service, web))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.service.executor.shutdown(wait=True)
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        data = response.read()
        status = response.status
        conn.close()
        return status, data

    def test_static_boundary_and_config_have_no_secret(self):
        self.assertEqual(self.request("GET", "/")[0], 200)
        for path in ("/../.env", "/%2e%2e/.env", "/.env", "/config/models.json", "/docs/supplier_risk_dataset.csv"):
            self.assertEqual(self.request("GET", path)[0], 404, path)
        status, data = self.request("GET", "/api/config")
        self.assertEqual(status, 200)
        self.assertNotIn(FakeClient.key.encode(), data)

    def test_cross_origin_host_json_body_and_malformed_request_rejected(self):
        body = json.dumps({"company": "Acme"})
        self.assertEqual(self.request("POST", "/api/research", body, {"Content-Type": "application/json", "Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request("GET", "/api/config", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("POST", "/api/research", body, {"Content-Type": "text/plain"})[0], 400)
        self.assertEqual(self.request("POST", "/api/research", "[]", {"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.request("POST", "/api/research", "{" * 17000, {"Content-Type": "application/json"})[0], 400)


if __name__ == "__main__":
    unittest.main()
