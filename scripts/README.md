# scripts/ - the data pipeline

Five steps. Each writes into `data/`; the last generates the HTML in `explore/`.

```bash
python3 scripts/fetch_observations.py   # 0. iNat API -> data/farm_data.json    (network)
python3 scripts/fetch_taxonomy.py       # 1. iNat API -> data/taxonomy.json     (network)
python3 scripts/build_interest.py       # 2. fold     -> data/interest.json     (offline)
python3 scripts/build_tree.py           # 3. fold     -> data/tree_data.json    (offline)
python3 scripts/fetch_gap_pool.py       # 4. iNat API -> data/gap_pool.json     (network)
python3 scripts/build_pages.py          # 5. inline   -> index.html + explore/  (offline)
```

Steps 2, 3 and 5 are offline and run in well under a second, so iterating on visuals never
needs the API. `inat.py` is a shared helper, not a step.

**Two scopes live in `inat.py` and must not be conflated:** `FARM_RADIUS_KM = 2` is the
property, `NEARBY_RADIUS_KM = 15` is the gap pool's "around here". Pulling the farm at 15 km
returns 1,747 observations instead of 1,393.

Both network scripts take `--check`: one tiny request that prints the response shape. Run it
before a full pull - it is the cheapest way to catch a changed endpoint.

## Why each step exists

**0. `fetch_observations.py`** - rebuilds `farm_data.json` from the live API. Without this
step nothing new Roy logs ever reaches the atlas: every other script reads `farm_data.json`
and none of them produce it, so the whole site would silently freeze at whatever snapshot was
committed. The CSV export is reference only and **deliberately not in this repo** - it
carries obscured-species coordinates and `.gitignore` blocks `*.csv` (BUILD_SPEC §11). iNat
generates exports on request
and emails them, so CI cannot fetch one.

Guards: refuses to write an empty file, and refuses a drop of more than 10% in observation
count unless you pass `--allow-shrink`. A cron that fails loudly beats one that quietly
publishes an empty atlas. `--dry-run` pulls and diffs without writing.

**1. `fetch_taxonomy.py`** - the CSV and `farm_data.json` carry only iconic class, genus and
scientific name, which cannot express *Insecta -> Coleoptera -> Cerambycidae -> Typocerus ->
Typocerus velutinus*. `GET /v1/taxa/ID1,ID2,...` returns each taxon's full ancestor chain.
About 950 farm taxa, 30 per call, ~32 calls, ~40 seconds. At the snapshot: 952/952 resolved,
951 with order, 947 with family. Cached - a re-run after new species only fetches the new taxa; `--force`
refetches everything.

**2. `build_interest.py`** - scores how interested Roy is in each group, at class, family and
genus, with **one** formula (BUILD_SPEC §6). Recency is anchored to `--asof`, default today,
never to a date baked into the data. Also emits the family multiplier the gap ranking needs;
BUILD_SPEC §7 explains why a multiplier rather than a family score replacing the class score.

**3. `build_tree.py`** - folds observations plus ancestry into the hierarchy every view
renders. Output at the 2026-07-30 snapshot was 1,393 observations, 950 leaves, 1,930 taxa
across 5 ranks; the counts grow as Roy logs. What matters is that the assertions pass.

**4. `fetch_gap_pool.py`** - every research grade species recorded within the radius, with
counts, plus resolved order and family names. Ancestor names come from `taxonomy.json` where
already known and a batched `/taxa` lookup otherwise, cached in `taxa_cache.json`.

**5. `build_pages.py`** - inlines data and vendored D3 into the templates, and builds the
product: `index.html`, the assembled atlas. The two `explore/` pages are still generated as
standalone single-view files.

It does **not** just dump the JSONs into the page. `farm_data.json` is 550 KB and the atlas
needs four fields of it; the gap subtraction needs 4,381 life-list ids the browser would only
use to compute one boolean per pool row. Both fold here, offline, so the page ships
aggregates: accumulation points, a group x month grid, and gap rows that already carry their
interest weight. `gap_rows()` is where the §7 subtraction and weighting live - read it before
changing the ranking.

    python3 scripts/build_pages.py --gap-top 30    # print the ranked gaps, write nothing

`COUNT_EXP` lives at the top of the file and ships at 0.5. BUILD_SPEC §7 has the calibration
and, importantly, which population it was measured on.

## The one non-obvious rule

69 records are identified only as far as a genus or family. Folded naively they get absorbed
into an internal node and disappear from the leaf count - 881 leaves instead of 950 - so the
totals quietly stop reconciling with the headline figures.

Instead each such group becomes an explicit child: *"Scutellaria sp."*, *"Curculionidae
(undetermined)"*. `build_tree.py` then **asserts** that every parent equals the sum of its
children and that the root equals `meta.total_obs`, so the build fails loudly rather than
shipping numbers that do not add up. Do not relax those assertions to make a change pass.

## Editing the views

`index.html`, `explore/explorer-2pane.html` and `explore/sunburst-zoom.html` are **generated**.
Edit `scripts/templates/*.html` and re-run `build_pages.py` - hand edits to the 376 KB /
646 KB / 991 KB output files are overwritten. Do not open them to read the code either; the
templates are the same views at ~20-45 KB with no inlined data.

Templates carry four placeholders and use whichever they need: `/*__DATA__*/` and
`/*__TREE__*/` (both the tree JSON), `/*__ATLAS__*/` (the composed atlas payload) and
`/*__D3__*/` (vendored `d3.v7.min.js`, v7.9.0). `build_pages.py` then asserts no external
`<script src>`, no `localStorage`/`sessionStorage`, and no unfilled placeholder survived -
**before** writing the file, so a failed check cannot leave a broken artifact on disk.

**Namespacing, and why prefixing ids was not enough.** The two standalone templates prefix
their ids `ex-` and `sb-`. That is necessary but not sufficient once they share a page with
the shell: all three used `.card`, `.stat`, `.crumb`, `.note` and `.btn` for different things,
so the explorer's thumbnail cards would have inherited the shell's panel padding. In
`tpl_atlas.html` the explorer is `x-*` classes / `ex-*` ids scoped under `.exv`, and the
sunburst is `s-*` / `sb-*` under `.sbv`. Keep new names inside those namespaces, and check
`index.html` for duplicate ids after any change - BUILD_SPEC §8 and §13.

Running the offline steps on unchanged inputs reproduces the shipped files byte identically.

## Verifying a change

`scripts/screenshot.py` is not a pipeline step - it is the evidence tool. It screenshots each
page, reports console errors, treats offline taxon photos as expected rather than as failures,
fails a page that renders nothing at all, and exits non-zero so CI can gate on it.

```bash
pip3 install --user playwright && python3 -m playwright install chromium   # once
python3 scripts/screenshot.py explore/*.html
python3 scripts/screenshot.py --tabs index.html   # clicks every [data-tab] and shoots each
```

Use `python3 -m playwright`, not a bare `playwright` - pip puts the CLI somewhere that is
usually not on PATH.

PNGs land in `shots/`, which is **gitignored** - they will not show up in `git status`, so
attach them from disk rather than expecting them in a diff.

`--tabs` tries a real click first so a control hidden behind an overlay still fails the run,
and falls back to a DOM click. The fallback exists for one specific case: the Tree of Life
view toggle lives inside its own panel, and DOM order means the tool reaches it after some
other panel is showing, where a real click cannot land. Its handler activates the containing
tab, so the fallback is safe rather than a way of pretending something was clickable.

## Rate limits

iNaturalist asks for "about 1 per second, and around 10k API requests a day", and warns that
over 5 GB of media an hour may result in a permanent block. `DELAY = 1.1` s in `inat.py` puts
us at ~55 req/min - their forum has repeated 429 reports at exactly 60/min, so the margin is
deliberate. **Do not lower it to speed a run up.** A full cold run is ~100 requests; a warm
weekly one is a handful. `get()` honours `Retry-After` on a 429 and backs off exponentially
otherwise. BUILD_SPEC section 15 has the full policy and where we knowingly deviate.

Every fetcher caches, and `fetch_gap_pool.py` checkpoints every 10 batches, so a dropped
connection costs one batch rather than the whole run. Re-run and it resumes.

## No credentials

The API is public read. There are no tokens, keys or logins anywhere in this pipeline, and
none should ever be added.
