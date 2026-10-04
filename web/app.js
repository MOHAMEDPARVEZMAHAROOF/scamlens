/* ScamLens frontend — vanilla JS */
"use strict";
const $ = (id) => document.getElementById(id);

let lang = "en";
let currentScan = null;

/* ---------- toast ---------- */
let toastTimer = null;
function toast(msg, isErr) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.toggle("err", !!isErr);
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 4000);
}

/* ---------- tabs ---------- */
document.querySelectorAll("nav button").forEach((b) => {
  b.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    $("tab-" + b.dataset.tab).classList.add("active");
    if (b.dataset.tab === "history") loadHistory();
  });
});
function showTab(name) {
  document.querySelector(`nav button[data-tab="${name}"]`).click();
}

/* ---------- status ---------- */
async function refreshStatus() {
  try {
    const s = await (await fetch("/api/status")).json();
    const badge = $("status-badge");
    badge.textContent = (s.llm ? "● AI online" : "○ rules mode") + " · " + s.backend;
    badge.title = s.llm ? "AI analysis enabled" : "No API key — rules-based analysis";
    $("history-count").textContent = s.scans ? s.scans + " scan" + (s.scans > 1 ? "s" : "") + " total" : "";
  } catch (e) {
    $("status-badge").textContent = "○ offline";
  }
}
refreshStatus();
setInterval(refreshStatus, 30000);

/* ---------- language toggle ---------- */
document.querySelectorAll(".lang-toggle button").forEach((b) => {
  b.addEventListener("click", () => {
    document.querySelectorAll(".lang-toggle button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    lang = b.dataset.lang;
    if (currentScan) renderTrick(currentScan);
  });
});

/* ---------- scan ---------- */
$("scan-btn").addEventListener("click", async () => {
  const text = $("scan-input").value.trim();
  if (!text) { toast("Paste a message first.", true); return; }
  const btn = $("scan-btn");
  btn.disabled = true;
  btn.textContent = "Analyzing…";
  try {
    const r = await fetch("/api/scan", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text}),
    });
    if (!r.ok) throw new Error(await r.text());
    const scan = await r.json();
    currentScan = scan;
    renderResult(scan);
    refreshStatus();
  } catch (e) {
    toast("Scan failed: " + (e.message || "network error"), true);
  } finally {
    btn.disabled = false;
    btn.textContent = "Scan";
  }
});

function verdictClass(v) {
  return v === "SAFE" ? "v-safe" : v === "SCAM" ? "v-scam" : "v-suspicious";
}

function renderResult(scan) {
  const box = $("result");
  box.innerHTML = "";
  box.classList.remove("hidden");

  const verdict = document.createElement("div");
  verdict.className = "verdict " + verdictClass(scan.verdict);
  const label = document.createElement("span");
  label.className = "v-label";
  label.textContent = scan.verdict;
  const conf = document.createElement("span");
  conf.className = "v-conf";
  conf.textContent = scan.confidence + "% confident";
  verdict.append(label, conf);
  box.appendChild(verdict);

  const body = document.createElement("div");
  body.className = "result-body";

  /* red flags */
  const h1 = document.createElement("h3");
  h1.textContent = "Red flags";
  body.appendChild(h1);
  const flags = scan.red_flags || [];
  if (!flags.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "No suspicious phrases detected.";
    body.appendChild(p);
  }
  flags.forEach((f) => {
    const d = document.createElement("div");
    d.className = "flag";
    const q = document.createElement("blockquote");
    q.textContent = "“" + f.phrase + "”";
    const meta = document.createElement("div");
    meta.className = "meta";
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = f.category;
    const why = document.createElement("span");
    why.className = "why";
    why.textContent = f.why;
    meta.append(chip, why);
    d.append(q, meta);
    body.appendChild(d);
  });

  /* the trick, explained */
  const h2 = document.createElement("h3");
  h2.textContent = "The trick, explained";
  body.appendChild(h2);
  const trick = document.createElement("p");
  trick.className = "trick-text";
  trick.id = "trick-text";
  body.appendChild(trick);
  renderTrickInto(scan, trick);

  /* checklist */
  const h3 = document.createElement("h3");
  h3.textContent = "What to do now";
  body.appendChild(h3);
  const ul = document.createElement("ul");
  ul.className = "checklist";
  (scan.checklist || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    ul.appendChild(li);
  });
  body.appendChild(ul);

  /* actions */
  const actions = document.createElement("div");
  actions.className = "result-actions";
  const copyBtn = document.createElement("button");
  copyBtn.className = "btn-ghost";
  copyBtn.textContent = "Copy verdict card";
  copyBtn.addEventListener("click", () => copyCard(scan.id));
  const mode = document.createElement("span");
  mode.className = "mode-note";
  mode.textContent = scan.mode === "llm" ? "Analyzed with AI" : "Analyzed with rules (offline mode)";
  actions.append(copyBtn, mode);
  body.appendChild(actions);

  box.appendChild(body);
  box.scrollIntoView({behavior: "smooth", block: "start"});
}

function renderTrick(scan) {
  const el = $("trick-text");
  if (el) renderTrickInto(scan, el);
}
function renderTrickInto(scan, el) {
  el.textContent = (lang === "ta" && scan.trick_ta) ? scan.trick_ta : scan.trick_en;
  el.lang = lang === "ta" ? "ta" : "en";
}

async function copyCard(id) {
  try {
    const r = await fetch("/api/card/" + encodeURIComponent(id));
    if (!r.ok) throw new Error(await r.text());
    const text = await r.text();
    await navigator.clipboard.writeText(text);
    toast("Verdict card copied.");
  } catch (e) {
    toast("Couldn't copy: " + (e.message || "clipboard unavailable"), true);
  }
}

/* ---------- history ---------- */
async function loadHistory() {
  const list = $("history-list");
  list.innerHTML = "";
  try {
    const scans = await (await fetch("/api/scans")).json();
    if (!scans.length) {
      list.innerHTML = '<div class="empty">No scans yet. Paste a suspicious message on the Scan tab.</div>';
      return;
    }
    scans.forEach((s) => {
      const item = document.createElement("div");
      item.className = "hitem";

      const main = document.createElement("div");
      main.className = "h-main";
      const top = document.createElement("div");
      top.style.cssText = "display:flex;gap:8px;align-items:center;flex-wrap:wrap;";
      const chip = document.createElement("span");
      chip.className = "vchip " + verdictClass(s.verdict);
      chip.textContent = s.verdict;
      const conf = document.createElement("span");
      conf.className = "h-conf";
      conf.textContent = s.confidence + "%";
      top.append(chip, conf);
      const excerpt = document.createElement("p");
      excerpt.className = "h-excerpt";
      excerpt.textContent = s.excerpt;
      const time = document.createElement("div");
      time.className = "h-time";
      const d = new Date(s.created_at);
      time.textContent = isNaN(d) ? s.created_at : d.toLocaleString();
      main.append(top, excerpt, time);

      const del = document.createElement("button");
      del.className = "h-del";
      del.textContent = "Delete";
      del.addEventListener("click", async (e) => {
        e.stopPropagation();
        try {
          const r = await fetch("/api/scans/" + encodeURIComponent(s.id), {method: "DELETE"});
          if (!r.ok) throw new Error(await r.text());
          loadHistory();
          refreshStatus();
        } catch (err) {
          toast("Delete failed: " + (err.message || "network error"), true);
        }
      });

      item.append(main, del);
      item.addEventListener("click", () => openScan(s.id));
      list.appendChild(item);
    });
  } catch (e) {
    list.innerHTML = '<div class="empty">Couldn\'t load history.</div>';
  }
}

async function openScan(id) {
  try {
    const r = await fetch("/api/scans/" + encodeURIComponent(id));
    if (!r.ok) throw new Error(await r.text());
    const scan = await r.json();
    currentScan = scan;
    showTab("scan");
    renderResult(scan);
  } catch (e) {
    toast("Couldn't load scan: " + (e.message || "network error"), true);
  }
}
