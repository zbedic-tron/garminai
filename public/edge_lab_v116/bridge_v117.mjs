/**
 * 1.1.7: Synthetic-only D1 --> authenticated MCP --> Neon bridge lab.
 * This Worker NEVER contacts Neon or Render. It cannot receive Garmin push.
 * BRIDGE_TOKEN is independent of the existing LAB_TOKEN, injected by operator.
 * Every object is a fixed-shape fictional receipt, no Garmin/user identifiers.
 */
const HEADERS = {
  'content-type': 'application/json; charset=utf-8',
  'cache-control': 'no-store',
  'x-content-type-options': 'nosniff',
};
const PREFIX = 'SYNTHETIC_BRIDGE_V117_';
const KEY_RE = /^[0-9a-f]{64}$/;
const ID_RE = /^SYNTHETIC_BRIDGE_V117_[0-9a-f]{32}$/;
const ACTIONS = Object.freeze({seed:'PENDING_SYNTHETIC', claim:'PENDING_SYNTHETIC', ack:'ACKED_SYNTHETIC'});
const enc = new TextEncoder();
const respond = (status, code, extra={}) =>
  new Response(JSON.stringify({status:code, mode:'SYNTHETIC_BRIDGE_ONLY', ...extra}),
    {status, headers:HEADERS});
const sha256 = async (data) => {
  const digest = await crypto.subtle.digest('SHA-256',enc.encode(data));
  return Array.from(new Uint8Array(digest), b=>b.toString(16).padStart(2,'0')).join('');
};
async function macHex(secret, data) {
  const key = await crypto.subtle.importKey('raw',enc.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);
  const signed = await crypto.subtle.sign('HMAC',key,enc.encode(data));
  return Array.from(new Uint8Array(signed), b=>b.toString(16).padStart(2,'0')).join('');
}
async function authMatches(provided,expected) {
  if(typeof expected!=='string'||expected.length<32||typeof provided!=='string'||provided.length<32||provided.length>4096) return false;
  const [a,b] = await Promise.all([sha256(provided),sha256(expected)]);
  // Iterate full fixed-length SHA-256 digest, no early exit on mismatch.
  let diff=0;for(let i=0;i<a.length;i++) diff |= a.charCodeAt(i)^b.charCodeAt(i);
  return diff===0;
}
function isBridgeEnabled(env) {
  return env?.LAB_SYNTHETIC_ONLY==='1' && !!env?.LAB_DB &&
    typeof env.BRIDGE_TOKEN==='string' && env.BRIDGE_TOKEN.length>=32;
}
async function strictJson(request) {
  if(request.headers.get('content-type')?.split(';',1)[0].trim().toLowerCase()!=='application/json')return null;
  const n=request.headers.get('content-length');
  if(n&&(!/^\d+$/.test(n)||Number(n)>1024)) return null;
  const raw=await request.arrayBuffer();
  if(raw.byteLength===0||raw.byteLength>1024)return null;
  const obj=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(raw));
  if(!obj||typeof obj!=='object'||Array.isArray(obj)||Object.keys(obj).sort().join(',')!=='event_id,kind,recipient_key')return null;
  if(obj.kind!=='SYNTHETIC_BRIDGE'||typeof obj.event_id!=='string'||!ID_RE.test(obj.event_id)||
    typeof obj.recipient_key!=='string'||!KEY_RE.test(obj.recipient_key))return null;
  return obj;
}
// Exported for deterministic unit tests; user subject never leaves Render.
export async function expectedEventId(secret,recipientKey) {
  return PREFIX + (await macHex(secret,'garminai-v117-event\x00'+recipientKey)).slice(0,32);
}
export async function handleBridge(request,env) {
  let url;
  try {url=new URL(request.url);}catch{return respond(400,'INVALID_URL');}
  if(url.pathname==='/_lab/bridge/status' && request.method==='GET' && !url.search) {
    return respond(200,'BRIDGE_LAB_STATUS',{
      version:'1.1.7',bridge_enabled:isBridgeEnabled(env),
      real_garmin_push_enabled:false,neon_connected_from_edge:false,
      uses_real_garmin_data:false, sender_authentication_verified:false
    });
  }
  const match=/^\/_lab\/bridge\/(seed|claim|ack)$/.exec(url.pathname);
  if(!match||request.method!=='POST'||url.search)return respond(404,'NOT_FOUND');
  if(!isBridgeEnabled(env))return respond(503,'BRIDGE_DISABLED');
  if(!(await authMatches(request.headers.get('x-bridge-token'),env.BRIDGE_TOKEN)))
    return respond(401,'BRIDGE_AUTH_REQUIRED');
  let payload;
  try {payload=await strictJson(request);} catch{return respond(400,'INVALID_JSON');}
  if(!payload)return respond(422,'SYNTHETIC_BRIDGE_ONLY');
  // Enforce event/recipient binding; a caller cannot seed someone else's key
  // with a chosen event ID, even if supplied non-Garmin fake values.
  if(payload.event_id !== await expectedEventId(env.BRIDGE_TOKEN,payload.recipient_key))
    return respond(403,'RECIPIENT_BINDING_INVALID');
  const {recipient_key:recipient,event_id:id}=payload;
  const digest=await sha256(recipient+'\x00'+id+'\x00SYNTHETIC_BRIDGE');
  try {
    if(match[1]==='seed'){
      const inserted=await env.LAB_DB.prepare(
        'INSERT INTO lab_bridge_v117 (recipient_key,event_id,payload_digest) VALUES (?,?,?) ON CONFLICT(recipient_key,event_id) DO NOTHING'
      ).bind(recipient,id,digest).run();
      if(inserted?.success!==true)return respond(503,'D1_NOT_READY');
    }
    if(match[1]==='ack'){
      const updated=await env.LAB_DB.prepare(
        'UPDATE lab_bridge_v117 SET acked_at = COALESCE(acked_at, CURRENT_TIMESTAMP) WHERE recipient_key=? AND event_id=? AND payload_digest=?'
      ).bind(recipient,id,digest).run();
      if(updated?.success!==true)return respond(503,'D1_NOT_READY');
    }
    const record=await env.LAB_DB.prepare(
      'SELECT payload_digest,acked_at FROM lab_bridge_v117 WHERE recipient_key=? AND event_id=?'
    ).bind(recipient,id).first();
    if(!record)return respond(404,'SYNTHETIC_EVENT_NOT_FOUND');
    if(record.payload_digest!==digest)return respond(409,'CONFLICTING_SYNTHETIC_EVENT');
    if(match[1]==='ack' && !record.acked_at)return respond(503,'D1_NOT_CONFIRMED');
    return respond(200, record.acked_at?'ACKED_SYNTHETIC':'PENDING_SYNTHETIC',
      {event_id:id,payload_digest:digest,acknowledged:!!record.acked_at});
  } catch {
    // Never expose SQL, D1 metadata, credentials, request bodies or stack traces.
    return respond(503,'D1_NOT_READY');
  }
}
