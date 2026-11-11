"""Starter push-event intake checks, staged only (no public ingestion in v0.5).

Garmin webhook payloads should ONLY be accepted after confirming official
notification schema, authentication scheme, ownership mapping and limits.
"""
import json
import hashlib

MAX_PUSH_BYTES = 512_000

def validate_envelope(raw_body, content_type):
    if not isinstance(raw_body,bytes) or len(raw_body)>MAX_PUSH_BYTES:
        raise ValueError('Invalid push size')
    if content_type.split(';',1)[0].strip().lower() != 'application/json':
        raise ValueError('JSON required')
    payload=json.loads(raw_body)
    if not isinstance(payload,dict):raise ValueError('Expected JSON object')
    return payload

def fingerprint(raw_body):
    return hashlib.sha256(raw_body).hexdigest()
