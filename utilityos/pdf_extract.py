"""Private in-memory IPC to a disposable local worker, with no automatic download."""
import base64
import json
import os
import subprocess
import sys
import threading
from .config import ROOT
from .extraction import empty_extraction
from .extraction_schema import Extraction

_WORKERS = threading.BoundedSemaphore(1)


def task(raw, *, action='extract', model_dir=None, page=1, rotation=0, timeout=60):
    if not _WORKERS.acquire(timeout=1):
        return empty_extraction('EXTRACTION_BUSY')
    try:
        request = {'data': base64.b64encode(raw).decode(), 'action': action,
                   'model_dir': str(model_dir) if model_dir else None, 'page': page, 'rotation': rotation}
        # Keep environment values and source names out of process arguments and
        # logs. Each child has its own PDFium instance (PDFium is not thread-safe).
        environment = {key: value for key, value in os.environ.items() if key in {'PATH', 'SYSTEMROOT', 'WINDIR'}}
        environment.update({'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1'})
        result = subprocess.run([sys.executable, '-m', 'utilityos.pdf_worker'], cwd=ROOT,
                                input=json.dumps(request).encode(), stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=timeout, env=environment)
        if result.returncode or len(result.stdout) > 20 * 1024 * 1024:
            return empty_extraction('PDF_RESOURCE_LIMIT')
        parsed = json.loads(result.stdout)
        if action == 'render' and set(parsed) == {'png'}:
            return parsed
        return Extraction.model_validate(parsed).model_dump(mode='json')
    except subprocess.TimeoutExpired:
        return empty_extraction('EXTRACTION_TIMED_OUT')
    except (ValueError, OSError):
        return empty_extraction('PDF_UNREADABLE_MANUAL_ENTRY')
    finally:
        _WORKERS.release()
