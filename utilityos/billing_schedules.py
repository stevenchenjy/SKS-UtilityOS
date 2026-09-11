"""Account-level invoice expectations; no retrieval, sampling or posting authority."""
import calendar
from datetime import date, timedelta
from hashlib import sha256
import json

from .audit import event, now
from .parsers import ValidationError, iso_date, text

SCHEMA = (
    '''CREATE TABLE billing_schedule_versions (
       id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
       revision INTEGER NOT NULL, payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
       at TEXT NOT NULL, UNIQUE(account_id,revision))''',
    "CREATE TRIGGER billing_schedule_no_update BEFORE UPDATE ON billing_schedule_versions BEGIN SELECT RAISE(ABORT,'SCHEDULE_HISTORY_IMMUTABLE'); END",
    "CREATE TRIGGER billing_schedule_no_delete BEFORE DELETE ON billing_schedule_versions BEGIN SELECT RAISE(ABORT,'SCHEDULE_HISTORY_IMMUTABLE'); END",
)


def initialize(db):
    for statement in SCHEMA:
        db.execute(statement)


def validate(data):
    if not isinstance(data, dict) or data.get('acknowledge') is not True:
        raise ValidationError('CONFIRM_EXPECTED_BILL_CADENCE')
    for key, low, high in [('account_id', 1, 2**63-1), ('revision', 0, 2**31-1),
                           ('anchor_month', 1, 12), ('issue_day', 1, 31), ('grace_days', 0, 60)]:
        if type(data.get(key)) is not int or not low <= data[key] <= high:
            raise ValidationError('BILLING_SCHEDULE_NUMBER_INVALID')
    if data.get('cadence') not in {'monthly', 'every_two_months', 'delivery', 'irregular'} or type(data.get('enabled')) is not bool:
        raise ValidationError('EXPECTATION_CADENCE_INVALID')
    result = {key: data[key] for key in ('account_id', 'revision', 'anchor_month', 'issue_day', 'grace_days', 'cadence', 'enabled')}
    result['effective_from'] = iso_date(data.get('effective_from'))
    result['effective_to'] = iso_date(data['effective_to']) if data.get('effective_to') else None
    if result['effective_to'] and result['effective_to'] < result['effective_from']:
        raise ValidationError('EXPECTATION_MONTH_RANGE_INVALID')
    if data.get('retrieval_cadence', 'manual') not in {'manual', 'weekly', 'monthly', 'on_issue'}:
        raise ValidationError('RETRIEVAL_CADENCE_INVALID')
    result['retrieval_cadence'] = data.get('retrieval_cadence', 'manual')
    result['reason'] = text(data.get('reason'), max_len=500)
    exceptions = data.get('exceptions', [])
    if not isinstance(exceptions, list) or len(exceptions) > 24:
        raise ValidationError('SCHEDULE_EXCEPTIONS_INVALID')
    result['exceptions'] = []
    months = set()
    for item in exceptions:
        if not isinstance(item, dict) or set(item) != {'month', 'expected', 'issue_date', 'reason'} or type(item['expected']) is not bool:
            raise ValidationError('SCHEDULE_EXCEPTIONS_INVALID')
        from .completeness import month
        selected = month(item['month'])
        if selected in months:
            raise ValidationError('SCHEDULE_EXCEPTION_DUPLICATE_MONTH')
        months.add(selected)
        issued = iso_date(item['issue_date']) if item['expected'] else None
        if issued and issued[:7] != selected:
            raise ValidationError('SCHEDULE_EXCEPTION_ISSUE_MONTH_MISMATCH')
        result['exceptions'].append({'month': selected, 'expected': item['expected'], 'issue_date': issued,
                                     'reason': text(item['reason'], max_len=500)})
    return result


def verify(db):
    version = db.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
    if not version or int(version[0]) < 6:
        return
    triggers = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    if not {'billing_schedule_no_update', 'billing_schedule_no_delete'}.issubset(triggers):
        raise ValidationError('BILLING_SCHEDULE_HISTORY_DAMAGED')
    hashes, revisions = set(), {}
    for account_id, revision, payload, digest in db.execute('SELECT account_id,revision,payload,payload_sha256 FROM billing_schedule_versions ORDER BY account_id,revision'):
        try:
            value = json.loads(payload)
            if (sha256(payload.encode()).hexdigest() != digest or value['account_id'] != account_id
                    or value['revision'] != revision or validate({**value, 'acknowledge': True}) != value
                    or not db.execute("SELECT 1 FROM audit_events WHERE code='CONFIGURE_BILLING_SCHEDULE' AND related_hash=?", (digest,)).fetchone()):
                raise ValueError()
            if revision != revisions.get(account_id, 0) + 1 or digest in hashes:
                raise ValueError()
            revisions[account_id] = revision
            hashes.add(digest)
        except (ValueError, KeyError, TypeError):
            raise ValidationError('BILLING_SCHEDULE_HISTORY_DAMAGED') from None
    # A removed suspension must not silently reactivate an earlier schedule.
    # The intact audit retains every journal hash even if a damaged database's
    # missing row and immutable trigger have been independently restored.
    audit_hashes = [row[0] for row in db.execute("SELECT related_hash FROM audit_events WHERE code='CONFIGURE_BILLING_SCHEDULE'")]
    if len(audit_hashes) != len(hashes) or set(audit_hashes) != hashes:
        raise ValidationError('BILLING_SCHEDULE_HISTORY_DAMAGED')


def current(db):
    verify(db)
    return [json.loads(row[0]) for row in db.execute('''SELECT s.payload FROM billing_schedule_versions s
            WHERE s.revision=(SELECT MAX(v.revision) FROM billing_schedule_versions v WHERE v.account_id=s.account_id)
            ORDER BY s.account_id''')]


def configure(store, data):
    value = validate(data)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        verify(db)
        if not db.execute('SELECT 1 FROM account_meters WHERE account_id=?', (value['account_id'],)).fetchone():
            raise ValidationError('CONFIRMED_ACCOUNT_METER_RELATIONSHIP_REQUIRED')
        prior = db.execute('SELECT MAX(revision) FROM billing_schedule_versions WHERE account_id=?', (value['account_id'],)).fetchone()[0] or 0
        if value['revision'] != prior:
            raise ValidationError('EXPECTATION_CHANGED_REOPEN')
        value['revision'] += 1
        payload = json.dumps(value, sort_keys=True, separators=(',', ':'))
        digest = sha256(payload.encode()).hexdigest()
        db.execute('INSERT INTO billing_schedule_versions(account_id,revision,payload,payload_sha256,at) VALUES (?,?,?,?,?)',
                   (value['account_id'], value['revision'], payload, digest, now()))
        event(db, 'CONFIGURE_BILLING_SCHEDULE', related_hash=digest)
    return {'ok': True, 'revision': value['revision']}


def expected_date(schedule, selected):
    """Invoice issue day, with month-end clamping; never invent a service period."""
    year, number = map(int, selected.split('-'))
    issued = date(year, number, min(schedule['issue_day'], calendar.monthrange(year, number)[1]))
    expected = schedule['cadence'] == 'monthly' or (schedule['cadence'] == 'every_two_months' and (number - schedule['anchor_month']) % 2 == 0)
    exception = next((item for item in schedule['exceptions'] if item['month'] == selected), None)
    if exception:
        expected = exception['expected']
        if expected:
            issued = date.fromisoformat(exception['issue_date'])
    if not schedule['enabled'] or issued.isoformat() < schedule['effective_from'] or (schedule['effective_to'] and issued.isoformat() > schedule['effective_to']):
        expected = False
    return issued if expected else None


def apply(db, result, selected, as_of=None):
    schedules = current(db)
    # Legacy meter expectations are retained as evidence. Count one statement per
    # account and expose conflicting legacy decisions for reconfirmation.
    overridden = {s['account_id'] for s in schedules}
    grouped = {}
    for row in result['rows']:
        if row['account_id'] not in overridden:
            grouped.setdefault(row['account_id'], []).append(row)
    rows = []
    for items in grouped.values():
        row = dict(items[0])
        states = {item['state'] for item in items}
        cadences = {item['cadence'] for item in items}
        row['meter_code'] = ', '.join(sorted({item['meter_code'] for item in items}))
        row['scope'] = 'legacy_account'
        row['observed_approved'] = 'approved' in states
        row['observed_under_review'] = 'under_review' in states or any(item['also_under_review'] for item in items)
        row['also_under_review'] = row['observed_approved'] and row['observed_under_review']
        row['expected'] = len(cadences) == 1 and row['cadence'] == 'monthly'
        row['state'] = 'needs_confirmation' if len(cadences) > 1 else 'approved' if row['observed_approved'] else 'under_review' if row['observed_under_review'] else row['state']
        if len(cadences) > 1:
            row['cadence'] = 'conflicting_legacy'
        rows.append(row)
    today = as_of or date.today()
    approved = {row[0] for row in db.execute("SELECT DISTINCT account_id FROM bills WHERE status='active' AND substr(bill_date,1,7)=?", (selected,))}
    pending = set()
    from .review_data import payload as stored_payload
    for stage in db.execute("SELECT * FROM staged WHERE kind='bill' AND status='pending'"):
        try:
            bill = stored_payload(stage, db)
            if bill['bill_date'][:7] == selected:
                pending.add((bill['provider'], bill['account_alias']))
        except ValidationError:
            continue
    for schedule in schedules:
        row = dict(db.execute('''SELECT a.id account_id,a.alias account_alias,p.name provider FROM accounts a
                                JOIN providers p ON p.id=a.provider_id WHERE a.id=?''', (schedule['account_id'],)).fetchone())
        meters = [r[0] for r in db.execute('SELECT DISTINCT m.code FROM account_meters am JOIN meters m ON m.id=am.meter_id WHERE am.account_id=? ORDER BY m.code', (row['account_id'],))]
        issued = expected_date(schedule, selected)
        deadline = issued + timedelta(days=schedule['grace_days']) if issued else None
        is_pending = (row['provider'], row['account_alias']) in pending
        is_approved = row['account_id'] in approved
        state = 'approved' if is_approved else 'under_review' if is_pending else 'not_scheduled' if not issued else 'not_due' if today <= deadline else 'missing'
        row.update(cadence=schedule['cadence'], meter_code=', '.join(meters), state=state, scope='account_statement',
                   expected=bool(issued), issue_date=issued.isoformat() if issued else None,
                   missing_after=deadline.isoformat() if deadline else None, also_under_review=is_approved and is_pending,
                   retrieval_cadence=schedule['retrieval_cadence'])
        rows.append(row)
    counts = {'expected': 0, 'received': 0, 'under_review': 0, 'approved': 0, 'missing': 0}
    if schedules:
        counts['not_due'] = 0
    for row in rows:
        expected = row.get('expected', row['cadence'] == 'monthly' and row['state'] != 'needs_confirmation')
        if expected:
            counts['expected'] += 1
            if row['state'] in counts:
                counts[row['state']] += 1
            if row['state'] in {'approved', 'under_review'}:
                counts['received'] += 1
    result.update(rows=rows, counts=counts, schedules=schedules, as_of=today.isoformat(), counting_basis='one_expected_statement_per_account_invoice_month')
    return result
