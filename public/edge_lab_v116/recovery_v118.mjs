/**
 * v1.1.8 D1 synthetic delivery recovery lab: never real Garmin data.
 * This Worker stores one HMAC-pseudonymized fictional receipt per caller.
 * It NEVER contacts Neon, Render or Garmin. All writes require BRIDGE_TOKEN.
 * Claim attempts are diagnostic counters, not a retry scheduler or SLA.
 */
const HDR={
  'content-type':'application/json; charset=utf-8',
  'cache-control':'no-store',
  'x-content-type-options':'nosniff',
};
const PREFIX='SYNTHETIC_RECOVERY_V118_';
const KEY_RE=/^[0-9a-f]{64}$/;
const ID_RE=/^SYNTHETIC_RECOVERY_V118_[0-9a-f]{32}$/;
const enc=new TextEncoder();
const respond=(status,code,extra={})=>new Response(
  JSON.stringify({status:code,mode:'SYNTHETIC_RECOVERY_ONLY',...extra}),
  {status,headers:HDR});

async function sha(data){
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256',enc.encode(data)))]
    .map(b=>b.toString(16).padStart(2,'0')).join('');
}
async function hmacHex(secret,data){
  const key=await crypto.subtle.importKey('raw',enc.encode(secret),
    {name:'HMAC',hash:'SHA-256'},false,['sign']);
  return [...new Uint8Array(await crypto.subtle.sign('HMAC',key,enc.encode(data)))]
    .map(b=>b.toString(16).padStart(2,'0')).join('');
}
async function tokenMatches(actual,secret){
  if(typeof secret!=='string'||secret.length<40||typeof actual!=='string'||
      actual.length<40||actual.length>4096)return false;
  const [a,b]=await Promise.all([sha(actual),sha(secret)]);
  let difference=0;
  for(let i=0;i<a.length;i++) difference |= a.charCodeAt(i)^b.charCodeAt(i);
  return difference===0;
}
export async function expectedRecoveryEvent(secret,recipientKey){
  return PREFIX+(await hmacHex(secret,'garminai-v118-recovery-event\x00'+recipientKey)).slice(0,32);
}
async function strictPayload(request){
  if(request.headers.get('content-type')?.split(';',1)[0].trim().toLowerCase()!=='application/json')return null;
  const n=request.headers.get('content-length');
  if(n&&(!/^\d+$/.test(n)||Number(n)>1024))return null;
  const raw=await request.arrayBuffer();
  if(raw.byteLength===0||raw.byteLength>1024)return null;
  const data=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(raw));
  if(!data||typeof data!=='object'||Array.isArray(data)||
    Object.keys(data).sort().join(',')!=='event_id,kind,recipient_key'||
    data.kind!=='SYNTHETIC_RECOVERY'||
    typeof data.recipient_key!=='string'||!KEY_RE.test(data.recipient_key)||
    typeof data.event_id!=='string'||!ID_RE.test(data.event_id))return null;
  return data;
}
export async function handleRecovery(request,env){
  let url;
  try{url=new URL(request.url);}catch{return respond(400,'INVALID_URL');}
  if(url.pathname==='/_lab/recovery/status'&&!url.search&&request.method==='GET'){
    return respond(200,'RECOVERY_LAB_STATUS',{
      version:'1.1.8', recovery_enabled:env?.LAB_SYNTHETIC_ONLY==='1'&&
        !!env?.LAB_DB&&typeof env?.BRIDGE_TOKEN==='string'&&env.BRIDGE_TOKEN.length>=40,
      real_garmin_push_enabled:false, outbounds_to_neon_or_render:false,
      automatic_retry_enabled:false, synthetic_only:true
    });
  }
  const match=/^\/_lab\/recovery\/(seed|claim|ack|inspect)$/.exec(url.pathname);
  if(!match||request.method!=='POST'||url.search)return respond(404,'NOT_FOUND');
  if(env?.LAB_SYNTHETIC_ONLY!=='1'||!env?.LAB_DB||
    typeof env?.BRIDGE_TOKEN!=='string'||env.BRIDGE_TOKEN.length<40)return respond(503,'LAB_DISABLED');
  if(!(await tokenMatches(request.headers.get('x-bridge-token'),env.BRIDGE_TOKEN)))
    return respond(401,'BRIDGE_AUTH_REQUIRED');
  let body;
  try{body=await strictPayload(request);}catch{return respond(400,'INVALID_JSON');}
  if(!body)return respond(422,'SYNTHETIC_RECOVERY_ONLY');
  if(body.event_id !== await expectedRecoveryEvent(env.BRIDGE_TOKEN,body.recipient_key))
    return respond(403,'RECIPIENT_BINDING_INVALID');
  const {recipient_key:tenant,event_id:event}=body;
  const digest=await sha(tenant+'\x00'+event+'\x00SYNTHETIC_RECOVERY');
  const action=match[1];
  try{
    if(action==='seed'){
      const inserted=await env.LAB_DB.prepare(
        'INSERT INTO lab_recovery_v118 (recipient_key,event_id,payload_digest) VALUES (?,?,?) ON CONFLICT(recipient_key,event_id) DO NOTHING'
      ).bind(tenant,event,digest).run();
      if(inserted?.success!==true)return respond(503,'D1_NOT_READY');
    }
    if(action==='claim'){
      const updated=await env.LAB_DB.prepare(
        'UPDATE lab_recovery_v118 SET attempt_count = attempt_count + 1 WHERE recipient_key=? AND event_id=? AND payload_digest=?'
      ).bind(tenant,event,digest).run();
      if(updated?.success!==true)return respond(503,'D1_NOT_READY');
    }
    if(action==='ack'){
      const updated=await env.LAB_DB.prepare(
        'UPDATE lab_recovery_v118 SET acked_at=COALESCE(acked_at,CURRENT_TIMESTAMP) WHERE recipient_key=? AND event_id=? AND payload_digest=?'
      ).bind(tenant,event,digest).run();
      if(updated?.success!==true)return respond(503,'D1_NOT_READY');
    }
    const row=await env.LAB_DB.prepare(
      'SELECT payload_digest,acked_at,attempt_count FROM lab_recovery_v118 WHERE recipient_key=? AND event_id=?'
    ).bind(tenant,event).first();
    if(!row)return respond(404,'SYNTHETIC_EVENT_NOT_FOUND');
    if(row.payload_digest!==digest)return respond(409,'CONFLICTING_SYNTHETIC_EVENT');
    if(!Number.isSafeInteger(row.attempt_count)||row.attempt_count<0||row.attempt_count>1000000)
      return respond(503,'D1_INVALID_COUNTER');
    if(action==='ack'&&!row.acked_at)return respond(503,'ACK_NOT_DURABLE');
    return respond(200,row.acked_at?'ACKED_SYNTHETIC':'PENDING_SYNTHETIC',{
      event_id:event,payload_digest:digest,acknowledged:!!row.acked_at,
      attempts:row.attempt_count
    });
  }catch{
    return respond(503,'D1_NOT_READY');
  }
}
