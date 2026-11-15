"""v0.8.9 isolated FICTIONAL demo view, tied to verified OAuth subject.

No production data, database writes or subject identifiers are retained. IDs are
opaque and process-local (they change after restart/scale-out). Production
identity requires persistent tenant binding and database RLS instead.
"""
from dataclasses import dataclass
import hashlib
import hmac
import secrets

from . import core

# Ephemeral per-process key: no env secret or user identifier is persisted.
_KEY = secrets.token_bytes(32)


@dataclass(frozen=True)
class DemoPrincipal:
    # Created ONLY inside StagingOAuthGate after signature/claims verification.
    key: str


def principal_from_claims(claims):
    """Never derive identity from headers, caller arguments, or unsigned JWT."""
    issuer = claims['iss']
    subject = claims['sub']
    if not (isinstance(issuer, str) and 0 < len(issuer) <= 512 and
            isinstance(subject, str) and 0 < len(subject) <= 256):
        raise ValueError('INVALID_VERIFIED_PRINCIPAL')
    digest = hmac.new(_KEY, (issuer + '\x00' + subject).encode('utf-8'), hashlib.sha256).hexdigest()
    return DemoPrincipal(digest)


def principal_from_context(ctx):
    """MCP v1 carries the trusted ASGI Request as request_context.request."""
    try:
        request = ctx.request_context.request
        principal = request.scope.get('garminai.oauth_staging_principal')
    except (AttributeError, TypeError, ValueError):
        principal = None
    if not isinstance(principal, DemoPrincipal) or len(principal.key) != 64:
        # Fail closed if MCP transport changes or context is missing.
        raise RuntimeError('STAGING_IDENTITY_UNAVAILABLE')
    return principal


def _external_id(principal, internal_id):
    return 'demo-' + principal.key[:16] + '-' + internal_id


def activities_for(principal, limit=5):
    """Only synthetic records; IDs are scoped to the verified token subject."""
    if not isinstance(principal, DemoPrincipal):
        raise RuntimeError('STAGING_IDENTITY_UNAVAILABLE')
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError('INVALID_DEMO_LIMIT')
    result = core.activities(limit=limit)
    records = [dict(a, id=_external_id(principal, a['id'])) for a in result['activities']]
    return {'mode': 'DEMO_ONLY', 'isolation': 'TOKEN_SUBJECT_SCOPED',
            'count': len(records), 'activities': records}


def detail_for(principal, activity_id):
    """Missing and foreign IDs have the *same* response (no existence leak)."""
    if not isinstance(principal, DemoPrincipal):
        raise RuntimeError('STAGING_IDENTITY_UNAVAILABLE')
    if not isinstance(activity_id, str) or len(activity_id) > 120:
        return {'mode':'DEMO_ONLY','error':'unknown_demo_activity'}
    for record in core.activities(limit=100)['activities']:
        if hmac.compare_digest(_external_id(principal, record['id']), activity_id):
            return {'mode':'DEMO_ONLY', 'activity':dict(record, id=activity_id)}
    return {'mode':'DEMO_ONLY','error':'unknown_demo_activity'}
