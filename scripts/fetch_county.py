#!/usr/bin/env python3
"""4b. County and statewide context for the farm's species  ->  data/county.json

Answers the question the rest of the atlas cannot: not "what is here" but "what does
having it here mean". A species Roy has photographed 40 times is ordinary; a species
whose only record in the entire county is his is a contribution to the state's fauna.

    GET /v1/observations/species_counts?place_id=<county>                 everyone, ever
    GET /v1/observations/species_counts?place_id=<county>&not_user_id=..  everyone but him
    GET /v1/observations/species_counts?place_id=<county>&user_login=..   his
    GET /v1/observations/species_counts?place_id=<state>                  statewide scarcity

    python3 scripts/fetch_county.py --check      validate endpoints + place resolution
    python3 scripts/fetch_county.py              full pull, ~62 requests, ~3 min
    python3 scripts/fetch_county.py --dry-run    pull, diff, write nothing

WHY not_user_id RATHER THAN COMPARING COUNTS. The obvious way to find "taxa only he has
recorded" is to pull the county's counts and his counts and keep the taxa where the two
numbers are equal. That is wrong, and it is wrong in a way that looks right: iNat
aggregates species_counts live, so two paged pulls taken seconds apart disagree slightly,
and taxa drift in and out of pages. Measured on the first attempt, count-equality claimed
651 sole-observer taxa where comparing the two id sets gave 623 - and comparing LINEAGES,
which is what this file actually does and what section 16 reports, gives 606. Three
methods, three answers, on the same data. `not_user_id` asks iNat to do the subtraction
server-side, and set membership is then exact.

    sole observer  ==  taxon is in his county list AND NOT in the county-without-him list

Output shape (data/county.json):

    meta   {county_place_id, county_name, state_place_id, state_name, generated,
            county_taxa, county_taxa_without_him, sole_taxa, county_obs, his_county_obs}
    taxa   [{tid, name, common, rank, r, c, s, sole}]   his county taxa, r/c/s = his /
                                                        county / statewide record counts
    pool   [{tid, name, common, rank, c}]               county taxa he has NOT recorded
"""
import argparse
import collections
import sys

import inat

# A drop this large means iNat changed something, not that the county lost its species.
SHRINK_GUARD = 0.90


def resolve_places():
    """Derive the county and state place ids from his own observations.

    Deliberately not hardcoded-and-trusted. The farm's postal address is "376 Lamar County
    Line Rd" in Griffin, and Griffin is in Spalding County - so the plausible-looking guess
    is the wrong one, and an earlier draft of the atlas shipped a "Spalding County, GA"
    option in the gap selector on exactly that reasoning. iNat already knows which side of
    the line each observation fell on; ask it.
    """
    payload = inat.get("/observations", {
        "user_login": inat.USER_LOGIN,
        "lat": inat.LAT, "lng": inat.LNG, "radius": inat.FARM_RADIUS_KM,
        "per_page": 30,
    })
    tally = collections.Counter()
    for o in payload.get("results") or []:
        for pid in o.get("place_ids") or []:
            tally[pid] += 1
    if not tally:
        sys.exit("ERROR: no observations returned - cannot resolve the county.")

    places = inat.get("/places/" + ",".join(str(p) for p, _ in tally.most_common(25)))
    def label(r, suffix=""):
        # iNat's `name` for a county is the bare "Lamar"; display_name is "Lamar County,
        # US, GA". Neither reads well on its own in a sentence, so build the short form.
        n = r.get("name") or r.get("display_name") or ""
        return f"{n} {suffix}".strip() if suffix and not n.endswith(suffix) else n

    county = state = None
    for r in places.get("results") or []:
        if r.get("admin_level") == 20 and county is None:
            county = (r["id"], label(r, "County"))
        if r.get("admin_level") == 10 and state is None:
            state = (r["id"], label(r))
    if not county or not state:
        sys.exit(f"ERROR: could not resolve county/state from place_ids {list(tally)[:10]}")

    # Fail loudly rather than describe the wrong county.
    if county[0] != inat.COUNTY_PLACE_ID:
        sys.exit(f"ERROR: his observations fall in place {county[0]} ({county[1]}), but "
                 f"inat.COUNTY_PLACE_ID is {inat.COUNTY_PLACE_ID} ({inat.COUNTY_NAME}). "
                 f"Fix the constant - do not fix this check.")
    if state[0] != inat.STATE_PLACE_ID:
        sys.exit(f"ERROR: his observations fall in state {state[0]} ({state[1]}), but "
                 f"inat.STATE_PLACE_ID is {inat.STATE_PLACE_ID} ({inat.STATE_NAME}).")
    print(f"places resolved: {county[1]} ({county[0]}) in {state[1]} ({state[0]})")
    return county, state


def sole_observers(his, without_him):
    """Taxa in the county whose only records are his - compared by LINEAGE, not by id.

    The naive `set(his) - set(without_him)` is wrong here, and its wrongness is provable
    from the totals rather than a matter of taste. On the 2026-08-11 data it returns 667,
    while the county holds 1,894 taxa of which 1,020 are his and 1,271 are other people's:
    1,020 + 1,271 - 667 implies a union of 1,938 taxa inside an 1,894-taxon county. Two
    subsets cannot union to more than the whole. The excess is rank rollup - species_counts
    reports the finest rank available *within each query*, so his genus-level `Xanthotype`
    and someone else's `Xanthotype urticaria` arrive as unrelated ids for one lineage. This
    is the same failure BUILD_SPEC section 7 documents for the gap checklist.

    A taxon T of his is sole-observed when no other observer's taxon U touches its lineage:

      U == T                    someone else recorded the same taxon
      T is an ancestor of U     he has the genus, someone else has a species in it
      U is an ancestor of T     he has the species, someone else has a genus-only record

    The third case is the conservative one. An unidentified genus-level record by another
    observer may or may not be his species, so it is counted as NOT sole. This understates
    the headline rather than overstating it, which is the right direction for a claim about
    the county's fauna.
    """
    covered = set()                      # every id another observer's records can speak to
    for tid, rec in without_him.items():
        covered.add(tid)
        covered.update(rec["ancestors"])

    others = set(without_him)
    sole = set()
    for tid, rec in his.items():
        if tid in covered:
            continue
        if others & set(rec["ancestors"]):
            continue
        sole.add(tid)
    return sole


def obscured_taxa(county):
    """Taxa iNaturalist obscures the location of, anywhere in this county.

    These must never carry the sole-observer flag. iNat hides these coordinates precisely
    because the species are collection targets, and "the only record in the county" is a
    scarcity signal published beside a farm whose address is in the page header - the exact
    inference the obscuring exists to prevent. *Platanthera ciliaris*, the yellow fringed
    orchid, is the live case: iNat obscures it, and Roy is its only observer in Lamar.

    It stays off the tab today only by accident - obscured coordinates are fuzzed, so those
    records fall outside the 2 km farm query and never reach `farm_data.json` (which also
    means the farm species list silently under-reports them; BUILD_SPEC section 11). An
    accident is not a safeguard. This makes it deliberate.

    Queried across ALL observers, not just his: the property of being obscured belongs to
    the taxon, not to who photographed it.

    TWO FILTERS, BOTH NECESSARY, both learned by getting it wrong. The obscured-observation
    query returns whatever rank each observation was identified to, which included bare
    `Animalia`, `Poales` and `Homo sapiens` - observations a user obscured by hand, not
    species iNat protects. Suppressing by lineage against that set removed 573 of 606 sole
    taxa, because `Animalia` is an ancestor of nearly every insect on the farm.

      1. Rank must be species or finer. A kingdom is not a collection target.
      2. Some entry in the taxon's `conservation_statuses` must set
         `geoprivacy: "obscured"`, confirmed by a batched /taxa lookup. This separates
         "iNat protects this species" from "this observer chose to hide their garden".

    CHECK THE PLURAL FIELD. `taxon.conservation_status` (singular) and `taxon.threatened`
    are both null for *Platanthera ciliaris* - the yellow fringed orchid this guard exists
    for - while `conservation_statuses` (plural) carries 30 entries, the global one among
    them setting geoprivacy to obscured. Testing the singular field silently let the one
    species that motivated the whole guard straight through.
    """
    SPECIES_OR_FINER = ("species", "subspecies", "variety", "form", "hybrid")
    candidates, page = {}, 1
    while page <= 5:
        payload = inat.get("/observations", {
            "place_id": county[0], "taxon_geoprivacy": "obscured",
            "per_page": 200, "page": page,
        })
        results = payload.get("results") or []
        if not results:
            break
        for o in results:
            t = o.get("taxon") or {}
            if t.get("id") and t.get("rank") in SPECIES_OR_FINER:
                candidates[t["id"]] = t.get("name") or ""
        if page * 200 >= (payload.get("total_results") or 0):
            break
        page += 1
    if not candidates:
        return {}

    confirmed = {}
    ids = sorted(candidates)
    for i in range(0, len(ids), inat.BATCH):
        chunk = ids[i:i + inat.BATCH]
        payload = inat.get("/taxa/" + ",".join(str(t) for t in chunk))
        for t in payload.get("results") or []:
            statuses = t.get("conservation_statuses") or []
            single = t.get("conservation_status") or {}
            hidden = (any(s.get("geoprivacy") == "obscured" for s in statuses)
                      or single.get("geoprivacy") == "obscured")
            if hidden:
                confirmed[t["id"]] = t.get("name") or candidates.get(t["id"], "")
    return confirmed


def rollup(counts):
    """taxon id -> records of that taxon INCLUDING everything below it.

    species_counts reports each observation at the finest rank available, so a bare genus
    id is usually absent from a large pull even when hundreds of records sit inside it.
    Read literally, the Georgia pull says *Carya* (hickories) has 0 records statewide,
    because every Georgia hickory is filed under a species. Attributing each leaf's count
    to its ancestors as well makes the number mean "records of this taxon or anything
    within it", which is the only reading under which a genus-level row is not nonsense.

    Each observation is still counted once per ancestor level, never twice at the same
    level, so a species' own figure is unchanged by this.
    """
    total = collections.Counter()
    for tid, rec in counts.items():
        n = rec["count"]
        # iNat's ancestor_ids ENDS WITH THE TAXON'S OWN ID. Adding the taxon separately
        # and then walking ancestor_ids therefore counts every record twice - which is
        # exactly what shipped in the first draft, turning 1 record into 2 everywhere and
        # making four species look like Georgia endemics. The set union makes the
        # operation idempotent regardless of whether iNat keeps that convention.
        for a in set(rec["ancestors"]) | {tid}:
            total[a] += n
    return total


def observation_totals(county):
    """The county's real record counts, for the headline share.

    Two requests, deliberately not derived from species_counts. `per_page=0` returns only
    total_results, so this is as cheap as an API call gets.

    NO GRADE FILTER, deliberately. `verifiable=true` would drop casual records from the
    denominator (5,330 rather than 5,475) while the species_counts pulls this file also
    makes use the endpoint's default, which includes them. Mixing the two filters across
    one tab is worse than either choice on its own: the share would be computed over a
    different population than the taxon counts beside it. Every figure here is therefore
    "all grades", and none of his own records are excluded either way.
    """
    both = {}
    for key, extra in (("county", {}), ("his", {"user_login": inat.USER_LOGIN})):
        payload = inat.get("/observations", dict(extra, place_id=county[0], per_page=0))
        both[key] = payload.get("total_results") or 0
    return both


def build(county_all, without_him, his, statewide, county, state, asof, obs_totals,
          obscured):
    sole = sole_observers(his, without_him)

    # Strip the flag from anything iNat obscures, and from anything beneath it - an
    # obscured species covers its own subspecies. Done after sole_observers() rather than
    # inside it so the two concerns stay separable: that function answers "is he the only
    # observer", this answers "may we say so out loud".
    suppressed = {t for t in sole
                  if t in obscured or (set(his[t]["ancestors"]) & set(obscured))}

    # Suppression is meant to remove a handful of protected species, not to rewrite the
    # headline. The first version of obscured_taxa() included bare `Animalia` and took out
    # 573 of 606; a withholding rate this high always means the obscured set is too broad,
    # never that the county is full of orchids. Fail rather than publish a gutted number.
    if len(sole) and len(suppressed) > max(25, 0.05 * len(sole)):
        sys.exit(f"ERROR: {len(suppressed)} of {len(sole)} sole taxa would be withheld as "
                 f"obscured. That is far too many - obscured_taxa() has almost certainly "
                 f"picked up a coarse-rank taxon whose lineage covers half the farm. "
                 f"Obscured set was: {sorted(obscured.values())[:12]}")
    sole -= suppressed
    county_roll = rollup(county_all)
    state_roll = rollup(statewide)
    his_roll = rollup(his)

    taxa = []
    for tid, rec in his.items():
        r = his_roll.get(tid, rec["count"])
        # Floors, not just conveniences. His own records are a subset of the county's and
        # the county's of the state's, so a smaller number upstream can only be paging
        # drift or a lineage the rollup could not reach - never a real fact about the
        # world. Taking the max keeps a row from claiming he has more records of something
        # than the county contains.
        c = max(r, county_roll.get(tid, 0))
        s = max(c, state_roll.get(tid, 0))
        taxa.append({
            "tid": tid,
            "name": rec["name"],
            "common": rec["common"],
            "rank": rec["rank"],
            "iconic": rec["iconic"],
            "r": r, "c": c, "s": s,
            "sole": 1 if tid in sole else 0,
        })
    taxa.sort(key=lambda t: (-t["sole"], t["s"], t["name"]))

    # The county gap pool: what others have recorded here and he has not. Filtered by
    # LINEAGE for the same reason the sole determination is - pure id subtraction leaves in
    # genera he already holds at species rank (Diatraea, Scopula, Acronicta, Apantesis and
    # ~20 more), which is precisely the bug this file exists to avoid. Not user-facing yet;
    # the gap tab's county scope stays disabled until the pool carries family and order
    # names for section 7's weighting. Filtering now stops a wrong number being quoted as
    # fact in the meantime.
    his_covered = set(his)
    for rec in his.values():
        his_covered.update(rec["ancestors"])
    pool = [{"tid": tid, "name": r["name"], "common": r["common"],
             "rank": r["rank"], "iconic": r["iconic"], "c": r["count"]}
            for tid, r in without_him.items()
            if tid not in his_covered and not (set(r["ancestors"]) & set(his))]
    pool.sort(key=lambda p: -p["c"])

    return {
        "meta": {
            "county_place_id": county[0], "county_name": county[1],
            "state_place_id": state[0], "state_name": state[1],
            "generated": asof,
            "county_taxa": len(county_all),
            "county_taxa_without_him": len(without_him),
            "sole_taxa": len(sole),
            "sole_suppressed_obscured": len(suppressed),
            # What id-only matching would have claimed. Kept so the page can show the
            # correction rather than assert a bare number, and so a regression in
            # sole_observers() shows up as the two converging.
            "sole_taxa_id_only": len(set(his) - set(without_him)),
            "state_taxa": len(statewide),
            # Summing species_counts gives the observations it could attribute to a leaf
            # taxon, NOT the county's record count - every coarse identification is missing
            # from both halves. The ratio of the two sums read 38% where the real share is
            # ~35%, so the headline share comes from /observations totals instead.
            "county_obs": obs_totals["county"],
            "his_county_obs": obs_totals["his"],
            "county_obs_leaf": sum(r["count"] for r in county_all.values()),
            "his_county_obs_leaf": sum(r["count"] for r in his.values()),
        },
        "taxa": taxa,
        "pool": pool,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="validate endpoints and exit")
    ap.add_argument("--dry-run", action="store_true", help="pull and diff, write nothing")
    ap.add_argument("--asof", default=None, help="date stamp for the output (YYYY-MM-DD)")
    args = ap.parse_args()

    if args.check:
        county, state = resolve_places()
        inat.check("/observations/species_counts", {"place_id": county[0]})
        inat.check("/observations/species_counts",
                   {"place_id": county[0], "not_user_id": inat.USER_ID})
        inat.check("/observations/species_counts",
                   {"place_id": county[0], "user_login": inat.USER_LOGIN})
        print(f"\n{inat.requests_made()} requests")
        return

    asof = args.asof or __import__("datetime").date.today().isoformat()
    county, state = resolve_places()

    print(f"pulling species counts (this is ~55 requests, mostly {state[1]})")
    county_all = inat.species_counts({"place_id": county[0]},
                                     label=f"{county[1]}, all observers")
    without_him = inat.species_counts({"place_id": county[0],
                                       "not_user_id": inat.USER_ID},
                                      label=f"{county[1]}, without him")
    his = inat.species_counts({"place_id": county[0],
                               "user_login": inat.USER_LOGIN},
                              label=f"{county[1]}, his records")
    statewide = inat.species_counts({"place_id": state[0]},
                                    label=f"{state[1]}, all observers")
    obs_totals = observation_totals(county)
    print(f"  {'observation totals':34s} {obs_totals['his']:>6} of {obs_totals['county']}")
    obscured = obscured_taxa(county)
    print(f"  {'obscured taxa (never flagged sole)':34s} {len(obscured):>6}"
          f"  {', '.join(sorted(obscured.values())[:3])}...")

    # not_user_id must actually filter. If iNat ever ignores it the subtraction silently
    # becomes "every taxon he has is shared", and the tab reports zero sole records with
    # no error anywhere. Verified real on 2026-08-11: 1,894 -> 1,271.
    if len(without_him) >= len(county_all):
        sys.exit(f"ERROR: not_user_id had no effect ({len(without_him)} >= "
                 f"{len(county_all)}). Refusing to write - the sole-observer count would "
                 f"be silently wrong.")
    if not his:
        sys.exit("ERROR: he has no records in the county. Check USER_LOGIN.")

    fresh = build(county_all, without_him, his, statewide, county, state, asof, obs_totals,
                  obscured)
    m = fresh["meta"]

    # THE INVARIANT THAT CAUGHT THE ID-ONLY BUG. His taxa and other people's taxa are both
    # subsets of the county's, so their union cannot exceed it. Overlap is |his| - |sole|,
    # giving union = |his| + |others| - (|his| - |sole|). Id-only matching produced a union
    # of 1,938 inside an 1,894-taxon county; the lineage-aware count gives 1,877. Any future
    # change that reintroduces id-only comparison trips this rather than shipping a wrong
    # headline number.
    union = len(his) + len(without_him) - (len(his) - m["sole_taxa"])
    if union > m["county_taxa"]:
        sys.exit(f"ERROR: {len(his)} of his taxa + {len(without_him)} others' imply a union "
                 f"of {union} taxa, but the county holds only {m['county_taxa']}. The "
                 f"sole-observer count ({m['sole_taxa']}) is too high - almost certainly "
                 f"taxa are being compared by id instead of by lineage.")

    old = inat.load("county.json") or {}
    if old.get("meta"):
        o = old["meta"]
        keep = m["county_taxa"] >= o["county_taxa"] * SHRINK_GUARD
        print(f"\ncounty taxa: {o['county_taxa']} -> {m['county_taxa']}   "
              f"sole: {o['sole_taxa']} -> {m['sole_taxa']}")
        if not keep:
            sys.exit(f"ERROR: county taxa dropped more than "
                     f"{(1 - SHRINK_GUARD) * 100:.0f}%. Refusing to write.")

    print(f"\n{m['county_name']}: {m['county_taxa']} taxa ever recorded, "
          f"{m['county_obs']} observations")
    print(f"  his share:      {len(fresh['taxa'])} taxa "
          f"({len(fresh['taxa']) / m['county_taxa'] * 100:.0f}%), "
          f"{m['his_county_obs']} observations "
          f"({m['his_county_obs'] / m['county_obs'] * 100:.0f}%)")
    print(f"  sole observer:  {m['sole_taxa']} taxa "
          f"({m['sole_taxa'] / m['county_taxa'] * 100:.0f}% of the county list)")
    if m["sole_suppressed_obscured"]:
        print(f"  withheld:       {m['sole_suppressed_obscured']} obscured taxa not "
              f"flagged sole (collection targets - see fetch_county.obscured_taxa)")
    print(f"  {m['state_name']}: {m['state_taxa']} taxa statewide")
    print(f"  county gap pool: {len(fresh['pool'])} taxa others have and he has not")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return
    inat.save("county.json", fresh)
    print(f"{inat.requests_made()} requests")


if __name__ == "__main__":
    main()
