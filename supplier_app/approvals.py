"""Append-only local requests to negotiate, with evidence frozen at submission."""
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import uuid


class Approvals:
    def __init__(self, directory, data, research_store):
        self.path = Path(directory) / 'approvals.json'
        self.data = data
        self.rows = {row[0]: dict(zip(data['columns'], row)) for row in data['rows']}
        self.research_store = research_store
        self.lock = threading.Lock()

    @staticmethod
    def text(value, field, limit=4000, required=True):
        if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
            raise ValueError(f'{field} must be {"nonempty " if required else ""}text of at most {limit} characters')
        return value.strip()

    def _read(self):
        if not self.path.exists():
            return []
        saved = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(saved, list) or any(not isinstance(item, dict) for item in saved):
            raise ValueError('Saved approval requests could not be read; original file retained')
        return saved

    def list(self):
        with self.lock:
            return list(reversed(self._read()))

    def submit(self, values):
        if not isinstance(values, dict):
            raise ValueError('Approval request must be an object')
        result = {key: self.text(values.get(key), key, limit) for key, limit in
                  [('requester', 200), ('reviewer', 200), ('project', 300), ('rationale', 4000)]}
        result['scope'] = self.text(values.get('scope', ''), 'scope', 1000, required=False)
        candidates = values.get('candidates')
        if not isinstance(candidates, list) or not 3 <= len(candidates) <= 5:
            raise ValueError('An approval request requires 3 to 5 candidates')
        research = {'research:' + item['id']: item for item in self.research_store.suppliers()}
        seen, frozen = set(), []
        for item in candidates:
            if not isinstance(item, dict):
                raise ValueError('Each candidate must be an object')
            supplier_id = item.get('supplier_id')
            if not isinstance(supplier_id, str) or supplier_id not in self.rows and supplier_id not in research:
                raise ValueError('Each candidate must name a known supplier ID')
            if supplier_id in seen:
                raise ValueError('Approval candidates must be distinct')
            seen.add(supplier_id)
            notes = {key: self.text(item.get(key), key, 2000) for key in ['tradeoffs', 'negotiation_questions']}
            if supplier_id in self.rows:
                snapshot = {'kind': 'dataset', 'values': self.rows[supplier_id],
                            'source': self.data['source'], 'sha256': self.data['sha256'],
                            'augmentation': self.data['manifest']['augmentation'],
                            'notice': 'System, part and relationship tags are synthetic demo metadata. Total risk weights are not supplied.'}
            else:
                record = research[supplier_id]
                try:
                    dossier = self.research_store.get(record['run_id'])
                except KeyError:
                    raise ValueError(f'Research evidence for {supplier_id} is unavailable; restore its dossier before submitting') from None
                snapshot = {'kind': 'research', 'record': record, 'dossier': dossier,
                            'notice': 'Public research report, kept separate from the anonymised catalogue. Its score is not comparable to catalogue scores.'}
            frozen.append({'supplier_id': supplier_id, **notes, 'snapshot': snapshot})
        result.update(id=uuid.uuid4().hex, created_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                      status='awaiting_approval', purpose='approval_to_negotiate', candidates=frozen,
                      notice='Saved locally for review. No notification sent, authenticated approval granted, or supplier award made.')
        # JSON round-trip severs all mutable references to current catalog/research data.
        result = json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False))
        with self.lock:
            saved = self._read()
            saved.append(result)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(saved, ensure_ascii=False, allow_nan=False), encoding='utf-8')
            temporary.replace(self.path)
        return result
