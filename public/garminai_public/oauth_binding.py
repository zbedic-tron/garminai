"""Garmin OAuth identity-binding *staging contract*, not a public endpoint.

This module accepts only principals already verified by an external trusted
identity provider. It deliberately cannot verify ChatGPT user identities itself.
Neither bearer demo access nor a Garmin OAuth state is evidence of identity.
"""
from dataclasses import dataclass
from .identity import VerifiedPrincipal


@dataclass(frozen=True)
class CallbackResolution:
    """Private hand-off to a future server-side Garmin code-exchange service."""
    subject: str
    pkce_verifier: str


class IdentityBoundGarminFlow:
    """Use only behind an authenticated application session.

    Start and callback must both receive the same server-verified user. Callback
    state alone must *never* select an account or become an authentication token.
    """
    def __init__(self, pending_store):
        self._store = pending_store

    @staticmethod
    def _subject(principal):
        if not isinstance(principal, VerifiedPrincipal):
            raise PermissionError('Verified user session required')
        return principal.subject

    def start(self, principal, *, client_id, redirect_uri):
        self._subject(principal)
        if not client_id or not isinstance(redirect_uri, str) or not redirect_uri.startswith('https://'):
            raise ValueError('Registered HTTPS redirect and client ID required')
        return self._store.begin(principal, client_id=client_id, redirect_uri=redirect_uri)

    def resolve_callback(self, principal, *, state, code=None, error=None):
        subject = self._subject(principal)
        if not isinstance(state, str) or not state:
            raise ValueError('Missing OAuth state')
        # A denial consumes any matching state too, preventing a retry of a
        # cancelled flow from bypassing one-time handling.
        verifier = self._store.consume(principal, state)
        if verifier is None:
            raise PermissionError('Unknown, expired, wrong-user, or replayed OAuth state')
        if error:
            raise PermissionError('Garmin authorization was declined or failed')
        if not isinstance(code, str) or not code.strip():
            raise ValueError('Missing Garmin authorization code')
        # Intentionally does not persist, log, or return Garmin tokens or codes.
        return CallbackResolution(subject=subject, pkce_verifier=verifier)
