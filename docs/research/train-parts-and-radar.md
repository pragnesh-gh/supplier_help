# Train parts, synthetic suppliers, and six-axis radar

Prepared 18 October 2026. Bounded research: four primary sources, approximately five minutes. This note proposes a data contract; it does not implement enrichment or change the supplied CSV.

## Evidence and limits

- **S1 — ERA, LOC&PAS TSI application guide (2023):** structure (§4.2.2), wheelsets (§4.2.3.5.2), braking (§4.2.4), passenger items including doors and ventilation (§4.2.5), traction/electrical equipment (§4.2.8), and cab (§4.2.9) provide a rail-specific taxonomy foundation. [Official guide](https://www.era.europa.eu/system/files/2024-02/LOC-PAS_Guide-2023.pdf).
- **S2 — Alstom components portfolio:** identifies bogies, motors, dampers, brake friction, switchgear, traction/auxiliary converters, transformers, interiors, and train control/information systems. These support useful procurement subdivisions. [Manufacturer portfolio](https://www.alstom.com/solutions/components).
- **S3 — ERA, Common Safety Methods application guide:** §2.1.4 distinguishes codes of practice, comparison with similar systems, and explicit risk estimation. This older guidance provides conceptual context only. Our inference: a generic supplier radar cannot establish component safety, certification, or railway risk acceptance. [Official guide](https://www.era.europa.eu/system/files/2022-11/Guide%20for%20the%20application%20of%20the%20Common%20Safety%20Methods%20on%20risk%20assessment%20(EN).pdf).
- **S4 — OECD, Due Diligence Guidance for Responsible Business Conduct (2018):** covers adverse impacts involving workers, human rights, environment, bribery, consumers, and governance. This supports broader due diligence context, not these numerical axes or weights. [Official publication](https://www.oecd.org/en/publications/oecd-due-diligence-guidance-for-responsible-business-conduct_15f5f4b3-en.html).

The taxonomy below is a simplified application design informed by S1/S2, not an exhaustive engineering breakdown. None of these sources establishes supplier counts, supplier-to-part relationships, empirical market shares, these radar weights, or any anonymized supplier's qualification.

## Local input findings

Inspected [criteria descriptions](../risk_criteria_description.md) and [source CSV](../supplier_risk_dataset.csv): 10,000 rows, 46 columns, 10,000 distinct `supplierID` values. All supplied numeric risk scores are populated and within 0–100; `Total_Risk_Index` spans 6–93. There are no supplied part assignments, country names/codes, favorite flags, or previous-use records.

The criteria explicitly say **0 = no risk; 100 = maximum risk**. Therefore `Financial_Health_Score`, `Credit_Rating_Score`, and other positively named score fields remain risk values; do not invert them. Delivery and confirmation percentages are performance metrics, distinct from risk score columns.

## Train regions and exact illustrative quotas

Use ten selectable regions on an illustrative electric passenger train. Geometry is a schematic, not a specific vehicle configuration. Counts mean unique suppliers assigned to a primary subsystem, not component quantities, available capacity, verified suppliers, or spend.

| Stable `train_region_id` | Label / suggested visible location | Allowed `train_part_id` values | Synthetic quota |
|---|---|---|---:|
| `carbody` | Carbody & couplings / shell and vehicle ends | `body_structure`, `glazing`, `coupler` | 1,400 |
| `bogie_structure` | Bogies & suspension / undercarriage frames | `bogie_frame`, `suspension`, `damper` | 1,100 |
| `wheelsets` | Wheels & axles / wheels | `wheel`, `axle`, `axle_bearing` | 900 |
| `braking` | Braking / wheel-adjacent brake assemblies | `brake_disc`, `brake_actuator`, `brake_control` | 1,100 |
| `traction` | Traction / underfloor propulsion modules | `traction_motor`, `traction_converter`, `gearbox` | 1,200 |
| `electrical_auxiliary` | Power & auxiliaries / roof pickup and electrical boxes | `pantograph`, `transformer`, `auxiliary_converter`, `battery` | 1,100 |
| `control_cab` | Controls & cab / cab and control equipment | `train_control`, `driver_interface`, `onboard_communications` | 900 |
| `doors` | Passenger doors / side entrances | `door_leaf`, `door_drive`, `door_control` | 700 |
| `hvac` | HVAC / roof ventilation modules | `hvac_unit`, `air_filter`, `ventilation_fan` | 700 |
| `interiors` | Interiors / cutaway passenger space | `seat`, `interior_panel`, `passenger_information` | 900 |
| **Total** | | | **10,000** |

These quotas are chosen for demo coverage and varied counts. They are **synthetic allocation, not empirical market shares**. They do not depend on risk scores or imply real suppliers make these parts. Electrical boundary: traction converters belong to `traction`; auxiliary converters and transformers to `electrical_auxiliary`. Door/brake controllers stay with their functional subsystem. Passenger information stays with interiors; train-wide controls and communications stay with cab/control. Braking and wheelsets may overlap visually but remain disjoint data categories.

Proposed deterministic generation (`train-demo-v1`):

1. Sort all IDs by ascending SHA-256 hex of UTF-8 `train-demo-v1|region|{supplierID}`; break ties by ID. Assign consecutive blocks to quotas in table order.
2. Within each region, sort by SHA-256 of `train-demo-v1|part|{supplierID}` and cycle through that row's part IDs in listed order. This gives balanced illustrative parts without claiming observed distribution.
3. Independently sort all IDs using `train-demo-v1|favorite|{supplierID}`; mark the first 500 as favorites. Repeat using `train-demo-v1|previous|{supplierID}`; mark the first 1,500 as previously used. Overlap is allowed. These exact counts are product choices. Do not invent transaction dates, buyer identities, or qualification outcomes.
4. Restore original CSV row order. Freeze the algorithm and input SHA-256 in a manifest; a changed input or allocation requires a new version.

Hover **and keyboard focus** show region label, total supplier count, filtered count when applicable, and synthetic-data disclosure. Click/Enter selects the same region and filters the list. Map every visual mesh to `train_region_id`; multiple meshes can share one region. Use labelled controls for hidden/interior regions and small or overlapping parts. Counts derive from data, never hardcoded mesh labels. Default primary counts sum to 10,000; future secondary capabilities must not inflate them.

## Six radar axes: proposed mapping, not recovered source weights

Interpret the requested six as **financial, legal, country, people & safety, operations, reputation**. Combining people and safety is an explicit product interpretation; separating them would create seven axes. Each axis below is a weighted arithmetic mean of named source risk columns. Within-axis weights sum to 1.

| Axis ID / display label | Exact source mapping and proposed weights |
|---|---|
| `financial` / Financial | `Financial_Health_Score` 0.50 + `Credit_Rating_Score` 0.50 |
| `legal` / Legal & governance | `Compliance_Risk_Score` 0.70 + `Governance_Risk_Score` 0.30 |
| `country` / Country exposure | `Geopolitical_Risk_Score` 0.40 + `Political_Stability_Score` 0.40 + `Environmental_Exposure_Score` 0.20 |
| `people_safety` / People & safety | `Labor_Stability_Score` 0.40 + `Safety_Incident_Score` 0.60 |
| `operations` / Operations | `Operational_Resilience_Score` 0.40 + `Quality_Risk_Score` 0.30 + `Digital_Security_Score` 0.15 + `Sub_Tier_Visibility_Score` 0.15 |
| `reputation` / Reputation | `Media_Sentiment_Score` 0.50 + `Market_Sentiment_Score` 0.50 |

Rationale: direct measures receive more emphasis; equal weights apply where the local descriptions do not support prioritization. This is a transparent prototype heuristic, not a calibrated or validated risk model. Quality is assigned to operations to avoid double counting across axes; that does not imply defects lack safety implications. Country exposure is only a summary of provided scores: no supplier country can be inferred. People & safety lacks separate human-rights evidence.

Keep `Industry_Benchmark_Score`, `External_Intelligence_Score`, and `ESG_Performance_Score` in supplier details but exclude them from radar calculations: their broad/overlapping descriptions do not identify independent contributions to the six axes. This is a proposed choice, not evidence that they are unimportant. Keep PO value, order change/delivery/confirmation metrics, sourcing level, and supply-chain complexity available separately; no undisclosed conversion of percentages or categorical labels into risk points.

Preserve `Total_Risk_Index` and its existing level unchanged. Its original weights were not supplied, so neither these six axes nor their mean may be presented as its explanation or reconstruction. Do not create a new overall score by default. If later requested, an equal-axis mean must have its own name and disclosed 1/6 weights.

All radar axes use a fixed 0–100 scale with larger radius meaning **higher risk**. Show “Higher = more risk”; no implicit health/spider-area goodness interpretation. Compute with full precision, round only displayed values to one decimal. Avoid inferring thresholds for derived axes from the supplied `*_Level` strings.

For a missing or invalid component (including research-added suppliers), set the affected axis to `null`; do not substitute zero or silently renormalize. For a region's radar, average valid supplier axis values with equal supplier weights, independent of PO spend; return valid `n` per axis and total supplier count. Render nulls as unavailable rather than connecting across them. Label the result “Mean supplier risk”; it is not a component failure probability or safety determination (S3). Filtered aggregates must state their scope.

## Recommended data contract

Create a future derivative at `docs/supplier_risk_dataset_augmented.csv`; leave `docs/supplier_risk_dataset.csv` byte-for-byte unchanged. Preserve all 46 original headers, values, IDs, and row order; append:

| Appended CSV field | Type / rule |
|---|---|
| `train_region_id` | One of ten region enum values above; exactly one per original supplier |
| `train_part_id` | One allowed part ID within that region |
| `is_favorite_demo` | Literal `true` / `false`; synthetic initial state |
| `previously_used_demo` | Literal `true` / `false`; synthetic initial state |
| `assignment_provenance` | Constant `synthetic_demo` |
| `assignment_version` | Constant `train-demo-v1` |
| `relationship_provenance` | Constant `synthetic_demo` |
| `radar_mapping_version` | Constant `radar-v1` |
| `risk_financial`, `risk_legal`, `risk_country`, `risk_people_safety`, `risk_operations`, `risk_reputation` | Derived numbers 0–100, or empty for null; no early rounding |

Store labels, part-to-region membership, axis source weights, allocation quotas, algorithm, source-file hash, and generation version in a shared manifest, not repeated human-readable CSV descriptions. Runtime supplier identity remains `supplierID`.

Recommended view/API shape: `RegionSummary { regionId, totalSupplierCount, matchingSupplierCount, meanRisk: { financial, legal, country, people_safety, operations, reputation }, validCountByAxis, allocationVersion, radarMappingVersion }`. Each mean may be null. Supplier records expose original source fields, appended metadata, and the six derived values.

Persist buyer changes to favorites separately by supplier ID so reset can restore synthetic initial state; retain the `_demo` provenance. Previously used is a demo relationship tag, not a sourcing recommendation. New research-derived suppliers need distinct IDs and provenance, a selected primary region, nullable scores, and separate counts such as “10,000 demo + 1 research-added”; never rewrite the original cohort or assign fabricated risk values.

Future enrichment acceptance checks: source-file hash unchanged; exact ID/row preservation; 10,000 enriched rows; valid region/part membership; quotas sum correctly; 500 favorite and 1,500 previous-use flags; deterministic regeneration; axis outputs match manifest weights and preserve nulls. No augmentation has been generated by this research task.

## Unknowns to retain explicitly

Original total-index weights, score calibration, observation dates, underlying evidence, supplier geography, actual part capability, certification/qualification, relationships, capacity, and spend by part are unknown. Source descriptions alone do not establish empirical accuracy or current status. A future operational use needs verified supplier mappings, user-owned relationship history, dated evidence, and approved scoring methodology. Rail-source taxonomy support does not validate the synthetic allocation or radar.
