# APIx — Real-time Airfare Price Index

This README is written for someone who has just been handed the repo and has to
work on it. It explains what the thing does, why each part exists, and what will
confuse you. No prior knowledge of price-index statistics is assumed.

If you only read two things, read **[this README](README.md)** and then
**[METHODOLOGY.md](METHODOLOGY.md)**, which is the formal spec for the maths.

---

## 1. What are we building?

India's Consumer Price Index has a **Transport & Communication** sub-group. Air
fares belong in it. The problem is that air fares move *fast* — a fare can change
several times in a day — while CPI collection is monthly and manual.

APIx is a prototype answer: collect airline fares off the public web every day,
turn them into a **price index**, and publish it on a website.

A price index is just a number that says "prices today, compared to prices on
some starting day, expressed as a percentage." We anchor at **100.0 on
2026-04-01**. If the index reads 104, fares are 4% above the starting day. That
is the whole idea. Everything else in this repo is about making that number
*honest*.

### Why it takes 6,000 lines to compute one number

Three problems, and most of the code is one of these three:

1. **You are not comparing the same thing twice.** Yesterday's DEL–BOM flights
   are not today's DEL–BOM flights. Making the comparison fair is the *index*
   part (`apix/index/`).
2. **Most of the data is missing, most days.** Airlines and travel sites are
   allowed to say no, and they do. Handling that without lying is the
   *imputation and quality* part (`apix/index/imputation.py`, `apix/normalize/qc.py`).
3. **You have to be allowed to collect it.** A statistic that underpins policy
   cannot be built by sneaking past a site's access controls. That is the
   *compliance* part (`apix/compliance/`), and it is genuinely the most
   load-bearing directory in the repo.

---

## 2. The vocabulary

You need six words. They appear everywhere in the code.

**Quote** — one price we saw. "EaseMyTrip says Air India AI-665, DEL→BOM,
departing in 7 days, costs ₹5,499 all-in." That's a quote. We collect a few
hundred a day.

**Cell** — the "item" of the index. Defined in `apix/models.py` as
`(source, route, carrier, advance-purchase window, cabin)`:

> EaseMyTrip × DEL-BOM × Air India × 7 days ahead × Economy

Why so specific? Because an index has to compare like with like. A seat bought a
day before departure and the same seat bought 45 days ahead are different
products with different prices, and mixing them means the index moves when the
*mix* changes rather than when prices change.

**Note that the source is part of the cell.** That is deliberate and it matters.
An OTA (online travel agency) and the airline's own site show different prices
for the same seat — the OTA adds a markup and often gets shown different fare
inventory. By putting the source inside the cell identity, the index only ever
compares a source against *itself* over time. So when a source stops responding,
coverage drops but no fake price movement is injected.

**Basket** — every cell we *want* to observe, with a weight saying how much each
matters. Defined in `config/basket.yaml`: 15 city pairs × 6 carriers × 5 advance
windows × Economy. With the three currently collectable sources, that's **975
cells**. Weights come from route passenger share × carrier market share ×
booking-window share. *(The weights in the file are placeholders shaped like the
real DGCA figures. Read the warning at the top of `basket.yaml` before you quote
any number from this system.)*

**Chained index** — how we get from cell prices to one number. Each day we ask:
"for the cells we saw both yesterday and today, how much did they move on
average?" That gives a ratio (a *link*), and today's index = yesterday's index ×
that link. Multiply the links together and you get a series.

The alternative — compare everything back to April 1st every day — breaks the
moment a carrier drops a route or a new fare family appears, because you'd have
to invent what that cell cost in April. Chaining never asks that question. A cell
joins from its second observation and leaves when it disappears, and neither
event moves the index by itself.

**Imputation** — what we do about missing cells. If EaseMyTrip doesn't respond
for Air India DEL-BOM today, we don't drop that cell: dropping it would silently
re-weight the index toward whatever *did* respond, and non-response would start
looking like inflation. Instead we estimate its movement from similar cells
(`apix/index/imputation.py`), most-specific donor first:

```
1. class-mean  → other cells on the same route + same advance window
2. route-mean  → any matched cell on the same route
3. all-items   → the overall matched movement
```

**Coverage and quality** — every index point publishes how much of the basket we
actually observed (`coverage`) and how much rested on imputation
(`imputation_share`), then flags itself:

| imputation share | flag | what happens |
|---|---|---|
| under 35% | `ok` | published normally |
| 35–60% | `warn` | published, badged on the site |
| **60% or more** | **`fail`** | **hidden by the website, and the rebuild now refuses to publish it** |

That last row is the single most important operational fact in this repo. See
§7.

---

## 3. How the data flows

Two runtimes that never talk to each other. They share a Postgres database.

```
   PYTHON WORKER                      POSTGRES                  NEXT.JS SITE
   (GitHub Actions, nightly)                                    (Vercel)

   robots.txt gate                    raw_quote      ─read─▶    API routes
   Playwright browser     ─write─▶    cell_price     ─read─▶    dashboard
   normalise + QC                     index_point    ─read─▶    /compliance
   index engine                       collection_log            /methodology
                                      source
```

The collector needs a real browser, a long-running process and a five-second
pause between requests to each host. None of that fits in a serverless request
handler, so it runs on a schedule and only ever *writes*. The website only ever
*reads*. `db/migrations/001_init.sql` is the single source of truth for the
schema — the Python dataclasses and the TypeScript row types are both written
against it by hand, so if you change the SQL, change both.

### One quote's journey, end to end

Follow a single price through the system. This is the fastest way to learn the
codebase.

**1. Decide what to ask for.** `apix/collect/runner.py:search_requests()` walks
the basket and produces 75 search requests: 15 routes × 5 advance windows.

**2. Ask permission.** `apix/compliance/robots.py` fetches the site's
`robots.txt` and decides. It **fails closed**: if we can't read the file, or the
answer is ambiguous, we don't fetch. Ever.

**3. Fetch.** `apix/collect/base.py:BaseAdapter.fetch()` is the *only* place in
the codebase that makes an outbound request. Adapters build a URL and hand it
over; they never touch the network themselves. That single choke point is what
makes the compliance guarantee checkable rather than aspirational. A rate limiter
(`apix/compliance/ratelimit.py`) enforces the crawl delay.

**4. Parse.** One adapter per site: `apix/collect/adapters/{air_india,yatra,easemytrip}.py`.
Each returns `RawQuote` objects. If the site declined us (403/429/challenge), the
adapter records a **non-response** — a row saying "we asked, they said no" — and
moves on. It is never retried from elsewhere.

**5. Store raw.** `apix/store.py` writes to `raw_quote`, append-only. This table
is the archive: everything downstream can be recomputed from it, which is what
makes the index reproducible.

**6. Normalise.** `apix/normalize/fares.py` turns messy scraped text into
comparable numbers. `"₹ 5,499"` → `5499.0`. `"Eco Value"` → `SAVER`. It also
fixes the *price concept*: the index price is the **all-in fare** — base + GST +
airport charges + mandatory surcharges — because that's what a household actually
hands over. Optional extras (seat selection, bags, meals) are excluded; including
them would make the index track the site's default checkbox state.

**7. Quality control.** `apix/normalize/qc.py` throws out impossible values
(under ₹800, over ₹120,000) and statistical outliers, using a median-absolute-
deviation score on **log** fares — because fare dispersion is multiplicative, so
a 2× fare on a cheap route and a 2× fare on an expensive one are the same
anomaly. Rejections are counted and reported, never silently dropped.

**8. Collapse to cell prices.** `apix/index/elementary.py` takes all the quotes
in one cell on one day and produces a single price using a **geometric mean**
(not an average). Airfare distributions are right-skewed: a couple of last-seat
fares at 5× the normal price will drag an arithmetic mean upward, and the index
would then report widening dispersion as inflation even when the typical fare
never moved.

**9. Build the index.** `apix/index/aggregate.py` does the chaining described
above, imputes missing cells, and produces `IndexPoint` rows carrying value,
coverage, imputation share and quality flag. Daily and weekly series are chained;
the **published monthly figure is a direct month-to-month comparison**, not a
product of thirty daily links, to bound chain drift.

**10. Publish.** `scripts/seed_postgres.py` writes `cell_price` and
`index_point`. The website picks it up on the next request.

---

## 4. The repo, folder by folder

```
config/
  basket.yaml          routes, carriers, windows, weights, QC thresholds
  sources.yaml         the 9 sources + the robots.txt audit for each

db/migrations/
  001_init.sql         the schema. Both runtimes are written against this.

apix/                  ← the Python worker
  models.py            Cell, RawQuote, NormalisedQuote, CellPrice, IndexPoint
  config.py            loads the YAML, computes cell weights
  store.py             database access. Backend chosen by DSN (see §6 gotchas)
  db.py                the SQLite half of that
  pipeline.py          raw → normalised → QC → cells → index. Start reading here.

  compliance/          ← read this directory before changing anything in collect/
    rfc9309.py         our own robots.txt parser (the stdlib one is broken — §8)
    robots.py          the runtime gate. Fails closed.
    ratelimit.py       per-host crawl delay + hourly ceiling

  collect/
    base.py            adapter contract + the ONE gated network call
    adapters/          one file per site
    runner.py          orchestrates a full collection pass
    simulator.py       synthetic fare generator — a test fixture, NOT a data source

  normalize/
    fares.py           price concept, currency parsing, fare-family mapping
    qc.py              range checks, MAD outliers, day-move flags

  index/
    elementary.py      quotes → one geometric-mean price per cell per day
    imputation.py      the class-mean → route-mean → all-items donor hierarchy
    aggregate.py       the chained index itself. The core of the project.

  api/main.py          a small FastAPI server for local poking. The real site is web/.

scripts/
  audit_robots.py      re-check every source's robots.txt; exits 1 on a real conflict
  run_collection.py    one collection pass
  seed_postgres.py     build the index and publish it
  compute_index.py     rebuild from a local SQLite archive
  simulate_history.py  fill a local DB with synthetic data for UI work

web/                   ← Next.js 16 App Router, TypeScript strict
  src/lib/queries.ts   all SQL the site runs. Note the quality filter (§7).
  src/app/             pages and /api route handlers
  src/components/      charts and UI

tests/                 74 tests
.github/workflows/
  collect.yml          the nightly job: test → audit → collect → publish → report
```

### Where to start reading

- **Understand the maths** → `apix/index/aggregate.py`, top-of-file docstring first.
- **Understand the ethics** → `apix/compliance/robots.py`, top-of-file docstring.
- **Understand the shape of the data** → `db/migrations/001_init.sql`.
- **Understand the whole flow** → `apix/pipeline.py` is 46 lines and calls everything.

The docstrings in this repo explain *why*, not *what*. They are worth reading.

---

## 5. Running it

```bash
# 1. Database
createdb apix
export DATABASE_URL="postgresql://localhost/apix"
# no need to run the SQL by hand — seed_postgres.py applies migrations itself

# 2. Python worker
pip install -r requirements.txt
python -m pytest -q                            # 74 tests, ~12s
python scripts/seed_postgres.py --days 120     # SYNTHETIC demo data

# 3. Website
cd web && npm install
cp .env.example .env.local                     # set DATABASE_URL
npm run dev                                    # http://localhost:3000
```

That gets you a working site full of fake data. The synthetic source ids are
prefixed `sim_`, the site detects that and shows a banner, and **there is no flag
to turn the banner off**.

For a real collection pass:

```bash
playwright install chromium
python scripts/audit_robots.py     # re-check robots.txt; exits 1 on a real conflict
python scripts/run_collection.py -v
python scripts/seed_postgres.py --from-postgres
```

Deployment (Vercel + Neon, or self-hosted Docker) is in **[DEPLOY.md](DEPLOY.md)**.

---

## 6. The nightly job

`.github/workflows/collect.yml`, scheduled 02:30 UTC (08:00 IST). GitHub often
runs scheduled jobs late — hours late — so don't be alarmed by the timestamps.

```
run tests  →  re-audit robots.txt  →  collect  →  rebuild index  →  report
```

Each step can stop the run, and each stop means something different:

| Step | Exits non-zero when | What it means |
|---|---|---|
| tests | any test fails | don't let a broken engine touch real data |
| audit | a source we intend to collect is **actively disallowed** | the site changed its policy; update `sources.yaml` |
| collect | the pass collected nothing at all | every source failed — network or site-side |
| rebuild | fewer than 2 collection days (exit 3) | can't form a chain link; would republish the base period |
| rebuild | newest point is `fail` quality (exit 4) | **nothing publishable was produced — see §7** |

An *unreadable* robots.txt is a warning, not a failure: the runtime gate refuses
those requests individually and records them as absences, so one unreachable host
doesn't take down collection for the other eight.

The report step runs **even when the rebuild refuses**, which is exactly when you
want it — it prints the last five published index points, so you can see what the
site is actually serving and how stale it is.

---

## 7. The thing that will bite you: a green job and a frozen site

This happened for real, 2026-08-28 to 08-30, and both fixes in the current code
exist because of it. Read this section before debugging anything.

**The symptom.** The nightly job reported success three nights running. The
website hadn't moved since 2026-08-27.

**What was actually happening.** Air India and Yatra returned zero quotes from
GitHub's runners — their `robots.txt` reads timed out, so the gate correctly
failed closed and all 75 requests per source became non-responses. Only
EaseMyTrip produced data. But Air India and Yatra *are* in the basket and *were*
present in the earlier days, so their cells — about 85% of basket weight — got
imputed every single day.

Imputation share hit 84.9%. That's past the 60% fail threshold, so every new
point came out `fail`. And `web/src/lib/queries.ts` filters `fail` points out by
default (`AND quality <> 'fail'`), so no reader ever saw them. The index behind
them had drifted 101.37 → 104.50 → 109.68 — **+8.2% in three days, entirely from
imputed movements** — and nothing anywhere exited non-zero.

**The general lesson.** In this system a failure surfaces several steps from its
cause. A collector that stops returning quotes shows up as an *index quality*
problem, days later. When something looks wrong, walk the chain backwards:

```
site is stale  →  are recent points quality='fail'?
               →  what is the imputation share?
               →  which sources priced cells yesterday and none today?
               →  what did the Collect step's per-source counts say?
               →  what did the robots gate decide, and why?
```

The rebuild step now prints most of that for you when it refuses.

**What was changed.** Two things, at the two places it stayed quiet:

- `scripts/seed_postgres.py --from-postgres` now **exits 4 rather than
  publishing a `fail`-quality newest point**. Writing one changed nothing a
  reader could see; it only froze the series while the job stayed green. The
  refusal names the coverage, the imputation share, the span of bad days, and
  which sources went silent. Use `--allow-failed-quality` for deliberate
  backfills. The last good series stays published either way.
- `apix/compliance/robots.py` now distinguishes **a refusal from a network
  failure**. An HTTP status is the operator answering us: one attempt, fail
  closed, cached for the full hour, never retried. A timeout is the network
  between us and them: three patient attempts, then cached for only 120 seconds.
  Previously one timeout poisoned the cache for a full hour, so a single slow
  response at the top of a run cost that source all 75 of its requests.

To be clear about the limits of that second fix: it does not prove those hosts
are reachable from GitHub's network at all. If they are simply refusing that
network, the job will now go **red** instead of quietly publishing an index built
out of imputation. Red is the correct outcome. A stale index with a visible alarm
beats a moving index nobody can trust.

### Other gotchas worth knowing

- **`--db` and `$DATABASE_URL`.** `CollectionRun` resolves its target as
  `db_path or $DATABASE_URL or "data/apix.db"`. A CLI default of `"data/apix.db"`
  is *truthy*, so it silently shadows the environment. That bug sent an entire
  night's quotes to the CI runner's disposable filesystem. `--db` now defaults to
  `None`, and `tests/test_collection_target.py` pins it.
- **The runner's filesystem is discarded.** Anything the nightly job needs to
  keep must go to Postgres. There is no local archive in CI.
- **The rebuild reads the whole history, not just today.** A chained index is
  recomputed from every quote ever collected. This is what makes the daily job
  idempotent, and it is why the job gets slower as the archive grows.
- **`sources.yaml` is documentation, not enforcement.** It records an audit. The
  live gate in `robots.py` decides, every request, regardless of what the YAML
  says. If they disagree, `audit_robots.py` tells you.

---

## 8. The compliance rules (non-negotiable)

The original brief asked for handling of "dynamic CAPTCHAs, anti-bot measures, IP
rotation". **This project does not do those**, and you should not add them.

A CAPTCHA, a 403 or a bot challenge is the site declining our request. An index
that could underpin monetary policy cannot rest on data obtained by circumventing
access controls — it would be inadmissible as official statistics, which defeats
the entire point of building it.

So: blocks are **recorded as non-response and imputed, never evaded**. There is a
test, `test_codebase_contains_no_evasion_machinery`, that fails the build if
anyone ever adds a CAPTCHA solver, a stealth plugin or a proxy-rotation library.

The collector also identifies itself honestly — a real user agent pointing at
this repository and its issue tracker, so an operator who wants us to stop can
say so. Don't put a fake affiliation or an unreachable contact address in there.
(Someone did, once. It claimed a `.gov.in` address. See commit `8ffa1a4`.)

Retrying a *timeout* is fine — it's the same request, asked again, nothing
varied. Retrying a *403* is not. The tests pin that distinction.

### What the audit found

The brief named five airlines and "leading OTAs". Most of them disallow exactly
the fare paths an index needs:

| Source | Verdict | Basis |
|---|---|---|
| **Air India** | ✅ collect | fare search not disallowed; AI bots explicitly `Allow: *` |
| **Yatra** (OTA) | ✅ collect | flight search not disallowed; `Crawl-delay: 5` |
| **EaseMyTrip** (OTA) | ✅ collect | fare search not disallowed |
| SpiceJet | ❌ | `/api/v1` — the endpoint the UI calls for fares — is disallowed |
| IndiGo | ❌ | `Disallow: /booking/*`, `/book/*` |
| Air India Express | ❌ | `Disallow: /flight-availability` |
| Akasa Air | ❌ | robots.txt returns HTTP 403 — policy unreadable, fail closed |
| Cleartrip | ❌ | `Disallow: /flights/search*` |
| MakeMyTrip | ❌ | robots.txt fetch times out — policy unknown, fail closed |

Three of nine. Every design decision downstream — source inside the cell,
class-mean imputation, published coverage — exists because the index has to stay
honest on coverage this sparse and this uneven.

The real long-run fix is **data access, not better scraping**: partner feeds, GDS
transaction data, or a statutory reporting requirement under the Collection of
Statistics Act. A partner feed drops in as one more adapter and the index engine
doesn't change at all.

### A robots.txt parser bug worth knowing about

Python's own `urllib.robotparser` implements neither wildcards nor full-URL
directives, and it fails **permissive** — it says "allowed" when the answer is
"disallowed":

| Directive | stdlib says | correct answer |
|---|---|---|
| IndiGo `Disallow: /booking/*` | ALLOW | **DISALLOW** |
| SpiceJet `Disallow: https://www.spicejet.com/api/v1` | ALLOW | **DISALLOW** |

A collector built on the stdlib parser would believe it had permission it does
not have. `apix/compliance/rfc9309.py` implements RFC 9309 properly, and
`test_stdlib_parser_would_have_been_wrong` pins the difference so nobody
"simplifies" it back.

---

## 9. The website

| Route | What it serves |
|---|---|
| `/` | index chart, stat tiles, advance-purchase curve, route × window fare matrix |
| `/compliance` | the robots.txt audit from the database, the stdlib bug, the collection log |
| `/methodology` | `METHODOLOGY.md`, rendered |
| `/api/index/{daily\|weekly\|monthly}` | index series + provenance. `?start=&end=&includeFailed=` |
| `/api/inflation/{frequency}?periods=` | period-over-period percent change |
| `/api/routes?on=` | observed fare matrix for one collection day |
| `/api/compliance` | source registry with verdicts and reasons |
| `/api/collection-log?limit=` | why a given day looks the way it does |
| `/api/health` | liveness + what data is loaded (503 when empty) |

Two things to know:

- **`fail` points are hidden by default.** `includeFailed=true` shows them. This
  is the filter that made the outage in §7 invisible.
- **Every response carrying a number also carries its provenance**, and any
  series containing simulated quotes is flagged `synthetic` with a warning that
  cannot be switched off.

TypeScript is strict with `noUncheckedIndexedAccess`. `npm run build` passes with
`DATABASE_URL` unset, so a deploy can't fail on database reachability.

---

## 10. Testing

74 tests, ~12 seconds. `python -m pytest -q`.

The index tests use price paths whose true movement is **worked out by hand**, so
they check correctness rather than re-asserting whatever the implementation
happens to do:

- uniform inflation recovered exactly
- a hand-computed weighted geometric mean matched
- a cell entering contributes no movement; a cell leaving is imputed, not dropped
- imputation draws from the cell's own stratum, not the global mean
- chaining stays drift-free under constant coverage on a deliberately
  oscillating path
- total non-response carries the index flat and flags `fail`

End to end on a 90-day synthetic stream with known drift, seasonality, a +12%
shock and 6% non-response, the engine recovers the true path to **0.05% at the
endpoint**.

The other suites pin the things that broke in production: the robots gate's
fail-closed behaviour and its refusal/timeout distinction
(`test_compliance.py`, `test_publication_guards.py`), where a collection run
writes (`test_collection_target.py`), and what the pipeline refuses to publish
(`test_publication_guards.py`).

---

## 11. Honest status

**This is a prototype.** It works end to end and it is verified against ground
truth. It is *not* a publishable statistic. Before it could be:

1. Placeholder weights → actual DGCA origin-destination traffic and market share
2. Assumed booking-lead weights → industry/GDS data, and the joint
   O-D × lead-time distribution rather than the independence assumption we make now
3. Partner feeds for the carriers whose sites exclude crawling
4. A measured direct-vs-OTA channel split (the source weight split is equal-weight today)
5. Seasonal adjustment and a published revision policy
6. Independent replication from the raw quote archive

Anything produced by `scripts/simulate_history.py` or `seed_postgres.py --days`
is **synthetic**. The API flags it, the dashboard banners it, and the source ids
start with `sim_`.
