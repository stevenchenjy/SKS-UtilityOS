"""Explicit local intake attempts and stable-file inbox scanning; no daemon."""
from hashlib import sha256
import os
from pathlib import Path
import stat
import threading
import time
from .audit import now, event
from .config import Config, ROOT, MAX_UPLOAD
from .intake_storage import get_extraction
from .parsers import ValidationError

MAX_BATCH = 25


class Intake:
    def __init__(self, ledger, mode):
        self.ledger, self.store, self.mode = ledger, ledger.store, mode
        self.scan_lock = threading.Lock()

    def recover_interrupted(self):
        # Called once at application startup while the launcher owns its lock.
        with self.store.connect() as db:
            db.execute("UPDATE intake_attempts SET state='failed_safely',code='INTAKE_INTERRUPTED_RETRY_SOURCE',finished_at=? WHERE state IN ('new','processing')", (now(),))
            db.execute('''UPDATE intake_attempts SET document_id=(SELECT id FROM documents WHERE sha256=intake_attempts.sha256),
                       state='extracted',code='INTAKE_COMPLETED_BEFORE_RESPONSE' WHERE code='INTAKE_INTERRUPTED_RETRY_SOURCE'
                       AND EXISTS(SELECT 1 FROM documents WHERE sha256=intake_attempts.sha256)''')

    def import_file(self, filename, raw, origin='picker'):
        filename = Path(filename.replace('\\', '/')).name[:180]
        if origin not in {'picker','inbox'}:
            raise ValidationError('INTAKE_ORIGIN_INVALID')
        digest = sha256(raw).hexdigest()
        with self.store.connect() as db:
            identifier = db.execute('INSERT INTO intake_attempts(filename,sha256,origin,started_at,state) VALUES (?,?,?,?,?)',
                                    (filename,digest,origin,now(),'new')).lastrowid
            event(db,'INTAKE_ATTEMPT')
        with self.store.connect() as db:
            db.execute("UPDATE intake_attempts SET state='processing' WHERE id=?", (identifier,))
        result = {'staged_ids':[], 'count':0}
        code, state, document_id = '', 'extracted', None
        try:
            result = self.ledger.import_file(filename, raw)
            with self.store.connect() as db:
                document_id = db.execute('SELECT id FROM documents WHERE sha256=?', (digest,)).fetchone()[0]
        except ValidationError as exc:
            code = exc.code
            state = 'duplicate' if code == 'DUPLICATE_SOURCE_DOCUMENT' else 'unsupported' if code == 'SUPPORTED_FILES_CSV_XML_PDF' else 'failed_safely'
            if state == 'duplicate':
                with self.store.connect() as db:
                    document_id = db.execute('SELECT id FROM documents WHERE sha256=?', (digest,)).fetchone()[0]
                    result['staged_ids'] = [row[0] for row in db.execute('SELECT id FROM staged WHERE document_id=? ORDER BY id', (document_id,))]
        except Exception:
            code, state = 'INTAKE_FAILED_CHECK_STORAGE_AND_RETRY', 'failed_safely'
        with self.store.connect() as db:
            db.execute('UPDATE intake_attempts SET state=?,code=?,document_id=?,finished_at=? WHERE id=?',
                       (state,code,document_id,now(),identifier))
        return {**result, **self.item(identifier)}

    def _decorate(self, db, row):
        item = dict(row)
        item['staged_ids'] = []
        if item['document_id'] is None:
            return item
        stages = list(db.execute('SELECT id,status,kind FROM staged WHERE document_id=? ORDER BY id', (item['document_id'],)))
        item['staged_ids'] = [row['id'] for row in stages]
        if item['state'] == 'duplicate':
            return item
        statuses = {row['status'] for row in stages}
        if statuses == {'approved'}:
            item['state'] = 'approved'
        elif statuses == {'rejected'}:
            item['state'] = 'rejected'
        elif statuses == {'approved','rejected'}:
            item['state'] = 'partially_approved'
        elif 'pending' in statuses:
            item['state'] = 'needs_review'
            extraction = get_extraction(db,item['document_id'])
            if extraction:
                item['extraction_state'] = 'extracted' if any(field['value'] is not None for field in extraction['fields'].values()) else 'needs_entry'
                item.update(layout_state=extraction['layout_state'], template_version=extraction['template_version'])
                if extraction['pdf_kind'] == 'unreadable':
                    item['state'], item['code'] = 'failed_safely', extraction['codes'][0]
                elif extraction['document_type'] == 'supporting_document':
                    item['state'], item['code'] = 'unsupported', 'SUPPORTING_DOCUMENT_REQUIRES_REVIEW'
                else:
                    provider = extraction['fields']['provider']['value']
                    account = extraction['fields']['account_identifier']['value']
                    meters = [field['value'] for key,field in extraction['fields'].items() if key.endswith('.meter_identifier')]
                    if not meters or any(not db.execute('''SELECT 1 FROM account_meters am JOIN meters m ON m.id=am.meter_id
                            JOIN accounts a ON a.id=am.account_id JOIN providers p ON p.id=a.provider_id
                            WHERE m.code=? AND a.alias=? AND p.name=?''', (meter,account,provider)).fetchone() for meter in meters):
                        item['state'] = 'needs_mapping'
                    if extraction['layout_state'] != 'known':
                        item['code'] = 'KNOWN_PROVIDER_UNKNOWN_LAYOUT' if extraction['provider_key'] else 'UNKNOWN_PROVIDER'
            elif any(row['kind']=='intervals' for row in stages):
                item['state']='needs_mapping'
        return item

    def item(self, identifier):
        with self.store.connect() as db:
            return self._decorate(db,db.execute('SELECT * FROM intake_attempts WHERE id=?',(identifier,)).fetchone())

    def history(self):
        with self.store.connect() as db:
            return [self._decorate(db,row) for row in db.execute('SELECT * FROM intake_attempts ORDER BY id DESC LIMIT 200')]

    def configuration(self):
        with self.store.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key='inbox_directory'").fetchone()
        return {'directory':row[0] if row else '', 'max_files':MAX_BATCH, 'scan_is_explicit':True}

    def _directory(self, value):
        if not isinstance(value,str) or not value or len(value)>2048:
            raise ValidationError('INBOX_DIRECTORY_INVALID')
        original=Path(value).expanduser()
        if not original.is_absolute() or any(p.is_symlink() for p in [original,*original.parents]):
            raise ValidationError('INBOX_DIRECTORY_MUST_BE_ABSOLUTE_WITHOUT_SYMLINKS')
        path=original.resolve()
        try:
            Config(path,self.mode).validate()
        except ValueError:
            raise ValidationError('INBOX_MUST_BE_LOCAL_AND_OUTSIDE_SOURCE') from None
        if path == self.store.directory or path.is_relative_to(self.store.directory) or self.store.directory.is_relative_to(path) or ROOT.is_relative_to(path):
            raise ValidationError('INBOX_MUST_BE_SEPARATE_FROM_CODE_AND_WORKSPACE')
        if not path.is_dir():
            raise ValidationError('CREATE_LOCAL_INBOX_DIRECTORY_FIRST')
        return path

    def configure(self, directory, acknowledge):
        if acknowledge is not True:
            raise ValidationError('CONFIRM_LOCAL_INBOX_LOCATION')
        path = str(self._directory(directory)) if directory else ''
        with self.store.connect() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES ('inbox_directory',?)",(path,))
            event(db,'CONFIGURE_INBOX')
        return self.configuration()

    def scan(self, expected_directory, acknowledge, cursor=0):
        if acknowledge is not True:
            raise ValidationError('CONFIRM_LOCAL_INBOX_SCAN')
        if expected_directory != self.configuration()['directory']:
            raise ValidationError('INBOX_LOCATION_CHANGED_REOPEN')
        path=self._directory(expected_directory)
        if type(cursor) is not int or not 0<=cursor<=1000:
            raise ValidationError('INBOX_SCAN_CURSOR_INVALID')
        if not self.scan_lock.acquire(blocking=False):
            raise ValidationError('INBOX_SCAN_ALREADY_RUNNING')
        try:
            with self.store.connect() as db:
                event(db,'SCAN_INBOX')
            # A bounded, non-recursive snapshot. Files are never moved/deleted.
            candidates=[]
            with os.scandir(path) as entries:
                for index,entry in enumerate(entries):
                    if index>=1000:
                        raise ValidationError('INBOX_EXCEEDS_1000_ENTRIES')
                    if not entry.name.startswith('.') and Path(entry.name).suffix.lower() in {'.pdf','.csv','.xml'}:
                        candidates.append(Path(entry.path))
            results=[]
            for candidate in sorted(candidates)[cursor:cursor+MAX_BATCH]:
                try:
                    before=candidate.lstat()
                    if not stat.S_ISREG(before.st_mode) or before.st_size>MAX_UPLOAD:
                        raise ValidationError('INBOX_FILE_UNSAFE_OR_TOO_LARGE')
                    if time.time_ns()-before.st_mtime_ns<2_000_000_000:
                        raise ValidationError('INBOX_FILE_STILL_CHANGING_RESCAN')
                    descriptor=os.open(candidate,os.O_RDONLY | getattr(os,'O_NOFOLLOW',0))
                    with os.fdopen(descriptor,'rb') as stream:
                        opened=os.fstat(stream.fileno())
                        raw=stream.read(MAX_UPLOAD+1)
                        after=os.fstat(stream.fileno())
                    current=candidate.lstat()
                    identity=lambda item:(item.st_dev,item.st_ino,item.st_size,item.st_mtime_ns,item.st_ctime_ns)
                    if identity(before)!=identity(opened) or identity(opened)!=identity(after) or identity(after)!=identity(current) or len(raw)!=before.st_size:
                        raise ValidationError('INBOX_FILE_CHANGED_DURING_READ_RESCAN')
                    results.append(self.import_file(candidate.name,raw,'inbox'))
                except (OSError,ValueError) as exc:
                    code=exc.code if isinstance(exc,ValidationError) else 'INBOX_FILE_UNREADABLE_RESCAN'
                    with self.store.connect() as db:
                        identifier=db.execute("INSERT INTO intake_attempts(filename,sha256,origin,started_at,finished_at,state,code) VALUES (?,'','inbox',?,?,'failed_safely',?)",
                                              (candidate.name,now(),now(),code)).lastrowid
                        event(db,'INTAKE_ATTEMPT')
                    results.append(self.item(identifier))
            remaining=max(0,len(candidates)-cursor-MAX_BATCH)
            return {'results':results,'remaining':remaining,'next_cursor':cursor+MAX_BATCH if remaining else None}
        finally:
            self.scan_lock.release()
