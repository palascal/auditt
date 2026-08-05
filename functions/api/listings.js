/**
 * Cloudflare Pages Function — GET listings from AUDIT_KV (updated by scraper without redeploy).
 */

const KEY = "listings_v1";

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  };
}

export async function onRequestOptions() {
  return new Response(null, { status: 204, headers: corsHeaders() });
}

export async function onRequestGet(context) {
  const env = context.env;
  if (env && env.AUDIT_KV) {
    const raw = await env.AUDIT_KV.get(KEY);
    if (raw) {
      return new Response(raw, { headers: corsHeaders() });
    }
  }
  return new Response(JSON.stringify({ error: "listings unavailable", items: [] }), {
    status: 503,
    headers: corsHeaders(),
  });
}
