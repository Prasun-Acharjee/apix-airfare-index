# APIx — Methodology

*Prototype Real-time Airfare Price Index for the CPI Transport & Communication sub-group.*

---

## 1. What is being measured

The index measures the change over time in the **all-in fare a consumer pays** for
a domestic economy seat, holding constant the route, the carrier, the number of
days booked ahead, and the sales channel.

The price concept is the acquisition price: base fare + GST + regulated airport
charges (UDF/PSF/ASF) + non-optional carrier surcharges. Statutory rate changes
are genuine price changes to the household and are **not** netted out. Optional
ancillaries — seat selection, extra baggage, meals, priority boarding, insurance —
are excluded, because including them would make the index track the booking site's
default checkbox state rather than the fare.

`base_inr` and `taxes_inr` are retained per quote so an **ex-tax variant** can be
published beside the headline. That is the series a monetary-policy user wants when
separating a GST change from an underlying fare movement.

---

## 2. The item, and why the source is part of it

The unit that is matched across time — the "item" — is:

```
cell = (source, route, carrier, advance-purchase window, cabin)
```

Airfares have no persistent SKU. A seat sold today is not the same good as a seat
sold tomorrow, and the same flight carries a dozen simultaneous prices. The cell is
the closest stable analogue: it holds constant everything that legitimately makes
one fare different from another, so that what is left is price movement.

**Source is inside the cell on purpose.** An OTA quote and an airline-direct quote
for nominally the same seat are different prices: the OTA applies its own markup and
is often shown different fare inventory. If the source were outside the cell, a
source dropping in or out of the collection would inject a step change into the
index that is pure composition, not inflation. With source inside, the index only
ever compares Yatra-6E-DEL-BOM-T+7 to itself over time.

---

## 3. Elementary aggregate — the geometric mean

Many quotes fall into one cell on a given day (several flights, several fare
buckets). They are collapsed with a **geometric mean**, not an arithmetic one.

Airfare distributions within a cell are strongly right-skewed: a handful of
last-seat fares sit at several multiples of the modal fare. Under an arithmetic
mean, one such quote drags the whole cell, and the index would then report
inflation whenever fare *dispersion* widened — even with no change in what a
typical passenger pays. The geometric mean is also the form that makes the chained
construction below transitive.

This is asserted as a test, not just claimed: `test_geometric_mean_resists_a_last_seat_outlier`.

---

## 4. Upper-level aggregation — chained weighted geometric (Young)

For consecutive periods *t−1* and *t*:

```
R_t = exp( Σ_c  w̃_c · ln( p_{c,t} / p_{c,t−1} ) )
I_t = I_{t−1} · R_t
```

where *c* runs over cells present in **both** periods (after imputation) and `w̃_c`
is the basket weight of *c* renormalised over that matched set.

**Why chained rather than fixed-base Laspeyres.** Airline coverage churns
constantly: a carrier drops a pair, an OTA stops quoting a fare family, a window
opens. A fixed-base index must answer "what was this cell's price in the base
period?" for cells that did not exist then. A chained index never asks. A cell
contributes from its second observation onward and stops when it disappears, and
neither event moves the index by itself. Both properties are tested
(`test_cell_entry_does_not_move_the_index`, `test_cell_exit_is_imputed_not_dropped`).

**The cost of chaining is drift.** With volatile, oscillating prices — which
airfares emphatically are — repeated chaining can wander away from a direct
comparison of the endpoints. Two controls:

1. The geometric form is transitive under a stable matched set, so drift is bounded
   by matched-set churn rather than by volatility. Asserted directly in
   `test_chaining_is_drift_free_under_constant_coverage`, on a deliberately
   oscillating price path.
2. The **published monthly figure is a direct month-over-month comparison** of
   monthly cell averages — not a product of thirty daily links. The daily series is
   for monitoring; the monthly series is the statistic.

### Weights

| Stratum | Weight | Source |
|---|---|---|
| Route | share of domestic O-D passengers | DGCA monthly Traffic Statistics |
| Carrier | domestic market share | DGCA monthly |
| Advance window | share of bookings at each lead time | industry/GDS; currently assumed |
| Source | equal split across sources quoting that carrier | assumed |

Cell weight = route × carrier × window ÷ (number of sources quoting that carrier).

**Known weakness.** Multiplying the three strata assumes independence, and that is
not true: leisure routes book earlier than business routes. The honest fix is an
O-D × lead-time cross-tabulation from DGCA or a GDS feed, replacing the product with
the joint distribution. `Basket.cell_weight` is the single place that changes.

**The weights shipped in `config/basket.yaml` are placeholders** shaped to the
published ordering of Indian domestic traffic. They are not DGCA figures and must
be replaced before any published run.

---

## 5. Non-response and imputation

A cell can vanish for reasons that carry no price signal: the site declined the
request, the collector errored, the route was not served. If those cells simply drop
out of the matched sample, the index silently reweights toward whatever responded —
and **non-response starts to look like inflation.**

Missing cells are therefore imputed by the movement of the cells around them, with a
donor hierarchy, most specific first:

1. **class-mean** — the cell's own stratum (route × window × cabin)
2. **route-mean** — all matched cells on the same route
3. **all-items** — the overall matched movement

The imputed price is carried forward so a cell that disappears for a few days rejoins
the matched sample on its return rather than re-entering as a new item.

Every index point publishes `coverage` and `imputation_share`, and a `quality` flag
that goes to `warn` at 35% imputation and `fail` at 60%. The API excludes `fail`
points by default. `test_imputation_uses_own_stratum_not_global_mean` verifies the
donor hierarchy is actually being used and not quietly collapsing to the global mean.

**Warm-up.** A cell missing on day 1 has no previous price and cannot be imputed, so
coverage starts below 100% and climbs over roughly three days at a 6% non-response
rate. The published series should begin a few days after collection starts.

---

## 6. Collection, and what this project refuses to do

The problem statement asks for scraping that handles "dynamic CAPTCHAs, anti-bot
measures, IP rotation, and session management." **This implementation does not do
those things, and the omission is deliberate.**

A CAPTCHA, a 403, a 429 or a bot challenge is the site operator declining the
request. Defeating that is unauthorised access to a computer resource, it breaches
the terms of service of every site in scope, and — decisively for this use — it would
make the resulting numbers inadmissible as official statistics. An index that
underpins monetary policy cannot rest on data obtained by circumventing access
controls. The statement's own words are "ethically-designed"; the two halves of the
requirement are in tension and this project resolves them toward the first.

What is implemented instead:

- **A robots.txt gate on every outbound request, failing closed.** If robots.txt
  cannot be read, or the directive is ambiguous, nothing is fetched.
- **JavaScript rendering via a real browser engine** (Playwright/Chromium). This is
  what "handle JS-rendered pages" actually requires. It is not a stealth browser: no
  fingerprint patching, no automation-flag hiding.
- **Politeness**: honest identifying user-agent with a contact address, per-host
  crawl-delay with a 5s floor, an hourly request ceiling, and an abort after three
  consecutive block responses from a source.
- **Blocks recorded, not evaded.** A refusal becomes a `BLOCKED_BY_SITE` row in
  `collection_log` and is handled by imputation.

A test (`test_codebase_contains_no_evasion_machinery`) fails the build if CAPTCHA
solvers, stealth plugins, or proxy-rotation libraries are ever added.

### A parser bug worth knowing about

Python's standard `urllib.robotparser` matches rules with `path.startswith(rule)`.
It implements neither wildcards nor full-URL directives, and both failures are in
the **permissive** direction:

| Directive | stdlib verdict | correct verdict |
|---|---|---|
| IndiGo `Disallow: /booking/*` | ALLOW | **DISALLOW** |
| SpiceJet `Disallow: https://www.spicejet.com/api/v1` | ALLOW | **DISALLOW** |

A collector built on the stdlib parser would have believed it had permission to
scrape IndiGo's entire booking tree and SpiceJet's fare API. `apix/compliance/rfc9309.py`
implements RFC 9309 properly — `*` wildcards, `$` end-anchor, longest-match-wins with
allow winning ties, user-agent group selection — and `test_stdlib_parser_would_have_been_wrong`
pins the difference.

### Audit result (2026-08-25)

| Source | Verdict | Basis |
|---|---|---|
| **Air India** | collect | Fare search not disallowed; ClaudeBot/GPTBot et al. explicitly `Allow: *` |
| **Yatra** (OTA) | collect | Flight search not disallowed; ClaudeBot permitted, `Crawl-delay: 5` |
| SpiceJet | excluded | `/api/v1` — the fare endpoint the UI calls — is disallowed |
| IndiGo | excluded | `Disallow: /booking/*`, `/book/*` |
| Air India Express | excluded | `Disallow: /flight-availability` |
| Akasa Air | excluded | robots.txt returns HTTP 403; policy unreadable, fail closed |
| Cleartrip | excluded | `Disallow: /flights/search*` |
| MakeMyTrip | excluded | robots.txt fetch timed out; policy unknown, fail closed |

**Two of eight sources are cleanly collectable.** That is the honest finding, and it
is the single most important input to the design.

---

## 7. Coverage bias — the real limitation

IndiGo carries roughly 60% of Indian domestic passengers and its site cannot be
collected. Air India Express and Akasa cannot either. Direct-channel coverage is
therefore heavily skewed toward one carrier.

The OTA partially rescues this: Yatra quotes every major carrier, so IndiGo *fares*
are observable even though IndiGo's *site* is not. But an OTA quote is not an
airline-direct quote, and channel mix is not measured. Concretely:

- If OTA markups move differently from direct fares, the index tracks the OTA.
- If a carrier restricts OTA inventory, its cells thin out and lean on imputation.
- The equal source-weight split is an assumption with no evidence behind it.

**None of this is fixable by better scraping.** It is fixable by data access:

1. **Partner/commercial feeds** from the carriers whose robots.txt excludes crawling.
2. **GDS/ARC-type transaction data** — which would give actual transaction prices and
   real booking-lead weights, replacing two assumptions at once.
3. **A statutory reporting requirement** under the Collection of Statistics Act, which
   is the mechanism a national statistical office actually has for this problem.

For an official CPI component, (3) is the right answer and web scraping is the
interim. The prototype is built so that a partner feed drops in as another adapter
without touching the index engine.

---

## 8. Verification

The index engine is tested against price paths whose true movement is constructed by
hand, so the tests check correctness rather than merely re-asserting the implementation:

- uniform inflation is recovered exactly
- a hand-computed weighted geometric mean is matched
- cell entry contributes no movement; cell exit is imputed, not dropped
- imputation draws from the cell's own stratum
- chaining is drift-free under constant coverage, on an oscillating path
- total non-response carries the index flat and flags `fail`

End-to-end, a 90-day synthetic quote stream with a known drift, seasonality, a +12%
shock and 6% non-response is recovered to **within 0.05% at the endpoint** and under
5% at any point, with no systematic drift.

---

## 9. Open items before this could be published

1. Replace placeholder weights with DGCA O-D passenger traffic and market share.
2. Replace assumed booking-lead weights with industry or GDS data; move to a joint
   O-D × lead-time distribution.
3. Secure partner feeds for IndiGo, Akasa, Air India Express, SpiceJet.
4. Establish a channel-share split (direct vs OTA) to replace the equal split.
5. Seasonal adjustment and a published revision policy.
6. Decide the treatment of ancillary unbundling — if carriers shift fare into
   baggage fees, an all-in fare that excludes ancillaries understates inflation.
7. Basket revision and chain-linking policy at annual review.
8. Independent replication of the index from the raw quote archive.
