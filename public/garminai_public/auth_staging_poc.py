"""v0.8.4: isolated, opt-in Neon Auth browser-only Google sign-in experiment.

This page does NOT authenticate to GarminAI MCP. It does not relay or process
user tokens and does not change any production setting. Neon handles credentials.
Cross-site browser cookies may prevent the experiment from working in some browsers.
"""
import os
from html import escape
from urllib.parse import urlsplit

from starlette.responses import HTMLResponse, Response


def validate_staging_auth_url(value: str) -> bool:
    if not isinstance(value, str) or len(value) > 512 or value != value.strip():
        return False
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        parts = host.split(".")
        return (
            parsed.scheme == "https"
            and len(parts) >= 6
            and parts[0].startswith("ep-")
            and "neonauth" in parts
            and host.endswith(".aws.neon.tech")
            and parsed.path == "/neondb/auth"
            and parsed.port in (None, 443)
            and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment
            and not any(c in value for c in ("\\", "\n", "\r", "\t", "<", ">", "\"", "'"))
        )
    except (ValueError, TypeError):
        return False


def staging_login_enabled(env=None) -> bool:
    e = os.environ if env is None else env
    return e.get("GARMINAI_STAGING_LOGIN_ENABLED") == "1" and validate_staging_auth_url(
        e.get("NEON_AUTH_STAGING_URL", "")
    )


_CSS = """
:root{font:16px system-ui,sans-serif;color-scheme:dark}*{box-sizing:border-box}
body{background:#0b1220;color:#f3f7fa;min-height:100vh;display:grid;place-items:center;margin:0;padding:20px}
main{width:min(640px,100%);border-radius:18px;border:1px solid #324155;background:#142133;padding:32px}
.brand{color:#76ead4;font-weight:750;letter-spacing:.04em}p{color:#d2dfed;line-height:1.55}
.notice{background:#292a33;border-left:4px solid #f0b85a;border-radius:5px;padding:14px}
button{border:1px solid #7ee6d2;border-radius:10px;background:#157763;color:white;min-height:44px;padding:10px 18px;cursor:pointer}
button:disabled{background:#344255;color:#b8c5d3;cursor:not-allowed;border-color:#596979}
#status{min-height:2em}footer{margin-top:28px;border-top:1px solid #33475c;padding-top:14px;color:#9fb3ca;font-size:13px}
"""


async def staging_login(request):
    config = os.environ
    enabled = staging_login_enabled(config)
    raw_url = config.get("NEON_AUTH_STAGING_URL", "") if enabled else ""
    # Only safe, operator-configured URLs are used; no user input is reflected.
    auth_url = escape(raw_url, quote=True)
    origin = f"{urlsplit(raw_url).scheme}://{urlsplit(raw_url).netloc}" if enabled else "'none'"
    csp = (
        "default-src 'none'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
        "style-src 'unsafe-inline'; script-src 'self'; "
        "connect-src " + origin + "; form-action 'none'"
    )
    explanation = (
        "This is an isolated Google sign-in test against the Neon auth-staging branch. "
        "It does not authorize the MCP server or access Garmin data."
        if enabled else
        "Test sign-in is disabled. No identity or OAuth data is processed on this page."
    )
    actions = ('<button id="signin" type="button">Continue with Google (test)</button>'
               '<button id="check" type="button">Check Neon session</button>'
               '<button id="signout" type="button">Sign out</button>'
               '<p id="status" role="status" aria-live="polite">No session verified.</p>'
               '<script defer src="/auth/staging/google.js"></script>') if enabled else ''
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GarminAI — Google auth staging</title><style>{_CSS}</style></head>
<body><main data-neon-auth="{auth_url}"><div class="brand">GARMINAI PUBLIC · AUTH STAGING</div>
<h1>Google sign-in test</h1><p class="notice">{escape(explanation)}</p>
<p>Only use a test account. The result is browser-level Neon authentication, not proof of GarminAI server authorization.</p>
{actions}<footer>No Garmin data, MCP access tokens or developer credentials are enabled here. Cross-site browser cookie restrictions may prevent session persistence.</footer></main></body></html>'''
    headers = {
        "Cache-Control": "no-store, max-age=0", "Pragma": "no-cache",
        "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY", "Content-Security-Policy": csp,
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }
    return HTMLResponse(html, headers=headers)


_JS = r'''"use strict";
// Staging only. No MCP or Garmin access; diagnostics never display secrets.
(() => {
  const root = document.querySelector("main[data-neon-auth]");
  const base = root?.dataset.neonAuth;
  const status = document.getElementById("status");
  const buttons = ["signin", "check", "signout"].map(x => document.getElementById(x));
  if (!base || !status || buttons.some(x => !x)) return;
  const setStatus = s => { status.textContent = s; };
  const safeErrorCode = e => {
    // NEVER show arbitrary API messages, tokens, URLs or credentials.
    if (e instanceof TypeError) return "NETWORK_OR_CORS";
    return (e && /^HTTP_[0-9]{3}$|^INVALID_RESPONSE$|^INVALID_DESTINATION$|^UNEXPECTED_REDIRECT$/.test(e.message))
      ? e.message : "UNEXPECTED_ERROR";
  };
  async function call(path, init={}) {
    let result;
    try {
      result = await fetch(base + path, {
        method: init.method || "GET", credentials:"include", mode:"cors",
        // Better Auth's disableRedirect:true must return a JSON authorize URL.
        // Any HTTP redirect here is unexpected and must not be followed by fetch.
        redirect:"error", cache:"no-store",
        headers:{"Accept":"application/json", ...(init.headers || {})},
        ...(init.body ? {body:init.body} : {})
      });
    } catch (e) { throw new TypeError("network or browser policy"); }
    if (!result.ok) throw Error("HTTP_" + String(result.status).padStart(3, "0"));
    try { return await result.json(); }
    catch { throw Error("INVALID_RESPONSE"); }
  }
  buttons[0].addEventListener("click", async () => {
    setStatus("Starting Google sign-in…");
    buttons.forEach(b => b.disabled = true);
    try {
      const callbackURL = location.origin + location.pathname;
      const result = await call("/sign-in/social", {method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({provider:"google",callbackURL,disableRedirect:true})});
      const dest = result.url || result.data?.url;
      if (typeof dest !== "string") throw Error("INVALID_RESPONSE");
      let u;
      try { u = new URL(dest); } catch { throw Error("INVALID_DESTINATION"); }
      if (u.protocol !== "https:" || u.hostname !== "accounts.google.com") {
        throw Error("INVALID_DESTINATION");
      }
      // Only navigate to the known Google Accounts origin, never arbitrary URLs.
      location.assign(dest);
    } catch (e) {
      setStatus("Sign-in start failed [" + safeErrorCode(e) + "]. No session was accepted. " +
        "If it repeats, open F12 > Network and check only the status of sign-in/social; do not share tokens or full URLs.");
      buttons.forEach(b => b.disabled = false);
    }
  });
  buttons[1].addEventListener("click", async () => {
    setStatus("Checking Neon session…");
    try {
      const result = await call("/get-session");
      const user = result.user || result.data?.user;
      setStatus(user?.id ? "Neon reports a signed-in test session. Not authorized for MCP." : "No active Neon session found in this browser.");
    } catch (e) { setStatus("Session check failed [" + safeErrorCode(e) + "]. No identity was accepted."); }
  });
  buttons[2].addEventListener("click", async () => {
    try {
      await call("/sign-out",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
      setStatus("Signed out from the test session.");
    } catch (e) { setStatus("Sign-out could not be confirmed [" + safeErrorCode(e) + "]."); }
  });
  if (location.search) history.replaceState(null,"",location.pathname);
})();
'''


async def staging_js(request):
    if not staging_login_enabled():
        return Response(status_code=404)
    return Response(_JS, media_type="text/javascript", headers={"Cache-Control":"no-store", "X-Content-Type-Options":"nosniff"})
