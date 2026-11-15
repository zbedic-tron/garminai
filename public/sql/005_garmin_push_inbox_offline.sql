-- GarminAI Public v1.1.1: durable inbox, OFFLINE-ONLY simulation.
-- Apply as Neon schema owner, NEVER via application garminai_app role.
-- No live Garmin push processing, no MCP real-data exposure, no AI analysis.
CREATE TABLE IF NOT EXISTS garminai.garmin_push_inbox (
    subject text NOT NULL REFERENCES garminai.athletes(subject) ON DELETE CASCADE,
    activity_id text NOT NULL CHECK (length(activity_id) BETWEEN 1 AND 128),
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    summary jsonb NOT NULL CHECK (jsonb_typeof(summary) = 'object' AND octet_length(summary::text) <= 65536),
    received_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (subject, activity_id)
);
ALTER TABLE garminai.garmin_push_inbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE garminai.garmin_push_inbox FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS garmin_push_inbox_owner ON garminai.garmin_push_inbox;
CREATE POLICY garmin_push_inbox_owner ON garminai.garmin_push_inbox
    FOR ALL
    USING (subject = nullif(current_setting('garminai.subject', true), ''))
    WITH CHECK (subject = nullif(current_setting('garminai.subject', true), ''));
GRANT SELECT, INSERT ON garminai.garmin_push_inbox TO garminai_app;
-- No UPDATE or DELETE privileges. Per-user deletion via athletes FK cascade.
