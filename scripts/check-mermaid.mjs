// Parse every ```mermaid block in the Markdown files named on the command line with the pinned
// mermaid build, in a headless Chromium. A block GitHub would refuse to render fails make check.
// Dependencies live in scripts/mermaid (npm ci there first; make check does).
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(resolve(here, 'mermaid/package.json'));
const { chromium } = require('playwright-core');

const files = process.argv.slice(2);
const blocks = files.flatMap((f) =>
  [...readFileSync(f, 'utf8').matchAll(/```mermaid\n([\s\S]*?)```/g)].map((m, i) => ({ where: `${f} block ${i + 1}`, code: m[1] })));

const browser = await chromium.launch();
const page = await browser.newPage();
await page.addScriptTag({ path: require.resolve('mermaid/dist/mermaid.min.js') });
let bad = 0;
for (const b of blocks) {
  const err = await page.evaluate(async (code) => {
    try { await window.mermaid.parse(code); return null; } catch (e) { return String(e.message || e).split('\n').slice(0, 4).join('\n'); }
  }, b.code);
  if (err) { bad++; console.log(`${b.where}: ${err}`); }
}
await browser.close();
console.log(`mermaid: ${bad} problems in ${blocks.length} blocks`);
process.exit(bad ? 1 : 0);
