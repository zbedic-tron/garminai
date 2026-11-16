import assert from 'node:assert/strict';
import {test} from 'node:test';
import {handleSynthetic} from './worker.mjs';

const TOKEN='LOCAL_TEST_ONLY_TOKEN_NOT_A_REAL_SECRET_6789012345';
const URL='https://lab.invalid/_lab/synthetic';
const input=(id='SYNTHETIC_V116_001',scenario='NORMAL')=>({event_id:id,kind:'SYNTHETIC',scenario});
function request(obj=input(),opts={}){
  const headers={'content-type':'application/json','x-lab-token':TOKEN,...(opts.headers??{})};
  return new Request(opts.url??URL,{method:'POST',headers,body:opts.raw??JSON.stringify(obj)});
}
class FakeD1 {
  constructor(){this.rows=new Map();this.fail=false;this.decline=false;this.missing=false;this.calls=[];}
  prepare(sql){return {bind:(...params)=>({
    run:async()=>{this.calls.push('insert');if(this.fail)throw Error('PRIVATE_DB_ERROR');
      if(!sql.startsWith('INSERT INTO lab_events_v116'))throw Error('BAD_SQL');
      if(this.decline)return {success:false};
      if(!this.rows.has(params[0]))this.rows.set(params[0],params[1]);
      return {success:true};},
    first:async()=>{this.calls.push('read');if(this.fail)throw Error('PRIVATE_DB_ERROR');
      if(!sql.startsWith('SELECT payload_digest'))throw Error('BAD_SQL');
      if(this.missing)return null;
      return this.rows.has(params[0])?{payload_digest:this.rows.get(params[0])}:null;}
  })};}
}
const env=()=>({LAB_DB:new FakeD1(),LAB_TOKEN:TOKEN,LAB_SYNTHETIC_ONLY:'1'});
test('status is public but never includes secrets or personal data',async()=>{
  const e=env();const r=await handleSynthetic(new Request('https://lab.invalid/_lab/status'),e);
  assert.equal(r.status,200);const v=await r.json();
  assert.equal(v.version,'1.1.6');assert.equal(v.real_garmin_push_enabled,false);
  assert.equal(v.sender_authentication_verified,false);assert.equal(v.lab_enabled,true);
  assert.doesNotMatch(JSON.stringify(v),/LOCAL_TEST_ONLY_TOKEN|PRIVATE_DB_ERROR/);
});
test('disabled unless token + flag + DB all configured',async()=>{
  for(const e of [{},{LAB_DB:new FakeD1(),LAB_SYNTHETIC_ONLY:'1'}, {...env(),LAB_SYNTHETIC_ONLY:'0'},{...env(),LAB_DB:null}]){
    assert.equal((await handleSynthetic(request(),e)).status,503);
  }
});
test('durable ack occurs only after D1 insert and confirming read',async()=>{
  const e=env();const r=await handleSynthetic(request(),e);
  assert.equal(r.status,200);assert.deepEqual(e.LAB_DB.calls,['insert','read']);
  assert.equal(e.LAB_DB.rows.size,1);
  assert.equal((await r.json()).status,'DURABLY_ACCEPTED_SYNTHETIC');
});
test('duplicate same ID and content stores one row',async()=>{
  const e=env();await handleSynthetic(request(),e);const r=await handleSynthetic(request(),e);
  assert.equal(r.status,200);assert.equal(e.LAB_DB.rows.size,1);
});
test('same ID different scenario is conflict without overwrite',async()=>{
  const e=env();await handleSynthetic(request(),e);
  assert.equal((await handleSynthetic(request(input('SYNTHETIC_V116_001','DUPLICATE')),e)).status,409);
  assert.equal(e.LAB_DB.rows.size,1);
});
test('failed D1 write does not produce 200',async()=>{
  const e=env();e.LAB_DB.fail=true;
  const r=await handleSynthetic(request(),e);assert.equal(r.status,503);
  assert.doesNotMatch(await r.text(),/PRIVATE_DB_ERROR/);
});
test('non-exception unsuccessful D1 write does not produce 200',async()=>{
  const e=env();e.LAB_DB.decline=true;
  assert.equal((await handleSynthetic(request(),e)).status,503);
});
test('missing read-back does not produce 200',async()=>{
  const e=env();e.LAB_DB.missing=true;
  assert.equal((await handleSynthetic(request(),e)).status,503);
});
test('real-looking Garmin formats and spoofed headers cannot write',async()=>{
  const e=env();const r=await handleSynthetic(request({activities:[{userId:'NOT_REAL'}]},
    {headers:{'cf-connecting-ip':'203.0.113.1','x-forwarded-for':'203.0.113.1'}}),e);
  assert.equal(r.status,422);assert.equal(e.LAB_DB.calls.length,0);
});
test('no secret or wrong secret cannot write',async()=>{
  const e=env();const r=await handleSynthetic(request(input(),{headers:{'x-lab-token':'short'}}),e);
  assert.equal(r.status,401);assert.equal(e.LAB_DB.calls.length,0);
});
test('unrelated routes and GET /_lab/synthetic refuse',async()=>{
  const e=env();for(const u of ['https://lab.invalid/garmin/push/activities',URL+'?x=1']){
    assert.equal((await handleSynthetic(new Request(u,{method:'POST'}),e)).status,404);
  }
  assert.equal((await handleSynthetic(new Request(URL),e)).status,404);
});
test('oversize / wrong content type / unexpected fields refuse',async()=>{
  const e=env();const samples=[
    request(input(),{raw:'x'.repeat(2500)}),
    request(input(),{headers:{'content-type':'text/plain'}}),
    request({...input(),gps:'123.123'}),
    request({...input(),kind:'GARMIN'}),
    request(input(),{raw:'{'})
  ];
  for(const x of samples)assert.notEqual((await handleSynthetic(x,e)).status,200);
  assert.equal(e.LAB_DB.calls.length,0);
});
test('no Render, Neon or Garmin fetch for successful response',async()=>{
  const e=env();const old=globalThis.fetch;
  globalThis.fetch=()=>{throw Error('UNAUTHORIZED_NETWORK_CALL');};
  try{assert.equal((await handleSynthetic(request(input('SYNTHETIC_V116_SLEEP','RENDER_SLEEP')),e)).status,200);}
  finally{globalThis.fetch=old;}
});
test('status disabled without secret',async()=>{
  const r=await handleSynthetic(new Request('https://lab.invalid/_lab/status'),{});
  const v=await r.json();assert.equal(v.lab_enabled,false);
});
