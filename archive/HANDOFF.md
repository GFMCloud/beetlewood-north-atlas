# Claude Code Handoff — Beetlewood Farms North Atlas (visualization track)

Read this first. It orients you to the project, what's already built, the design/tech
conventions to hold to, and the visualization directions we're actively exploring. For the
live-data build details (iNat API endpoints, gap-list ranking, interest scoring, data
caveats) see **`BUILD_SPEC.md`** — this handoff doesn't repeat them.

You're picking up from a series of chat sessions with Graham. Nothing here needs prior
context beyond these files.

## The one-paragraph what & why

An interactive dashboard over one iNaturalist observer's records, **scoped to a single
property**: Roy F Morris II (`roymorrisii`, user_id 764712), an entomologist specializing in
longhorn beetles, and his ~6-acre farm "Beetlewood Farms North" at 376 Lamar County Line Rd,
Griffin, GA (lat 33.18, lng -84.20). Roy is Graham's dad; this is a personal project, and the
dashboard may become either a gift Graham shows him or a tool Roy uses — undecided, and it
shapes polish-vs-depth. The farm subset is 1,393 observations / ~950 species / 2023–2026,
75% research-grade, heavily skewed to insects (Insecta 1,090 obs → 702 genera; then Plantae
147, Aves 78, a long tail). His full account is 8,287 obs across several countries — **do not
treat the whole account as "the farm."**

## What's already built (all in this folder)

- `wireframe/index.html` — the main dashboard prototype, four tabs, **self-contained**
  (real data embedded, no network). Views: **Tree of Life** (sunburst), **Seasonal Calendar**
  (phenology heatmap + species-accumulation curve), **What He Logs** (derived interest
  profile), **Gap Checklist** (mocked; the only view needing the live API).
- `explore/explorations.html` — a **visualization playground** built to answer "what should
  the Tree of Life tab be?" Two prototypes on the real data, toggled at top:
  - **Interactive radial tree** — collapsible class → genus → species dendrogram (d3.tree,
    radial). Genera are capped per class (top 14 + an expandable "+N more genera" node) so
    the Insecta skew doesn't eat the whole circle. "Show every genus" removes the cap.
  - **Brain map** — force-directed graph (d3-force) with two edge modes:
    - *Taxonomy*: genus → class hubs. Same structure as the tree, less legible.
    - *Seasonal co-occurrence*: links genera Roy logs on the **same days**; a min-shared-days
      slider (2–5) controls density. Clusters = things he photographs in the same session.
  - D3 v7 is **vendored inline** in that file (no CDN) so it stays offline-safe.

## Recommendation on the table (Graham hasn't finalized — confirm before ripping things out)

The two exploration prototypes do different jobs, and the finding was that they're **not
competitors**:
- The **radial tree** is the better *replacement* for the sunburst in the Tree of Life tab —
  same taxonomic job, far more legible, and it visually echoes real phylogenetic trees (it
  resonates for an entomologist).
- The brain map's **taxonomy** mode is redundant with the tree (a prettier hairball).
- The brain map's **co-occurrence** mode shows something *neither* the sunburst nor the tree
  can: field-session associations. That earns its own place.

**Proposed direction:** replace the sunburst with the radial tree; add co-occurrence as its
own new tab; drop the taxonomy brain map. Net result = three distinct lenses (structure /
timing / field-associations) instead of two overlapping ones. **Confirm with Graham before
committing** — he may want to keep the taxonomy brain map or the sunburst too.

Honest caveats to preserve if you ship these:
- The radial tree is only class → genus → species until the taxonomy enrichment (BUILD_SPEC)
  adds order/family. Until then it's a solid 3-rank tree, not a full phylogeny.
- Co-occurrence is "**logged together**," not "found together ecologically" — a big mothing
  night links every moth photographed that evening. Label it so Roy doesn't over-read it. The
  threshold slider is what separates signal from same-session coincidence.

## Design & tech conventions — hold to these for consistency

1. **Self-contained single HTML files.** Everything inline: CSS, JS, data, and any library
   (D3 is vendored, not CDN-loaded). The files must open by double-click and work offline.
   No build step required to view. No `localStorage`/`sessionStorage` (breaks in some
   sandboxes) — keep state in memory.
2. **Palette is a validated data-viz system**, not ad-hoc hex. Categorical hues are
   colorblind-safe and assigned in fixed order; sequential ramp is single-hue blue; dark mode
   is re-stepped, not flipped. Colors live as CSS custom properties — reference roles, never
   raw hex. The fixed class→color mapping used across every view:

   | class | Insecta | Plantae | Aves | Fungi | Arachnida | Reptilia | Amphibia | Mammalia | other |
   |---|---|---|---|---|---|---|---|---|---|
   | light | #2a78d6 | #eb6834 | #1baf7a | #eda100 | #e87ba4 | #008300 | #4a3aa7 | #e34948 | #b7b4aa |
   | dark  | #3987e5 | #d95926 | #199e70 | #c98500 | #d55181 | #008300 | #9085e9 | #e66767 | #6f6d64 |

   Color follows the **entity (class)**, never rank; a filter that changes series count must
   not repaint survivors. If you add a chart, read the `dataviz` skill first and keep to this
   system.
3. **Interaction defaults:** hover tooltip on every mark; zoom/pan on the big canvases; drag
   on force nodes; direct labels selectively (never a label on every one of 950 nodes).
4. **The wireframe is dashboard-shell (light default, theme toggle); the explorations are
   dark** to match the Obsidian/phylogeny references. Pick per view, but keep both modes
   working if you add a toggle.

## Data you have locally (no API needed to iterate on visuals)

- `data/farm_data.json` — 1,393 farm records + precomputed `class_interest`, `genus_interest`,
  and `life_taxa`/`farm_taxa` sets. Schema documented in `BUILD_SPEC.md` § Data shipped.
- `data/observations764712.csv` — raw 40-column iNat export (source of truth).

Everything visual can be prototyped against these offline. The API is only needed for the gap
list's "what others recorded nearby" pool and for taxonomy enrichment (order/family) — see
BUILD_SPEC. **The iNat API is CORS-open and reachable from a normal browser/machine; it is
often blocked from headless CI sandboxes** — if a fetch fails in an automated context, that's
the environment, not your code.

## A backlog of visualization ideas worth exploring (Graham's call on priority)

- **Order/family enrichment** for the radial tree — the single biggest upgrade; turns a
  3-rank tree into a real phylogeny (BUILD_SPEC has the `/taxa` ancestry calls).
- **Light-mode radial tree** to match the reference tree images (they're on white).
- **Per-species phenology** — the current calendar is class×month; drill to a species'
  emergence weeks (e.g. when to look for each *Catocala*). `week_of_year` histogram or client
  compute.
- **Map view** — his coords are tight around the farm; a fine-grained within-property map
  (habitat patches) could be a fifth lens. Watch the 87 obscured-coordinate records.
- **Time scrubber** — animate species accumulation / co-occurrence growth 2023→2026.
- **Cerambycidae focus mode** — his specialty; a filtered sub-view where he's the authority.
- **"New this year" novelty highlighting** across any view — he's actively logging.

## How to run & verify

Open the HTML files directly in a browser. For automated checks, headless Chromium +
Playwright works; screenshot each tab and confirm no console errors before calling a change
done (Graham wants evidence — command output, screenshots, diffs — not assertions of
success). If you regenerate `farm_data.json`, re-run the small Python prep that derived it
from the CSV (interest-scoring formula is in BUILD_SPEC) and sanity-check counts land near
1,393 obs / 950 species.

## Guardrails (Graham's working preferences)

- Never handle raw credentials; the iNat public API needs none. Env vars / CLI-native auth if
  anything ever does.
- Make sensible calls on low-stakes work and proceed; check before anything irreversible.
- Show evidence of what you did. Push back if you think a direction is wrong.
- Plan multi-step work first, then execute without per-step permission asks; ask before
  creating files or sending anything external.
- He uses hyphens, not em dashes, in anything he'll paste elsewhere; plain text, straight
  quotes.
