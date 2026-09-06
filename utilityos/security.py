"""Local app authentication. Utility portal credentials are never requested."""
import hashlib
import hmac
import secrets
import time
from .db import Store

DEMO_PASSWORD = "synthetic-demo-only"
ITERATIONS = 600_000


def set_password(store: Store, password: str) -> None:
    if len(password) < 12 or len(password) > 256:
        raise ValueError("PASSPHRASE_REQUIRES_12_TO_256_CHARACTERS")
    salt = secrets.token_hex(32)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    with store.connect() as db:
        for key, value in {"password_salt": salt, "password_hash": digest}.items():
            db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))


def has_password(store: Store) -> bool:
    with store.connect() as db:
        return db.execute("SELECT 1 FROM settings WHERE key='password_hash'").fetchone() is not None


def verify_password(store: Store, password: str) -> bool:
    if len(password) > 256:
        return False
    with store.connect() as db:
        values = dict(db.execute("SELECT key,value FROM settings WHERE key LIKE 'password_%'"))
    if "password_salt" not in values:
        return False
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(values['password_salt']), ITERATIONS).hex()
    return hmac.compare_digest(test, values['password_hash'])


class Sessions:
    """Memory-only sessions; logout/restart invalidates them. Single-user local pilot."""
    def __init__(self):
        self.items = {}
        self.failures = []

    def rate_limited(self):
        now = time.monotonic()
        self.failures = [x for x in self.failures if now-x < 60]
        return len(self.failures) >= 5

    def create(self):
        self.items = {key: value for key, value in self.items.items() if time.monotonic()-value['last'] < 1800}
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.items[hashlib.sha256(token.encode()).hexdigest()] = {'csrf': csrf, 'last': time.monotonic(), 'created': time.monotonic()}
        return token, csrf

    def get(self, token):
        key = hashlib.sha256((token or '').encode()).hexdigest()
        item = self.items.get(key)
        if item and time.monotonic()-item['last'] < 1800 and time.monotonic()-item['created'] < 28800:
            item['last'] = time.monotonic()
            return item
        self.items.pop(key, None)
        return None

    def remove(self, token):
        self.items.pop(hashlib.sha256((token or '').encode()).hexdigest(), None)
