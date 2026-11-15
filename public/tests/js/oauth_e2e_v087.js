"use strict";
// GarminAI v0.8.9 public-client OAuth diagnostic, no token or code display/storage.
(() => {
  const root = document.querySelector('main[data-oauth-test]');
  if (!root) return;
  const mode = root.dataset.mode;
  const issuer = root.dataset.issuer;
  const clientId = root.dataset.clientId;
  const resource = root.dataset.resource;
  const callback = root.dataset.callback;
  const note = s => {document.getElementById('status').textContent=s;};
  const storageKey = 'garminai.oauth-test.v087';
  const maxAge = 10 * 60 * 1000;
  const b64url = bytes => btoa(String.fromCharCode(...bytes)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  const fresh = () => b64url(crypto.getRandomValues(new Uint8Array(32)));
  const valid = (s) => typeof s === 'string' && /^[A-Za-z0-9_-]{43}$/.test(s);
  const params = new URLSearchParams(location.search);
  // Clear any incoming code/state/issuer BEFORE making any request or updating DOM.
  if (location.search) history.replaceState(null, '', location.pathname);
  const clear = () => {try {sessionStorage.removeItem(storageKey);}catch (_) {}};
  function pending() {
    try {return JSON.parse(sessionStorage.getItem(storageKey) || 'null');}
    catch (_) {return null;}
  }
  function correctMarker(m) {
    return !!(m && valid(m.verifier) && valid(m.state) && Number.isFinite(m.at) &&
      Date.now() >= m.at && Date.now()-m.at <= maxAge &&
      m.issuer === issuer && m.clientId === clientId &&
      m.resource === resource && m.callback === callback);
  }
  const start = document.getElementById('start');
  if (mode === 'start' && start) {
    start.addEventListener('click', async () => {
      start.disabled=true;
      clear(); note('Creating a new PKCE/S256 request…');
      try {
        const verifier = fresh(); const state = fresh();
        const hash = await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier));
        const challenge = b64url(new Uint8Array(hash));
        sessionStorage.setItem(storageKey,JSON.stringify({verifier,state,at:Date.now(),
                                  issuer,clientId,resource,callback}));
        const url = new URL(issuer + '/oauth2/authorize');
        const query = {
          response_type:'code', client_id:clientId,redirect_uri:callback,
          scope:'openid', resource, state,code_challenge:challenge,
          code_challenge_method:'S256',prompt:'consent'
        };
        for (const [k,v] of Object.entries(query)) url.searchParams.set(k,v);
        location.assign(url.href);
      } catch (_) {clear();note('Browser could not start PKCE. No OAuth request was sent.');start.disabled=false;}
    });
    return;
  }
  if (mode !== 'callback') return;
  const marker = pending(); clear();
  if (!correctMarker(marker)) {note('Callback rejected: no matching fresh OAuth request in this browser tab.');return;}
  const receivedState = params.getAll('state');
  const receivedIssuer = params.getAll('iss');
  const errors = params.getAll('error');
  if (receivedState.length !== 1 || receivedState[0] !== marker.state ||
      receivedIssuer.length !== 1 || receivedIssuer[0] !== issuer) {
    note('Callback rejected: state or issuer mismatch. No code exchanged.');return;
  }
  if (errors.length === 1 && errors[0] === 'access_denied' && params.getAll('code').length === 0) {
    note('Consent denied by user. No token was requested.');return;
  }
  const codes=params.getAll('code');
  if (errors.length || codes.length !== 1 || !/^[A-Za-z0-9._~+-]{12,2048}$/.test(codes[0])) {
    note('OAuth returned an error or invalid code. No token requested.');return;
  }
  note('Code and issuer validated locally. Exchanging with Neon on the server…');
  void (async () => {
    try {
      const response=await fetch('/auth/oauth-test/exchange',{
        method:'POST',credentials:'same-origin',cache:'no-store',redirect:'error',
        headers:{'Content-Type':'application/json','Accept':'application/json'},
        body:JSON.stringify({code:codes[0],code_verifier:marker.verifier})
      });
      const result=await response.json();
      if (response.ok && result?.result === 'OAUTH_STAGING_VERIFIED' &&
          result?.mcp_authorized === false && result?.garmin_access === false) {
        if (result?.mcp_demo_probe === 'PASS')
          note('PASS: Neon OAuth + PKCE + verified JWT + MCP tools/list and tools/call (status, activities, owned details) + foreign-ID denial. Fictional data only; real MCP/Garmin access disabled.');
        else if (result?.mcp_demo_probe === 'FAILED')
          note('PARTIAL PASS: Neon OAuth verified; authenticated MCP demo probe failed. No live Garmin data or production MCP access.');
        else
          note('PASS: authorization code exchanged; Neon access token signature, issuer, audience, scope and client verified. Demo MCP tool probe not enabled; live Garmin access disabled.');
      }
      else note('Staging stopped [' + (/^[A-Z0-9_]{3,48}$/.test(result?.error||'') ? result.error : 'EXCHANGE_FAILED') + ']. No MCP/Garmin access.');
    } catch (_) {note('Staging stopped [NETWORK_OR_BROWSER_POLICY]. No MCP/Garmin access.');}
  })();
})();
