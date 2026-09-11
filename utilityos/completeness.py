"""Explicit invoice-month expectations, never inferred campus coverage."""
from datetime import date
import json
import re
from .audit import event, now
from .parsers import ValidationError, text
from .review_data import payload as stored_payload


def month(value):
    if not isinstance(value,str) or not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',value):
        raise ValidationError('EXPECTATION_MONTH_INVALID')
    return value


class Completeness:
    def __init__(self,store):
        self.store=store

    def configure(self,data):
        if data.get('scope') == 'account':
            from .billing_schedules import configure
            return configure(self.store, data)
        if data.get('acknowledge') is not True:
            raise ValidationError('CONFIRM_EXPECTED_BILL_CADENCE')
        if any(type(data.get(key)) is not int for key in ('account_id','meter_id','revision')):
            raise ValidationError('EXPECTATION_IDENTIFIERS_INVALID')
        if data.get('cadence') not in {'monthly','delivery','irregular'} or type(data.get('enabled')) is not bool:
            raise ValidationError('EXPECTATION_CADENCE_INVALID')
        first=month(data.get('first_month'));last=month(data['last_month']) if data.get('last_month') else None
        if last and last<first:
            raise ValidationError('EXPECTATION_MONTH_RANGE_INVALID')
        reason=text(data.get('reason'),max_len=500)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM account_meters WHERE account_id=? AND meter_id=?', (data['account_id'],data['meter_id'])).fetchone():
                raise ValidationError('CONFIRMED_ACCOUNT_METER_RELATIONSHIP_REQUIRED')
            before=db.execute('SELECT * FROM bill_expectations WHERE account_id=? AND meter_id=?', (data['account_id'],data['meter_id'])).fetchone()
            if data['revision']!=(before['revision'] if before else 0):
                raise ValidationError('EXPECTATION_CHANGED_REOPEN')
            db.execute('''INSERT INTO bill_expectations(account_id,meter_id,cadence,first_month,last_month,enabled,revision)
                        VALUES (?,?,?,?,?,?,?) ON CONFLICT(account_id,meter_id) DO UPDATE SET cadence=excluded.cadence,
                        first_month=excluded.first_month,last_month=excluded.last_month,enabled=excluded.enabled,revision=excluded.revision''',
                       (data['account_id'],data['meter_id'],data['cadence'],first,last,int(data['enabled']),data['revision']+1))
            after=db.execute('SELECT * FROM bill_expectations WHERE account_id=? AND meter_id=?',(data['account_id'],data['meter_id'])).fetchone()
            db.execute('INSERT INTO expectation_history(expectation_id,at,before_value,after_value,reason) VALUES (?,?,?,?,?)',
                       (after['id'],now(),json.dumps(dict(before)) if before else None,json.dumps(dict(after)),reason))
            event(db,'CONFIGURE_EXPECTATION')
        return {'ok':True}

    def report(self,selected=None,*,as_of=None):
        selected=month(selected or date.today().strftime('%Y-%m'))
        with self.store.connect() as db:
            expectations=[dict(row) for row in db.execute('''SELECT e.*,a.alias account_alias,p.name provider,m.code meter_code
                          FROM bill_expectations e JOIN accounts a ON a.id=e.account_id JOIN providers p ON p.id=a.provider_id
                          JOIN meters m ON m.id=e.meter_id ORDER BY p.name,m.code''')]
            approved={(row[0],row[1]) for row in db.execute('''SELECT DISTINCT b.account_id,l.meter_id FROM bills b
                      JOIN bill_lines l ON l.bill_id=b.id WHERE b.status='active' AND substr(b.bill_date,1,7)=?''',(selected,))}
            pending=set()
            for row in db.execute("SELECT * FROM staged WHERE kind='bill' AND status='pending'"):
                try:
                    bill=stored_payload(row,db)
                except ValidationError:
                    continue
                if bill['bill_date'][:7]==selected:
                    pending.update((bill['provider'],bill['account_alias'],line['meter_code']) for line in bill['lines'])
        counts={'expected':0,'received':0,'under_review':0,'approved':0,'missing':0}
        rows=[]
        for item in expectations:
            if not item['enabled'] or item['first_month']>selected or item['last_month'] and item['last_month']<selected:
                continue
            is_approved=(item['account_id'],item['meter_id']) in approved
            is_pending=(item['provider'],item['account_alias'],item['meter_code']) in pending
            state='approved' if is_approved else 'under_review' if is_pending else 'missing' if item['cadence']=='monthly' else 'not_scheduled'
            item.update(state=state,also_under_review=is_pending and is_approved)
            rows.append(item)
            if item['cadence']=='monthly':
                counts['expected']+=1
                counts[state]+=1
                if state in {'approved','under_review'}:counts['received']+=1
        result = {'month':selected,'basis':'invoice_month','authoritative':False,'counts':counts,'rows':rows,'configuration':expectations}
        from .billing_schedules import apply
        with self.store.connect() as db:
            return apply(db, result, selected, as_of)
