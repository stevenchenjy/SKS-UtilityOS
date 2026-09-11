"""Bounded, staff-mapped CSV measurements. No invoice or consumption-total writes."""
import csv
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import io
from itertools import islice
from pathlib import Path
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from . import __version__
from .audit import event, now
from .parsers import ValidationError
from .storage import publish_source, read_source
from .usage_storage import ACTIVE_READINGS, READING_FIELDS, digest, read_payload, serialize

UNITS = {'water': ('US_gal','m3','L'), 'natural_gas': ('ft3','CCF','Mcf','m3','therm','kWh'), 'electricity': ('Wh','kWh')}
MAPPING_FIELDS = {'meter_code','commodity','unit','semantics','timezone','meter_column','source_meter',
                  'start_column','end_column','value_column','unit_column','quality_column'}
MAX_ROWS = 5000


def csv_rows(raw):
    if not raw:
        raise ValidationError('EMPTY_FILE')
    if len(raw) > 8 * 1024 * 1024:
        raise ValidationError('FILE_EXCEEDS_8_MB')
    try:
        rows = list(islice(csv.reader(io.StringIO(raw.decode('utf-8-sig')), strict=True), MAX_ROWS + 2))
    except (UnicodeError, csv.Error):
        raise ValidationError('USAGE_REQUIRES_UTF8_COMMA_SEPARATED_CSV') from None
    if len(rows) < 2 or len(rows) > MAX_ROWS + 1:
        raise ValidationError('USAGE_REQUIRES_1_TO_5000_ROWS')
    headers = rows[0]
    if not 2 <= len(headers) <= 30 or len(set(headers)) != len(headers) or any(not h.strip() or h != h.strip() for h in headers):
        raise ValidationError('USAGE_HEADERS_MUST_BE_UNIQUE_NONEMPTY')
    for row in rows:
        if len(row) != len(headers):
            raise ValidationError('USAGE_CSV_ROW_WIDTH_MISMATCH')
        for cell in row:
            if len(cell) > 250 or any(ord(c) < 32 for c in cell):
                raise ValidationError('USAGE_CELL_TOO_LONG_OR_CONTROL_CHARACTER')
            if cell.lstrip().startswith(('=', '+', '-', '@')):
                raise ValidationError('USAGE_FORMULA_LIKE_CELL_REJECTED')
    return headers, [dict(zip(headers, row)) for row in rows[1:]]


def timestamp(raw, zone):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?', raw):
        raise ValidationError('USAGE_TIMESTAMP_REQUIRES_ISO_DATETIME')
    try:
        value = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if value.tzinfo is None:
            if zone is None:
                raise ValidationError('USAGE_NAIVE_TIMESTAMP_NEEDS_TIMEZONE')
            candidates = []
            for fold in (0, 1):
                candidate = value.replace(tzinfo=zone, fold=fold)
                if candidate.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == value:
                    candidates.append(candidate)
            offsets = {candidate.utcoffset() for candidate in candidates}
            if len(offsets) != 1:
                raise ValidationError('USAGE_DST_AMBIGUOUS_OR_NONEXISTENT_USE_OFFSET')
            value = candidates[0]
        return int(value.timestamp())
    except ValidationError:
        raise
    except (ValueError, OverflowError, OSError):
        raise ValidationError('USAGE_TIMESTAMP_INVALID') from None


def revision(value):
    if type(value) is not int or value < 0:
        raise ValidationError('USAGE_REVISION_REQUIRED')
    return value


def mapped_readings(db, raw, mapping):
    headers, rows = csv_rows(raw)
    if not isinstance(mapping, dict) or set(mapping) != MAPPING_FIELDS or any(not isinstance(v,str) or len(v)>250 for v in mapping.values()):
        raise ValidationError('USAGE_EXPLICIT_MAPPING_REQUIRED')
    commodity, unit, semantics = mapping['commodity'], mapping['unit'], mapping['semantics']
    if commodity not in UNITS or unit not in UNITS[commodity]:
        raise ValidationError('USAGE_COMMODITY_UNIT_UNSUPPORTED_OR_AMBIGUOUS')
    if semantics not in {'delta','cumulative'}:
        raise ValidationError('USAGE_DELTA_OR_CUMULATIVE_SEMANTICS_REQUIRED')
    meter = db.execute('SELECT * FROM meters WHERE code=?', (mapping['meter_code'],)).fetchone()
    if not meter or meter['commodity'] != commodity:
        raise ValidationError('USAGE_CONFIRMED_METER_COMMODITY_REQUIRED')
    required = ['meter_column','start_column','value_column'] + (['end_column'] if semantics == 'delta' else [])
    used = [mapping[k] for k in required] + [mapping[k] for k in ('unit_column','quality_column') if mapping[k]]
    if not mapping['source_meter'] or any(c not in headers for c in used) or len(set(used)) != len(used):
        raise ValidationError('USAGE_COLUMN_MAPPING_INVALID')
    if semantics == 'cumulative' and mapping['end_column']:
        raise ValidationError('USAGE_CUMULATIVE_HAS_NO_INTERVAL_END')
    zone = None
    if mapping['timezone']:
        try:
            zone = ZoneInfo(mapping['timezone'])
        except (ZoneInfoNotFoundError, ValueError):
            raise ValidationError('USAGE_IANA_TIMEZONE_REQUIRED') from None
    readings = []
    seen = set()
    for row in rows:
        if row[mapping['meter_column']] != mapping['source_meter']:
            raise ValidationError('USAGE_ONE_SOURCE_METER_PER_FILE_REQUIRED')
        if mapping['unit_column'] and row[mapping['unit_column']] != unit:
            raise ValidationError('USAGE_SOURCE_UNIT_DIFFERS_FROM_DECLARATION')
        raw_value = row[mapping['value_column']]
        if not re.fullmatch(r'\d{1,16}(?:\.\d{1,9})?', raw_value):
            raise ValidationError('USAGE_NONNEGATIVE_DECIMAL_REQUIRED')
        quantity = Decimal(raw_value)
        start = timestamp(row[mapping['start_column']], zone)
        end = timestamp(row[mapping['end_column']], zone) if semantics == 'delta' else start
        if semantics == 'delta' and end <= start:
            raise ValidationError('USAGE_EXCLUSIVE_END_MUST_FOLLOW_START')
        quality = row[mapping['quality_column']] if mapping['quality_column'] else 'unknown'
        reading = {'meter_id':meter['id'], 'commodity':commodity, 'unit':unit, 'semantics':semantics,
                   'start_utc':start, 'end_utc':end, 'quantity':format(quantity.normalize(), 'f'), 'quality':quality or 'unknown'}
        key = digest(reading)
        if key not in seen:
            readings.append(reading)
            seen.add(key)
    readings.sort(key=lambda r:r['start_utc'])
    for previous, current in zip(readings, readings[1:]):
        if current['start_utc'] < previous['end_utc'] or current['start_utc'] == previous['start_utc']:
            raise ValidationError('USAGE_CONFLICTING_OR_OVERLAPPING_SOURCE_ROWS')
        if semantics == 'cumulative' and Decimal(current['quantity']) < Decimal(previous['quantity']):
            raise ValidationError('USAGE_CUMULATIVE_RESET_REQUIRES_RECONCILIATION')
    return readings, len(rows) - len(readings)


def conflicts(db, readings, mapping=None):
    """Run inside the posting transaction too: a preview is never a lock."""
    result = {}
    duplicates = 0
    if mapping:
        for row in db.execute('''SELECT d.import_id,p.payload,p.payload_hash FROM usage_decisions d
             JOIN usage_previews p ON p.import_id=d.import_id AND p.revision=d.revision
             WHERE d.state='approved' AND NOT EXISTS(SELECT 1 FROM usage_withdrawals w WHERE w.import_id=d.import_id)'''):
            prior = read_payload(row)['mapping']
            if (prior['source_meter'] == mapping['source_meter'] and prior['commodity'] == mapping['commodity']
                and prior['meter_code'] != mapping['meter_code']):
                result[row['import_id']] = {'import_id':row['import_id'],'code':'USAGE_SOURCE_METER_ALREADY_MAPPED_ELSEWHERE'}
    for reading in readings:
        if reading['semantics'] == 'delta':
            condition, bounds = 'r.start_utc<? AND r.end_utc>?', (reading['end_utc'],reading['start_utc'])
        else:
            condition, bounds = 'r.start_utc=?', (reading['start_utc'],)
        active = db.execute(f'''SELECT * FROM ({ACTIVE_READINGS}) r WHERE r.meter_id=? AND r.semantics=? AND {condition}''',
                            (reading['meter_id'],reading['semantics'],*bounds)).fetchall()
        exact = False
        for old in active:
            if old['payload_hash'] == digest(reading):
                exact = True
            else:
                for source in db.execute('''SELECT e.import_id FROM usage_evidence e JOIN usage_decisions d ON d.import_id=e.import_id
                   WHERE e.reading_id=? AND d.state='approved' AND NOT EXISTS(SELECT 1 FROM usage_withdrawals w WHERE w.import_id=e.import_id)''', (old['id'],)):
                    result[source[0]] = {'import_id':source[0], 'code':'USAGE_CONFLICT_WITH_ACTIVE_EVIDENCE'}
        duplicates += int(exact)
        if reading['semantics'] == 'cumulative':
            # An export may contain only one point or interleave earlier exports.
            # Check both adjacent retained points; do not derive consumption.
            for comparison, direction in (('<','DESC'),('>','ASC')):
                neighbor = db.execute(f'''SELECT * FROM ({ACTIVE_READINGS}) r
                    WHERE r.meter_id=? AND r.unit=? AND r.semantics='cumulative' AND r.start_utc{comparison}?
                    ORDER BY r.start_utc {direction} LIMIT 1''',
                    (reading['meter_id'],reading['unit'],reading['start_utc'])).fetchone()
                if neighbor and ((comparison == '<' and Decimal(neighbor['quantity']) > Decimal(reading['quantity']))
                                 or (comparison == '>' and Decimal(neighbor['quantity']) < Decimal(reading['quantity']))):
                    for source in db.execute('''SELECT e.import_id FROM usage_evidence e JOIN usage_decisions d ON d.import_id=e.import_id
                       WHERE e.reading_id=? AND d.state='approved' AND NOT EXISTS(SELECT 1 FROM usage_withdrawals w WHERE w.import_id=e.import_id)''', (neighbor['id'],)):
                        result[source[0]] = {'import_id':source[0],'code':'USAGE_CUMULATIVE_RESET_REQUIRES_RECONCILIATION'}
        if reading['semantics'] == 'delta' and reading['commodity'] == 'electricity' and db.execute('''SELECT 1 FROM interval_readings r
             JOIN interval_channels c ON c.id=r.channel_id WHERE c.meter_id=? AND r.start_utc<? AND r.start_utc+r.duration_s>?''',
             (reading['meter_id'],reading['end_utc'],reading['start_utc'])).fetchone():
            result['xml'] = {'import_id':None, 'code':'USAGE_OVERLAPS_EXISTING_XML_EVIDENCE'}
    return list(result.values()), duplicates


class UsageImport:
    def __init__(self, ledger):
        self.store = ledger.store

    def _record(self, db, identifier):
        row = db.execute('''SELECT u.*,d.filename,d.sha256,d.extension FROM usage_imports u
          JOIN documents d ON d.id=u.document_id WHERE u.id=?''', (identifier,)).fetchone()
        if not row:
            raise ValidationError('USAGE_IMPORT_NOT_FOUND')
        decision = db.execute('SELECT * FROM usage_decisions WHERE import_id=?', (identifier,)).fetchone()
        withdrawn = db.execute('SELECT * FROM usage_withdrawals WHERE import_id=?', (identifier,)).fetchone()
        latest = db.execute('SELECT * FROM usage_previews WHERE import_id=? ORDER BY revision DESC LIMIT 1', (identifier,)).fetchone()
        return row, decision, withdrawn, latest

    def _pending(self, db, identifier, expected):
        row, decision, withdrawn, latest = self._record(db, identifier)
        if decision:
            raise ValidationError('USAGE_PENDING_IMPORT_REQUIRED')
        if revision(expected) != (latest['revision'] if latest else 0):
            raise ValidationError('USAGE_CHANGED_REOPEN_PREVIEW')
        return row, latest

    def import_file(self, filename, raw):
        filename = Path(filename.replace('\\','/')).name[:180]
        if Path(filename).suffix.lower() != '.csv':
            raise ValidationError('USAGE_CSV_ONLY_CONVERT_VERIFIED_VALUES_LOCALLY')
        csv_rows(raw)
        source_hash = sha256(raw).hexdigest()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT id FROM documents WHERE sha256=?', (source_hash,)).fetchone()
            if old:
                existing = db.execute('SELECT id FROM usage_imports WHERE document_id=? ORDER BY id DESC LIMIT 1', (old[0],)).fetchone()
                if existing:
                    return {'import_id':existing[0], 'duplicate_source':True}
                raise ValidationError('DUPLICATE_SOURCE_DOCUMENT')
            publish_source(self.store.sources / (source_hash + '.csv'), raw)
            at = now()
            doc = db.execute('INSERT INTO documents(sha256,filename,extension,size,created_at,importer_version) VALUES (?,?,?,?,?,?)',
                             (source_hash,filename,'.csv',len(raw),at,__version__)).lastrowid
            identifier = db.execute('SELECT COALESCE(MAX(id),0)+1 FROM usage_imports').fetchone()[0]
            payload = {'import_id':identifier,'document_id':doc,'source_sha256':source_hash,'at':at,'parser':'generic-mapped-csv-v1'}
            db.execute('INSERT INTO usage_imports VALUES (?,?,?,?,?)', (identifier,doc,at,serialize(payload),digest(payload)))
            event(db,'IMPORT_USAGE_CSV',related_hash=digest(payload))
        return {'import_id':identifier,'duplicate_source':False}

    def listing(self):
        with self.store.connect() as db:
            meters = [dict(r) for r in db.execute('''SELECT m.id,m.code,m.commodity,m.unit,b.name building FROM meters m
                  LEFT JOIN buildings b ON b.id=m.building_id ORDER BY m.code''')]
            items = [dict(r) for r in db.execute('''SELECT u.id,u.document_id,d.filename,u.created_at,
                 CASE WHEN w.import_id IS NOT NULL THEN 'withdrawn' ELSE COALESCE(c.state,'pending') END state
                 FROM usage_imports u JOIN documents d ON d.id=u.document_id LEFT JOIN usage_decisions c ON c.import_id=u.id
                 LEFT JOIN usage_withdrawals w ON w.import_id=u.id ORDER BY u.id DESC LIMIT 200''')]
            count = db.execute(f'SELECT COUNT(*) FROM ({ACTIVE_READINGS})').fetchone()[0]
            readings = [dict(r) for r in db.execute(f'''SELECT r.*,m.code FROM ({ACTIVE_READINGS}) r JOIN meters m ON m.id=r.meter_id
                   ORDER BY r.start_utc DESC,r.id DESC LIMIT 100''')]
        return {'items':items,'meters':meters,'units':UNITS,'active_reading_count':count,'readings':readings}

    def detail(self, identifier):
        with self.store.connect() as db:
            row, decision, withdrawn, latest = self._record(db, identifier)
            headers, rows = csv_rows(read_source(self.store,row))
            payload = read_payload(latest) if latest else None
            conflicts_now, duplicates = conflicts(db,payload['readings'],payload['mapping']) if payload else ([],0)
            return {'id':identifier,'document_id':row['document_id'],'filename':row['filename'],'source_sha256':row['sha256'],
                    'headers':headers,'source_rows':rows[:8],'row_count':len(rows),'revision':latest['revision'] if latest else 0,
                    'state':'withdrawn' if withdrawn else decision['state'] if decision else 'pending',
                    'preview':{**payload, 'readings':payload['readings'][:20], 'reading_count':len(payload['readings'])} if payload else None,
                    'conflicts':conflicts_now,'duplicate_readings':duplicates,
                    'decision':read_payload(decision) if decision else None,'withdrawal':read_payload(withdrawn) if withdrawn else None,
                    'source_history':read_payload(row)}

    def preview(self, identifier, data):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row, latest = self._pending(db,identifier,data.get('revision'))
            readings, duplicate_rows = mapped_readings(db,read_source(self.store,row),data.get('mapping'))
            payload = {'import_id':identifier,'revision':(latest['revision'] if latest else 0)+1,'source_sha256':row['sha256'],
                       'mapping':data['mapping'],'readings':readings,'duplicate_source_rows':duplicate_rows,'at':now()}
            db.execute('INSERT INTO usage_previews VALUES (?,?,?,?)', (identifier,payload['revision'],serialize(payload),digest(payload)))
            event(db,'PREVIEW_USAGE',related_hash=digest(payload))
        return self.detail(identifier)

    def approve(self, identifier, data):
        if data.get('acknowledge') is not True:
            raise ValidationError('USAGE_MAPPING_ACKNOWLEDGEMENT_REQUIRED')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row, latest = self._pending(db,identifier,data.get('revision'))
            if not latest:
                raise ValidationError('USAGE_MAPPING_PREVIEW_REQUIRED')
            payload = read_payload(latest)
            readings, _ = mapped_readings(db,read_source(self.store,row),payload['mapping'])
            if readings != payload['readings']:
                raise ValidationError('USAGE_SOURCE_OR_MAPPING_CHANGED')
            conflicts_now, duplicates = conflicts(db,readings,payload['mapping'])
            if conflicts_now:
                raise ValidationError('USAGE_CONFLICT_RECONCILE_ACTIVE_IMPORTS')
            for reading in readings:
                key = digest(reading)
                db.execute('INSERT OR IGNORE INTO usage_readings(meter_id,commodity,unit,semantics,start_utc,end_utc,quantity,quality,payload_hash) VALUES (?,?,?,?,?,?,?,?,?)',
                           tuple(reading[k] for k in READING_FIELDS)+(key,))
                reading_id = db.execute('SELECT id FROM usage_readings WHERE payload_hash=?', (key,)).fetchone()[0]
                db.execute('INSERT INTO usage_evidence VALUES (?,?)', (identifier,reading_id))
            decision = {'import_id':identifier,'revision':latest['revision'],'state':'approved','preview_hash':latest['payload_hash'],'reason':'','at':now()}
            db.execute('INSERT INTO usage_decisions VALUES (?,?,?,?,?)', (identifier,latest['revision'],'approved',serialize(decision),digest(decision)))
            event(db,'APPROVE_USAGE',related_hash=digest(decision))
        return {'ok':True,'reading_count':len(readings),'duplicate_readings':duplicates}

    def close(self, identifier, data, *, withdraw=False):
        if data.get('acknowledge') is not True:
            raise ValidationError('USAGE_RECONCILIATION_ACKNOWLEDGEMENT_REQUIRED')
        reason = data.get('reason')
        if not isinstance(reason,str) or not 3 <= len(reason.strip()) <= 500:
            raise ValidationError('USAGE_RECONCILIATION_REASON_REQUIRED')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row, decision, withdrawn, latest = self._record(db,identifier)
            expected = latest['revision'] if latest else 0
            if revision(data.get('revision')) != expected:
                raise ValidationError('USAGE_CHANGED_REOPEN_PREVIEW')
            if withdraw:
                if not decision or decision['state'] != 'approved' or withdrawn:
                    raise ValidationError('USAGE_ACTIVE_APPROVED_IMPORT_REQUIRED')
                payload = {'import_id':identifier,'revision':expected,'reason':reason.strip(),'at':now()}
                db.execute('INSERT INTO usage_withdrawals VALUES (?,?,?)', (identifier,serialize(payload),digest(payload)))
                event(db,'WITHDRAW_USAGE',related_hash=digest(payload))
            else:
                if decision:
                    raise ValidationError('USAGE_PENDING_IMPORT_REQUIRED')
                payload = {'import_id':identifier,'revision':expected,'state':'rejected','reason':reason.strip(),'at':now()}
                db.execute('INSERT INTO usage_decisions VALUES (?,?,?,?,?)', (identifier,expected,'rejected',serialize(payload),digest(payload)))
                event(db,'REJECT_USAGE',related_hash=digest(payload))
        return {'ok':True}

    def reattempt(self, identifier, data):
        """Start another explicit mapping review of unchanged retained bytes."""
        if data.get('acknowledge') is not True:
            raise ValidationError('USAGE_RECONCILIATION_ACKNOWLEDGEMENT_REQUIRED')
        reason = data.get('reason')
        if not isinstance(reason,str) or not 3 <= len(reason.strip()) <= 500:
            raise ValidationError('USAGE_RECONCILIATION_REASON_REQUIRED')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row, decision, withdrawn, latest = self._record(db,identifier)
            if not decision or (decision['state'] != 'rejected' and not withdrawn):
                raise ValidationError('USAGE_WITHDRAW_OR_REJECT_BEFORE_REATTEMPT')
            if revision(data.get('revision')) != (latest['revision'] if latest else 0):
                raise ValidationError('USAGE_CHANGED_REOPEN_PREVIEW')
            active_attempt = db.execute("""SELECT 1 FROM usage_imports u LEFT JOIN usage_decisions d ON d.import_id=u.id
                 WHERE u.document_id=? AND (d.import_id IS NULL OR (d.state='approved'
                 AND NOT EXISTS(SELECT 1 FROM usage_withdrawals w WHERE w.import_id=u.id)))""", (row['document_id'],)).fetchone()
            if active_attempt:
                raise ValidationError('USAGE_SOURCE_ALREADY_HAS_ACTIVE_REVIEW')
            read_source(self.store,row)
            next_id = db.execute('SELECT COALESCE(MAX(id),0)+1 FROM usage_imports').fetchone()[0]
            at = now()
            payload = {'import_id':next_id,'document_id':row['document_id'],'source_sha256':row['sha256'],
                       'at':at,'parser':'generic-mapped-csv-v1','reattempt_of':identifier,'reason':reason.strip()}
            db.execute('INSERT INTO usage_imports VALUES (?,?,?,?,?)', (next_id,row['document_id'],at,serialize(payload),digest(payload)))
            event(db,'IMPORT_USAGE_CSV',related_hash=digest(payload))
        return {'import_id':next_id,'reattempt_of':identifier}
