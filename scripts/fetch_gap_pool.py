#!/usr/bin/env python3
"""Step 4 of 5 - bake the pool of species other people record near the farm.

    GET /v1/observations/species_counts?lat=..&lng=..&radius=15&quality_grade=research

Every research-grade species recorded in range, with how often. Subtracting Roy's
own taxa from this pool is the Gap Checklist.

species_counts gives ids but not ancestor names, so a second pass fetches each pool
species from /taxa (30 per call) and reads the `ancestors` array it already carries.
Results are cached in data/taxa_cache.json and checkpointed every 10 batches, so a
dropped connection costs one batch and a re-run resumes where it stopped.

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


def resolve_ranks(pool, checkpoint_every=10):
    """Fill order/family names for every pool entry.

    Fetches the POOL SPECIES themselves, 30 at a time, and reads the `ancestors` array
    each /taxa record already carries - the same trick fetch_taxonomy.py uses. The earlier
    approach collected every distinct ancestor id across the pool and looked those up
    instead, which meant 5,348 ids / 179 requests to learn 2 ranks per species. Going
    through the species directly is ~60 requests, because one record answers both ranks at
    once and anything already in taxonomy.json is free.

    Progress is checkpointed to taxa_cache.json every `checkpoint_every` batches, so a
    dropped connection costs one batch rather than the whole run. Re-running resumes.
    """
    taxonomy = inat.load("taxonomy.json", {})
    cache = inat.load("taxa_cache.json", {})

    # anything already resolved for the farm's own taxa is free
    seeded = 0
    for tid, entry in taxonomy.items():
        if tid in cache:
            continue
        chain = entry.get("chain") or {}
        cache[tid] = {r: (chain.get(r) or [""])[0] for r in RANKS_WANTED}
        seeded += 1

    todo = [p["tid"] for p in pool if str(p["tid"]) not in cache]
    print(f"rank resolution: {len(cache)} cached ({seeded} reused from taxonomy.json), "
          f"{len(todo)} to fetch in {(len(todo) + inat.BATCH - 1) // inat.BATCH} batches")

    for i in range(0, len(todo), inat.BATCH):
        batch = todo[i:i + inat.BATCH]
        payload = inat.get("/taxa/" + ",".join(str(b) for b in batch))
        for t in payload.get("results", []):
            names = {}
            for a in t.get("ancestors", []):
                if a.get("rank") in RANKS_WANTED:
                    names[a["rank"]] = a.get("name") or ""
            cache[str(t["id"])] = {r: names.get(r, "") for r in RANKS_WANTED}
        for b in batch:                       # remember misses so we stop re-asking
            cache.setdefault(str(b), {r: "" for r in RANKS_WANTED})

        n = i // inat.BATCH + 1
        total = (len(todo) + inat.BATCH - 1) // inat.BATCH
        if n % checkpoint_every == 0 or i + inat.BATCH >= len(todo):
            inat.save("taxa_cache.json", cache, quiet=True)
            print(f"  batch {n}/{total} (checkpointed)", flush=True)
        else:
            print(f"  batch {n}/{total}", flush=True)

    if todo or seeded:
        inat.save("taxa_cache.json", cache, quiet=True)

    unresolved = 0
    for p in pool:
        entry = cache.get(str(p["tid"])) or {}
        p["order"] = entry.get("order", "")
        p["family"] = entry.get("family", "")
        if not p["family"]:
            unresolved += 1
        p.pop("ancestor_ids", None)
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
    unresolved = resolve_ranks(pool)

    farm = inat.load("farm_data.json") or {}
    life = set(farm.get("life_taxa") or [])
    life_names = set(farm.get("life_names") or [])
    farm_taxa = set(farm.get("farm_taxa") or [])
    farm_names = set(farm.get("farm_names") or [])

    def is_gap(p, ids, names):
        # id OR name - see fetch_observations.fetch_life_taxa() for why both are needed
        return p["tid"] not in ids and p["name"] not in names

    not_lifers = sum(1 for p in pool if is_gap(p, life, life_names))
    not_on_farm = sum(1 for p in pool if is_gap(p, farm_taxa, farm_names))

    inat.save("gap_pool.json", {
        "meta": {
            "lat": inat.LAT, "lng": inat.LNG, "radius_km": inat.NEARBY_RADIUS_KM,
            "quality_grade": "research",
            "generated": datetime.date.today().isoformat(),
            "pool_size": len(pool),
            "complete": args.max_pages is None,
        },
        # Tie-break on name, not just count. Sorting on count alone leaves species with
        # equal counts in whatever order the API happened to return them, and the median
        # count in this pool is 1 - so most of the file is ties. The result churned on
        # every run even when not a single record had changed, which meant the weekly cron
        # committed noise every week and the "nothing changed" guard could never fire.
        "pool": sorted(pool, key=lambda p: (-p["count"], p["name"])),
    })

    print(f"\npool: {len(pool)} species   without a resolved family: {unresolved}")
    print(f"not on his life list (true lifers): {not_lifers}")
    print(f"not yet recorded on the farm:       {not_on_farm}")
    if not_lifers < 50:
        print("WARNING: very few gaps - check the scope before building a tab around this")
    print(f"api requests this run: {inat.requests_made()}")


if __name__ == "__main__":
    main()
