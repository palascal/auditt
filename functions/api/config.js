/**
 * Cloudflare Pages Function — GET/PUT AudiTT scrape config (KV: AUDIT_KV).
 */

const ENGINE_IDS = ["1.8_tfsi", "2.0_tfsi", "2.0_tdi", "3.2_v6", "tts", "ttrs"];

const DEFAULT_CONFIG = {
  version: 1,
  year_min: 2006,
  year_max: 2010,
  engines: ENGINE_IDS.slice(),
  price_max: 25000,
  sites: {
    lacentrale: { enabled: true, label: "La Centrale" },
    leboncoin: { enabled: true, label: "Leboncoin" },
    autoscout24: { enabled: true, label: "AutoScout24" },
    paruvendu: { enabled: true, label: "ParuVendu" },
  },
  custom_sites: [],
};

const KEY = "scrape_config_v1";

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, PUT, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  };
}

function normalize(raw) {
  const cfg = { ...DEFAULT_CONFIG, ...(raw || {}) };
  let ymin = Number(cfg.year_min) || 2006;
  let ymax = Number(cfg.year_max) || 2010;
  if (ymin > ymax) [ymin, ymax] = [ymax, ymin];
  cfg.year_min = ymin;
  cfg.year_max = ymax;
  cfg.price_max = Number(cfg.price_max) || 25000;
  cfg.engines = Array.isArray(cfg.engines)
    ? cfg.engines.map(String).filter((id) => ENGINE_IDS.includes(id))
    : ENGINE_IDS.slice();
  cfg.sites = { ...DEFAULT_CONFIG.sites, ...(cfg.sites || {}) };
  cfg.custom_sites = [];
  delete cfg.filters;
  delete cfg.include_mouthpieces;
  delete cfg.include_ligatures;
  delete cfg.filter_mode;
  return cfg;
}

async function readConfig(env) {
  if (env && env.AUDIT_KV) {
    const raw = await env.AUDIT_KV.get(KEY);
    if (raw) {
      try {
        return normalize(JSON.parse(raw));
      } catch (_) {
        /* fall through */
      }
    }
  }
  return normalize(DEFAULT_CONFIG);
}

async function writeConfig(env, data) {
  if (env && env.AUDIT_KV) {
    const cfg = normalize(data);
    await env.AUDIT_KV.put(KEY, JSON.stringify(cfg));
    return { ok: true, persisted: "kv", ...cfg };
  }
  return { ok: false, persisted: "none", error: "KV binding AUDIT_KV missing" };
}

export async function onRequestOptions() {
  return new Response(null, { status: 204, headers: corsHeaders() });
}

export async function onRequestGet(context) {
  const cfg = await readConfig(context.env);
  return new Response(JSON.stringify(cfg), { headers: corsHeaders() });
}

export async function onRequestPut(context) {
  try {
    const body = await context.request.json();
    const result = await writeConfig(context.env, body);
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
