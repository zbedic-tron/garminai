"""Configuration-only readiness checks. Do not include secrets in output."""
import os
from .postgres_store import validate_database_url


def db_configuration_status(env=None):
    e=os.environ if env is None else env
    try:
        validate_database_url(e.get('DATABASE_URL',''))
        db_url_valid=True
    except ValueError:
        db_url_valid=False
    return {
        'postgres_url_configured_and_tls_required':db_url_valid,
        'token_encryption_key_configured':bool(e.get('GARMINAI_TOKEN_ENCRYPTION_KEY')),
        'schema_initialized':'NOT_CHECKED',
        'runtime_identity_provider_enabled':False,
        'real_garmin_data_enabled':False,
    }
