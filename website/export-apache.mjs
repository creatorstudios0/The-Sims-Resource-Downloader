import { copyFile, lstat, mkdir, mkdtemp, readFile, rename, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, join } from "node:path";
import { fileURLToPath } from "node:url";
import worker from "./dist/server/index.js";

const dest = process.argv[2];
if (!dest || !isAbsolute(dest) || process.argv.length !== 3) {
  throw new Error("Usage: node export-apache.mjs <absolute new Apache site directory>");
}
const read = path => readFile(new URL(path, import.meta.url), "utf8");
const [html, css, js] = await Promise.all([read("index.html"), read("site.css"), read("site.js")]);
try {
  await lstat(dest);
  throw new Error("The destination already exists. Choose a new folder to preserve your edits.");
} catch (error) {
  if (error.code !== "ENOENT") throw error;
}
const items = [];
for (let page = 1; ; page++) {
  const response = await worker.fetch(new Request("https://sample.invalid/api/catalog?page=" + page), {});
  if (!response.ok) throw new Error("The sample catalog could not be exported.");
  const batch = await response.json();
  items.push(...batch.items);
  if (!batch.next) break;
}
const stage = await mkdtemp(join(dirname(dest), ".sims4-export-"));
const assets = join(stage, "assets");
await mkdir(assets);

await Promise.all([
  writeFile(join(stage, "index.html"), html.replace('data-mode="sample"', 'data-mode="sample" data-host="apache"')
    .replaceAll('"/assets/', '"./assets/').replaceAll('href="/#', 'href="./#').replaceAll('href="/"', 'href="./"')),
  writeFile(join(stage, "catalog.json"), JSON.stringify(items, null, 2) + "\n"),
  writeFile(join(assets, "site.css"), css.replaceAll('url("/assets/', 'url("./')),
  writeFile(join(assets, "site.js"), js),
  copyFile(fileURLToPath(new URL("assets/catalog-art.jpg", import.meta.url)), join(assets, "catalog-art.jpg")),
  writeFile(join(stage, "EDITING.txt"), [
    "Sims 4 Mod Library · local Apache edition",
    "",
    "Open the folder through Apache, for example http://localhost/sims4-mod-library/.",
    "Edit index.html for page copy and layout, assets/site.css for styling,",
    "assets/site.js for behavior, and catalog.json for sample listings.",
    "Edit this copy directly; publishing the hosted site is a separate step.",
    "This copy uses the included fictional listings and has no live provider or download actions.",
    "",
  ].join("\n")),
]);
await rename(stage, dest);
console.log("Editable Apache site written to " + dest);
