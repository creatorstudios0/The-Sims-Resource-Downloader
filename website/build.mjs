import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const root = fileURLToPath(new URL(".", import.meta.url));
const read = (path, encoding = "utf8") => readFile(join(root, path), encoding);
const [html, css, js, art, catalog, worker] = await Promise.all([
  read("index.html"), read("site.css"), read("site.js"),
  readFile(join(root, "assets/catalog-art.jpg")), read("catalog.js"), read("worker.js"),
]);
const directory = join(root, "dist/server");
await mkdir(directory, { recursive: true });
const embedded = Object.entries({ PAGE_HTML: html, PAGE_CSS: css, PAGE_JS: js, ARTWORK: art.toString("base64") })
  .map(([name, value]) => "const " + name + " = " + JSON.stringify(value) + ";").join("\n");
await writeFile(join(directory, "index.js"), [embedded, catalog, worker].join("\n\n"));
try {
  const manifest = join(root, ".openai/hosting.json");
  await readFile(manifest);
  await mkdir(join(root, "dist/.openai"), { recursive: true });
  await copyFile(manifest, join(root, "dist/.openai/hosting.json"));
} catch (error) {
  if (error.code !== "ENOENT") throw error;
}
