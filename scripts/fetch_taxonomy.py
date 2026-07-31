#!/usr/bin/env python3
"""Step 1 of 3 - fetch order/family/genus ancestry for every farm taxon from iNaturalist.

The CSV export only carries class, genus and scientific name, so the farm data alone
cannot express "Insecta -> Coleoptera -> Cerambycidae". This fills that gap by asking
the API for each taxon's full ancestor chain.

    GET /v1/taxa/ID1,ID2,...   (max 30 ids per call, per BUILD_SPEC)

Public read, no auth, no credentials. Rate limit is ~60 req/min and <10k/day, so the
batches are capped at 30 ids and paced ~1.1s apart - roughly 32 calls / 40s for the
farm's 952 taxa. Failed batches retry 3x before being reported as unresolved.

Writes data/taxonomy.json:

    { "<taxon_id>": {
        "rank":   "species",
        "name":   "Harmonia axyridis",
        "common": "Asian Lady Beetle",
        "chain":  { "kingdom": ["Animalia", 1], "class": ["Insecta", 47158],
                    "order": ["Coleoptera", 47208], "family": ["Coccinellidae", 48486],
                    "genus": ["Harmonia", 121850], "species": [...] }
      }, ... }

Each chain value is [name, taxon_id]; the id is what lets every node in the wireframes
link back to its own iNaturalist page. Only the seven major ranks are kept - suborder,
infraorder, superfamily and tribe are dropped so the tree stays a clean 5 levels.

Usage:  python3 scripts/fetch_taxonomy.py [--force]

Re-run it whenever farm_data.json gains new taxa; already-cached ids are skipped
unless --force is passed.
"""
import json, time, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "BeetlewoodAtlas/0.1 (+https://github.com/ - personal project)"
RANKS = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]
BATCH = 30           # API hard limit for /taxa/ID1,ID2,...
DELAY = 1.1          # keeps us near ~55 req/min, under the ~60/min limit
OUT = ROOT / "data" / "taxonomy.json"


def main(force=False):
    farm = json.loads((ROOT / "data" / "farm_data.json").read_text())
    tids = sorted({o["tid"] for o in farm["observations"] if o.get("tid")})

    cache = {}
    if OUT.exists() and not force:
        cache = json.loads(OUT.read_text())
        todo = [t for t in tids if str(t) not in cache]
        print(f"{len(cache)} taxa already cached; {len(todo)} to fetch")
    else:
        todo = tids
        print(f"fetching all {len(todo)} taxa")

    if not todo:
        print("nothing to do - taxonomy.json is current")
        return 0

    missing = []
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        url = "https://api.inaturalist.org/v1/taxa/" + ",".join(str(t) for t in batch)
        req = urllib.request.Request(url, headers={"User-Agent": UA})

        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    payload = json.load(r)
                break
            except Exception as e:
                print(f"  retry {attempt + 1}/3 on batch {i // BATCH + 1}: {e}", flush=True)
                time.sleep(3)
        else:
            missing.extend(batch)
            continue

        got = set()
        for t in payload.get("results", []):
            chain = {}
            for a in t.get("ancestors", []):
                if a["rank"] in RANKS:
                    chain[a["rank"]] = [a["name"], a["id"]]
            if t["rank"] in RANKS:                 # the taxon occupies its own rank
                chain[t["rank"]] = [t["name"], t["id"]]
            cache[str(t["id"])] = {
                "rank": t["rank"],
                "name": t["name"],
                "common": t.get("preferred_common_name") or "",
                "chain": chain,
            }
            got.add(t["id"])

        missing.extend([b for b in batch if b not in got])
        print(f"batch {i // BATCH + 1}/{(len(todo) + BATCH - 1) // BATCH}: "
              f"{len(cache)} taxa cached", flush=True)
        time.sleep(DELAY)

    OUT.write_text(json.dumps(cache, separators=(",", ":")))

    have_order = sum(1 for v in cache.values() if v["chain"].get("order"))
    have_family = sum(1 for v in cache.values() if v["chain"].get("family"))
    print(f"\nresolved {len(cache)} / {len(tids)} taxa   unresolved: {len(missing)}")
    print(f"  with order:  {have_order}")
    print(f"  with family: {have_family}")
    if missing:
        print(f"  unresolved ids: {missing[:40]}")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(force="--force" in sys.argv))
