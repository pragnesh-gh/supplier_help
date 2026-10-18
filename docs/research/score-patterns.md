# What the supplied scores can teach the research agent

Analysis of the original, unchanged 10,000-row, 46-column dataset. Reproduce with `python scripts/analyze_research_patterns.py`; exact results and the source SHA-256 are in [score-patterns.json](score-patterns.json).

The user identifies the scores as synthetic. The file has 18 component score columns, a supplied Total Risk Index, 19 corresponding level columns, identifiers, and six operational metrics. It contains no source links, observation dates, countries, verified real-company mappings, or component qualification evidence.

## Patterns actually observed

- Every supplied score/level pair uses the same observed bands: 0–24 Low, 25–49 Medium, 50–74 High, 75–100 Critical. There are zero mismatches across the 190,000 supplied pairs. These describe this file; they do not validate risk thresholds for real suppliers.
- The unweighted mean of the 18 component scores correlates strongly with the supplied total (Pearson r = 0.991631). Its mean absolute difference is 1.4447 points, its largest absolute difference is 6.833333, and rounding that mean reproduces only 2,186 of 10,000 totals. It is therefore not the supplied formula.
- Operations-related fields have some of the strongest individual correlations with the total: Operational Resilience 0.787850, Quality Risk 0.783458, Sub-Tier Visibility 0.767429, and Digital Security 0.762254. Country-related fields have weaker correlations: Geopolitical 0.395558, Political Stability 0.392792, and Environmental Exposure 0.389714. Correlation does not establish a weight or causal contribution.
- All 10,000 supplier IDs and names are unique. They are anonymized entities, not a directory for matching real company names.

## How to use this

Reuse the category vocabulary and the explicit direction, **higher score = higher risk**, for browsing the supplied cohort. Even positively named Financial Health and Credit Rating fields follow that direction. Delivery and confirmation percentages remain operational performance percentages.

Use the six-category mapping as a research checklist. The latest v2 brief selects equal weights within each axis for its illustrative radar, superseding the preliminary weighted mapping in the earlier rail research note. That mapping groups columns; it does not recreate the original total or establish a real-world model.

For a researched company, store claims, sources, concern, confidence, coverage, open questions, and actions. Keep the supplied total and all six numerical axes `null`. A qualitative concern is an evidence-triage judgment with reasons, not a substitute 0–100 score. No result, inaccessible evidence, and an unresearched category must never become “low risk.”

## What would make future scoring defensible

Start with real dated observations tied to the exact legal entity and relevant sites/components. Define each feature, source eligibility, missing-data policy, time window, and outcome of interest. Have a domain owner approve severity and materiality rules. Validate proposed thresholds and weights against independent outcomes, inspect error cases and bias, version the method, and retain human review. Synthetic score correlations can help test a UI, but cannot supply this calibration.

## Separate outputs

1. **Research dossier:** scope, plan, searches, sources and excerpts, findings and their status, contradictions, coverage and gaps.
2. **Risk report:** evidence-based category summaries, procurement implications, mitigations and unresolved diligence. A report is not supplier approval.
3. **Research supplier list:** a separate durable catalog of researched entities with report provenance and unknown numerical scores.
4. **Diligence queue:** the outstanding evidence requests and mitigations with owner and open/done status. Closing a task does not prove a risk is resolved.
