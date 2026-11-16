import assert from 'node:assert/strict';
import {test} from 'node:test';
import {handleRecovery,expectedRecoveryEvent} from './recovery_v118.mjs';
import worker from './worker.mjs';

const TOKEN='V118_ONLY_TEST_BRIDGE_TOKEN_LONG_RANDOM_SHAPE_FAKE_0012345';
const TENANT='a'.repeat(64);
const BASE='https://lab.invalid/_lab/recovery/';
const event=()=>expectedRecoveryEvent(TOKEN,TENANT);
const payload=async(who=TENANT,id)=>({kind:'SYNTHETIC_RECOVERY',recipient_key:who,event_id:id??await event()});
async function req(action,data,token=TOKEN,headers={}){
  return new Request(BASE+action,{method:'POST',headers:{'content-type':'application/json',
    'x-bridge-token':token,...headers},body:JSON.stringify(data??await payload())});
}
class FakeD1{
  constructor(){this.rows=new Map();this.calls=[];this.fail=false;this.bad=false;this.tamper=false;}
  prepare(sql){return {bind:(...args)=>({
    run:async()=>{
      this.calls.push(sql.startsWith('INSERT')?'INSERT':'UPDATE');
      if(this.fail)throw Error('DATABASE_SECRET_EXCEPTION');
      if(this.bad)return {success:false};
      if(sql.startsWith('INSERT')){
        const [tenant,id,digest]=args;
        const key=tenant+'\x00'+id;
        if(!this.rows.has(key))this.rows.set(key,{payload_digest:digest,attempt_count:0,acked_at:null});
      }else if(sql.includes('attempt_count = attempt_count + 1')){
        const [tenant,id,digest]=args;
        const row=this.rows.get(tenant+'\x00'+id);
        if(row&&row.payload_digest===digest)row.attempt_count++;
      }else if(sql.includes('SET acked_at=')){
        const [tenant,id,digest]=args;
        const row=this.rows.get(tenant+'\x00'+id);
        if(row&&row.payload_digest===digest)row.acked_at=row.acked_at??'SYNTHETIC_TIME';
      }else throw Error('unexpected SQL');
      return {success:true};
    },
    first:async()=>{
      this.calls.push('SELECT');
      if(this.fail)throw Error('DATABASE_SECRET_EXCEPTION');
      if(!sql.startsWith('SELECT payload_digest,acked_at,attempt_count'))throw Error('Unexpected select');
      const row=this.rows.get(args[0]+'\x00'+args[1]);
      return row ? {...row,payload_digest:this.tamper?'0'.repeat(64):row.payload_digest}:null;
    },
  })};}
}
function env(){return {LAB_SYNTHETIC_ONLY:'1',LAB_DB:new FakeD1(),
  BRIDGE_TOKEN:TOKEN,LAB_TOKEN:'EXISTING_LAB_TOKEN_NOT_ROTATED_LONG_ENOUGH_TEST_XXX'};}

test('recovery lab public status is read-only, static and never production-ready',async()=>{
  const e=env();const r=await handleRecovery(new Request(BASE+'status'),e);
  const j=await r.json();
  assert.equal(r.status,200);assert.equal(j.version,'1.1.8');
  assert.equal(j.real_garmin_push_enabled,false);
  assert.equal(j.outbounds_to_neon_or_render,false);
  assert.equal(j.automatic_retry_enabled,false);
  assert.deepEqual(e.LAB_DB.calls,[]);
  assert.doesNotMatch(JSON.stringify(j),/V118_ONLY_TEST|EXISTING_LAB_TOKEN/);
});
test('seed -> pending; inspect read-only; claim increments; ack -> durable state',async()=>{
  const e=env();let j=await (await handleRecovery(await req('seed'),e)).json();
  assert.equal(j.status,'PENDING_SYNTHETIC');assert.equal(j.attempts,0);
  const before=e.LAB_DB.calls.length;
  j=await (await handleRecovery(await req('inspect'),e)).json();
  assert.equal(j.attempts,0);assert.deepEqual(e.LAB_DB.calls.slice(before),['SELECT']);
  j=await (await handleRecovery(await req('claim'),e)).json();
  assert.equal(j.attempts,1);assert.equal(j.acknowledged,false);
  j=await (await handleRecovery(await req('claim'),e)).json();
  assert.equal(j.attempts,2);
  j=await (await handleRecovery(await req('ack'),e)).json();
  assert.equal(j.status,'ACKED_SYNTHETIC');assert.equal(j.acknowledged,true);
  assert.equal(j.attempts,2);assert.equal(e.LAB_DB.rows.size,1);
});
test('idempotent seeded and re-ACKed; no reset of saved event',async()=>{
  const e=env();await handleRecovery(await req('seed'),e);
  await handleRecovery(await req('ack'),e);
  assert.equal((await (await handleRecovery(await req('seed'),e)).json()).acknowledged,true);
  assert.equal((await (await handleRecovery(await req('ack'),e)).json()).attempts,0);
  assert.equal(e.LAB_DB.rows.size,1);
});
test('two recipients separated by secret-derived event binding',async()=>{
  const e=env();const a=await payload();const b=await payload('b'.repeat(64),
    await expectedRecoveryEvent(TOKEN,'b'.repeat(64)));
  assert.equal((await handleRecovery(await req('seed',a),e)).status,200);
  assert.equal((await handleRecovery(await req('seed',b),e)).status,200);
  assert.equal(e.LAB_DB.rows.size,2);
  assert.notEqual(a.event_id,b.event_id);
  assert.equal((await handleRecovery(await req('inspect',a),e)).status,200);
});
test('unauthorized, wrong event, real Garmin data and invalid shape never hit D1',async()=>{
  const e=env();
  assert.equal((await handleRecovery(await req('seed',undefined,'WRONG'),e)).status,401);
  assert.equal((await handleRecovery(await req('seed',{kind:'GARMIN',recipient_key:TENANT,event_id:await event()}),e)).status,422);
  assert.equal((await handleRecovery(await req('seed',{...await payload(),activities:[{userId:'REAL_GARMIN'}]}),e)).status,422);
  assert.equal((await handleRecovery(await req('seed',{...await payload(),event_id:'SYNTHETIC_RECOVERY_V118_'+'0'.repeat(32)}),e)).status,403);
  assert.equal((await handleRecovery(await req('seed',{...await payload(),recipient_key:'b'.repeat(64)}),e)).status,403);
  assert.deepEqual(e.LAB_DB.calls,[]);
});
test('missing, malformed, or disabled state never acknowledges nonexistent data',async()=>{
  const e=env();
  assert.equal((await handleRecovery(await req('inspect'),e)).status,404);
  assert.equal((await handleRecovery(await req('claim'),e)).status,404);
  assert.equal((await handleRecovery(await req('ack'),e)).status,404);
  assert.equal((await handleRecovery(await req('seed'),{...e,LAB_SYNTHETIC_ONLY:'0'})).status,503);
  assert.equal((await handleRecovery(await req('seed'),{...e,LAB_DB:null})).status,503);
  assert.equal((await handleRecovery(new Request(BASE+'seed'),e)).status,404);
  assert.equal((await handleRecovery(new Request(BASE+'seed?q=1',{method:'POST'}),e)).status,404);
});
test('D1 unavailable or failed run always 503, not a fake ACK',async()=>{
  const e=env();e.LAB_DB.fail=true;
  const r=await handleRecovery(await req('seed'),e);
  assert.equal(r.status,503);assert.doesNotMatch(await r.text(),/DATABASE_SECRET_EXCEPTION/);
  e.LAB_DB.fail=false;e.LAB_DB.bad=true;
  assert.equal((await handleRecovery(await req('seed'),e)).status,503);
});
test('tampered D1 digest denies inspection, claim and ACK',async()=>{
  const e=env();await handleRecovery(await req('seed'),e);
  e.LAB_DB.tamper=true;
  for(const action of ['inspect','claim','ack']){
    const r=await handleRecovery(await req(action),e);
    assert.equal(r.status,409);
  }
});
test('Worker router preserves previous v1.1.6 and v1.1.7 routes',async()=>{
  const e=env();
  const legacy=await (await worker.fetch(new Request('https://lab.invalid/_lab/status'),e)).json();
  const bridge=await (await worker.fetch(new Request('https://lab.invalid/_lab/bridge/status'),e)).json();
  const recovery=await (await worker.fetch(new Request(BASE+'status'),e)).json();
  assert.equal(legacy.version,'1.1.6');assert.equal(bridge.version,'1.1.7');
  assert.equal(recovery.version,'1.1.8');
  assert.equal((await worker.fetch(new Request('https://lab.invalid/garmin/push/activities',{method:'POST'}),e)).status,404);
});
test('no outbound fetch from Cloudflare Worker',async()=>{
  const e=env();const old=globalThis.fetch;
  globalThis.fetch=()=>{throw Error('NO_EXTERNAL_NETWORK_ALLOWED');};
  try{assert.equal((await worker.fetch(await req('seed'),e)).status,200);}
  finally{globalThis.fetch=old;}
});
test('Python/JavaScript recovery event HMAC stays identical for a fixed offline principal',async()=>{
  // Fixed value generated from Python recipient_for_recovery for the test-only
  // principal "alice"; this is a non-secret fixture, never a Garmin account.
  const tenant='310ad4650f052032104e486ceb63e174fe777502b261212bc959b2ef74ede0c1';
  assert.equal(await expectedRecoveryEvent(TOKEN,tenant),
    'SYNTHETIC_RECOVERY_V118_50a3d902e1afcb8bfac9bd6c5cd09cca');
});
