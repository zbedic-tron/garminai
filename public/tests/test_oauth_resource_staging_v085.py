"""OAuth protected resource discovery is isolated and disabled by default."""
import asyncio
import unittest
from unittest.mock import patch
from starlette.requests import Request
from garminai_public.oauth_resource_staging import build_contract, assess_discovery, status, metadata, protected_stub

HOST='garminai-public-demo.onrender.com'
BASE='https://ep-young-block-b9f41ynt.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth'
ENV={'RENDER_EXTERNAL_HOSTNAME':HOST,'NEON_AUTH_STAGING_URL':BASE,'GARMINAI_MCP_OAUTH_STAGING_ISSUER':BASE}


def req():
    return Request({'type':'http','method':'GET','path':'/','headers':[]})

class StagingOAuthTests(unittest.TestCase):
    def test_off_by_default(self):
        c=build_contract(ENV)
        self.assertFalse(c.complete)
        self.assertFalse(c.enabled)

    def test_missing_explicit_issuer_refused(self):
        c=build_contract({**ENV,'GARMINAI_MCP_OAUTH_STAGING_ENABLED':'1','GARMINAI_MCP_OAUTH_STAGING_ISSUER':''})
        self.assertFalse(c.complete)
        self.assertIn('STAGING_ISSUER_NOT_VERIFIED',c.problems)

    def test_production_issuer_rejected(self):
        c=build_contract({**ENV,'GARMINAI_MCP_OAUTH_STAGING_ENABLED':'1','GARMINAI_MCP_OAUTH_STAGING_ISSUER':'https://another.neon.tech/auth'})
        self.assertFalse(c.complete)

    def test_invalid_hostname_rejected(self):
        c=build_contract({**ENV,'GARMINAI_MCP_OAUTH_STAGING_ENABLED':'1','RENDER_EXTERNAL_HOSTNAME':'evil.example/mcp'})
        self.assertFalse(c.complete)

    def test_explicit_opt_in_staging_only(self):
        c=build_contract({**ENV,'GARMINAI_MCP_OAUTH_STAGING_ENABLED':'1'})
        self.assertTrue(c.complete)
        self.assertEqual(c.resource,'https://'+HOST+'/mcp-oauth-staging')
        self.assertEqual(c.document()['authorization_servers'],[BASE])
        self.assertEqual(c.document()['scopes_supported'],['openid'])
        self.assertTrue(c.challenge().startswith('Bearer resource_metadata="https://'+HOST))

    def test_disabled_endpoint_404(self):
        with patch.dict('os.environ',ENV,clear=True):
            r=asyncio.run(metadata(req()))
            self.assertEqual(r.status_code,404)
            r=asyncio.run(protected_stub(req()))
            self.assertEqual(r.status_code,404)

    def test_opted_in_metadata_and_challenge(self):
        with patch.dict('os.environ',{**ENV,'GARMINAI_MCP_OAUTH_STAGING_ENABLED':'1'},clear=True):
            r=asyncio.run(metadata(req()))
            self.assertEqual(r.status_code,200)
            self.assertIn(b'authorization_servers',r.body)
            r=asyncio.run(protected_stub(req()))
            self.assertEqual(r.status_code,401)
            self.assertIn('resource_metadata',r.headers['WWW-Authenticate'])
            self.assertNotIn('garmin',r.body.decode().lower())

    def test_status_never_reports_real_oauth(self):
        with patch.dict('os.environ',ENV,clear=True):
            r=asyncio.run(status(req()))
            self.assertIn(b'"mcp_authenticated_tools_enabled":false',r.body)
            self.assertIn(b'"garmin_live_data_enabled":false',r.body)

    def test_provider_metadata_not_trusted_without_issuer_identification(self):
        item={'issuer':BASE,'authorization_endpoint':BASE+'/oauth2/authorize',
              'token_endpoint':BASE+'/oauth2/token',
              'code_challenge_methods_supported':['S256'],
              'response_types_supported':['code'],
              'client_id_metadata_document_supported':True,
              'token_endpoint_auth_methods_supported':['none']}
        result=assess_discovery(item,issuer=BASE)
        self.assertFalse(result['compatible_on_paper'])
        self.assertIn('issuer_parameter_not_confirmed',result['issues'])
        item['authorization_response_iss_parameter_supported']=True
        self.assertTrue(assess_discovery(item,issuer=BASE)['compatible_on_paper'])

    def test_staging_metadata_does_not_mutate_demo_route(self):
        from pathlib import Path
        code=(Path(__file__).parents[1]/'garminai_public'/'http_server.py').read_text()
        self.assertIn('DemoBearerGate(mcp_asgi)',code)
        self.assertIn('Route("/mcp-oauth-staging", oauth_staging_stub',code)

if __name__=='__main__': unittest.main()
