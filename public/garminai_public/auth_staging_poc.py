"""v0.8.4.3: isolated, opt-in Neon Auth browser-only Google sign-in experiment.

This page does NOT authenticate to GarminAI MCP. It does not relay or process
user tokens and does not change any production setting. Neon handles credentials.
The one-time verifier exchange still depends on the Neon session protocol and browser cookie policy.
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
{actions}<footer>No Garmin data, MCP access tokens or developer credentials are enabled here. No real Garmin data or MCP permissions are available on this test page.</footer></main></body></html>'''
    headers = {
        "Cache-Control": "no-store, max-age=0", "Pragma": "no-cache",
        "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY", "Content-Security-Policy": csp,
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }
    return HTMLResponse(html, headers=headers)


_JS = r'''"use strict";
// v0.8.4.3: browser-only staging proof of concept. No MCP or Garmin access.
// Neon Managed Auth returns an OAuth session verifier to the callback URL.
// A single /get-session request must exchange it before regular cookie checks.
(() => {
  const root = document.querySelector("main[data-neon-auth]");
  const base = root?.dataset.neonAuth;
  const status = document.getElementById("status");
  const buttons = ["signin", "check", "signout"].map(x => document.getElementById(x));
  if (!base || !status || buttons.some(x => !x)) return;
  const setStatus = value => { status.textContent = value; };
  const PENDING_KEY = "garminai.auth-staging.google.pending.v1";
  const MAX_PENDING_MS = 10 * 60 * 1000;
  let wasExchanged = false;

  const safeErrorCode = e => {
    if (e instanceof TypeError) return "NETWORK_OR_BROWSER_POLICY";
    const code = e?.message || "";
    return /^(HTTP_[0-9]{3}|INVALID_RESPONSE|INVALID_DESTINATION|BROWSER_STORAGE_UNAVAILABLE)$/.test(code)
      ? code : "UNEXPECTED_ERROR";
  };
  const clearPending = () => { try { sessionStorage.removeItem(PENDING_KEY); } catch (_) {} };

  // Read the one-time verifier BEFORE removing the sensitive query string.
  // Never put the verifier in DOM, console, analytics, storage or an MCP request.
  const callbackParams = new URLSearchParams(location.search);
  const verifier = callbackParams.get("neon_auth_session_verifier");
  const callbackHasVerifier = callbackParams.has("neon_auth_session_verifier");
  const validVerifier = typeof verifier === "string" &&
    /^[A-Za-z0-9._~-]{16,2048}$/.test(verifier) &&
    callbackParams.getAll("neon_auth_session_verifier").length === 1;
  // Explicit no-referrer policy is also set on the HTML response.
  if (location.search) history.replaceState(history.state, "", location.pathname + location.hash);

  async function call(path, init={}) {
    let response;
    try {
      response = await fetch(base + path, {
        method: init.method || "GET", credentials: "include", mode: "cors",
        redirect: "error", cache: "no-store",
        headers: {"Accept": "application/json", ...(init.headers || {})},
        ...(init.body ? {body: init.body} : {})
      });
    } catch (_) { throw new TypeError("network or browser policy"); }
    if (!response.ok) throw Error("HTTP_" + String(response.status).padStart(3, "0"));
    try { return await response.json(); }
    catch (_) { throw Error("INVALID_RESPONSE"); }
  }

  function isValidSession(result) {
    // A 200 response with JSON null is NOT a network or CORS error.
    const user = result?.user ?? result?.data?.user;
    const session = result?.session ?? result?.data?.session;
    return typeof user?.id === "string" && user.id.length > 0 &&
      session !== null && typeof session === "object";
  }

  async function checkSession(oneTimeVerifier) {
    const path = oneTimeVerifier
      ? "/get-session?neon_auth_session_verifier=" + encodeURIComponent(oneTimeVerifier)
      : "/get-session";
    return isValidSession(await call(path));
  }

  async function handleOAuthReturn() {
    if (!callbackHasVerifier) return;
    // Fail closed if a callback is injected without a recent sign-in attempt
    // from this same tab. The staging page does not trust arbitrary URL params.
    let pending = null;
    try { pending = sessionStorage.getItem(PENDING_KEY); }
    catch (_) { setStatus("Login callback cannot be verified [BROWSER_STORAGE_UNAVAILABLE]."); return; }
    clearPending();
    const timestamp = Number(pending);
    if (!Number.isFinite(timestamp) || timestamp <= 0 ||
        Date.now() < timestamp || Date.now() - timestamp > MAX_PENDING_MS) {
      setStatus("Unexpected or expired login callback; start a new Google sign-in.");
      return;
    }
    if (!validVerifier) {
      setStatus("Login callback was not in the expected format.");
      return;
    }
    setStatus("Finalizing Neon OAuth session…");
    buttons.forEach(b => b.disabled = true);
    try {
      wasExchanged = await checkSession(verifier);
      setStatus(wasExchanged
        ? "Neon session verified after Google login (staging only; no MCP access)."
        : "OAuth callback received, but Neon did not establish a session.");
    } catch (error) {
      setStatus("Neon session exchange failed [" + safeErrorCode(error) + "].");
    } finally { buttons.forEach(b => b.disabled = false); }
  }

  buttons[0].addEventListener("click", async () => {
    setStatus("Starting Google sign-in…");
    buttons.forEach(b => b.disabled = true);
    try {
      const callbackURL = location.origin + location.pathname;
      const result = await call("/sign-in/social", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({provider: "google", callbackURL, disableRedirect: true})
      });
      const dest = result?.url ?? result?.data?.url;
      if (typeof dest !== "string") throw Error("INVALID_RESPONSE");
      let next;
      try { next = new URL(dest); }
      catch (_) { throw Error("INVALID_DESTINATION"); }
      const authBase = new URL(base);
      const neonInit = next.protocol === "https:" && next.origin === authBase.origin &&
        next.pathname === authBase.pathname + "/sign-in/social/init" &&
        !next.hash && next.searchParams.size === 1 &&
        /^[A-Za-z0-9_-]{16,256}$/.test(next.searchParams.get("token") || "");
      const googleAuthorize = next.protocol === "https:" &&
        next.origin === "https://accounts.google.com" &&
        ["/o/oauth2/v2/auth", "/o/oauth2/auth"].includes(next.pathname) && !next.hash;
      if (!neonInit && !googleAuthorize) throw Error("INVALID_DESTINATION");
      // The marker contains only a timestamp, never a token or a user ID.
      try { sessionStorage.setItem(PENDING_KEY, String(Date.now())); }
      catch (_) { throw Error("BROWSER_STORAGE_UNAVAILABLE"); }
      location.assign(next.href);
    } catch (error) {
      clearPending();
      setStatus("Sign-in start failed [" + safeErrorCode(error) + "]. No session was accepted.");
      buttons.forEach(b => b.disabled = false);
    }
  });

  buttons[1].addEventListener("click", async () => {
    setStatus("Checking Neon session…");
    try {
      const active = await checkSession();
      setStatus(active
        ? "Neon reports an active test session. Not authorized for MCP."
        : (wasExchanged
          ? "One-time verification succeeded, but no session cookie is available now."
          : "No active Neon session found in this browser."));
    } catch (error) {
      setStatus("Session check failed [" + safeErrorCode(error) + "]. No identity was accepted.");
    }
  });

  buttons[2].addEventListener("click", async () => {
    setStatus("Requesting test sign-out…");
    try {
      await call("/sign-out", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"});
      wasExchanged = false;
      clearPending();
      setStatus("Sign-out requested. Confirm it using Check Neon session.");
    } catch (error) {
      setStatus("Sign-out could not be confirmed [" + safeErrorCode(error) + "].");
    }
  });
  void handleOAuthReturn();
})();
'''

async def staging_js(request):
    if not staging_login_enabled():
        return Response(status_code=404)
    return Response(_JS, media_type="text/javascript", headers={"Cache-Control":"no-store", "X-Content-Type-Options":"nosniff"})
