#!/usr/bin/env python3
"""Step 2 of 3 - fold farm observations + fetched ancestry into one hierarchy payload.

Reads  data/farm_data.json   (his 1,393 farm records)
       data/taxonomy.json    (ancestry from fetch_taxonomy.py)
Writes data/tree_data.json   (what all three wireframes render)

Shape: root -> iconic class -> order -> family -> genus -> species, skipping any rank
a taxon doesn't resolve to (a plant IDed only to family simply has no genus level).

Node schema - short keys because this ships inlined in every HTML file:

    n  name            o  observation count
    r  rank            s  distinct leaves beneath (the "species" count)
    c  iconic class    d  total descendant taxa
    id iNat taxon_id   k  children (absent on leaves)

Leaves additionally carry:  cm common name, im photo url, u sample observation url,
q research-grade count, mo months present, f/l first & last observation date.

PARTIAL IDs - the one non-obvious rule. 69 of his records are identified only to genus
or family. Left alone they get absorbed into an internal node and vanish from the leaf
count (881 leaves instead of 950), so the totals silently stop reconciling. Instead each
such group becomes an explicit child - "Scutellaria sp." or "Curculionidae
(undetermined)" - which keeps every parent equal to the sum of its children and the
grand total at 1,393. The verify block at the bottom asserts exactly that.
"""
import json, collections, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH_RANKS = ["order", "family", "genus"]

farm = json.loads((ROOT / "data" / "farm_data.json").read_text())
tax = json.loads((ROOT / "data" / "taxonomy.json").read_text())
OBS = farm["observations"]


def path_for(o):
    """[(rank, name, taxon_id), ...] from iconic class down to the observed taxon."""
    t = tax.get(str(o["tid"]))
    cls = o["cls"]
    out = [("class", cls, None)]
    if not t:
        out.append(("unresolved", o["sci"], o["tid"]))
        return out
    chain, seen = t["chain"], {cls}
    for r in PATH_RANKS:
        v = chain.get(r)
        if v and v[0] not in seen:
            out.append((r, v[0], v[1]))
            seen.add(v[0])
    if t["name"] not in seen:      # the taxon itself, if below the deepest rank used
        out.append((t["rank"], t["name"], o["tid"]))
    return out


def new_node(name, rank, cls, tid):
    return {"n": name, "r": rank, "c": cls, "id": tid, "o": 0, "k": {}, "_leaf_obs": []}


root = new_node(farm["meta"]["farm_name"], "root", "other", None)

for o in OBS:
    node = root
    node["o"] += 1
    for (rank, name, tid) in path_for(o):
        if name not in node["k"]:
            node["k"][name] = new_node(name, rank, o["cls"], tid)
        node = node["k"][name]
        node["o"] += 1
        if tid is not None and node["id"] is None:
            node["id"] = tid
    node["_leaf_obs"].append(o)


def finish(node):
    kids = list(node["k"].values())
    node.pop("k")

    if kids and node["_leaf_obs"]:
        # see PARTIAL IDs in the module docstring
        stub_name = node["n"] + " sp." if node["r"] == "genus" else node["n"] + " (undetermined)"
        stub = new_node(stub_name, "stub", node["c"], node["id"])
        stub["o"] = len(node["_leaf_obs"])
        stub["_leaf_obs"] = node["_leaf_obs"]
        stub.pop("k")
        stub["k"] = {}
        kids.append(stub)
        node["_leaf_obs"] = []

    if kids:
        for k in kids:
            finish(k)
        kids.sort(key=lambda d: (-d["o"], d["n"]))
        node["k"] = kids
        node["s"] = sum(k["s"] for k in kids)
        node["d"] = sum(k.get("d", 0) + 1 for k in kids)
        node.pop("_leaf_obs", None)
    else:
        obs = node.pop("_leaf_obs")
        node["s"], node["d"] = 1, 0
        node["cm"] = next((x["com"] for x in obs if x.get("com")), "")
        img = next((x["img"] for x in obs if x.get("img")), "")
        if img:
            node["im"] = img
        node["u"] = obs[0]["url"]
        node["q"] = sum(1 for x in obs if x["q"] == "research")
        node["mo"] = sorted({x["m"] for x in obs})
        ds = sorted(x["d"] for x in obs)
        node["f"], node["l"] = ds[0], ds[-1]
    return node


finish(root)

# ── verify: every parent must equal the sum of its children ────────────────────
def check(n):
    if not n.get("k"):
        return n["o"], 1
    o = s = 0
    for c in n["k"]:
        a, b = check(c)
        o += a
        s += b
    assert o == n["o"], f'{n["n"]}: children sum {o} != node {n["o"]}'
    assert s == n["s"], f'{n["n"]}: leaf sum {s} != node {n["s"]}'
    return o, s


total_obs, total_leaves = check(root)
assert total_obs == farm["meta"]["total_obs"], f'{total_obs} != {farm["meta"]["total_obs"]}'


def depths(n, d=0, acc=None):
    acc = acc if acc is not None else collections.Counter()
    acc[d] += 1
    for k in n.get("k", []):
        depths(k, d + 1, acc)
    return acc


out = ROOT / "data" / "tree_data.json"
out.write_text(json.dumps({"meta": farm["meta"], "tree": root}, separators=(",", ":")))

print(f"observations: {total_obs}   leaves: {total_leaves}   taxa in tree: {root['d']}")
print(f"depth histogram: {dict(sorted(depths(root).items()))}")
print(f"top level: {[(k['n'], k['o']) for k in root['k'][:6]]}")
print("totals reconcile at every level: OK")
print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")
