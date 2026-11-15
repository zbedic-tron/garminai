'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {webcrypto,createHash} = require('node:crypto');
const {TextEncoder} = require('node:util');
const source = fs.readFileSync(process.argv[2], 'utf8');
const BASE = 'https://ep-test.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth';
const RESOURCE = 'https://garminai-public-demo.onrender.com/mcp-oauth-staging';
const CLIENT = 'garminai-test-public-client-001';
const CALLBACK = 'https://garminai-public-demo.onrender.com/auth/oauth-test/callback';
const NOW = 1794735000000;
const TOKEN='ABCDEFGHIJKLMNOP123456';

function signedQuery(overrides={}) {
  const fields = {
    client_id:CLIENT, scope:'openid', response_type:'code',
    code_challenge_method:'S256', code_challenge:'C'.repeat(43), state:'S'.repeat(43),
    redirect_uri:CALLBACK, resource:RESOURCE, prompt:'consent', ...overrides
  };
  const p = new URLSearchParams();
  for (const [k,v] of Object.entries(fields)) {p.append('ba_param',k); p.append(k,v);}
  p.append('sig','NOT_A_REAL_SIGNATURE_PROVIDER_CHECKS_THIS');
  return '?' + p.toString();
}
// Reproduces Neon's actual redirect syntax: ba_param=ba_param is intentional.
// The signature is synthetic; these tests check local structure, not crypto.
function neonSignedQuery() {
  const fields = {
    response_type:'code', redirect_uri:CALLBACK, scope:'openid',
    state:'S'.repeat(43), client_id:CLIENT, prompt:'consent',
    code_challenge:'C'.repeat(43), code_challenge_method:'S256',
    resource:RESOURCE, exp:String(Math.floor(NOW/1000)+600), ba_iat:String(NOW)
  };
  const p = new URLSearchParams();
  for (const [k,v] of Object.entries(fields)) p.append(k,v);
  for (const name of ['ba_iat','ba_param',...Object.keys(fields).filter(k=>k!=='ba_iat')])
    p.append('ba_param',name);
  p.append('sig','synthetic/Base64+sig==');
  return '?' + p.toString();
}
const flush = async () => {for(let i=0;i<40;i++) await Promise.resolve();};
function page({mode='consent', query=signedQuery(), active=true, reply, pending=null, resume=null}={}) {
  const calls=[], navigations=[], nodes={};
  const element = id => nodes[id] ??= {id, disabled:true, hidden:true, textContent:'', href:'',
    addEventListener(_name,callback){this.click=callback;}};
  const storage = new Map([
    ...(pending ? [['garminai.oauth-ui-staging.pending.v1',pending]] : []),
    ...(resume ? [['garminai.oauth-ui-staging.resume.v0871',resume]] : [])
  ]);
  const ctx = {
    URL, URLSearchParams, encodeURIComponent, TextEncoder, crypto:webcrypto,
    Date:class extends Date {static now(){return NOW;}},
    location:{origin:'https://garminai-public-demo.onrender.com',pathname:'/auth/'+mode,search:query,
              assign(uri){navigations.push(uri);}},
    history:{replaceState(_x,_y,uri){assert.ok(uri.startsWith('/auth/'+mode));}},
    sessionStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    document:{querySelector:s=>{assert.equal(s,'main[data-mode]');
      return {dataset:{mode,auth:BASE,resource:RESOURCE,clientId:CLIENT,callback:CALLBACK}};},getElementById:element},
    fetch:async (url,opts)=>{
      assert.equal(opts.credentials,'include');
      assert.equal(opts.redirect,'error');
      calls.push({url,opts});
      const path=url.slice(BASE.length);
      let result=reply ? await reply(path,opts) : undefined;
      if (result===undefined) {
        if (path.startsWith('/get-session')) result = active ? {user:{id:'user'},session:{id:'session'}} : null;
        else if (path.startsWith('/oauth2/public-client?')) result={client_id:CLIENT,client_name:'Registered Test App',redirect_uris:[CALLBACK]};
        else if (path==='/oauth2/continue') result={redirect:true,url:'https://garminai-public-demo.onrender.com/auth/consent'+query};
        else if (path==='/oauth2/consent') result={redirect:true,url:CALLBACK+'?code=fake'};
        else if (path==='/sign-in/social') result={url:BASE+'/sign-in/social/init?token='+TOKEN,redirect:false};
        else throw Error('Unexpected call: '+path);
      }
      if (result?.status) return {ok:false,status:result.status,json:async()=>null};
      return {ok:true,status:200,json:async()=>result};
    },
    console:{error(){throw Error('Do not log sensitive values');},log(){throw Error('No logging');}}
  };
  vm.runInNewContext(source,ctx,{timeout:1000});
  return {calls,navigations,nodes,storage,element};
}
(async()=>{
  let checks=0;
  // Regression: Neon signed query includes ba_param among its signed names.
  const liveShapeLogin=page({mode:'login',query:neonSignedQuery(),active:false}); await flush();
  assert.equal(liveShapeLogin.element('signin').disabled,false);
  assert.equal(liveShapeLogin.calls.length,1);
  assert.ok(!liveShapeLogin.element('status').textContent.includes('INVALID_SIGNED_REQUEST'));checks++;

  const liveShapeConsent=page({mode:'consent',query:neonSignedQuery()}); await flush();
  assert.equal(liveShapeConsent.element('allow').disabled,false);
  await liveShapeConsent.element('allow').click(); await flush();
  const consentPost=liveShapeConsent.calls.find(c=>c.url.endsWith('/oauth2/consent'));
  assert.ok(consentPost);
  const sent=new URLSearchParams(JSON.parse(consentPost.opts.body).oauth_query);
  assert.ok(sent.getAll('ba_param').includes('ba_param'));
  assert.equal(sent.get('sig'),'synthetic/Base64+sig==');checks++;

  // Duplicating a single-valued signed name must still be rejected.
  const duplicateSigned = page({query:neonSignedQuery()+'&client_id=another-client'}); await flush();
  assert.equal(duplicateSigned.calls.length,0);
  assert.match(duplicateSigned.element('status').textContent,/INVALID_SIGNED_REQUEST/);checks++;

  // Duplicating the list entry itself remains invalid.
  const duplicateList = page({query:neonSignedQuery()+'&ba_param=client_id'}); await flush();
  assert.equal(duplicateList.calls.length,0);
  assert.match(duplicateList.element('status').textContent,/INVALID_SIGNED_REQUEST/);checks++;

  const missing=page({query:''}); await flush();
  assert.equal(missing.calls.length,0); assert.equal(missing.element('allow').disabled,true);checks++;

  for (const [override,code] of [
    [{scope:'openid garmin:read'},'UNSUPPORTED_SCOPE'],
    [{resource:'https://evil.test/mcp'},'RESOURCE_MISMATCH'],
    [{client_id:'another-client'},'UNEXPECTED_CLIENT'],
    [{redirect_uri:'https://evil.test/callback'},'UNSAFE_CLIENT_REDIRECT'],
    [{code_challenge_method:'plain'},'UNSUPPORTED_OAUTH_FLOW'],
    [{state:'short'},'UNSUPPORTED_OAUTH_FLOW'],
    [{prompt:'none'},'UNEXPECTED_PROMPT']
  ]) {
    const v=page({query:signedQuery(override)}); await flush();
    assert.equal(v.calls.length,0);assert.equal(v.element('allow').disabled,true);
    assert.match(v.element('status').textContent,new RegExp(code));checks++;
  }

  const unsigned=page({query:signedQuery().replace(/sig=[^&]*/, 'sig=')}); await flush();
  assert.equal(unsigned.calls.length,0);checks++;

  const notLoggedIn=page({active:false}); await flush();
  assert.equal(notLoggedIn.element('allow').disabled,true);
  assert.equal(notLoggedIn.element('login-link').hidden,false);checks++;

  const rejectedClient=page({reply:async p=>p.startsWith('/oauth2/public-client?')?{status:403}:undefined});
  await flush();assert.equal(rejectedClient.element('allow').disabled,true);checks++;

  const wrongRegisteredUri=page({reply:async p=>p.startsWith('/oauth2/public-client?')?
    {client_id:CLIENT,redirect_uris:['https://evil.test/cb']}:undefined});
  await flush();assert.equal(wrongRegisteredUri.element('allow').disabled,true);checks++;

  const approve=page(); await flush();
  assert.equal(approve.element('allow').disabled,false);
  assert.equal(approve.element('client-name').textContent,'Registered Test App');
  assert.equal(approve.calls.length,2);
  assert.ok(approve.calls.some(x=>x.url.includes('/oauth2/public-client?client_id=')));
  assert.ok(!approve.calls.some(x=>x.url.includes('public-client-prelogin')));
  await approve.element('allow').click();await flush();
  assert.equal(approve.navigations.length,1);
  const accept=approve.calls.find(x=>x.url.endsWith('/oauth2/consent'));
  assert.equal(JSON.parse(accept.opts.body).accept,true);
  assert.equal(JSON.parse(accept.opts.body).scope,'openid');checks++;

  const deny=page();await flush();await deny.element('deny').click();await flush();
  assert.equal(JSON.parse(deny.calls.find(x=>x.url.endsWith('/oauth2/consent')).opts.body).accept,false);checks++;

  const invalidSignature=page({reply:async p=>p==='/oauth2/consent'?{status:400}:undefined});
  await flush();await invalidSignature.element('allow').click();await flush();
  assert.equal(invalidSignature.navigations.length,0);
  assert.match(invalidSignature.element('status').textContent,/HTTP_400/);checks++;

  const redirectAttack=page({reply:async p=>p==='/oauth2/consent'?{redirect:true,url:'https://evil.test/steal'}:undefined});
  await flush();await redirectAttack.element('allow').click();await flush();
  assert.equal(redirectAttack.navigations.length,0);checks++;

  const login=page({mode:'login',active:false});await flush();
  assert.equal(login.element('signin').disabled,false);
  assert.equal(login.calls.length,1); // session only; no prelogin
  await login.element('signin').click();await flush();
  assert.equal(login.navigations.length,1);
  assert.ok(login.storage.has('garminai.oauth-ui-staging.pending.v1'));
  assert.ok(JSON.parse(login.calls.find(x=>x.url.endsWith('/sign-in/social')).opts.body).oauth_query);checks++;

  // A signed-in login page must continue the ORIGINAL signed request, rather
  // than issuing a second /oauth2/authorize and getting redirected to login.
  const already=page({mode:'login',active:true}); await flush();
  assert.equal(already.navigations.length,1);
  const next=new URL(already.navigations[0]);
  assert.equal(next.pathname,'/auth/consent');
  assert.equal(next.searchParams.get('client_id'),CLIENT);
  assert.equal(next.searchParams.get('code_challenge'),'C'.repeat(43));
  const continued=already.calls.filter(x=>x.url.endsWith('/oauth2/continue'));
  assert.equal(continued.length,1);
  assert.equal(continued[0].opts.method,'POST');
  const continuedBody=JSON.parse(continued[0].opts.body);
  assert.equal(continuedBody.selected,true);
  assert.equal(new URLSearchParams(continuedBody.oauth_query).get('sig'), 'NOT_A_REAL_SIGNATURE_PROVIDER_CHECKS_THIS');
  assert.equal(already.calls.some(x=>x.url.includes('/oauth2/authorize')),false);checks++;

  // Provider errors and redirects to untrusted origins must not proceed.
  const continueRefused=page({mode:'login',active:true,reply:async p=>p==='/oauth2/continue'?{status:403}:undefined});
  await flush();
  assert.equal(continueRefused.navigations.length,0);
  assert.match(continueRefused.element('status').textContent,/HTTP_403/);checks++;
  const continueUnsafe=page({mode:'login',active:true,reply:async p=>p==='/oauth2/continue'?{redirect:true,url:'https://evil.test/capture'}:undefined});
  await flush();
  assert.equal(continueUnsafe.navigations.length,0);
  assert.match(continueUnsafe.element('status').textContent,/UNSAFE_PROVIDER_REDIRECT/);checks++;
  const continueMissingRedirect=page({mode:'login',active:true,reply:async p=>p==='/oauth2/continue'?{redirect:false,url:CALLBACK}:undefined});
  await flush();
  assert.equal(continueMissingRedirect.navigations.length,0);
  assert.match(continueMissingRedirect.element('status').textContent,/NO_VERIFIED_REDIRECT/);checks++;

  // Google callback: only the exact pending request may use the verifier,
  // and then it must exchange the verifier and continue the same signed query.
  const returningQuery=signedQuery();
  const returningPending=JSON.stringify({at:NOW,hash:createHash('sha256').update(returningQuery.slice(1)).digest('hex')});
  const returning=page({mode:'login',query:returningQuery+'&neon_auth_session_verifier='+TOKEN,
    active:true,pending:returningPending});
  await new Promise(resolve=>setTimeout(resolve,30)); await flush();
   assert.equal(returning.navigations.length,1);
  assert.equal(returning.calls.filter(x=>x.url.includes('neon_auth_session_verifier=')).length,1);
  assert.equal(returning.calls.filter(x=>x.url.endsWith('/oauth2/continue')).length,1);
  assert.ok(!returning.storage.has('garminai.oauth-ui-staging.pending.v1'));checks++;

  // If Neon redirects to login again for the same state, stop rather than
  // automatically issuing a second continuation request.
  const loopGuard=page({mode:'login',active:true,resume:JSON.stringify({state:'S'.repeat(43),at:NOW})});
  await flush();
  assert.equal(loopGuard.navigations.length,0);
  assert.equal(loopGuard.calls.filter(x=>x.url.endsWith('/oauth2/continue')).length,0);
  assert.match(loopGuard.element('status').textContent,/OAUTH_SESSION_LOOP/);checks++;

  const unexpectedVerifier=page({mode:'login',active:false,query:signedQuery()+'&neon_auth_session_verifier='+TOKEN});await flush();
  assert.equal(unexpectedVerifier.element('signin').disabled,true);
  assert.match(unexpectedVerifier.element('status').textContent,/CALLBACK_UNEXPECTED/);checks++;

  console.log('PASS: '+checks+' OAuth UI browser simulations (staging-only, provider-enforced grants)');
})().catch(e=>{console.error(e);process.exitCode=1;});
