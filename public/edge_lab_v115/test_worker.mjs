import assert from 'node:assert/strict';
import {test} from 'node:test';
import {handleSynthetic} from './worker.mjs';

const TOKEN = 'test-only-randomish-secret-not-used-in-production-01234567';
const URL='https://edge.example.invalid/_lab/synthetic';
const body=(id='SYNTHETIC_001', scenario='NORMAL')=>({event_id:id,kind:'SYNTHETIC',scenario});
function req(data=body(), opts={}) {
  const headers=new Headers({'x-lab-token':TOKEN,'content-type':'application/json'});
  for(const [k,v] of Object.entries(opts.headers||{})) headers.set(k,v);
  return new Request(opts.url||URL,{method:opts.method||'POST',headers,body:opts.raw ?? JSON.stringify(data)});
}
class FakeD1 {
  constructor(){this.rows=new Map();this.fail=false;this.calls=0;}
  prepare(sql){
    return {bind:(...args)=>({run:async()=>{
      this.calls++;
      if(this.fail) throw Error('SENSITIVE_DB_ERROR');
      if (!sql.startsWith('INSERT INTO lab_events_v115')) throw Error('bad query');
      if(!this.rows.has(args[0])) this.rows.set(args[0],args[1]);
      return {success:true};
    }, first:async()=>{
      this.calls++;
      if(this.fail) throw Error('SENSITIVE_DB_ERROR');
      if(!sql.startsWith('SELECT payload_digest')) throw Error('bad query');
      return this.rows.has(args[0])?{payload_digest:this.rows.get(args[0])}:null;
    }})};
  }
}
const environment=()=>({LAB_SYNTHETIC_ONLY:'1',LAB_DB:new FakeD1(),LAB_TOKEN:TOKEN});

// Test suite exercises the REAL Worker module but only mocked D1, no network.
test('disabled by default without external service or secret',async()=>{
  const r=await handleSynthetic(req(),{});
  assert.equal(r.status,503);assert.equal((await r.json()).status,'LAB_DISABLED');
});
test('exact bounded synthetic payload ACK only after durable round-trip',async()=>{
  const e=environment();const r=await handleSynthetic(req(),e);
  assert.equal(r.status,200);assert.equal(e.LAB_DB.rows.size,1);
  assert.equal(e.LAB_DB.calls,2);assert.equal((await r.json()).status,'DURABLY_ACCEPTED_SYNTHETIC');
});
test('same ID same content does not duplicate',async()=>{
  const e=environment();
  assert.equal((await handleSynthetic(req(),e)).status,200);
  assert.equal((await handleSynthetic(req(),e)).status,200);
  assert.equal(e.LAB_DB.rows.size,1);
});
test('same ID different content is rejected and original preserved',async()=>{
  const e=environment();await handleSynthetic(req(),e);
  const r=await handleSynthetic(req(body('SYNTHETIC_001','DUPLICATE')),e);
  assert.equal(r.status,409);assert.equal(e.LAB_DB.rows.size,1);
});
test('D1 down refuses success without data leakage',async()=>{
  const e=environment();e.LAB_DB.fail=true;
  const r=await handleSynthetic(req(),e);
  assert.equal(r.status,503);assert.doesNotMatch(await r.text(),/SENSITIVE_DB_ERROR/);
});
test('fake Garmin body and fake IP headers cannot be ingested',async()=>{
  const e=environment();
  const headers={'cf-connecting-ip':'203.0.113.55','x-forwarded-for':'203.0.113.55'};
  const r=await handleSynthetic(req({activities:[{userId:'FAKE_USER'}]},{headers}),e);
  assert.equal(r.status,422);assert.equal(e.LAB_DB.rows.size,0);
});
test('no lab secret, no storage; wrong secret, no storage',async()=>{
  const e=environment();
  assert.equal((await handleSynthetic(req(body(),{headers:{'x-lab-token':'not-a-secret'}}),e)).status,401);
  assert.equal((await handleSynthetic(req(body(),{headers:{'x-lab-token':''}}),e)).status,401);
  assert.equal(e.LAB_DB.rows.size,0);
});
test('oversized, wrong content type, non synthetic and extra fields',async()=>{
  const e=environment();
  const samples=[
    req(body(),{headers:{'content-type':'text/plain'}}),
    req({event_id:'SYNTHETIC_2',kind:'REAL',scenario:'NORMAL'}),
    req({...body(),userId:'ACTUAL_GARMIN_USER'}),
    req({...body(),activities:[{}]}),
    req(body(),{raw:'x'.repeat(3000)}),
  ];
  for(const sample of samples) assert.notEqual((await handleSynthetic(sample,e)).status,200);
  assert.equal(e.LAB_DB.rows.size,0);
});
test('route methods and query strings are restricted',async()=>{
  const e=environment();
  assert.equal((await handleSynthetic(new Request('https://edge.example.invalid/garmin/push/activities',{method:'POST'}),e)).status,404);
  assert.equal((await handleSynthetic(new Request(URL+'?x=1',{method:'POST'}),e)).status,404);
  assert.equal((await handleSynthetic(new Request(URL),e)).status,404);
  assert.equal(e.LAB_DB.rows.size,0);
});
test('Render is never called: synthetic ACK is independent of its cold start',async()=>{
  const e=environment();
  const old=globalThis.fetch;
  globalThis.fetch=()=>{throw Error('UNEXPECTED_NETWORK_CALL');};
  try {assert.equal((await handleSynthetic(req(body('SYNTHETIC_SLEEP','RENDER_SLEEP')),e)).status,200);}
  finally {globalThis.fetch=old;}
});
test('commit then missing read result does not claim success',async()=>{
  const e=environment();e.LAB_DB.prepare=(sql)=>({bind:()=>({run:async()=>({success:true}),first:async()=>null})});
  assert.equal((await handleSynthetic(req(),e)).status,503);
});
