/* Self Scanner UI - vanilla JS, no build step */
"use strict";

const $ = (s) => document.querySelector(s);

/* ---------- helpers ---------- */
function deviceId() {
  let d = localStorage.getItem("ss_device");
  if (!d) {
    d = "web-" + Math.random().toString(36).slice(2, 10);
    localStorage.setItem("ss_device", d);
  }
  return d;
}

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "X-Device-Id": deviceId() }, ...opts });
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return r.json();
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

function toast(msg, isErr = false) {
  let t = $("#toast");
  if (!t) {
    t = document.createElement("div");
    t.id = "toast";
    t.className = "toast";
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.className = "toast show" + (isErr ? " err" : "");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), 3200);
}

function coverURL(b) {
  return "/api/covers/" + encodeURIComponent((b && b.image) || "");
}

function prettyKey(k) {
  return String(k).replace(/[-_]+/g, " ").trim();
}

/* ---------- engine status ---------- */
async function pollHealth() {
  const dot = $("#statusDot"), txt = $("#statusText");
  try {
    const h = await api("/api/health");
    if (h.status === "ok") {
      dot.className = "dot ok";
      txt.textContent = h.books_indexed.toLocaleString() + " books indexed";
    } else {
      dot.className = "dot warn";
      txt.textContent = "engine loading…";
    }
  } catch (_) {
    dot.className = "dot err";
    txt.textContent = "API offline";
  }
}

/* ---------- scattered book background ---------- */
async function buildBackground() {
  const host = $("#bg");
  try {
    const data = await api("/api/background?n=44");
    host.innerHTML = "";
    (data.covers || []).forEach((name) => {
      const img = new Image();
      img.decoding = "async";
      img.alt = "";
      img.src = "/api/covers/" + encodeURIComponent(name);
      img.style.width = (80 + Math.random() * 90).toFixed(0) + "px";
      img.style.left = (Math.random() * 90).toFixed(1) + "vw";
      img.style.top = (Math.random() * 85).toFixed(1) + "vh";
      img.style.transform = "rotate(" + (Math.random() * 26 - 13).toFixed(1) + "deg)";
      host.appendChild(img);
    });
  } catch (_) { /* background is decorative */ }
}

/* ---------- scan flow ---------- */
let file = null;
const dz = $("#dropzone"), fi = $("#file"), scanBtn = $("#scanBtn"), state = $("#scanState");

function setFile(f) {
  if (!f) return;
  if (!f.type.startsWith("image/")) { toast("Please choose an image file", true); return; }
  file = f;
  scanBtn.disabled = false;
  state.textContent = f.name;
  const old = dz.querySelector(".dz-preview");
  if (old) old.remove();
  const prev = document.createElement("div");
  prev.className = "dz-preview";
  const im = document.createElement("img");
  im.src = URL.createObjectURL(f);
  prev.appendChild(im);
  dz.appendChild(prev);
}

dz.addEventListener("click", () => fi.click());
dz.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fi.click(); }
});
fi.addEventListener("change", () => setFile(fi.files[0]));
["dragenter", "dragover"].forEach((ev) =>
  dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
["dragleave", "drop"].forEach((ev) =>
  dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
dz.addEventListener("drop", (e) => setFile(e.dataTransfer.files[0]));

scanBtn.addEventListener("click", async () => {
  if (!file) return;
  scanBtn.disabled = true;
  state.innerHTML = '<span class="spinner"></span>Identifying + matching covers…';
  try {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("device_id", deviceId());
    const res = await api("/api/scan", { method: "POST", body: fd });
    renderResult(res);
    showRateCard(res);
    state.textContent = "";
    toast("Scan complete");
  } catch (e) {
    state.textContent = "";
    toast("Scan failed: " + e.message, true);
  } finally {
    scanBtn.disabled = false;
  }
});

function renderResult(res) {
  const id = res.identified || {};
  const en = res.enriched || {};
  $("#result").hidden = false;

  const conf = Math.max(0, Math.min(1, Number(id.confidence) || 0));
  const chips = ['<span class="chip">' + esc(res.identification_provider || "ai") + "</span>"];
  if (id.is_book_cover) chips.push('<span class="chip green">cover detected</span>');
  if (id.age_band && id.age_band !== "unknown") chips.push('<span class="chip">' + esc(id.age_band) + "</span>");
  if (id.cover_style) chips.push('<span class="chip">' + esc(id.cover_style) + "</span>");

  const title = (en.title && String(en.title).trim()) || id.title || "Unknown title";
  const author = (Array.isArray(en.authors) ? en.authors.join(", ") : en.authors) || id.author || "";
  const extra = en.publishedDate ? " · " + en.publishedDate : "";

  const idEl = $("#identified");
  idEl.innerHTML =
    '<img src="' + coverURL((res.similar_books || [])[0] || {}) + '" alt="cover" onerror="this.style.opacity=0.1">' +
    "<div><p class=\"t\">" + esc(title) + "</p>" +
    "<p class=\"a\">" + esc(author) + esc(extra) + "</p>" +
    '<div class="chips">' + chips.join("") + "</div>" +
    '<div class="conf"><div class="confbar"><i style="width:' + (conf * 100).toFixed(0) + '%"></i></div>' +
    "<small>identification confidence " + (conf * 100).toFixed(0) + "%</small></div></div>";

  const grid = $("#similar");
  grid.innerHTML = "";
  (res.similar_books || []).forEach((b) => {
    const card = document.createElement("div");
    card.className = "book";
    card.innerHTML =
      '<img src="' + coverURL(b) + '" alt="cover" loading="lazy" onerror="this.style.opacity=0.15">' +
      '<p class="bt">' + esc(b.title || b.slug || "") + "</p>" +
      '<div class="brow"><span class="bs">' + ((b.similarity || 0) * 100).toFixed(1) + "%</span>" +
      '<select><option value="">+ shelf…</option>' +
      '<option value="want-to-read">want to read</option>' +
      '<option value="reading">reading</option>' +
      '<option value="completed">completed</option></select></div>';
    const sel = card.querySelector("select");
    sel.addEventListener("change", async () => {
      const status = sel.value;
      if (!status) return;
      try {
        await api("/api/shelf/" + encodeURIComponent(b.slug || String(b.idx)),
          { method: "POST", body: new URLSearchParams({ status: status }) });
        toast("Added: " + (b.title || b.slug));
        loadShelf();
      } catch (e) { toast(e.message, true); }
      sel.value = "";
    });
    grid.appendChild(card);
  });
  $("#result").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ---------- shelf ---------- */
async function loadShelf() {
  const ul = $("#shelf");
  try {
    const data = await api("/api/shelf");
    const items = data.items || [];
    if (!items.length) { ul.innerHTML = '<li class="muted">No books yet — scan one!</li>'; return; }
    ul.innerHTML = items.map((it) =>
      "<li><span class=\"sk\" title=\"" + esc(it.book_key) + "\">" + esc(prettyKey(it.book_key)) + "</span>" +
      '<span class="tag ' + esc(it.status) + '">' + esc(String(it.status || "").replace(/-/g, " ")) + "</span></li>"
    ).join("");
  } catch (_) {
    ul.innerHTML = '<li class="muted">Could not load shelf</li>';
  }
}

$("#refreshShelf").addEventListener("click", loadShelf);
pollHealth();
setInterval(pollHealth, 15000);
buildBackground();
loadShelf();

/* ---------- taste profile + predicted ratings ---------- */
let currentScanKey = null;

function starWidget(el, onRate) {
  el.innerHTML = "";
  el._v = 0;
  const paint = (v) => {
    el._v = v || el._v;
    el.querySelectorAll(".star").forEach((s) =>
      s.classList.toggle("on", Number(s.dataset.v) <= (v || el._v)));
  };
  for (let i = 1; i <= 5; i++) {
    const b = document.createElement("button");
    b.className = "star";
    b.textContent = "★";
    b.dataset.v = i;
    b.setAttribute("aria-label", i + " star" + (i > 1 ? "s" : ""));
    b.addEventListener("mouseenter", () => paint(i));
    b.addEventListener("mouseleave", () => paint(0));
    b.addEventListener("click", () => onRate(i));
    el.appendChild(b);
  }
  el._paint = paint;
}

async function showRateCard(res) {
  const top = (res.similar_books || [])[0];
  if (!top) return;
  currentScanKey = top.slug || String(top.idx);
  $("#rateCover").src = coverURL(top);
  $("#rateTitle").textContent =
    ((res.identified || {}).title || top.title || "This book").trim() || "This book";
  const stars = $("#stars");
  if (!stars._wired) {
    stars._wired = true;
    starWidget(stars, async (v) => {
      try {
        await api("/api/rate/" + encodeURIComponent(currentScanKey) + "?rating=" + v);
        stars._v = v;
        stars._paint(v);
        toast("Rated " + v + "★ — taste profile updated");
        loadProfile();
        loadShelf();
      } catch (e) { toast(e.message, true); }
    });
  }
  $("#rateCard").hidden = false;
  $("#rateCard").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function loadProfile() {
  try {
    const p = await api("/api/profile?predictions=6");
    if (!p.ready) return;
    $("#profileCard").hidden = false;
    $("#profStats").textContent =
      p.stats.n_rated + " rated · avg " + (p.stats.avg || "—") + "★ · confidence " +
      Math.round((p.stats.confidence || 0) * 100) + "%";
    const chips = (p.patterns || []).map((pt) =>
      '<span class="chip pat" title="' + esc(pt.text) + '">' +
      esc(pt.label) + ": " + esc(pt.value) + " · " + pt.lift + "×</span>");
    $("#patterns").innerHTML = chips.join("") ||
      '<span class="muted">Keep rating — patterns appear after a few scans.</span>';
    renderPredictions(p);
  } catch (_) { /* profile is optional */ }
}

function renderPredictions(p) {
  const card = $("#predictCard"), grid = $("#predictions");
  const preds = p.predictions || [];
  if (!preds.length) { card.hidden = true; return; }
  card.hidden = false;
  $("#predNote").textContent = (p.stats.confidence || 0) < 0.5
    ? "early guesses — rate more books to sharpen these"
    : "from your taste vector + rating history";
  grid.innerHTML = "";
  preds.forEach((b) => {
    const el = document.createElement("div");
    el.className = "book";
    el.innerHTML =
      '<img src="' + coverURL(b) + '" alt="cover" loading="lazy" onerror="this.style.opacity=0.15">' +
      '<p class="bt">' + esc(b.title || "") + "</p>" +
      '<div class="predrow"><span class="pred">★ ' + Number(b.predicted).toFixed(1) + " predicted</span></div>" +
      '<p class="why" title="' + esc(b.why) + '">' + esc(b.why) + "</p>" +
      '<div class="brow"><select><option value="">+ shelf…</option>' +
      '<option value="want-to-read">want to read</option>' +
      '<option value="reading">reading</option>' +
      '<option value="completed">completed</option></select></div>';
    const sel = el.querySelector("select");
    sel.addEventListener("change", async () => {
      const status = sel.value;
      if (!status) return;
      try {
        await api("/api/shelf/" + encodeURIComponent(b.book_key),
          { method: "POST", body: new URLSearchParams({ status: status }) });
        toast("Added: " + b.title);
        loadShelf();
        loadProfile();
      } catch (e) { toast(e.message, true); }
      sel.value = "";
    });
    grid.appendChild(el);
  });
}

loadProfile();
