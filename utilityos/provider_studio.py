"""Authenticated local setup, selected-corpus validation and explicit activation."""
from collections import Counter
from decimal import Decimal
from . import __version__, SCHEMA_VERSION
from .extraction_schema import MONEY_FIELDS, NUMBER_FIELDS
from .intake_storage import get_extraction, reviewed_values, differences
from .parsers import ValidationError, UNITS, text
from .pdf_extract import task
from .provider_rules import definition, extract_layout, digest
from . import provider_storage as journal
from .storage import read_source
from .review_data import payload as stored_payload


def fail(code):
    raise ValidationError(code)


def same(field, left, right):
    if left is None or right is None:
        return left == right
    if field.split('.')[-1] in MONEY_FIELDS | NUMBER_FIELDS:
        try:
            return Decimal(left) == Decimal(right)
        except (ValueError, ArithmeticError):
            return False
    return left == right


class ProviderStudio:
    def __init__(self, ledger):
        self.ledger, self.store = ledger, ledger.store

    def _registry(self, db):
        result = journal.registry(db)
        if result[3]:
            fail('LOCAL_TEMPLATE_DAMAGED_MANUAL_REVIEW')
        return result[:3]

    def _layout(self, db, layout_id):
        providers, layouts, rows = self._registry(db)
        layout = next((row for row in layouts if row['id'] == layout_id), None)
        if not layout:
            fail('LOCAL_LAYOUT_NOT_FOUND')
        provider = next((row for row in providers if row['id'] == layout['provider_id']), None)
        if not provider:
            fail('LOCAL_TEMPLATE_DAMAGED_MANUAL_REVIEW')
        return provider, layout, rows

    def observe(self, document_id):
        if type(document_id) is not int or document_id < 1:
            fail('PDF_SOURCE_REQUIRED')
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE id=? AND extension='.pdf'", (document_id,)).fetchone()
            if not row:
                fail('PDF_SOURCE_REQUIRED')
            raw = read_source(self.store, row)
        result = task(raw, action='observe', model_dir=self.ledger.ocr_model_dir)
        if 'adapter_version' not in result:
            # A fixed, source-free error leaves normal manual entry untouched.
            fail('LOCAL_OBSERVATIONS_UNAVAILABLE_USE_MANUAL_ENTRY')
        return result

    def documents(self):
        with self.store.connect() as db:
            return [dict(row) for row in db.execute('''SELECT d.id,d.filename,s.id staged_id,s.status
                FROM documents d JOIN staged s ON s.document_id=d.id WHERE d.extension='.pdf'
                AND s.id=(SELECT MAX(s2.id) FROM staged s2 WHERE s2.document_id=d.id)
                ORDER BY d.id DESC LIMIT 500''')]

    def create_provider(self, data):
        if set(data) != {'label', 'commodity'} or not isinstance(data['label'], str):
            fail('LOCAL_PROVIDER_FIELDS_INVALID')
        label = text(data['label'])
        if not label or len(label) > 120 or not isinstance(data['commodity'], str) or data['commodity'] not in UNITS:
            fail('LOCAL_PROVIDER_FIELDS_INVALID')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            providers, _, _ = self._registry(db)
            if len(providers) >= 100:
                fail('LOCAL_PROVIDER_LIMIT')
            if any(row['label'].casefold() == label.casefold() for row in providers):
                fail('LOCAL_PROVIDER_ALREADY_EXISTS')
            return journal.append(db, 'provider', {'label': label, 'commodity': data['commodity']})

    def save_layout(self, provider_id, data):
        if set(data) - {'definition', 'parent_layout_id', 'expected_version'}:
            fail('LOCAL_LAYOUT_FIELDS_INVALID')
        spec = definition(data.get('definition'))
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            providers, layouts, _ = self._registry(db)
            provider = next((row for row in providers if row['id'] == provider_id), None)
            if not provider:
                fail('LOCAL_PROVIDER_NOT_FOUND')
            previous = [row for row in layouts if row['provider_id'] == provider_id]
            latest = max((row['version'] for row in previous), default=0)
            if type(data.get('expected_version')) is not int or data['expected_version'] != latest:
                fail('LOCAL_LAYOUT_STALE_RELOAD')
            parent = data.get('parent_layout_id')
            if parent is not None and parent not in {row['id'] for row in previous}:
                fail('LOCAL_LAYOUT_PARENT_INVALID')
            if len(layouts) >= 1000:
                fail('LOCAL_LAYOUT_LIMIT')
            if spec.quantity_treatment == 'delivery' and provider['commodity'] not in {'heating_oil', 'propane'}:
                fail('LOCAL_DELIVERY_COMMODITY_INVALID')
            created = journal.append(db, 'layout', {'version': latest + 1, 'parent_layout_id': parent,
                'provenance': 'staff_setup', 'definition': spec.model_dump(mode='json')}, parent_id=provider_id)
            journal.append(db, 'state', {'state': 'draft', 'validation_id': None}, parent_id=created['id'])
            return self._layout(db, created['id'])[1]

    def preview(self, provider_id, document_id, value, layout_id=None):
        spec = definition(value)
        with self.store.connect() as db:
            providers, _, _ = self._registry(db)
            provider = next((p for p in providers if p['id'] == provider_id), None)
            if provider is None:
                fail('LOCAL_PROVIDER_NOT_FOUND')
            layout = self._layout(db, layout_id)[1] if layout_id else {
                'id': '0' * 32, 'definition': spec.model_dump(mode='json'), 'hash': digest(spec.model_dump(mode='json'))}
        extraction = extract_layout(self.observe(document_id), provider, layout)
        from .extraction import proposed_bill
        return {'extraction': extraction, 'payload': proposed_bill(extraction),
                'preview_only': True, 'approved_history_unchanged': True}

    def _sample(self, db, document_id, provider):
        if type(document_id) is not int or document_id < 1:
            fail('LOCAL_VALIDATION_DOCUMENT_INVALID')
        row = db.execute('''SELECT s.* FROM staged s JOIN bills b ON b.staged_id=s.id
            JOIN documents d ON d.id=s.document_id WHERE s.document_id=? AND d.extension='.pdf'
            AND b.status!='cancelled' AND s.status='approved' ORDER BY b.id DESC LIMIT 1''', (document_id,)).fetchone()
        if not row:
            fail('LOCAL_VALIDATION_REQUIRES_APPROVED_PDFS')
        bill = stored_payload(row, db)
        if bill['provider'] != provider['label'] or any(line['commodity'] != provider['commodity'] for line in bill['lines']):
            fail('LOCAL_VALIDATION_PROVIDER_OR_COMMODITY_MISMATCH')
        original = get_extraction(db, document_id)
        if not original:
            fail('LOCAL_VALIDATION_REQUIRES_REVIEW_EVIDENCE')
        values = reviewed_values(db, row, original, bill)
        source = db.execute('SELECT sha256 FROM documents WHERE id=?', (document_id,)).fetchone()[0]
        snapshot = {'document_id': document_id, 'staged_id': row['id'], 'revision': row['revision'],
                    'source_hash': source, 'review_hash': digest({'bill': bill, 'details': values})}
        return snapshot, values, len(bill['lines']), original

    def validate(self, layout_id, document_ids):
        if (not isinstance(document_ids, list) or not 1 <= len(document_ids) <= 10 or
                any(type(value) is not int for value in document_ids) or len(set(document_ids)) != len(document_ids)):
            fail('LOCAL_VALIDATION_SELECT_ONE_TO_TEN_DISTINCT_PDFS')
        with self.store.connect() as db:
            provider, layout, _ = self._layout(db, layout_id)
            samples = [self._sample(db, identifier, provider) for identifier in sorted(document_ids)]
        counts, evidence = {}, Counter()
        drift, failed_required = 0, 0
        for snapshot, reviewed, service_count, original in samples:
            candidate = extract_layout(self.observe(snapshot['document_id']), provider, layout)
            if candidate['layout_state'] != 'known':
                drift += 1
            actual_count = len({key.split('.')[1] for key in candidate['fields'] if key.startswith('services.')})
            if actual_count != service_count:
                failed_required += 1
            for rule in layout['definition']['rules']:
                paths = [rule['field'].replace('*', str(i)) for i in range(service_count)] if '*' in rule['field'] else [rule['field']]
                for path in paths:
                    field = candidate['fields'].get(path, {'value': None, 'state': 'missing'})
                    target, value = reviewed.get(path), field['value']
                    stats = counts.setdefault(rule['field'], {'tested': 0, 'exact': 0, 'missing': 0,
                        'corrected': 0, 'unit_conflicts': 0, 'manual_entry': 0})
                    stats['tested'] += 1
                    exact = same(path, value, target)
                    stats['exact'] += int(exact)
                    stats['missing'] += int(value is None and target is not None)
                    stats['corrected'] += int(not exact and value is not None)
                    stats['unit_conflicts'] += int(path.endswith('_unit') and (not exact or field['state'] == 'conflict'))
                    stats['manual_entry'] += int(original['fields'].get(path, {}).get('value') is None and target is not None)
                    evidence[field['state']] += 1
                    if rule['required'] and (not exact or value is None or target is None):
                        failed_required += 1
        summary = {'documents_tested': len(samples), 'fields': counts, 'layout_drift': drift,
                   'required_failures': failed_required, 'evidence_states': dict(evidence),
                   'eligible': len(samples) >= 2 and drift == 0 and failed_required == 0,
                   'scope': 'selected_approved_documents_only'}
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._layout(db, layout_id) # Fail closed if corruption appeared during observation.
            for snapshot, _, _, _ in samples:
                if self._sample(db, snapshot['document_id'], provider)[0] != snapshot:
                    fail('LOCAL_VALIDATION_REVIEW_CHANGED_RETRY')
            return journal.append(db, 'validation', {'samples': [sample[0] for sample in samples],
                                  'summary': summary}, parent_id=layout_id)

    def change_state(self, layout_id, state, data):
        if set(data) - {'state_id', 'validation_id', 'acknowledge'} or data.get('acknowledge') is not True:
            fail('LOCAL_LAYOUT_CONFIRMATION_REQUIRED')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            provider, layout, _ = self._layout(db, layout_id)
            if data.get('state_id') != layout['state_id']:
                fail('LOCAL_LAYOUT_STALE_RELOAD')
            if layout['state'] == 'retired' or state == layout['state']:
                fail('LOCAL_LAYOUT_STATE_TRANSITION_INVALID')
            validation = layout['validation']
            if state == 'active':
                _, all_layouts, _ = self._registry(db)
                if sum(row['state'] == 'active' and row['provider_id'] == provider['id'] for row in all_layouts) >= 5:
                    fail('LOCAL_ACTIVE_LAYOUT_LIMIT_RETIRE_UNUSED')
                if (not validation or data.get('validation_id') != validation['id'] or
                        validation['summary']['eligible'] is not True):
                    fail('LOCAL_LAYOUT_VALIDATE_TWO_APPROVED_SOURCES')
                for snapshot in validation['samples']:
                    if self._sample(db, snapshot['document_id'], provider)[0] != snapshot:
                        fail('LOCAL_VALIDATION_REVIEW_CHANGED_RETRY')
            elif state != 'retired':
                fail('LOCAL_LAYOUT_STATE_TRANSITION_INVALID')
            journal.append(db, 'state', {'state': state, 'validation_id': validation['id'] if validation else None}, parent_id=layout_id)
            return self._layout(db, layout_id)[1]

    def quality(self, db, provider_id, layout_id, rows):
        counts, documents, drift = Counter(), set(), 0
        birth = next(i for i, row in enumerate(rows) if row['id'] == layout_id)
        drift_since_version = any(row['kind'] == 'link' and row['provider_id'] == provider_id and
            row['classification'] in {'drift', 'ambiguous'} for row in rows[birth+1:])
        links = [row for row in rows if row['kind'] == 'link' and row['provider_id'] == provider_id]
        for link in links:
            if link['classification'] in {'drift', 'ambiguous'}:
                drift += 1
            if link['layout_id'] != layout_id:
                continue
            document_id = link['document_id']
            # Corrections of the same original count once, using the latest
            # approved interpretation of that source; saved keystrokes don't.
            row = db.execute("SELECT * FROM staged WHERE document_id=? AND status='approved' ORDER BY id DESC LIMIT 1", (document_id,)).fetchone()
            if row:
                documents.add(document_id)
                original = get_extraction(db, document_id)
                reviewed = reviewed_values(db, row, original, stored_payload(row, db))
                for item in differences(original, reviewed):
                    path = item['field']
                    semantic = 'services.*.' + path.split('.')[-1] if path.startswith('services.') else path
                    counts[semantic] += 1
        return {'reviewed_documents': len(documents), 'field_corrections': dict(sorted(counts.items())),
                'correction_count': sum(counts.values()), 'provider_drift_documents': drift,
                'investigate': drift_since_version or any(count >= 2 for count in counts.values())}

    def listing(self):
        with self.store.connect() as db:
            providers, layouts, rows, damaged = journal.registry(db)
            for layout in layouts:
                layout['quality'] = self.quality(db, layout['provider_id'], layout['id'], rows)
            return {'providers': providers, 'layouts': layouts, 'damaged': damaged,
                    'status_code': 'LOCAL_TEMPLATE_DAMAGED_MANUAL_REVIEW' if damaged else 'LOCAL_REGISTRY_OK'}

    def inspect(self, layout_id):
        listing = self.listing()
        if listing['damaged']:
            fail('LOCAL_TEMPLATE_DAMAGED_MANUAL_REVIEW')
        layout = next((row for row in listing['layouts'] if row['id'] == layout_id), None)
        if not layout:
            fail('LOCAL_LAYOUT_NOT_FOUND')
        return {'layout': layout, 'provider': next(row for row in listing['providers'] if row['id'] == layout['provider_id'])}

    def support(self, layout_id):
        # Construct a positive schema from typed semantics and integer counts.
        # Never copy private record dictionaries, source strings, exceptions,
        # invoice dates, locator labels/regions or validation sample references.
        from .provider_support import SupportBundle, FieldSupport
        detail = self.inspect(layout_id)
        layout, provider = detail['layout'], detail['provider']
        validation = layout['validation']
        summary = validation['summary'] if validation else {}
        quality = layout['quality']
        fields = []
        for rule in layout['definition']['rules']:
            counts = summary.get('fields', {}).get(rule['field'], {})
            fields.append(FieldSupport(semantic=rule['field'], rule_type=rule['mode'],
                exact=counts.get('exact', 0), tested=counts.get('tested', 0),
                missing=counts.get('missing', 0), corrected=counts.get('corrected', 0),
                unit_conflicts=counts.get('unit_conflicts', 0), manual_entry=counts.get('manual_entry', 0),
                approved_corrections=quality['field_corrections'].get(rule['field'], 0)))
        bundle = SupportBundle(application_version=__version__, schema_version=SCHEMA_VERSION,
            anonymous_provider=provider['id'], anonymous_layout=layout['id'], template_version=layout['version'],
            template_hash=layout['hash'], state=layout['state'],
            validation_status='passed_selected_set' if summary.get('eligible') else 'needs_validation',
            documents_tested=summary.get('documents_tested', 0), fields=fields,
            evidence_states=summary.get('evidence_states', {}),
            drift='investigate' if quality['investigate'] or summary.get('layout_drift', 0) else 'none_observed',
            drift_count=quality['provider_drift_documents'] + summary.get('layout_drift', 0))
        serialized = bundle.model_dump_json(indent=2) + '\n'
        return {'text': serialized, 'sha256': __import__('hashlib').sha256(serialized.encode()).hexdigest()}
