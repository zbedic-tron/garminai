-- GarminAI Public v1.1.0: OFFLINE-ONLY durable push rehearsal.
-- Review on existing Neon Primary/neondb; apply as schema owner.
-- Does NOT enable any Garmin callback, ingestion, MCP real-data tool or AI sharing.
-- Requires 001 base schema and least-privilege garminai_app role.
CREATE TABLE IF NOT EXISTS garminai.garmin_push_receipts (
    subject text NOT NULL,
    activity_id text NOT NULL CHECK (length(activity_id) BETWEEN 1 AND 128),
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    received_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(subject, activity_id),
    FOREIGN KEY (subject, activity_id)
        REFERENCES garminai.activities(subject, activity_id) ON DELETE CASCADE
);
ALTER TABLE garminai.garmin_push_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE garminai.garmin_push_receipts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS garmin_push_receipts_owner ON garminai.garmin_push_receipts;
CREATE POLICY garmin_push_receipts_owner ON garminai.garmin_push_receipts
    FOR ALL
    USING (subject = nullif(current_setting('garminai.subject', true), ''))
    WITH CHECK (subject = nullif(current_setting('garminai.subject', true), ''));
GRANT SELECT, INSERT ON garminai.garmin_push_receipts TO garminai_app;
-- No UPDATE/DELETE grant: deletion occurs via FK cascade from user-owned
-- activity/athlete records, preserving disconnect semantics.
