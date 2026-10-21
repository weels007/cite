# Cite

> **Prediction markets settled by evidence, not by assertion.**
> *Every settlement has to quote the web. The contract checks that the quotes are real.*

<!-- Project name: Cite. The repository folder is still `prediction-markets`
     because it was created before the name was chosen; only the contract,
     the class and the docs carry the product name. -->

Bets on future events, settled automatically by an AI-validator committee that
reads the public web inside a non-deterministic block and reaches consensus
under the Equivalence Principle. Nobody is trusted, including the node that
produced the answer.

```
        create_market()          place_bet()            resolve_market()
 creator ──────────────▶ question +  bettors ──────▶   leader reads the web
 criteria + sources     criteria + sources           and asks an LLM to
                                                       extract + quote
                                                          │
                              validators re-read ◀────────┘
                              the sources and compare
                              only the decision fields
                                                          │
                                          consensus ──────┴──────▶ outcome
                                                       + citation trail
```

---

## 1. What we predict

**The short answer: we predict the weather.**

Not "what will happen" (a forecast, which is a guess) but **"what will the
official record say about a specific place, on a specific day"** — a document,
which can be checked. That distinction is the whole product.

A weather market is only as good as its *measurement specification*. Get that
wrong and no amount of AI consensus helps: the committee will simply split, and
the market will never settle. So Cite treats the measurement spec as part of
the market definition, locked at creation time.

### The five things a weather market has to lock

| lock | why it matters |
|---|---|
| **the station** | "Jakarta" is not a measurement. There are at least three stations inside Jakarta alone: `ID000096745` JAKARTA/OBSERVATORY (8 m), `IDM00096741` TANJUNG PRIOK (2 m), `IDM00096749` SOEKARNO HATTA (10.4 m) — and BOGOR sits at 250 m. Each reads a different number. |
| **the variable** | daily maximum, daily minimum, total precipitation, mean — not interchangeable |
| **the unit and scale** | NOAA GHCN prints tenths of a degree (`"  278"` = 27.8 °C), ERA5 prints `33.4`. Both become exact integers, but only if the scale is part of the spec |
| **the day boundary** | the local civil day at the station, in the station's timezone — not the UTC day. Kolkata is UTC+05:30, Sydney is UTC+11, Mexico City is UTC−06:00 |
| **the authoritative publisher** | this is the sharpest one. For Jakarta on 10 October 2026, ERA5 says **33.4 °C** and NASA POWER says **30.98 °C**. Both are correct; they are different products. The market has to name which one decides. |

### The two tiers

| tier | example | what resolves it |
|---|---|---|
| **measurement** | "will the maximum temperature in Jakarta on 14 Dec 2026 be at least 33.0 °C?" | the locked spec, read from the locked source — **Cite's core** |
| **consequence** | "will Poland record at least 5 orange wind warning areas on 14 Dec?" | official alert feeds — **where Cite's AI consensus earns its keep** |

The measurement tier is the trust anchor: it is objective, reproducible and
cheap to verify. The consequence tier is where the market becomes interesting —
counting the qualifying warning areas in a feed and deciding which entries
count is exactly the judgement a single oracle cannot make and Cite's
committee can.

### Tier 2: two evidence groups

A tier 2 market reads two groups of pages, and the contract keeps them apart:

```
MEASUREMENT SOURCES   the locked weather facts, from the allowlisted publishers
EVENT SOURCES         the official reports about the consequences, from their own allowlist
```

Three rules make the two-stage resolution safe:

1. **The metric has to be cited from the source the market designated as
   authoritative.** `measurement.metric_source` says which group provides the
   value: `measurement` (a reading) or `event` (a count of records).
2. **A consequence can never be inferred from a measurement.** If the market
   has event sources, the decision must be supported by at least one verified
   citation from them, or the market does not settle.
3. **The evidence rule is asymmetric on purpose.** The measurement group is a
   corroboration device and needs **two** independent pages, because two
   publishers have to agree on the reading. The event group is a *single
   authoritative record* — one official feed is the whole record — and needs
   **one**.

### The event sources that were checked

| source | what it is | what it gives |
|---|---|---|
| **NWS Alerts API** (`api.weather.gov/alerts`) | the US National Weather Service, JSON, queryable by date and area | every watch, warning and advisory with its event type, severity and polygon |
| **MeteoAlarm** (`feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-<country>`) | the European alerting network, CAP/Atom | per-area entries with `cap:event`, `cap:severity`, `cap:areaDesc`, `cap:onset`, `cap:status` |

Both were fetched live and their structure confirmed. One operational detail
matters a lot: **the MeteoAlarm feed only keeps roughly two days of entries**,
so a market reading it has to resolve within a day or two of the event. The
NWS API accepts an arbitrary date range and has no such limit.

### The tier 2 launch set

`markets/tier2_markets.json`, five markets:

| id | asks | shape |
|---|---|---|
| `t2-nws-severe-ny-2026-12-14` | at least 2 severe thunderstorm warnings covering New York State | metric, counted from the event feed |
| `t2-nws-any-warning-ny-2026-12-14` | any watch, warning or advisory in force for New York State | choice |
| `t2-nyc-hot-and-warning-2026-12-14` | New York reaches 8.0 °C **and** a warning is in force | choice, **both** groups |
| `t2-meteoalarm-poland-orange-wind-2026-12-14` | at least 5 areas with an orange wind warning in Poland | metric, counted from the event feed |
| `t2-meteoalarm-germany-frost-2026-12-14` | any frost warning for Germany | choice |

---

## 2. Global by construction

**Yes — and the architecture was already location agnostic.** The measurement
spec is *data*, not code: the station, the coordinates, the timezone and the
unit are parameters of the market. The sources are global. The committee reads
pages in any language.

`markets/stations.json` is the registry that makes it work. Eighteen cities,
every GHCN id taken from the official NOAA inventory and every coordinate
checked against the live API:

| | cities | notes |
|---|---|---|
| Asia | Jakarta, Tokyo, Seoul, Singapore, Mumbai, Delhi, Dubai | |
| Europe | London, Berlin, Moscow, Santiago (CL) | |
| Americas | New York, Toronto, São Paulo, Mexico City | |
| Africa & Oceania | Cairo, Nairobi, Sydney | |

`scripts/build_seed_markets.py` turns the registry into the market board, so
the registry stays the single source of truth. The result is **41 markets across
18 cities and 15 countries**.

### Three things that had to be curated, not engineered

**1. The canonical station per city.** Every city has several candidate
stations and no default. The registry names one and lists the alternatives, so
a dispute about "the temperature in Berlin" is settled by the registry instead
of by an argument.

**2. Thresholds from local climatology.** "35 °C" is unremarkable in Jakarta
and impossible in Dublin. The registry stores the observed ERA5 window
(`observed`, real measurements for 2026-10-10..14) and a seed threshold. The
seed thresholds are now calibrated, not guessed: `scripts/calibrate_thresholds.py`
pulls ten years of ERA5 normals for the market window and writes the
distribution into the registry, and `scripts/build_seed_markets.py` turns the
registry into the board. Thirty year normals would be better still, and the
ERA5 archive can fetch them in a single call.

**3. Which sources actually publish for that country.** This is where the
verification paid off, and the answer is not what you would hope:

| station | window 2026-10-05..12 | verdict |
|---|---|---|
| `USW00094728` New York | 8 days of data | live |
| `ASN00066037` Sydney | 4 days of data | live |
| `JA000047662` Tokyo | **nothing** | not publishing |
| `GM000003319` Berlin | **nothing** | not publishing |
| `ID000096745` Jakarta | **nothing** for all of 2026 | not publishing |

GHCN-Daily's international feed is **not** near-real-time. So the global
backbone has to be the reanalysis pair (ERA5 + NASA POWER), which cover every
coordinate on earth consistently, and the station record becomes a *per station
upgrade* where the national network still publishes. The registry is what tells
you which is which.

### One bug this shook out

The deterministic page gate matched the market question's keywords against the
page. The stopword list is English, so a market whose question is in
Indonesian or Japanese produced a keyword list that no JSON page could ever
match — every market outside English would have voided itself.

The fix is `measurement.match_terms`: the date and the variable name the source
is *guaranteed* to print, regardless of the language of the question. The
generated board ships them, and `test_a_market_in_another_language_still_finds_its_page`
pins the behaviour down.

### What does not globalise

* **Regulation.** Betting on weather is a licensed activity in most
  jurisdictions. Geoblocking and licensing are a business problem, not a
  contract problem.
* **The interface.** The board is language neutral; the UI is not.
* **Threshold calibration.** Local normals per city, forever. It is a data
  chore, and it is the one thing that cannot be automated away.

---

## 3. It runs on a live network

Cite runs on **one contract**, deployed on studionet. The demo markets have
been resolved by the real validator committee, with real web pages and real
LLM calls. `deployments.json` has the address and the full record.

```
contract : 0xeA384Ef9a0d8F87314ddb40d58F0183e69E0707b   (studionet, chain 61999)
wallets  : tester1 (creator) / tester2 (bettor), read from
           D:\Genlayer-project\weels\wallet, which is never modified
```

| market | shape | result |
|---|---|---|
| Jakarta max temp at least 33.0 degrees Celsius | tier 1, metric | **resolved, Yes**, confidence 100, metric 346, 1 citation |
| at least 1 NWS alert for New York State | tier 2, metric from the event group | **resolved, Yes**, confidence 90, metric 1, 5 event citations |
| New York at least 20 degrees Celsius **and** a warning in force | tier 2, two stages | **resolved, Yes**, confidence 97, 4 citations, 2 domains |
| an orange or red disaster affecting Australia | tier 2, counted by the contract | **resolved, No**, metric 0 |

The committee is genuinely mixed — gpt-5.4, claude-sonnet-4.6,
gemini-3-flash-preview, gpt-oss-120b, grok, qwen and glm — with three
agreeing on every round.

### What the committee actually did

**Tier 1, the cross publisher divergence, handled.** ERA5 reported **34.6
degrees Celsius** and NASA POWER reported **31.6** for the same place and day.
The committee noticed, said so, and applied the locked authoritative source:

> Source 2 reports a lower value (31.6), but per the MEASUREMENT
> SPECIFICATION, only Source 1 provides the authoritative value for resolution.

The stored citation is the verbatim line out of the ERA5 response, checked by
the contract against the fetched page:

```
"daily":{"time":["2026-10-14"],"temperature_2m_max":[34.6]}
```

**Tier 2, two stages, both conditions and both cited.**

> Resolve Yes. The authoritative measurement source (Source 1) gives a daily
> maximum temperature of 24.7 degrees Celsius for 2026-10-14, which is at
> least 20.0 degrees Celsius. **The event source (Source 3) shows at least one
> NWS alert for New York on 2026-10-14**: a Special Weather Statement
> affecting NY zones in Suffolk County, with effective and expiry times on that
> day. **That satisfies both required conditions.**

### Three things running it on a real network taught us

**1. A value transfer is asynchronous.** The money leaves the contract only when
the child transaction is activated, not when it is emitted. The strict equality
invariant therefore cannot hold while a payout is in flight. The accounting
reports two properties instead: `covered` (the contract holds at least
everything it owes, true at every point in time) and `reconciled` (the books
match the balance exactly, true once nothing is in flight).

**2. A retry must not put a second transfer in flight.** A second `claim` on a
payout that is still in flight would emit a second transfer and could overdraw
the contract. A retry is therefore only allowed once a failure came after the
last attempt, and the contract tracks that per position. Measured on chain: the
second claim was refused and `in_flight` stayed at 198 GEN instead of 396.

**3. Value can arrive that no market accounts for.** A transaction that is
rejected after its value was credited leaves money behind. The owner can
`sweep_stranded()` it after a grace period, so no value is ever stuck.

### Tier 2: consequences, counted by the contract

Tier 1 measures the weather. Tier 2 asks what the weather *did* — and the
answer is a record, not a number: a disaster logged in a registry, a warning
issued, a service suspended.

The example that ran on chain is the sharpest one, because the feed is
structured:

```
https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?fromDate=...&toDate=...
```

GDACS is the Joint Research Centre of the European Commission's global
disaster registry. It answers a date range with GeoJSON, and every record
carries an alert level, the countries it affected, a numeric severity and the
dates it was active for.

**The contract counts the records, the model does not.** Counting is the one
thing a language model is bad at, and a market that settles on a miscounted
list is worthless. So the market carries machine-checkable rules:

```json
"count_rules": {
  "eventtype": ["FL"],
  "alertlevel": ["Orange", "Red"],
  "affected_iso3": ["IDN"]
}
```

The contract parses the feed, applies the rules and derives the outcome. The
model only has to quote the record it relied on, and that quote is verified
against the page. On chain, the model reported ninety-nine and the contract
counted two; the market settled on the contract's number.

The community runs the same idea on the same shape of source:

| source | what it records | how it is filtered |
|---|---|---|
| GDACS | global disasters, floods, cyclones, droughts, wildfires | `eventtype`, `alertlevel`, `affected_iso3`, `severity_min` |
| MeteoAlarm | European weather warnings in CAP format | the event type, the severity and the area |
| US National Weather Service | watches, warnings and advisories with their polygons | the event, the area and the time it is in force |

A note on retention: the alert feeds only keep the last few days, so a tier 2
market has to resolve shortly after the event. The GDACS API, in contrast, is
queryable by date range and keeps its history, which is what the Indonesia
markets in `markets/tier2_markets.json` use.

### Running it yourself

```bash
python scripts/calibrate_thresholds.py # ten years of ERA5 normals into the registry
python scripts/build_seed_markets.py   # the registry into the 46 market board
python scripts/demo_studionet.py       # create, bet, wait, resolve
python scripts/claim_demo.py           # claim, retry, confirm
python scripts/demo_tier2.py           # a consequence market, counted by the contract
python scripts/show_resolutions.py     # print the resolutions and the citations
```

## 4. The frontend

`frontend/` is a Next.js 14 app (App Router, TypeScript, Tailwind v3, shadcn
conventions) that talks to the deployed contract through `genlayer-js`.

| route | what it shows |
|---|---|
| `/` | the animated backdrop, the open board, how the last market was settled |
| `/markets` | the whole board, grouped by status, each settled card showing its number |
| `/markets/[id]` | the number behind the settlement, the measurement spec, the event spec, the odds, the bet panel, the citation trail |
| `/settlements` | every settlement with the quotes the committee relied on |

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

### Deploying it to Vercel

The app is a plain Next.js project with nothing that needs a build server, so
it goes up as it is.

| setting | value |
|---|---|
| root directory | `frontend` |
| framework preset | Next.js (pinned in `frontend/vercel.json`) |
| build command | `npm run build` |
| output | the default `.next` output |

Three environment variables, all public by nature, set on the project:

| variable | value |
|---|---|
| `NEXT_PUBLIC_CONTRACT_ADDRESS` | `0xeA384Ef9a0d8F87314ddb40d58F0183e69E0707b` |
| `NEXT_PUBLIC_RPC_URL` | `https://studio.genlayer.com/api` |
| `NEXT_PUBLIC_CHAIN_ID` | `61999` |

They have to be set for **Production and Preview**, because a
`NEXT_PUBLIC_` variable is written into the bundle at build time. A build
without them still succeeds, but the pages have no contract to read and stay
empty, so the variables are set before the first deploy, not after.

From the command line, after `vercel login`:

```bash
cd frontend
vercel link                                   # pick the project, root = frontend
vercel env add NEXT_PUBLIC_CONTRACT_ADDRESS production
vercel env add NEXT_PUBLIC_RPC_URL production
vercel env add NEXT_PUBLIC_CHAIN_ID production
vercel --prod
```

The chain id is read from the environment rather than hard coded, so the same
build can be pointed at a local network, which is what the integration tests
do.

Two things to know about the hosted network. It allows thirty requests a
minute and five hundred an hour, and every page reads the chain, so the
reads are cached for twenty seconds and a throttled read waits and tries
again instead of failing the page. And the pages are rendered per request
where they read live data, so the first request after a deploy is the slow
one.

### The number behind the settlement

This is the panel that makes a Tier 2 market legible. On the market page the
number is shown first, in the same slot as the outcome, and it always says
where it came from:

| situation | what the page says |
|---|---|
| a measurement market | `34.6` degrees Celsius, "counted by the committee, from the authoritative source" |
| a consequence market the contract counted | `3` records, "counted by the contract, counting the feed itself", plus the note that the committee was asked to quote, not to count |
| a consequence market the committee counted | `1` records, "counted by the committee, from the event feed" |
| a comparison market | the committee's decision, with a line saying the number is context, not the result |

The distinction matters. A reader must be able to tell, without reading the
source code, whether a number is something a model asserted or something the
chain computed. So the page never shows a bare number: it shows the number,
the unit, and the sentence that names the counter. And the citation trail
under it opens with a line explaining that those quotes are the records the
contract matched against its count rules.

No contract change was needed for any of this. "Counted by the contract" is
read off the measurement specification, which already carries the count rules,
so the interface tells the truth about the chain without asking the chain
again.

### The backdrop

`src/components/ui/modern-background-paths.tsx` draws a **printed weather
chart**, not a screensaver: a fixed graticule, hairline isobars, a cold front
with triangles, station plots and a radar sweep. The palette is ink, paper and
a single sodium accent, the way a weather bureau prints a synoptic chart.

| layer | what it stands for |
|---|---|
| **synoptic** | the locked measurement |
| **radar** | the field the committee reads |
| **stations** | the validators that have to agree |
| **wind** | how the evidence moves |

The cards are the product, not decoration: one is a **live market** with its
implied probability, the other is a **settlement** with the verified quote and
the publishers that corroborated it.

Three things the original prompt got wrong and that are fixed here:

* `Math.random()` during render would break hydration — the server and the
  browser would draw different paths. Every path now comes from a fixed seed.
* The `viewBox` had no `preserveAspectRatio`, so the drawing did not fill the
  viewport.
* The motion ignored `prefers-reduced-motion`.

### Wallets, without a fight

Several extensions inject into the same `window.ethereum`, and whichever
injected last takes the global. `src/lib/wallets.ts` collects every provider
from `window.ethereum.providers`, from the EIP 6963 announcements and from the
well known globals, lets the user pick one when there is more than one, and
then **locks that provider object**. Every later signing call uses the locked
object, and `accountsChanged` and `chainChanged` are only listened for on it.

The header also shows a warning when the wallet sits on the wrong chain.

### Why the pages were slow

Not the chain: **the node rate limits at thirty requests a minute**, and every
page used to ask it for the same numbers on every request. Two changes fixed
it:

* `src/lib/cache.ts` keeps the reads for twenty seconds and collapses the
  stampede while a request is in flight.
* The pages are ISR with `revalidate = 30` instead of `force-dynamic`, so they
  are prerendered and served from disk. `/settlements` is the exception: it
  reads the live chain on every request, because baking a settlement ledger
  into a build spends the RPC budget of a whole minute.
* Studionet allows **thirty requests a minute**, and a burst of page reads can
  cross that line. `src/lib/genlayer-client.ts` wraps every read in a retry
  that waits for the window the node suggests and tries again, so a throttled
  read slows a page down instead of breaking it.

Measured on the production build:

| page | cold | warm |
|---|---|---|
| `/` | 65 ms | 11–14 ms |
| `/markets` | 5 ms | 4–7 ms |
| `/settlements` | 5 ms | 4–6 ms |
| `/markets/[id]` | 4.3 s | 43–49 ms |

A write invalidates the cache and the page pulls itself again.

---

## 5. The three resolution shapes

| shape | the market asks | the committee extracts | the contract decides |
|---|---|---|---|
| `choice` | will Jakarta be hotter than Singapore | which outcome | accepts the validated index |
| `metric` | will the maximum temperature be at least 35.0 °C | one integer | `outcome = derive(metric)` |
| `metric` + window | will there be at least 5 launches between A and B | one integer, counted inside the window | `outcome = derive(metric)` |

### The launch set

`markets/seed_markets.json` holds **46 markets** built from the city registry in
`markets/stations.json` and the consequence set in `markets/tier2_markets.json`:

| group | count | shape | source |
|---|---|---|---|
| max temperature | 18 cities | metric ≥ threshold | Open-Meteo ERA5 (authoritative) + NASA POWER (corroboration) |
| daily rainfall | 17 cities | metric ≥ 200 tenths | Open-Meteo ERA5 + NASA POWER |
| cross-city comparison | 3 pairs | choice | Open-Meteo ERA5 ×2 |
| GDACS disaster registry | 3 | metric, count by the contract | `www.gdacs.org` |
| MeteoAlarm CAP | 1 | metric, count by the contract | `feeds.meteoalarm.org` |
| NWS alerts | 1 | metric, count by the contract | `api.weather.gov` |

Every source url was checked against the live service:

| source | what it is | unit |
|---|---|---|
| **NOAA GHCN-Daily** | official station observations, `www.ncei.noaa.gov/access/services/data/v1` | integers in tenths |
| **Open-Meteo archive** | ERA5 reanalysis grid, `archive-api.open-meteo.com` | one decimal |
| **NASA POWER** | GEOS-IT reanalysis grid, `power.larc.nasa.gov` | two decimals |
| **GDACS** | global disaster registry, orange and red events | records |
| **MeteoAlarm** | CAP alerting network across Europe | warning areas |
| **NWS** | US watches, warnings and advisories | alerts |

### Where the thresholds come from

A threshold that is a guess is a market that resolves for the wrong reason, so
none of them are guesses. `scripts/calibrate_thresholds.py` pulls the ERA5
daily maximum for 1–20 December across **2016–2025** for every city, in one
multi-location request per year, and writes the distribution back into the
registry:

| city | n | mean | p25 | p75 | threshold |
|---|---|---|---|---|---|
| Jakarta | 200 | 30.5 °C | 29.6 | 31.5 | **31.0 °C** |
| New York | 200 | 6.5 °C | 3.4 | 9.8 | **8.1 °C** |
| Tokyo | 200 | 12.1 °C | 9.7 | 14.5 | **13.3 °C** |
| Moscow | 200 | −2.2 °C | −4.7 | 1.1 | **0.0 °C** |

The threshold is the midpoint between the mean and the upper quartile, so a
Yes means "warmer than three days in four usually are", and a No means the day
was ordinary or cold. The numbers are reproducible: the script prints the same
table every run.

One case needed a decision rather than a formula. Moscow's calibrated
threshold is **−0.5 °C**, and the contract stores thresholds as unsigned
integers, so a negative threshold cannot exist on chain. In a city that cold
the interesting question is not "unusually warm" but "will it reach freezing
at all", so the Moscow market became *"will the maximum temperature in
Moscow on 14 December reach 0.0 °C, that is, will it touch freezing?"* — a
real question with a real answer, and a threshold the chain can hold.

### The rule for adding a market

A question qualifies when all four hold:

1. the ground truth can be written as one crisp, checkable line
2. the answer is only knowable at the deadline
3. answering it requires reading and combining sources
4. it is objective *given* the criteria

and it fails when:

* a price API settles it — use an oracle
* the criteria cannot be stated in a sentence — the validators will never agree
* the "right" answer depends on taste

### The honest risks

* **Cross-publisher divergence is real.** ERA5 and NASA POWER differ by more
  than 2 °C for the same Jakarta day. That is why the metric is read from the
  designated authoritative source only, and the others are corroboration. The
  corroborating source confirms *that the event happened*, never the number.
* **Liveness at the boundary.** In `metric` mode a leader that reads 35.1 and
  a validator that reads 35.2 agree, because both clear a threshold of 35.0.
  But 35.0 against a threshold of 35.0 does not. Keep thresholds off the
  rounding boundaries of the units you use.
* **Data availability is not uniform.** GHCN-Daily is reliable for the US and
  Europe but the Indonesian feed had no 2026 rows at the time of writing, and
  rows with a missing value come back as objects without the field. The
  resolution deadline has to leave room for the record to be published, and the
  spec has to say what a missing value means.
* **Reanalysis is not an observation.** ERA5 is a gridded model product, not a
  thermometer. It is reproducible and immutable, which is why it is a good
  anchor, but it is not what a person at the airport measured. A market that
  wants the observation has to name a station.
* **A citation gate can cost a settlement.** `require_citation` voids a market
  whose model paraphrased instead of quoting. That is the safe direction to
  fail in, but it is a real cost.

---

## 6. What Cite is for

Most prediction markets on a smart chain quietly cheat: the frontend computes
the answer, an API signs it, and the chain only stores it. That is a normal
backend with extra steps.

Cite uses GenLayer for exactly the one part that needs consensus — the
settlement — and draws the boundary explicitly:

| Layer | Owns |
|---|---|
| **Frontend / backend** | UI, auth, indexing, market discovery, cached odds, non-authoritative previews |
| **Cite contract** | The state transition that needs consensus: the evidence inputs, the validator comparison rule, the settlement, the appeal path, the escrow |
| **External sources** | Raw facts. Never trusted unless validators can re-fetch, normalize and compare them |

### The niche: aggregate and long-horizon markets

GenLayer is expensive and slow (a web fetch plus an LLM call per validator).
Spending that on *"will ETH be above $5000 on December 31st"* would be waste —
a price oracle does it cheaper and faster. Cite therefore targets questions
where the **resolution itself** is the hard part:

| Category | Example | Why it needs Cite |
|---|---|---|
| **Aggregate** | "Will this team win the league?" | The answer is a synthesis of dozens of match results. A plain oracle literally cannot compute it. |
| **Long-horizon** | "Will this company ship product X before Q3?" | The answer only becomes knowable at the deadline, and depends on evidence nobody predicted. |
| **Regulatory** | "Will the FDA approve this drug by year end?" | The criteria ("approved", "by when", "which drug") need judgment over documents. |
| **Delivery** | "Will this launch happen at least 3 times in 2026?" | Requires counting across sources. |

The filter a market has to pass:

1. **The ground truth can be stated crisply.** If the criteria cannot be
   written down, the validators will disagree forever and the market dies.
   *"Will this be a good movie?"* is not a market.
2. **The answer only becomes knowable at the deadline.**
3. **Resolving it requires reading and interpreting several sources.**
4. **It is objective *given* the criteria.** The objectivity lives in the
   reading, not in the definition.

Filter 1 and 3 are where GenLayer has an edge: an optimistic oracle with a
single disputer (the usual approach) is slow and contentious exactly on
questions with ambiguous criteria.

---

## 7. The two ideas that make Cite different

### 2.1 Cite or it did not happen

Every settlement carries **citations**: the sentences that support the answer.
The contract verifies them **deterministically** — every quote has to appear,
character for character, in the page it points at. A quote that does not
verify is dropped. A market that cannot cite the web does not settle.

The citation is checked by plain substring search over the fetched page text,
folded to alphanumerics, so it is deterministic and every node reaches the
same conclusion. `get_citations()` returns the trail for auditing.

### 2.2 The committee extracts, the contract decides

In `metric` mode the model only extracts **one integer** — a count, a total, a
threshold value. The contract then derives the outcome itself:

```python
def derive_outcome(metric: int) -> int:
    if comparator == ">=":  passed = metric >= threshold
    elif comparator == ">": passed = metric > threshold
    ...
    return 0 if passed else 1
```

The model cannot talk the contract into the wrong outcome, and the validators
only ever have to agree on the **derived decision** — not on the raw number.
That is what makes aggregate markets work: a leader that counts 12 and a
validator that counts 15 both clear a threshold of 10, so they agree on *Yes*;
but a leader that counts 12 and a validator that counts 5 disagree on the
outcome, so the market does not settle.

| Mode | The model returns | The contract decides |
|---|---|---|
| `choice` | `outcome_index` | accepts it (validated) |
| `metric` | `metric` (integer) | `outcome_index = derive_outcome(metric)` |

---

## 8. Architecture

### 3.1 One contract, many markets

`contracts/cite.py` is a single registry contract. It holds a `TreeMap` of
markets and a `TreeMap` of positions, plus an ordered `DynArray` of market ids
for pagination.

*Why not one contract per market?* A factory would isolate state per market,
but it forces N deployments and needs its own enumeration index anyway. A
registry keeps the deployment, the address book and the accounting in one
place, and each market still resolves in its own transaction — resolution of
one market never blocks another.

### 3.2 Storage layout

Nested `DynArray` inside a storage dataclass is a known footgun in GenVM, so
lists are stored as JSON strings:

```python
@allow_storage
@dataclass
class Market:
    market_id: u256
    creator: Address
    question: str
    criteria: str
    outcomes_json: str          # '["Yes", "No"]'
    source_urls_json: str
    allowed_domains_json: str
    close_ts: u256
    resolution_deadline_ts: u256
    challenge_window: u256
    status: str                 # open | closed | resolved | settled | voided
    outcome: u256               # index of the winning outcome
    confidence: u256
    resolution_json: str        # the full consensus payload
    resolved_at: str
    pools_json: str             # '[1000000, 0]'
    total_staked: u256
    paid_out: u256
    refunded: u256
    fee_wei: u256
    winning_claimed_stake: u256
    challenge_count: u256
    challenge_deadline_ts: u256
    swept: bool
    # --- Cite specifics ---
    resolution_mode: str        # choice | metric
    comparator: str             # >= | > | <= | < | ==
    threshold: u256
    metric_name: str
    window_start_ts: u256       # the period the metric is counted over
    window_end_ts: u256
    require_citation: bool
    citations_json: str         # the verified citation trail
    citations_verified: u256
    metric_value: i256
    cited_domains_json: str
```

Positions are keyed by `"{market_id}:{bettor}:{outcome}"` so a bettor can back
several outcomes and each position is settled independently.

### 3.3 The consensus block

`resolve_market()` is the heart of the project.

**Leader**

1. Fetch every source with `gl.nondet.web.render(url, mode="text")`.
   Failures are normalised to an empty string — the raw text of a network error
   differs between nodes and would poison the agreed value.
2. Drop every page whose domain is not in the market's allowlist.
3. Drop every page that does not mention the subject (a cheap deterministic
   gate — no point spending an LLM call on a page about banana bread).
4. Require **at least 2 verified sources from 2 distinct registrable domains**.
   Without that, return `resolved: false` — the market is voided, not settled
   on thin evidence.
5. Ask the LLM for a structured answer (`response_format="json"`), with the
   fetched pages wrapped in an explicit *untrusted data* block and the
   instruction to copy supporting sentences **verbatim**.
6. Validate the answer exhaustively: booleans are rejected where an int is
   expected (`bool` is a subclass of `int` in Python!), the outcome index must
   be inside the allowed range, the metric must be a non-negative integer, the
   confidence must be 0..100. A malformed answer raises a `[LLM_ERROR]` user
   error, which makes validators *disagree* and forces a leader rotation
   rather than settling on garbage.
7. **Verify the citations** against the page text. With `require_citation`
   enabled, a resolution that cites nothing verifiable does not settle.
8. Derive the outcome (in `metric` mode) with deterministic code.

**Validator**

```python
def validator_fn(leader_result) -> bool:
    if not isinstance(leader_result, gl.vm.Return):
        return handle_leader_error(leader_result, leader_fn)

    theirs = leader_result.calldata
    mine = leader_fn()          # <- independent re-derivation

    if bool(theirs["resolved"]) != bool(mine["resolved"]):
        return False
    if mine["resolved"]:
        if int(theirs["outcome_index"]) != int(mine["outcome_index"]):
            return False
        # reject only a strong confidence mismatch
        if theirs["confidence"] >= 67 and mine["confidence"] <= 33:
            return False
    return True
```

The validator **re-runs the whole task**. It does not read the leader's answer
and sanity check it. The prose (`reasoning`) and the citations are stored but
never compared — two LLMs always word them differently.

### 3.4 The challenge path

A settlement can be disputed inside a challenge window:

```
resolve_market()          -> status = resolved, challenge_deadline_ts set
challenge_market(url)     -> a second, independent consensus block
```

The challenge is itself adjudicated by the committee: it reads the original
sources *and* the challenger's evidence and decides whether the challenge
holds. A successful challenge voids the market and refunds everybody (the bond
is returned to the challenger). A failed challenge forfeits the bond to the
protocol. This is a second, genuinely useful use of GenLayer: adjudicating
*evidence about evidence*.

### 3.5 The money

Parimutuel pools, one per outcome. A bettor buys at par (1:1); the implied
probability is `pool / total_staked` and the implied odds are
`total_staked / pool`.

Payouts use the **cumulative rounding** identity so that the market can never
create or destroy a single wei, whatever order the winners claim in:

```
claim_i = floor(cum_i * payout_pool / winning_pool)
        - floor(cum_{i-1} * payout_pool / winning_pool)
```

Summed over every winner this telescopes to exactly `payout_pool`, because
`cum_n == winning_pool`. No "last claimant takes the dust" special case is
needed and no rounding can be lost.

A 1% protocol fee is carved out of the settled pool and is withdrawable by the
contract owner.

### 3.6 Accounting invariant

`get_accounting()` exposes the invariant that must always hold:

```
balance == staked + bonds_received
          - paid_out - refunded - bonds_returned - fees_withdrawn
```

Two subtleties that are easy to get wrong, and are handled here:

* The market fee is carved **out of** the staked amount, so it must not be
  added to the balance expectation a second time.
* If a market is voided **after** it was already settled, the fee that was
  collected at settlement time has to be reversed, otherwise the contract would
  promise more than it holds.

---

## 9. Contract API

### Write methods

| Method | Value | Description |
|---|---|---|
| `create_market(question, criteria, outcomes, source_urls, allowed_domains, close_ts, resolution_deadline_ts, challenge_window, resolution_mode, comparator, threshold, metric_name, window_start_ts, window_end_ts, require_citation, measurement_json, event_urls, event_domains)` | — | Register a market. Returns the market id. |
| `place_bet(market_id, outcome)` | payable | Stake GEN on an outcome. |
| `close_market(market_id)` | — | Close the betting window. Permissionless, idempotent. |
| `resolve_market(market_id)` | — | **Consensus block.** Reads the web, settles the market. |
| `challenge_market(market_id, evidence_url)` | payable | Dispute a settlement with evidence and a bond. |
| `claim(market_id)` | — | Collect the winnings of the caller's winning position. |
| `claim_refund(market_id)` | — | Recover the stake in a voided market. |
| `void_market(market_id)` | — | Void a market whose resolution deadline has passed. |
| `sweep_unclaimed(market_id)` | — | Owner reclaims winnings nobody claimed (after a grace period). |
| `withdraw_fees()` | — | Owner withdraws the protocol fees. |

### View methods

| Method | Description |
|---|---|
| `get_market(market_id)` | Full market state. |
| `get_citations(market_id)` | The verified citation trail of a settled market. |
| `get_market_odds(market_id)` | Implied probability and odds per outcome. |
| `get_position(market_id, bettor, outcome)` | A single position. |
| `get_market_count()` | Number of markets. |
| `get_markets(offset, limit)` | Paginated market index. |
| `get_accounting()` | Global accounting snapshot + invariant flag. |

---

## 10. Getting started

### Requirements

* Python 3.12+
* Node.js 18+ and the GenLayer CLI: `npm install -g genlayer`

### Install

```bash
pip install -r requirements.txt
```

### Lint

```bash
genvm-lint check contracts/cite.py
genvm-lint typecheck contracts/cite.py
```

### Run the tests

Fast direct-mode tests (no server, ~5 s, 104 tests):

```bash
pytest tests/direct -v
```

Integration tests against the hosted Studio (full consensus, real web and LLM
calls, minutes):

```bash
pytest tests/integration -v -s
```

The integration suite has three parts:

| file | what it proves | needs |
|---|---|---|
| `test_cite.py` | the contract's own lifecycle on a real network: create, bet, settle, the accounting invariant, a cited settlement | a deployment of its own |
| `test_frontend_contract.py` | the interface reads the chain the way the chain stores it, field by field | the deployed contract |
| `test_frontend_pages.py` | the pages a reader sees carry the question, the number and the quotes | a server, started by the test |
| `test_seed_markets.py` | the board is well formed, every market has a closing time | nothing |

### How the interface is tested against the chain

The frontend never talks to the chain directly. It goes through
`frontend/src/lib/cite.ts`, which is where the field names, the number
conversions and the JSON parsing live. A contract that renames a field, or a
return value that arrives as a string instead of a number, breaks the
interface long before it breaks the contract.

So the integration tests read the chain twice. Once through the chain client,
which gives the contract's own view, and once through the frontend's read
layer, through `frontend/scripts/contract-read.ts`, which gives the view the
pages render. The two have to agree on every field:

```bash
cd frontend
npx tsx scripts/contract-read.ts market 1     # what the interface sees
npx tsx scripts/contract-read.ts accounting   # what the auditor sees
```

The script reads `.env.local` itself, and the environment wins over the file,
so the same script points at Studionet or at a local network.

Two things were found this way, and both are the reason the tests exist. The
payout queue returns a struct with a count and a list, and the interface
shows the list, so a naive comparison of the two reads the two keys of the
struct as two payouts. And a market that asks for a number its sources do not
contain cannot be settled at all, which is a fact about the market, not about
the contract, and the test now asks for a number the source really contains.

The typed test framework is not used for the integration suite, because it has
to fetch the contract schema from the source code, and the source of this
contract is not plain ASCII.

### Deploy

```bash
genlayer network set studionet          # or testnet-bradbury
genlayer account                         # create + fund if needed
./scripts/deploy.sh                     # or scripts/deploy.ps1
genlayer schema <address>
```

StudioNet is gasless. Testnets need a funded account
(<https://testnet-faucet.genlayer.foundation/>).

---

## 11. How Cite differs from `betcle`

`betcle` (same workspace) is a working binary YES/NO market with a frontend,
already deployed on studionet. Cite is not a replacement for it, it is the
market for the questions betcle cannot settle well:

| | betcle | Cite |
|---|---|---|
| Outcomes | binary YES/NO | N outcomes, plus derived `metric` mode |
| Sources | **1 URL** | N URLs, allowlist, ≥2 distinct registrable domains |
| Evidence quality | raw HTML straight into the prompt | rendered text, subject gate, quote verification |
| Citations | none | every settlement carries a verifiable trail |
| Disputes | none | `challenge_market` + a second consensus block |
| Decision | the model picks the outcome | in `metric` mode the contract derives it |
| Money | no published invariant | `get_accounting()` invariant, cumulative rounding, exact wei |

---

## 12. Security notes

* **The creator cannot pick the outcome.** They only supply the question, the
  criteria and the sources. The committee reads them; the leader does not get
  to interpret them.
* **In `metric` mode the model cannot pick the outcome at all.** It extracts a
  number; the contract decides.
* **Fetched pages are untrusted data.** The prompt states this explicitly and
  the evidence is fenced off from the trusted part of the prompt.
* **Citations are verified against the source.** A quote that is not in the
  page is dropped, and with `require_citation` an unsubstantiated resolution
  does not settle.
* **Source allowlist.** Only pages from the market's registered domains count
  as evidence, and at least two *distinct registrable domains* are required
  (`bbc.co.uk` and `news.bbc.co.uk` are one domain, not two).
* **No raw exception text reaches the consensus value.** Network errors are
  normalised, so two nodes with different connectivity cannot manufacture a
  disagreement on wording.
* **Malformed LLM output never settles a market.** It raises `[LLM_ERROR]`,
  which makes validators disagree and rotates the leader.
* **Unresolved is a first-class outcome.** Insufficient evidence voids the
  market and refunds everybody; it never guesses.
* **The money is conserved.** The cumulative rounding identity plus the
  accounting invariant make it impossible to pay out more than was staked.
* **Value transfers are emitted `on="finalized"`** so a re-execution after an
  appeal cannot pay twice.

---

## 13. Known limitations and roadmap

| Limitation | Plan |
|---|---|
| Parimutuel only: you always buy at par, you cannot buy at the current price. | Add a constant-product AMM over the outcome pools (the `omnimarket_v3` approach) with ceiling division so the curve stays over-collateralised. |
| `require_citation` can void a market whose model paraphrased instead of quoting. | Measure the rate on a real network; if it is high, soften the rule to "cite or acknowledge" and keep the trail as the audit artifact. |
| A market resolves with one committee reading. | Superimpose the protocol-level appeal: validators can `genlayer appeal <txHash>` and a new leader is rotated. |
| Sources are fixed at creation. | Allow the committee to discover additional sources, still bound by the domain allowlist. |
| Thresholds are calibrated on ten years of normals, not thirty. | Extend the calibration to thirty years and to more windows per year. The ERA5 archive serves the whole range in one call, so this is a matter of range, not effort. |
| The alert feeds retain only about two to three days. | The consequence markets must be created and resolved inside that window, or the publishers need to keep an archive. Until then, the launch set is dated against the live retention. |
| `sweep_unclaimed` needs a 30 day grace period. | Replace the wall-clock grace period with an epoch-based one. |
| One contract for all markets. | Split into a factory + per-market contracts once storage isolation becomes a bottleneck. |
| No on-chain liquidity provider. | Add LP shares over the pools. |

---

## 14. Notes on the GenLayer SDK

Things that cost time to discover and that this contract deliberately avoids.
The published docs contain a few inaccuracies:

| Docs say | Reality |
|---|---|
| `response.status_code` | `response.status` — the dataclass is `Response(status, headers, body)` |
| `gl.UserError(...)` | `gl.vm.UserError(...)` |
| `gl.get_webpage(url)` | does not exist — use `gl.nondet.web.get` / `gl.nondet.web.render` |
| `gl.message.sender_account` | `gl.message.sender_address` |
| `gl.message.timestamp` | does not exist — use `datetime.now(timezone.utc)`, which is pinned to the transaction time and therefore deterministic across validators |

Two more that are not in the docs but decide whether the contract works at all:

1. **Never call a module level function from inside a non-deterministic
   block.** `cloudpickle` serialises a module level function *by reference*
   (module + qualified name) and the validator sandbox cannot re-import the
   contract module. Nested functions are serialised *by value*, which is why
   every helper used inside a consensus block lives in the closure returned by
   `_make_toolkit()`.
2. **The GenVM linter wants `gl.nondet.*` calls to be lexically inside the
   consensus block**, so the web and LLM calls live directly in the leader
   function rather than behind a helper.
