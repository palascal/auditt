const STORAGE_FOLLOWED = "auditt_followed_v1";
const STORAGE_DISMISSED = "auditt_dismissed_v1";
const STORAGE_CONFIG = "auditt_config_v1";

const ENGINE_OPTIONS = [
  { id: "1.8_tfsi", label: "1.8 TFSI" },
  { id: "2.0_tfsi", label: "2.0 TFSI" },
  { id: "2.0_tdi", label: "2.0 TDI" },
  { id: "3.2_v6", label: "3.2 V6" },
  { id: "tts", label: "TTS" },
  { id: "ttrs", label: "TT RS" },
];

const DEFAULT_CONFIG = {
  version: 1,
  year_min: 2006,
  year_max: 2010,
  engines: ENGINE_OPTIONS.map((e) => e.id),
  price_max: 25000,
  sites: {
    lacentrale: { enabled: true, label: "La Centrale" },
    leboncoin: { enabled: true, label: "Leboncoin" },
    autoscout24: { enabled: true, label: "AutoScout24" },
    paruvendu: { enabled: true, label: "ParuVendu" },
  },
  custom_sites: [],
};

const state = {
  tab: "inbox",
  configTab: "filters",
  items: [],
  followed: new Set(),
  dismissed: new Set(),
  config: structuredClone(DEFAULT_CONFIG),
  prefsReady: false,
};

const grid = document.getElementById("grid");
const empty = document.getElementById("empty");
const updated = document.getElementById("updated");
const panel = document.getElementById("config-panel");
const backdrop = document.getElementById("config-backdrop");
const statusEl = document.getElementById("config-status");

let prefsSaveTimer = null;
let prefsSaveChain = Promise.resolve();

function readLegacyLocalPrefs() {
  const followed = [];
  const dismissed = [];
  try {
    const f = JSON.parse(localStorage.getItem(STORAGE_FOLLOWED) || "[]");
    if (Array.isArray(f)) followed.push(...f.map(String).filter(Boolean));
  } catch (_) {}
  try {
    const d = JSON.parse(localStorage.getItem(STORAGE_DISMISSED) || "[]");
    if (Array.isArray(d)) dismissed.push(...d.map(String).filter(Boolean));
  } catch (_) {}
  return { followed, dismissed };
}

function clearLegacyLocalPrefs() {
  try {
    localStorage.removeItem(STORAGE_FOLLOWED);
    localStorage.removeItem(STORAGE_DISMISSED);
  } catch (_) {}
}

function prefsPayload() {
  return { followed: [...state.followed], dismissed: [...state.dismissed] };
}

function applyPrefs(prefs) {
  state.followed = new Set((prefs.followed || []).map(String).filter(Boolean));
  const followSet = state.followed;
  state.dismissed = new Set(
    (prefs.dismissed || []).map(String).filter((id) => id && !followSet.has(id))
  );
}

async function savePrefsNow() {
  const res = await fetch("/api/prefs", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(prefsPayload()),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.persisted !== "kv") console.warn("prefs sync failed", data);
  return data;
}

function persistFollow() {
  clearTimeout(prefsSaveTimer);
  prefsSaveTimer = setTimeout(() => {
    prefsSaveChain = prefsSaveChain
      .catch(() => {})
      .then(() => savePrefsNow())
      .catch((err) => console.warn("prefs sync error", err));
  }, 180);
}

async function loadPrefs() {
  let server = { followed: [], dismissed: [] };
  try {
    const res = await fetch(`/api/prefs?ts=${Date.now()}`);
    if (res.ok) server = await res.json();
  } catch (_) {}
  const local = readLegacyLocalPrefs();
  const hasLocal = local.followed.length > 0 || local.dismissed.length > 0;
  if (hasLocal) {
    const followed = [...new Set([...(server.followed || []), ...local.followed])];
    const followSet = new Set(followed);
    const dismissed = [...new Set([...(server.dismissed || []), ...local.dismissed])].filter(
      (id) => !followSet.has(id)
    );
    applyPrefs({ followed, dismissed });
    clearLegacyLocalPrefs();
    try {
      await savePrefsNow();
    } catch (_) {}
  } else {
    applyPrefs(server);
  }
  state.prefsReady = true;
}

function persistConfigLocal() {
  localStorage.setItem(STORAGE_CONFIG, JSON.stringify(state.config));
}

function formatWhen(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}

function formatCardDate(item) {
  if (item.posted_at) {
    const p = String(item.posted_at);
    if (/^\d{4}-\d{2}-\d{2}/.test(p)) {
      try {
        return new Date(p).toLocaleDateString("fr-FR", { dateStyle: "short" });
      } catch {
        return p.slice(0, 10);
      }
    }
    return p;
  }
  if (item.found_at) {
    try {
      return new Date(item.found_at).toLocaleDateString("fr-FR", { dateStyle: "short" });
    } catch {
      return "";
    }
  }
  return "";
}

function siteEnabledForItem(item) {
  const key = item.site;
  if (!key) return true;
  const s = state.config.sites?.[key];
  return !s || s.enabled !== false;
}

function yearOk(item) {
  const y = Number(item.year);
  if (!Number.isFinite(y)) return true;
  return y >= state.config.year_min && y <= state.config.year_max;
}

function visibleItems() {
  const all = state.items.filter((it) => it && it.id);
  const base =
    state.tab === "followed"
      ? all.filter((it) => state.followed.has(it.id) && !state.dismissed.has(it.id))
      : all.filter((it) => !state.dismissed.has(it.id) && !state.followed.has(it.id));
  return base
    .filter((it) => siteEnabledForItem(it))
    .filter((it) => yearOk(it))
    .sort((a, b) => (b.found_at || "").localeCompare(a.found_at || ""));
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

const ICON_FOLLOW = `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 21.35 10.55 20.03C5.4 15.36 2 12.27 2 8.5 2 5.41 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.08C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.41 22 8.5c0 3.77-3.4 6.86-8.55 11.54L12 21.35Z"/></svg>`;
const ICON_UNFOLLOW = `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M16.5 3c-1.74 0-3.41.81-4.5 2.09C10.91 3.81 9.24 3 7.5 3 4.42 3 2 5.42 2 8.5c0 3.78 3.4 6.86 8.55 11.54L12 21.35l1.45-1.32C18.6 15.36 22 12.28 22 8.5 22 5.42 19.58 3 16.5 3Zm-4.4 15.55-.1.1-.1-.1C7.14 14.24 4 11.39 4 8.5 4 6.5 5.5 5 7.5 5c1.54 0 3.04.99 3.57 2.36h1.87C13.46 5.99 14.96 5 16.5 5c2 0 3.5 1.5 3.5 3.5 0 2.89-3.14 5.74-7.9 10.05Z"/></svg>`;
const ICON_TRASH = `<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12ZM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4Z"/></svg>`;

function applyCardAction(id, action) {
  if (action === "follow") {
    state.followed.add(id);
    state.dismissed.delete(id);
  } else if (action === "unfollow") {
    state.followed.delete(id);
  } else if (action === "remove") {
    state.dismissed.add(id);
    state.followed.delete(id);
  } else return;
  persistFollow();
  render();
}

function cardHtml(item) {
  const site = item.site_label || item.site || "Site";
  const title = item.titre || "Audi TT";
  const price = item.prix || "N/A";
  const img = item.image || "";
  const thumbClass = img ? "thumb" : "thumb placeholder";
  const thumbStyle = img ? ` style="background-image:url('${img.replace(/'/g, "%27")}')"` : "";
  const thumbInner = img ? "" : "Sans photo";
  const onFollowed = state.tab === "followed";
  const primaryAction = onFollowed ? "unfollow" : "follow";
  const primaryLabel = onFollowed ? "Ne plus suivre" : "Suivre";
  const primaryShort = onFollowed ? "Liste" : "Suivre";
  const primaryIcon = onFollowed ? ICON_UNFOLLOW : ICON_FOLLOW;
  const primaryClass = onFollowed ? "is-unfollow" : "is-follow";
  const encId = encodeURIComponent(item.id);
  const encLien = encodeURIComponent(item.lien || item.id);
  const dateLabel = formatCardDate(item);
  const yearLabel = item.year ? String(item.year) : "";
  const metaBits = [site, yearLabel, dateLabel].filter(Boolean);

  return `
    <div class="swipe-row${onFollowed ? " is-followed-tab" : ""}" data-id="${encId}" data-lien="${encLien}">
      <div class="swipe-bg swipe-bg-left" aria-hidden="true">
        <span class="swipe-action ${primaryClass}">${primaryIcon}<span>${primaryShort}</span></span>
      </div>
      <div class="swipe-bg swipe-bg-right" aria-hidden="true">
        <span class="swipe-action is-remove">${ICON_TRASH}<span>Supprimer</span></span>
      </div>
      <article class="card swipe-front" data-id="${encId}" data-lien="${encLien}" data-primary-action="${primaryAction}">
        <div class="${thumbClass}"${thumbStyle}>
          <span class="badge">${escapeHtml(site)}</span>
          ${yearLabel ? `<span class="badge badge-year">${escapeHtml(yearLabel)}</span>` : ""}
          ${thumbInner}
        </div>
        <div class="body">
          <h2 class="title">${escapeHtml(title)}</h2>
          <p class="price">${escapeHtml(price)}</p>
          <p class="card-meta">${escapeHtml(metaBits.join(" · "))}</p>
          <div class="actions">
            <button type="button" class="follow" data-action="${primaryAction}">${primaryLabel}</button>
            <button type="button" class="remove" data-action="remove">Supprimer</button>
          </div>
        </div>
      </article>
    </div>
  `;
}

const SWIPE = { threshold: 72, max: 112, suppressClick: false };

function bindSwipeHandlers() {
  grid.querySelectorAll(".swipe-front").forEach((front) => {
    if (front.dataset.swipeBound) return;
    front.dataset.swipeBound = "1";
    let startX = 0, startY = 0, dx = 0, axis = null, dragging = false, pointerId = null;

    const setX = (x, animate) => {
      front.style.transition = animate ? "transform 0.28s var(--ease)" : "none";
      front.style.transform = `translate3d(${x}px,0,0)`;
      const row = front.closest(".swipe-row");
      if (!row) return;
      row.classList.toggle("is-revealing-left", x > 8);
      row.classList.toggle("is-revealing-right", x < -8);
      row.style.setProperty("--reveal", String(Math.min(1, Math.abs(x) / SWIPE.max)));
    };
    const reset = (animate = true) => { dx = 0; setX(0, animate); };
    const commit = (action, dir) => {
      const id = decodeURIComponent(front.dataset.id || "");
      const row = front.closest(".swipe-row");
      SWIPE.suppressClick = true;
      front.style.transition = "transform 0.28s var(--ease), opacity 0.28s var(--ease)";
      front.style.transform = `translate3d(${dir * (window.innerWidth || 400)}px,0,0)`;
      front.style.opacity = "0";
      if (row) row.classList.add("is-leaving");
      window.setTimeout(() => applyCardAction(id, action), 220);
    };

    front.addEventListener("pointerdown", (e) => {
      if (e.pointerType === "mouse" && e.button !== 0) return;
      if (e.target.closest("button")) return;
      pointerId = e.pointerId;
      startX = e.clientX; startY = e.clientY; dx = 0; axis = null; dragging = true;
      front.setPointerCapture?.(pointerId);
      front.classList.add("is-dragging");
    });
    front.addEventListener("pointermove", (e) => {
      if (!dragging || e.pointerId !== pointerId) return;
      const mx = e.clientX - startX, my = e.clientY - startY;
      if (!axis) {
        if (Math.abs(mx) < 8 && Math.abs(my) < 8) return;
        axis = Math.abs(mx) > Math.abs(my) ? "h" : "v";
        if (axis === "v") { dragging = false; front.classList.remove("is-dragging"); reset(false); return; }
      }
      if (axis !== "h") return;
      e.preventDefault();
      dx = Math.sign(mx) * Math.min(SWIPE.max, Math.abs(mx)) + Math.sign(mx) * Math.max(0, Math.abs(mx) - SWIPE.max) * 0.18;
      setX(dx, false);
    }, { passive: false });
    const onUp = (e) => {
      if (e.pointerId !== pointerId) return;
      const wasDragging = dragging && axis === "h";
      dragging = false;
      front.classList.remove("is-dragging");
      try { front.releasePointerCapture?.(pointerId); } catch (_) {}
      pointerId = null;
      if (!wasDragging) { reset(true); return; }
      const primaryAction = front.dataset.primaryAction || "follow";
      if (dx <= -SWIPE.threshold) commit("remove", -1);
      else if (dx >= SWIPE.threshold) commit(primaryAction, 1);
      else reset(true);
      if (Math.abs(dx) > 12) SWIPE.suppressClick = true;
    };
    front.addEventListener("pointerup", onUp);
    front.addEventListener("pointercancel", onUp);
  });
}

function render() {
  const items = visibleItems();
  empty.hidden = items.length > 0;
  empty.textContent = items.length ? "" : "Aucune annonce ici.";
  grid.innerHTML = items.map(cardHtml).join("");
  bindSwipeHandlers();
}

function setStatus(msg, kind) {
  statusEl.textContent = msg || "";
  statusEl.classList.remove("is-ok", "is-err");
  if (kind) statusEl.classList.add(kind);
}

function setConfigTab(tab) {
  state.configTab = tab === "sites" ? "sites" : "filters";
  document.querySelectorAll(".config-tab").forEach((b) => {
    const on = b.dataset.configTab === state.configTab;
    b.classList.toggle("is-active", on);
    b.setAttribute("aria-selected", on ? "true" : "false");
  });
  document.querySelectorAll(".config-panel-pane").forEach((p) => {
    const on = p.dataset.configPanel === state.configTab;
    p.classList.toggle("is-active", on);
    p.hidden = !on;
  });
}

function syncYearUi() {
  let a = Number(document.getElementById("year-min").value);
  let b = Number(document.getElementById("year-max").value);
  if (a > b) [a, b] = [b, a];
  document.getElementById("year-min").value = a;
  document.getElementById("year-max").value = b;
  document.getElementById("year-range-label").textContent = `${a} – ${b}`;
  const min = 1998, max = 2024;
  const left = ((a - min) / (max - min)) * 100;
  const right = ((b - min) / (max - min)) * 100;
  document.querySelector(".dual-range")?.style.setProperty("--range-left", `${left}%`);
  document.querySelector(".dual-range")?.style.setProperty("--range-right", `${right}%`);
}

function renderConfigForm() {
  document.getElementById("year-min").value = state.config.year_min;
  document.getElementById("year-max").value = state.config.year_max;
  document.getElementById("price-max").value = state.config.price_max;
  syncYearUi();

  const eng = document.getElementById("engines-list");
  const selected = new Set(state.config.engines || []);
  eng.innerHTML = ENGINE_OPTIONS.map(
    (e) => `<label class="engine-chip"><input type="checkbox" data-engine="${e.id}" ${selected.has(e.id) ? "checked" : ""}/><span>${e.label}</span></label>`
  ).join("");

  const sites = document.getElementById("sites-list");
  sites.innerHTML = Object.entries(state.config.sites || [])
    .map(
      ([key, s]) =>
        `<label class="site-row"><span>${escapeHtml(s.label || key)}</span><span class="switch"><input type="checkbox" data-site="${key}" ${s.enabled !== false ? "checked" : ""}/><span class="slider"></span></span></label>`
    )
    .join("");
}

function readFormIntoConfig() {
  let ymin = Number(document.getElementById("year-min").value) || 2006;
  let ymax = Number(document.getElementById("year-max").value) || 2010;
  if (ymin > ymax) [ymin, ymax] = [ymax, ymin];
  state.config.year_min = ymin;
  state.config.year_max = ymax;
  state.config.price_max = Number(document.getElementById("price-max").value) || 25000;
  state.config.engines = [...document.querySelectorAll("[data-engine]:checked")].map((el) => el.dataset.engine);
  for (const el of document.querySelectorAll("[data-site]")) {
    const key = el.dataset.site;
    if (!state.config.sites[key]) state.config.sites[key] = { enabled: true, label: key };
    state.config.sites[key].enabled = el.checked;
  }
}

function openConfig() {
  renderConfigForm();
  setConfigTab(state.configTab);
  panel.hidden = false;
  backdrop.hidden = false;
  setStatus("");
}
function closeConfig() {
  panel.hidden = true;
  backdrop.hidden = true;
}

async function saveConfig() {
  readFormIntoConfig();
  persistConfigLocal();
  setStatus("Enregistrement…");
  try {
    const res = await fetch("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.config),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.persisted !== "kv") {
      setStatus("Enregistré en local — sync cloud échouée.", "is-err");
    } else {
      setStatus("Config enregistrée. Prochain scrape à jour.", "is-ok");
    }
  } catch (e) {
    setStatus(String(e.message || e), "is-err");
  }
  render();
}

async function loadConfig() {
  let cfg = null;
  try {
    const res = await fetch(`/api/config?ts=${Date.now()}`);
    if (res.ok) cfg = await res.json();
  } catch (_) {}
  if (!cfg) {
    try { cfg = JSON.parse(localStorage.getItem(STORAGE_CONFIG) || "null"); } catch (_) {}
  }
  state.config = {
    ...structuredClone(DEFAULT_CONFIG),
    ...(cfg || {}),
    sites: { ...DEFAULT_CONFIG.sites, ...((cfg && cfg.sites) || {}) },
    engines: (cfg && Array.isArray(cfg.engines) && cfg.engines.length)
      ? cfg.engines
      : DEFAULT_CONFIG.engines.slice(),
    year_min: Number(cfg?.year_min) || DEFAULT_CONFIG.year_min,
    year_max: Number(cfg?.year_max) || DEFAULT_CONFIG.year_max,
    price_max: Number(cfg?.price_max) || DEFAULT_CONFIG.price_max,
  };
  persistConfigLocal();
}

function isStandaloneApp() {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.matchMedia("(display-mode: fullscreen)").matches ||
    !!window.navigator.standalone
  );
}

function openListing(url) {
  if (!url) return;
  if (isStandaloneApp()) {
    window.open(url, "_blank", "noopener,noreferrer");
    return;
  }
  window.location.assign(url);
}

function onGridClick(e) {
  if (SWIPE.suppressClick) {
    e.preventDefault();
    e.stopPropagation();
    SWIPE.suppressClick = false;
    return;
  }
  const actionBtn = e.target.closest("button[data-action]");
  const card = e.target.closest(".card");
  if (!card) return;
  const id = decodeURIComponent(card.dataset.id || "");
  if (actionBtn) {
    e.preventDefault();
    e.stopPropagation();
    applyCardAction(id, actionBtn.dataset.action);
    return;
  }
  const lien = decodeURIComponent(card.dataset.lien || "");
  if (lien) openListing(lien);
}

let listingsUpdatedAt = "";
let listingsPollTimer = null;

async function fetchListingsPayload() {
  let res = await fetch(`/api/listings?ts=${Date.now()}`);
  if (!res.ok) res = await fetch(`data/listings.json?ts=${Date.now()}`);
  if (!res.ok) throw new Error("listings introuvables");
  return res.json();
}

function applyListingsData(data, { quiet = false } = {}) {
  const nextUpdated = data.updated_at || "";
  const items = Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : [];
  const changed = nextUpdated !== listingsUpdatedAt || items.length !== state.items.length;
  listingsUpdatedAt = nextUpdated;
  state.items = items;
  updated.textContent = nextUpdated
    ? `Mise à jour : ${formatWhen(nextUpdated)} · ${state.items.length} annonces`
    : `${state.items.length} annonces`;
  if (!quiet || changed) render();
  return changed;
}

async function loadData() {
  applyListingsData(await fetchListingsPayload());
}

async function refreshListingsQuiet() {
  try {
    applyListingsData(await fetchListingsPayload(), { quiet: true });
  } catch (_) {}
}

function startListingsPoll() {
  if (listingsPollTimer) return;
  listingsPollTimer = window.setInterval(refreshListingsQuiet, 90_000);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") refreshListingsQuiet();
  });
}

grid.addEventListener("click", onGridClick);
document.getElementById("btn-config").addEventListener("click", openConfig);
document.getElementById("config-close").addEventListener("click", closeConfig);
document.getElementById("config-backdrop").addEventListener("click", closeConfig);
document.getElementById("config-save").addEventListener("click", saveConfig);
document.getElementById("config-reset").addEventListener("click", () => {
  state.config = structuredClone(DEFAULT_CONFIG);
  persistConfigLocal();
  renderConfigForm();
  setStatus("Valeurs par défaut restaurées (pas encore envoyées).", "is-ok");
  render();
});
document.querySelector(".config-tabs")?.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-config-tab]");
  if (!btn) return;
  try { readFormIntoConfig(); } catch (_) {}
  setConfigTab(btn.getAttribute("data-config-tab"));
});
document.getElementById("year-min")?.addEventListener("input", syncYearUi);
document.getElementById("year-max")?.addEventListener("input", syncYearUi);
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    state.tab = btn.dataset.tab;
    render();
  });
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !panel.hidden) closeConfig();
});

(async function boot() {
  await Promise.all([loadConfig(), loadPrefs()]);
  try {
    await loadData();
    startListingsPoll();
  } catch (err) {
    updated.textContent = "Impossible de charger les annonces.";
    empty.hidden = false;
    empty.textContent = String(err.message || err);
  }
})();
