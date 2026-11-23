const HEADERS = {
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "Content-Security-Policy": "default-src 'self'; img-src 'self' https://*.forgecdn.net https://forgecdn.net; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
};

function reply(body, contentType, status = 200, cache = "no-store") {
  return new Response(body, { status, headers: { ...HEADERS, "Content-Type": contentType, "Cache-Control": cache } });
}

function json(value, status = 200) {
  return reply(JSON.stringify(value), "application/json; charset=utf-8", status);
}

function html(showDetail, mode) {
  return PAGE_HTML.replace('data-view="browse"', showDetail ? 'data-view="detail"' : 'data-view="browse"')
    .replace('data-mode="sample"', mode === "live" ? 'data-mode="live"' : 'data-mode="sample"');
}

export default {
  async fetch(request, env = {}) {
    const url = new URL(request.url);
    if (request.method !== "GET") return json({ error: "Method not allowed." }, 405);
    try {
      if (url.pathname === "/api/catalog") return json(await catalogSearch(url, env));
      const item = url.pathname.match(/^\/api\/mods\/([a-z0-9-]{1,70})$/);
      if (item) return json(await catalogDetail(item[1], env));
      if (url.pathname === "/") return reply(html(false, env.CURSEFORGE_API_KEY ? "live" : "sample"), "text/html; charset=utf-8");
      if (/^\/mods\/[a-z0-9-]{1,70}$/.test(url.pathname)) return reply(html(true, env.CURSEFORGE_API_KEY ? "live" : "sample"), "text/html; charset=utf-8");
      if (url.pathname === "/assets/site.css") return reply(PAGE_CSS, "text/css; charset=utf-8");
      if (url.pathname === "/assets/site.js") return reply(PAGE_JS, "text/javascript; charset=utf-8");
      if (url.pathname === "/assets/catalog-art.jpg") {
        return reply(Uint8Array.from(atob(ARTWORK), character => character.charCodeAt(0)), "image/jpeg", 200, "public, max-age=3600");
      }
      return json({ error: "Page not found." }, 404);
    } catch (error) {
      if (error instanceof CatalogError) return json({ error: error.message }, error.status);
      return json({ error: "The catalog could not be loaded. Try again shortly." }, 502);
    }
  },
};
