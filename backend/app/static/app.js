/* =============================================================================
   Celestial Classifier: frontend logic (vanilla JS)
   ========================================================================== */
(() => {
  "use strict";

  const API = "/api";
  const PAGE_SIZE = 12;

  const META = {
    black_hole:        { emoji: "🕳️", color: "#c084fc" },
    galaxy:            { emoji: "🌌", color: "#818cf8" },
    star:              { emoji: "⭐", color: "#fcd34d" },
    planet:            { emoji: "🪐", color: "#fb923c" },
    moon:              { emoji: "🌙", color: "#cbd5e1" },
    nebula:            { emoji: "🌫️", color: "#f472b6" },
    cosmic_dust:       { emoji: "✨", color: "#fde68a" },
    star_cluster:      { emoji: "💫", color: "#67e8f9" },
    supernova_remnant: { emoji: "💥", color: "#f87171" },
    comet:             { emoji: "☄️", color: "#5eead4" },
    asteroid:          { emoji: "🪨", color: "#a8a29e" },
    quasar:            { emoji: "🔆", color: "#facc15" },
    other_celestial:   { emoji: "🔭", color: "#a78bfa" },
    not_celestial:     { emoji: "🚫", color: "#fb7185" },
  };
  const meta = (slug) => META[slug] || { emoji: "🔭", color: "#a78bfa" };

  const state = {
    file: null,
    previewUrl: null,
    maxUploadMb: 5,
    categories: [],
    counts: {},
    filter: "all",
    offset: 0,
    total: 0,
    busy: false,
    modalId: null,
  };

  const $ = (sel) => document.querySelector(sel);
  const el = {
    statusPill: $("#status-pill"), statusText: $("#status-text"),
    dropzone: $("#dropzone"), fileInput: $("#file-input"),
    dzEmpty: $("#dropzone-empty"), dzPreview: $("#dropzone-preview"), previewImg: $("#preview-img"),
    scan: $("#scan-overlay"), fileMeta: $("#file-meta"), fileName: $("#file-name"), fileSize: $("#file-size"),
    uploadLimit: $("#upload-limit"), clearBtn: $("#clear-btn"), classifyBtn: $("#classify-btn"),
    resultEmpty: $("#result-empty"), result: $("#result"), resultModel: $("#result-model"),
    resultBadge: $("#result-badge"), resultName: $("#result-name"), ringValue: $("#ring-value"),
    ringText: $("#ring-text"), resultDesc: $("#result-desc"), resultFeatures: $("#result-features"),
    resultFact: $("#result-fact"),
    kpiTotal: $("#kpi-total"), kpiCelestial: $("#kpi-celestial"), kpiEarthly: $("#kpi-earthly"),
    kpiConfidence: $("#kpi-confidence"), bars: $("#category-bars"),
    filters: $("#filters"), gallery: $("#gallery"), galleryEmpty: $("#gallery-empty"),
    historyCount: $("#history-count"), loadMore: $("#load-more-btn"),
    modal: $("#detail-modal"), modalClose: $("#modal-close"), modalImg: $("#modal-img"),
    modalBadge: $("#modal-badge"), modalName: $("#modal-name"), modalMeta: $("#modal-meta"),
    modalConfBar: $("#modal-conf-bar"), modalConfText: $("#modal-conf-text"), modalDesc: $("#modal-desc"),
    modalFeatures: $("#modal-features"), modalFact: $("#modal-fact"), modalDelete: $("#modal-delete"),
    toasts: $("#toasts"),
  };

  // ---------------------------------------------------------------------------
  // Utilities
  // ---------------------------------------------------------------------------
  const escapeHtml = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  const formatBytes = (b) => (b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(2)} MB`);

  const pct = (x) => `${Math.round((x ?? 0) * 100)}%`;

  function timeAgo(iso) {
    const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.floor(s / 60)} min ago`;
    if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
    if (s < 604800) return `${Math.floor(s / 86400)} d ago`;
    return new Date(iso).toLocaleDateString();
  }

  async function api(path, options = {}) {
    const res = await fetch(API + path, options);
    if (!res.ok) {
      let msg = `${res.status} ${res.statusText}`;
      try {
        const body = await res.json();
        if (body.detail) msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      } catch { /* not JSON */ }
      throw new Error(msg);
    }
    return res.status === 204 ? null : res.json();
  }

  function toast(message, type = "info", ms = 4500) {
    const t = document.createElement("div");
    t.className = `toast toast--${type}`;
    t.textContent = message;
    el.toasts.appendChild(t);
    setTimeout(() => {
      t.classList.add("is-leaving");
      t.addEventListener("animationend", () => t.remove(), { once: true });
    }, ms);
  }

  function animateNumber(node, to, { suffix = "", duration = 900 } = {}) {
    const from = parseFloat(node.dataset.value || "0") || 0;
    node.dataset.value = to;
    const start = performance.now();
    const step = (now) => {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      node.textContent = `${Math.round(from + (to - from) * eased)}${suffix}`;
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  const badgeHtml = (slug, label) => {
    const m = meta(slug);
    return `<span class="badge" style="--c:${m.color}">${m.emoji} ${escapeHtml(label)}</span>`;
  };

  function setBadge(node, slug, label) {
    const m = meta(slug);
    node.style.setProperty("--c", m.color);
    node.textContent = `${m.emoji} ${label}`;
  }

  function renderChips(ul, items) {
    ul.innerHTML = items
      .map((f, i) => `<li style="animation-delay:${i * 60}ms">${escapeHtml(f)}</li>`)
      .join("");
  }

  // ---------------------------------------------------------------------------
  // Starfield background
  // ---------------------------------------------------------------------------
  function initStarfield() {
    const canvas = $("#starfield");
    const ctx = canvas.getContext("2d");
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let stars = [];
    let shooting = null;
    let w = 0, h = 0, dpr = 1;

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.width = innerWidth * dpr;
      h = canvas.height = innerHeight * dpr;
      const count = Math.round((innerWidth * innerHeight) / 3200);
      const palette = ["255,255,255", "199,210,254", "165,243,252", "245,208,254", "254,240,138"];
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        r: (Math.random() * 1.3 + 0.2) * dpr,
        a: Math.random(),
        s: Math.random() * 0.02 + 0.004,
        v: (Math.random() * 0.08 + 0.02) * dpr,
        c: palette[Math.floor(Math.random() * palette.length)],
      }));
    }

    function frame() {
      ctx.clearRect(0, 0, w, h);
      for (const st of stars) {
        st.a += st.s;
        const alpha = 0.35 + Math.abs(Math.sin(st.a)) * 0.65;
        st.y += st.v;
        if (st.y > h) st.y = 0;
        ctx.beginPath();
        ctx.fillStyle = `rgba(${st.c},${alpha})`;
        ctx.arc(st.x, st.y, st.r, 0, Math.PI * 2);
        ctx.fill();
      }
      if (!shooting && Math.random() < 0.004) {
        shooting = { x: Math.random() * w * 0.7, y: Math.random() * h * 0.4, len: 0, life: 1 };
      }
      if (shooting) {
        shooting.x += 14 * dpr; shooting.y += 6 * dpr; shooting.len = Math.min(shooting.len + 18 * dpr, 220 * dpr); shooting.life -= 0.018;
        const g = ctx.createLinearGradient(shooting.x, shooting.y, shooting.x - shooting.len, shooting.y - shooting.len * 0.43);
        g.addColorStop(0, `rgba(255,255,255,${shooting.life})`);
        g.addColorStop(1, "rgba(255,255,255,0)");
        ctx.strokeStyle = g; ctx.lineWidth = 1.6 * dpr;
        ctx.beginPath(); ctx.moveTo(shooting.x, shooting.y); ctx.lineTo(shooting.x - shooting.len, shooting.y - shooting.len * 0.43); ctx.stroke();
        if (shooting.life <= 0) shooting = null;
      }
      if (!reduced) requestAnimationFrame(frame);
    }

    resize();
    addEventListener("resize", resize);
    frame();
  }

  // ---------------------------------------------------------------------------
  // Health & categories
  // ---------------------------------------------------------------------------
  async function loadHealth() {
    try {
      const h = await api("/health");
      state.maxUploadMb = h.max_upload_mb;
      el.uploadLimit.textContent = `JPEG · PNG · WEBP · max ${h.max_upload_mb} MB`;
      el.statusPill.classList.remove("is-down", "is-live", "is-mock");
      if (h.classifier_mode === "gemini") {
        el.statusPill.classList.add("is-live");
        el.statusText.textContent = `Gemini online · ${h.model}`;
      } else {
        el.statusPill.classList.add("is-mock");
        el.statusText.textContent = "Mock mode · add GEMINI_API_KEY for real AI";
      }
    } catch {
      el.statusPill.classList.add("is-down");
      el.statusText.textContent = "Backend unreachable";
    }
  }

  async function loadCategories() {
    state.categories = await api("/categories");
  }

  // ---------------------------------------------------------------------------
  // File selection
  // ---------------------------------------------------------------------------
  function selectFile(file) {
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      toast("Please choose a JPEG, PNG or WEBP image.", "error");
      return;
    }
    if (file.size > state.maxUploadMb * 1024 * 1024) {
      toast(`That image is ${formatBytes(file.size)}. The limit is ${state.maxUploadMb} MB.`, "error");
      return;
    }
    state.file = file;
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.previewUrl = URL.createObjectURL(file);
    el.previewImg.src = state.previewUrl;
    el.dzEmpty.hidden = true;
    el.dzPreview.hidden = false;
    el.fileMeta.hidden = false;
    el.fileName.textContent = file.name || "pasted-image";
    el.fileSize.textContent = formatBytes(file.size);
    el.classifyBtn.disabled = false;
    el.clearBtn.disabled = false;
  }

  function clearFile() {
    state.file = null;
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.previewUrl = null;
    el.fileInput.value = "";
    el.previewImg.removeAttribute("src");
    el.dzEmpty.hidden = false;
    el.dzPreview.hidden = true;
    el.fileMeta.hidden = true;
    el.classifyBtn.disabled = true;
    el.clearBtn.disabled = true;
  }

  function initUpload() {
    el.fileInput.addEventListener("change", (e) => selectFile(e.target.files[0]));
    ["dragenter", "dragover"].forEach((ev) =>
      el.dropzone.addEventListener(ev, (e) => { e.preventDefault(); el.dropzone.classList.add("is-dragover"); })
    );
    ["dragleave", "drop"].forEach((ev) =>
      el.dropzone.addEventListener(ev, (e) => { e.preventDefault(); el.dropzone.classList.remove("is-dragover"); })
    );
    el.dropzone.addEventListener("drop", (e) => selectFile(e.dataTransfer.files[0]));
    el.dropzone.addEventListener("click", (e) => { if (state.busy) e.preventDefault(); });
    document.addEventListener("paste", (e) => {
      const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
      if (item) selectFile(item.getAsFile());
    });
    el.clearBtn.addEventListener("click", clearFile);
    el.classifyBtn.addEventListener("click", classify);
  }

  // ---------------------------------------------------------------------------
  // Classification
  // ---------------------------------------------------------------------------
  function setBusy(busy) {
    state.busy = busy;
    el.classifyBtn.disabled = busy || !state.file;
    el.clearBtn.disabled = busy || !state.file;
    el.classifyBtn.classList.toggle("is-loading", busy);
    el.classifyBtn.querySelector(".btn__label").textContent = busy ? "Scanning…" : "Classify object";
    el.scan.hidden = !busy;
  }

  async function classify() {
    if (!state.file || state.busy) return;
    setBusy(true);
    const form = new FormData();
    form.append("file", state.file, state.file.name || "pasted-image.png");
    try {
      const result = await api("/classify", { method: "POST", body: form });
      renderResult(result);
      toast(`Saved to your log: ${meta(result.category).emoji} ${result.category_label}`, "success");
      await Promise.all([loadStats(), loadHistory(true)]);
    } catch (err) {
      toast(err.message || "Classification failed", "error", 6500);
    } finally {
      setBusy(false);
    }
  }

  function renderResult(r) {
    el.resultEmpty.hidden = true;
    el.result.hidden = false;
    // restart entry animation
    el.result.style.animation = "none"; void el.result.offsetWidth; el.result.style.animation = "";

    setBadge(el.resultBadge, r.category, r.category_label);
    el.resultName.textContent = r.object_name || r.category_label;
    el.resultDesc.textContent = r.description || "";
    renderChips(el.resultFeatures, r.visual_features);
    el.resultFact.textContent = r.fun_fact || "";
    el.resultModel.textContent = `${r.model_used} · #${r.id}`;

    const circumference = 2 * Math.PI * 52;
    el.ringValue.style.strokeDashoffset = circumference;
    requestAnimationFrame(() => {
      el.ringValue.style.strokeDashoffset = circumference * (1 - r.confidence);
    });
    el.ringText.dataset.value = "0";
    animateNumber(el.ringText, Math.round(r.confidence * 100), { suffix: "%", duration: 1300 });
  }

  // ---------------------------------------------------------------------------
  // Stats
  // ---------------------------------------------------------------------------
  async function loadStats() {
    try {
      const s = await api("/stats");
      animateNumber(el.kpiTotal, s.total);
      animateNumber(el.kpiCelestial, s.celestial);
      animateNumber(el.kpiEarthly, s.not_celestial);
      if (s.avg_confidence == null) el.kpiConfidence.textContent = "–";
      else animateNumber(el.kpiConfidence, Math.round(s.avg_confidence * 100), { suffix: "%" });

      state.counts = Object.fromEntries(s.by_category.map((c) => [c.slug, c.count]));
      state.counts.all = s.total;
      const max = Math.max(1, ...s.by_category.map((c) => c.count));
      el.bars.innerHTML = s.by_category
        .map((c) => {
          const m = meta(c.slug);
          return `<div class="bar" title="${escapeHtml(c.label)}: ${c.count} scan(s)${c.avg_confidence != null ? `, avg ${pct(c.avg_confidence)}` : ""}">
              <span class="bar__emoji">${m.emoji}</span>
              <span class="bar__label">${escapeHtml(c.label)}</span>
              <span class="bar__track"><span class="bar__fill" style="--c:${m.color}" data-w="${(c.count / max) * 100}"></span></span>
              <span class="bar__count">${c.count}</span>
            </div>`;
        })
        .join("");
      requestAnimationFrame(() =>
        el.bars.querySelectorAll(".bar__fill").forEach((b) => (b.style.width = `${b.dataset.w}%`))
      );
      renderFilters();
    } catch (err) {
      toast(`Could not load stats: ${err.message}`, "error");
    }
  }

  // ---------------------------------------------------------------------------
  // History
  // ---------------------------------------------------------------------------
  function renderFilters() {
    const chips = [{ slug: "all", label: "All" }, ...state.categories];
    el.filters.innerHTML = chips
      .filter((c) => c.slug === "all" || state.counts[c.slug] > 0 || state.filter === c.slug)
      .map((c) => {
        const icon = c.slug === "all" ? "🌠" : meta(c.slug).emoji;
        const active = state.filter === c.slug;
        return `<button type="button" role="tab" aria-selected="${active}" id="filter-${c.slug}"
            class="filter ${active ? "is-active" : ""}" data-slug="${c.slug}">
            ${icon} ${escapeHtml(c.label)}<span class="filter__count">${state.counts[c.slug] ?? 0}</span>
          </button>`;
      })
      .join("");
  }

  function cardHtml(c, index) {
    return `<button type="button" class="obs" id="obs-${c.id}" data-id="${c.id}" style="animation-delay:${(index % PAGE_SIZE) * 45}ms">
        <div class="obs__media"><img src="${c.image_url}" alt="${escapeHtml(c.object_name || c.category_label)}" loading="lazy" /></div>
        ${badgeHtml(c.category, c.category_label)}
        <div class="obs__body">
          <h3 class="obs__name">${escapeHtml(c.object_name || c.category_label)}</h3>
          <div class="obs__meta"><span>${pct(c.confidence)} confidence</span><span>${timeAgo(c.created_at)}</span></div>
        </div>
      </button>`;
  }

  async function loadHistory(reset = false) {
    if (reset) state.offset = 0;
    const params = new URLSearchParams({ limit: PAGE_SIZE, offset: state.offset });
    if (state.filter !== "all") params.set("category", state.filter);
    try {
      const page = await api(`/classifications?${params}`);
      state.total = page.total;
      const html = page.items.map((c, i) => cardHtml(c, i)).join("");
      if (reset) el.gallery.innerHTML = html;
      else el.gallery.insertAdjacentHTML("beforeend", html);
      state.offset += page.items.length;
      el.galleryEmpty.hidden = page.total > 0;
      el.loadMore.hidden = state.offset >= page.total;
      el.historyCount.textContent = page.total ? `${page.total} observation${page.total === 1 ? "" : "s"}` : "";
    } catch (err) {
      toast(`Could not load history: ${err.message}`, "error");
    }
  }

  function initHistory() {
    el.filters.addEventListener("click", (e) => {
      const btn = e.target.closest(".filter");
      if (!btn) return;
      state.filter = btn.dataset.slug;
      renderFilters();
      loadHistory(true);
    });
    el.gallery.addEventListener("click", (e) => {
      const card = e.target.closest(".obs");
      if (card) openModal(Number(card.dataset.id));
    });
    el.loadMore.addEventListener("click", () => loadHistory(false));
  }

  // ---------------------------------------------------------------------------
  // Detail modal
  // ---------------------------------------------------------------------------
  async function openModal(id) {
    try {
      const c = await api(`/classifications/${id}`);
      state.modalId = id;
      el.modalImg.src = c.image_url;
      el.modalImg.alt = c.object_name || c.category_label;
      setBadge(el.modalBadge, c.category, c.category_label);
      el.modalName.textContent = c.object_name || c.category_label;
      el.modalMeta.textContent = `${c.original_name} · ${formatBytes(c.image_size)} · ${new Date(c.created_at).toLocaleString()} · ${c.model_used}`;
      el.modalConfBar.style.width = "0";
      el.modalConfText.textContent = `${pct(c.confidence)} confidence`;
      el.modalDesc.textContent = c.description || "";
      renderChips(el.modalFeatures, c.visual_features);
      el.modalFact.textContent = c.fun_fact || "";
      el.modal.showModal();
      requestAnimationFrame(() => (el.modalConfBar.style.width = pct(c.confidence)));
    } catch (err) {
      toast(err.message, "error");
    }
  }

  function initModal() {
    el.modalClose.addEventListener("click", () => el.modal.close());
    el.modal.addEventListener("click", (e) => { if (e.target === el.modal) el.modal.close(); });
    el.modalDelete.addEventListener("click", async () => {
      if (!state.modalId || !confirm("Delete this observation permanently?")) return;
      try {
        await api(`/classifications/${state.modalId}`, { method: "DELETE" });
        el.modal.close();
        toast("Observation deleted", "success");
        await loadStats();
        if (state.filter !== "all" && !state.counts[state.filter]) state.filter = "all";
        renderFilters();
        await loadHistory(true);
      } catch (err) {
        toast(err.message, "error");
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------------
  async function init() {
    initStarfield();
    initUpload();
    initHistory();
    initModal();
    await loadHealth();
    try { await loadCategories(); } catch (err) { toast(`Could not load categories: ${err.message}`, "error"); }
    await Promise.all([loadStats(), loadHistory(true)]);
    setInterval(loadHealth, 30000);
  }

  init();
})();
