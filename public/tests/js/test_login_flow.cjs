'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[2], 'utf8');
const authBase = 'https://ep-example-test123.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth';
const callbackPath = '/auth/staging/google';
const markerKey = 'garminai.auth-staging.google.pending.v1';
const time = 1770000000000;

async function flush() {
  // Asynchronous fetch & microtask queue.
  for (let n = 0; n < 12; n++) await Promise.resolve();
}
function createPage({query='', pending=null, sessionResponse=null, mockFetch}={}) {
  const all = {};
  const buttons = Object.fromEntries(['signin','check','signout'].map(id => [id, {disabled:false, async click(){ await this.handler?.(); }, addEventListener(event,fn){ assert.equal(event,'click'); this.handler=fn; }}]));
  const status = {textContent: ''};
  const storage = new Map(pending == null ? [] : [[markerKey, String(pending)]]);
  let cleared = false;
  const calls = [];
  const navigations = [];
  const context = {
    URL, URLSearchParams, encodeURIComponent,
    Date: class extends Date {static now(){return time;}},
    document: {querySelector(sel){ assert.equal(sel,'main[data-neon-auth]');return {dataset:{neonAuth:authBase}};}, getElementById(id){return id==='status'?status:buttons[id];}},
    location:{origin:'https://garminai-public-demo.onrender.com', pathname:callbackPath, search:query, hash:'', assign(href){navigations.push(href);}},
    history:{state:null,replaceState(_a,_b,path){assert.equal(path,callbackPath);cleared=true;}},
    sessionStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    fetch:async (url,opts) => {calls.push({url,opts});return mockFetch?mockFetch(url,opts):{ok:true,status:200,json:async()=>sessionResponse};},
    console:{log(){throw Error('console logging forbidden');}},
  };
  vm.runInNewContext(source,context,{timeout:1000});
  return {buttons,status,storage,calls,navigations,wasQueryCleared:()=>cleared};
}
(async()=> {
  const pending = createPage({mockFetch: async(url,options)=> {
    assert.ok(url.endsWith('/sign-in/social'));
    assert.equal(options.credentials,'include');
    return {ok:true,status:200,json:async()=>({url:authBase+'/sign-in/social/init?token=ABCDEFGHIJKLMNOP123456',redirect:false})};
  }});
  await pending.buttons.signin.click();
  assert.equal(pending.navigations.length,1);
  assert.ok(pending.storage.has(markerKey));
  assert.ok(pending.navigations[0].startsWith(authBase));
  const verifier = 'ABCDEFGHIJKLMNOPQRSTUVWX12345678';
  const returned = createPage({query:'?neon_auth_session_verifier='+verifier, pending:time-500,
    mockFetch:async(url)=>{
      assert.ok(url.endsWith('/get-session?neon_auth_session_verifier='+verifier));
      return {ok:true,status:200,json:async()=>({user:{id:'a'},session:{id:'s'}})};
    }});
  await flush();
  assert.equal(returned.calls.length,1);
  assert.equal(returned.wasQueryCleared(),true);
  assert.match(returned.status.textContent,/session verified/i);
  assert.ok(!returned.storage.has(markerKey));
  assert.ok(!returned.status.textContent.includes(verifier));
  const nullResp=createPage({query:'?neon_auth_session_verifier='+verifier,pending:time-100,
    mockFetch:async()=>({ok:true,status:200,json:async()=>null})});
  await flush();
  assert.equal(nullResp.calls.length,1);
  assert.match(nullResp.status.textContent,/did not establish a session/);
  assert.ok(!nullResp.status.textContent.includes('NETWORK_OR_CORS'));
  const noMarker=createPage({query:'?neon_auth_session_verifier='+verifier});
  await flush();
  assert.equal(noMarker.calls.length,0);
  assert.match(noMarker.status.textContent,/Unexpected or expired/);
  const expired=createPage({query:'?neon_auth_session_verifier='+verifier,pending:time-700000});
  await flush();
  assert.equal(expired.calls.length,0);
  const duplicate=createPage({query:'?neon_auth_session_verifier='+verifier+'&neon_auth_session_verifier='+verifier,pending:time-500});
  await flush();
  assert.equal(duplicate.calls.length,0);
  assert.match(duplicate.status.textContent,/expected format/);
  const regular=createPage({sessionResponse:null});
  await regular.buttons.check.click();
  assert.match(regular.status.textContent,/No active Neon session/);
  console.log('PASS: 7 Node browser-flow cases: sign-in, verifier exchange, null, missing/expired marker, duplicate verifier, manual check');
})().catch(e=>{console.error(e); process.exitCode=1});
