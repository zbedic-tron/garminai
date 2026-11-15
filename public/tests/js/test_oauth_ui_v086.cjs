'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const {TextEncoder} = require('node:util');
const source = fs.readFileSync(process.argv[2], 'utf8');
const BASE = 'https://ep-test.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth';
const RESOURCE = 'https://garminai-public-demo.onrender.com/mcp-oauth-staging';
const CLIENT = 'https://chatgpt.com/oauth/client.json';
const NOW = 1794735000000;

function signedQuery(overrides={}) {
  const signed = {
    client_id: CLIENT, scope: 'openid', response_type: 'code',
    code_challenge_method: 'S256', redirect_uri: 'https://chatgpt.com/connector_platform_oauth_redirect',
    resource: RESOURCE, ...overrides,
  };
  const p = new URLSearchParams();
  for (const [k,v] of Object.entries(signed)) {p.append('ba_param',k); p.append(k,v);}
  p.append('sig','signature-by-neon-not-verified-locally');
  return '?' + p.toString();
}
const flush = async () => {for(let i=0;i<35;i++) await Promise.resolve();};
function makePage({mode='consent', query=signedQuery(), active=true, verified=true, reply, pending=null}={}) {
  const calls=[], navigations=[], nodes={};
  const element = id => nodes[id] ??= {
    id, disabled: true, hidden:true, textContent:'', href:'',
    addEventListener(_name, callback){this.click = callback;}
  };
  const storage = new Map(pending ? [['garminai.oauth-ui-staging.pending.v1', pending]] : []);
  const ctx = {
    URL, URLSearchParams, encodeURIComponent, TextEncoder, crypto:webcrypto,
    Date: class extends Date {static now(){return NOW;}},
    location: {origin:'https://garminai-public-demo.onrender.com', pathname:'/auth/'+mode, search:query, assign(uri){navigations.push(uri);}},
    history: {replaceState(_x,_y,uri){ assert.ok(uri.startsWith('/auth/'+mode)); }},
    sessionStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    document:{querySelector: s => {assert.equal(s,'main[data-mode]'); return {dataset:{mode,auth:BASE,resource:RESOURCE}};},getElementById:element},
    fetch:async(url,opts)=> {
      assert.equal(opts.credentials, 'include');
      assert.equal(opts.redirect, 'error');
      calls.push({url,opts});
      const path = url.slice(BASE.length);
      let result;
      if (reply) result = await reply(path,opts);
      if (result === undefined) {
        if (path === '/oauth2/public-client-prelogin')
          result = verified ? {client_id:CLIENT, client_name:'Verified App'} : {status:403};
        else if (path.startsWith('/get-session'))
          result = active ? {user:{id:'test-user'},session:{id:'test-session'}} : null;
        else if (path === '/oauth2/continue' || path === '/oauth2/consent')
          result = {redirect:true,url:'https://chatgpt.com/connector_platform_oauth_redirect?code=fake'};
        else if (path === '/sign-in/social')
          result = {url:BASE+'/sign-in/social/init?token=ABCDEFGHIJKLMNOP123456',redirect:false};
        else throw Error('Unexpected call: '+path);
      }
      if (result?.status) return {ok:false,status:result.status,json:async()=>null};
      return {ok:true,status:200,json:async()=>result};
    },
    console:{error(){throw Error('Do not log sensitive values');}, log(){throw Error('No logging');}}
  };
  vm.runInNewContext(source,ctx,{timeout:1000});
  return {calls,navigations,nodes,storage,element};
}
(async()=>{
  const untrusted=makePage({verified:false});
  await flush();
  assert.equal(untrusted.calls.length,1);
  assert.equal(untrusted.element('allow').disabled,true);
  assert.match(untrusted.element('status').textContent,/OAuth staging stopped \[HTTP_403\]/);

  const missing=makePage({query:''});
  await flush();
  assert.equal(missing.calls.length,0);
  assert.equal(missing.element('deny').disabled,true);

  const tooBroad=makePage({query:signedQuery({scope:'openid garmin:read'})});
  await flush();
  assert.equal(tooBroad.calls.length,0);
  assert.match(tooBroad.element('status').textContent,/UNSUPPORTED_SCOPE/);

  const wrongResource=makePage({query:signedQuery({resource:'https://evil.test/mcp'})});
  await flush();
  assert.equal(wrongResource.calls.length,0);
  assert.match(wrongResource.element('status').textContent,/RESOURCE_MISMATCH/);

  const notLoggedIn=makePage({active:false});
  await flush();
  assert.equal(notLoggedIn.element('allow').disabled,true);
  assert.equal(notLoggedIn.element('login-link').hidden,false);
  assert.match(notLoggedIn.element('login-link').href,/^\/auth\/login\?/);

  const approve=makePage({active:true});
  await flush();
  assert.equal(approve.element('allow').disabled,false);
  assert.equal(approve.element('deny').disabled,false);
  assert.equal(approve.element('client-name').textContent,'Verified App');
  assert.equal(approve.element('scope').textContent,'openid — verify your sign-in identity');
  assert.equal(approve.calls.length,2);
  await approve.element('allow').click();
  await flush();
  assert.equal(approve.navigations.length,1);
  const accepted=approve.calls.find(c=>c.url.endsWith('/oauth2/consent'));
  const acceptedBody=JSON.parse(accepted.opts.body);
  assert.equal(acceptedBody.accept,true);
  assert.equal(acceptedBody.scope,'openid');
  assert.ok(acceptedBody.oauth_query.includes('ba_param'));
  assert.equal(accepted.opts.credentials,'include');

  const reject=makePage({active:true});
  await flush();
  await reject.element('deny').click();
  await flush();
  const rejected=reject.calls.find(c=>c.url.endsWith('/oauth2/consent'));
  assert.equal(JSON.parse(rejected.opts.body).accept,false);
  assert.equal(reject.navigations.length,1);

  const login=makePage({mode:'login',active:false});
  await flush();
  assert.equal(login.element('signin').disabled,false);
  await login.element('signin').click();
  await flush();
  assert.equal(login.navigations.length,1);
  assert.ok(login.storage.has('garminai.oauth-ui-staging.pending.v1'));
  const signIn=login.calls.find(c=>c.url.endsWith('/sign-in/social'));
  assert.ok(JSON.parse(signIn.opts.body).oauth_query);

  const existing=makePage({mode:'login', active:true});
  await flush();
  assert.equal(existing.navigations.length,1);
  assert.ok(existing.calls.find(c=>c.url.endsWith('/oauth2/continue')));

  console.log('PASS: 9 OAuth UI browser simulations: untrusted/missing/broad/wrong-resource, unsigned-out, allow, deny, login, continue');
})().catch(e=>{console.error(e);process.exitCode=1;});
