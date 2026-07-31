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

Farm subset as of the **2026-07-31** refresh, which is what is committed: **1,405
observations, 955 species, 1,939 taxa in the tree, 2023-2026, 75% research grade**, heavily
skewed to insects (Insecta 1,102 obs; then Plantae 147, Aves 78, a long tail). The 2026-07-30
snapshot read 1,393 / 950, five days of logging earlier. **These figures move on every
refresh.** Treat every count in this document as a dated snapshot, not an invariant. The
invariant is that the totals reconcile, which `build_tree.py` asserts. His full account is
8,287 observations across several countries - **do not treat the account as the farm.**

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

## 3. State of the build

1. **Atlas shell - DONE** (2026-07-31). One self contained SPA at `index.html`, generated
   from `scripts/templates/tpl_atlas.html` through `build_pages.py`. Tabs:
   - **Overview** - stat tiles + species accumulation curve.
   - **Tree of Life** - one tab, Explorer <-> Sunburst toggle, Explorer the default. Both
     `explore/` views ported rather than rebuilt; §8 records how.
   - **Seasonal Calendar** - phenology heatmap + stacked monthly bars.
   - **What He Logs** - the interest profile from `data/interest.json` (§6), at all three
     ranks rather than only classes.
   - **Gap Checklist** - real data (§7).

   The accumulation curve lives on Overview only. §3 originally listed it under Overview
   *and* Seasonal; rendering the identical chart twice was worse than picking one, so
   Seasonal got stacked monthly bars instead.

2. **Gap checklist - DONE.** `fetch_gap_pool.py` has now run in full. Numbers and the
   `COUNT_EXP` decision are in §7.

3. **Refresh automation - NOT STARTED.** Weekly Actions cron running the 5 step pipeline,
   committing refreshed JSON + rebuilt pages. §12 flags the one thing only this can settle:
   whether Actions runners can reach the iNat API.

4. **Deploy - NOT STARTED.** Create the repo, set the three settings in §13, hand Graham
   the URL.

**The output is `index.html`, not `atlas.html`.** Pages in deploy-from-a-branch mode serves
the repo root, so the file has to be `index.html` for Roy to get a bare URL rather than one
with a path on the end. Earlier drafts of this spec called it `atlas.html` throughout.

## 4. Repo layout

```
CLAUDE.md          auto-loaded pointer + hard rules
README.md          human orientation
BUILD_SPEC.md      this file - the source of truth
KICKOFF.md         the prompt to paste into Claude Code
index.html         THE PRODUCT - the assembled atlas  (GENERATED, ~990 KB)
.github/workflows/
  refresh.yml      weekly cron - runs the 5 steps, verifies, then commits
scripts/           the pipeline (see scripts/README.md)
  inat.py                shared API helpers + the farm scope constants
  fetch_observations.py  step 0  (network)
  fetch_taxonomy.py      step 1  (network)
  build_interest.py      step 2  (offline)
  build_tree.py          step 3  (offline)
  fetch_gap_pool.py      step 4  (network)
  build_pages.py         step 5  (offline) - also composes the atlas payload
  screenshot.py          verification helper, NOT a pipeline step
  templates/         tpl_explorer.html, tpl_sunburst.html, tpl_atlas.html
  vendor/            d3.v7.min.js (v7.9.0)
data/              farm_data.json, taxonomy.json, interest.json, tree_data.json,
                   gap_pool.json, taxa_cache.json, observations764712.csv (reference only)
explore/           explorer-2pane.html, sunburst-zoom.html  (GENERATED)
                   still shipped as standalone single-view pages
shots/             screenshot.py output - gitignored, not part of the product
wireframe/         index.html - prototype, superseded by the assembled app
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
| 5 | `build_pages.py` | all four JSONs + D3 -> `explore/*.html` **and `index.html`** | no |

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
- `build_pages.py` asserts no external `<script src>`, no web storage, and no unfilled
  placeholder survive inlining, **before** writing the file.
- Templates carry `/*__DATA__*/`, `/*__TREE__*/`, `/*__ATLAS__*/` and `/*__D3__*/`
  placeholders; each template uses whichever it needs. Edit templates, never the generated
  HTML.
- **Step 5 composes the atlas payload, it does not dump the JSONs.** `farm_data.json` is
  550 KB and the atlas needs four fields of it; the gap subtraction needs 4,381 life-list
  ids the browser would only use to compute one boolean per pool row. Both fold offline in
  `build_pages.py`, so the page ships aggregates - accumulation points, a class x month
  grid, and gap rows that already carry their weight and their two seen-flags. That, plus
  both tree views reading one shared `#treeData` block, is why `index.html` is ~990 KB
  rather than the ~1.5 MB §8 predicted.
- `python3 scripts/build_pages.py --gap-top 30` prints the ranked gap list and writes
  nothing. Use it to re-check the ranking after any change to §6 or §7.
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

**`COUNT_EXP` = 0.5, SHIPPED.** Calibrated against the real pool, re-measured 2026-07-31
after the full pull. The nearby counts are tiny: across the 838 lifer gaps the median is
**1** and the maximum is **26**. The worked example in earlier drafts assumed a weed with 180
nearby records dominating a longhorn with 12. No such species exists here. `log1p` over a
1-26 range spans 0.69 to 3.30, about 4.8x, against a weight range of roughly 47-185, about
4x - so the two terms are already comparable and the "abundance drowns interest" worry does
not materialise on this data.

What the exponent actually controls is how insect-heavy the top of the list is. Measured on
the 838 lifer gaps:

| COUNT_EXP | insects in top 50 | beetles in top 50 |
|---|---|---|
| 1.00 | 32 | 8 |
| **0.50** | **38** | **7** |
| 0.25 | 48 | 7 |

**Ship 0.5.** At 0.25 the list is 48/50 insects, which loses the genuinely useful "you have
somehow never logged this common thing" signal; at 1.0 it drifts plant-heavy. Note the beetle
count barely moves either way - there simply are not many nearby research-grade beetle records
he has missed, because he is the local authority. Getting to beetles is the group filter's
job, not the sort's. The UI says so rather than implying the global ranking does it.

**Which population you calibrate on matters.** The table above is the *lifer* list. The
not-yet-on-farm list is a different and larger population (1,053 rows) and runs hotter -
46/50 insects at the same exponent - because it also contains everything he has recorded
elsewhere but not here. Comparing a mix measured on one against a figure measured on the
other will look like a regression and is not one.

The raw lifer gap mix is Plantae 343, Insecta 258, Fungi 131, Arachnida 44, and a long tail -
so the interest weighting is doing real work to surface insects from a plant-majority pool.

**An iconic group with no interest score falls back to the weakest logged class, not to
zero.** 9 pool species sit in groups he has never logged (Actinopterygii 8, Unknown 1). A
zero weight would delete them from a list whose entire purpose is showing what he is missing;
the weakest class he *has* logged (Mollusca, 20.0) sorts them to the bottom but keeps them
visible.

Numbers at the 2026-07-31 pull, dated like every other count here: pool **1,807**, of which
**838** are true lifers and **1,053** are not yet recorded on the farm. 480 distinct families
appear in the pool and 231 of them carry a multiplier - the other 249 sit at the class
baseline of 1.0.

UI as built: scope (radius; the Spalding County option is present but disabled, because
county needs a `place_id` from `/places/autocomplete`), not-yet-logged (anywhere -> subtract
`life_taxa` ∪ `farm_taxa` | on farm -> subtract `farm_taxa`), group filter (iconic group or
order, both with counts, from the baked pool), min nearby count, and a free-text filter over
name/common/family/order. Each row shows the weight that drove its rank; the hover shows the
full `weight × log1p(count)^COUNT_EXP` arithmetic. Rows are paged 50 at a time.

Both the subtraction and the weight are computed in `build_pages.py`, not in the browser -
each row ships with its weight and two booleans (`lg` = not logged anywhere, and implicitly
not on the farm, since rows already on the farm are dropped at build time).

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

**Assembly is done** (2026-07-31), and what it took was more than prefixing ids.

- **Id prefixes alone were not enough.** The two templates still shared *class* names with
  each other and with the new shell - `.card`, `.stat`, `.stats`, `.crumb`, `.note`, `.btn`,
  `.nm`, `.sep`, `.swatch`, `.legend`, `.seg` all collided. The explorer's `.card` is a
  species thumbnail; the shell's `.card` is a padded panel. Merged flat, every thumbnail
  would have picked up panel padding. So the port namespaces **everything**: `x-*` classes
  and `ex-*` ids for the explorer, `s-*` classes and `sb-*` ids for the sunburst, with all
  view CSS scoped under `.exv` / `.sbv`. Keep new names inside those namespaces.
- **One shared tooltip.** Both views and all four charts draw into a single `#tip`; the
  innards are `.tip-t` / `.tip-r` / `.tip-v`.
- **One copy of the tree.** Both views read the same `#treeData` block instead of `ex-` and
  `sb-` copies, which is 350 KB saved.
- **Default view is the Explorer.** It is searchable and reads as a tool; the sunburst is the
  picture. Roy is the audience (§2), so the tool goes first.
- **Theme.** One toggle in the shell chrome, with a hook list. Only two things need repainting
  on a flip: the sunburst resolves its fills to hex at draw time, and the heatmap picks its
  cell-label ink by contrast (§9). Everything else is CSS custom properties and follows on
  its own.

Verified on the built page: **48 ids, no duplicates**; `screenshot.py --tabs` reports 1,947
marks and zero console errors across all seven views.

The 20 shared CSS custom properties had identical values in both templates and merged cleanly.
Final size is **~990 KB**, not the ~1.5 MB estimated here, because step 5 composes the payload
rather than dumping the source JSONs (§5) and the tree is inlined once.

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
  Mollusca (5 observations between them) collapse to "other". `wireframe/index.html` used
  raw hex rather than the tokens and was missing `#6f6d64` entirely; **that conversion is
  done** - `index.html` carries 21 `--c-<Class>` references and no palette colour hard coded
  anywhere. The only hex literals left in `tpl_atlas.html` outside the two token blocks are
  `#ffffff` and `#14140f`, which are label ink, not palette. Check it with:

      grep -o '#[0-9a-f]\{6\}' scripts/templates/tpl_atlas.html | sort -u

- Colour follows the class, never the rank. A filter must not repaint survivors.
- **Text on a filled mark picks its ink by measured contrast, not by a threshold.** The
  seasonal heatmap shades each cell with its group's own hue at varying opacity. A fixed
  "opacity >= 0.5 means white text" rule reads fine on the blue and green ramps and washes
  out on Fungi's `#eda100`. `inkOn()` blends the fill over `--panel` for real, computes
  relative luminance, and returns whichever of white / `#14140f` actually has more contrast.
  It is theme independent by construction, which is why the heatmap redraws on a theme flip.
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
  The reconciled figure is whatever `tree_data.json` reports as leaves (955 at this refresh).
- `life_taxa` is the authoritative life list count and `meta.life_list_species` is now derived
  from it. An older snapshot had 4,754 ids against a hand set 4,739 - fixed by construction,
  not by editing a number. It currently reads **4,381**: 4,276 species from `species_counts`
  plus his farm records folded in. **4,276 and 4,381 are both correct and mean different
  things** - the first is what the endpoint returns, the second is what the gap subtraction
  must use, and §7 explains why the union is required. If a doc or a stat tile quotes one
  where the other belongs, that is the bug.

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

Since verified, same day:

- **`fetch_gap_pool.py` has run in full.** 4 requests, 1,807 species, 0 without a resolved
  family (the rank cache was already warm). Numbers in §7.
- **`fetch_observations.py --dry-run` completed against the live API.** 1,405 observations /
  955 species / 4,381 life taxa, with no change against what was on disk, so the guards were
  not exercised in anger. The 4,381 is 4,276 from `species_counts` plus his farm records
  folded in - the union §7 needs is done in the fetcher, not at render time.
- **The offline photo fallback works.** With every HTTP request blocked, the tree renders and
  12 taxon photos fall back to the "photo offline" placeholder with zero JS errors.

Still unverified:

- Whether GitHub Actions runners can reach the iNat API. Expected yes (open egress), but the
  first run needs eyes on it, not an assumption. Give the workflow a `workflow_dispatch`
  trigger and watch one manual run before trusting the cron.
- Whether `fetch_observations.py`'s empty-file and >10% shrink guards fire correctly. They
  have never been triggered, only read.

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

**Tool permissions.** `.claude/settings.json` pre-approves the build loop - Python, the read
tools, and the git commands up to `commit` - with `defaultMode: "acceptEdits"` so file edits
do not prompt. `git push`, `gh repo create` and anything else that publishes is deliberately
**not** on the allowlist, so those still ask. The build should run uninterrupted; making
something public should not.

**No MCP connector is required.** The iNat API is public read over plain HTTP with no auth.
If something proposes adding a connector or an API key for iNaturalist, it has not read §5.

**Verification checklist.** Before calling any change done:

- `python3 scripts/build_tree.py` - **the reconciliation assertions pass**. Do not check the
  printed counts against any figure written in this document; every one of them is a dated
  snapshot and Roy is actively logging, so a mismatch is the expected outcome, not a
  regression. What must hold is that every parent equals the sum of its children and the root
  equals `meta.total_obs`. The script says `totals reconcile at every level: OK` when it does.
- `python3 scripts/build_interest.py` - classes, families and genera all scored, coverage
  reported.
- `python3 scripts/build_pages.py` - offline safety assertions pass.
- `python3 scripts/screenshot.py --tabs index.html explore/*.html` - shoots each page and,
  with `--tabs`, every `[data-tab]` on it. Separates real console errors from the expected
  offline photo failures, flags a page that renders zero marks, and exits non-zero so it can
  gate a build. PNGs land in `shots/`, which is **gitignored** - attach them, do not expect
  them in `git status`. A real click is tried first and a DOM click is the fallback, so
  controls nested inside a not-yet-active panel (the Tree of Life view toggle) are reachable.
- `python3 scripts/build_pages.py --gap-top 30` - the gap ranking still looks sane and the
  top-50 mix still matches §7's table for the population you are measuring.
- Confirm the palette still comes from custom properties, not raw hex (§9 has the grep).
- Confirm no duplicate DOM ids in `index.html` - the merged page's one structural hazard:

      python3 -c "import re,collections,pathlib; \
      print([k for k,v in collections.Counter(re.findall(r'\sid=\"([^\"]+)\"', \
      pathlib.Path('index.html').read_text())).items() if v>1] or 'no duplicates')"

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
