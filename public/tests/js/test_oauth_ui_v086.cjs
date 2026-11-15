'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
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
const flush = async () => {for(let i=0;i<40;i++) await Promise.resolve();};
function page({mode='consent', query=signedQuery(), active=true, reply, pending=null}={}) {
  const calls=[], navigations=[], nodes={};
  const element = id => nodes[id] ??= {id, disabled:true, hidden:true, textContent:'', href:'',
    addEventListener(_name,callback){this.click=callback;}};
  const storage = new Map(pending ? [['garminai.oauth-ui-staging.pending.v1',pending]] : []);
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

  const already=page({mode:'login',active:true}); await flush();
  assert.equal(already.navigations.length,1);
  const next=new URL(already.navigations[0]);
  assert.equal(next.origin,new URL(BASE).origin);
  assert.equal(next.pathname,new URL(BASE).pathname+'/oauth2/authorize');
  assert.equal(next.searchParams.get('client_id'),CLIENT);
  assert.equal(next.searchParams.get('code_challenge'),'C'.repeat(43));
  assert.ok(!already.calls.some(x=>x.url.includes('/oauth2/continue')));checks++;

  const unexpectedVerifier=page({mode:'login',active:false,query:signedQuery()+'&neon_auth_session_verifier='+TOKEN});await flush();
  assert.equal(unexpectedVerifier.element('signin').disabled,true);
  assert.match(unexpectedVerifier.element('status').textContent,/CALLBACK_UNEXPECTED/);checks++;

  console.log('PASS: '+checks+' OAuth UI browser simulations (staging-only, provider-enforced grants)');
})().catch(e=>{console.error(e);process.exitCode=1;});
