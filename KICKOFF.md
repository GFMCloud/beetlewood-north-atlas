# Claude Code kickoff prompt

Paste the block below into a fresh Claude Code session opened in this repo. `CLAUDE.md` is
auto-loaded and points at `BUILD_SPEC.md`, which is the single source of truth.

**Steps 1 and 2 of the original kickoff are done** (2026-07-31): the atlas is assembled at
`index.html` and the gap checklist runs on real data with `COUNT_EXP` shipped at 0.5. The
prompt below covers what is left. The original four-step version is in git history if you
need it.

**Before you paste it**, run this on your own machine - it takes seconds and it settles that
the API is still reachable and the shape has not changed:

```bash
python3 scripts/fetch_observations.py --check
python3 scripts/fetch_gap_pool.py --check
```

The first prints his current farm observation count, the second the nearby pool size and
whether `ancestor_ids` is present. Compare them to whatever `data/farm_data.json` and
`data/gap_pool.json` currently hold rather than to a number in a doc - every count in this
repo is a dated snapshot.

---

We are finishing the Beetlewood Farms North Atlas. Read `BUILD_SPEC.md` before writing code -
it is the source of truth. The 5 step pipeline in `scripts/`, the data model, and the
assembled app at `index.html` are already built and verified. Do not rebuild them, and do not
hand-edit `index.html` - it is generated from `scripts/templates/tpl_atlas.html`.

Decisions are locked in BUILD_SPEC §2: hybrid data (pre baked JSON plus a weekly CI refresh),
the audience is a tool Roy actually uses, Roy is non technical and Windows only so anything he
touches is a browser URL, and hosting is GitHub Pages under the `gfmcloud` account, repo
`beetlewood-north-atlas`, in deploy-from-a-branch mode with a weekly Actions cron.

Build in this order, showing me the result at each step before moving on:

1. **Refresh automation.** A GitHub Actions workflow on a weekly schedule running the full
   5 step pipeline, committing refreshed JSON and rebuilt pages. Give it a
   `workflow_dispatch` trigger too, and run it manually once while I watch - BUILD_SPEC §12
   lists "can Actions runners reach the iNat API" as the one thing still unverified, and the
   first scheduled run is a bad place to find out. Pages must be in deploy-from-a-branch
   mode: a commit made with the default `GITHUB_TOKEN` does not trigger other workflows, so
   an Actions based Pages deploy would never fire.

2. **Deploy** to GitHub Pages and give me the URL. BUILD_SPEC §13 lists three settings that
   fail *silently* if wrong - the repo must be public, Pages source must be
   "Deploy from a branch", and Actions workflow permissions must be read **and write**. The
   last one is the nastiest: wrong there and the weekly job runs green, commits nothing, and
   the site quietly stops updating.

Guardrails: no credentials anywhere, the iNat API needs none. Do not lower `DELAY` in
`inat.py` to make a CI run faster - BUILD_SPEC §15 explains the margin. Show evidence -
`scripts/screenshot.py --tabs index.html`, console error checks, and confirm the pipeline's
reconciliation assertions still pass. Do not assert specific totals; Roy is actively logging
and the counts move every refresh. What must hold is that parents equal the sum of their
children. §13 is the verification checklist. Push back if any step looks wrong.

---

Notes for Graham (not part of the prompt):

- If you change host, both remaining steps change but the app itself does not. Tell Claude
  Code "host on Cloudflare Pages" or "host on S3 + CloudFront".
- The in browser "Refresh now" button is deliberately out of the first pass. Add it once the
  weekly CI refresh is proven.
- `COUNT_EXP` in `build_pages.py` and the interest weights in `build_interest.py` are the two
  knobs worth tuning after you have lived with real output. Both are constants at the top of
  their files. `python3 scripts/build_pages.py --gap-top 30` shows the effect without
  writing anything.
- Deliberately parked, with reasoning, in BUILD_SPEC §14: the seasonal co-occurrence graph is
  the strongest candidate for a sixth tab.
