"""Private in-memory IPC to a disposable local worker, with no automatic download."""
import base64
import json
import os
import subprocess
import sys
import threading
import time
from .config import ROOT
from .extraction import empty_extraction
from .extraction_schema import Extraction

_WORKERS = threading.BoundedSemaphore(1)
_EXTRACTION_QUEUE = threading.BoundedSemaphore(1)


def task(raw, *, action='extract', model_dir=None, page=1, rotation=0, timeout=60):
    deadline = time.monotonic() + timeout
    if action == 'render':
        acquired = _WORKERS.acquire(timeout=min(1, timeout))
    else:
        # A page preview must not turn the next bill into a permanent empty
        # extraction. Admit at most one waiting extraction; waiting and execution
        # share the existing deadline, with only one worker active at a time.
        if not _EXTRACTION_QUEUE.acquire(blocking=False):
            return empty_extraction('EXTRACTION_BUSY')
        try:
            acquired = _WORKERS.acquire(timeout=max(0, deadline - time.monotonic()))
        finally:
            _EXTRACTION_QUEUE.release()
    if not acquired:
        return empty_extraction('EXTRACTION_BUSY')
    try:
        request = {'data': base64.b64encode(raw).decode(), 'action': action,
                   'model_dir': str(model_dir) if model_dir else None, 'page': page, 'rotation': rotation}
        # Keep environment values and source names out of process arguments and
        # logs. Each child has its own PDFium instance (PDFium is not thread-safe).
        environment = {key: value for key, value in os.environ.items() if key in {'PATH', 'SYSTEMROOT', 'WINDIR'}}
        environment.update({'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1'})
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return empty_extraction('EXTRACTION_TIMED_OUT')
        result = subprocess.run([sys.executable, '-m', 'utilityos.pdf_worker'], cwd=ROOT,
                                input=json.dumps(request).encode(), stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=remaining, env=environment)
        if result.returncode or len(result.stdout) > 20 * 1024 * 1024:
            return empty_extraction('PDF_RESOURCE_LIMIT')
        parsed = json.loads(result.stdout)
        if action == 'render' and set(parsed) == {'png'}:
            return parsed
        if action == 'observe' and 'adapter_version' in parsed:
            from .provider_rules import Observations
            return Observations.model_validate(parsed).model_dump(mode='json')
        return Extraction.model_validate(parsed).model_dump(mode='json')
    except subprocess.TimeoutExpired:
        return empty_extraction('EXTRACTION_TIMED_OUT')
    except (ValueError, OSError):
        return empty_extraction('PDF_UNREADABLE_MANUAL_ENTRY')
    finally:
        _WORKERS.release()
