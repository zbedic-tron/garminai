-- GarminAI Public v0.6. Apply once from Neon SQL Editor using database owner.
-- This defines schema only. NO data is imported or synced.
CREATE SCHEMA IF NOT EXISTS garminai;
REVOKE ALL ON SCHEMA garminai FROM PUBLIC;

CREATE TABLE IF NOT EXISTS garminai.athletes (
    subject text PRIMARY KEY CHECK(length(subject) BETWEEN 1 AND 128),
    garmin_user_id text UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS garminai.activities (
    subject text NOT NULL REFERENCES garminai.athletes(subject) ON DELETE CASCADE,
    activity_id text NOT NULL CHECK(length(activity_id) BETWEEN 1 AND 128),
    activity_date timestamptz,
    summary jsonb NOT NULL CHECK (jsonb_typeof(summary) = 'object' AND octet_length(summary::text) <= 65536),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(subject, activity_id)
);
CREATE INDEX IF NOT EXISTS activities_subject_date ON garminai.activities(subject, activity_date DESC);
CREATE TABLE IF NOT EXISTS garminai.garmin_credentials (
    subject text PRIMARY KEY REFERENCES garminai.athletes(subject) ON DELETE CASCADE,
    encrypted_blob bytea NOT NULL,
    nonce bytea NOT NULL CHECK(octet_length(nonce)=12),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS garminai.ai_consent (
    subject text PRIMARY KEY REFERENCES garminai.athletes(subject) ON DELETE CASCADE,
    consented boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Defense in depth. The app MUST set transaction-local garminai.subject
-- from a verified identity; never from an HTTP header or MCP argument.
-- Missing context matches no rows. FORCE makes owner subject to RLS too.
ALTER TABLE garminai.athletes ENABLE ROW LEVEL SECURITY;
ALTER TABLE garminai.athletes FORCE ROW LEVEL SECURITY;
ALTER TABLE garminai.activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE garminai.activities FORCE ROW LEVEL SECURITY;
ALTER TABLE garminai.garmin_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE garminai.garmin_credentials FORCE ROW LEVEL SECURITY;
ALTER TABLE garminai.ai_consent ENABLE ROW LEVEL SECURITY;
ALTER TABLE garminai.ai_consent FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS athletes_owner ON garminai.athletes;
CREATE POLICY athletes_owner ON garminai.athletes FOR ALL
USING (subject = nullif(current_setting('garminai.subject', true), ''))
WITH CHECK (subject = nullif(current_setting('garminai.subject', true), ''));
DROP POLICY IF EXISTS activities_owner ON garminai.activities;
CREATE POLICY activities_owner ON garminai.activities FOR ALL
USING (subject = nullif(current_setting('garminai.subject', true), ''))
WITH CHECK (subject = nullif(current_setting('garminai.subject', true), ''));
DROP POLICY IF EXISTS credentials_owner ON garminai.garmin_credentials;
CREATE POLICY credentials_owner ON garminai.garmin_credentials FOR ALL
USING (subject = nullif(current_setting('garminai.subject', true), ''))
WITH CHECK (subject = nullif(current_setting('garminai.subject', true), ''));
DROP POLICY IF EXISTS consent_owner ON garminai.ai_consent;
CREATE POLICY consent_owner ON garminai.ai_consent FOR ALL
USING (subject = nullif(current_setting('garminai.subject', true), ''))
WITH CHECK (subject = nullif(current_setting('garminai.subject', true), ''));

-- Least privilege runtime role: create in Neon SQL Editor manually first,
-- with a randomly generated password. Never use the owner URL at runtime.
-- Then execute after substitution of ACTUAL role name (no secrets below):
-- GRANT USAGE ON SCHEMA garminai TO garminai_runtime;
-- GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA garminai TO garminai_runtime;
-- The runtime role must NOT have BYPASSRLS or own these tables.
