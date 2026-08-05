/**
 * Cloudflare Pages Function — GET/PUT user prefs (followed / dismissed) in AUDIT_KV.
 */

const KEY = "user_prefs_v1";
const EMPTY = { followed: [], dismissed: [] };

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, PUT, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  };
}

function normalizePrefs(raw) {
  const followed = Array.isArray(raw?.followed)
    ? [...new Set(raw.followed.map(String).filter(Boolean))]
    : [];
  const dismissed = Array.isArray(raw?.dismissed)
    ? [...new Set(raw.dismissed.map(String).filter(Boolean))]
    : [];
  const followSet = new Set(followed);
  return {
    followed,
    dismissed: dismissed.filter((id) => !followSet.has(id)),
  };
}

async function readPrefs(env) {
  if (env && env.AUDIT_KV) {
    const raw = await env.AUDIT_KV.get(KEY);
    if (raw) {
      try {
        return normalizePrefs(JSON.parse(raw));
      } catch (_) {
        /* fall through */
      }
    }
  }
  return { ...EMPTY };
}

async function writePrefs(env, data) {
  if (env && env.AUDIT_KV) {
    const normalized = normalizePrefs(data);
    await env.AUDIT_KV.put(KEY, JSON.stringify(normalized));
    return { ok: true, persisted: "kv", ...normalized };
  }
  return { ok: false, persisted: "none", error: "KV binding AUDIT_KV missing" };
}

export async function onRequestOptions() {
  return new Response(null, { status: 204, headers: corsHeaders() });
}

export async function onRequestGet(context) {
  const prefs = await readPrefs(context.env);
  return new Response(JSON.stringify(prefs), { headers: corsHeaders() });
}

export async function onRequestPut(context) {
  try {
    const body = await context.request.json();
    if (!body || typeof body !== "object") {
      return new Response(JSON.stringify({ error: "invalid prefs" }), {
        status: 400,
        headers: corsHeaders(),
      });
    }
    const result = await writePrefs(context.env, body);
    if (!result.ok) {
      return new Response(JSON.stringify(result), {
        status: 503,
        headers: corsHeaders(),
      });
    }
    return new Response(JSON.stringify(result), { headers: corsHeaders() });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 500,
      headers: corsHeaders(),
    });
  }
}
