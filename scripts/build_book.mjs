/**
 * Render the workbook and the guide to PDF, then read the PDFs back.
 *
 *   make book
 *
 * WHY IT CHECKS ITSELF
 *
 * A Chromium print-to-PDF fails in a way no visual review catches: every page
 * looks perfect and the text layer extracts as garbage, or a command is cut off
 * and nobody notices. The causes are CSS properties that are correct on screen,
 * so nothing looks wrong and nobody rebuilds. Each is reset in the print block of
 * design/book.css, and this asserts the resets are still doing their job:
 *
 *   welded      a system font that Chromium embeds as per-word runs with no space glyph
 *   over-split  letter-spacing from about .13em emits one run per character
 *   clipped     a command that runs off the page is cut in the text layer too
 *   fonts       Inter and Inconsolata are embedded, not quietly replaced
 *   empty       a page that is mostly white, outside the cover, the contents and
 *               the last page of each document
 *   canaries    catch the rest, including corruptions local to one element
 *
 * poppler is a hard dependency. A verification that skips when its tool is
 * missing is not a verification.
 */

import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const ROOT = join(import.meta.dirname, "..");
const FRESHNESS = join(ROOT, "scripts/pdf_freshness.json");

/** Margin boxes are what put a page number on the page. Chromium grew them in 131. */
const MARGIN_BOXES_FROM = 131;

/** A page less full than this is a page of white space. */
const MIN_FILL = 0.55;
/** The A4 page in points, and the band the @page margins take at the top and bottom (16 mm and 18 mm). */
const PAGE_H_PT = 841.89;
const TOP_PT = (16 / 25.4) * 72;
const BOTTOM_PT = (18 / 25.4) * 72;

const FONTS = readdirSync(join(ROOT, "design/fonts"))
  .filter((f) => f.endsWith(".woff2"))
  .map((f) => `design/fonts/${f}`);
const SHARED = ["design/book.css", "design/tokens.css", ...FONTS, "scripts/build_book.mjs", "scripts/diagram.mjs"];

/** Every PDF this repository ships, and the files each one is built from. The
 *  builder counts as a source: a document and its PDF are both downstream of the
 *  script that writes them, so an edit there with no rebuild leaves the pair
 *  consistent with each other and both behind. */
const PDFS = {
  "ai-sre-workbook.pdf": { source: "workbook.html", head: "AI SRE workbook", sources: ["workbook.html", ...SHARED] },
  "ai-sre-guide.pdf": { source: "guide.html", head: "AI SRE facilitator guide", sources: ["guide.html", ...SHARED] },
};

const read = (file) => readFileSync(join(ROOT, file), "utf8");
const sha256 = (file) => createHash("sha256").update(readFileSync(join(ROOT, file))).digest("hex").slice(0, 16);

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
    if (words.length > 40 && !words.includes("&")) found.push(words);
  }
  return found;
}

const decode = (s) => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");
const bare = (s) => s.replace(/\s+/g, "");

/** Every line of every command block on a page. */
function commands(html) {
  const lines = [];
  for (const block of html.matchAll(/<pre[^>]*>([\s\S]*?)<\/pre>/g)) {
    for (const line of decode(block[1].replace(/<[^>]+>/g, "")).split("\n")) if (bare(line)) lines.push(line.trim());
  }
  return lines;
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
        "Reset letter-spacing in the print block of design/book.css."
    );
  }
  return problems;
}

/** A command the PDF does not carry whole. Whitespace is ignored: a long command wraps, and the wrap is a break, not a loss. */
export function clippedCommands(raw, lines) {
  const flat = bare(raw);
  return lines.filter((line) => !flat.includes(bare(line)));
}

/** Where each page's ink ends, as a share of the space between the margins. Read from a raster, so a picture counts. */
function fills(path) {
  const dpi = 24;
  const dir = execFileSync("mktemp", ["-d"], { encoding: "utf8" }).trim();
  execFileSync("pdftoppm", ["-gray", "-r", String(dpi), path, join(dir, "p")]);
  const pages = readdirSync(dir).filter((f) => f.endsWith(".pgm")).sort();
  const top = Math.floor((TOP_PT * dpi) / 72);
  const bottom = Math.floor(((PAGE_H_PT - BOTTOM_PT) * dpi) / 72);
  return pages.map((name) => {
    const buf = readFileSync(join(dir, name));
    // P5, then "width height", then "255", then the pixels: three newline-terminated header lines.
    let at = 0;
    for (let seen = 0; seen < 3; at++) if (buf[at] === 10) seen++;
    const [width, height] = buf.toString("latin1", 0, at).split("\n")[1].split(" ").map(Number);
    let last = top;
    for (let y = top; y < Math.min(bottom, height); y++) {
      for (let x = 0; x < width; x++) {
        if (buf[at + y * width + x] < 250) {
          last = y;
          break;
        }
      }
    }
    return (last - top) / (bottom - top);
  });
}

function pageText(path, n) {
  return execFileSync("pdftotext", ["-f", String(n), "-l", String(n), "-raw", path, "-"], { encoding: "utf8" });
}

/** Pages that are allowed to be short: the cover, the contents, the page before a forced break, the last one. */
function emptyPages(path, fill, opens) {
  const short = [];
  fill.forEach((share, i) => {
    const n = i + 1;
    if (share >= MIN_FILL || n === 1 || n === fill.length) return;
    if (/^\s*Contents\b/.test(pageText(path, n))) return;
    const next = bare(pageText(path, n + 1)).slice(0, 240);
    if (opens.some((mark) => next.includes(mark))) return;
    short.push(`page ${n} is ${Math.round(share * 100)}% full`);
  });
  return short;
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

const page = await browser.newPage();
const problems = [];
for (const [out, job] of Object.entries(PDFS)) {
  await page.goto(pathToFileURL(join(ROOT, job.source)).href, { waitUntil: "networkidle" });
  await page.addStyleTag({
    content:
      `@page { @top-left { content: ${JSON.stringify(job.head)}; font-family: Inter, Helvetica, Arial, sans-serif; font-size: 8.5pt; color: #606060; } }\n` +
      '@page :first { @top-left { content: ""; } }',
  });
  // The inset lives in @page in design/book.css and nowhere else. A CSS @page margin
  // overrides whatever is passed here, so passing one too would only hide which
  // of them is live.
  // A screenshot that did not load is a page that teaches nothing, and it prints
  // as white space rather than as an error. Every screenshot is lazy, so in a
  // viewport none of them below the fold has loaded yet. Printing loads them; this
  // has to as well, or it reports every figure as broken and gets switched off.
  const broken = await page.evaluate(async () => {
    const images = Array.from(document.images);
    for (const img of images) img.loading = "eager";
    await Promise.all(
      images.filter((img) => !img.complete).map((img) => new Promise((done) => { img.onload = done; img.onerror = done; }))
    );
    await document.fonts.ready;
    return images.filter((img) => img.naturalWidth === 0).map((img) => img.getAttribute("src"));
  });
  if (broken.length) problems.push(`${out}: ${broken.length} image(s) did not load, first: ${broken[0]}`);
  const opens = (await page.$$eval(".opens", (els) => els.map((el) => el.textContent ?? ""))).map((t) => bare(t).slice(0, 24)).filter(Boolean);

  const pdf = await page.pdf({ format: "A4", printBackground: true, margin: { top: "0", bottom: "0", left: "0", right: "0" } });
  writeFileSync(join(ROOT, out), pdf);
  const path = join(ROOT, out);

  const raw = extract(path);
  const html = read(job.source);
  problems.push(...textLayerProblems(raw, canaries(html)).map((line) => `${out}: ${line}`));
  const cut = clippedCommands(raw, commands(html));
  if (cut.length) problems.push(`${out}: ${cut.length} command line(s) are not whole in the text layer. First: "${cut[0].slice(0, 70)}"`);
  const embedded = execFileSync("pdffonts", [path], { encoding: "utf8" });
  for (const face of ["Inter", "Inconsolata"]) {
    if (!embedded.includes(face)) problems.push(`${out}: ${face} is not embedded, so the page fell back to a system font`);
  }
  const fill = fills(path);
  problems.push(...emptyPages(path, fill, opens).map((line) => `${out}: ${line}, under ${MIN_FILL * 100}%`));
  console.log(`${out.padEnd(24)} ${(pdf.length / 1024).toFixed(0).padStart(5)} KB  ${fill.length} pages  ${raw.split(" ").length} words extract`);
}
await browser.close();

if (problems.length) {
  console.error("\nmake book  FAIL  the PDFs render and do not read back");
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
console.log(`\nmake book  ok  ${Object.keys(PDFS).length} PDFs, every canary and command whole, fonts embedded, no page mostly empty`);
