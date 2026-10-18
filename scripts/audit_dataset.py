"""Validate the supplied CSV and write a reproducible, non-secret audit."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/supplier_risk_dataset.csv"


def audit():
    raw = SOURCE.read_bytes()
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        rows = list(reader)
    assert len(rows) == 10_000, "Expected 10,000 supplied suppliers"
    assert len({r["supplierID"] for r in rows}) == len(rows), "Duplicate supplier IDs"
    assert all(None not in r and all(v not in (None, "") for v in r.values()) for r in rows), "Missing or malformed cells"
    scores = [k for k in columns if k.endswith("_Score") or k == "Total_Risk_Index"]
    assert all(0 <= float(r[k]) <= 100 for r in rows for k in scores), "Out-of-range risk score"
    selected = ["SUPP_00012", "SUPP_00450", "SUPP_00731", "SUPP_00018"]
    report = {
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "rows": len(rows), "columns": columns, "unique_ids": len(rows), "missing_cells": 0,
        "risk_direction": "0 = no risk; 100 = maximum risk for all risk scores",
        "total_risk_levels": dict(Counter(r["Total_Risk_Index_Level"] for r in rows)),
        "score_ranges": {k: [min(float(r[k]) for r in rows), max(float(r[k]) for r in rows)] for k in scores},
        "challenge_examples": [r for r in rows if r["supplierID"] in selected],
        "limitations": ["Aggregate weights are not supplied", "No data as-of date", "No real-company identity mapping", "No country, component capability, qualification or unit-price fields", "Purchase order volume is historical exposure, not a quote"],
    }
    target = ROOT / "docs/data-audit.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Validated {len(rows):,} rows / {len(columns)} columns; audit: {target.relative_to(ROOT)}")


if __name__ == "__main__":
    audit()
