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

test("live catalog makes a partial last request within the provider limit", async t => {
  const lastFiles = [9997, 9998, 9999, 10000].map(id => ({ id, gameId: 781, name: "Resource " + id }));
  const search = t.mock.method(globalThis, "fetch", async url => {
    assert.equal(url.pathname, "/v1/mods/search");
    const index = Number(url.searchParams.get("index"));
    const size = Number(url.searchParams.get("pageSize"));
    assert.ok(index + size <= 10000);
    return Response.json({ data: index === 9996 ? lastFiles : [], pagination: { totalCount: 12000 } });
  });
  const env = { CURSEFORGE_API_KEY: "private-key" };
  const penultimate = await req("/api/catalog?page=1666", env);
  assert.equal(penultimate.status, 200);
  assert.equal((await penultimate.json()).next, true);
  const last = await req("/api/catalog?page=1667", env);
  assert.equal(last.status, 200);
  const finalPage = await last.json();
  assert.deepEqual(finalPage.items.map(item => Number(item.id)), [9997, 9998, 9999, 10000]);
  assert.equal(finalPage.next, false);
  const windows = search.mock.calls.map(({ arguments: [url] }) =>
    [url.searchParams.get("index"), url.searchParams.get("pageSize")]);
  assert.deepEqual(windows, [["9990", "6"], ["9996", "4"]]);
  assert.equal((await req("/api/catalog?page=1668", env)).status, 400);
  assert.equal(search.mock.callCount(), 2);
});
