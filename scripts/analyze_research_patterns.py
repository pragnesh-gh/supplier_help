"""Describe synthetic CSV patterns, never train or calibrate real supplier scores."""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/supplier_risk_dataset.csv"


def correlation(left, right):
    lm, rm = mean(left), mean(right)
    numerator = sum((a - lm) * (b - rm) for a, b in zip(left, right))
    denominator = math.sqrt(sum((a - lm) ** 2 for a in left) * sum((b - rm) ** 2 for b in right))
    return numerator / denominator if denominator else None


def analyze():
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    scores = [field for field in fields if field.endswith("_Score")]
    target = [float(row["Total_Risk_Index"]) for row in rows]
    equal_mean = [mean(float(row[field]) for field in scores) for row in rows]
    errors = [abs(a - b) for a, b in zip(equal_mean, target)]
    score_values = {field: [float(row[field]) for row in rows] for field in scores}
    levels = {}
    labels = ("Low", "Medium", "High", "Critical")
    for field in ["Total_Risk_Index"] + scores:
        groups = {}
        mismatches = 0
        for row in rows:
            value = float(row[field])
            label = row[field + "_Level"]
            groups.setdefault(label, []).append(value)
            expected = labels[min(3, int(value // 25))]
            mismatches += label != expected
        levels[field] = {
            "observed_ranges": {label: [min(values), max(values)] for label, values in groups.items()},
            "quartile_bucket_mismatches": mismatches,
        }
    return {
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "rows": len(rows), "columns": len(fields), "component_score_count": len(scores),
        "identity": {"unique_ids": len({row["supplierID"] for row in rows}),
                     "unique_names": len({row["Supplier Name"] for row in rows})},
        "total_risk_levels": dict(Counter(row["Total_Risk_Index_Level"] for row in rows)),
        "correlation_with_total": {field: round(correlation(values, target), 6)
                                   for field, values in score_values.items()},
        "equal_mean_diagnostic": {
            "description": "Unweighted mean of the 18 component score columns; descriptive diagnostic only",
            "correlation_with_total": round(correlation(equal_mean, target), 6),
            "mean_absolute_error": round(mean(errors), 6),
            "maximum_absolute_error": round(max(errors), 6),
            "rounded_exact_match_count": sum(round(a) == b for a, b in zip(equal_mean, target)),
        },
        "label_pattern": {"candidate": "[0,25) Low; [25,50) Medium; [50,75) High; [75,100] Critical",
                          "fields": levels},
        "limits": [
            "Synthetic scores are not observed adverse outcomes or labels for real companies.",
            "Correlation and bucket agreement do not recover original total-index weights.",
            "No observation dates, evidence URLs, real identity mapping, country or component qualification exist.",
            "Do not apply these descriptive patterns to new research records or fill unknown scores with zero.",
        ],
    }


if __name__ == "__main__":
    result = analyze()
    destination = ROOT / "docs/research/score-patterns.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("rows", "columns", "component_score_count", "identity", "equal_mean_diagnostic", "correlation_with_total")}, indent=2))
    print("Level bucket mismatches:", sum(field["quartile_bucket_mismatches"] for field in result["label_pattern"]["fields"].values()))
