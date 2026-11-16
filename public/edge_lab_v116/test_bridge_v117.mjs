import assert from 'node:assert/strict';
import {test} from 'node:test';
import {handleBridge,expectedEventId} from './bridge_v117.mjs';
import worker from './worker.mjs';

const TOKEN = 'V117_TEST_TOKEN_FOR_FIXED_OFFLINE_SIMULATION_abcdefghijklmnopqrstuvwxyz';
const tenant='a'.repeat(64);
const BASE='https://lab.invalid/_lab/bridge/';
const event = () => expectedEventId(TOKEN,tenant);
const payload = async (who=tenant,id) => ({kind:'SYNTHETIC_BRIDGE',recipient_key:who,event_id:id ?? await event()});
async function req(action,obj,t=TOKEN){
  const body=obj ?? await payload();
  return new Request(BASE+action,{method:'POST',headers:{'content-type':'application/json','x-bridge-token':t},body:JSON.stringify(body)});
}
class FakeD1{
  constructor(){this.rows=new Map();this.fail=false;this.calls=[];this.bad=false;}
  prepare(sql){return {bind:(...args)=>({
    run:async()=>{
      this.calls.push(sql.split(' ')[0]);if(this.fail)throw Error('SECRET_DATABASE_ERROR');
      if(this.bad)return {success:false};
      if(sql.startsWith('INSERT')){
        const [k,id,digest]=args;const key=k+'\x00'+id;
        if(!this.rows.has(key))this.rows.set(key,{payload_digest:digest,acked_at:null});
      } else if(sql.startsWith('UPDATE')) {
        const [k,id,digest]=args;const key=k+'\x00'+id;const record=this.rows.get(key);
        if(record&&record.payload_digest===digest)record.acked_at=record.acked_at??'SYNTHETIC_TIMESTAMP';
      } else throw Error('Unexpected query '+sql);
      return {success:true};
    },
    first:async()=>{
      this.calls.push('SELECT');if(this.fail)throw Error('SECRET_DATABASE_ERROR');
      if(!sql.startsWith('SELECT payload_digest'))throw Error('Unexpected query');
      return this.rows.get(args[0]+'\x00'+args[1])??null;
    }
  })};}
}
function env(){return {LAB_SYNTHETIC_ONLY:'1',LAB_DB:new FakeD1(),BRIDGE_TOKEN:TOKEN,LAB_TOKEN:'V116_EXISTING_TOKEN_WITH_FULL_LENGTH_123456789'};}
test('bridge status is read-only and does not reveal credentials',async()=>{
  const e=env();const r=await handleBridge(new Request(BASE+'status'),e);const j=await r.json();
  assert.equal(r.status,200);assert.equal(j.version,'1.1.7');assert.equal(j.bridge_enabled,true);
  assert.equal(j.real_garmin_push_enabled,false);assert.equal(j.neon_connected_from_edge,false);
  assert.equal(e.LAB_DB.calls.length,0);assert.doesNotMatch(JSON.stringify(j),/V117_TEST_TOKEN|SYNTHETIC_TIMESTAMP/);
});
test('bridge disabled with missing flag, secret or D1',async()=>{
  for(const override of [{LAB_SYNTHETIC_ONLY:'0'},{BRIDGE_TOKEN:''},{LAB_DB:null}]){
    assert.equal((await handleBridge(await req('seed'),{...env(),...override})).status,503);
  }
});
test('bridge requires authenticated strong token, before DB calls',async()=>{
  const e=env();assert.equal((await handleBridge(await req('seed',await payload(),'short'),e)).status,401);
  assert.equal(e.LAB_DB.calls.length,0);
});
test('seed and claim D1 receipt; ack only after explicit separate request',async()=>{
  const e=env();const r=await handleBridge(await req('seed'),e);const j=await r.json();
  assert.equal(r.status,200);assert.equal(j.status,'PENDING_SYNTHETIC');assert.equal(j.acknowledged,false);
  assert.deepEqual(e.LAB_DB.calls,['INSERT','SELECT']);
  assert.equal((await (await handleBridge(await req('claim'),e)).json()).status,'PENDING_SYNTHETIC');
  assert.equal((await (await handleBridge(await req('ack'),e)).json()).status,'ACKED_SYNTHETIC');
  assert.equal((await (await handleBridge(await req('claim'),e)).json()).acknowledged,true);
  assert.equal(e.LAB_DB.rows.size,1);
});
test('seeding same fixed ID is idempotent even after ACK',async()=>{
  const e=env();await handleBridge(await req('seed'),e);await handleBridge(await req('ack'),e);
  const j=await (await handleBridge(await req('seed'),e)).json();
  assert.equal(j.status,'ACKED_SYNTHETIC');assert.equal(e.LAB_DB.rows.size,1);
});
test('cannot seed event with foreign recipient key or forged event ID',async()=>{
  const e=env();const wrong='b'.repeat(64);
  assert.equal((await handleBridge(await req('seed',await payload(wrong)),e)).status,403);
  assert.equal((await handleBridge(await req('seed',{...await payload(),event_id:'SYNTHETIC_BRIDGE_V117_'+'0'.repeat(32)}),e)).status,403);
  assert.equal(e.LAB_DB.rows.size,0);
});
test('claim or ack missing event cannot return success',async()=>{
  const e=env();assert.equal((await handleBridge(await req('claim'),e)).status,404);
  assert.equal((await handleBridge(await req('ack'),e)).status,404);
});
test('D1 failure means 503, never 200',async()=>{
  const e=env();e.LAB_DB.fail=true;
  const r=await handleBridge(await req('seed'),e);
  assert.equal(r.status,503);assert.doesNotMatch(await r.text(),/SECRET_DATABASE_ERROR/);
});
test('unsuccessful D1 write means 503',async()=>{
  const e=env();e.LAB_DB.bad=true;assert.equal((await handleBridge(await req('seed'),e)).status,503);
});
test('tampered D1 payload is rejected',async()=>{
  const e=env();await handleBridge(await req('seed'),e);
  e.LAB_DB.rows.get(tenant+'\x00'+await event()).payload_digest='0'.repeat(64);
  assert.equal((await handleBridge(await req('claim'),e)).status,409);
});
test('invalid JSON, Garmin payload and extra fields do not reach D1',async()=>{
  const e=env();
  for(const body of [{activities:[{userId:'GARMIN_USER'}]}, {...await payload(),gps:'46.0'},
    {...await payload(),kind:'GARMIN'}, {...await payload(),recipient_key:'b'.repeat(65)}]){
    assert.notEqual((await handleBridge(await req('seed',body),e)).status,200);
  }
  assert.equal(e.LAB_DB.calls.length,0);
});
test('POST only, no query parameters, no unrelated Garmin route',async()=>{
  const e=env();assert.equal((await handleBridge(new Request(BASE+'seed'),e)).status,404);
  assert.equal((await handleBridge(new Request(BASE+'seed?q=1',{method:'POST'}),e)).status,404);
  assert.equal((await worker.fetch(new Request('https://lab.invalid/garmin/push/activities',{method:'POST'}),e)).status,404);
});
test('new routing preserves original v1.1.6 status and no real Garmin input',async()=>{
  const e=env();const v=await (await worker.fetch(new Request('https://lab.invalid/_lab/status'),e)).json();
  assert.equal(v.version,'1.1.6');
  const b=await (await worker.fetch(new Request(BASE+'status'),e)).json();
  assert.equal(b.version,'1.1.7');
});
test('no outbound network is used from Worker',async()=>{
  const e=env();const old=globalThis.fetch;globalThis.fetch=()=>{throw Error('FORBIDDEN_OUTBOUND');};
  try{assert.equal((await worker.fetch(await req('seed'),e)).status,200);}
  finally{globalThis.fetch=old;}
});
