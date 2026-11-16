/**
 * GarminAI Public v1.1.5 - SYNTHETIC ONLY proof-of-concept.
 * Never register this Worker URL with Garmin; it does NOT authenticate Garmin.
 * No real Garmin payload may be sent to this worker. It never contacts Render.
 * Requires operator-set LAB_SYNTHETIC_ONLY=1, LAB_TOKEN and a D1 LAB_DB binding.
 * No secrets or source IP allowlists are included in this source.
 */
const JSON_HEADERS = {
  'content-type': 'application/json; charset=utf-8',
  'cache-control': 'no-store',
  'x-content-type-options': 'nosniff'
};
const EVENT_RE = /^SYNTHETIC_[A-Za-z0-9_-]{1,60}$/;
const SCENARIOS = new Set(['NORMAL', 'DUPLICATE', 'RENDER_SLEEP', 'DB_FAILURE']);
function reply(status, code) {
  return new Response(JSON.stringify({status: code, mode:'SYNTHETIC_ONLY'}), {status, headers: JSON_HEADERS});
}
function fail(status, code) { return reply(status, code); }

// Digest comparison avoids naive timing leakage for the lab token; the secret
// must still be independently random, operator-managed and never committed.
async function tokenMatches(provided, expected) {
  if (typeof expected !== 'string' || expected.length < 32 ||
      typeof provided !== 'string' || provided.length < 32 || provided.length > 4096) return false;
  const enc = new TextEncoder();
  const [a, b] = await Promise.all([
    crypto.subtle.digest('SHA-256', enc.encode(provided)),
    crypto.subtle.digest('SHA-256', enc.encode(expected))
  ]);
  const aa=new Uint8Array(a), bb=new Uint8Array(b);
  let difference=0;
  for(let i=0;i<aa.length;i++) difference |= aa[i]^bb[i];
  return difference===0;
}

export async function handleSynthetic(request, env) {
  let url;
  try { url=new URL(request.url); } catch { return fail(400, 'INVALID_URL'); }
  if (url.pathname !== '/_lab/synthetic' || url.search || request.method !== 'POST')
    return fail(404, 'NOT_FOUND');
  if (env?.LAB_SYNTHETIC_ONLY !== '1' || !env?.LAB_DB ||
      typeof env.LAB_TOKEN !== 'string' || env.LAB_TOKEN.length < 32)
    return fail(503, 'LAB_DISABLED');
  const proof=request.headers.get('x-lab-token');
  if (!(await tokenMatches(proof, env.LAB_TOKEN)))
    return fail(401, 'LAB_AUTH_REQUIRED');
  if (request.headers.get('content-type')?.split(';',1)[0].trim().toLowerCase() !== 'application/json')
    return fail(415, 'JSON_ONLY');
  const length=request.headers.get('content-length');
  if (length && (!/^\d+$/.test(length) || Number(length) > 2048)) return fail(413,'PAYLOAD_TOO_LARGE');
  let body;
  try { body=await request.arrayBuffer(); } catch { return fail(400,'UNREADABLE'); }
  if (body.byteLength===0 || body.byteLength>2048) return fail(413,'PAYLOAD_TOO_LARGE');
  let parsed;
  try { parsed=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(body)); }
  catch { return fail(400,'INVALID_JSON'); }
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object' ||
      Object.keys(parsed).sort().join(',') !== 'event_id,kind,scenario' ||
      parsed.kind !== 'SYNTHETIC' ||
      typeof parsed.event_id !== 'string' || !EVENT_RE.test(parsed.event_id) ||
      typeof parsed.scenario !== 'string' || !SCENARIOS.has(parsed.scenario))
    return fail(422, 'NON_SYNTHETIC_DATA_REJECTED');
  // Every stored field is a synthetic label, never real Garmin account data.
  const enc=new TextEncoder();
  const msg=`${parsed.event_id}\u0000${parsed.kind}\u0000${parsed.scenario}`;
  const hex=[...new Uint8Array(await crypto.subtle.digest('SHA-256', enc.encode(msg)))].map(x=>x.toString(16).padStart(2,'0')).join('');
  try {
    // This await is the durable ACK boundary.  No status 200 before D1 returns.
    await env.LAB_DB.prepare(
      'INSERT INTO lab_events_v115 (event_id, payload_digest) VALUES (?, ?) ON CONFLICT(event_id) DO NOTHING'
    ).bind(parsed.event_id,hex).run();
    const record=await env.LAB_DB.prepare(
      'SELECT payload_digest FROM lab_events_v115 WHERE event_id = ?'
    ).bind(parsed.event_id).first();
    if (!record || typeof record.payload_digest !== 'string') return fail(503,'DB_NOT_CONFIRMED');
    if (record.payload_digest !== hex) return fail(409,'CONFLICTING_DUPLICATE');
  } catch {
    // Fail closed; avoid returning stack traces, payloads, D1 metadata.
    return fail(503,'DURABLE_STORAGE_UNAVAILABLE');
  }
  return reply(200,'DURABLY_ACCEPTED_SYNTHETIC');
}

export default {fetch: handleSynthetic};
