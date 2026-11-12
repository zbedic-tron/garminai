-- OPTIONAL v0.7 STAGING MIGRATION. Run as database owner only after deploy.
-- No OAuth endpoints are enabled by applying this migration.
-- No existing activities or user credentials are modified.
CREATE TABLE IF NOT EXISTS garminai.oauth_attempts (
    subject text NOT NULL REFERENCES garminai.athletes(subject) ON DELETE CASCADE,
    state_hash text NOT NULL CHECK (state_hash ~ '^[0-9a-f]{64}$'),
    verifier_nonce bytea NOT NULL CHECK (octet_length(verifier_nonce) = 12),
    verifier_blob bytea NOT NULL CHECK (octet_length(verifier_blob) BETWEEN 16 AND 512),
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (subject, state_hash)
);
CREATE INDEX IF NOT EXISTS oauth_attempts_expiry ON garminai.oauth_attempts(expires_at);
ALTER TABLE garminai.oauth_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE garminai.oauth_attempts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS oauth_attempts_owner ON garminai.oauth_attempts;
CREATE POLICY oauth_attempts_owner ON garminai.oauth_attempts FOR ALL
USING (subject = nullif(current_setting('garminai.subject', true), ''))
WITH CHECK (subject = nullif(current_setting('garminai.subject', true), ''));
GRANT SELECT, INSERT, DELETE ON garminai.oauth_attempts TO garminai_app;
-- Do NOT grant to neon_superuser app role or publish API secrets.
-- Later: schedule safe pruning of expired entries by a trusted maintenance role.
