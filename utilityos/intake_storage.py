"""Schema-4 private extraction evidence and reviewed differences."""
from hashlib import sha256
import json
from decimal import Decimal
from .audit import event
from .extraction_schema import Extraction, EvidenceField, HEADER_FIELDS, SERVICE_FIELDS, allowed_path, MONEY_FIELDS, NUMBER_FIELDS
from .extraction import HEADER_TO_BILL, SERVICE_TO_BILL, normalize
from .parsers import ValidationError

STATEMENTS = (
    '''CREATE TABLE expectation_history (
       id INTEGER PRIMARY KEY, expectation_id INTEGER NOT NULL REFERENCES bill_expectations(id),
       at TEXT NOT NULL, before_value TEXT, after_value TEXT NOT NULL, reason TEXT NOT NULL)''',
    '''CREATE TABLE document_extractions (
       document_id INTEGER PRIMARY KEY REFERENCES documents(id), payload TEXT NOT NULL,
       payload_sha256 TEXT NOT NULL, staged_id INTEGER NOT NULL REFERENCES staged(id))''',
    '''CREATE TABLE intake_reviews (
       staged_id INTEGER NOT NULL REFERENCES staged(id), revision INTEGER NOT NULL,
       fields TEXT NOT NULL, differences TEXT NOT NULL, PRIMARY KEY(staged_id,revision))''',
    '''CREATE TABLE intake_attempts (
       id INTEGER PRIMARY KEY, filename TEXT NOT NULL, sha256 TEXT NOT NULL,
       origin TEXT NOT NULL CHECK(origin IN ('picker','inbox')), started_at TEXT NOT NULL,
       finished_at TEXT, state TEXT NOT NULL, code TEXT NOT NULL DEFAULT '',
       document_id INTEGER REFERENCES documents(id))''',
    '''CREATE TABLE bill_expectations (
       id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
       meter_id INTEGER NOT NULL REFERENCES meters(id),
       cadence TEXT NOT NULL CHECK(cadence IN ('monthly','delivery','irregular')),
       first_month TEXT NOT NULL, last_month TEXT, enabled INTEGER NOT NULL DEFAULT 1,
       revision INTEGER NOT NULL DEFAULT 1, UNIQUE(account_id,meter_id))''',
) + tuple(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'EXTRACTION_HISTORY_IMMUTABLE'); END"
          for table in ('document_extractions', 'intake_reviews') for action in ('UPDATE', 'DELETE'))


def initialize(db):
    for statement in STATEMENTS:
        db.execute(statement)


def store_extraction(db, document_id, staged_id, extraction):
    serialized = Extraction.model_validate(extraction).model_dump_json()
    digest = sha256(serialized.encode()).hexdigest()
    db.execute('INSERT INTO document_extractions VALUES (?,?,?,?)', (document_id, serialized, digest, staged_id))
    event(db, 'EXTRACT_DOCUMENT', staged_id, related_hash=digest)


def get_extraction(db, document_id):
    row = db.execute('SELECT payload,payload_sha256,staged_id FROM document_extractions WHERE document_id=?', (document_id,)).fetchone()
    if not row:
        return None
    try:
        if sha256(row[0].encode()).hexdigest() != row[1] or not db.execute(
                "SELECT 1 FROM audit_events WHERE code='EXTRACT_DOCUMENT' AND staged_id=? AND related_hash=?", (row[2], row[1])).fetchone():
            raise ValueError()
        return Extraction.model_validate_json(row[0]).model_dump(mode='json')
    except ValueError:
        raise ValidationError('EXTRACTION_HISTORY_DAMAGED') from None


def verify(db):
    version = db.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
    if not version or int(version[0]) < 4:
        return
    triggers = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    expected = {f'{table}_no_{action}' for table in ('document_extractions', 'intake_reviews') for action in ('update', 'delete')}
    if not expected.issubset(triggers):
        raise ValidationError('EXTRACTION_HISTORY_DAMAGED')
    for row in db.execute('SELECT document_id FROM document_extractions'):
        get_extraction(db, row[0])


def detail_keys(extraction, service_count=0):
    keys = set(extraction['fields']) | set(HEADER_FIELDS) | {f'services.{i}.{key}' for i in range(service_count) for key in SERVICE_FIELDS}
    return {key for key in keys if key not in HEADER_TO_BILL and (
        not key.startswith('services.') or key.split('.')[-1] not in SERVICE_TO_BILL)}


def current_values(db, row, extraction):
    saved = db.execute('SELECT fields FROM intake_reviews WHERE staged_id=? AND revision<=? ORDER BY revision DESC LIMIT 1',
                       (row['id'], row['revision'])).fetchone()
    if saved:
        try:
            values = json.loads(saved[0])
            if not isinstance(values, dict) or any(not allowed_path(key) or value is not None and not isinstance(value, str) for key, value in values.items()):
                raise ValueError()
            return values
        except ValueError:
            raise ValidationError('EXTRACTION_HISTORY_DAMAGED') from None
    return {key: field['value'] for key, field in extraction['fields'].items()}


def reviewed_values(db, row, extraction, bill, details=None):
    values = current_values(db, row, extraction)
    if details is not None:
        if not isinstance(details, dict) or set(details) - detail_keys(extraction, len(bill['lines'])):
            raise ValidationError('EXTRACTION_REVIEW_FIELDS_INVALID')
        for key, raw in details.items():
            if not isinstance(raw, str) or len(raw) > 120:
                raise ValidationError('EXTRACTION_REVIEW_VALUE_INVALID')
            try:
                values[key] = normalize(key.split('.')[-1], raw) if raw.strip() else None
            except ValueError:
                raise ValidationError('EXTRACTION_REVIEW_VALUE_INVALID') from None
    for source, target in HEADER_TO_BILL.items():
        values[source] = bill[target] or None
    for index, line in enumerate(bill['lines']):
        for source, target in SERVICE_TO_BILL.items():
            if source == 'consumption_quantity' and line['usage_role'] in {'delivery', 'charges_only'}:
                continue
            values[f'services.{index}.{source}'] = line[target] or None
        if line['usage_role'] == 'delivery':
            values[f'services.{index}.delivery_quantity'] = line['usage'] or None
    return values


def differences(extraction, values):
    result = []
    for key in sorted(set(extraction['fields']) | set(values)):
        field = extraction['fields'].get(key, {'value':None, 'template_version':extraction['template_version'], 'method':'unavailable'})
        before, after = field['value'], values.get(key)
        equal = before == after
        if before is not None and after is not None and key.split('.')[-1] in MONEY_FIELDS | NUMBER_FIELDS:
            try:
                equal = Decimal(before) == Decimal(after)
            except Exception:
                pass
        if not equal:
            result.append({'field':key, 'proposed':before, 'reviewed':after,
                           'template_version':field['template_version'], 'method':field['method']})
    return result


def save_review(db, row, revision, bill, details=None):
    extraction = get_extraction(db, row['document_id'])
    if extraction:
        values = reviewed_values(db, row, extraction, bill, details)
        db.execute('INSERT INTO intake_reviews VALUES (?,?,?,?)',
                   (row['id'], revision, json.dumps(values), json.dumps(differences(extraction, values))))


def review_info(db, row, bill):
    extraction = get_extraction(db, row['document_id'])
    if not extraction:
        return None
    values = reviewed_values(db, row, extraction, bill)
    keys = detail_keys(extraction, len(bill['lines']))
    for key in keys:
        extraction['fields'].setdefault(key, EvidenceField(parser_version=extraction['parser_version']).model_dump(mode='json'))
    return {'extraction':extraction, 'reviewed_values':values,
            'detail_keys':sorted(keys), 'differences':differences(extraction, values)}


def validation_flags(db, row, bill, details=None):
    extraction = get_extraction(db, row['document_id'])
    if not extraction:
        return []
    values = reviewed_values(db, row, extraction, bill, details)
    flags = [{'code':'SOURCE_EVIDENCE_REVIEW_REQUIRED', 'blocking':False}]
    flags += [{'code':code, 'blocking':False} for code in extraction['codes']]
    if values.get('currency') not in (None, 'USD'):
        flags.append({'code':'LEDGER_REQUIRES_USD_CURRENT_CHARGES', 'blocking':True})
    if extraction['document_type'] == 'supporting_document' and values.get('document_kind') == 'supporting_document':
        flags.append({'code':'SUPPORTING_DOCUMENT_CANNOT_BE_APPROVED_AS_INVOICE', 'blocking':True})
    for index, line in enumerate(bill['lines']):
        value = lambda key: values.get(f'services.{index}.{key}')
        if values.get('supplier_only') == 'yes' and (line['usage_role'] != 'charges_only' or Decimal(line['usage']) != 0):
            flags.append({'code':'SUPPLIER_ONLY_MUST_NOT_REPEAT_CONSUMPTION', 'blocking':True})
        if value('demand_quantity') and (Decimal(value('demand_quantity')) < 0 or value('demand_unit') not in {'kW','kVA'} or line['commodity'] != 'electricity'):
            flags.append({'code':'DEMAND_QUANTITY_OR_UNIT_CONFLICT', 'blocking':True})
        if value('previous_reading') is not None and value('current_reading') is not None and line['usage_role'] == 'consumption':
            if Decimal(value('current_reading')) - Decimal(value('previous_reading')) != Decimal(line['usage']):
                flags.append({'code':'READING_DIFFERENCE_REQUIRES_REVIEW', 'blocking':False})
        parts = [value(key) for key in ('supply_charge','delivery_charge','demand_charge','taxes','fees','credits')]
        if all(part is not None for part in parts) and sum(Decimal(part) for part in parts) != Decimal(line['current_charge']):
            flags.append({'code':'EXTRACTED_CHARGE_COMPONENTS_DO_NOT_RECONCILE', 'blocking':False})
        known = db.execute('''SELECT 1 FROM account_meters am JOIN meters m ON m.id=am.meter_id
             JOIN accounts a ON a.id=am.account_id JOIN providers p ON p.id=a.provider_id
             WHERE m.code=? AND a.alias=? AND p.name=?''', (line['meter_code'],bill['account_alias'],bill['provider'])).fetchone()
        if not known:
            flags.append({'code':'ACCOUNT_SERVICE_MAPPING_NEEDS_CONFIRMATION', 'blocking':False})
    return list({flag['code']:flag for flag in flags}.values())
