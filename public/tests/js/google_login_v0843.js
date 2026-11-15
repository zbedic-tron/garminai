"use strict";
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
