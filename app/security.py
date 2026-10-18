"""Salted password hashes and server-side, hashed opaque bearer tokens."""
import hashlib
import hmac
import secrets
import time

ACCESS_SECONDS = 3600
REFRESH_SECONDS = 604800


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f'{salt}:{digest}'


def verify_password(password, encoded):
    return hmac.compare_digest(hash_password(password, encoded.split(':')[0]), encoded)


def token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def issue_tokens(db, user_id):
    result = {'token_type': 'bearer', 'expires_in': ACCESS_SECONDS}
    for kind, ttl in [('access', ACCESS_SECONDS), ('refresh', REFRESH_SECONDS)]:
        token = secrets.token_urlsafe(32)
        db.execute('INSERT INTO tokens VALUES (?,?,?,?)',
                   (token_digest(token), user_id, kind, time.time() + ttl))
        result[f'{kind}_token'] = token
    return result
