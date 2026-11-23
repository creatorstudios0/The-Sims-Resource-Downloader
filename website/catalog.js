const GAME = 781;
const PAGE = 6;
const GROUPS = ["Hair", "Clothing", "Build & Buy", "Lots", "Households", "Gameplay"];
const STYLES = ["Maxis Match", "Alpha"];
const CF_SEARCH = "https://www.curseforge.com/sims4";
const FORMATS = /\.(zip|package|ts4script|trayitem|blueprint|bpi|hhi|sgi|householdbinary|room|rmi)$/i;

const samples = [
  ["ivybrook-cottage", "Ivybrook Cottage", "Juniper Lane", "Lots", "Maxis Match", "A flower-lined stone cottage with a sunlit kitchen and room to grow.", "Cottage Living", "Place the lot from your in-game Library after importing its Tray files."],
  ["soft-wave-hair", "Soft Wave Hair", "Marigold Studio", "Hair", "Alpha", "Long, loose waves with a soft side part and warm swatches.", "Base game", "A standalone hairstyle for everyday outfits and formal looks."],
  ["honeywood-kitchen", "Honeywood Kitchen", "Oak & Fern", "Build & Buy", "Maxis Match", "Sage cabinets, oak counters, copper cookware, and a matching kitchen island.", "Base game", "A coordinated Build & Buy set with surfaces, storage, and decor."],
  ["sage-knit-cardigan", "Sage Knit Cardigan", "Marigold Studio", "Clothing", "Maxis Match", "A textured knit with relaxed sleeves and warm autumn colors.", "Base game", "Pair the cropped cardigan with high-waisted trousers in Create-a-Sim."],
  ["the-park-family", "The Park Family", "Juniper Lane", "Households", "", "Three Sims with a shared love of art, plants, and weekend pancakes.", "Growing Together", "A household for your Library with a ready-made family story."],
  ["slow-sunday-routines", "Slow Sunday Routines", "Nook Works", "Gameplay", "", "Make space for morning journaling, reading, and a slower start.", "Base game", "An example gameplay mod with a small set of daily interactions."],
  ["garden-room-annex", "Garden Room Annex", "Oak & Fern", "Lots", "Maxis Match", "A compact garden retreat with generous windows and an outdoor path.", "Base game", "A separate sample lot for players who enjoy small builds.", 0],
  ["weekend-knit-set", "Weekend Knit Set", "Marigold Studio", "Clothing", "Maxis Match", "Coordinating warm layers for a laid-back afternoon.", "Base game", "A seasonal outfit set with a coordinated palette.", 3],
  ["oakwood-study", "Oakwood Study", "Nook Works", "Build & Buy", "Maxis Match", "A dark-green study with an oak desk, brass lamp, and shelves.", "Base game", "A compact furniture and decor set for a home office.", 5],
].map(([id, name, creator, category, style, summary, pack, description, tile], i) => ({
  id, name, creator, category, style, summary, packs: [pack], description, tile: tile ?? i,
  sample: true, version: "1.0", compatibility: "", dependencies: null, source: "", file: null,
}));

class CatalogError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function curseforge(env, path, params = {}) {
  const url = new URL("https://api.curseforge.com/v1" + path);
  url.search = new URLSearchParams(params).toString();
  try {
    const response = await fetch(url, {
      headers: { "x-api-key": env.CURSEFORGE_API_KEY, Accept: "application/json" },
      redirect: "error", signal: AbortSignal.timeout(8000),
    });
    if (response.status === 404) throw new CatalogError("This resource could not be found.", 404);
    if (!response.ok) throw new CatalogError("CurseForge is unavailable. Try again shortly.", 503);
    return await response.json();
  } catch (error) {
    if (error instanceof CatalogError) throw error;
    throw new CatalogError("CurseForge is unavailable. Try again shortly.", 503);
  }
}

function verifiedUrl(value, kind) {
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password || url.port) return "";
    const allowed = kind === "image" ? /(^|\.)forgecdn\.net$/i : /^(www\.)?curseforge\.com$/i;
    return allowed.test(url.hostname) ? url.href : "";
  } catch {
    return "";
  }
}

function groupOf(tag) {
  const title = tag.trim().toLowerCase();
  if (/\b(hair|hairstyles)\b/.test(title)) return "Hair";
  if (/\b(clothing|clothes|tops|bottoms|full body|outfits)\b/.test(title)) return "Clothing";
  if (/\b(build|buy|furniture|decor)\b/.test(title)) return "Build & Buy";
  if (/\b(lots|rooms)\b/.test(title)) return "Lots";
  if (/\b(households|sims)\b/.test(title) && !/the sims 4|create.a.sim/.test(title)) return "Households";
  if (/^(mods|gameplay|gameplay mods)$/.test(title)) return "Gameplay";
  return "";
}

function normalize(project) {
  if (project.gameId !== GAME || !Number.isSafeInteger(project.id) || project.id < 1) return null;
  const tags = (project.categories ?? []).map(item => item.name ?? "");
  const groups = tags.map(groupOf).filter(Boolean);
  const category = groups.find(group => group !== "Gameplay") ?? groups[0] ?? "Custom Content";
  const candidates = (project.latestFiles ?? []).filter(file =>
    file.isAvailable && Number.isSafeInteger(file.id) && file.id > 0 &&
    FORMATS.test(file.fileName ?? "") && verifiedUrl(file.downloadUrl, "image"),
  );
  const file = project.allowModDistribution === false ? null
    : candidates.find(item => item.id === project.mainFileId) ?? candidates[0] ?? null;
  const style = STYLES.find(value => tags.some(tag => tag.toLowerCase() === value.toLowerCase())) ?? "";
  return {
    id: String(project.id), name: project.name || "Untitled resource",
    creator: (project.authors ?? []).map(author => author.name).filter(Boolean).join(", ") || "Unknown creator",
    category, style, summary: project.summary ?? "", description: project.summary ?? "",
    files: (project.latestFiles ?? []).slice(0, 6).map(item => item.displayName || item.fileName).filter(Boolean),
    source: verifiedUrl(project.links?.websiteUrl) || CF_SEARCH,
    image: verifiedUrl(project.logo?.thumbnailUrl ?? project.logo?.url, "image"),
    screenshots: (project.screenshots ?? []).map(item => verifiedUrl(item.url, "image")).filter(Boolean).slice(0, 5),
    packs: null, version: file?.displayName || file?.fileName || "",
    compatibility: file?.gameVersions?.join(", ") ?? "",
    dependencies: Array.isArray(file?.dependencies) ? file.dependencies.filter(dep => dep.relationType === 3 && Number.isSafeInteger(dep.modId) && dep.modId > 0).map(dep => dep.modId) : null,
    file: file ? { id: file.id } : null, sample: false,
  };
}

function matches(item, text, filter) {
  return (!filter.group || item.category === filter.group) &&
    (!filter.creator || item.creator.toLowerCase().includes(filter.creator.toLowerCase())) &&
    (!filter.style || item.style === filter.style) &&
    (!filter.pack || item.packs?.includes(filter.pack)) &&
    (!text || [item.name, item.creator, item.summary, item.category].join(" ").toLowerCase().includes(text));
}

function filtersFrom(url) {
  const value = (key, max) => (url.searchParams.get(key) ?? "").trim().slice(0, max);
  const index = Number(value("page", 5) || 1);
  if (!Number.isInteger(index) || index < 1 || index > Math.floor(10000 / PAGE)) {
    throw new CatalogError("Choose a valid results page.", 400);
  }
  const group = value("category", 30);
  const style = value("style", 20);
  if ((group && !GROUPS.includes(group)) || (style && !STYLES.includes(style))) {
    throw new CatalogError("Choose a valid category or style.", 400);
  }
  return { index, query: value("q", 100), creator: value("creator", 80), group, style, pack: value("pack", 80) };
}

async function catalogSearch(url, env) {
  const filter = filtersFrom(url);
  if (!env.CURSEFORGE_API_KEY) {
    const records = samples.filter(item => matches(item, filter.query.toLowerCase(), filter));
    const start = (filter.index - 1) * PAGE;
    return { mode: "sample", items: records.slice(start, start + PAGE), next: start + PAGE < records.length, total: records.length };
  }
  const params = { gameId: GAME, pageSize: PAGE, index: (filter.index - 1) * PAGE,
    sortField: 2, sortOrder: "desc", searchFilter: filter.query || filter.creator };
  if (filter.group || filter.style) {
    const { data } = await curseforge(env, "/categories", { gameId: GAME });
    const ids = (data ?? []).filter(tag => {
      if (filter.style && tag.name?.toLowerCase() === filter.style.toLowerCase()) return true;
      return filter.group && groupOf(tag.name ?? "") === filter.group;
    }).map(item => item.id).filter(Number.isSafeInteger);
    if (ids.length) params.categoryIds = ids.join(",");
  }
  if (filter.pack) return { mode: "live", items: [], next: false, total: null };
  const result = await curseforge(env, "/mods/search", params);
  const pagination = result.pagination ?? {};
  const filtered = Boolean(filter.group || filter.creator || filter.style);
  return {
    mode: "live",
    items: (result.data ?? []).map(normalize).filter(item => item && matches(item, "", filter)),
    next: params.index + PAGE < Math.min(10000, pagination.totalCount ?? 0),
    total: filtered ? null : pagination.totalCount ?? 0,
  };
}

async function catalogDetail(id, env) {
  const sample = !env.CURSEFORGE_API_KEY && samples.find(item => item.id === id);
  if (sample) return sample;
  if (env.CURSEFORGE_API_KEY && /^[1-9][0-9]{0,9}$/.test(id) && Number(id) <= 4294967295) {
    const { data } = await curseforge(env, "/mods/" + id);
    const item = normalize(data ?? {});
    if (item?.id === id) return item;
  }
  throw new CatalogError("This resource could not be found.", 404);
}
