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

- `scripts/` - a 5 step pipeline, all of it working. `scripts/README.md` documents it.
- `explore/` - two generated taxonomy views (explorer + sunburst), both rendering
  `data/tree_data.json`.
- `wireframe/index.html` - the 4 tab dashboard prototype. Source material for the Overview,
  Seasonal Calendar and What He Logs tabs. Being replaced by the assembled app.
- `archive/` - superseded prototypes kept for reference. Not part of the product.

The job now is assembling one single page app from these pieces and shipping it. BUILD_SPEC
§ "What to build now" has the ordered plan.

## Hard rules

1. **Self contained, offline safe.** Everything inline - CSS, JS, data, D3. No CDN, no
   `localStorage`/`sessionStorage`. Opens by double click. `build_pages.py` asserts this.
   The one exception is taxon photos, which are remote iNat URLs with a graceful
   "photo offline" fallback. Keep that fallback.
2. **Edit templates, never generated HTML.** `scripts/templates/*.html` -> `build_pages.py`
   -> `explore/*.html`. Hand edits to the output are overwritten.
3. **Palette is fixed and validated.** Reference the `--c-<Class>` custom properties, never
   raw hex. Colour follows the iconic class, never the rank. BUILD_SPEC §9 is the complete
   chart convention - there is no `dataviz` skill in this repo, so do not go hunting for one.
4. **No credentials, ever.** The iNat API is public read and needs none.
5. **Totals must reconcile.** `build_tree.py` asserts every parent equals the sum of its
   children. Do not relax those assertions to make a change pass.
6. **Show evidence.** Screenshots, console error checks, command output. Graham wants proof,
   not assertions of success. Push back if a direction looks wrong. BUILD_SPEC §13 lists the
   prerequisites, including the headless browser the screenshots need - install it before you
   need it rather than skipping verification when it is missing.
