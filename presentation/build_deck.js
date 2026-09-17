const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const DIR = __dirname;
const SIH = path.join(DIR, "assets", "sih_logo.png");
const BRAIN = path.join(DIR, "assets", "brain_only.png");

// ---- palette (template chrome + project accents) -------------------------
const NAVY = "1F4E79";   // template heading blue
const BLUE = "0070C0";   // template footer bar
const ORANGE = "F26522"; // SIH mark orange
const GREEN = "2E7D32";  // SIH mark green
const INK = "1A1A1A";
const GREY = "55606E";
const TINT = "EEF4FB";
const TINT2 = "FDF1EA";
const LINE = "C8D6E5";
const PURPLE = "7C6BA8";

const W = 13.333, H = 7.5;
const M = 0.5;                 // side margin
const CONTENT_TOP = 1.42;
const FOOT_Y = 6.94;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "APIx";
pres.title = "SIH 2026 - APIx Real-time Airfare Price Index";

const TEAM = "<Team Name>";

// ---- template chrome ------------------------------------------------------
function chrome(slide, pageNo, title) {
  slide.background = { color: "FFFFFF" };
  slide.addImage({ path: SIH, x: 10.86, y: 0.12, w: 2.05, h: 0.968 });
  // team-name oval (template element, top-left)
  slide.addShape(pres.ShapeType.ellipse, {
    x: 0.36, y: 0.20, w: 1.42, h: 0.80,
    fill: { color: "FFFFFF" }, line: { color: PURPLE, width: 1.25 },
  });
  slide.addText(TEAM, {
    x: 0.36, y: 0.20, w: 1.42, h: 0.80, align: "center", valign: "middle",
    fontFace: "Calibri", fontSize: 10, color: GREY, isTextBox: true, margin: 0,
  });
  slide.addText(title, {
    x: 1.95, y: 0.26, w: 8.75, h: 0.72, align: "center", valign: "middle",
    fontFace: "Cambria", fontSize: 30, bold: true, color: INK,
    isTextBox: true, margin: 0,
  });
  // footer band (part of the SIH template)
  slide.addShape(pres.ShapeType.rect, {
    x: 0, y: FOOT_Y, w: W, h: H - FOOT_Y, fill: { color: BLUE }, line: { color: BLUE },
  });
  slide.addText("@SIH Idea submission- Template", {
    x: 0, y: FOOT_Y, w: W, h: H - FOOT_Y, align: "center", valign: "middle",
    fontFace: "Calibri", fontSize: 11, color: "FFFFFF", isTextBox: true, margin: 0,
  });
  slide.addText(String(pageNo), {
    x: W - 1.1, y: FOOT_Y, w: 0.7, h: H - FOOT_Y, align: "right", valign: "middle",
    fontFace: "Calibri", fontSize: 11, bold: true, color: "FFFFFF", isTextBox: true, margin: 0,
  });
}

// mandated template pointer line (must not be reworded)
function pointer(slide, text, y, w) {
  slide.addText(text, {
    x: M, y, w: w || (W - 2 * M), h: 0.34,
    fontFace: "Calibri", fontSize: 16, bold: true, color: NAVY,
    isTextBox: true, margin: 0, valign: "middle",
  });
}

function card(slide, o) {
  slide.addShape(pres.ShapeType.roundRect, {
    x: o.x, y: o.y, w: o.w, h: o.h, rectRadius: 0.06,
    fill: { color: o.fill || TINT }, line: { color: o.line || LINE, width: 0.75 },
  });
}

function chip(slide, text, x, y, w, color) {
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h: 0.32, rectRadius: 0.14,
    fill: { color: "FFFFFF" }, line: { color: color, width: 1 },
  });
  slide.addText(text, {
    x, y, w, h: 0.32, align: "center", valign: "middle",
    fontFace: "Calibri", fontSize: 10, bold: true, color: color,
    isTextBox: true, margin: 0,
  });
}

function badge(slide, label, x, y, d, color) {
  slide.addShape(pres.ShapeType.ellipse, {
    x, y, w: d, h: d, fill: { color }, line: { color },
  });
  slide.addText(label, {
    x, y, w: d, h: d, align: "center", valign: "middle",
    fontFace: "Calibri", fontSize: 11, bold: true, color: "FFFFFF",
    isTextBox: true, margin: 0,
  });
}

function bullets(slide, items, o) {
  slide.addText(items.map((t, i) => ({
    text: t,
    options: { bullet: { code: "2022" }, breakLine: i !== items.length - 1 },
  })), {
    x: o.x, y: o.y, w: o.w, h: o.h,
    fontFace: "Calibri", fontSize: o.fs || 11, color: o.color || INK,
    lineSpacingMultiple: 0.95, paraSpaceAfter: o.gap === undefined ? 4 : o.gap,
    isTextBox: true, margin: 0, valign: "top",
  });
}

/* ==========================================================================
   SLIDE 1 — TITLE PAGE
   ========================================================================== */
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  s.addImage({ path: SIH, x: 10.86, y: 0.12, w: 2.05, h: 0.968 });
  s.addText("SMART INDIA HACKATHON 2026", {
    x: 0.6, y: 0.22, w: 10.1, h: 0.62, align: "center", valign: "middle",
    fontFace: "Cambria", fontSize: 32, bold: true, color: NAVY,
    isTextBox: true, margin: 0,
  });
  s.addText("TITLE PAGE", {
    x: 0.6, y: 0.92, w: 10.1, h: 0.5, align: "center", valign: "middle",
    fontFace: "Cambria", fontSize: 24, bold: true, color: INK,
    isTextBox: true, margin: 0,
  });

  s.addImage({ path: BRAIN, x: 9.88, y: 1.40, w: 1.90, h: 2.26 });

  const rows = [
    [1.58, "Problem Statement ID \u2013", "<fill from SIH portal>", true],
    [2.14, "Problem Statement Title-", "Real-time Airfare Price Index for the CPI Transport & Communication sub-group", false],
    [2.88, "Theme-", "<fill from SIH portal>", true],
    [3.44, "PS Category-", "Software", false],
    [4.00, "Team ID-", "<fill from SIH portal>", true],
    [4.56, "Team Name (Registered on portal)-", "<fill from SIH portal>", true],
  ];
  rows.forEach(([y, k, v, ph]) => {
    s.addShape(pres.ShapeType.ellipse, { x: M + 0.02, y: y + 0.10, w: 0.09, h: 0.09, fill: { color: ORANGE }, line: { color: ORANGE } });
    s.addText([
      { text: k + "  ", options: { bold: true, color: INK } },
      { text: v, options: { bold: false, color: ph ? GREY : NAVY, italic: !!ph } },
    ], {
      x: M + 0.24, y, w: 7.45, h: 0.62,
      fontFace: "Calibri", fontSize: 13, isTextBox: true, margin: 0, valign: "top",
      lineSpacingMultiple: 0.95,
    });
  });

  // one-line summary of the pipeline, bottom left
  card(s, { x: M, y: 5.30, w: 7.30, h: 1.38, fill: TINT2, line: "F0C9B2" });
  s.addText("WHAT THE PROTOTYPE ALREADY DOES, EVERY NIGHT", {
    x: M + 0.20, y: 5.42, w: 6.9, h: 0.24,
    fontFace: "Calibri", fontSize: 9, bold: true, color: ORANGE, charSpacing: 1, isTextBox: true, margin: 0,
  });
  const flow = ["Ask robots.txt", "Collect", "Normalise", "Geometric mean", "Chain", "Publish"];
  const fw = (7.30 - 0.40 - 5 * 0.16) / 6;
  flow.forEach((t, i) => {
    const x = M + 0.20 + i * (fw + 0.16);
    s.addShape(pres.ShapeType.roundRect, {
      x, y: 5.70, w: fw, h: 0.34, rectRadius: 0.08,
      fill: { color: "FFFFFF" }, line: { color: "F0C9B2", width: 0.75 },
    });
    s.addText(t, {
      x, y: 5.70, w: fw, h: 0.34, align: "center", valign: "middle",
      fontFace: "Calibri", fontSize: 9.5, bold: true, color: NAVY, isTextBox: true, margin: 0,
    });
    if (i < flow.length - 1) {
      s.addShape(pres.ShapeType.rightArrow, {
        x: x + fw + 0.03, y: 5.81, w: 0.10, h: 0.12,
        fill: { color: "E0B79E" }, line: { color: "E0B79E" },
      });
    }
  });
  s.addText("A block, a 403 or a CAPTCHA is recorded as non-response and imputed \u2014 never evaded. Every point published with its coverage, imputation share and quality flag.", {
    x: M + 0.20, y: 6.14, w: 6.9, h: 0.44,
    fontFace: "Calibri", fontSize: 9.5, color: GREY, isTextBox: true, margin: 0, lineSpacingMultiple: 0.92,
  });

  card(s, { x: 8.83, y: 3.94, w: 4.00, h: 2.74, fill: TINT });
  s.addText("APIx", {
    x: 9.05, y: 4.08, w: 3.6, h: 0.50,
    fontFace: "Cambria", fontSize: 28, bold: true, color: NAVY, isTextBox: true, margin: 0,
  });
  s.addText("A compliant, daily-frequency airfare price index \u2014 collected only where robots.txt permits, chained from geometric-mean cell prices, and published with its own coverage and quality on every point.", {
    x: 9.05, y: 4.62, w: 3.6, h: 1.10,
    fontFace: "Calibri", fontSize: 10.5, color: GREY, isTextBox: true, margin: 0, lineSpacingMultiple: 0.98,
  });
  const mini = [["975", "basket cells"], ["100.0", "base 01-Apr-26"], ["74", "tests passing"]];
  mini.forEach(([n, l], i) => {
    const x = 9.05 + i * 1.22;
    s.addText(n, { x, y: 5.82, w: 1.20, h: 0.34, fontFace: "Cambria", fontSize: 18, bold: true, color: ORANGE, isTextBox: true, margin: 0 });
    s.addText(l, { x, y: 6.16, w: 1.20, h: 0.28, fontFace: "Calibri", fontSize: 8.5, color: GREY, isTextBox: true, margin: 0 });
  });

  s.addNotes("Title slide. Problem Statement ID, Theme, Team ID and Team Name must be copied from the SIH portal registration before upload.");
}

/* ==========================================================================
   SLIDE 2 — IDEA TITLE
   ========================================================================== */
{
  const s = pres.addSlide();
  chrome(s, 2, "IDEA TITLE");
  s.addText("APIx — Real-time Airfare Price Index", {
    x: 1.95, y: 0.94, w: 8.75, h: 0.34, align: "center",
    fontFace: "Calibri", fontSize: 13, italic: true, color: GREY, isTextBox: true, margin: 0,
  });
  pointer(s, "Proposed Solution (Describe your Idea/Solution/Prototype)", CONTENT_TOP);

  const TOP = 1.86, CH = 4.94, LW = 9.05;

  // --- left: three mandated sub-heads
  const blocks = [
    {
      h: "Detailed explanation of the proposed solution", c: NAVY, y: TOP, hh: 1.74,
      items: [
        "Collect public domestic fares daily from airline and OTA sites — only where robots.txt permits — rendering JS pages in a real Chromium browser at a 5-second crawl delay.",
        "Normalise every quote to the all-in fare a household pays: base + GST + UDF/PSF/ASF + mandatory surcharges. Optional seats, bags and meals are excluded.",
        "The item is a cell = source × route × carrier × advance-purchase window × cabin — a basket of 975 cells (15 city pairs × 6 carriers × 5 booking windows × Economy).",
        "Cells collapse to one geometric-mean price a day and chain into a weighted index anchored at 100.0 on 01-Apr-2026, published as daily / weekly / monthly series with a JSON API.",
      ],
    },
    {
      h: "How it addresses the problem", c: GREEN, y: TOP + 1.84, hh: 1.24,
      items: [
        "CPI air-fare collection is monthly and manual, while a fare can change several times a day — APIx makes that item observable daily, automatically.",
        "Every published point carries coverage, imputation share and a quality flag, so a reader sees how much of the basket was really observed.",
        "The raw quote archive is append-only, so the whole series is recomputable and independently replicable.",
      ],
    },
    {
      h: "Innovation and uniqueness of the solution", c: ORANGE, y: TOP + 3.18, hh: 1.74,
      items: [
        "The source sits inside the item identity — when a site goes dark, coverage falls but no fake price movement enters the index.",
        "Ethically designed for real: a 403, a CAPTCHA or a bot challenge is recorded as non-response and never evaded — a unit test fails the build if evasion machinery is added. That is what keeps the number admissible as official statistics.",
        "Our own RFC 9309 robots.txt parser: Python's stdlib parser ignores wildcards and fails permissive — it would have claimed permission we do not have.",
        "The pipeline refuses to publish a point it cannot stand behind (exit code 4) instead of quietly freezing the site behind a green build.",
      ],
    },
  ];
  blocks.forEach((b) => {
    card(s, { x: M, y: b.y, w: LW, h: b.hh, fill: "FFFFFF", line: LINE });
    s.addShape(pres.ShapeType.roundRect, { x: M + 0.14, y: b.y + 0.12, w: 0.20, h: 0.20, rectRadius: 0.05, fill: { color: b.c }, line: { color: b.c } });
    s.addText(b.h, {
      x: M + 0.44, y: b.y + 0.08, w: LW - 0.6, h: 0.28,
      fontFace: "Calibri", fontSize: 12.5, bold: true, color: b.c, isTextBox: true, margin: 0, valign: "middle",
    });
    bullets(s, b.items, { x: M + 0.44, y: b.y + 0.38, w: LW - 0.66, h: b.hh - 0.46, fs: 9.5, gap: 3 });
  });

  // --- right: prototype evidence rail
  const RX = M + LW + 0.28, RW = W - RX - M;
  card(s, { x: RX, y: TOP, w: RW, h: CH, fill: TINT });
  s.addText("PROTOTYPE STATUS", {
    x: RX + 0.22, y: TOP + 0.16, w: RW - 0.44, h: 0.26,
    fontFace: "Calibri", fontSize: 10, bold: true, color: GREY, charSpacing: 1.2, isTextBox: true, margin: 0,
  });
  s.addText("Working end to end", {
    x: RX + 0.22, y: TOP + 0.42, w: RW - 0.44, h: 0.30,
    fontFace: "Cambria", fontSize: 16, bold: true, color: NAVY, isTextBox: true, margin: 0,
  });
  const stats = [
    ["975", "cells in the basket", ORANGE],
    ["3 of 9", "sources permit collection", NAVY],
    ["74", "tests, ~12 s", GREEN],
    ["0.05%", "endpoint error vs. known truth", ORANGE],
  ];
  stats.forEach(([n, l, c], i) => {
    const y = TOP + 0.86 + i * 0.92;
    s.addText(n, { x: RX + 0.22, y, w: RW - 0.44, h: 0.42, fontFace: "Cambria", fontSize: 24, bold: true, color: c, isTextBox: true, margin: 0 });
    s.addText(l, { x: RX + 0.22, y: y + 0.42, w: RW - 0.44, h: 0.34, fontFace: "Calibri", fontSize: 9.5, color: GREY, isTextBox: true, margin: 0, lineSpacingMultiple: 0.9 });
  });
  s.addText("Verified on a 90-day stream with known drift, a +12% shock and 6% non-response.", {
    x: RX + 0.22, y: TOP + 4.46, w: RW - 0.44, h: 0.42,
    fontFace: "Calibri", fontSize: 8.5, italic: true, color: GREY, isTextBox: true, margin: 0, lineSpacingMultiple: 0.9,
  });

  s.addNotes("APIx turns a monthly, manual CPI item into a daily automated one, without ever circumventing a site's access controls.");
}

/* ==========================================================================
   SLIDE 3 — TECHNICAL APPROACH
   ========================================================================== */
{
  const s = pres.addSlide();
  chrome(s, 3, "TECHNICAL APPROACH");
  pointer(s, "Technologies to be used (e.g. programming languages, frameworks, hardware)", CONTENT_TOP);

  const stack = [
    ["COLLECTION & INDEX ENGINE", NAVY, ["Python 3.11", "Playwright / Chromium", "PyYAML", "pytest"]],
    ["DATA", GREEN, ["PostgreSQL (Neon)", "psycopg 3", "SQL migrations"]],
    ["WEB", ORANGE, ["Next.js 16", "React 19", "TypeScript strict", "Tailwind 4"]],
    ["RUNTIME", PURPLE, ["GitHub Actions 02:30 UTC", "Vercel", "FastAPI (local)"]],
  ];
  let cx = M;
  const CW = (W - 2 * M - 0.36) / 4;
  stack.forEach(([label, color, items], i) => {
    const x = M + i * (CW + 0.12);
    card(s, { x, y: 1.80, w: CW, h: 1.14, fill: "FFFFFF", line: LINE });
    s.addText(label, {
      x: x + 0.14, y: 1.88, w: CW - 0.28, h: 0.24,
      fontFace: "Calibri", fontSize: 9, bold: true, color: color, charSpacing: 0.8, isTextBox: true, margin: 0,
    });
    s.addText(items.join("  ·  "), {
      x: x + 0.14, y: 2.14, w: CW - 0.28, h: 0.72,
      fontFace: "Calibri", fontSize: 10.5, color: INK, isTextBox: true, margin: 0, lineSpacingMultiple: 0.98,
    });
  });

  pointer(s, "Methodology and process for implementation", 3.06);

  // --- pipeline flow: 5 + 4 boxes over two rows
  const steps1 = [
    ["1", "Basket", "975 cells from\nconfig/basket.yaml", NAVY],
    ["2", "robots.txt gate", "RFC 9309 parser,\nfails closed", GREEN],
    ["3", "Fetch", "Chromium renders JS,\n5 s crawl delay", NAVY],
    ["4", "Parse", "one adapter per site;\na block = non-response", NAVY],
    ["5", "raw_quote", "append-only archive\nin Postgres", GREEN],
  ];
  const steps2 = [
    ["6", "Normalise", "all-in fare, currency,\nfare family", NAVY],
    ["7", "Quality control", "range checks + MAD\noutliers on log fares", GREEN],
    ["8", "Cell price", "geometric mean per\ncell per day", NAVY],
    ["9", "Impute & chain", "class → route → all-items;\nI(t) = I(t−1) × R(t)", ORANGE],
    ["10", "Publish", "index_point → dashboard,\n/api/index, /api/inflation", GREEN],
  ];
  const BW = (W - 2 * M - 4 * 0.30) / 5, BH = 0.98;
  function row(steps, y) {
    steps.forEach(([n, t, d, c], i) => {
      const x = M + i * (BW + 0.30);
      card(s, { x, y, w: BW, h: BH, fill: i % 2 ? TINT : "FFFFFF", line: LINE });
      badge(s, n, x + 0.10, y + 0.10, 0.26, c);
      s.addText(t, {
        x: x + 0.42, y: y + 0.09, w: BW - 0.52, h: 0.28,
        fontFace: "Calibri", fontSize: 11, bold: true, color: c, isTextBox: true, margin: 0, valign: "middle",
      });
      s.addText(d, {
        x: x + 0.12, y: y + 0.40, w: BW - 0.24, h: 0.52,
        fontFace: "Calibri", fontSize: 8.5, color: GREY, isTextBox: true, margin: 0, lineSpacingMultiple: 0.9,
      });
      if (i < steps.length - 1) {
        s.addShape(pres.ShapeType.rightArrow, {
          x: x + BW + 0.055, y: y + BH / 2 - 0.075, w: 0.19, h: 0.15,
          fill: { color: LINE }, line: { color: LINE },
        });
      }
    });
  }
  row(steps1, 3.44);
  row(steps2, 4.62);

  // --- formula + guardrail strip
  card(s, { x: M, y: 5.78, w: 7.30, h: 1.02, fill: TINT2, line: "F0C9B2" });
  s.addText("Chained weighted geometric (Young) index", {
    x: M + 0.18, y: 5.86, w: 6.9, h: 0.24,
    fontFace: "Calibri", fontSize: 9.5, bold: true, color: ORANGE, isTextBox: true, margin: 0,
  });
  s.addText("R(t) = exp( Σc  w̃c · ln[ p(c,t) / p(c,t−1) ] )        I(t) = I(t−1) × R(t)", {
    x: M + 0.18, y: 6.10, w: 6.9, h: 0.30,
    fontFace: "Cambria", fontSize: 13, bold: true, color: INK, isTextBox: true, margin: 0,
  });
  s.addText("c runs over cells seen in both periods; w̃ is the basket weight renormalised over that matched set. The monthly figure is a direct month-over-month comparison, not a product of 30 daily links.", {
    x: M + 0.18, y: 6.42, w: 6.9, h: 0.32,
    fontFace: "Calibri", fontSize: 8.5, color: GREY, isTextBox: true, margin: 0, lineSpacingMultiple: 0.9,
  });

  card(s, { x: 8.02, y: 5.78, w: W - M - 8.02, h: 1.02, fill: TINT, line: LINE });
  s.addText("Nightly job — every step can stop the run", {
    x: 8.20, y: 5.86, w: 4.6, h: 0.24,
    fontFace: "Calibri", fontSize: 9.5, bold: true, color: NAVY, isTextBox: true, margin: 0,
  });
  s.addText("tests → robots audit → collect → rebuild → report", {
    x: 8.20, y: 6.10, w: 4.6, h: 0.28,
    fontFace: "Calibri", fontSize: 10, bold: true, color: INK, isTextBox: true, margin: 0,
  });
  s.addText("A failing test, a newly disallowed source, an empty pass or an unpublishable point each exits non-zero — the report still runs.", {
    x: 8.20, y: 6.40, w: 4.6, h: 0.34,
    fontFace: "Calibri", fontSize: 8.5, color: GREY, isTextBox: true, margin: 0, lineSpacingMultiple: 0.9,
  });

  s.addNotes("One gated network call is the only outbound request in the codebase, which is what makes the compliance guarantee checkable rather than aspirational.");
}

/* ==========================================================================
   SLIDE 4 — FEASIBILITY AND VIABILITY
   ========================================================================== */
{
  const s = pres.addSlide();
  chrome(s, 4, "FEASIBILITY AND VIABILITY");
  pointer(s, "Analysis of the feasibility of the idea", CONTENT_TOP);

  card(s, { x: M, y: 1.80, w: W - 2 * M, h: 1.30, fill: TINT, line: LINE });
  const feas = [
    ["Already built", "The prototype runs end to end today: collection, index engine, database, dashboard and API."],
    ["Cheap to run", "One nightly GitHub Actions job plus a read-only Vercel site on managed Postgres — free tiers."],
    ["Verified maths", "74 tests, index paths worked out by hand; 0.05% endpoint error against a known synthetic truth."],
    ["Extensible", "A new site — or a partner data feed — drops in as one adapter file; the index engine is untouched."],
  ];
  const FW = (W - 2 * M - 0.6) / 4;
  feas.forEach(([t, d], i) => {
    const x = M + 0.16 + i * (FW + 0.16);
    badge(s, "✓", x, 1.94, 0.26, GREEN);
    s.addText(t, { x: x + 0.34, y: 1.93, w: FW - 0.36, h: 0.26, fontFace: "Calibri", fontSize: 11.5, bold: true, color: NAVY, isTextBox: true, margin: 0, valign: "middle" });
    s.addText(d, { x, y: 2.26, w: FW - 0.04, h: 0.72, fontFace: "Calibri", fontSize: 9.5, color: GREY, isTextBox: true, margin: 0, lineSpacingMultiple: 0.92 });
  });

  const CY = 3.26;
  pointer(s, "Potential challenges and risks", CY, 6.05);
  s.addText("Strategies for overcoming these challenges", {
    x: 6.95, y: CY, w: W - M - 6.95, h: 0.34,
    fontFace: "Calibri", fontSize: 16, bold: true, color: NAVY, isTextBox: true, margin: 0, valign: "middle",
  });

  const pairs = [
    ["Coverage is sparse and uneven",
     "Only 3 of 9 audited sites allow the fare paths an index needs. IndiGo, SpiceJet and Cleartrip disallow them; Akasa and MakeMyTrip are unreadable, so we fail closed.",
     "Source is part of the cell and weights renormalise over matched cells, so a silent source costs coverage, never a fake price move. The real fix is data access, not better scraping: a partner feed, GDS data or reporting under the Collection of Statistics Act arrives as one more adapter."],
    ["Non-response can masquerade as inflation",
     "It already did: 28–30 Aug 2026, two sources returned nothing, imputation hit 84.9%, and the index drifted +8.2% in three days while the build stayed green and the site stayed frozen.",
     "Donor hierarchy imputes from the cell's own stratum (class → route → all-items); quality flags warn at 35% and fail at 60%; the rebuild now exits 4 rather than publishing a fail-quality point, naming the coverage, the bad days and which sources went silent."],
    ["One slow robots.txt read cost a whole source",
     "A single timeout poisoned the cache for an hour, turning all 75 of that source's requests into non-responses.",
     "The gate now separates a refusal from a network failure: an HTTP status is the operator answering — one attempt, cached an hour; a timeout is the network — three attempts, cached 120 seconds."],
    ["Weights are placeholders, not statistics",
     "Basket weights are shaped like DGCA figures but are not them, and O-D and booking-lead shares are combined assuming independence.",
     "Flagged in basket.yaml, METHODOLOGY.md and the README's honest-status section; replace with DGCA monthly O-D traffic and GDS booking-lead data, on an annual basket review, before anything is published as a statistic."],
  ];
  let y = 3.62;
  pairs.forEach(([t, risk, fix], i) => {
    const h = i === 2 ? 0.62 : 0.76;
    card(s, { x: M, y, w: 6.20, h, fill: "FFFFFF", line: "E6C9C9" });
    card(s, { x: 6.95, y, w: W - M - 6.95, h, fill: TINT, line: LINE });
    s.addText(t, { x: M + 0.14, y: y + 0.06, w: 5.9, h: 0.24, fontFace: "Calibri", fontSize: 10.5, bold: true, color: "9B2C2C", isTextBox: true, margin: 0 });
    s.addText(risk, { x: M + 0.14, y: y + 0.29, w: 5.9, h: h - 0.35, fontFace: "Calibri", fontSize: 9, color: GREY, isTextBox: true, margin: 0, lineSpacingMultiple: 0.9 });
    s.addText(fix, { x: 7.09, y: y + 0.08, w: W - M - 7.23, h: h - 0.16, fontFace: "Calibri", fontSize: 9, color: INK, isTextBox: true, margin: 0, lineSpacingMultiple: 0.92 });
    y += h + 0.09;
  });

  s.addNotes("Every mitigation on this slide is code that exists, not a plan: the publication guard, the refusal/timeout split and the donor hierarchy are all pinned by tests.");
}

/* ==========================================================================
   SLIDE 5 — IMPACT AND BENEFITS
   ========================================================================== */
{
  const s = pres.addSlide();
  chrome(s, 5, "IMPACT AND BENEFITS");
  pointer(s, "Potential impact on the target audience", CONTENT_TOP);

  const aud = [
    ["MoSPI / NSO", "CPI compilers of the\nTransport & Communication\nsub-group", NAVY],
    ["RBI & analysts", "A fast-moving component\nread daily instead of\nonce a month", GREEN],
    ["MoCA / DGCA", "Fare behaviour by route,\ncarrier and booking\nwindow", ORANGE],
    ["Researchers", "An append-only archive\nthat lets anyone replicate\nthe series", PURPLE],
    ["Travellers & media", "A public advance-purchase\ncurve: how far ahead\nfares actually change", NAVY],
  ];
  const AW = (W - 2 * M - 4 * 0.16) / 5;
  aud.forEach(([t, d, c], i) => {
    const x = M + i * (AW + 0.16);
    card(s, { x, y: 1.80, w: AW, h: 1.42, fill: "FFFFFF", line: LINE });
    s.addShape(pres.ShapeType.roundRect, { x: x + 0.14, y: 1.94, w: 0.22, h: 0.22, rectRadius: 0.05, fill: { color: c }, line: { color: c } });
    s.addText(t, { x: x + 0.44, y: 1.90, w: AW - 0.56, h: 0.30, fontFace: "Calibri", fontSize: 11.5, bold: true, color: c, isTextBox: true, margin: 0, valign: "middle" });
    s.addText(d, { x: x + 0.14, y: 2.28, w: AW - 0.28, h: 0.84, fontFace: "Calibri", fontSize: 9.5, color: GREY, isTextBox: true, margin: 0, lineSpacingMultiple: 0.92 });
  });

  card(s, { x: M, y: 3.34, w: W - 2 * M, h: 0.92, fill: TINT2, line: "F0C9B2" });
  const kpis = [
    ["Daily", "instead of monthly observation of the air-fare item"],
    ["Every point", "ships coverage, imputation share and a quality flag"],
    ["Zero", "access controls circumvented — so the number is admissible"],
    ["Reproducible", "the whole index recomputes from the raw quote archive"],
  ];
  const KW = (W - 2 * M - 0.5) / 4;
  kpis.forEach(([n, l], i) => {
    const x = M + 0.18 + i * (KW + 0.10);
    s.addText(n, { x, y: 3.44, w: KW, h: 0.32, fontFace: "Cambria", fontSize: 17, bold: true, color: ORANGE, isTextBox: true, margin: 0 });
    s.addText(l, { x, y: 3.76, w: KW - 0.08, h: 0.40, fontFace: "Calibri", fontSize: 9, color: GREY, isTextBox: true, margin: 0, lineSpacingMultiple: 0.9 });
  });

  pointer(s, "Benefits of the solution (social, economic, environmental, etc.)", 4.42);

  const bens = [
    ["ECONOMIC", NAVY, [
      "An earlier, higher-frequency signal on transport inflation, where the current one lags by weeks.",
      "Base fare and tax are kept per quote, so an ex-tax variant can sit beside the headline — separating a GST change from a genuine fare move.",
      "Automated collection removes recurring manual price-collection effort for this item.",
    ]],
    ["SOCIAL", GREEN, [
      "Open methodology and a public compliance page: which sites were asked, what they answered, and why.",
      "Households can see the advance-purchase curve and the route × window fare matrix rather than guessing when to book.",
      "Any series built on simulated data is banner-flagged, with no switch to turn the warning off.",
    ]],
    ["GOVERNANCE & ENVIRONMENTAL", ORANGE, [
      "Statistics produced without defeating any site's access controls — defensible in a way scraped-by-evasion data is not.",
      "The audit trail, the collection log and the raw archive make independent replication possible.",
      "One nightly job and a read-only site: a negligible compute footprint and no field travel to collect prices.",
    ]],
  ];
  const BWD = (W - 2 * M - 0.36) / 3;
  bens.forEach(([t, c, items], i) => {
    const x = M + i * (BWD + 0.18);
    card(s, { x, y: 4.84, w: BWD, h: 1.92, fill: "FFFFFF", line: LINE });
    s.addText(t, { x: x + 0.16, y: 4.92, w: BWD - 0.32, h: 0.26, fontFace: "Calibri", fontSize: 9.5, bold: true, color: c, charSpacing: 1, isTextBox: true, margin: 0 });
    bullets(s, items, { x: x + 0.16, y: 5.20, w: BWD - 0.32, h: 1.48, fs: 9.5, gap: 5 });
  });

  s.addNotes("The benefit that matters most is admissibility: an index that underpins policy cannot rest on data obtained by circumventing access controls.");
}

/* ==========================================================================
   SLIDE 6 — RESEARCH AND REFERENCES
   ========================================================================== */
{
  const s = pres.addSlide();
  chrome(s, 6, "RESEARCH AND REFERENCES");
  pointer(s, "Details / Links of the reference and research work", CONTENT_TOP);

  const cols = [
    ["PROJECT ARTEFACTS", NAVY, [
      ["Source code, docs and issue tracker", "github.com/Prasun-Acharjee/apix-airfare-index"],
      ["METHODOLOGY.md", "the formal spec: price concept, the cell, the geometric mean, chaining, the imputation hierarchy and the quality flags"],
      ["DEPLOY.md", "Vercel + Neon and self-hosted Docker deployment"],
      ["Live pages", "/ index chart and route × window matrix · /compliance robots audit and collection log · /methodology"],
      ["Public API", "/api/index/{daily|weekly|monthly} · /api/inflation · /api/routes · /api/compliance · /api/collection-log"],
      ["Test suite — 74 tests", "including test_stdlib_parser_would_have_been_wrong and test_codebase_contains_no_evasion_machinery, which pin the two claims this slide deck makes"],
    ]],
    ["STANDARDS, SOURCES AND PRIOR ART", ORANGE, [
      ["RFC 9309 — Robots Exclusion Protocol", "rfc-editor.org/rfc/rfc9309.html — implemented in apix/compliance/rfc9309.py, because Python's urllib.robotparser handles neither wildcards nor full-URL directives and fails permissive"],
      ["CPI Manual: Concepts and Methods — ILO, IMF, OECD, UNECE, Eurostat", "chained indices, elementary aggregates and the imputation of missing prices"],
      ["Eurostat and ONS practice on web-scraped prices", "treatment of airfares in the HICP/CPI and the use of scraped data in official statistics"],
      ["MoSPI — Consumer Price Index", "the Transport & Communication sub-group this index is scoped to"],
      ["DGCA — Monthly Traffic Statistics", "origin–destination passenger traffic and carrier market share, the intended replacement for the placeholder basket weights"],
      ["Collection of Statistics Act, 2008", "the statutory route to airline data access that removes the coverage problem entirely"],
      ["Playwright · Next.js · PostgreSQL documentation", "JS rendering, the App Router read path and the schema"],
    ]],
  ];

  const CW2 = [5.30, W - 2 * M - 5.30 - 0.34];
  let x = M;
  cols.forEach(([head, color, items], ci) => {
    const w = CW2[ci];
    card(s, { x, y: 1.80, w, h: 4.96, fill: ci === 0 ? TINT : "FFFFFF", line: LINE });
    s.addText(head, {
      x: x + 0.20, y: 1.92, w: w - 0.4, h: 0.26,
      fontFace: "Calibri", fontSize: 10, bold: true, color: color, charSpacing: 1, isTextBox: true, margin: 0,
    });
    let yy = ci === 0 ? 2.26 : 2.24;
    items.forEach(([t, d], i) => {
      badge(s, String(i + 1), x + 0.20, yy + 0.01, 0.24, color);
      s.addText(t, {
        x: x + 0.54, y: yy, w: w - 0.74, h: 0.24,
        fontFace: "Calibri", fontSize: 10, bold: true, color: INK, isTextBox: true, margin: 0, valign: "middle",
      });
      const dh = ci === 0 ? 0.44 : 0.40;
      s.addText(d, {
        x: x + 0.54, y: yy + 0.23, w: w - 0.74, h: dh,
        fontFace: "Calibri", fontSize: 8.8, color: GREY, isTextBox: true, margin: 0, lineSpacingMultiple: 0.9,
      });
      yy += (ci === 0 ? 0.74 : 0.63);
    });
    x += w + 0.34;
  });

  s.addNotes("The reference that most shaped the build is RFC 9309: implementing it properly is what showed that six of nine candidate sources do not permit fare-path collection.");
}

pres.writeFile({ fileName: path.join(DIR, "SIH2026_APIx_Idea_Presentation.pptx") })
  .then((f) => console.log("wrote", f));
