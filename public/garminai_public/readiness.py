"""Safe operator readiness report. Never reveal credentials or hashes."""
import os
from urllib.parse import urlparse

def get_readiness(env=None):
    e=os.environ if env is None else env
    redirect=e.get('GARMIN_REDIRECT_URI','')
    parsed=urlparse(redirect)
    return {
        'version':'0.7.0',
        'mode':'DEMO_ONLY',
        'garmin_connect_enabled':False,
        'garmin_client_id_configured':bool(e.get('GARMIN_CLIENT_ID')),
        'garmin_client_secret_configured':bool(e.get('GARMIN_CLIENT_SECRET')),
        'redirect_uri_configured':bool(parsed.scheme=='https' and parsed.netloc and parsed.path=='/garmin/oauth/callback'),
        'durable_database_configured':bool(e.get('DATABASE_URL')),
        'user_identity_provider_configured':False,
        'push_delivery_configured':False,
        'ai_processing_enabled':False,
    }
