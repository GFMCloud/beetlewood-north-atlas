# Claude Code kickoff prompt

Paste the block below into a fresh Claude Code session opened in this repo. `CLAUDE.md` is
auto-loaded and points at `BUILD_SPEC.md`, which is the single source of truth.

**Before you paste it**, run these two commands on your own machine - they take seconds and
they settle the one thing nobody has verified:

```bash
python3 scripts/fetch_observations.py --check
python3 scripts/fetch_gap_pool.py --check
```

The first prints his current farm observation count (compare to the 1,393 snapshot). The
second prints the nearby species pool size and whether `ancestor_ids` is present. If the pool
is small, say so in the prompt - the Gap Checklist may not deserve a tab.

---

We are assembling the Beetlewood Farms North Atlas into one shippable app. Read
`BUILD_SPEC.md` before writing code - it is the source of truth. The 5 step pipeline in
`scripts/`, the two taxonomy views in `explore/`, and the data model are already built and
verified. Do not rebuild them.

Decisions are locked in BUILD_SPEC §2: hybrid data (pre baked JSON plus a weekly CI refresh),
the audience is a tool Roy actually uses, Roy is non technical and Windows only so anything he
touches is a browser URL, the Tree of Life is one tab with an Explorer <-> Sunburst toggle,
and hosting is GitHub Pages under the `gfmcloud` account, repo `beetlewood-north-atlas`, in
deploy-from-a-branch mode with a weekly Actions cron.

Build in this order, showing me the result at each step before moving on:

1. **Atlas shell.** One self contained single page app with tabs: Overview, Tree of Life
   (Explorer <-> Sunburst toggle, porting both `explore/` views into this one tab), Seasonal
   Calendar, What He Logs, Gap Checklist. Template generated through `build_pages.py`,
   offline safe, palette from the `--c-<Class>` custom properties. BUILD_SPEC §8 covers what
   has already been done to make the two views mergeable and what has not; §9 flags that the
   wireframe uses raw hex and needs converting to tokens.

2. **Gap checklist, real data.** Run `fetch_gap_pool.py` first and look at the numbers before
   building the view - the pool is 1,807 species and his life list is 4,276. Follow BUILD_SPEC §7 exactly, including the `family_multiplier` weight -
   the obvious `family_interest ?? class_interest` rule is a known bug that inverts the
   ranking, and §7 explains why. `COUNT_EXP` is an open calibration; start at 0.5, show me the
   top 30 rows, and we will tune it together.

3. **Refresh automation.** A GitHub Actions workflow on a weekly schedule running the full
   5 step pipeline, committing refreshed JSON and rebuilt pages. Pages must be in
   deploy-from-a-branch mode - a commit made with the default `GITHUB_TOKEN` does not trigger
   other workflows, so an Actions based Pages deploy would never fire.

4. **Deploy** to GitHub Pages and give me the URL.

Guardrails: no credentials anywhere, the iNat API needs none. Show evidence - screenshots of
each tab, console error checks, and confirm the pipeline's reconciliation
assertions still pass. Do not assert specific totals - Roy is actively logging and the counts
move every refresh; what must hold is that parents equal the sum of their children. BUILD_SPEC §12 lists what has never been verified
against the live API; check those rather than assuming. §13 is the verification checklist.
Push back if any step looks wrong.

---

Notes for Graham (not part of the prompt):

- If you change host, only steps 3-4 change. Tell Claude Code "host on Cloudflare Pages" or
  "host on S3 + CloudFront" and the app itself is unaffected.
- The in browser "Refresh now" button is deliberately out of the first pass. Add it once the
  weekly CI refresh is proven.
- `COUNT_EXP` and the interest weights in `build_interest.py` are the two knobs worth tuning
  after you see real output. Both are constants at the top of their files.
