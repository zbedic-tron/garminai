import unittest
from garminai_public.oauth_provider_compat import assess_provider, deployment_requirements

ISSUER = 'https://accounts.example.org'

def meta():
    return {
        'issuer': ISSUER,
        'authorization_endpoint': ISSUER + '/authorize',
        'token_endpoint': ISSUER + '/token',
        'code_challenge_methods_supported': ['S256'],
        'response_types_supported': ['code'],
        'token_endpoint_auth_methods_supported': ['none'],
        'client_id_metadata_document_supported': True,
    }

class ProviderTests(unittest.TestCase):
    def test_cimd(self):
        a=assess_provider(meta(),expected_issuer=ISSUER)
        self.assertTrue(a.compatible_on_paper)
        self.assertEqual(a.registration_method,'CIMD')
    def test_dcr(self):
        m=meta();m['client_id_metadata_document_supported']=False
        m['registration_endpoint']=ISSUER+'/register'
        a=assess_provider(m,expected_issuer=ISSUER)
        self.assertTrue(a.compatible_on_paper)
        self.assertEqual(a.registration_method,'DCR')
    def test_reject_issuer_mismatch(self):
        m=meta(); m['issuer']='https://evil.example'
        self.assertIn('issuer_mismatch',assess_provider(m,expected_issuer=ISSUER).issues)
    def test_reject_pkce_missing(self):
        m=meta();m['code_challenge_methods_supported']=['plain']
        self.assertIn('pkce_s256_missing',assess_provider(m,expected_issuer=ISSUER).issues)
    def test_reject_http_endpoints(self):
        m=meta();m['token_endpoint']='http://accounts.example.org/token'
        self.assertIn('token_endpoint_not_https',assess_provider(m,expected_issuer=ISSUER).issues)
    def test_reject_bad_registration(self):
        m=meta();m['client_id_metadata_document_supported']=False
        self.assertIn('client_registration_not_supported',assess_provider(m,expected_issuer=ISSUER).issues)
    def test_reject_non_dict(self):
        self.assertFalse(assess_provider([], expected_issuer=ISSUER).compatible_on_paper)
    def test_reject_fake_issuer(self):
        self.assertIn('invalid_expected_issuer',assess_provider(meta(),expected_issuer='http://internal').issues)
    def test_reject_missing_code(self):
        m=meta();m['response_types_supported']=[]
        self.assertIn('authorization_code_flow_missing',assess_provider(m,expected_issuer=ISSUER).issues)
    def test_readiness_fail_closed(self):
        d=deployment_requirements()
        self.assertFalse(d['mcp_oauth_enabled'])
        self.assertFalse(d['end_user_login_ready'])
        self.assertFalse(d['garmin_oauth_enabled'])
