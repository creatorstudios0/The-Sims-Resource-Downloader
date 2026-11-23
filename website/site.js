const $ = id => document.getElementById(id);
const browse = document.body.dataset.view === "browse";
const sample = document.body.dataset.mode === "sample";
const apache = document.body.dataset.host === "apache";
const detailId = apache ? new URLSearchParams(location.search).get("mod") : location.pathname.split("/").pop();
const isBrowse = apache ? !detailId : browse;
if (apache) document.body.dataset.view = isBrowse ? "browse" : "detail";
const allCategories = ["All", "Hair", "Clothing", "Build & Buy", "Lots", "Households", "Gameplay"];
const escaped = value => String(value ?? "").replace(/[&<>"']/g, char =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const plain = value => escaped(value || "Unknown");
const route = id => (apache ? "?mod=" : "/mods/") + encodeURIComponent(id);
const catalogUrl = apache ? "./catalog.json" : "/api/catalog";
let apacheCatalog;

async function getApacheCatalog() {
  if (!apacheCatalog) {
    const data = await get(catalogUrl);
    if (!Array.isArray(data)) throw new Error("The local catalog must contain a JSON array.");
    apacheCatalog = data;
  }
  return apacheCatalog;
}

async function searchApache(params) {
  const data = await getApacheCatalog();
  const value = key => (params.get(key) || "").toLowerCase();
  const found = data.filter(item => (!value("category") || item.category.toLowerCase() === value("category")) &&
    (!value("creator") || item.creator.toLowerCase().includes(value("creator"))) &&
    (!value("style") || item.style.toLowerCase() === value("style")) &&
    (!value("pack") || item.packs?.some(pack => pack.toLowerCase() === value("pack"))) &&
    [item.name, item.creator, item.summary, item.category].join(" ").toLowerCase().includes(value("q")));
  const start = (Number(params.get("page") || 1) - 1) * 6;
  return { items: found.slice(start, start + 6), total: found.length, next: start + 6 < found.length };
}

async function detailApache(id) {
  const item = (await getApacheCatalog()).find(entry => entry.id === id);
  if (!item) throw new Error("This resource could not be found.");
  return { ...item, sample: true, file: null };
}

function image(item, detail = false) {
  if (item.sample && Number.isInteger(item.tile) && item.tile >= 0 && item.tile < 6) {
    return '<div class="tile tile-' + item.tile + '" role="img" aria-label="' + escaped(item.name) + ' sample artwork"></div>';
  }
  const url = detail ? item.screenshots?.[0] || item.image : item.image;
  return url ? '<img src="' + escaped(url) + '" alt="' + escaped(item.name) + '" loading="lazy">' : "";
}

async function get(url, signal) {
  const response = await fetch(url, { signal });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Please try again.");
  return payload;
}

if (isBrowse) {
  const fields = { q: $("query"), creator: $("creator"), style: $("style"), pack: $("pack") };
  const stored = new URLSearchParams(location.search);
  for (const [key, control] of Object.entries(fields)) control.value = stored.get(key) || "";
  if (!sample) fields.pack.value = "";
  let category = allCategories.includes(stored.get("category")) ? stored.get("category") : "All";
  let page = Math.max(1, Number.parseInt(stored.get("page"), 10) || 1);
  let request;

  for (const group of allCategories) {
    const control = document.createElement("button");
    control.type = "button";
    control.className = "chip";
    control.textContent = group;
    control.dataset.category = group;
    $("categories").append(control);
  }

  function query() {
    const values = new URLSearchParams();
    for (const [name, control] of Object.entries(fields)) {
      if (control.value.trim()) values.set(name, control.value.trim());
    }
    if (category !== "All") values.set("category", category);
    if (page !== 1) values.set("page", page);
    return values;
  }

  async function update(scroll = false) {
    request?.abort();
    request = new AbortController();
    const signal = request.signal;
    const params = query().toString();
    history.replaceState(null, "", location.pathname + (params ? "?" + params : "") + location.hash);
    for (const control of $("categories").children) {
      control.setAttribute("aria-pressed", control.dataset.category === category);
    }
    $("results-status").textContent = "Loading catalog…";
    $("pagination").hidden = true;
    $("results").setAttribute("aria-busy", "true");
    try {
      const data = apache ? await searchApache(new URLSearchParams(params))
        : await get(catalogUrl + (params ? "?" + params : ""), signal);
      if (signal.aborted) return;
      $("results-status").textContent = Number.isInteger(data.total)
        ? data.total.toLocaleString() + (data.total === 1 ? " resource" : " resources")
        : (data.items.length ? "Page " + page : "No matches on this page");
      const content = data.items.map(item =>
        '<a class="card" href="' + route(item.id) + '"><div class="card-media">' +
        image(item) + '<span class="category-tag">' + plain(item.category) + '</span></div><div class="card-body">' +
        '<h3 class="card-title">' + plain(item.name) + '</h3><p class="card-creator">' + plain(item.creator) + '</p>' +
        '<p class="card-summary">' + escaped(item.summary) + '</p>' +
        (item.style ? '<span class="card-style">' + escaped(item.style) + '</span>' : "") + '</div></a>');
      $("results").innerHTML = content.length ? content.join("")
        : '<p class="empty">' + (data.next ? "Try the next page or adjust your filters." : "Try another search or clear your filters.") + '</p>';
      $("pagination").hidden = page === 1 && !data.next;
      $("previous").disabled = page <= 1;
      $("next").disabled = !data.next;
      $("page-label").textContent = "Page " + page;
      if (scroll) $("catalog").scrollIntoView();
    } catch (error) {
      if (signal.aborted) return;
      $("results").innerHTML = "";
      $("results-status").textContent = error.message;
      const retry = document.createElement("button");
      retry.className = "btn secondary";
      retry.textContent = "Try again";
      retry.onclick = () => update();
      $("results").append(retry);
    } finally {
      if (!signal.aborted) $("results").removeAttribute("aria-busy");
    }
  }

  $("categories").addEventListener("click", event => {
    const group = event.target.closest("[data-category]")?.dataset.category;
    if (!group) return;
    category = group;
    page = 1;
    update();
  });
  $("search-form").addEventListener("submit", event => { event.preventDefault(); page = 1; update(); });
  for (const control of [fields.creator, fields.style, fields.pack]) {
    control.addEventListener("change", () => { page = 1; update(); });
  }
  $("clear").addEventListener("click", () => {
    for (const control of Object.values(fields)) control.value = "";
    category = "All";
    page = 1;
    update();
  });
  $("previous").addEventListener("click", () => { if (page > 1) { page--; update(true); } });
  $("next").addEventListener("click", () => { page++; update(true); });
  update();
} else {
  const back = '<a class="back" href="' + (apache ? './#catalog' : '/#catalog') + '">Back to Discover</a>';
  const loadDetail = apache ? detailApache(detailId) : get("/api/mods/" + encodeURIComponent(detailId));

  loadDetail.then(item => {
    document.title = item.name + " · Sims 4 Mod Library";
    const source = /^https?:\/\//i.test(item.source || "")
      ? '<a class="btn secondary" href="' + escaped(item.source) + '">Visit creator</a>' : "";
    const validId = value => /^[1-9][0-9]{0,9}$/.test(value) && Number(value) <= 4294967295;
    const link = !item.sample && validId(item.id) && validId(item.file?.id)
      ? "sims4modlibrary://curseforge/install?project=" + item.id + "&amp;file=" + item.file.id : "";
    const install = link ? '<a class="btn primary" href="' + link + '">Open in Mod Library</a>' : "";
    const gallery = item.screenshots?.length > 1
      ? '<div class="screenshots">' + item.screenshots.slice(1).map(url => '<a href="' + escaped(url) + '"><img src="' +
        escaped(url) + '" alt="' + escaped(item.name) + ' screenshot" loading="lazy"></a>').join("") + '</div>' : "";
    const versions = item.files?.length
      ? '<details class="versions"><summary>Recent files</summary><ul>' + item.files.map(file => '<li>' + escaped(file) + '</li>').join("") + '</ul></details>' : "";
    const deps = item.dependencies?.length
      ? item.dependencies.filter(validId).map(id => '<a href="' + route(id) + '">CurseForge resource ' + id + '</a>').join(", ")
      : item.dependencies ? "None listed" : "Unknown";
    const preview = item.sample ? '<p class="preview-note">Sample preview · fictional listing</p>' : "";
    const note = item.sample ? "This sample illustrates the install flow. No download is available."
      : link ? "Requires the Windows app with website links enabled. You’ll review the files before installing."
        : "Download from the creator when available, then use Import files in the Windows app.";
    $("detail").innerHTML = back + '<div class="detail-grid"><div><div class="detail-media">' + image(item, true) +
      '</div>' + gallery + '</div><div>' + preview + '<p class="type-label">' + plain(item.category) + '</p>' +
      '<h1 class="detail-heading">' + plain(item.name) + '</h1><p class="card-creator">By ' + plain(item.creator) + '</p>' +
      '<p class="detail-description">' + escaped(item.description) + '</p><dl class="meta-list">' +
      '<div><dt>Version</dt><dd>' + plain(item.version) + '</dd></div>' +
      '<div><dt>Required packs</dt><dd>' + plain(item.packs?.join(", ")) + '</dd></div>' +
      '<div><dt>Game versions</dt><dd>' + plain(item.compatibility) + '</dd></div>' +
      '<div><dt>Dependencies</dt><dd>' + deps + '</dd></div></dl>' +
      '<div class="detail-actions">' + install + source + '</div><p class="detail-note">' + note + '</p>' + versions + '</div></div>';
  }).catch(error => {
    $("detail").innerHTML = back + '<h1 class="detail-heading">Resource unavailable</h1><p>' + escaped(error.message) + '</p>';
  });
}
