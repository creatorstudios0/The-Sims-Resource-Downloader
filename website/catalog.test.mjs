import assert from "node:assert/strict";
import test from "node:test";
import worker from "./dist/server/index.js";

const req = (path, env) => worker.fetch(new Request("https://catalog.example" + path), env);

test("sample catalog pages, filters, search and artwork", async () => {
  const first = await (await req("/api/catalog")).json();
  assert.equal(first.mode, "sample");
  assert.equal(first.total, 9);
  assert.equal(first.items.length, 6);
  assert.equal(first.next, true);
  const second = await (await req("/api/catalog?page=2")).json();
  assert.equal(second.items.length, 3);
  assert.equal(second.next, false);
  const match = await (await req("/api/catalog?q=wave&creator=Marigold&category=Hair&style=Alpha")).json();
  assert.deepEqual(match.items.map(item => item.id), ["soft-wave-hair"]);
  const packs = await (await req("/api/catalog?pack=Cottage%20Living")).json();
  assert.deepEqual(packs.items.map(item => item.id), ["ivybrook-cottage"]);
  assert.equal((await req("/assets/catalog-art.jpg")).headers.get("content-type"), "image/jpeg");
});

test("sample details never hand off a file, invalid queries return an error", async () => {
  const detail = await (await req("/api/mods/ivybrook-cottage")).json();
  assert.equal(detail.sample, true);
  assert.equal(detail.file, null);
  assert.equal((await req("/api/mods/404")).status, 404);
  assert.equal((await req("/api/catalog?page=0")).status, 400);
  assert.match(await (await req("/mods/ivybrook-cottage")).text(), /data-view="detail"/);
});

test("live provider keeps API keys server-side and respects distribution", async t => {
  const allowed = { id: 42, gameId: 781, name: "Example", categories: [{ name: "Hair" }],
    latestFiles: [{ id: 11, fileName: "hair.package", isAvailable: true, downloadUrl: "https://mediafilez.forgecdn.net/file" }],
    links: { websiteUrl: "https://www.curseforge.com/sims4/example" } };
  const unavailable = { ...allowed, id: 43, allowModDistribution: false };
  const unsafe = { ...allowed, id: 44, latestFiles: [{ ...allowed.latestFiles[0], downloadUrl: "https://forgecdn.net.example.com/file" }] };
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url.host, "api.curseforge.com");
    assert.equal(options.headers["x-api-key"], "private-key");
    assert.equal(options.redirect, "error");
    if (url.pathname === "/v1/mods/search") {
      assert.equal(url.searchParams.get("gameId"), "781");
      return Response.json({ data: [allowed, unavailable, unsafe], pagination: { totalCount: 3 } });
    }
    return Response.json({ data: allowed });
  });
  const env = { CURSEFORGE_API_KEY: "private-key" };
  const raw = await (await req("/api/catalog", env)).text();
  assert.doesNotMatch(raw, /private-key|mediafilez/);
  const live = JSON.parse(raw);
  assert.equal(live.mode, "live");
  assert.deepEqual(live.items.map(item => item.file), [{ id: 11 }, null, null]);
  assert.equal((await (await req("/api/mods/42", env)).json()).file.id, 11);
});
