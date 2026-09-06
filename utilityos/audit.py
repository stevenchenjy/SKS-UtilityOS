"""Shared fixed-code audit helpers. Reasons and record history stay private."""
from datetime import datetime, timezone
from decimal import Decimal


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def money(value):
    return f'{Decimal(value)/100:.2f}'


def event(db, code, staged_id=None):
    db.execute('INSERT INTO audit_events(at,code,staged_id) VALUES (?,?,?)', (now(), code, staged_id))
