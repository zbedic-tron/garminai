'use strict';
// In-browser contract simulation. Not a Neon signature or ChatGPT live test.
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const {TextEncoder}=require('node:util');
const source=fs.readFileSync(process.argv[2]||'tests/js/oauth_ui_v086.js','utf8');
const HOST='https://garminai-public-demo.onrender.com';
const BASE='https://ep-test.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth';
const CLIENT='https://chatgpt.com/oauth/client.json';
const RESOURCE=HOST+'/mcp-oauth-staging';
const CALLBACK='https://chatgpt.com/connector_platform_oauth_redirect';
const STATE='c'.repeat(40);
const CHALLENGE='z'.repeat(43);
function signedQuery(changes={}) {
  const params={response_type:'code',client_id:CLIENT,redirect_uri:CALLBACK,
    scope:'openid email offline_access',resource:RESOURCE,state:STATE,
    code_challenge:CHALLENGE,code_challenge_method:'S256', ...changes};
  const query=new URLSearchParams();
  for (const [name,v] of Object.entries(params)) {
    if (v!==null) {query.append(name,v);query.append('ba_param',name);}
  }
  query.append('ba_param','ba_param');
  query.append('sig','synthetic-signature-NOT-VALIDATED-HERE');
  return '?'+query.toString();
}
const flush=async()=>{for(let i=0;i<30;i++)await Promise.resolve();};
function page({changes={},replyUrl=CALLBACK+'?code=ACODE&state='+STATE,client=CLIENT,callback=CALLBACK}={}) {
  const nodes={},navigations=[],requests=[];
  const element=id=>nodes[id] ??= {disabled:true,hidden:true,textContent:'',
    addEventListener(name,cb){this.click=cb;}};
  const context={URL,URLSearchParams,TextEncoder,crypto:crypto.webcrypto,
    location:{origin:HOST,pathname:'/auth/consent',search:signedQuery(changes),assign:u=>navigations.push(u)},
    history:{replaceState(){}},
    document:{querySelector:()=>({dataset:{mode:'consent',auth:BASE,resource:RESOURCE,
      clientId:client,callback,chatgptClient:'true',demoTools:'true'}}), getElementById:element},
    sessionStorage:{getItem:()=>null,setItem(){},removeItem(){}},
    fetch:async(url,options)=>{
      requests.push({url,options});
      let output;
      if(url.endsWith('/get-session'))output={user:{id:'u'},session:{id:'s'}};
      else if(url.includes('/oauth2/public-client?'))output={client_id:client,client_name:'ChatGPT private demo',redirect_uris:[]};
      else if(url.endsWith('/oauth2/consent'))output={redirect:true,url:replyUrl};
      else throw Error('unknown mock route');
      return {ok:true,json:async()=>output};
    },
  };
  vm.runInNewContext(source,context,{timeout:1500});
  return {element,navigations,requests};
}
(async()=>{
 let checks=0;
 const ok=page();await flush();
 assert.equal(ok.element('allow').disabled,false);
 assert.equal(ok.element('deny').disabled,false);
 await ok.element('allow').click();await flush();
 assert.deepEqual(ok.navigations,[CALLBACK+'?code=ACODE&state='+STATE]);
 const posted=ok.requests.find(r=>r.url.endsWith('/oauth2/consent'));
 assert.ok(posted);
 assert.equal(JSON.parse(posted.options.body).scope,'openid email offline_access');checks++;
 for (const [changes,error] of [
   [{client_id:'different-client'},'UNEXPECTED_CLIENT'],
   [{redirect_uri:'https://evil.test/callback'},'UNSAFE_CLIENT_REDIRECT'],
   [{scope:'openid garmin:read'},'UNSUPPORTED_SCOPE'],
   [{scope:'openid openid email offline_access'},'UNSUPPORTED_SCOPE'],
   [{scope:'openid email offline_access write:all'},'UNSUPPORTED_SCOPE'],
   [{resource:'https://evil.test/mcp'},'RESOURCE_MISMATCH'],
   [{code_challenge_method:'plain'},'UNSUPPORTED_OAUTH_FLOW'],
   [{prompt:'none'},'UNEXPECTED_PROMPT'],
 ]) {
    const p=page({changes});await flush();
    assert.equal(p.element('allow').disabled,true);
    assert.match(p.element('status').textContent,new RegExp(error));checks++;
 }
 for (const replyUrl of [
    'https://evil.test/steal?code=ACODE&state='+STATE,
    CALLBACK+'?code=ACODE&state=WRONG',
    CALLBACK+'?code=ACODE',
    CALLBACK+'?code=ACODE&state='+STATE+'&other=evil',
    CALLBACK+'?code=ACODE&state='+STATE+'&iss=https://evil.test',
    'https://chatgpt.com/other?code=ACODE&state='+STATE,
    CALLBACK+'?error=access_denied&code=ACODE&state='+STATE,
 ]) {
    const p=page({replyUrl});await flush();
    await p.element('allow').click();await flush();
    assert.equal(p.navigations.length,0);
    assert.match(p.element('status').textContent,/UNSAFE_PROVIDER_REDIRECT/);checks++;
 }
 const denied=page({replyUrl:CALLBACK+'?error=access_denied&state='+STATE});await flush();
 await denied.element('deny').click();await flush();
 assert.equal(denied.navigations.length,1);
 assert.equal(JSON.parse(denied.requests.find(r=>r.url.endsWith('/oauth2/consent')).options.body).accept,false);checks++;
 console.log('PASS: '+checks+' ChatGPT private staging UI simulations');
})().catch(err=>{console.error(err);process.exitCode=1;});
