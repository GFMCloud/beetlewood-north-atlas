# Beetlewood Farms North Atlas - Build Spec

**Single source of truth.** Decisions, data model, formulas, hosting, caveats. Reconciled
2026-07-31; `HANDOFF.md` was folded in here and archived because the two files had drifted
into contradicting each other on every locked decision.

---

## 1. The project

An interactive atlas over one iNaturalist observer's records, scoped to a single property.
Roy F Morris II (`roymorrisii`, user_id 764712) is an entomologist specialising in longhorn
beetles; the property is his ~6 acre farm "Beetlewood Farms North", 376 Lamar County Line Rd,
Griffin, GA (lat 33.18, lng -84.20). Roy is Graham's dad.

**Two scopes, and they are not the same number.** The farm itself is a 2 km radius
(`FARM_RADIUS_KM`); "what other people record nearby", used only for the gap pool, is 15 km
(`NEARBY_RADIUS_KM`). Both live in `scripts/inat.py`. Conflating them inflates every headline
figure on the site by 25% - see §11.

Farm subset as of the 2026-07-30 snapshot: **1,393 observations, 950 species, 2023-2026,
75% research grade**, heavily skewed to insects (Insecta 1,090 obs; then Plantae 147,
Aves 78, a long tail). **These figures move on every refresh** - a 2026-07-31 dry run
already read 1,405 / 955. Treat every count in this document as a dated snapshot, not an
invariant. The invariant is that the totals reconcile, which `build_tree.py` asserts. His full
account is 8,287 observations across several countries - **do not treat the account as the
farm.**

## 2. Locked decisions

- **Audience: a tool Roy actually uses.** Utility and currency over gift polish. The gap
  checklist is a first class feature.
- **Roy is non technical and Windows only.** Anything he operates is a browser URL. Never a
  shell, script or Python run. All builds run in CI.
- **Data strategy: hybrid.** Pre baked JSON committed to the repo for instant offline safe
  load, plus a weekly automated refresh. Nothing is fetched on page load.
- **Tree of Life is one tab with an Explorer <-> Sunburst toggle.** Not two tabs.
- **Hosting: GitHub Pages under the `gfmcloud` account, repo `beetlewood-north-atlas`,
  Pages in "deploy from a branch" mode**, refreshed by a weekly GitHub Actions cron.
  Branch mode is not a detail: a workflow commit made with the default `GITHUB_TOKEN` does
  **not** trigger other workflows, so an Actions based Pages deploy would never fire and the
  site would silently stop updating. Default URL, no custom domain.
- **Interest is one formula at three ranks** (§6). The old genus level
  `log1p(obs)+log1p(species)` metric is gone.
- **Observations are refetched from the API every run** (§5 step 0). This is what makes the
  weekly refresh real.
- **Farm scope is a 2 km radius, verified against the export** (§11). The 15 km figure that
  appeared in earlier drafts was the nearby-species radius, not the farm.
- **Dropped:** the icicle view (deleted), the radial tree and force directed brain map
  (`archive/explorations.html`, kept for reference only), the old sunburst tab in the
  wireframe. No in browser "Refresh now" button in v1.

## 3. What to build now

Assemble one cohesive single page app, wire the live data, ship it.

1. **Atlas shell.** One self contained SPA, template generated through `build_pages.py`.
   Tabs:
   - **Overview** - stat tiles + species accumulation curve (from `wireframe/index.html`).
   - **Tree of Life** - Explorer <-> Sunburst toggle. Port both `explore/` views into this
     one tab. See §8 for what is already done to make them mergeable and what is not.
   - **Seasonal Calendar** - phenology heatmap + accumulation (from the wireframe).
   - **What He Logs** - the interest profile, now reading `data/interest.json` (§6).
   - **Gap Checklist** - real data (§7).
2. **Gap checklist.** `fetch_gap_pool.py` has been probed with `--check` but never run in
   full (§12). Run it, look at the numbers, then build the view. The pool is 1,807 nearby
   research-grade species against his 4,276 recorded species.
3. **Refresh automation.** Weekly Actions cron running the 5 step pipeline, committing
   refreshed JSON + rebuilt pages.
4. **Deploy** and hand Graham the URL.

## 4. Repo layout

```
CLAUDE.md          auto-loaded pointer + hard rules
README.md          human orientation
BUILD_SPEC.md      this file - the source of truth
KICKOFF.md         the prompt to paste into Claude Code
scripts/           the pipeline (see scripts/README.md)
  inat.py                shared API helpers + the farm scope constants
  fetch_observations.py  step 0  (network)
  fetch_taxonomy.py      step 1  (network)
  build_interest.py      step 2  (offline)
  build_tree.py          step 3  (offline)
  fetch_gap_pool.py      step 4  (network)
  build_pages.py         step 5  (offline)
  templates/         tpl_explorer.html, tpl_sunburst.html
  vendor/            d3.v7.min.js (v7.9.0)
data/              farm_data.json, taxonomy.json, interest.json, tree_data.json,
                   gap_pool.json (after step 4), observations764712.csv (reference only)
explore/           explorer-2pane.html, sunburst-zoom.html  (GENERATED)
wireframe/         index.html - prototype, source material for 3 tabs
archive/           explorations.html - radial tree + brain map, not in the product
```

## 5. The pipeline

| step | script | in -> out | network |
|---|---|---|---|
| 0 | `fetch_observations.py` | iNat API -> `data/farm_data.json` | yes |
| 1 | `fetch_taxonomy.py` | farm_data -> `data/taxonomy.json` (ancestry) | yes |
| 2 | `build_interest.py` | farm + taxonomy -> `data/interest.json` | no |
| 3 | `build_tree.py` | farm + taxonomy -> `data/tree_data.json` | no |
| 4 | `fetch_gap_pool.py` | iNat API -> `data/gap_pool.json` | yes |
| 5 | `build_pages.py` | tree + D3 -> `explore/*.html` | no |

Run in that order. Conventions the pipeline enforces and you must keep:

- 30 id batches, ~1.1 s pace, retries. All of it lives in `scripts/inat.py`; use it rather
  than writing new HTTP code.
- **The farm scope constants live in `inat.py` and nowhere else.** Do not re-hardcode
  lat/lng/radius/user in a script or a template.
- `fetch_observations.py` refuses to write an empty file and refuses a >10% drop in
  observation count without `--allow-shrink`. That guard is the difference between a cron
  that fails loudly and one that quietly publishes an empty atlas.
- `build_tree.py` asserts every parent equals the sum of its children and that the root
  equals `meta.total_obs`.
- `build_pages.py` asserts no external `<script src>` and no web storage survive inlining,
  **before** writing the file.
- Templates use `/*__DATA__*/` and `/*__D3__*/` placeholders. Edit templates, never the
  generated HTML.
- Every network script takes `--check`: one tiny request that prints the response shape.
  Use it before committing to a full pull.

## 6. Interest scoring - one formula, three ranks

Computed by `build_interest.py` into `data/interest.json`.

```
effort      = observation count
depth       = distinct species
recency     = fraction of observations in the last 365 days, anchored to --asof
persistence = distinct months of the year present

normalise each 0..1 across peers in the same grouping (effort and depth on log1p), then
interest = 100 * (0.35*effort + 0.30*depth + 0.20*recency + 0.15*persistence)
```

Applied three times: classes ranked against classes, families against families, genera
against genera. **A score is only comparable within its own grouping.** That is not a
technicality - ignoring it is what produced the ranking bug described in §7.

Two things that must not regress:

- **Recency is anchored to the run date** (`--asof`, default today). A frozen anchor stops
  decaying the moment the cron starts running, and nothing would surface the drift.
- **There is one definition of "interest".** Earlier snapshots shipped a second, undocumented
  one at genus level (`log1p(obs)+log1p(species)`, scale 1.4-5.0) alongside the 0-100 class
  score. Both were called "interest" and they were not comparable. `class_interest` and
  `genus_interest` have been removed from `farm_data.json`; `interest.json` is the only
  source. Verified: the class scores this formula produces reproduce the old shipped values
  exactly, so nothing visible changed at class level.

`interest.json` shape:

```
asof, recent_days, weights{}, mult_span_lo
class{}   family{}   genus{}      each: {obs, species, recent_frac, months, years, interest}
family_class{}       family -> the iconic class its records sit under
family_multiplier{}  family -> the gap weight multiplier (§7)
coverage{}           observations, without_family, without_genus
```

## 7. Gap checklist

```
pool  = gap_pool.json
seen  = (life_taxa, life_names)  |  (farm_taxa, farm_names)   -- user toggle
gaps  = pool where tid NOT in seen_ids AND name NOT in seen_names

weight(g) = interest.class[g.iconic] * family_multiplier[g.family]   (default 1.0)
rank(g)   = weight(g) * log1p(g.count) ** COUNT_EXP
```

**Match on id AND name.** Matching ids alone produced 2 false gaps out of 840 on the first
real run, both worth understanding because they are structural, not flukes. `Xanthotype` is a
genus he has recorded; `species_counts` rolls up to the finest rank available, so it can be
absent from his own rollup while present in the pool - the fix is unioning `farm_taxa` into
`life_taxa`. `Hericium erinaceus` carries id 1520823 in his records and 49158 in the pool,
because iNat splits and merges taxa and an observation keeps the id it was made under - the
fix is matching scientific name as a second key. Earlier drafts of this spec claimed both
sides were species-rank rollups and therefore directly comparable. That was wrong.

**Why a multiplier and not `family_interest ?? class_interest`.** The obvious rule is wrong,
and wrong in the worst direction. Family scores are normalised among families and class
scores among classes, so the two scales never meet: measured on the real data, Insecta scores
94.0 while the single best represented family tops out at 91.0. Under the `??` rule **all 133
of his insect families ranked below the baseline of a family he has never touched** -
Cerambycidae, his own speciality, landed at 63.9 against a 94.0 baseline. The gap list would
have systematically demoted exactly what it exists to surface.

The multiplier form fixes it. `family_multiplier` is `MULT_SPAN_LO + percentile of the family
within its own class`, with **`MULT_SPAN_LO` pinned at 1.0**. An unlogged family has no
multiplier and sits at the class baseline; a logged family can only score at or above it.
The floor matters: 112 of his 248 families have exactly one record (Buprestidae among them),
and any floor below 1.0 means logging a family once penalises it relative to never having
touched it. Measured after the fix: 133/133 logged insect families at or above baseline,
Cerambycidae 11th of 133 at weight 180.9 against a 94.0 baseline, Buprestidae at 94.8.

**`COUNT_EXP`, calibrated against the real pool (2026-07-31).** The nearby counts turn out to
be tiny: across 840 gaps the median is **1** and the maximum is **26**. The worked example in
earlier drafts assumed a weed with 180 nearby records dominating a longhorn with 12. No such
species exists here. `log1p` over a 1-26 range spans 0.69 to 3.30, about 4.8x, against a
weight range of roughly 47-185, about 4x - so the two terms are already comparable and the
"abundance drowns interest" worry does not materialise on this data.

What the exponent actually controls is how insect-heavy the top of the list is:

| COUNT_EXP | insects in top 50 | beetles in top 50 |
|---|---|---|
| 1.00 | 32 | 8 |
| 0.50 | 38 | 7 |
| 0.25 | 48 | 7 |

**Ship 0.5.** At 0.25 the list is 48/50 insects, which loses the genuinely useful "you have
somehow never logged this common thing" signal; at 1.0 it drifts plant-heavy. Note the beetle
count barely moves either way - there simply are not many nearby research-grade beetle records
he has missed, because he is the local authority. Getting to beetles is the group filter's
job, not the sort's. Say that in the UI rather than implying the global ranking does it.

The raw gap mix is Plantae 343, Insecta 259, Fungi 132, Arachnida 44, and a long tail - so the
interest weighting is doing real work to surface insects from a plant-majority pool.

UI, ported from the wireframe mock: scope (radius now, Spalding County as a second pass -
county needs a `place_id` from `/places/autocomplete`), not-yet-logged (anywhere -> subtract
`life_taxa` | on farm -> subtract `farm_taxa`), group filter (iconic class, or `order`/`family`
from the baked pool), min nearby count. Each row shows the weight that drove its rank. Note
that the mock only prototypes scope and a group filter - **min nearby count and the
group-by-iconic control do not exist in it and have to be built.**

## 8. Tree of Life - merging the two views

Both templates are complete standalone documents. Two things were checked directly rather
than assumed:

- **JS scope is already safe.** Both main scripts are wrapped in
  `(function(){ "use strict"; ... })()`. Concatenating them does not throw. (An earlier
  review claimed a redeclaration `SyntaxError` here - that was a false positive from reading
  declarations inside the existing IIFE.)
- **DOM ids were not safe.** `treeData`, `theme` and `hsub` were duplicated across the two
  templates, so a merged page silently cross wired: both scripts read whichever `#treeData`
  came first, both dark mode toggles bound to the same button. Ids are now prefixed `ex-` and
  `sb-`. A merged smoke page renders both views simultaneously - 11 class rows and 1,930
  sunburst paths, zero JS errors, zero duplicate ids.

Still to do in assembly: shared chrome (one header, one theme toggle), CSS scoping, loading
D3 once, and deciding which view is the default. The 20 shared CSS custom properties have
identical values in both templates and merge cleanly. A merged page carrying both views plus
D3 lands around 1 MB; adding the wireframe tabs and their data puts the finished SPA near
1.5 MB, which is fine for Pages but worth knowing before you inline a fourth copy of anything.

## 9. Design conventions

- **Self contained, single file, offline safe.** Everything inline. No CDN, no web storage.
  `build_pages.py` enforces it. **Honest exception:** taxon photos are remote iNat S3 URLs.
  Opened with no network the pages render fine and photo cards show a "photo offline"
  placeholder. Keep that fallback; do not claim the pages are fully offline without it.
- **No web storage means the dark mode toggle cannot persist** across loads. That is a
  deliberate trade, not an oversight. Roy will re-toggle each visit.
- **Validated palette**, class -> colour fixed. Reference `--c-<Class>` custom properties,
  never raw hex.

  | | Insecta | Plantae | Aves | Fungi | Arachnida | Reptilia | Amphibia | Mammalia | other |
  |---|---|---|---|---|---|---|---|---|---|
  | light | #2a78d6 | #eb6834 | #1baf7a | #eda100 | #e87ba4 | #008300 | #4a3aa7 | #e34948 | #b7b4aa |
  | dark  | #3987e5 | #d95926 | #199e70 | #c98500 | #d55181 | #008300 | #9085e9 | #e66767 | #6f6d64 |

  The palette covers 9 buckets; his data has 11 iconic groups. Animalia, Protozoa and
  Mollusca (5 observations between them) collapse to "other". **`wireframe/index.html` uses
  raw hex rather than the tokens and is missing `#6f6d64` entirely** - converting it to
  tokens is part of assembly, and is where colours will silently drift if you rush it.
- Colour follows the class, never the rank. A filter must not repaint survivors.
- Hover tooltips on marks, zoom/pan on big canvases, selective direct labels. The palette,
  the class mapping and the interaction rules above are the whole convention - follow them
  directly. (If a `dataviz` skill happens to be available it is worth reading, but nothing in
  this repo provides one, so do not go looking for it.)

## 10. Data model

**`data/farm_data.json`** - `meta`, `observations[]` with `d m y cls g sci com tid q img url`,
`life_taxa[]`, `farm_taxa[]`. Interest blocks deliberately absent (§6).

**`data/taxonomy.json`** - `{"<taxon_id>": {rank, name, common, chain}}`, chain maps each
major rank to `[name, taxon_id]`. 952 taxa, 951 with order, 947 with family.

**`data/tree_data.json`** - `{meta, tree}`. Nested node:

```
n  name              o  observation count        k  children (absent on leaves)
r  rank              s  distinct leaves beneath   id iNat taxon_id (for deep links)
c  iconic class      d  total descendant taxa
leaves add:  cm common name - im photo url - u sample obs url - q research grade count
             mo months present [1..12] - f/l first & last obs date
```

Ranks present: `root, class, order, family, genus, species`, plus `stub` and `unresolved`.

**`data/gap_pool.json`** - `{meta, pool[]}` with `{tid, name, common, iconic, family, order, count}`.

## 11. Data caveats - respect these

- **The farm is a 2 km radius, not 15 km.** Measured from the export: all 1,393 farm records
  sit inside a 0.55 x 0.32 km box, no more than 0.64 km from the centre. His next cluster of
  records is ~10 km away, so any radius in [0.7, 9] km returns exactly the same 1,393
  observations; 2 km sits in the middle of that gap. Pulling at 15 km returns **1,747**
  observations - roughly 350 records from a different site, a 25% inflation of every headline
  number. Earlier drafts of this spec specified `radius=15` for the observations refresh. That
  was wrong and would have silently redefined what "the farm" means on the first cron run.
- **The top level of the tree is `iconic_taxon_name`, not the taxonomic class.** 178 of 1,393
  observations have a real class that differs from the iconic label - Plantae -> Magnoliopsida
  (110), Fungi -> Agaricomycetes (19), and others - and the fold skips the class rank
  entirely. So for insects the tree really is class -> order -> family -> genus -> species,
  but for plants and fungi it is iconic -> order -> family -> genus -> species. Do not
  describe the product as a full 5 rank phylogeny across all life; it is not.
- 69 records are partial IDs (genus or family only), kept as explicit `stub` nodes
  ("Scutellaria sp.", "Curculionidae (undetermined)") so totals reconcile. Do not clean them
  away - the leaf count drops to 881 and the numbers stop adding up.
- 87 observations are coordinate obscured (threatened taxa). Minor, but relevant if a map
  view is ever added.
- The farm boundary is a lat/lng radius, not an official iNat place, so a few edge records
  are approximate.
- "Species" as distinct `scientific_name` runs slightly higher than iNat's leaf species count.
  The reconciled figure is whatever `tree_data.json` reports as leaves (950 at the snapshot).
- `life_taxa` is the authoritative life list count and `meta.life_list_species` is now derived
  from it. An older snapshot had 4,754 ids against a hand set 4,739 - fixed by construction,
  not by editing a number.

## 12. Verified against the live API, 2026-07-31

Both `--check` probes were run from Graham's machine. Results:

- **`species_counts` returns `taxon.ancestor_ids`.** Confirmed present. The family and order
  resolution in `fetch_gap_pool.py` works as designed.
- **Gap pool: 1,807 research-grade species within 15 km.** Comfortably enough to justify the
  tab. The exact gap count needs the full pull and the subtraction.
- **His life list via `species_counts` is 4,276 species**, not the 4,754 in the snapshot. The
  478 difference is genus- and family-rank IDs from the CSV export, which can never match a
  pool entry because the pool is also a species rollup. Both sides of the subtraction are now
  species rank, which is what makes it valid.
- **The retry path works.** One probe hit "Remote end closed connection without response" and
  recovered on retry 1 of 3.

Still unverified:

- Neither network script has run a **full** pull yet, only `--check`. Use `--dry-run` on
  `fetch_observations.py` first; it pulls and diffs without writing.
- Whether GitHub Actions runners can reach the iNat API. Expected yes (open egress), but the
  first scheduled run needs eyes on it, not an assumption.

## 13. Prerequisites and verification

**Environment.** Verified working on macOS, Python 3.9.6, git 2.50.1, 2026-07-31.

- **Python 3.9+ and nothing else.** Every import across all six scripts is stdlib -
  `argparse, collections, datetime, json, math, pathlib, random, sys, time, urllib`. No pip
  install, no requirements.txt, no virtualenv needed to run the pipeline. Keep it that way:
  a new third-party dependency also has to be installed on the CI runner.
- **Network egress to `api.inaturalist.org`** for steps 0, 1 and 4. If this is blocked the
  failure looks like a code bug. It is not. Diagnose it in five seconds with
  `python3 scripts/fetch_observations.py --check`.
- **A headless browser, for verification only.** Not installed by default and not needed by
  the pipeline:

      pip3 install --user playwright && python3 -m playwright install chromium

  (A `.venv` is tidier if you prefer; it is a dev-only tool either way.)
- **`gh` authenticated**, for creating the repo and configuring Pages. Run `gh auth status`
  first. Never handle tokens in this repo - the pipeline needs no credentials and none should
  ever be added.

**Three GitHub settings that fail silently if wrong:**

1. **Repo must be public** or free Pages will not serve it. Roy's iNat data is already public.
2. **Pages source = "Deploy from a branch."** An Actions-based Pages deploy never fires,
   because a push made with the default `GITHUB_TOKEN` does not trigger other workflows.
3. **Actions workflow permissions = read and write.** Some account defaults are read-only, and
   the weekly cron commits refreshed JSON back. Wrong here, the workflow runs green, commits
   nothing, and the site quietly stops updating. This is the nastiest of the three.

**No MCP connector is required.** The iNat API is public read over plain HTTP with no auth.
If something proposes adding a connector or an API key for iNaturalist, it has not read §5.

**Verification checklist.** Before calling any change done:

- `python3 scripts/build_tree.py` - **the reconciliation assertions pass**. Do not check the
  printed counts against 1,393 / 950 / 1,930; those are the 2026-07-30 snapshot and Roy is
  actively logging. What must hold is that every parent equals the sum of its children and
  the root equals `meta.total_obs`.
- `python3 scripts/build_interest.py` - classes, families and genera all scored, coverage
  reported.
- `python3 scripts/build_pages.py` - offline safety assertions pass.
- `python3 scripts/screenshot.py explore/*.html` (or `--tabs` once the SPA exists) - shoots
  each page, separates real console errors from the expected offline photo failures, flags a
  page that renders zero marks, and exits non-zero so it can gate a build. Attach the PNGs.
- Confirm the palette still comes from custom properties, not raw hex.

## 14. Parked, not forgotten

Explored and deliberately left out of v1. `archive/explorations.html` holds working
implementations of the first two.

- **Radial dendrogram** - a collapsible class -> genus -> species tree. Was the leading
  candidate to replace the sunburst before the Explorer/Sunburst pair was chosen.
- **Seasonal co-occurrence graph** - a force directed view linking genera Roy logs on the
  same days. This shows something neither taxonomy view can: field session associations.
  The strongest candidate for a future tab. Label it carefully if it ships - it means
  "logged together", not "found together ecologically", and one big mothing night links
  every moth photographed that evening.
- Per species phenology (emergence weeks rather than class x month), a within property map
  view, a 2023-2026 time scrubber, a Cerambycidae focus mode, and "new this year" highlighting.

## 15. Rate limits and fair use

From iNaturalist's [API Recommended Practices](https://www.inaturalist.org/pages/api+recommended+practices),
checked 2026-07-31. These are their words, not our guesses:

- **"about 1 per second, and around 10k API requests a day."** Over that returns HTTP 429,
  and "we may block IPs that consistently exceed these limits."
- **"Downloading over 5 GB of media per hour or 24 GB of media per day may result in a
  permanent block."**
- **"Please use a single IP address for fetching data."**
- A custom User-Agent identifying the application is requested.
- For bulk data they would rather you use an observation export or the weekly GBIF dataset
  than many API requests.

How this project complies:

- `DELAY = 1.1` s in `inat.py`, i.e. ~55 req/min before latency. Their forum carries repeated
  reports of 429s at exactly 60/min with ~55 given as the safe target, so the margin is
  deliberate. **Do not lower DELAY to make a run faster.**
- Request budget per full run: ~17 for observations and the life list, ~32 for taxonomy on a
  cold cache (5 on a warm one), ~50 for gap pool ranks on a cold cache, 4 for the pool
  itself. Roughly 100 cold, a handful warm. Against 10k/day that is negligible - but it is
  the reason no script should ever loop per-record instead of per-batch.
- `get()` honours `Retry-After` on a 429 and otherwise backs off exponentially with jitter,
  capped at 120 s, 5 attempts. A 4xx that is not 429 fails immediately rather than retrying
  into a wall.
- Every fetcher caches and checkpoints, so re-runs cost near zero. This is a rate-limit
  measure as much as a convenience one.

**Media bandwidth is the limit with real teeth, and it is the one this design touches.** The
pages hotlink taxon photos directly from iNat's S3 bucket rather than caching them, so every
page load draws on their media bandwidth rather than ours. At Roy-and-Graham scale that is
irrelevant. If this URL ever circulates in a naturalist group it stops being irrelevant, and
the penalty is a permanent block, not throttling. If traffic ever becomes non-trivial, cache
the thumbnails into the repo at build time instead.

**Known deviation:** they ask for a single fetching IP; GitHub Actions runners rotate. Our
weekly volume is ~100 requests, so this is noted rather than mitigated. If it ever matters,
move the refresh to a fixed-IP runner.

**Their preference for exports over the API is acknowledged and deliberately not followed**
for observations: iNat generates CSV exports on request and emails them, which CI cannot
automate. The API is the only automatable source. Our volume is ordinary API use, not bulk
extraction.
