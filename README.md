# Beetlewood Farms North Atlas

Interactive atlas over Roy Morris's (`roymorrisii`) iNaturalist records, scoped to his 6 acre
farm in Griffin, GA. Five views: an Overview, a taxonomic Tree of Life, a seasonal phenology
calendar, a data derived "what he logs" interest profile, and a gap checklist of nearby
species he has not recorded yet, ranked by that interest profile.

**`BUILD_SPEC.md` is the source of truth** for decisions, formulas, data model and hosting.
Read it before changing anything.

## Status

**Assembled, not yet deployed.** The app is built and running on real data; what remains is
the weekly refresh job and the deploy.

- `index.html` - **the atlas.** Five tabs, self contained, ~990 KB, opens by double click.
  Generated - edit `scripts/templates/tpl_atlas.html`, never this.
- `scripts/` - 5 step pipeline, working. Offline steps run in under a second.
- `explore/explorer-2pane.html`, `explore/sunburst-zoom.html` - the two taxonomy views as
  standalone pages. The atlas ports both into its Tree of Life tab; these are still generated
  because a single view is sometimes the thing you want.
- `wireframe/index.html` - the original 4 tab prototype with a mocked gap list. **Superseded**,
  kept for reference only.
- `archive/explorations.html` - radial tree + co-occurrence brain map. Not in the product,
  kept because the co-occurrence lens is the strongest candidate for a future tab.

Remaining: a weekly GitHub Actions cron running the pipeline and committing the refreshed
JSON plus rebuilt pages, then GitHub Pages in deploy-from-a-branch mode. BUILD_SPEC §13 lists
three Pages/Actions settings that fail **silently** if wrong - read it before deploying.

## Layout

```
CLAUDE.md      auto-loaded pointer for Claude Code (defers to BUILD_SPEC.md)
BUILD_SPEC.md  decisions, data model, formulas, hosting, caveats - START HERE
KICKOFF.md     the prompt to paste into a fresh Claude Code session
README.md      this file
index.html     THE PRODUCT - the assembled atlas (generated)
scripts/       the pipeline + templates + vendored D3 (scripts/README.md)
data/          farm_data, taxonomy, interest, tree_data, gap_pool, taxa_cache
explore/       generated single-view taxonomy pages
shots/         screenshot.py output - gitignored
wireframe/     superseded 4 tab prototype
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
  Every farm record sits within 0.64 km of centre; the next cluster is ~10 km out.
- Nearby scope, for the gap pool only: 15 km, which holds 1,807 research-grade species.
- Farm subset (2026-07-31 refresh, grows on every run): 1,405 observations, 955 species,
  1,939 taxa, 2023-2026, 75% research grade. **Every count here is a dated snapshot** - Roy
  logs actively. The invariant is that the totals reconcile, which `build_tree.py` asserts.
- Gap checklist at that refresh: 838 species he has never recorded anywhere, 1,053 not yet
  recorded on the farm.
- Full account (not the farm): ~8,300 observations, several countries. His life list reads
  4,276 from `species_counts` and 4,381 once farm records are folded in - both correct, see
  BUILD_SPEC §11.
- iNat API v1, base `https://api.inaturalist.org/v1`, no auth, CORS open, ~60 req/min.
