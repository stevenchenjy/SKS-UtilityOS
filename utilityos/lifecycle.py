"""Reviewed invoice replacement, cancellation, and private draft history.

Financial payloads are never edited after approval. Lifecycle changes happen in
one transaction; reporting includes active versions only.
"""
import json
from .audit import now, event
from .review_data import payload as stored_payload, decode
from .parsers import ValidationError, blank_bill, text


def reason_text(value):
    return text(value, max_len=500)


def draft_payload(payload):
    """Save incomplete entry safely; complete financial validation is at approval."""
    template = blank_bill()
    if not isinstance(payload, dict):
        raise ValidationError('BILL_OBJECT_REQUIRED')
    result = {key: text(payload.get(key, ''), required=False) for key in template if key != 'lines'}
    lines = payload.get('lines')
    if not isinstance(lines, list) or not 1 <= len(lines) <= 50:
        raise ValidationError('BILL_REQUIRES_1_TO_50_LINES')
    result['lines'] = []
    for line in lines:
        if not isinstance(line, dict):
            raise ValidationError('BILL_LINE_INVALID')
        result['lines'].append({key: text(line.get(key, ''), required=False) for key in template['lines'][0]})
    return result


class BillLifecycle:
    @staticmethod
    def _pending(db, staged_id, revision=None, *, check_payload=True):
        row = db.execute("SELECT * FROM staged WHERE id=? AND kind='bill' AND status='pending'", (staged_id,)).fetchone()
        if not row:
            raise ValidationError('PENDING_BILL_REQUIRED')
        if revision is not None and (type(revision) is not int or row['revision'] != revision):
            raise ValidationError('DRAFT_CHANGED_REOPEN_REVIEW')
        if check_payload:
            stored_payload(row, db)
        return row

    @staticmethod
    def _active(db, bill_id):
        if type(bill_id) is not int:
            raise ValidationError('ACTIVE_ORIGINAL_INVOICE_REQUIRED')
        row = db.execute("SELECT * FROM bills WHERE id=? AND status='active'", (bill_id,)).fetchone()
        if not row:
            raise ValidationError('ACTIVE_ORIGINAL_INVOICE_REQUIRED')
        return row

    @staticmethod
    def _ancestors(db, bill_id):
        return [r[0] for r in db.execute('''WITH RECURSIVE chain(id,supersedes_id) AS (
            SELECT id,supersedes_id FROM bills WHERE id=? UNION ALL
            SELECT b.id,b.supersedes_id FROM bills b JOIN chain c ON b.id=c.supersedes_id)
            SELECT id FROM chain''', (bill_id,))]

    @staticmethod
    def _save_revision(db, row, payload, correction_of, reason, intake_details=None):
        revision = row['revision'] + 1
        serialized = json.dumps(payload)
        db.execute('''UPDATE staged SET review_payload=?,revision=?,correction_of=?,correction_reason=? WHERE id=?''',
                   (serialized, revision, correction_of, reason, row['id']))
        db.execute('''INSERT INTO draft_history(staged_id,at,revision,payload,correction_of,reason)
                      VALUES (?,?,?,?,?,?)''', (row['id'], now(), revision, serialized, correction_of, reason))
        from .intake_storage import save_review
        save_review(db,row,revision,payload,intake_details)
        event(db, 'SAVE_DRAFT', row['id'])
        return revision

    def save_draft(self, staged_id, payload, revision, correction_of=None, reason='', intake_details=None):
        payload = draft_payload(payload)
        if type(revision) is not int:
            raise ValidationError('DRAFT_REVISION_REQUIRED')
        reason = reason_text(reason) if correction_of is not None else ''
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self._pending(db, staged_id, revision)
            if correction_of is not None:
                self._active(db, correction_of)
                other = db.execute("SELECT id FROM staged WHERE correction_of=? AND status='pending' AND id<>?", (correction_of, staged_id)).fetchone()
                if other:
                    raise ValidationError('PENDING_CORRECTION_ALREADY_EXISTS')
            self._save_revision(db, row, payload, correction_of, reason, intake_details)
        return self.stage(staged_id)

    def recover_draft(self, staged_id, revision, acknowledge=False):
        if acknowledge is not True:
            raise ValidationError('CONFIRM_DRAFT_RECOVERY')
        if type(revision) is not int:
            raise ValidationError('DRAFT_REVISION_REQUIRED')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self._pending(db, staged_id, revision, check_payload=False)
            try:
                stored_payload(row, db)
            except ValidationError:
                pass
            else:
                raise ValidationError('DRAFT_RECOVERY_NOT_NEEDED')
            candidates = [dict(r) for r in db.execute('SELECT payload,correction_of,reason FROM draft_history WHERE staged_id=? ORDER BY revision DESC', (staged_id,))]
            candidates.append({'payload':row['payload'], 'correction_of':row['correction_of'], 'reason':row['correction_reason']})
            for saved in candidates:
                try:
                    recovered = decode(saved['payload'], 'bill')
                except ValidationError:
                    continue
                self._save_revision(db, row, recovered, saved['correction_of'], saved['reason'])
                event(db, 'RECOVER_DRAFT', staged_id)
                break
            else:
                raise ValidationError('DRAFT_RECOVERY_REQUIRES_IT_OR_BACKUP')
        return self.stage(staged_id)

    def create_correction(self, bill_id, reason):
        reason = reason_text(reason)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            original = self._active(db, bill_id)
            if db.execute("SELECT 1 FROM staged WHERE correction_of=? AND status='pending'", (bill_id,)).fetchone():
                raise ValidationError('PENDING_CORRECTION_ALREADY_EXISTS')
            source = db.execute('SELECT * FROM staged WHERE id=?', (original['staged_id'],)).fetchone()
            if not source:
                raise ValidationError('ORIGINAL_REVIEW_REQUIRED')
            payload = json.dumps(stored_payload(source, db))
            staged_id = db.execute('''INSERT INTO staged(document_id,kind,payload,created_at,correction_of,correction_reason)
                      VALUES (?,'bill',?,?,?,?)''', (original['document_id'], payload, now(), bill_id, reason)).lastrowid
            event(db, 'CREATE_CORRECTION', staged_id)
            details = db.execute('SELECT fields,differences FROM intake_reviews WHERE staged_id=? ORDER BY revision DESC LIMIT 1', (source['id'],)).fetchone()
            if details:
                db.execute('INSERT INTO intake_reviews VALUES (?,0,?,?)', (staged_id,details[0],details[1]))
        return {'staged_id': staged_id}

    def cancel_bill(self, bill_id, reason, acknowledge=False):
        reason = reason_text(reason)
        if acknowledge is not True:
            raise ValidationError('CONFIRM_CANCELLATION_REPORTING_EFFECT')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            original = self._active(db, bill_id)
            db.execute("UPDATE bills SET status='cancelled' WHERE id=?", (bill_id,))
            db.execute("INSERT INTO bill_history(bill_id,at,action,reason) VALUES (?,?,'cancelled',?)", (bill_id, now(), reason))
            event(db, 'CANCEL_BILL', original['staged_id'])
        return {'id': bill_id, 'status': 'cancelled'}

    def bills(self, building=None, month=None):
        from .reporting import building_scope, reporting_month
        reporting_month(month)
        with self.store.connect() as db:
            _, _, where, params = building_scope(db, building)
            if month is not None:
                where += ' AND substr(b.bill_date,1,7)=?'
                params = (*params, month)
            return [dict(row) for row in db.execute(f"""SELECT b.*,a.alias account_alias,p.name provider,
                SUM(bl.charge_cents) matched_total_cents FROM bills b
                JOIN accounts a ON a.id=b.account_id JOIN providers p ON p.id=a.provider_id
                JOIN bill_lines bl ON bl.bill_id=b.id JOIN meters m ON m.id=bl.meter_id
                WHERE {where} GROUP BY b.id ORDER BY b.bill_date DESC,b.id DESC""", params)]

    def _bill_detail(self, db, bill_id):
        row = db.execute('SELECT * FROM bills WHERE id=?', (bill_id,)).fetchone()
        if not row:
            raise ValidationError('INVOICE_NOT_FOUND')
        result = dict(row)
        ancestors = self._ancestors(db, bill_id)
        root = ancestors[-1]
        versions = [dict(r) for r in db.execute('''WITH RECURSIVE versions AS (
            SELECT * FROM bills WHERE id=? UNION ALL
            SELECT b.* FROM bills b JOIN versions v ON b.supersedes_id=v.id)
            SELECT id,invoice_number,bill_date,current_total_cents,status,staged_id,document_id FROM versions ORDER BY id''', (root,))]
        ids = [v['id'] for v in versions]
        marks = ','.join('?' for _ in ids)
        result['versions'] = versions
        result['history'] = [dict(r) for r in db.execute(f'SELECT * FROM bill_history WHERE bill_id IN ({marks}) ORDER BY id', ids)]
        return result
