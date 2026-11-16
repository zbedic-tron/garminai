-- v1.1.8 Cloudflare D1 ONLY. Existing database. Strictly fictional receipts.
-- Do not use this file in Neon PostgreSQL or with Garmin data.
CREATE TABLE IF NOT EXISTS lab_recovery_v118 (
    recipient_key TEXT NOT NULL CHECK (length(recipient_key)=64 AND recipient_key NOT GLOB '*[^0-9a-f]*'),
    event_id TEXT NOT NULL CHECK (event_id GLOB 'SYNTHETIC_RECOVERY_V118_*' AND length(event_id)=56 AND substr(event_id,25) NOT GLOB '*[^0-9a-f]*'),
    payload_digest TEXT NOT NULL CHECK (length(payload_digest)=64 AND payload_digest NOT GLOB '*[^0-9a-f]*'),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count BETWEEN 0 AND 1000000),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    acked_at TEXT DEFAULT NULL,
    PRIMARY KEY (recipient_key,event_id)
);
