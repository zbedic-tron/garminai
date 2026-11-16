-- Cloudflare D1: 1.1.5 SYNTHETIC-only edge lab; not production Garmin storage.
-- Not to be run in Neon. No actual Garmin, user, activity or token columns.
CREATE TABLE IF NOT EXISTS lab_events_v115 (
    event_id TEXT PRIMARY KEY NOT NULL CHECK (event_id GLOB 'SYNTHETIC_*'),
    payload_digest TEXT NOT NULL CHECK (length(payload_digest) = 64),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
