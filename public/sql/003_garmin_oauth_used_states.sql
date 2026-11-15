-- GarminAI Public v1.0.1. Execute only in existing Neon staging database.
-- Run as schema owner after review. Requires garminai_app runtime role from v0.6.
-- State values ARE NEVER persisted: only 256-bit SHA-256 digests of opaque
-- AES-GCM-encrypted states. No Garmin token is stored here.
CREATE TABLE IF NOT EXISTS garminai.garmin_oauth_used_states (
    state_hash text PRIMARY KEY CHECK (state_hash ~ '^[a-f0-9]{64}$'),
    subject text NOT NULL CHECK (subject ~ '^[a-f0-9]{64}$'),
    expires_at timestamptz NOT NULL
);
ALTER TABLE garminai.garmin_oauth_used_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE garminai.garmin_oauth_used_states FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS garmin_oauth_used_owner ON garminai.garmin_oauth_used_states;
CREATE POLICY garmin_oauth_used_owner ON garminai.garmin_oauth_used_states FOR ALL
USING (subject = nullif(current_setting('garminai.subject',true),''))
WITH CHECK (subject = nullif(current_setting('garminai.subject',true),''));
GRANT SELECT, INSERT ON garminai.garmin_oauth_used_states TO garminai_app;
-- CLEANUP via privileged maintenance at planned intervals after >15 min.
-- Do not grant schema modification, UPDATE or DELETE to the application role.
