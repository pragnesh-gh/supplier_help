"""Build the disposable, fully offline supplier workbench. No dependencies."""
from pathlib import Path
import csv
import hashlib
import io
import json

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "docs/supplier_risk_dataset.csv"
raw = source.read_bytes()
reader = csv.reader(io.StringIO(raw.decode("utf-8-sig")))
columns = next(reader)
numeric = {i for i, key in enumerate(columns) if key.endswith("_Score") or key == "Total_Risk_Index" or key in {"Purchase Order Volume (EUR)", "Order Change Rate", "Supplier Delivery Rating", "Order Confirmation Rate"}}
# Only numeric source columns may be converted; names can contain punctuation.
rows = []
for row in reader:
    rows.append([float(value) if i in numeric and "." in value else int(value) if i in numeric else value for i, value in enumerate(row)])
payload = json.dumps({"columns": columns, "rows": rows, "sha256": hashlib.sha256(raw).hexdigest(), "source": "docs/supplier_risk_dataset.csv"}, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
template = (ROOT / "prototype/workbench.template.html").read_text(encoding="utf-8")
target = ROOT / "prototype/supplier-workbench.html"
target.write_text(template.replace("__DATA_PAYLOAD__", payload), encoding="utf-8")
print(f"Built {target.name}: {len(rows):,} rows, {target.stat().st_size:,} bytes; SHA256 {hashlib.sha256(raw).hexdigest()}")
