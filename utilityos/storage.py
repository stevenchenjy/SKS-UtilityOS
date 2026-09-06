"""Atomic local file publication; incomplete writes never get a source filename."""
from pathlib import Path
import hashlib
import os
import tempfile
import re
from .parsers import ValidationError


def sync_directory(path):
    if os.name != 'nt':
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def replace_file(source, target):
    """Both paths must be on the workspace filesystem. Caller validates content."""
    with Path(source).open('rb') as handle:
        os.fsync(handle.fileno())
    os.replace(source, target)
    sync_directory(Path(target).parent)


def publish_source(target: Path, raw: bytes):
    """Publish complete bytes without ever overwriting an existing source.

    A killed process may leave a .pending file or a complete unreferenced source.
    Neither is a financial record; a retry can safely reuse complete bytes.
    """
    sha = hashlib.sha256(raw).hexdigest()
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != sha:
            raise ValidationError('SOURCE_STORAGE_CONFLICT')
        return
    fd, name = tempfile.mkstemp(prefix='.source-', suffix='.pending', dir=target.parent)
    pending = Path(name)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        # A hard link publishes the completed inode and refuses replacement.
        # Temp and destination are in the same directory/filesystem.
        try:
            os.link(pending, target)
        except FileExistsError:
            if target.is_symlink() or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != sha:
                raise ValidationError('SOURCE_STORAGE_CONFLICT') from None
        sync_directory(target.parent)
    finally:
        pending.unlink(missing_ok=True)


def read_source(store, row):
    sha, extension = row['sha256'], row['extension']
    if not re.fullmatch(r'[0-9a-f]{64}', sha) or extension not in {'.csv', '.xml', '.pdf'}:
        raise ValidationError('SOURCE_REFERENCE_INVALID')
    path=store.sources/(sha+extension)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>8*1024*1024:
        raise ValidationError('SOURCE_INTEGRITY_CHECK_FAILED')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha:
        raise ValidationError('SOURCE_INTEGRITY_CHECK_FAILED')
    return raw
