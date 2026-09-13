"""Opt-in bounded acquisition worker owned by the running application.

Configuration of the folder is durable; permission to watch is deliberately not.
Each launch starts disabled, including restored workspaces. No network, recursive
traversal, source modification or financial/operational approval is available.
"""
import os
from pathlib import Path
import threading
import time
from .adapters import ADAPTERS, identify
from .audit import event, now
from .connectors import PortfolioManagerBoundary
from .parsers import ValidationError

POLL_SECONDS = 5
STABLE_SECONDS = 2
MAX_ENTRIES = 1000
TEMP_SUFFIXES = ('.crdownload', '.part', '.partial', '.download', '.tmp', '.temp')


class Acquisition:
    def __init__(self, intake):
        self.intake = intake
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.worker = None
        self.closed = False
        self.state = 'disabled'
        self.generation = 0
        self.observed = {}
        self.attempted = {}
        self.last_poll = None
        self.last_success = None
        self.error = ''
        self.processing = False

    def start(self):
        if self.worker is not None:
            return
        self.worker = threading.Thread(target=self._run, name='utilityos-acquisition', daemon=False)
        self.worker.start()

    def stop(self):
        with self.lock:
            self.closed = True
            self.state = 'disabled'
            self.generation += 1
        self.wake.set()
        if self.worker is not None:
            self.worker.join()  # Finish at most one bounded import before exit.

    def _run(self):
        while not self.wake.wait(POLL_SECONDS):
            if self.closed:
                return
            self.tick()

    def control(self, data):
        action = data.get('action')
        if action not in {'enable', 'disable', 'pause', 'resume'}:
            raise ValidationError('ACQUISITION_ACTION_INVALID')
        with self.lock:
            if self.closed:
                raise ValidationError('ACQUISITION_APPLICATION_STOPPING')
            if action in {'enable', 'resume'}:
                if data.get('acknowledge') is not True:
                    raise ValidationError('CONFIRM_LOCAL_ACQUISITION')
                if self.intake.mode == 'demo' and data.get('synthetic') is not True:
                    raise ValidationError('DEMO_REQUIRES_SYNTHETIC_DATA_CONFIRMATION')
                directory = self.intake.configuration()['directory']
                if data.get('directory') != directory:
                    raise ValidationError('INBOX_LOCATION_CHANGED_REOPEN')
                self.intake._directory(directory)
                if action == 'resume' and self.state != 'paused':
                    raise ValidationError('ACQUISITION_PAUSED_STATE_REQUIRED')
            if action == 'pause' and self.state != 'watching':
                raise ValidationError('ACQUISITION_WATCHING_STATE_REQUIRED')
            self.state = {'enable':'watching', 'resume':'watching', 'pause':'paused', 'disable':'disabled'}[action]
            self.generation += 1
            self.error = ''
            # Reobserve on every enable/resume so a file changed while paused
            # must again be stable across separate polls.
            self.observed.clear()
            with self.intake.store.connect() as db:
                event(db, 'ACQUISITION_' + action.upper())
        return self.status()

    def configure(self, directory, acknowledge):
        with self.lock:
            if self.state != 'disabled' or self.processing:
                raise ValidationError('DISABLE_ACQUISITION_BEFORE_CHANGING_FOLDER')
            result = self.intake.configure(directory, acknowledge)
            self.observed.clear()
            self.attempted.clear()
            return result

    def tick(self, monotonic=None):
        moment = time.monotonic() if monotonic is None else monotonic
        with self.lock:
            if self.closed or self.state != 'watching':
                return
            generation = self.generation
        if not self.intake.scan_lock.acquire(blocking=False):
            return
        try:
            directory = self.intake._directory(self.intake.configuration()['directory'])
            candidates = []
            with os.scandir(directory) as entries:
                for index, entry in enumerate(entries):
                    if index >= MAX_ENTRIES:
                        raise ValidationError('INBOX_EXCEEDS_1000_ENTRIES')
                    if entry.name.startswith('.') or entry.name.lower().endswith(TEMP_SUFFIXES):
                        continue
                    # Only ordinary files and symlinks (which get a safe error)
                    # are considered; subdirectories are never traversed.
                    if not entry.is_dir(follow_symlinks=False):
                        candidates.append(Path(entry.path))
            live = {str(p) for p in candidates}
            with self.lock:
                self.last_poll = now()
                self.error = ''
                self.observed = {k:v for k,v in self.observed.items() if k in live}
                self.attempted = {k:v for k,v in self.attempted.items() if k in live}
            for candidate in sorted(candidates):
                key = str(candidate)
                try:
                    signature = self.intake.identity(candidate.lstat())
                except OSError:
                    continue
                with self.lock:
                    if self.state != 'watching' or self.generation != generation or self.closed:
                        return
                    if self.attempted.get(key) == signature:
                        continue
                    prior = self.observed.get(key)
                    if prior is None or prior[0] != signature:
                        self.observed[key] = (signature, moment)
                        continue
                    if moment - prior[1] < STABLE_SECONDS:
                        continue
                    self.processing = True
                try:
                    raw = self.intake.read_stable(candidate)
                    with self.lock:
                        if self.state != 'watching' or self.generation != generation or self.closed:
                            return
                    result = self.intake.import_file(candidate.name, raw, 'inbox')
                    with self.lock:
                        self.attempted[key] = signature
                        if result.get('document_id'):
                            self.last_success = now()
                except (OSError, ValueError) as exc:
                    code = exc.code if isinstance(exc, ValidationError) else 'INBOX_FILE_UNREADABLE_RESCAN'
                    if code in {'INBOX_FILE_STILL_CHANGING_RESCAN', 'INBOX_FILE_CHANGED_DURING_READ_RESCAN'}:
                        # A future timestamp or continuing download must not
                        # starve stable files later in the bounded snapshot.
                        # No parser/import was called for this candidate.
                        continue
                    self.intake.record_failure(candidate.name, code)
                    with self.lock:
                        self.attempted[key] = signature
                finally:
                    with self.lock:
                        self.processing = False
                # At most one file per tick: bounded CPU, storage and queue work.
                return
        except Exception as exc:
            with self.lock:
                self.error = exc.code if isinstance(exc, ValidationError) else 'ACQUISITION_CHECK_FOLDER_AND_RETRY'
        finally:
            self.intake.scan_lock.release()

    def status(self):
        history = self.intake.history()
        # Successful documents also include direct mapped-usage uploads, which
        # have their own immutable audit path and need not be inbox attempts.
        with self.intake.store.connect() as db:
            documents = [dict(row) for row in db.execute('''SELECT d.id,d.filename,d.extension,d.created_at,
                EXISTS(SELECT 1 FROM usage_imports u WHERE u.document_id=d.id) operational,
                (SELECT COUNT(*) FROM staged s WHERE s.document_id=d.id AND s.status='pending') +
                (SELECT COUNT(*) FROM usage_imports u WHERE u.document_id=d.id AND NOT EXISTS
                    (SELECT 1 FROM usage_decisions x WHERE x.import_id=u.id)) pending
                FROM documents d ORDER BY d.id DESC''')]
        for document in documents:
            document['adapter'] = ('usage_xlsx' if document['extension']=='.xlsx' else 'usage_csv') if document['operational'] else {
                '.pdf':'pdf_invoice','.csv':'invoice_csv','.xml':'green_button'}.get(document['extension'],'unsupported')
        modes = []
        for adapter in ADAPTERS:
            attempts = [r for r in history if r.get('adapter') == adapter['id']]
            retained = [r for r in documents if r['adapter'] == adapter['id']]
            latest = attempts[0] if attempts else None
            successful = retained[0] if retained else None
            if successful and (not latest or successful['created_at'] > latest['started_at']):
                latest = {'filename':successful['filename'],'started_at':successful['created_at']}
            modes.append({**adapter, 'last_file': latest['filename'] if latest else None,
                          'last_attempt': latest['started_at'] if latest else None,
                          'last_success': successful['created_at'] if successful else None,
                          'pending_review': sum(r['pending'] for r in retained),
                          'errors': sum(r['state'] in {'unsupported','failed_safely'} for r in attempts)})
        with self.lock:
            return {'state': self.state, 'processing': self.processing,
                    'directory': self.intake.configuration()['directory'],
                    'poll_seconds': POLL_SECONDS, 'stable_seconds': STABLE_SECONDS,
                    'last_poll': self.last_poll, 'last_success': self.last_success,
                    'error': self.error, 'recursive': False, 'restart_state': 'disabled',
                    'sources': modes, 'history': history,
                    'connector': {**PortfolioManagerBoundary.status(), 'network_enabled':False}}
