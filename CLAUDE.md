# Beetlewood Farms North Atlas

Auto-loaded context for Claude Code. **`BUILD_SPEC.md` is the single source of truth** for
decisions, data model, formulas and hosting. Read it before writing code. There is no
`HANDOFF.md` any more - it was merged into BUILD_SPEC on 2026-07-31 because the two docs had
drifted into contradicting each other.

## What this is

An interactive atlas over Roy F Morris II's (`roymorrisii`, user_id 764712) iNaturalist
records, scoped to his ~6 acre farm in Griffin, GA. Roy is Graham's dad, an entomologist who
specialises in longhorn beetles. Farm subset: ~1,400 observations / ~950 species / 2023-2026, and growing - he logs actively,
so treat any exact count in the docs as a dated snapshot.
His full account is 8,287 obs across several countries - **the account is not the farm**.

## State

- `index.html` - **the product.** The assembled 5 tab atlas, generated. ~990 KB.
- `scripts/` - a 5 step pipeline, all of it working. `scripts/README.md` documents it.
- `explore/` - two generated taxonomy views (explorer + sunburst), both rendering
  `data/tree_data.json`. Still shipped as standalone single-view pages; the atlas ports
  both into its Tree of Life tab rather than linking to them.
- `wireframe/index.html` - the 4 tab prototype. **Superseded** - it was the source material
  for three tabs and is kept only for reference. Do not build against it.
- `archive/` - superseded prototypes kept for reference. Not part of the product.

The app is assembled and the gap checklist runs on real data. What remains is the weekly
GitHub Actions refresh and the deploy. BUILD_SPEC § "State of the build" has the detail.

## Hard rules

1. **Self contained, offline safe.** Everything inline - CSS, JS, data, D3. No CDN, no
   `localStorage`/`sessionStorage`. Opens by double click. `build_pages.py` asserts this.
   The one exception is taxon photos, which are remote iNat URLs with a graceful
   "photo offline" fallback. Keep that fallback.
2. **Edit templates, never generated HTML.** `scripts/templates/*.html` -> `build_pages.py`
   -> `index.html` and `explore/*.html`. Hand edits to the output are overwritten.
3. **Do not read the big generated files - read the templates.** `index.html` is 991 KB,
   `explore/sunburst-zoom.html` 646 KB, `explorer-2pane.html` 376 KB, `wireframe/index.html`
   466 KB, and almost all of that is inlined JSON and vendored D3 you already have in `data/`
   and `scripts/vendor/`. Opening one whole burns a large slice of context on a blob you can
   query with two lines of Python. Read `scripts/templates/*.html` instead - `tpl_atlas.html`
   is the whole app at ~45 KB, the other two ~20 KB each, none with data. For the wireframe,
   grep out the structure rather than reading it end to end.
4. **Palette is fixed and validated.** Reference the `--c-<Class>` custom properties, never
   raw hex. Colour follows the iconic class, never the rank. BUILD_SPEC §9 is the complete
   chart convention - there is no `dataviz` skill in this repo, so do not go hunting for one.
5. **No credentials, ever.** The iNat API is public read and needs none.
6. **Totals must reconcile.** `build_tree.py` asserts every parent equals the sum of its
   children. Do not relax those assertions to make a change pass.
7. **Show evidence.** Screenshots, console error checks, command output. Graham wants proof,
   not assertions of success. Push back if a direction looks wrong. BUILD_SPEC §13 lists the
   prerequisites, including the headless browser the screenshots need - install it before you
   need it rather than skipping verification when it is missing.
