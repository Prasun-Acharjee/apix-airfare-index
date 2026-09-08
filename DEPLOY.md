# Deploying APIx

Two moving parts, deliberately separated:

| Part | What it does | Where it runs |
|---|---|---|
| **Next.js app** (`web/`) | Reads Postgres, serves the dashboard and API | Vercel (serverless) |
| **Python worker** (`apix/`, `scripts/`) | Scrapes, normalises, computes the index, writes Postgres | GitHub Actions (scheduled) |

They never talk to each other — only to the same database. The scraper needs a
real browser, a long-running process and a five-second-per-host crawl delay, none
of which belongs in a serverless request handler.

---

## Path A — Vercel + Neon (recommended)

### 1. Database

Create a free Postgres at [neon.tech](https://neon.tech). From the dashboard copy
the **Pooled connection** string — it looks like:

```
postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require
```

Use the *pooled* one. Serverless functions open many short-lived connections and
will exhaust a direct connection limit.

### 2. Schema and first data

From the repository root:

```bash
export DATABASE_URL="postgresql://...your neon pooled string..."

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/seed_postgres.py --days 120           # applies schema, then synthetic demo data
```

The seeder runs `db/migrations/001_init.sql` itself, so no `psql` client is
needed. With one to hand you can apply the schema separately instead:
`psql "$DATABASE_URL" -f db/migrations/001_init.sql`. On Windows PowerShell the
first two lines are `$env:DATABASE_URL = "..."` and
`py -m venv .venv; .venv\Scripts\Activate.ps1`.

`seed_postgres.py` writes source ids prefixed `sim_`, and the site banners any
series containing them. To publish real collected data instead:

```bash
playwright install chromium
python scripts/audit_robots.py                       # confirm crawl policy first
python scripts/run_collection.py --db data/apix.db
python scripts/seed_postgres.py --from-sqlite data/apix.db
```

### 3. Deploy the site

Use the **Git integration**, not the CLI. It gives you deploy-on-push, which the
CLI path does not, and it is the only path where the Root Directory setting
below applies.

1. Push this repository to GitHub.
2. In Vercel: **Add New → Project → Import** your repository.
3. Set **Root Directory** to `web`. Leave the framework preset as Next.js and
   the build/output settings at their defaults.
4. Under **Environment Variables**, add `DATABASE_URL` (the pooled Neon string)
   for Production, Preview and Development.
5. Deploy.

> **Do not mix the two paths.** If you would rather use the CLI, run
> `vercel link` and `vercel --prod` **from inside `web/`** and leave Root
> Directory at its default — the CLI uploads your current directory, so setting
> Root Directory to `web` as well makes Vercel look for `web/web`. Pick one.

> **Note on the methodology page.** It renders `METHODOLOGY.md` from the repo
> root, which sits outside `web/`. `web/src/content/methodology.md` is committed
> so the page works with Root Directory set to `web`.
> `web/scripts/sync-docs.mjs` refreshes that copy on every local build — commit
> the result when you edit the methodology.

The build does **not** need `DATABASE_URL`: every database-backed route is
rendered per request, so a deploy cannot fail because the database is asleep or
firewalled. It is needed at runtime.

### 4. Schedule collection

Add `DATABASE_URL` as a repository secret
(*Settings → Secrets and variables → Actions → New repository secret*).
`.github/workflows/collect.yml` then runs daily at 02:30 UTC (08:00 IST). It:

1. runs the test suite, and stops if the index engine is broken;
2. reports which sources this runner can reach (never fails the run — see
   *Runner network* below);
3. re-audits robots.txt, and stops if any site's crawl policy has changed;
4. collects — writing raw quotes **directly to Postgres**;
5. rebuilds the index over the **entire accumulated history**, and publishes it
   only if the newest point clears the quality thresholds;
6. prints the last five index points so the run log shows what is actually live.

Trigger it by hand from the Actions tab; use the `dry_run` input to audit only.

> **Why the history lives in Postgres.** The index is chained: each point is the
> previous point times a link computed from cells present in *both* periods. A
> runner's filesystem is discarded after every job, so a collector writing to a
> local SQLite file would start empty each day, and an index rebuilt from a
> single day is just the base period — the published series would silently reset
> to 100 every morning. The rebuild refuses to run on fewer than two collection
> days for the same reason.

**The first run will fail, and that is correct.** With one day of quotes there is
no link to compute, so `seed_postgres.py --from-postgres` exits non-zero rather
than overwriting the series. The second day's run succeeds and every run after it
extends the series. If you want the site populated immediately, seed the
synthetic history first (step 2) and let real collection accumulate alongside it —
or wait two days.

### 5. Runner network

**GitHub-hosted runners cannot reach every source.** From `ubuntu-latest`,
`airindia.com` and `yatra.com` time out on every robots.txt read. The gate fails
closed, so both sources return zero quotes on every run — not because those sites
disallow us (their policies permit the fare paths) but because the network
between GitHub and them does not carry the request.

The basket is narrowed to EaseMyTrip alone as a result (`config/basket.yaml`,
*Source scope*) — a real but reduced, single-channel index.

Narrowing the basket did not, on its own, make the index publish again. The
binding constraint is EaseMyTrip's own success rate: it serves a handful of
requests and then returns 403/429, and after three consecutive blocks the runner
stops that source for the day. A day where it answers three requests observes
about 15 of its ~324 cells and imputes the rest — 91%, withheld. A day where it
runs for eight minutes before blocking publishes at 45%. Moving to a network the
sites answer is worth trying for this too, not only for the two timed-out hosts:
a 403 served to a datacenter IP is a plausible part of the same picture.

**Getting them back.** Run the collector from a network those hosts answer.
Qualify a candidate machine before you commit to it:

```bash
python scripts/check_reachability.py
python scripts/check_reachability.py --only air_india,yatra --attempts 5
```

It fetches robots.txt and nothing else — no fare pages — so it is safe to run
repeatedly from anywhere. Read the verdicts as:

| verdict | meaning | worth moving hosts? |
|---|---|---|
| `readable` | policy read successfully | already fine here |
| `unreachable` | the network between you and them | **yes** — this is the fixable case |
| `refused` | HTTP 403/429: the operator declining automated clients | no. Same answer anywhere |

Once a host reports `readable` for the sources you need:

1. Register it as a self-hosted runner
   (*Settings → Actions → Runners → New self-hosted runner*), giving it a label
   such as `apix-collector`. It needs Python 3.11 and Chromium via
   `playwright install --with-deps chromium`.
2. Set the repository **variable** `COLLECTOR_RUNNER` to that label
   (*Settings → Secrets and variables → Actions → Variables*). The workflow reads
   `runs-on: ${{ vars.COLLECTOR_RUNNER || 'ubuntu-latest' }}`, so leaving it unset
   keeps the GitHub-hosted default and nothing else changes.
3. Watch the *Report which sources this runner can reach* step on the next run.
4. When `air_india` and `yatra` come back `readable` **and** the collection step
   shows non-zero quotes for them, widen the basket again: delete the `active`
   key under `sources:` in `config/basket.yaml`. Until you do, their quotes are
   collected and archived but carry no weight.

A self-hosted runner executes repository code on your machine. This repository is
public, so anyone opening a pull request could propose a workflow change — use
the runner only on a machine you are willing to expose, and keep
*Settings → Actions → Fork pull request workflows* set to require approval.

The same reasoning applies to any other host you run the collector from: a small
VPS on a cron schedule, or your own laptop running `scripts/run_collection.py`
with `DATABASE_URL` set, works identically. The collector only ever writes to
Postgres, so where it runs is free.

---

## Path B — self-hosted with Docker

```bash
cp web/.env.example .env          # set POSTGRES_PASSWORD
docker compose up -d db web
docker compose run --rm collector python scripts/seed_postgres.py --days 120
```

The site is on `http://localhost:3000`. The schema is applied automatically —
`db/migrations/` is mounted into the Postgres entrypoint. The `collector`
service is a one-shot container under the `tools` profile; run it from host cron,
or keep the GitHub Actions workflow pointed at this database.

---

## Local development

```bash
# Postgres (any instance will do)
createdb apix
export DATABASE_URL="postgresql://localhost/apix"

# Python worker
pip install -r requirements.txt
python -m pytest -q
python scripts/seed_postgres.py --days 120

# Web
cd web
cp .env.example .env.local        # set DATABASE_URL
npm install
npm run dev                       # http://localhost:3000
```

Useful checks:

```bash
npm run typecheck   # tsc --noEmit, strict + noUncheckedIndexedAccess
npm run lint
npm run build       # must pass with DATABASE_URL unset
```

---

## Environment variables

| Variable | Where | Required | Notes |
|---|---|---|---|
| `DATABASE_URL` | web runtime | yes | Postgres connection string. Use the **pooled** endpoint on Neon. |
| `DATABASE_URL` | Actions secret | yes | Same database; the worker writes to it. |
| `POSTGRES_PASSWORD` | docker compose | no | Defaults to `apix`. Change it before exposing the port. |

`DATABASE_URL` is never needed at build time on any path.

---

## Operational notes

- **Cost.** Neon free tier and Vercel Hobby are sufficient for this dataset
  (~100k cell prices, ~150 index points). GitHub Actions minutes are free for
  public repositories.
- **The database is the contract.** `db/migrations/001_init.sql` is the single
  source of truth; the Python dataclasses and the TypeScript row types are both
  written against it. Change the SQL first.
- **Migrations are manual and additive.** Add `002_*.sql` rather than editing
  `001`. There is no automatic migration on boot: an index that has to be
  reproducible years later should not have its schema mutated by a deploy.
- **Caching.** Pages and API routes render per request and set
  `Cache-Control: s-maxage=300, stale-while-revalidate=3600`, so Vercel's edge
  serves most traffic without touching Postgres. The pipeline writes at most
  once a day, so five minutes is generous.
- **If the site shows "No index data"**, the app reached Postgres but found an
  empty `index_point` table — run the seeder against that same `DATABASE_URL`.
  `/api/health` returns 503 with the reason.
