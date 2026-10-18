"""Explicit historical fixture. These summaries are not live source quotations."""
from .core import now


def apply_demo(run):
    sources = [
        ("Siemens Report 2025", "https://assets.new.siemens.com/siemens/assets/api/uuid:428ea18a-e7ab-4f93-a160-33908f1c3540/Siemens-Annual-Report-2025.pdf#page=28", "December 2025 (exact publication day not established)",
         "Saved fixture paraphrase: Siemens identifies cybersecurity verification difficulty across distributed suppliers, critical single-source supply exposure, and cost/execution exposure on long-term projects. See printed pages 26–27, PDF pages 28–29."),
        ("Siemens Mobility cybersecurity standards and supply chain management", "https://www.mobility.siemens.com/global/en/portfolio/digital-solutions-software/cybersecurity/certification-standards.html", None,
         "Saved fixture paraphrase: Siemens Mobility describes supplier verification according to criticality, including declarations, self-assessments, evidence, contractual requirements and software bills of materials."),
        ("Siemens SCM Downloadcenter", "https://www.siemens.com/en-us/company/about/supply-chain-management/scm-downloadcenter/", None,
         "Saved fixture paraphrase: The SCM page lists cybersecurity rules for business partners dated July 2026. The revision month is not the publication date of the whole page; implementation was not audited."),
    ]
    run["sources"] = [{"id": f"S{i}", "title": title, "url": url, "publisher": "Siemens (corporate disclosure)",
         "published_at": date, "accessed_at": "2026-10-18 (fixture source check)", "excerpt": excerpt,
         "kind": "saved_fixture_summary", "verification": "Historical paraphrase from docs/research/company-fixture.md, not a verbatim source quotation"}
         for i, (title, url, date, excerpt) in enumerate(sources, 1)]
    rows = [
        ("Supplier cybersecurity verification", "Siemens' annual report discloses potential cybersecurity disruption and supplier-verification difficulty. This is a company-disclosed exposure, not an established incident.", "Check current cybersecurity evidence for the exact supplier and component.", ["S1", "S2", "S3"]),
        ("Critical supply concentration", "The annual report discusses potential bottlenecks, export restrictions, delays and concentration in single-source critical components. No current shortage is established by this fixture.", "Request component-specific alternate-source and continuity evidence.", ["S1"]),
        ("Long-term project delivery exposure", "The annual report describes cost, execution, partner-performance and penalty exposure on long-term projects. This does not establish failure of a specific contract.", "Review contract-specific capacity, schedule assumptions and change-control terms.", ["S1"]),
    ]
    run["findings"] = [{"id": f"F{i}", "category": "operations", "title": title, "detail": detail,
         "severity": "unknown", "confidence": "medium", "status": "disclosed", "source_ids": source_ids,
         "evidence": [{"source_id": source_ids[0], "quote": "Historical fixture paraphrase — open the original source to verify the exact wording."}],
         "follow_up": follow_up} for i, (title, detail, follow_up, source_ids) in enumerate(rows, 1)]
    run["entity"] = {"requested_name": "Siemens AG", "verification": "Saved fixture identifies Siemens AG / Siemens Group; rail assurance guidance is Siemens Mobility-specific"}
    run["gaps"] = ["This saved example covers three operational disclosures only; the other five categories need live research.",
         "Rail assurance guidance describes a company-stated process; it does not prove that a specific supplier passed verification.",
         "Historical 2025 annual report disclosures do not establish current status."]
    run["events"].append({"at": now(), "stage": "saved_example", "message": "Loaded explicitly labeled historical Siemens AG fixture. No web search or inference performed."})
    if run["mode"] == "deep":
        run["events"].append({"at": now(), "stage": "follow_up", "message": "Saved branch: cybersecurity disclosure → Siemens Mobility assurance process → July 2026 rules listing. Process evidence found; supplier-specific evidence remains needed."})
