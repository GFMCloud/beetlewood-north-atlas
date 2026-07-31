# Beetlewood Farms North Atlas

Interactive atlas over Roy Morris's (`roymorrisii`) iNaturalist records, scoped to his 6 acre
farm in Griffin, GA. Five views: an Overview, a taxonomic Tree of Life, a seasonal phenology
calendar, a data derived "what he logs" interest profile, and a gap checklist of nearby
species he has not recorded yet, ranked by that interest profile.

**`BUILD_SPEC.md` is the source of truth** for decisions, formulas, data model and hosting.
Read it before changing anything.

## Status

**Pre assembly.** The pipeline and the two taxonomy views are built and verified; the app
itself is not assembled yet.

- `scripts/` - 5 step pipeline, working. Offline steps run in under a second.
- `explore/explorer-2pane.html`, `explore/sunburst-zoom.html` - generated taxonomy views,
  self contained, open by double click.
- `wireframe/index.html` - the original 4 tab prototype on real data, with a mocked gap list.
  Source material for three of the five tabs. Being replaced.
- `archive/explorations.html` - radial tree + co-occurrence brain map. Not in the product,
  kept because the co-occurrence lens is the strongest candidate for a future tab.

Next step is assembling one single page app from these pieces. `KICKOFF.md` has the prompt.

## Layout

```
CLAUDE.md      auto-loaded pointer for Claude Code (defers to BUILD_SPEC.md)
BUILD_SPEC.md  decisions, data model, formulas, hosting, caveats - START HERE
KICKOFF.md     the prompt to paste into a fresh Claude Code session
README.md      this file
scripts/       the pipeline + templates + vendored D3 (scripts/README.md)
data/          farm_data, taxonomy, interest, tree_data (+ gap_pool after step 4)
explore/       generated taxonomy views
wireframe/     4 tab dashboard prototype
archive/       superseded prototypes
```

## Running it

Nothing here needs a server, and Roy never runs any of it - all builds happen in CI and he
only ever opens a URL.

```bash
python3 scripts/fetch_observations.py --check   # validate the API, 2 requests
python3 scripts/fetch_observations.py           # step 0  (network)
python3 scripts/fetch_taxonomy.py               # step 1  (network)
python3 scripts/build_interest.py               # step 2  (offline)
python3 scripts/build_tree.py                   # step 3  (offline)
python3 scripts/fetch_gap_pool.py               # step 4  (network)
python3 scripts/build_pages.py                  # step 5  (offline)
```

The iNat API is public read and needs no credentials. It is reachable from a normal machine
but is often blocked from sandboxed environments - a fetch failure there is the environment,
not the code.

## Key facts

- Observer: `roymorrisii` (user_id 764712), entomologist, Cerambycidae specialist.
- Farm: 376 Lamar County Line Rd, Griffin, GA - lat 33.18, lng -84.20, **2 km scope**.
  All 1,393 records sit within 0.64 km of centre; the next cluster is ~10 km out.
- Nearby scope, for the gap pool only: 15 km, which holds 1,807 research-grade species.
- Farm subset: 1,393 observations, 950 species, 2023-2026, 75% research grade.
- Full account (not the farm): 8,287 observations, 4,276 species, several countries.
- iNat API v1, base `https://api.inaturalist.org/v1`, no auth, CORS open, ~60 req/min.
