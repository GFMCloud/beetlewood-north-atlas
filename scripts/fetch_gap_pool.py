#!/usr/bin/env python3
"""Step 4 of 5 - bake the pool of species other people record near the farm.

    GET /v1/observations/species_counts?lat=..&lng=..&radius=15&quality_grade=research

Every research-grade species recorded in range, with how often. Subtracting Roy's
own taxa from this pool is the Gap Checklist.

Each result carries taxon.ancestor_ids but not ancestor *names*, so order and family
names are resolved by (i) reusing anything already in data/taxonomy.json, and
(ii) a batched /taxa lookup for the rest, cached in data/taxa_cache.json so re-runs
only fetch genuinely new ancestors.

Usage:
    python3 scripts/fetch_gap_pool.py --check      # 1 request, prints the response shape
    python3 scripts/fetch_gap_pool.py              # full pull
    python3 scripts/fetch_gap_pool.py --max-pages 2   # bounded trial run

Writes data/gap_pool.json:
    meta  scope + generated date + pool size
    pool  [{tid, name, common, iconic, family, order, count}, ...]

NOTE: the pool is the raw nearby-species list. Subtraction against his life list and
the interest weighting both happen at render time, so the same baked pool serves the
"anywhere" and "on-farm" toggles without a refetch.
"""
import argparse
import datetime

import inat

RANKS_WANTED = ("order", "family")


def fetch_pool(max_pages=None):
    pool, page = [], 1
    while True:
        payload = inat.get("/observations/species_counts", {
            "lat": inat.LAT, "lng": inat.LNG, "radius": inat.NEARBY_RADIUS_KM,
            "quality_grade": "research",
            "per_page": inat.COUNTS_PER_PAGE, "page": page,
        })
        results = payload.get("results") or []
        total = payload.get("total_results")
        print(f"  page {page}: +{len(results)} of {total}", flush=True)
        for r in results:
            taxon = r.get("taxon") or {}
            if not taxon.get("id"):
                continue
            pool.append({
                "tid": taxon["id"],
                "name": taxon.get("name") or "",
                "common": taxon.get("preferred_common_name") or "",
                "iconic": taxon.get("iconic_taxon_name") or "Unknown",
                "ancestor_ids": taxon.get("ancestor_ids") or [],
                "count": r.get("count", 0),
            })
        if len(results) < inat.COUNTS_PER_PAGE:
            break
        page += 1
        if max_pages and page > max_pages:
            print(f"  stopping early at --max-pages {max_pages} "
                  f"(pool is NOT complete)")
            break
    return pool


def resolve_ancestors(pool):
    """Fill order/family names for every pool entry, fetching only unknown ids."""
    taxonomy = inat.load("taxonomy.json", {})
    cache = inat.load("taxa_cache.json", {})

    # seed the cache from ancestry already resolved for the farm's own taxa
    for entry in taxonomy.values():
        for rank, value in (entry.get("chain") or {}).items():
            if rank in RANKS_WANTED and value:
                cache.setdefault(str(value[1]), {"rank": rank, "name": value[0]})

    wanted = set()
    for p in pool:
        for aid in p["ancestor_ids"]:
            if str(aid) not in cache:
                wanted.add(aid)
    wanted = sorted(wanted)
    print(f"ancestor ids: {len(cache)} cached, {len(wanted)} to fetch")

    for i in range(0, len(wanted), inat.BATCH):
        batch = wanted[i:i + inat.BATCH]
        payload = inat.get("/taxa/" + ",".join(str(b) for b in batch))
        for t in payload.get("results", []):
            cache[str(t["id"])] = {"rank": t.get("rank"), "name": t.get("name")}
        for b in batch:                       # remember misses so we stop re-asking
            cache.setdefault(str(b), {"rank": None, "name": None})
        print(f"  taxa batch {i // inat.BATCH + 1}/"
              f"{(len(wanted) + inat.BATCH - 1) // inat.BATCH}", flush=True)

    if wanted:
        inat.save("taxa_cache.json", cache)

    unresolved = 0
    for p in pool:
        names = {}
        for aid in p["ancestor_ids"]:
            entry = cache.get(str(aid)) or {}
            if entry.get("rank") in RANKS_WANTED and entry.get("name"):
                names[entry["rank"]] = entry["name"]
        p["order"] = names.get("order", "")
        p["family"] = names.get("family", "")
        if not p["family"]:
            unresolved += 1
        p.pop("ancestor_ids")
    return unresolved


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--max-pages", type=int)
    args = ap.parse_args()

    if args.check:
        inat.check("/observations/species_counts", {
            "lat": inat.LAT, "lng": inat.LNG, "radius": inat.NEARBY_RADIUS_KM,
            "quality_grade": "research"})
        return

    print(f"nearby research-grade species within {inat.NEARBY_RADIUS_KM} km of "
          f"{inat.LAT},{inat.LNG}")
    pool = fetch_pool(args.max_pages)
    unresolved = resolve_ancestors(pool)

    farm = inat.load("farm_data.json") or {}
    life = set(farm.get("life_taxa") or [])
    farm_taxa = set(farm.get("farm_taxa") or [])
    not_lifers = sum(1 for p in pool if p["tid"] not in life)
    not_on_farm = sum(1 for p in pool if p["tid"] not in farm_taxa)

    inat.save("gap_pool.json", {
        "meta": {
            "lat": inat.LAT, "lng": inat.LNG, "radius_km": inat.NEARBY_RADIUS_KM,
            "quality_grade": "research",
            "generated": datetime.date.today().isoformat(),
            "pool_size": len(pool),
            "complete": args.max_pages is None,
        },
        "pool": sorted(pool, key=lambda p: -p["count"]),
    })

    print(f"\npool: {len(pool)} species   without a resolved family: {unresolved}")
    print(f"not on his life list (true lifers): {not_lifers}")
    print(f"not yet recorded on the farm:       {not_on_farm}")
    if not_lifers < 50:
        print("WARNING: very few gaps - check the scope before building a tab around this")


if __name__ == "__main__":
    main()
