#!/usr/bin/env python3
"""Step 5 of 5 - inline data (and D3) into the templates to produce the shipped pages.

The shipped HTML files are GENERATED. Edit scripts/templates/*.html, then re-run this;
do not hand-edit the 400 KB - 1.5 MB files in explore/ or atlas.html, your changes will
be overwritten.

Placeholders each template may carry:
    /*__DATA__*/   contents of data/tree_data.json          (both taxonomy views)
    /*__TREE__*/   same, for the atlas (one copy, shared by both views)
    /*__ATLAS__*/  the composed atlas payload built below
    /*__D3__*/     scripts/vendor/d3.v7.min.js

Inlining is what keeps the project convention: self-contained single files that open by
double-click and work offline, with no CDN and no build step to *view*.

THE ATLAS PAYLOAD IS COMPOSED, NOT DUMPED. farm_data.json is 550 KB and the atlas needs
four fields of it; the gap subtraction needs 4,381 life-list ids that the browser would
only use to compute one boolean per pool row. Both are folded here instead, offline, so
the page ships aggregates rather than raw records. See gap_rows() for the subtraction.

Usage:
    python3 scripts/build_pages.py
    python3 scripts/build_pages.py --gap-top 30    # print the ranked gap list and stop
"""
import argparse
import collections
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "scripts" / "templates"
DATA = ROOT / "data"

# (template, output, needs D3)
PAGES = [
    ("tpl_explorer.html", "explore/explorer-2pane.html", False),
    ("tpl_sunburst.html", "explore/sunburst-zoom.html", True),
    ("tpl_atlas.html", "index.html", True),
]

# The 8 hues the palette defines plus a neutral. BUILD_SPEC section 9 - his data has 11
# iconic groups, so the tail collapses to "other" rather than inventing colours.
PALETTE_CLASSES = ("Insecta", "Plantae", "Aves", "Fungi", "Arachnida",
                   "Reptilia", "Amphibia", "Mammalia")

# BUILD_SPEC section 7. Calibrated against the real pool, not guessed: across the real
# gaps the nearby counts span 1-43, so log1p spans ~4.8x against a weight range of ~4x -
# the two terms are already comparable. What the exponent actually moves is how
# insect-heavy the top of the list is. 0.25 makes it 48/50 insects and loses the "you have
# somehow never logged this common thing" signal; 1.0 drifts plant-heavy.
COUNT_EXP = 0.5


def load(name):
    return json.loads((DATA / name).read_text())


def dump(obj):
    """JSON for inlining inside <script type="application/json">.

    `</` is escaped because a scientific name or common name containing "</script" would
    otherwise close the tag and shred the page. \\/ is legal JSON, so parsers are unaffected
    and files with no such sequence come out byte-identical.
    """
    return json.dumps(obj, separators=(",", ":")).replace("</", "<\\/")


def palette_class(name):
    return name if name in PALETTE_CLASSES else "other"


# ── overview + seasonal aggregates ────────────────────────────────────────────
def accumulation(observations):
    """Cumulative distinct species over time - one point per NEW species, plus a final
    point at the last observation date so the curve's flat tail is honest."""
    dated = sorted((o for o in observations if o.get("sci") and o.get("d")),
                   key=lambda o: o["d"])
    seen, pts = set(), []
    for o in dated:
        if o["sci"] not in seen:
            seen.add(o["sci"])
            pts.append([o["d"], len(seen)])
    if dated and pts and dated[-1]["d"] != pts[-1][0]:
        pts.append([dated[-1]["d"], len(seen)])
    return pts


def phenology(observations):
    """Iconic group x month of year, pooled across seasons."""
    grid = collections.defaultdict(lambda: [0] * 12)
    for o in observations:
        m = o.get("m")
        if m:
            grid[o.get("cls") or "Unknown"][m - 1] += 1
    rows = sorted(grid.items(), key=lambda kv: -sum(kv[1]))
    return [{"c": c, "pc": palette_class(c), "m": months} for c, months in rows]


def class_totals(observations):
    obs = collections.Counter()
    spp = collections.defaultdict(set)
    for o in observations:
        c = o.get("cls") or "Unknown"
        obs[c] += 1
        if o.get("sci"):
            spp[c].add(o["sci"])
    return [{"c": c, "pc": palette_class(c), "o": n, "s": len(spp[c])}
            for c, n in obs.most_common()]


# ── gap checklist ─────────────────────────────────────────────────────────────
def gap_rows(pool, farm, interest):
    """Subtract his taxa from the nearby pool and attach the interest weight.

    MATCH ON ID **AND** NAME (BUILD_SPEC section 7). Ids alone produced false gaps two
    different ways, both structural: `Xanthotype` is a genus he has recorded but
    species_counts rolls up to the finest rank available, and `Hericium erinaceus` carries
    a different taxon id in his records than in the pool because iNat split the taxon after
    he logged it. The name key catches the second; folding farm_taxa into the life list
    catches the first.

    weight = interest.class[iconic] * family_multiplier[family]   (multiplier default 1.0)

    NOT `family_interest ?? class_interest`. Family scores are normalised among families
    and class scores among classes, so the scales never meet - under that rule all 133 of
    his insect families rank BELOW the baseline of a family he has never touched, burying
    exactly what the list exists to surface.
    """
    life = set(farm.get("life_taxa") or []) | set(farm.get("farm_taxa") or [])
    life_names = set(farm.get("life_names") or []) | set(farm.get("farm_names") or [])
    farm_taxa = set(farm.get("farm_taxa") or [])
    farm_names = set(farm.get("farm_names") or [])

    cls_interest = {k: v["interest"] for k, v in interest["class"].items()}
    mult = interest["family_multiplier"]
    # An iconic group he has never logged has no score of its own. Falling back to 0 would
    # delete it from the list entirely; the weakest class he *has* logged is the honest
    # floor - it sorts to the bottom but stays visible.
    fallback = min(cls_interest.values()) if cls_interest else 1.0

    rows = []
    for p in pool:
        on_farm = p["tid"] in farm_taxa or p["name"] in farm_names
        if on_farm:
            continue                     # never a gap in either mode - drop it here
        lifer = p["tid"] not in life and p["name"] not in life_names
        w = cls_interest.get(p["iconic"], fallback) * mult.get(p["family"], 1.0)
        rows.append({
            "t": p["tid"], "n": p["name"], "cm": p.get("common") or "",
            "ic": p["iconic"], "pc": palette_class(p["iconic"]),
            "f": p.get("family") or "", "or": p.get("order") or "",
            "ct": p["count"], "w": round(w, 1), "lg": 1 if lifer else 0,
        })
    rows.sort(key=lambda r: -(r["w"] * math.log1p(r["ct"]) ** COUNT_EXP))
    return rows


def genus_class(observations, taxonomy):
    """genus name -> the iconic group its records sit under, so the interest tab can
    colour genus bars. Derived from the ancestry chain, exactly the way build_interest.py
    groups genera - keying off the observation's own `g` field instead would disagree with
    the scores for any taxon iNat has since moved."""
    out = {}
    for o in observations:
        chain = (taxonomy.get(str(o.get("tid"))) or {}).get("chain") or {}
        g = chain.get("genus")
        if g:
            out.setdefault(g[0], o.get("cls") or "Unknown")
    return out


def build_payload():
    farm = load("farm_data.json")
    interest = load("interest.json")
    gap = load("gap_pool.json")
    tree = load("tree_data.json")
    taxonomy = load("taxonomy.json")
    observations = farm["observations"]
    rows = gap_rows(gap["pool"], farm, interest)
    interest = dict(interest, genus_class=genus_class(observations, taxonomy))

    return {
        "meta": dict(farm["meta"], taxa_in_tree=tree["tree"]["d"]),
        "overview": {
            "accum": accumulation(observations),
            "classes": class_totals(observations),
        },
        "phenology": phenology(observations),
        "interest": interest,
        "gap": {
            "meta": dict(gap["meta"], count_exp=COUNT_EXP,
                         pool_size=len(gap["pool"]),
                         farm_gaps=len(rows),
                         life_gaps=sum(r["lg"] for r in rows)),
            "rows": rows,
        },
    }


def print_gap_top(payload, n):
    g = payload["gap"]
    m = g["meta"]
    print(f"pool {m['pool_size']} nearby research-grade species within {m['radius_km']} km")
    print(f"not yet on the farm: {m['farm_gaps']}    never recorded anywhere (lifers): "
          f"{m['life_gaps']}")
    print(f"COUNT_EXP = {m['count_exp']}\n")
    print(f"{'#':>3}  {'species':32s} {'common name':30s} {'group':12s} "
          f"{'family':18s} {'near':>4} {'weight':>7} {'rank':>7}  lifer")
    print("-" * 130)
    for i, r in enumerate(g["rows"][:n], 1):
        rank = r["w"] * math.log1p(r["ct"]) ** m["count_exp"]
        print(f"{i:3d}  {r['n'][:32]:32s} {r['cm'][:30]:30s} {r['ic'][:12]:12s} "
              f"{r['f'][:18]:18s} {r['ct']:4d} {r['w']:7.1f} {rank:7.1f}  "
              f"{'yes' if r['lg'] else 'no'}")
    top = g["rows"][:50]
    insects = sum(1 for r in top if r["ic"] == "Insecta")
    beetles = sum(1 for r in top if r["or"] == "Coleoptera")
    print(f"\ntop 50 mix: {insects} insects, {beetles} beetles")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gap-top", type=int, metavar="N",
                    help="print the top N ranked gaps and exit (no pages written)")
    args = ap.parse_args()

    payload = build_payload()
    if args.gap_top:
        print_gap_top(payload, args.gap_top)
        return

    tree = (DATA / "tree_data.json").read_text()
    d3 = (ROOT / "scripts" / "vendor" / "d3.v7.min.js").read_text()
    atlas = dump(payload)

    for tpl_name, out_rel, needs_d3 in PAGES:
        src = (TPL / tpl_name).read_text()

        for token, value, required in (("/*__DATA__*/", tree, False),
                                       ("/*__TREE__*/", tree, False),
                                       ("/*__ATLAS__*/", atlas, False),
                                       ("/*__D3__*/", d3, needs_d3)):
            if token in src:
                src = src.replace(token, value)
            elif required:
                sys.exit(f"ERROR: {tpl_name} is missing the {token} placeholder")

        # the offline-safe convention, enforced rather than assumed.
        # CHECK BEFORE WRITING - a failed assertion must not leave a bad artifact on disk.
        assert "<script src=" not in src, f"{out_rel} references an external script"
        assert "localStorage" not in src and "sessionStorage" not in src, \
            f"{out_rel} uses web storage (breaks in some sandboxes)"
        assert "/*__" not in src, f"{out_rel} has an unfilled placeholder"

        out = ROOT / out_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(src)

        print(f"{out_rel:34s} {out.stat().st_size // 1024:5d} KB   d3={needs_d3}")

    g = payload["gap"]["meta"]
    print(f"\ngap checklist: {g['farm_gaps']} not on the farm, {g['life_gaps']} lifers, "
          f"COUNT_EXP={g['count_exp']}")
    print("all pages self-contained: no external scripts, no web storage")


if __name__ == "__main__":
    main()
