"""Garmin OAuth attempt persistence, NOT an exposed endpoint in v0.7.

Identity MUST be an already-verified internal principal from a separately
implemented ChatGPT-compatible OAuth authorization server. Demo bearer != user.
State is random and only its SHA256 fingerprint is stored. The PKCE verifier is
AES-GCM encrypted under a server-held key. Each state is atomically consumed.
"""
import hashlib
import time
from datetime import datetime, timezone, timedelta
from .identity import VerifiedPrincipal
from .garmin_oauth import create_authorization_attempt, build_authorization_url
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

TTL_SECONDS = 600

def state_digest(state):
    if not isinstance(state, str) or not 20 <= len(state) <= 256:
        raise ValueError('Invalid OAuth state')
    return hashlib.sha256(state.encode('ascii')).hexdigest()

class PendingOAuthStore:
    """Requires existing athlete row and migrated oauth_attempts table.

    A separate connection per transaction, scoped via transaction-local GUC;
    RLS is an additional guard, not an authentication mechanism.
    Use a *dedicated*, persistent encryption key in Render secrets.
    """
    def __init__(self, database_url, encryption_key, *, connection_factory=None, clock=None):
        from .postgres_store import validate_database_url
        self.url = validate_database_url(database_url)
        if not isinstance(encryption_key, bytes) or len(encryption_key) != 32:
            raise ValueError('32-byte key required')
        self._aes = AESGCM(encryption_key)
        self._factory = connection_factory
        self._clock = clock or time.time

    def _connect(self):
        if self._factory:
            return self._factory(self.url)
        import psycopg
        return psycopg.connect(self.url, connect_timeout=8)

    @staticmethod
    def _sub(principal):
        if not isinstance(principal, VerifiedPrincipal):
            raise PermissionError('Verified principal required')
        return principal.subject

    def begin(self, principal, *, client_id, redirect_uri):
        subject = self._sub(principal)
        attempt = create_authorization_attempt(now=self._clock())
        digest = state_digest(attempt.state)
        nonce = os.urandom(12)
        aad = ('garminai:oauth-state:v07:' + subject + ':' + digest).encode()
        encrypted = self._aes.encrypt(nonce, attempt.verifier.encode('ascii'), aad)
        expires = datetime.fromtimestamp(int(self._clock()), tz=timezone.utc) + timedelta(seconds=TTL_SECONDS)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('garminai.subject', %s, true)", (subject,))
                cur.execute("""INSERT INTO garminai.oauth_attempts
                    (subject,state_hash,verifier_nonce,verifier_blob,expires_at)
                    VALUES (%s,%s,%s,%s,%s)""", (subject,digest,nonce,encrypted,expires))
        return build_authorization_url(client_id, redirect_uri, attempt), attempt.state

    def consume(self, principal, state):
        """Return verifier once, otherwise None. No token exchange performed here.

        Atomic deletion via DELETE RETURNING prevents replay under concurrent requests.
        State cannot be supplied as evidence of who the user is.
        """
        subject = self._sub(principal)
        digest = state_digest(state)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('garminai.subject', %s, true)", (subject,))
                cur.execute("""DELETE FROM garminai.oauth_attempts
                    WHERE subject=%s AND state_hash=%s AND expires_at > now()
                    RETURNING verifier_nonce,verifier_blob""", (subject,digest))
                row = cur.fetchone()
                if row is None:
                    return None
                nonce,encrypted = row
                aad = ('garminai:oauth-state:v07:' + subject + ':' + digest).encode()
                return self._aes.decrypt(bytes(nonce),bytes(encrypted),aad).decode('ascii')
