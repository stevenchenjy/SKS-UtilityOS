from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
import csv
import hashlib
import io
import json
import statistics
from . import __version__
from .db import Store
from .parsers import ValidationError, parse_csv, parse_greenbutton, blank_bill, validate_bill, cents, text


from .audit import now, money, event
from .lifecycle import BillLifecycle
from .inventory import InventoryEditing
from .storage import publish_source, read_source
from .review_data import payload as stored_payload

class Ledger(BillLifecycle, InventoryEditing):
    def __init__(self, store: Store, ocr_model_dir=None):
        self.store = store
        self.ocr_model_dir = ocr_model_dir

    def import_file(self, filename: str, raw: bytes):
        filename = Path(filename.replace('\\','/')).name[:180]
        ext = Path(filename).suffix.lower()
        if not raw:
            raise ValidationError('EMPTY_FILE')
        if ext not in {'.csv','.xml','.pdf'}:
            raise ValidationError('SUPPORTED_FILES_CSV_XML_PDF')
        if len(raw)>8*1024*1024:
            raise ValidationError('FILE_EXCEEDS_8_MB')
        sha = hashlib.sha256(raw).hexdigest()
        with self.store.connect() as db:
            if db.execute('SELECT 1 FROM documents WHERE sha256=?', (sha,)).fetchone():
                raise ValidationError('DUPLICATE_SOURCE_DOCUMENT')
        extraction = None
        if ext=='.csv':
            records = [('bill',bill) for bill in parse_csv(raw)]
        elif ext=='.xml':
            records = [('intervals',channel) for channel in parse_greenbutton(raw)]
        else:
            if not raw.startswith(b'%PDF-'):
                raise ValidationError('PDF_SIGNATURE_INVALID')
            from .pdf_extract import task
            from .extraction import proposed_bill
            extraction = task(raw, model_dir=self.ocr_model_dir)
            records = [('bill', proposed_bill(extraction))]
        target = self.store.sources / f'{sha}{ext}'
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM documents WHERE sha256=?',(sha,)).fetchone():
                raise ValidationError('DUPLICATE_SOURCE_DOCUMENT')
            publish_source(target, raw)
            doc_id = db.execute('INSERT INTO documents(sha256,filename,extension,size,created_at,importer_version) VALUES (?,?,?,?,?,?)',
                                (sha,filename,ext,len(raw),now(),__version__)).lastrowid
            ids = []
            for kind,payload in records:
                ids.append(db.execute('INSERT INTO staged(document_id,kind,payload,created_at) VALUES (?,?,?,?)',
                                     (doc_id,kind,json.dumps(payload),now())).lastrowid)
                event(db, 'CREATE_DRAFT', ids[-1])
            if extraction:
                from .intake_storage import store_extraction
                store_extraction(db, doc_id, ids[0], extraction)
            event(db, {'.csv':'IMPORT_CSV','.xml':'IMPORT_XML','.pdf':'IMPORT_PDF'}[ext])
        return {'staged_ids':ids,'count':len(ids)}

    def _bill_flags(self, db, payload, correction_of=None):
        flags = []
        excluded = self._ancestors(db, correction_of) if correction_of is not None else []
        if correction_of is not None:
            self._active(db, correction_of)
        duplicate = db.execute('''SELECT b.id FROM bills b JOIN accounts a ON a.id=b.account_id
          JOIN providers p ON p.id=a.provider_id WHERE p.name=? AND a.alias=? AND b.invoice_number=?''',
          (payload['provider'],payload['account_alias'],payload['invoice_number'])).fetchall()
        if any(row['id'] not in excluded for row in duplicate):
            flags.append({'code':'DUPLICATE_INVOICE','blocking':True})
        if date.fromisoformat(payload['bill_date']) > date.today():
            flags.append({'code':'FUTURE_INVOICE_DATE','blocking':False})
        for line in payload['lines']:
            meter = db.execute('SELECT m.*,b.name building FROM meters m LEFT JOIN buildings b ON b.id=m.building_id WHERE code=?', (line['meter_code'],)).fetchone()
            if not meter:
                flags.append({'code':'NEW_METER_VERIFY_BUILDING_ASSIGNMENT','blocking':False})
            elif meter['commodity']!=line['commodity'] or meter['unit']!=line['unit']:
                flags.append({'code':'EXISTING_METER_UNIT_OR_COMMODITY_MISMATCH','blocking':True})
            elif (meter['building'] or '')!=line['building']:
                flags.append({'code':'EXISTING_METER_BUILDING_MISMATCH','blocking':True})
            if not line['building']:
                flags.append({'code':'UNASSIGNED_OR_SHARED_METER','blocking':False})
            if line['read_type']=='estimated':
                flags.append({'code':'ESTIMATED_READING','blocking':False})
            if line['usage_role']=='delivery':
                flags.append({'code':'DELIVERED_QUANTITY_IS_A_PURCHASE','blocking':False})
            if cents(line['current_charge'])<0:
                flags.append({'code':'CREDIT_VERIFY_CURRENT_CHARGES','blocking':False})
            if meter and line['usage_role']=='consumption':
                overlap = db.execute('''SELECT 1 FROM bill_lines l JOIN bills b ON b.id=l.bill_id
                                       WHERE b.status='active' AND b.id<>? AND meter_id=? AND usage_role='consumption'
                                       AND period_start<? AND period_end>?''',
                                     (correction_of or -1,meter['id'],line['period_end'],line['period_start'])).fetchone()
                if overlap:
                    flags.append({'code':'APPROVED_CONSUMPTION_PERIOD_OVERLAP','blocking':True})
                previous = db.execute('''SELECT usage,period_start,period_end FROM bill_lines l JOIN bills b ON b.id=l.bill_id
                        WHERE b.status='active' AND meter_id=? AND usage_role='consumption' AND unit=? AND period_end<=?
                        ORDER BY period_end DESC LIMIT 3''', (meter['id'],line['unit'],line['period_start'])).fetchall()
                if len(previous)>=3:
                    rates=[Decimal(row['usage'])/Decimal((date.fromisoformat(row['period_end'])-date.fromisoformat(row['period_start'])).days) for row in previous]
                    baseline=statistics.median(rates)
                    current=Decimal(line['usage'])/Decimal((date.fromisoformat(line['period_end'])-date.fromisoformat(line['period_start'])).days)
                    if baseline and current>baseline*Decimal('1.5'):
                        flags.append({'code':'DAILY_USAGE_ABOVE_150_PERCENT_OF_RECENT_MEDIAN','blocking':False})
        return list({flag['code']:flag for flag in flags}.values())

    def validate_draft(self, payload, staged_id=None, intake_details=None):
        bill=validate_bill(payload)
        with self.store.connect() as db:
            row=self._pending(db,staged_id) if staged_id is not None else None
            flags = self._bill_flags(db,bill,row['correction_of'] if row else None)
            if row:
                from .intake_storage import validation_flags
                flags += validation_flags(db,row,bill,intake_details)
            return {'payload':bill,'flags':flags}

    def approve_bill(self, staged_id: int, payload, acknowledge=False, revision=None, intake_details=None):
        bill=validate_bill(payload)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=self._pending(db,staged_id,revision)
            correction_of=row['correction_of']
            flags=self._bill_flags(db,bill,correction_of)
            from .intake_storage import validation_flags
            flags += validation_flags(db,row,bill,intake_details)
            if correction_of is not None and acknowledge is not True:
                raise ValidationError('REVIEW_WARNINGS_AND_ACKNOWLEDGE')
            if any(flag['blocking'] for flag in flags):
                raise ValidationError(next(flag['code'] for flag in flags if flag['blocking']))
            if flags and not acknowledge:
                raise ValidationError('REVIEW_WARNINGS_AND_ACKNOWLEDGE')
            db.execute('INSERT OR IGNORE INTO providers(name) VALUES (?)',(bill['provider'],))
            provider=db.execute('SELECT id FROM providers WHERE name=?',(bill['provider'],)).fetchone()[0]
            db.execute('INSERT OR IGNORE INTO accounts(provider_id,alias) VALUES (?,?)',(provider,bill['account_alias']))
            account=db.execute('SELECT id FROM accounts WHERE provider_id=? AND alias=?',(provider,bill['account_alias'])).fetchone()[0]
            if correction_of is not None:
                db.execute("UPDATE bills SET status='superseded' WHERE id=?",(correction_of,))
            bill_id=db.execute('''INSERT INTO bills(account_id,invoice_number,bill_date,current_total_cents,document_id,staged_id,approved_at,supersedes_id)
                                VALUES (?,?,?,?,?,?,?,?)''',(account,bill['invoice_number'],bill['bill_date'],cents(bill['current_total']),row['document_id'],staged_id,now(),correction_of)).lastrowid
            for line in bill['lines']:
                building=None
                if line['building']:
                    db.execute('INSERT OR IGNORE INTO buildings(name) VALUES (?)',(line['building'],))
                    building=db.execute('SELECT id FROM buildings WHERE name=?',(line['building'],)).fetchone()[0]
                db.execute('INSERT OR IGNORE INTO meters(code,building_id,commodity,unit) VALUES (?,?,?,?)',
                           (line['meter_code'],building,line['commodity'],line['unit']))
                meter=db.execute('SELECT id FROM meters WHERE code=?',(line['meter_code'],)).fetchone()[0]
                link=db.execute('SELECT * FROM account_meters WHERE account_id=? AND meter_id=? AND valid_from<=? AND (valid_to IS NULL OR valid_to>=?)',
                                (account,meter,line['period_end'],line['period_start'])).fetchone()
                if link:
                    db.execute('UPDATE account_meters SET valid_from=?,valid_to=? WHERE id=?',
                               (min(link['valid_from'],line['period_start']),max(link['valid_to'] or line['period_end'],line['period_end']),link['id']))
                else:
                    db.execute('INSERT INTO account_meters(account_id,meter_id,valid_from,valid_to) VALUES (?,?,?,?)',
                               (account,meter,line['period_start'],line['period_end']))
                event(db, 'OBSERVE_ACCOUNT_MAPPING', staged_id)
                db.execute('''INSERT INTO bill_lines(bill_id,meter_id,period_start,period_end,usage,unit,charge_cents,usage_role,read_type)
                              VALUES (?,?,?,?,?,?,?,?,?)''',(bill_id,meter,line['period_start'],line['period_end'],line['usage'],line['unit'],cents(line['current_charge']),line['usage_role'],line['read_type']))
            self._save_revision(db,row,bill,correction_of,row['correction_reason'],intake_details)
            db.execute('UPDATE staged SET status=?,reviewed_at=? WHERE id=?',('approved',now(),staged_id))
            db.execute("INSERT INTO bill_history(bill_id,at,action,related_bill_id,reason) VALUES (?,?,'approved',?,?)",
                       (bill_id,now(),correction_of,row['correction_reason']))
            if correction_of is not None:
                db.execute("INSERT INTO bill_history(bill_id,at,action,related_bill_id,reason) VALUES (?,?,'superseded',?,?)",
                           (correction_of,now(),bill_id,row['correction_reason']))
                event(db,'SUPERSEDE_BILL',staged_id)
                original_document = db.execute('SELECT document_id FROM bills WHERE id=?', (correction_of,)).fetchone()[0]
                if original_document != row['document_id']:
                    event(db, 'APPROVE_REBILL', staged_id)
            event(db,'APPROVE_BILL',staged_id)
        return {'id':bill_id,'flags':flags}

    def approve_intervals(self, staged_id: int, meter_code: str):
        meter_code=text(meter_code)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            stage=db.execute("SELECT * FROM staged WHERE id=? AND kind='intervals' AND status='pending'",(staged_id,)).fetchone()
            if not stage:
                raise ValidationError('PENDING_INTERVAL_IMPORT_REQUIRED')
            payload=stored_payload(stage,db)
            document=db.execute('SELECT sha256,extension FROM documents WHERE id=?',(stage['document_id'],)).fetchone()
            originals=parse_greenbutton(read_source(self.store,document))
            if payload not in originals:
                raise ValidationError('DRAFT_DATA_DAMAGED_RECOVERY_REQUIRED')
            meter=db.execute("SELECT id FROM meters WHERE code=? AND commodity='electricity' AND unit='kWh'",(meter_code,)).fetchone()
            if not meter:
                raise ValidationError('MAP_TO_EXISTING_ELECTRICITY_KWH_METER')
            # One consumption stream per local meter in this pilot prevents a
            # second supplier/usage point from silently duplicating the stream.
            if db.execute('SELECT 1 FROM interval_channels WHERE source_channel=? AND meter_id<>?',(payload['source_channel'],meter['id'])).fetchone():
                raise ValidationError('INTERVAL_STREAM_ALREADY_MAPPED_TO_ANOTHER_METER')
            existing=db.execute('SELECT * FROM interval_channels WHERE meter_id=?',(meter['id'],)).fetchall()
            if any(item['source_channel']!=payload['source_channel'] for item in existing):
                raise ValidationError('METER_ALREADY_MAPPED_TO_ANOTHER_INTERVAL_STREAM')
            db.execute('INSERT OR IGNORE INTO interval_channels(meter_id,source_channel,metadata) VALUES (?,?,?)',
                       (meter['id'],payload['source_channel'],json.dumps(payload['metadata'],sort_keys=True)))
            channel=db.execute('SELECT * FROM interval_channels WHERE meter_id=? AND source_channel=?',(meter['id'],payload['source_channel'])).fetchone()
            if json.loads(channel['metadata'])!=payload['metadata']:
                raise ValidationError('INTERVAL_METADATA_CHANGED_REQUIRES_REVIEW')
            skipped=0
            for item in payload['readings']:
                prior=db.execute('SELECT * FROM interval_readings WHERE channel_id=? AND start_utc=?',(channel['id'],item['start_utc'])).fetchone()
                if prior:
                    if prior['duration_s']!=item['duration_s'] or Decimal(prior['quantity'])!=Decimal(item['quantity']) or prior['quality']!=item['quality']:
                        raise ValidationError('INTERVAL_REVISION_CONFLICT_REQUIRES_REVIEW')
                    skipped+=1
                    continue
                overlap=db.execute('''SELECT 1 FROM interval_readings WHERE channel_id=? AND start_utc<? AND start_utc+duration_s>?''',
                                   (channel['id'],item['start_utc']+item['duration_s'],item['start_utc'])).fetchone()
                if overlap:
                    raise ValidationError('INTERVAL_OVERLAPS_APPROVED_READING')
                db.execute('INSERT INTO interval_readings VALUES (?,?,?,?,?,?)',
                           (channel['id'],item['start_utc'],item['duration_s'],item['quantity'],item['quality'],stage['document_id']))
            db.execute('UPDATE staged SET status=?,reviewed_at=?,review_payload=? WHERE id=?',
                       ('approved',now(),json.dumps({'meter_code':meter_code}),staged_id))
            event(db,'APPROVE_INTERVALS',staged_id)
        return {'inserted':len(payload['readings'])-skipped,'identical_readings_skipped':skipped}

    def reject(self, staged_id):
        with self.store.connect() as db:
            cur=db.execute("UPDATE staged SET status='rejected',reviewed_at=? WHERE id=? AND status='pending'",(now(),staged_id))
            if not cur.rowcount:
                raise ValidationError('PENDING_ITEM_REQUIRED')
            event(db,'REJECT_DRAFT',staged_id)

    def inventory(self):
        with self.store.connect() as db:
            buildings=[dict(r) for r in db.execute('SELECT b.*,COUNT(m.id) meter_count FROM buildings b LEFT JOIN meters m ON m.building_id=b.id GROUP BY b.id ORDER BY name')]
            meters=[dict(r) for r in db.execute('SELECT m.*,b.name building FROM meters m LEFT JOIN buildings b ON b.id=m.building_id ORDER BY code')]
            accounts=[dict(r) for r in db.execute('''SELECT a.id,a.alias,p.name provider,COUNT(DISTINCT am.meter_id) meter_count
                        FROM accounts a JOIN providers p ON p.id=a.provider_id LEFT JOIN account_meters am ON am.account_id=a.id GROUP BY a.id ORDER BY p.name,a.alias''')]
            links=[dict(r) for r in db.execute('SELECT * FROM account_meters ORDER BY valid_from')]
            history=[dict(r) for r in db.execute('SELECT * FROM inventory_history ORDER BY id DESC LIMIT 100')]
        return {'buildings':buildings,'meters':meters,'accounts':accounts,'account_meters':links,'history':history}

    def stages(self):
        with self.store.connect() as db:
            result=[]
            for row in db.execute("SELECT s.*,d.filename,d.extension,b.status bill_status FROM staged s JOIN documents d ON d.id=s.document_id LEFT JOIN bills b ON b.staged_id=s.id WHERE s.status='pending' OR s.id IN (SELECT id FROM staged WHERE status<>'pending' ORDER BY id DESC LIMIT 500) ORDER BY s.id DESC"):
                item=dict(row)
                try:
                    payload=stored_payload(row,db)
                except ValidationError:
                    item.pop('payload');item.pop('review_payload',None)
                    item.update({'label':'Damaged review data','provider':'Recovery required','current_total':None,'data_error':'DRAFT_DATA_DAMAGED_RECOVERY_REQUIRED'})
                    result.append(item)
                    continue
                item.pop('payload')
                item.pop('review_payload',None)
                if item['kind']=='bill':
                    item.update({'label':payload.get('invoice_number') or 'PDF requires staff entry','provider':payload.get('provider') or 'Unassigned',
                                 'current_total':payload.get('current_total') or None})
                else:
                    item.update({'label':'Electricity interval file','provider':'Map to a local meter','interval_count':len(payload['readings'])})
                result.append(item)
        return result

    def stage(self, staged_id):
        with self.store.connect() as db:
            row=db.execute('SELECT s.*,d.filename,d.extension,d.sha256 source_sha256,d.importer_version FROM staged s JOIN documents d ON d.id=s.document_id WHERE s.id=?',(staged_id,)).fetchone()
            if not row:
                raise ValidationError('ITEM_NOT_FOUND')
            item=dict(row)
            try:
                item['payload']=stored_payload(row,db)
            except ValidationError:
                item.pop('payload');item.pop('review_payload',None)
                item['data_error']='DRAFT_DATA_DAMAGED_RECOVERY_REQUIRED'
                return item
            item.pop('review_payload',None)
            if item['kind']=='bill':
                from .intake_storage import review_info, validation_flags
                item['intake'] = review_info(db,row,item['payload'])
                try:
                    payload=validate_bill(item['payload'])
                    item['flags']=self._bill_flags(db,payload,item['correction_of']) if item['status']=='pending' else []
                    if item['status']=='pending':
                        item['flags'] += validation_flags(db,row,payload)
                except ValidationError as exc:
                    item['flags']=[{'code':exc.code,'blocking':True}]
                approved=db.execute('SELECT id FROM bills WHERE staged_id=?',(staged_id,)).fetchone()
                item['bill']=self._bill_detail(db,approved['id']) if approved else None
                item['original_bill']=self._bill_detail(db,item['correction_of']) if item['correction_of'] else None
                item['draft_history']=[dict(r) for r in db.execute('SELECT at,revision,reason FROM draft_history WHERE staged_id=? ORDER BY revision',(staged_id,))]
            else:
                readings=item['payload'].pop('readings')
                item['payload'].update({'interval_count':len(readings),'first_utc':readings[0]['start_utc'],
                                       'last_utc':readings[-1]['start_utc']+readings[-1]['duration_s'],
                                       'total_kwh':format(sum(Decimal(r['quantity']) for r in readings),'f')})
        return item

    def overview(self, month=None):
        with self.store.connect() as db:
            monthly=[dict(r) for r in db.execute("SELECT substr(bill_date,1,7) month,SUM(current_total_cents) cents,COUNT(*) bills FROM bills WHERE status='active' GROUP BY month ORDER BY month")]
            available=[row['month'] for row in monthly]
            selected=month if month in available else (available[-1] if available else None)
            rows=db.execute('''SELECT bl.*,m.commodity,m.code,bld.name building,b.bill_date FROM bill_lines bl
                     JOIN bills b ON b.id=bl.bill_id JOIN meters m ON m.id=bl.meter_id LEFT JOIN buildings bld ON bld.id=m.building_id
                     WHERE b.status='active' AND substr(b.bill_date,1,7)=?''',(selected,)).fetchall()
            stats={'buildings':db.execute('SELECT COUNT(*) FROM buildings').fetchone()[0],
                   'meters':db.execute('SELECT COUNT(*) FROM meters').fetchone()[0],
                   'accounts':db.execute('SELECT COUNT(*) FROM accounts').fetchone()[0],
                   'pending':db.execute("SELECT COUNT(*) FROM staged WHERE status='pending'").fetchone()[0],
                   'approved_bills':db.execute("SELECT COUNT(*) FROM bills WHERE status='active'").fetchone()[0]}
            latest=[dict(r) for r in db.execute('''SELECT b.id,b.invoice_number,b.bill_date,b.current_total_cents,b.staged_id,p.name provider
                       FROM bills b JOIN accounts a ON a.id=b.account_id JOIN providers p ON p.id=a.provider_id WHERE b.status='active' ORDER BY b.bill_date DESC,b.id DESC LIMIT 6''')]
            quantities=defaultdict(Decimal)
            cost=defaultdict(int)
            buildings=defaultdict(int)
            for row in rows:
                cost[row['commodity']]+=row['charge_cents']
                buildings[row['building'] or 'Unassigned / shared']+=row['charge_cents']
                if row['usage_role']!='charges_only':
                    quantities[(row['commodity'],row['unit'],row['usage_role'])]+=Decimal(row['usage'])
            selected_total=next((row['cents'] for row in monthly if row['month']==selected),0)
        return {'selected_month':selected,'months':available,'monthly':monthly,'stats':stats,'total_cents':selected_total,
                'cost_by_commodity':[{'commodity':k,'cents':v} for k,v in sorted(cost.items())],
                'cost_by_building':[{'building':k,'cents':v} for k,v in sorted(buildings.items(),key=lambda x:-x[1])],
                'quantities':[{'commodity':k[0],'unit':k[1],'role':k[2],'value':format(v,'f')} for k,v in quantities.items()],
                'latest':latest}

    def intervals(self,meter_code=None):
        with self.store.connect() as db:
            channels=[dict(r) for r in db.execute('SELECT c.id,m.code,m.unit,b.name building FROM interval_channels c JOIN meters m ON m.id=c.meter_id LEFT JOIN buildings b ON b.id=m.building_id ORDER BY code')]
            channel=next((row for row in channels if row['code']==meter_code),channels[0] if channels else None)
            rows=[dict(r) for r in db.execute('SELECT start_utc,duration_s,quantity,quality FROM interval_readings WHERE channel_id=? ORDER BY start_utc DESC LIMIT 1000',(channel['id'],))][::-1] if channel else []
            total_count=db.execute('SELECT COUNT(*) FROM interval_readings WHERE channel_id=?',(channel['id'],)).fetchone()[0] if channel else 0
        return {'channels':channels,'selected':channel,'readings':rows,'total_readings':total_count,
                'display_timezone':'America/New_York','display_limit':1000}

    def diagnostics(self, mode, port=8765, *, running=False):
        from .diagnostics import report
        return report(self.store.directory, mode, port, running=running)

    def audit_history(self, before=None):
        from .audit import verify
        if before is not None and (type(before) is not int or before < 1):
            raise ValidationError('AUDIT_CURSOR_INVALID')
        with self.store.connect() as db:
            verify(db)
            rows = [dict(r) for r in db.execute('SELECT id,at,code,staged_id,actor,subject_kind,subject_id,operation_id FROM audit_events WHERE id<? ORDER BY id DESC LIMIT 101', (before or 2**63-1,))]
        return {'events':rows[:100], 'next_before':rows[99]['id'] if len(rows)>100 else None,
                'attribution':'Single local operator; named-person attribution is unavailable.'}

    def export_csv(self):
        def safe(value):
            raw=str(value or '')
            return "'"+raw if raw.lstrip().startswith(('=','+','-','@','\t','\r')) else raw
        out=io.StringIO(newline='')
        writer=csv.writer(out)
        header=['provider','account_alias','invoice_number','bill_date','meter_code','building','commodity','period_start','period_end','usage','unit','current_charge','usage_role','read_type','current_total']
        writer.writerow(header)
        with self.store.connect() as db:
            rows=db.execute('''SELECT p.name provider,a.alias account_alias,b.invoice_number,b.bill_date,m.code meter_code,
                 COALESCE(bld.name,'') building,m.commodity,l.*,b.current_total_cents FROM bill_lines l
                 JOIN bills b ON b.id=l.bill_id JOIN accounts a ON a.id=b.account_id JOIN providers p ON p.id=a.provider_id
                 JOIN meters m ON m.id=l.meter_id LEFT JOIN buildings bld ON bld.id=m.building_id WHERE b.status='active' ORDER BY b.id,l.id''')
            for row in rows:
                values=dict(row)
                values['current_charge']=money(row['charge_cents'])
                values['current_total']=money(row['current_total_cents'])
                writer.writerow([values[k] if k in {'usage','current_charge','current_total'} else safe(values[k]) for k in header])
        return out.getvalue().encode('utf-8-sig')
