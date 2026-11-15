'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const source=fs.readFileSync(process.argv[2],'utf8');
const issuer='https://ep-test.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth';
const clientId='garminai-test-public-client-001';
const resource='https://garminai-public-demo.onrender.com/mcp-oauth-staging';
const callback='https://garminai-public-demo.onrender.com/auth/oauth-test/callback';
const at=Date.now();
const state='S'.repeat(43),verifier='V'.repeat(43);
const key='garminai.oauth-test.v087';
const flush=async()=>{for(let i=0;i<45;i++)await Promise.resolve();};
function page({mode='start',search='',record=null,answer={result:'OAUTH_STAGING_VERIFIED',mcp_authorized:false,garmin_access:false}}={}) {
  const store=new Map(record?[[key,JSON.stringify(record)]]:[]), visits=[],notes=[],calls=[];
  const elements={start:{disabled:false,addEventListener(_event,cb){this.click=cb;}},status:{set textContent(v){notes.push(v);}}};
  const ctx={ URL, URLSearchParams, TextEncoder, Date, crypto:webcrypto,
    btoa:raw=>Buffer.from(raw,'binary').toString('base64'),
    document:{querySelector:s=>s==='main[data-oauth-test]'?{dataset:{mode,issuer,clientId,resource,callback}}:null,
      getElementById:id=>elements[id]},
    location:{pathname:mode==='start'?'/auth/oauth-test':'/auth/oauth-test/callback',search,assign:u=>visits.push(u)},
    history:{replaceState(_a,_b,u){assert.ok(u.startsWith('/auth/oauth-test'));}},
    sessionStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},
    fetch:async (url,params)=>{calls.push({url,params});return {ok:true,json:async()=>answer};}
  };
  vm.runInNewContext(source,ctx,{timeout:1000});
  return {store,visits,notes,calls,elements};
}
(async()=>{
  const initial=page();
  await initial.elements.start.click();await flush();
  assert.equal(initial.visits.length,1);
  const destination=new URL(initial.visits[0]);
  assert.equal(destination.pathname,'/neondb/auth/oauth2/authorize');
  assert.equal(destination.searchParams.get('response_type'),'code');
  assert.equal(destination.searchParams.get('code_challenge_method'),'S256');
  assert.equal(destination.searchParams.get('scope'),'openid');
  assert.equal(destination.searchParams.get('resource'),resource);
  assert.equal(destination.searchParams.get('redirect_uri'),callback);
  const marker=JSON.parse(initial.store.get(key));
  assert.equal(marker.verifier.length,43);
  assert.equal(destination.searchParams.get('state'),marker.state);
  assert.notEqual(destination.searchParams.get('code_challenge'),marker.verifier);
  const positive=page({mode:'callback',record:marker,search:'?iss='+encodeURIComponent(issuer)+'&state='+marker.state+'&code='+'C'.repeat(32)});
  await flush();
  assert.equal(positive.calls.length,1);
  assert.equal(positive.calls[0].url,'/auth/oauth-test/exchange');
  assert.equal(JSON.parse(positive.calls[0].params.body).code_verifier,marker.verifier);
  assert.equal(positive.store.has(key),false);
  assert.match(positive.notes.at(-1),/PASS: authorization code exchanged/);
  const denied=page({mode:'callback',record:marker,search:'?iss='+encodeURIComponent(issuer)+'&state='+marker.state+'&error=access_denied'});
  await flush();assert.equal(denied.calls.length,0);assert.match(denied.notes.at(-1),/Consent denied/);
  const wrongState=page({mode:'callback',record:marker,search:'?iss='+encodeURIComponent(issuer)+'&state=bogus&code='+'C'.repeat(32)});
  await flush();assert.equal(wrongState.calls.length,0);
  const wrongIssuer=page({mode:'callback',record:marker,search:'?iss=https://evil.test&state='+marker.state+'&code='+'C'.repeat(32)});
  await flush();assert.equal(wrongIssuer.calls.length,0);
  const missing=page({mode:'callback',search:'?iss='+encodeURIComponent(issuer)+'&state='+marker.state+'&code='+'C'.repeat(32)});
  await flush();assert.equal(missing.calls.length,0);
  const stale=page({mode:'callback',record:{...marker,at:at-1000000},search:'?iss='+encodeURIComponent(issuer)+'&state='+marker.state+'&code='+'C'.repeat(32)});
  await flush();assert.equal(stale.calls.length,0);
  const codeInError=page({mode:'callback',record:marker,search:'?iss='+encodeURIComponent(issuer)+'&state='+marker.state+'&code='+'C'.repeat(32),answer:{result:'STAGING_VERIFICATION_FAILED',error:'JWKS_INVALID'}});
  await flush();assert.equal(codeInError.calls.length,1);assert.match(codeInError.notes.at(-1),/JWKS_INVALID/);
  assert.ok(!codeInError.notes.join(' ').includes('C'.repeat(32)));
  console.log('PASS: 8 OAuth E2E browser simulations (PKCE, approved, denied, bad state, bad issuer, missing/expired marker, safe failure)');
})().catch(e=>{console.error(e);process.exitCode=1});
