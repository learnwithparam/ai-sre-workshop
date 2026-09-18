/**
 * Render the teaching surfaces to PDF, then read the PDFs back.
 *
 *   make book
 *
 * WHY IT CHECKS ITSELF
 *
 * A Chromium print-to-PDF fails in a way no visual review catches: every page
 * looks perfect and the text layer extracts as garbage. The causes are CSS
 * properties that are correct on screen, so nothing about the document looks
 * wrong and nobody rebuilds. Each is reset in the print block of teach.css, and
 * this asserts the resets are still doing their job:
 *
 *   welded      ui-sans-serif or system-ui resolves to SF Pro, which Chromium
 *               embeds as per-word runs with no space glyph
 *   over-split  letter-spacing from about .13em emits one run per character
 *   canaries    catch the rest, including corruptions that are local to one
 *               element and move no whole-document count
 *
 * poppler is a hard dependency. A verification that skips when its tool is
 * missing is not a verification.
 */

import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";

const ROOT = join(import.meta.dirname, "..");
const GENERATED = "artifacts/book.html";
const FRESHNESS = join(ROOT, "scripts/pdf_freshness.json");

/** Margin boxes are what put a page number on the page. Chromium grew them in 131. */
const MARGIN_BOXES_FROM = 131;

const SHARED = ["concepts.html", "teach.html", "teach.css", "scripts/build_book.mjs"];

/** Every PDF this repository ships, and the files each one is built from. The
 *  builder counts as a source: a document and its PDF are both downstream of the
 *  script that writes them, so an edit there with no rebuild leaves the pair
 *  consistent with each other and both behind. */
const PDFS = {
  "ai-sre-book.pdf": { source: GENERATED, head: "AI SRE", sources: SHARED },
  "ai-sre-concepts.pdf": { source: "concepts.html", head: "AI SRE: the concepts", sources: ["concepts.html", "teach.css", "scripts/build_book.mjs"] },
  "ai-sre-run-sheet.pdf": { source: "teach.html", head: "AI SRE run sheet", sources: ["teach.html", "teach.css", "scripts/build_book.mjs"] },
};

const read = (file) => readFileSync(join(ROOT, file), "utf8");
const sha256 = (file) => createHash("sha256").update(readFileSync(join(ROOT, file))).digest("hex").slice(0, 16);

/** The body of a teaching surface, without its shell. */
function body(file) {
  const text = read(file);
  const open = text.indexOf('<main class="doc">');
  const close = text.lastIndexOf("</main>");
  if (open === -1 || close === -1) throw new Error(`${file} has no <main class="doc"> to bind`);
  return text.slice(open + '<main class="doc">'.length, close);
}

/** A block of a surface, and the surface without it. */
function lift(html, open, close) {
  const from = html.indexOf(open);
  if (from === -1) throw new Error(`no ${open} to lift`);
  const to = html.indexOf(close, from) + close.length;
  return [html.slice(from, to), html.slice(0, from) + html.slice(to)];
}

/**
 * Phrases that have to survive the round trip into the text layer.
 *
 * Read off the document rather than written down, because a hand-kept list
 * checks the chapters somebody remembered. A phrase is only usable if it carries
 * no inline markup: an <strong> in the middle splits the run, and a canary that
 * straddles one tests the markup instead of the font.
 */
function canaries(html) {
  const found = [];
  for (const match of html.matchAll(/<p(?: class="(?:deck|lede)")?>([^<]{80,})/g)) {
    const words = match[1].replace(/\s+/g, " ").trim().split(" ").slice(0, 9).join(" ");
    if (words.length > 40) found.push(words);
  }
  return found;
}

function compose() {
  const [spineContents, withoutContents] = lift(body("concepts.html"), '<nav class="contents"', "</nav>");
  const [, spine] = lift(withoutContents, '<header class="cover">', "</header>");
  const [sheetContents, withoutSheetContents] = lift(body("teach.html"), '<nav class="contents"', "</nav>");
  const [, sheetBody] = lift(withoutSheetContents, '<header class="cover">', "</header>");
  const sheet = sheetBody
    // The bound book is written into artifacts/, one directory down, and inside it
    // the spine is a few pages back rather than another file.
    .replace(/src="evidence\//g, 'src="../evidence/')
    .replace(/href="concepts\.html#/g, 'href="#');

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AI SRE</title>
<link rel="stylesheet" href="../teach.css">
<style>
/* Running head. Chromium has supported @page margin boxes since ${MARGIN_BOXES_FROM}, and
   the build checks the version before rendering, so a missing head fails rather
   than vanishes. */
@page { @top-left { content: "AI SRE"; font-family: Helvetica, Arial, sans-serif; font-size: 8.5pt; color: #948D80; } }
@page :first { @top-left { content: ""; } }
</style>
</head>
<body>
<main class="doc">

<header class="cover">
<p class="series">learnwithparam</p>
<h1>AI SRE</h1>
<p class="deck">The concepts, and the run sheet for the day that teaches them. Part one explains each idea once. Part two is what a facilitator reads standing up, and it cites part one by name.</p>
<dl class="facts">
<dt>Built by</dt><dd><code>make book</code>, from the same pages the browser serves</dd>
<dt>Checked by</dt><dd>its own text layer, read back with <code>pdftotext</code> after every build</dd>
</dl>
</header>

${spineContents.replace("<h2>Contents</h2>", "<h2>Part one, the concepts</h2>")}

${sheetContents.replace("<h2>Contents</h2>", "<h2>Part two, the day</h2>")}

${spine}

${sheet}

</main>
</body>
</html>
`;
}

function extract(path) {
  return execFileSync("pdftotext", ["-raw", path, "-"], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 }).replace(/\s+/g, " ");
}

export function textLayerProblems(raw, expected) {
  const problems = [];
  const missing = expected.filter((phrase) => !raw.includes(phrase));
  for (const phrase of missing.slice(0, 3)) problems.push(`missing from the text layer: "${phrase}"`);
  if (missing.length > 3) problems.push(`and ${missing.length - 3} more phrases missing`);

  // A slug and a URL are legitimately long and always carry a separator. Welded
  // prose never does.
  const welded = raw.split(" ").filter((w) => w.length > 30 && /^[A-Za-z]+$/.test(w));
  if (welded.length) {
    problems.push(
      `${welded.length} run-together token(s), so the text layer lost its spaces. First: "${welded[0].slice(0, 48)}". ` +
        "Something put ui-sans-serif or system-ui back into a printed font stack."
    );
  }
  // Five or more single letters separated by spaces is not prose.
  const split = raw.match(/\b(?:[A-Za-z] ){4,}[A-Za-z]\b/g) ?? [];
  if (split.length) {
    problems.push(
      `${split.length} over-split run(s), so a tracked label emitted one run per character. First: "${split[0].slice(0, 48)}". ` +
        "Reset letter-spacing in the print block of teach.css."
    );
  }
  return problems;
}

const { chromium } = await import(pathToFileURL(join(ROOT, "e2e/node_modules/playwright/index.mjs")).href);
const browser = await chromium.launch();
const version = Number(browser.version().split(".")[0]);
if (Number.isNaN(version) || version < MARGIN_BOXES_FROM) {
  await browser.close();
  throw new Error(
    `Chromium ${browser.version()} predates @page margin boxes (${MARGIN_BOXES_FROM}), so the book would print with no page numbers and nothing would say so. Run: cd e2e && npx playwright install chromium`
  );
}

mkdirSync(join(ROOT, dirname(GENERATED)), { recursive: true });
writeFileSync(join(ROOT, GENERATED), compose());

const page = await browser.newPage();
const problems = [];
for (const [out, job] of Object.entries(PDFS)) {
  await page.goto(pathToFileURL(join(ROOT, job.source)).href, { waitUntil: "networkidle" });
  if (job.source !== GENERATED) {
    await page.addStyleTag({
      content:
        `@page { @top-left { content: ${JSON.stringify(job.head)}; font-family: Helvetica, Arial, sans-serif; font-size: 8.5pt; color: #948D80; } }\n` +
        '@page :first { @top-left { content: ""; } }',
    });
  }
  // The inset lives in @page in teach.css and nowhere else. A CSS @page margin
  // overrides whatever is passed here, so passing one too would only hide which
  // of them is live.
  // A screenshot that did not load is a page that teaches nothing, and it prints
  // as white space rather than as an error. The bound book is written one
  // directory down from the pages, so this is exactly where a path breaks.
  // Every screenshot on these pages is lazy, so in a viewport none of them below
  // the fold has loaded yet. Printing loads them; this has to as well, or it
  // reports every figure as broken and gets switched off.
  const broken = await page.evaluate(async () => {
    const images = Array.from(document.images);
    for (const img of images) img.loading = "eager";
    await Promise.all(
      images.filter((img) => !img.complete).map((img) => new Promise((done) => { img.onload = done; img.onerror = done; }))
    );
    return images.filter((img) => img.naturalWidth === 0).map((img) => img.getAttribute("src"));
  });
  if (broken.length) problems.push(`${out}: ${broken.length} image(s) did not load, first: ${broken[0]}`);

  const pdf = await page.pdf({ format: "A4", printBackground: true, margin: { top: "0", bottom: "0", left: "0", right: "0" } });
  writeFileSync(join(ROOT, out), pdf);

  const raw = extract(join(ROOT, out));
  const found = textLayerProblems(raw, canaries(read(job.source)));
  if (found.length) problems.push(...found.map((line) => `${out}: ${line}`));
  console.log(`${out.padEnd(26)} ${(pdf.length / 1024).toFixed(0).padStart(5)} KB  ${raw.split(" ").length} words extract`);
}
await browser.close();

if (problems.length) {
  console.error("\nmake book  FAIL  the PDFs render correctly and do not extract");
  for (const line of problems) console.error(`    ${line}`);
  console.error("\n    Compare: pdftotext -raw <file> - | less");
  process.exit(1);
}

// Content hashes, never modification times: a fresh checkout gives every file the
// same timestamp in an arbitrary order, so an mtime gate could never pass in CI.
const freshness = {};
for (const [out, job] of Object.entries(PDFS)) {
  freshness[out] = Object.fromEntries(job.sources.filter((f) => existsSync(join(ROOT, f))).map((f) => [f, sha256(f)]));
}
writeFileSync(FRESHNESS, `${JSON.stringify(freshness, null, 2)}\n`);
console.log(`\nmake book  ok  ${Object.keys(PDFS).length} PDFs, every canary present, no welded and no over-split runs`);
