"use strict";
// GarminAI v0.8.7.3: one known staging client only; Neon validates the signed
// query when handling authorization/consent. This browser does NOT verify sig.
(() => {
  const root = document.querySelector('main[data-mode]');
  if (!root) return;
  const mode = root.dataset.mode;
  const base = root.dataset.auth;
  const resource = root.dataset.resource;
  const expectedClient = root.dataset.clientId;
  const expectedCallback = root.dataset.callback;
  const status = document.getElementById('status');
  const signin = document.getElementById('signin');
  const allow = document.getElementById('allow');
  const deny = document.getElementById('deny');
  const pendingKey = 'garminai.oauth-ui-staging.pending.v1';
  const resumeKey = 'garminai.oauth-ui-staging.resume.v0871';
  const maxAgeMs = 10 * 60 * 1000;
  let busy = false;
  const note = message => { status.textContent = message; };
  const disableAll = () => { for (const b of [signin, allow, deny]) if (b) b.disabled = true; };

  function signedRequest(params) {
    const names = params.getAll('ba_param');
    if (params.getAll('sig').length !== 1 || !params.get('sig') ||
        names.length < 1 || names.length > 48 || new Set(names).size !== names.length ||
        names.some(n => !/^[a-zA-Z][a-zA-Z0-9_]{0,63}$/.test(n)) ||
        params.toString().length > 8192) return null;
    const keys = new Set(['sig', 'ba_param', ...names]);
    const query = new URLSearchParams([...params].filter(([key]) => keys.has(key)));
    // Neon includes 'ba_param' in the signed name list itself. Its repeated
    // values enumerate signed fields; it is not a single-valued OAuth field.
    // All other declared signed parameters must appear exactly once.
    for (const name of names) {
      if (name !== 'ba_param' && query.getAll(name).length !== 1) return null;
    }
    if (!names.includes('client_id')) return null;
    return query;
  }

  const params = new URLSearchParams(location.search);
  const verifier = params.get('neon_auth_session_verifier');
  const hasVerifier = params.has('neon_auth_session_verifier');
  const signed = signedRequest(params);
  // Remove the one-time verifier before any fetch, DOM update or navigation.
  if (signed) history.replaceState(null, '', location.pathname + '?' + signed.toString());
  else if (location.search) history.replaceState(null, '', location.pathname);

  function usableRedirect(value, {neonOnly = false, providerReply = false} = {}) {
    if (typeof value !== 'string' || value.length > 4096) return null;
    let u;
    try { u = new URL(value); } catch (_) { return null; }
    if (u.protocol !== 'https:' || u.username || u.password || u.hash) return null;
    const auth = new URL(base);
    if (neonOnly) {
      if (u.origin !== auth.origin || u.pathname !== auth.pathname + '/sign-in/social/init' ||
          u.searchParams.size !== 1 || !/^[A-Za-z0-9_-]{16,256}$/.test(u.searchParams.get('token') || '')) return null;
    }
    if (providerReply) {
      const onNeon = u.origin === auth.origin && u.pathname.startsWith(auth.pathname + '/');
      const onOurApp = u.origin === location.origin &&
        ['/auth/login','/auth/consent','/auth/oauth-test/callback'].includes(u.pathname);
      if (!onNeon && !onOurApp) return null;
    }
    return u.href;
  }

  async function api(path, {method = 'GET', body = undefined} = {}) {
    let res;
    try {
      res = await fetch(base + path, {
        method, credentials:'include', mode:'cors', redirect:'error', cache:'no-store',
        headers: {'Accept':'application/json', ...(body === undefined ? {} : {'Content-Type':'application/json'})},
        ...(body === undefined ? {} : {body:JSON.stringify(body)})
      });
    } catch (_) { throw Error('NETWORK_OR_BROWSER_POLICY'); }
    if (!res.ok) throw Error('HTTP_' + res.status);
    try { return await res.json(); } catch (_) { throw Error('INVALID_JSON'); }
  }

  const data = v => v?.data ?? v;
  const signedValue = n => signed?.get(n) || '';
  const sessionActive = v => { const x = data(v); return !!(
    typeof x?.user?.id === 'string' && x.user.id && x.session && typeof x.session === 'object'); };
  async function checkSession(withVerifier) {
    const path = withVerifier
      ? '/get-session?neon_auth_session_verifier=' + encodeURIComponent(withVerifier)
      : '/get-session';
    return sessionActive(await api(path));
  }
  async function queryHash(query) {
    const bytes = new TextEncoder().encode(query);
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2,'0')).join('');
  }
  const clearPending = () => { try {sessionStorage.removeItem(pendingKey);} catch (_) {} };
  async function callbackWasStartedHere() {
    let marker;
    try { marker = JSON.parse(sessionStorage.getItem(pendingKey) || 'null'); }
    catch (_) { return false; }
    clearPending();
    return !!(marker && Number.isFinite(marker.at) && marker.at > 0 &&
      Date.now() >= marker.at && Date.now() - marker.at <= maxAgeMs &&
      marker.hash === await queryHash(signed.toString()));
  }

  // Staging-only structural restrictions. These do NOT prove Neon's signature;
  // Neon will independently validate the client, redirect, scopes, PKCE, and
  // signed oauth_query when issuing any authorization code or accepting consent.
  function validateStagingRequest() {
    if (!signed) throw Error('INVALID_SIGNED_REQUEST');
    if (signedValue('client_id') !== expectedClient) throw Error('UNEXPECTED_CLIENT');
    if (signedValue('redirect_uri') !== expectedCallback) throw Error('UNSAFE_CLIENT_REDIRECT');
    if (signedValue('scope') !== 'openid') throw Error('UNSUPPORTED_SCOPE');
    if (signedValue('resource') !== resource) throw Error('RESOURCE_MISMATCH');
    if (signedValue('response_type') !== 'code' || signedValue('code_challenge_method') !== 'S256' ||
        !/^[A-Za-z0-9_-]{43}$/.test(signedValue('code_challenge')) ||
        !/^[A-Za-z0-9_-]{43}$/.test(signedValue('state')))
      throw Error('UNSUPPORTED_OAUTH_FLOW');
    // Prompt must remain the value initiated by our e2e test client.
    if (signedValue('prompt') !== 'consent') throw Error('UNEXPECTED_PROMPT');
  }

  async function registeredClient() {
    const result = data(await api('/oauth2/public-client?client_id=' + encodeURIComponent(expectedClient)));
    const client = result?.client ?? result;
    const id = client?.client_id ?? client?.clientId;
    if (id !== expectedClient || client?.disabled === true) throw Error('CLIENT_NOT_VERIFIED');
    // If Neon includes registered redirect URIs, they must contain our exact callback.
    const uris = client.redirect_uris ?? client.redirectUris;
    if (uris !== undefined && (!Array.isArray(uris) || !uris.includes(expectedCallback)))
      throw Error('CLIENT_NOT_VERIFIED');
    return client;
  }

  async function resumeAtNeon() {
    validateStagingRequest();
    // Do not re-start /oauth2/authorize here. On the Render top-level site,
    // the fetch-visible Neon session can be partitioned from the first-party
    // session seen after navigating directly to Neon. A fresh authorize would
    // redirect to login again. Neon documents oauth2.continue({selected:true})
    // for login pages, even after the social sign-in callback.
    // Fail closed if the same signed state is repeatedly resumed.
    try {
      const last = JSON.parse(sessionStorage.getItem(resumeKey) || 'null');
      if (last?.state === signedValue('state') && Number.isFinite(last.at) &&
          Date.now() >= last.at && Date.now() - last.at < maxAgeMs)
        throw Error('OAUTH_SESSION_LOOP');
      sessionStorage.setItem(resumeKey, JSON.stringify({state:signedValue('state'),at:Date.now()}));
    } catch (e) {
      if (e?.message === 'OAUTH_SESSION_LOOP') throw e;
      throw Error('BROWSER_STORAGE_UNAVAILABLE');
    }
    note('Session established; asking Neon to continue the signed OAuth request…');
    // Selected:true is the Neon documented login-page continuation flag, NOT
    // a grant of access. Neon checks the signature/session and determines the
    // next step (usually Consent); our page cannot issue an OAuth code.
    const result = await api('/oauth2/continue', {method:'POST', body:{
      selected:true, oauth_query:signed.toString()
    }});
    await followProviderReply(result);
  }

  async function followProviderReply(result) {
    const payload = data(result);
    if (payload?.redirect !== true) throw Error('NO_VERIFIED_REDIRECT');
    const dest = usableRedirect(payload.url, {providerReply:true});
    if (!dest) throw Error('UNSAFE_PROVIDER_REDIRECT');
    location.assign(dest);
  }
  function failure(e) {
    disableAll();
    const code = String(e?.message || 'ERROR');
    const safe = /^(HTTP_[0-9]{3}|NETWORK_OR_BROWSER_POLICY|INVALID_JSON|INVALID_SIGNED_REQUEST|UNEXPECTED_CLIENT|UNEXPECTED_PROMPT|UNSUPPORTED_SCOPE|RESOURCE_MISMATCH|UNSUPPORTED_OAUTH_FLOW|UNSAFE_CLIENT_REDIRECT|CLIENT_NOT_VERIFIED|NO_VERIFIED_REDIRECT|UNSAFE_PROVIDER_REDIRECT|CALLBACK_UNEXPECTED|CALLBACK_INVALID|BROWSER_STORAGE_UNAVAILABLE|NEON_SIGNIN_INVALID|OAUTH_SESSION_LOOP)$/.test(code) ? code : 'UNEXPECTED_ERROR';
    note('OAuth staging stopped [' + safe + ']. Start a fresh OAuth test. No access was granted.');
  }
  function showConsent(client) {
    const name = typeof client.client_name === 'string' ? client.client_name :
      (typeof client.clientName === 'string' ? client.clientName : 'Registered OAuth test client');
    const host = new URL(expectedCallback).hostname;
    document.getElementById('client-name').textContent = name.slice(0,160);
    document.getElementById('client-host').textContent = 'Return destination: ' + host + ' (check carefully)';
    document.getElementById('scope').textContent = 'openid — verify your sign-in identity';
    document.getElementById('resource').textContent = 'Requested staging resource: ' + resource;
    document.getElementById('client').hidden = false;
    document.getElementById('rights').hidden = false;
    allow.disabled = false; deny.disabled = false;
    note('Registered staging client. Neon validates the signed request when you submit consent.');
  }
  async function initialize() {
    disableAll();
    try {
      validateStagingRequest();
      if (mode === 'login') {
        if (hasVerifier) {
          if (!verifier || !/^[A-Za-z0-9_-]{12,2048}$/.test(verifier) || !(await callbackWasStartedHere()))
            throw Error('CALLBACK_UNEXPECTED');
        }
        const loggedIn = await checkSession(hasVerifier ? verifier : undefined);
        if (loggedIn) return await resumeAtNeon();
        if (hasVerifier) throw Error('CALLBACK_INVALID');
        signin.disabled = false;
        note('Google sign-in available. Neon validates the authorization request; no access is granted on this page.');
      } else if (mode === 'consent') {
        if (!(await checkSession())) {
          const link = document.getElementById('login-link');
          link.href = '/auth/login?' + signed.toString();
          link.hidden = false;
          note('Sign in first. No OAuth consent was issued.');
          return;
        }
        // Only an authenticated Neon session can look up the registered client.
        showConsent(await registeredClient());
      } else throw Error('INVALID_SIGNED_REQUEST');
    } catch (e) { failure(e); }
  }

  if (signin) signin.addEventListener('click', async () => {
    if (busy || !signed || signin.disabled) return;
    busy = true; disableAll(); note('Starting Google sign-in…');
    try {
      const callbackURL = location.origin + location.pathname + '?' + signed.toString();
      const response = data(await api('/sign-in/social', {method:'POST', body:{
        provider:'google', callbackURL, disableRedirect:true, oauth_query:signed.toString()
      }}));
      const dest = usableRedirect(response?.url, {neonOnly:true});
      if (!dest) throw Error('NEON_SIGNIN_INVALID');
      try {sessionStorage.setItem(pendingKey, JSON.stringify({at:Date.now(),hash:await queryHash(signed.toString())}));}
      catch (_) {throw Error('BROWSER_STORAGE_UNAVAILABLE');}
      location.assign(dest);
    } catch (e) {clearPending();failure(e);} finally {busy=false;}
  });

  async function decide(accept) {
    if (busy || !signed || allow.disabled) return;
    busy = true; disableAll(); note(accept ? 'Submitting approval to Neon…' : 'Submitting denial to Neon…');
    try {
      const result = await api('/oauth2/consent', {method:'POST', body:{
        accept, ...(accept ? {scope:'openid'} : {}), oauth_query:signed.toString()
      }});
      await followProviderReply(result);
    } catch (e) {failure(e);} finally {busy=false;}
  }
  if (allow) allow.addEventListener('click', () => {void decide(true);});
  if (deny) deny.addEventListener('click', () => {void decide(false);});
  void initialize();
})();
