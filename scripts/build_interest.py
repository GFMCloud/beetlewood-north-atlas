#!/usr/bin/env python3
"""Step 2 of 5 - compute how interested Roy is in each group, at every rank.

Offline. Reads data/farm_data.json + data/taxonomy.json, writes data/interest.json.

ONE FORMULA, THREE GROUPINGS. Earlier snapshots shipped two different things both
called "interest": a 4-factor 0-100 score at class level and a bare
log1p(obs)+log1p(species) at genus level on a 1.4-5.0 scale. They were not
comparable and only one of them was documented. This script replaces both.

    effort      = observation count
    depth       = distinct species
    recency     = fraction of observations in the last 365 days (from --asof)
    persistence = distinct months of the year present

    normalise each 0..1 across peers in the same grouping (effort and depth on
    log1p, because his Insecta count dwarfs everything), then

    interest = 100 * (0.35*effort + 0.30*depth + 0.20*recency + 0.15*persistence)

Peers means: classes are ranked against classes, families against families, genera
against genera. A score is only meaningful within its own grouping.

RECENCY IS ANCHORED TO --asof, DEFAULT TODAY. Never to a date baked into the data.
A frozen anchor silently stops decaying the moment the cron starts running.

GAP WEIGHTING. The gap checklist needs one weight per candidate species. Family
interest cannot be used directly for that: family scores are normalised among
families and class scores among classes, so the two scales do not meet. Ranking on
`family_interest ?? class_interest` puts every family Roy has ever worked BELOW the
baseline of a family he has never touched - it demotes his own specialities. So the
family term is emitted as a MULTIPLIER on the class weight instead:

    multiplier(family) = MULT_SPAN_LO + percentile of that family within its class
    weight(species)    = interest.class[iconic] * multiplier(family, default 1.0)

A family he has never logged has no multiplier and sits at the class baseline (1.0).
His strongest family in a class approaches MULT_SPAN_LO + 1. Tune the span here.
"""
import argparse
import collections
import datetime
import math

import inat

WEIGHTS = {"effort": 0.35, "depth": 0.30, "recency": 0.20, "persistence": 0.15}
RECENT_DAYS = 365
# Weakest logged family multiplier. MUST NOT drop below 1.0: an unlogged family sits at
# the class baseline (1.0), so anything lower would mean logging a family once PENALISES
# it relative to never having touched it. 112 of his 248 families have a single record -
# Buprestidae among them - and a sub-1.0 floor buries exactly the specialist families the
# gap list exists to surface.
MULT_SPAN_LO = 1.0


def normalise(values, log=False):
    vals = {k: (math.log1p(v) if log else v) for k, v in values.items()}
    if not vals:
        return {}
    lo, hi = min(vals.values()), max(vals.values())
    if hi == lo:
        return {k: 0.0 for k in vals}
    return {k: (v - lo) / (hi - lo) for k, v in vals.items()}


def score(groups, asof):
    """groups: {key: [observation, ...]} -> {key: {obs, species, recent_frac, months, interest}}"""
    if not groups:
        return {}
    cutoff = asof - datetime.timedelta(days=RECENT_DAYS)
    effort = {g: len(v) for g, v in groups.items()}
    depth = {g: len({o["sci"] for o in v}) for g, v in groups.items()}
    recency = {g: sum(1 for o in v if datetime.date.fromisoformat(o["d"]) >= cutoff) / len(v)
               for g, v in groups.items()}
    persistence = {g: len({o["m"] for o in v}) for g, v in groups.items()}

    n_effort = normalise(effort, log=True)
    n_depth = normalise(depth, log=True)
    n_recency = normalise(recency)
    n_persistence = normalise(persistence)

    out = {}
    for g in groups:
        interest = 100 * (
            WEIGHTS["effort"] * n_effort[g]
            + WEIGHTS["depth"] * n_depth[g]
            + WEIGHTS["recency"] * n_recency[g]
            + WEIGHTS["persistence"] * n_persistence[g]
        )
        out[g] = {
            "obs": effort[g],
            "species": depth[g],
            "recent_frac": round(recency[g], 3),
            "months": persistence[g],
            "years": len({o["y"] for o in groups[g]}),
            "interest": round(interest, 1),
        }
    return out


def group_by(observations, taxonomy, rank):
    """Group observations by iconic class, or by a taxonomic rank from the ancestry."""
    groups = collections.defaultdict(list)
    unresolved = 0
    for o in observations:
        if rank == "class":
            groups[o["cls"]].append(o)
            continue
        chain = (taxonomy.get(str(o["tid"])) or {}).get("chain") or {}
        value = chain.get(rank)
        if value:
            groups[value[0]].append(o)
        else:
            unresolved += 1
    return dict(groups), unresolved


def family_multipliers(family_scores, family_class):
    """Percentile of each family within its own class, mapped onto the weight span."""
    by_class = collections.defaultdict(list)
    for fam, cls in family_class.items():
        if fam in family_scores:
            by_class[cls].append(fam)

    mult = {}
    for cls, fams in by_class.items():
        ranked = sorted(fams, key=lambda f: family_scores[f]["interest"])
        n = len(ranked)
        for i, fam in enumerate(ranked):
            pct = 0.5 if n == 1 else i / (n - 1)
            mult[fam] = round(MULT_SPAN_LO + pct, 3)
    return mult


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--asof", help="YYYY-MM-DD anchor for the recency window (default today)")
    args = ap.parse_args()
    asof = datetime.date.fromisoformat(args.asof) if args.asof else datetime.date.today()

    farm = inat.load("farm_data.json")
    taxonomy = inat.load("taxonomy.json", {})
    if not farm:
        raise SystemExit("data/farm_data.json missing - run fetch_observations.py first")
    observations = farm["observations"]

    by_class, _ = group_by(observations, taxonomy, "class")
    by_family, no_family = group_by(observations, taxonomy, "family")
    by_genus, no_genus = group_by(observations, taxonomy, "genus")

    class_scores = score(by_class, asof)
    family_scores = score(by_family, asof)
    genus_scores = score(by_genus, asof)

    # which class does each family sit under (by where his records put it)
    family_class = {}
    for fam, obs in by_family.items():
        family_class[fam] = collections.Counter(o["cls"] for o in obs).most_common(1)[0][0]

    payload = {
        "asof": asof.isoformat(),
        "recent_days": RECENT_DAYS,
        "weights": WEIGHTS,
        "mult_span_lo": MULT_SPAN_LO,
        "class": class_scores,
        "family": family_scores,
        "genus": genus_scores,
        "family_class": family_class,
        "family_multiplier": family_multipliers(family_scores, family_class),
        "coverage": {
            "observations": len(observations),
            "without_family": no_family,
            "without_genus": no_genus,
        },
    }
    inat.save("interest.json", payload)

    print(f"asof {asof}   classes {len(class_scores)}   families {len(family_scores)}   "
          f"genera {len(genus_scores)}")
    print(f"observations with no family in the ancestry: {no_family} "
          f"(they fall back to the class weight)")
    top = sorted(class_scores.items(), key=lambda kv: -kv[1]["interest"])[:4]
    print("top classes:", [(k, v["interest"]) for k, v in top])
    tf = sorted(family_scores.items(), key=lambda kv: -kv[1]["interest"])[:4]
    print("top families:", [(k, v["interest"]) for k, v in tf])


if __name__ == "__main__":
    main()
