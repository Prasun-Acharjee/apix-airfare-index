# APIx — Real-time Airfare Price Index

A working prototype of an end-to-end airfare price index for the CPI
**Transport & Communication** sub-group: compliant collection → normalisation →
quality control → index computation → API → dashboard.

> **Read `METHODOLOGY.md` before the code.** The index construction, the weighting,
> the imputation scheme and — most importantly — what this project refuses to build
> and why, are all there.

---

## The short version

| | |
|---|---|
| **Stack** | Next.js 16 + React 19 + TypeScript (strict) · Postgres · Python 3.11 worker |
| **Index** | Chained weighted geometric (Young), matched-model on `(source, route, carrier, advance window, cabin)` |
| **Frequencies** | Daily (monitoring), weekly, monthly (published — direct comparison, not chained) |
| **Basket** | 15 city pairs × 6 carriers × 5 advance windows × collectable sources = 525 cells |
| **Collection** | Playwright/Chromium, robots.txt-gated, fails closed. **No CAPTCHA solving, no proxy rotation, no fingerprint spoofing.** |
| **Sources collectable** | 2 of 8 audited. See below. |
| **Verification** | 45 Python tests; index recovers a known synthetic price path to within 0.05%; strict typecheck and clean production build |

---

## Architecture

Two runtimes, one database, no direct coupling:

```
  Python worker                     Postgres                  Next.js app
  ─────────────                     ────────                  ───────────
  robots.txt gate                                             typed API routes
  Playwright collection    ──write──▶  cell_price   ──read──▶  dashboard
  normalisation + QC                   index_point             compliance page
  index engine                         source                  methodology
  (GitHub Actions, daily)              collection_log          (Vercel)
```

The scraper needs a real browser, a long-running process and a five-second
per-host crawl delay — none of which belongs in a serverless request handler. So
it runs on a schedule and writes to Postgres; the website only ever reads.

`db/migrations/001_init.sql` is the single source of truth for the schema. The
Python dataclasses and the TypeScript row types are both written against it.

## Quick start

```bash
# 1. Database
createdb apix
export DATABASE_URL="postgresql://localhost/apix"
psql "$DATABASE_URL" -f db/migrations/001_init.sql

# 2. Python worker — index engine and collector
pip install -r requirements.txt
python -m pytest -q                            # 45 tests, ~7s
python scripts/seed_postgres.py --days 120     # SYNTHETIC demo data

# 3. Website
cd web && npm install
cp .env.example .env.local                     # set DATABASE_URL
npm run dev                                    # http://localhost:3000
```

For live collection (permitted sources only):

```bash
playwright install chromium
python scripts/audit_robots.py                 # re-run the compliance audit
python scripts/run_collection.py               # collect
python scripts/seed_postgres.py --from-sqlite data/apix.db
```

Deployment — Vercel + Neon, or self-hosted Docker — is in **[DEPLOY.md](DEPLOY.md)**.

## The website

| Route | What it serves |
|---|---|
| `/` | Index chart with crosshair, stat tiles, advance-purchase curve, route × window fare matrix, provenance |
| `/compliance` | The robots.txt audit from the database, the stdlib parser bug, the collection log |
| `/methodology` | `METHODOLOGY.md`, rendered |
| `/api/index/{daily\|weekly\|monthly}` | Index series + provenance. `?start=&end=&includeFailed=` |
| `/api/inflation/{frequency}?periods=` | Period-over-period percent change |
| `/api/routes?on=` | Observed fare matrix for a collection day |
| `/api/compliance` | Source registry with verdicts and reasons |
| `/api/collection-log?limit=` | Why a given day looks the way it does |
| `/api/health` | Liveness + what data is loaded (503 when empty) |

Every response that carries a number also carries its provenance, and any series
containing simulated quotes is flagged `synthetic` with a warning that cannot be
switched off.

TypeScript is strict with `noUncheckedIndexedAccess`; `npm run build` passes with
`DATABASE_URL` unset, so a deploy cannot fail on database reachability.

---

## The finding that shaped the design

The problem statement names five airlines and "leading OTAs". A robots.txt audit
(2026-08-25) found that **most of them disallow exactly the fare paths the index
needs**:

| Source | Verdict | Basis |
|---|---|---|
| **Air India** | ✅ collect | Fare search not disallowed; AI bots explicitly `Allow: *` |
| **Yatra** (OTA) | ✅ collect | Flight search not disallowed; ClaudeBot permitted, `Crawl-delay: 5` |
| SpiceJet | ❌ | `/api/v1` — the endpoint the UI calls for fares — is disallowed |
| IndiGo | ❌ | `Disallow: /booking/*`, `/book/*` |
| Air India Express | ❌ | `Disallow: /flight-availability` |
| Akasa Air | ❌ | robots.txt returns HTTP 403 — policy unreadable, fail closed |
| Cleartrip | ❌ | `Disallow: /flights/search*` |
| MakeMyTrip | ❌ | robots.txt fetch timed out — policy unknown, fail closed |

Two of eight. Everything downstream — matched-model cells with the source inside
them, class-mean imputation, published coverage and imputation shares — exists
because the index has to stay honest on sparse, uneven, legally-constrained coverage.

The right long-run fix is **data access, not better scraping**: partner feeds, GDS
transaction data, or a statutory reporting requirement under the Collection of
Statistics Act. A partner feed drops in as another adapter without touching the
index engine.

### A robots.txt parser bug worth knowing about

Python's `urllib.robotparser` implements neither wildcards nor full-URL directives,
and fails **permissive**:

| Directive | stdlib | correct |
|---|---|---|
| IndiGo `Disallow: /booking/*` | ALLOW | **DISALLOW** |
| SpiceJet `Disallow: https://www.spicejet.com/api/v1` | ALLOW | **DISALLOW** |

A collector built on it would believe it had permission it does not have.
`apix/compliance/rfc9309.py` implements RFC 9309 properly; the difference is pinned
by `test_stdlib_parser_would_have_been_wrong`.

---

## What was deliberately not built

The statement asks for handling of "dynamic CAPTCHAs, anti-bot measures, IP
rotation". This project does not do those, because a CAPTCHA or a 403 is the site
declining the request, and an index underpinning monetary policy cannot rest on data
obtained by circumventing access controls.

Blocks are **recorded as non-response and imputed**, never evaded.
`test_codebase_contains_no_evasion_machinery` fails the build if a CAPTCHA solver,
stealth plugin, or proxy-rotation library is ever added.

---

## Layout

```
db/migrations/
  001_init.sql           the schema — single source of truth for both runtimes
config/
  basket.yaml            city pairs, weights, windows, QC thresholds
  sources.yaml           source registry + the compliance audit
apix/
  compliance/
    rfc9309.py           RFC 9309 robots.txt matcher (the stdlib one is wrong)
    robots.py            runtime gate — fails closed
    ratelimit.py         per-host crawl-delay + hourly ceiling
  collect/
    base.py              adapter contract; the single gated network path
    adapters/            air_india.py, yatra.py
    runner.py            orchestration
    simulator.py         SYNTHETIC generator (test harness, never a data source)
  normalize/
    fares.py             price concept, fare-family/cabin canonicalisation
    qc.py                range checks, MAD outlier detection, day-move flags
  index/
    elementary.py        geometric-mean cell prices
    imputation.py        class-mean → route-mean → all-items donor hierarchy
    aggregate.py         chained weighted geometric index + direct comparison
  api/main.py            FastAPI (local dev server; the site is the Next.js app)
  db.py                  SQLite backend; raw quotes append-only, blocks recorded
  store.py               backend chosen by DSN — SQLite locally, Postgres for the site
  pipeline.py            raw → normalised → QC → cells → index → DB
tests/                   45 tests, ground-truth based
web/                     Next.js 16 App Router, TypeScript strict
  src/lib/               db client (lazy), typed queries, zod params, formatting
  src/app/               pages + API route handlers
  src/components/        charts and UI, typed props throughout
scripts/
  audit_robots.py        re-run the compliance audit
  run_collection.py      one collection pass, permitted sources only
  seed_postgres.py       build the index and publish it to Postgres
.github/workflows/
  collect.yml            daily: test → re-audit → collect → publish
docker-compose.yml       self-hosted alternative to Vercel + Neon
```

---

## Verification approach

The index is tested against price paths whose true movement is **constructed by
hand**, so the tests check correctness rather than re-asserting the implementation:

- uniform inflation recovered exactly
- hand-computed weighted geometric mean matched
- cell entry contributes no movement; cell exit imputed, not dropped
- imputation draws from the cell's own stratum, not the global mean
- chaining drift-free under constant coverage, on a deliberately oscillating path
- total non-response carries the index flat and flags `fail`

End-to-end on a 90-day synthetic stream with known drift, seasonality, a +12% shock
and 6% non-response: recovered to **0.05% at the endpoint**, under 5% at any point,
no systematic drift.

---

## Honest status

**Prototype.** Working end to end, verified against ground truth, and not a
publishable statistic. Before it could be one:

1. Placeholder weights → actual DGCA O-D traffic and market share
2. Assumed booking-lead weights → industry/GDS data; joint O-D × lead-time distribution
3. Partner feeds for the four carriers whose sites exclude crawling
4. A measured direct-vs-OTA channel split
5. Seasonal adjustment and a published revision policy
6. Independent replication from the raw quote archive

Everything demonstrated with `scripts/simulate_history.py` uses **synthetic data**.
The API flags it, the dashboard banners it, and the source ids are prefixed `sim_`.
