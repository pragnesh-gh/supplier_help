"""Reproducible illustrative enrichment; original CSV is never written."""
from pathlib import Path
import csv
import hashlib
import io
import json
import math
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'train-demo-v1'
SOURCE_SHA256 = '2c77a672130039fd6ba420527e51cc9d915239de674064f832e7db659d3956bc'
REGION_SPECS = [
    ('carbody', 'Carbody & couplings', 'Carbody', 1400, 'body_structure glazing coupler'),
    ('bogie_structure', 'Bogies & wheelsets', 'Bogies', 2000, 'bogie_frame suspension damper wheel axle axle_bearing'),
    ('braking', 'Braking', 'Braking', 1100, 'brake_disc brake_actuator brake_control'),
    ('traction', 'Traction', 'Traction', 1200, 'traction_motor traction_converter gearbox'),
    ('electrical_auxiliary', 'Power & auxiliaries', 'Power & aux', 1100, 'pantograph transformer auxiliary_converter battery'),
    ('control_cab', 'Controls & cab', 'Controls', 900, 'train_control driver_interface onboard_communications'),
    ('doors', 'Passenger doors', 'Doors', 700, 'door_leaf door_drive door_control'),
    ('hvac', 'HVAC', 'HVAC', 700, 'hvac_unit air_filter ventilation_fan'),
    ('interiors', 'Interiors', 'Interiors', 900, 'seat interior_panel passenger_information'),
]
AXIS_SPECS = [
    ('financial', 'Financial (derived)', 'Financial_Health_Score Credit_Rating_Score'),
    ('legal', 'Legal & governance', 'Compliance_Risk_Score Governance_Risk_Score'),
    ('country', 'Country exposure', 'Geopolitical_Risk_Score Political_Stability_Score Environmental_Exposure_Score'),
    ('people_safety', 'People & safety', 'Labor_Stability_Score Safety_Incident_Score'),
    ('operations', 'Operations', 'Operational_Resilience_Score Quality_Risk_Score Digital_Security_Score Sub_Tier_Visibility_Score'),
    ('reputation', 'Reputation', 'Media_Sentiment_Score Market_Sentiment_Score'),
]
METADATA = ['train_region_id', 'train_part_id', 'is_favorite_demo', 'previously_used_demo', 'assignment_provenance', 'assignment_version', 'relationship_provenance', 'radar_mapping_version']

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def ordered(ids, purpose):
    return sorted(ids, key=lambda sid: (digest(f'{VERSION}|{purpose}|{sid}'.encode()), sid))

def axis_value(row, components):
    try:
        values = [float(row[c['field']]) for c in components]
    except (KeyError, TypeError, ValueError):
        return None
    if any(not math.isfinite(v) or not 0 <= v <= 100 for v in values):
        return None
    return sum(values) / len(values)

def generate():
    source = ROOT / 'docs/supplier_risk_dataset.csv'
    raw = source.read_bytes()
    assert digest(raw) == SOURCE_SHA256, 'Source changed: freeze a new allocation version before proceeding'
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    columns = reader.fieldnames
    original = list(reader)
    assert len(columns) == 46 and len(original) == 10000
    ids = [r['supplierID'] for r in original]
    assert len(set(ids)) == 10000
    regions = [{'id': rid, 'label': label, 'shortLabel': short, 'quota': quota,
                'parts': [{'id': p, 'label': p.replace('_', ' ').capitalize()} for p in parts.split()]}
               for rid, label, short, quota, parts in REGION_SPECS]
    axes = [{'id': aid, 'label': label, 'field': 'risk_' + aid,
             'components': [{'field': f, 'weight': 1 / len(fields.split())} for f in fields.split()]}
            for aid, label, fields in AXIS_SPECS]
    ranked = ordered(ids, 'region')
    assignments, cursor = {}, 0
    for region in regions:
        for sid in ranked[cursor:cursor + region['quota']]:
            assignments[sid] = region['id']
        cursor += region['quota']
    challenges = ['SUPP_00012', 'SUPP_00450', 'SUPP_00731']
    overrides = []
    for sid in challenges:
        before = assignments[sid]
        if before == 'doors':
            continue
        other = next(i for i in ranked if assignments[i] == 'doors' and i not in challenges)
        assignments[sid], assignments[other] = 'doors', before
        overrides.append({'id': sid, 'from': before, 'to': 'doors', 'swappedWith': other})
    parts = {}
    for region in regions:
        members = ordered([i for i in ids if assignments[i] == region['id']], 'part')
        for index, sid in enumerate(members):
            parts[sid] = region['parts'][index % len(region['parts'])]['id']
    favorites, previous = set(ordered(ids, 'favorite')[:500]), set(ordered(ids, 'previous')[:1500])
    fields = columns + METADATA + [a['field'] for a in axes]
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    enriched = []
    for row in original:
        sid = row['supplierID']
        record = dict(row, train_region_id=assignments[sid], train_part_id=parts[sid],
                      is_favorite_demo=str(sid in favorites).lower(), previously_used_demo=str(sid in previous).lower(),
                      assignment_provenance='synthetic_demo', assignment_version=VERSION,
                      relationship_provenance='synthetic_demo', radar_mapping_version='radar-v1-equal')
        for axis in axes:
            record[axis['field']] = axis_value(row, axis['components'])
        enriched.append(record)
        writer.writerow(record)
    augmented = output.getvalue().encode('utf-8')
    assert Counter(assignments.values()) == {r['id']: r['quota'] for r in regions}
    assert all(assignments[i] == 'doors' for i in challenges)
    assert len(favorites) == 500 and len(previous) == 1500
    parsed = list(csv.DictReader(io.StringIO(augmented.decode())))
    assert [[r[c] for c in columns] for r in parsed] == [[r[c] for c in columns] for r in original]
    for row, record in zip(original, parsed):
        region = next(r for r in regions if r['id'] == record['train_region_id'])
        assert record['train_part_id'] in {p['id'] for p in region['parts']}
        for axis in axes:
            expected = axis_value(row, axis['components'])
            assert math.isclose(float(record[axis['field']]), expected, abs_tol=1e-12)
    manifest = {
        'version': VERSION, 'radar_mapping_version': 'radar-v1-equal',
        'regions': regions, 'axes': axes, 'overrides': overrides,
        'source_sha256': SOURCE_SHA256, 'augmented_sha256': digest(augmented),
        'source': {'path': 'docs/supplier_risk_dataset.csv', 'sha256': SOURCE_SHA256, 'rows': 10000, 'columns': 46},
        'augmentation': {'path': 'docs/supplier_risk_dataset_augmented.csv', 'sha256': digest(augmented), 'rows': 10000, 'columns': len(fields)},
        'algorithm': {'hash': 'SHA-256', 'encoding': 'UTF-8', 'seed': VERSION,
            'region': 'Sort ascending SHA-256(train-demo-v1|region|supplierID), then ID; assign consecutive region quota blocks.',
            'overrides': 'For each challenge ID in listed order, swap with first region-hash-ordered non-challenge doors member; then assign parts.',
            'part': 'Within final region sort SHA-256(train-demo-v1|part|supplierID), then ID; cycle listed parts.',
            'favorite': 'First 500 IDs sorted by SHA-256(train-demo-v1|favorite|supplierID), then ID.',
            'previous': 'First 1500 IDs sorted by SHA-256(train-demo-v1|previous|supplierID), then ID.',
            'output': 'Restore original source row order; retain all original values as strings in derivative CSV.'},
        'provenance': {'assignment': 'synthetic_demo', 'relationships': 'synthetic_demo',
            'disclosure': 'Illustrative assignments and quotas are product choices, independent of risk; they are not verified capability, market shares or qualification.',
            'radar': 'Equal arithmetic mean of listed source scores; prototype assumption, not a validated model. Higher means more risk. Missing/invalid component yields null; no renormalization. Original Total_Risk_Index is unchanged and its weights are unknown.',
            'taxonomy_sources': ['https://www.era.europa.eu/system/files/2024-02/LOC-PAS_Guide-2023.pdf', 'https://www.alstom.com/solutions/components'],
            'decision': 'docs/prototype-v2-brief.md: Final pre-implementation decisions'},
        'demo_counts': {'favorites': 500, 'previously_used': 1500},
    }
    assert source.read_bytes() == raw
    return augmented, manifest

def main():
    augmented, manifest = generate()
    again, repeated = generate()
    assert augmented == again and manifest == repeated, 'Non-deterministic generation'
    (ROOT / 'docs/supplier_risk_dataset_augmented.csv').write_bytes(augmented)
    (ROOT / 'docs/train-demo-v1.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Validated 10,000 rows, 46 preserved columns, 9 quotas, 500 favorites, 1,500 previous; {len(manifest["overrides"])} swaps. Source {SOURCE_SHA256}')

if __name__ == '__main__':
    main()
