-- GarminAI 1.1.7.  Only synthetic bridge receipts; NO Garmin data, tokens,
-- real user identifiers, activity details, or AI payloads.
-- Apply ONLY to pre-existing D1 database garminai-synthetic-edge-v116.
CREATE TABLE IF NOT EXISTS lab_bridge_v117 (
    recipient_key TEXT NOT NULL CHECK (length(recipient_key) = 64 AND recipient_key NOT GLOB '*[^0-9a-f]*'),
    event_id TEXT NOT NULL CHECK (event_id GLOB 'SYNTHETIC_BRIDGE_V117_*' AND length(event_id) = 54 AND substr(event_id,23) NOT GLOB '*[^0-9a-f]*'),
    payload_digest TEXT NOT NULL CHECK (length(payload_digest) = 64),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    acked_at TEXT DEFAULT NULL,
    PRIMARY KEY (recipient_key, event_id)
);
