"""Inline the validated derivative and pinned single-file train module, offline."""
from pathlib import Path
import csv
import hashlib
import io
import json
import re
from augment_dataset import ROOT, SOURCE_SHA256, generate

def main():
    expected, expected_manifest = generate()
    derivative = ROOT / 'docs/supplier_risk_dataset_augmented.csv'
    manifest_path = ROOT / 'docs/train-demo-v1.manifest.json'
    assert derivative.read_bytes() == expected, 'Regenerate augmentation first'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    assert {k: v for k, v in manifest.items() if k != 'build'} == expected_manifest
    vendor_path = ROOT / 'prototype/v2/vendor/three.module.min.js'
    vendor_raw = vendor_path.read_bytes()
    assert hashlib.sha256(vendor_raw).hexdigest() == 'ce1fa418de16a19495a9f72495580e3015d7745c296d3ce0485897f902ddedfb', 'Pinned Three.js r170 vendor hash mismatch'
    vendor = vendor_raw.decode('utf-8')
    # Mask comments and strings before detecting static/dynamic imports. Export
    # declarations are allowed in the single inline module.
    masked = re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`', ' ', vendor)
    assert not re.search(r'\bimport\b', masked), 'Vendor must be a self-contained module with no imports'
    assert re.search(r'REVISION\s*=\s*["\']170["\']', vendor) or re.search(r'\b\w+\s*=\s*["\']170["\']', vendor), 'Expected pinned Three.js r170'
    renderer = (ROOT / 'prototype/v2/train-scene.js').read_text(encoding='utf-8')
    assert not re.search(r'(?m)^\s*import\s', renderer), 'Renderer must use vendor bindings in the same module'
    manifest['build'] = {'three_version': '0.170.0', 'three_revision': '170',
                         'vendor_path': 'prototype/v2/vendor/three.module.min.js',
                         'vendor_sha256': hashlib.sha256(vendor_raw).hexdigest(),
                         'renderer_sha256': hashlib.sha256(renderer.encode()).hexdigest()}
    reader = csv.reader(io.StringIO(expected.decode('utf-8')))
    columns = next(reader)
    numeric = {i for i, key in enumerate(columns) if key.endswith('_Score') or key.startswith('risk_') or key == 'Total_Risk_Index' or key in {'Purchase Order Volume (EUR)', 'Order Change Rate', 'Supplier Delivery Rating', 'Order Confirmation Rate'}}
    booleans = {columns.index('is_favorite_demo'), columns.index('previously_used_demo')}
    rows = [[(None if not v else float(v) if '.' in v or 'e' in v.lower() else int(v)) if i in numeric else v == 'true' if i in booleans else v for i, v in enumerate(row)] for row in reader]
    assert len(rows) == 10000 and len(columns) == 60
    payload = {'columns': columns, 'rows': rows, 'source': 'docs/supplier_risk_dataset.csv', 'sha256': SOURCE_SHA256, 'manifest': manifest}
    data_json = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
    template = (ROOT / 'prototype/train-workbench-v2.template.html').read_text(encoding='utf-8')
    assert template.count('__DATA_PAYLOAD__') == 1 and template.count('__TRAIN_MODULE__') == 1
    module = (vendor + '\n;\n' + renderer).replace('</script', '<\\/script')
    result = template.replace('__DATA_PAYLOAD__', data_json).replace('__TRAIN_MODULE__', module)
    assert '__DATA_PAYLOAD__' not in result and '__TRAIN_MODULE__' not in result
    assert hashlib.sha256((ROOT / 'docs/supplier_risk_dataset.csv').read_bytes()).hexdigest() == SOURCE_SHA256
    target = ROOT / 'prototype/train-risk-v2.html'
    target.write_text(result, encoding='utf-8')
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Built {target.name}: {len(rows):,} rows / {len(columns)} columns; {target.stat().st_size:,} bytes; Three.js r170 SHA256 {manifest["build"]["vendor_sha256"]}')

if __name__ == '__main__':
    main()
