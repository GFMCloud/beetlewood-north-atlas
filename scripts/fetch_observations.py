#!/usr/bin/env python3
"""Step 0 of 5 - rebuild data/farm_data.json from the live iNaturalist API.

This is the step that makes the weekly refresh real. Every other script in the
pipeline *reads* farm_data.json; without this one, nothing new that Roy logs ever
reaches the atlas and the site silently freezes at whatever snapshot shipped.

    GET /v1/observations?user_login=..&lat=..&lng=..&radius=2    (his farm subset)
    GET /v1/observations/species_counts?user_login=..            (his whole life list)

The CSV export in data/ is kept only as a historical reference. iNat generates CSV
exports on request and emails them, so CI cannot fetch one - the API is the only
automatable source of truth.

Usage:
    python3 scripts/fetch_observations.py --check     # validate endpoints, 2 requests
    python3 scripts/fetch_observations.py             # full pull, ~10 requests
    python3 scripts/fetch_observations.py --dry-run   # pull, diff, write nothing
    python3 scripts/fetch_observations.py --allow-shrink   # accept a big count drop

Writes data/farm_data.json:
    meta          farm identity, scope, totals, quality split, year range
    observations  [{d m y cls g sci com tid q img url}, ...]
    life_taxa     every taxon id he has recorded anywhere (gap list: true lifers)
    life_names    the same set as scientific names, to survive iNat taxon id changes
    farm_taxa     every taxon id inside the farm scope     (gap list: new-to-farm)
    farm_names    the same set as scientific names

Interest scores are NOT written here - they live in data/interest.json, produced by
build_interest.py, so there is exactly one definition of "interest" in the project.
"""
import datetime
import sys

import inat

SHRINK_GUARD = 0.90     # fail if a refresh loses more than 10% of observations
GROWTH_WARN = 1.25      # warn if it gains more than 25% - usually means the scope moved


def photo_url(o):
    photos = o.get("photos") or []
    if not photos:
        return ""
    return (photos[0].get("url") or "").replace("/square.", "/medium.")


def fetch_farm_observations():
    """Page through his farm-scoped observations using an id cursor.

    id_above beats page= because the API caps paging at 10k results; a cursor has
    no such ceiling and cannot silently truncate as his record count grows.
    """
    out, cursor, page = [], 0, 0
    while True:
        payload = inat.get("/observations", {
            "user_login": inat.USER_LOGIN,
            "lat": inat.LAT, "lng": inat.LNG, "radius": inat.FARM_RADIUS_KM,
            "per_page": inat.PER_PAGE,
            "order_by": "id", "order": "asc", "id_above": cursor,
        })
        results = payload.get("results") or []
        page += 1
        print(f"  page {page}: +{len(results)} (total_results={payload.get('total_results')})",
              flush=True)
        if not results:
            break
        for o in results:
            taxon = o.get("taxon") or {}
            observed = o.get("observed_on")
            if not observed or not taxon.get("id"):
                continue                      # undated or unidentified - not renderable
            d = datetime.date.fromisoformat(observed)
            out.append({
                "d": observed,
                "m": d.month,
                "y": d.year,
                "cls": taxon.get("iconic_taxon_name") or "Unknown",
                "g": inat.genus_of(taxon.get("name") or "", taxon.get("rank") or ""),
                "sci": taxon.get("name") or "",
                "com": taxon.get("preferred_common_name") or "",
                "tid": taxon["id"],
                "q": o.get("quality_grade") or "",
                "img": photo_url(o),
                "url": o.get("uri") or f"https://www.inaturalist.org/observations/{o['id']}",
            })
        cursor = results[-1]["id"]
    return out


def fetch_life_taxa():
    """What he has already recorded, as both ids and names.

    Returns (ids, names). BOTH are needed, because matching on taxon id alone produces
    false gaps two different ways - measured against the real 840-gap list:

      - **Rank rollup.** species_counts returns leaf taxa at whatever rank is finest, so
        a genus he has recorded (Xanthotype) can be absent from his own rollup while
        present in the nearby pool. Unioning in farm_taxa covers the local case.
      - **Taxon id drift.** iNat splits and merges taxa, so an observation keeps the id it
        was made under. Hericium erinaceus is id 1520823 in his records and 49158 in the
        pool - same fungus, two ids, and it showed up as a gap he had already logged.
        Matching on scientific name as well catches this.

    Neither is exotic: 2 of 840 gaps were false on the first real run. That is a small
    number and exactly the kind that makes Roy stop trusting the list.
    """
    ids, names, page = [], [], 1
    while True:
        payload = inat.get("/observations/species_counts", {
            "user_login": inat.USER_LOGIN,
            "per_page": inat.COUNTS_PER_PAGE, "page": page,
        })
        results = payload.get("results") or []
        for r in results:
            taxon = r.get("taxon") or {}
            if taxon.get("id"):
                ids.append(taxon["id"])
            if taxon.get("name"):
                names.append(taxon["name"])
        print(f"  species_counts page {page}: +{len(results)} "
              f"(total_results={payload.get('total_results')})", flush=True)
        if len(results) < inat.COUNTS_PER_PAGE:
            break
        page += 1
    return sorted(set(ids)), sorted(set(names))


def build(observations, life_taxa, life_names, asof):
    years = [o["y"] for o in observations]
    quality = {}
    for o in observations:
        quality[o["q"]] = quality.get(o["q"], 0) + 1
    farm_taxa = sorted({o["tid"] for o in observations})
    # fold his own farm records into the lifer sets - see fetch_life_taxa()
    life_taxa = sorted(set(life_taxa) | set(farm_taxa))
    life_names = sorted(set(life_names) | {o["sci"] for o in observations if o["sci"]})
    return {
        "meta": {
            "farm_name": inat.FARM_NAME,
            "place_guess": inat.PLACE_GUESS,
            "lat": inat.LAT, "lng": inat.LNG, "radius_km": inat.FARM_RADIUS_KM,
            "generated": asof.isoformat(),
            "total_obs": len(observations),
            "total_species": len({o["sci"] for o in observations if o["sci"]}),
            "year_min": min(years) if years else None,
            "year_max": max(years) if years else None,
            "quality": quality,
            "life_list_species": len(life_taxa),   # derived, never hand-set
            "user_login": inat.USER_LOGIN,
        },
        "observations": sorted(observations, key=lambda o: (o["d"], o["sci"])),
        "life_taxa": life_taxa,
        "life_names": life_names,
        "farm_taxa": farm_taxa,
        "farm_names": sorted({o["sci"] for o in observations if o["sci"]}),
    }


def main(argv):
    if "--check" in argv:
        inat.check("/observations", {"user_login": inat.USER_LOGIN, "lat": inat.LAT,
                                     "lng": inat.LNG, "radius": inat.FARM_RADIUS_KM})
        inat.check("/observations/species_counts", {"user_login": inat.USER_LOGIN})
        return 0

    asof = datetime.date.today()
    print(f"farm observations for {inat.USER_LOGIN} within {inat.FARM_RADIUS_KM} km "
          f"of {inat.LAT},{inat.LNG}")
    observations = fetch_farm_observations()
    print(f"life list (whole account)")
    life_taxa, life_names = fetch_life_taxa()

    fresh = build(observations, life_taxa, life_names, asof)
    old = inat.load("farm_data.json") or {}
    old_n = (old.get("meta") or {}).get("total_obs", 0)
    new_n = fresh["meta"]["total_obs"]

    print(f"\nobservations: {old_n} -> {new_n}   "
          f"species: {(old.get('meta') or {}).get('total_species')} -> {fresh['meta']['total_species']}   "
          f"life taxa: {len(old.get('life_taxa') or [])} -> {len(life_taxa)}")

    if new_n == 0:
        sys.exit("ERROR: refusing to write an empty farm_data.json")
    if old_n and new_n > old_n * GROWTH_WARN:
        print(f"\nWARNING: observation count jumped {old_n} -> {new_n}. A jump this large is "
              f"usually a scope change, not a month of logging. Confirm FARM_RADIUS_KM "
              f"({inat.FARM_RADIUS_KM} km) is still right before publishing.")
    if old_n and new_n < old_n * SHRINK_GUARD and "--allow-shrink" not in argv:
        sys.exit(f"ERROR: observation count dropped from {old_n} to {new_n} "
                 f"(>{int((1 - SHRINK_GUARD) * 100)}%). This usually means the API or the "
                 f"scope changed, not that records vanished. Re-run with --allow-shrink "
                 f"if the drop is real.")

    if "--dry-run" in argv:
        print("dry run - nothing written")
        return 0

    inat.save("farm_data.json", fresh)
    print(f"api requests this run: {inat.requests_made()}")
    print("\nnext: fetch_taxonomy.py -> build_interest.py -> build_tree.py -> build_pages.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
