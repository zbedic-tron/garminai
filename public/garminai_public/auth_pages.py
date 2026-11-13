"""Safe pre-launch auth pages. No session or consent claims are made.

The real Neon Managed Better Auth sign-in/consent client must replace these pages
before enabling OAuth Provider. The signed oauth_query must be sent unchanged to
Neon's supported consent flow; do not interpret its contents as proof of identity.
"""
from html import escape
from starlette.responses import HTMLResponse

_HEADERS = {
    "cache-control": "no-store, max-age=0",
    "pragma": "no-cache",
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "content-security-policy": (
        "default-src 'none'; style-src 'unsafe-inline'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
}

_CSS = """
:root { font-family:system-ui,-apple-system,'Segoe UI',sans-serif; color-scheme:dark; }
* { box-sizing:border-box; }
body {margin:0; background:#0b1220; color:#eff5fa; min-height:100vh; display:grid;place-items:center;padding:22px;}
main {width:min(100%,640px); background:#142133; border:1px solid #324155;border-radius:18px;padding:30px;}
.brand {color:#76ead4; font-weight:750; letter-spacing:0.04em;}
h1 {line-height:1.2;font-size:clamp(25px,4vw,34px);margin:12px 0;}p,li{line-height:1.65;color:#cfdae7;}
.notice{border-left:4px solid #efb755;background:#2b2830;padding:14px 16px;border-radius:5px;}
.meta{font-size:14px;color:#a4b8c9;} .button{display:inline-block;color:#a0aeba;background:#233145;border:1px solid #506078;padding:10px 14px;border-radius:9px;cursor:not-allowed;}
a{color:#76ead4;} footer{margin-top:26px;border-top:1px solid #33475c;padding-top:16px;font-size:13px;color:#afbdcf;}
"""

def _page(title: str, body: str) -> HTMLResponse:
    text = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} | GarminAI Public</title><style>{_CSS}</style></head><body><main>
<div class="brand">GARMINAI PUBLIC · IDENTITY STAGING</div><h1>{escape(title)}</h1>{body}
<footer>This is an independent, pre-launch GarminAI project. No live Garmin account connections or user training data are enabled.</footer>
</main></body></html>'''
    return HTMLResponse(text, status_code=200, headers=_HEADERS)

async def login_page(request):
    # Do not log or echo query strings; a signed oauth_query may contain sensitive request metadata.
    return _page("Sign in to GarminAI", '''
<p class="notice"><strong>Sign-in is not active yet.</strong> This development page does not authenticate users or establish a session.</p>
<p>In the finished service, you will sign in to GarminAI, then separately authorize access to your Garmin activities.</p>
<p><span class="button" aria-disabled="true">Continue with Google — coming soon</span></p>
<p class="meta">Nothing is submitted from this page. Your Garmin password is never requested by GarminAI.</p>
''')

async def consent_page(request):
    return _page("Authorize GarminAI access", '''
<p class="notice"><strong>Consent is not active yet.</strong> No client permissions are granted by this page.</p>
<p>When the integration is ready, this page will identify the requesting application and clearly show the specific permissions and resource being requested.</p>
<ul><li>ChatGPT/MCP authorization is separate from Garmin Connect authorization.</li>
<li>AI processing of Garmin-derived data requires separate, explicit consent.</li>
<li>You will be able to decline access.</li></ul>
<p><span class="button" aria-disabled="true">Approve — unavailable in staging</span></p>
<p class="meta">OAuth requests must be verified by the Neon authorization server. This page never accepts or forwards authorization tokens.</p>
''')
