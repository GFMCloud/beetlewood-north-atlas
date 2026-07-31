# scripts/ - the data pipeline

Five steps. Each writes into `data/`; the last generates the HTML in `explore/`.

```bash
python3 scripts/fetch_observations.py   # 0. iNat API -> data/farm_data.json    (network)
python3 scripts/fetch_taxonomy.py       # 1. iNat API -> data/taxonomy.json     (network)
python3 scripts/build_interest.py       # 2. fold     -> data/interest.json     (offline)
python3 scripts/build_tree.py           # 3. fold     -> data/tree_data.json    (offline)
python3 scripts/fetch_gap_pool.py       # 4. iNat API -> data/gap_pool.json     (network)
python3 scripts/build_pages.py          # 5. inline   -> explore/*.html         (offline)
```

Steps 2, 3 and 5 are offline and run in well under a second, so iterating on visuals never
needs the API. `inat.py` is a shared helper, not a step.

Both network scripts take `--check`: one tiny request that prints the response shape. Run it
before a full pull - it is the cheapest way to catch a changed endpoint.

## Why each step exists

**0. `fetch_observations.py`** - rebuilds `farm_data.json` from the live API. Without this
step nothing new Roy logs ever reaches the atlas: every other script reads `farm_data.json`
and none of them produce it, so the whole site would silently freeze at whatever snapshot was
committed. The CSV export in `data/` is reference only - iNat generates exports on request
and emails them, so CI cannot fetch one.

Guards: refuses to write an empty file, and refuses a drop of more than 10% in observation
count unless you pass `--allow-shrink`. A cron that fails loudly beats one that quietly
publishes an empty atlas. `--dry-run` pulls and diffs without writing.

**1. `fetch_taxonomy.py`** - the CSV and `farm_data.json` carry only iconic class, genus and
scientific name, which cannot express *Insecta -> Coleoptera -> Cerambycidae -> Typocerus ->
Typocerus velutinus*. `GET /v1/taxa/ID1,ID2,...` returns each taxon's full ancestor chain.
952 farm taxa, 30 per call, ~32 calls, ~40 seconds. Result: 952/952 resolved, 951 with order,
947 with family. Cached - a re-run after new species only fetches the new taxa; `--force`
refetches everything.

**2. `build_interest.py`** - scores how interested Roy is in each group, at class, family and
genus, with **one** formula (BUILD_SPEC §6). Recency is anchored to `--asof`, default today,
never to a date baked into the data. Also emits the family multiplier the gap ranking needs;
BUILD_SPEC §7 explains why a multiplier rather than a family score replacing the class score.

**3. `build_tree.py`** - folds observations plus ancestry into the hierarchy every view
renders. Current output: 1,393 observations, 950 leaves, 1,930 taxa across 5 ranks.

**4. `fetch_gap_pool.py`** - every research grade species recorded within the radius, with
counts, plus resolved order and family names. Ancestor names come from `taxonomy.json` where
already known and a batched `/taxa` lookup otherwise, cached in `taxa_cache.json`.

**5. `build_pages.py`** - inlines data and vendored D3 into the templates.

## The one non-obvious rule

69 records are identified only as far as a genus or family. Folded naively they get absorbed
into an internal node and disappear from the leaf count - 881 leaves instead of 950 - so the
totals quietly stop reconciling with the headline figures.

Instead each such group becomes an explicit child: *"Scutellaria sp."*, *"Curculionidae
(undetermined)"*. `build_tree.py` then **asserts** that every parent equals the sum of its
children and that the root equals `meta.total_obs`, so the build fails loudly rather than
shipping numbers that do not add up. Do not relax those assertions to make a change pass.

## Editing the views

`explore/explorer-2pane.html` and `explore/sunburst-zoom.html` are **generated**. Edit
`scripts/templates/*.html` and re-run `build_pages.py` - hand edits to the 400-650 KB output
files are overwritten.

Templates carry two placeholders, `/*__DATA__*/` and `/*__D3__*/`. `build_pages.py` inlines
the data and the vendored D3 (`scripts/vendor/d3.v7.min.js`, v7.9.0), then asserts no external
`<script src>` and no `localStorage`/`sessionStorage` survived - **before** writing the file,
so a failed check cannot leave a broken artifact on disk.

DOM ids in the two templates are prefixed `ex-` and `sb-` so both views can live in one
merged page. Keep new ids prefixed; BUILD_SPEC §8 has the detail and the smoke test result.

Running the offline steps on unchanged inputs reproduces the shipped files byte identically.

## No credentials

The API is public read. There are no tokens, keys or logins anywhere in this pipeline, and
none should ever be added. Rate limits (~60 req/min, <10k/day) are respected by 30 id
batching and a 1.1 s pace, both centralised in `inat.py`.
