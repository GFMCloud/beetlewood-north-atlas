#!/usr/bin/env python3
"""Shared iNaturalist API helpers - politeness, retries, and the one place the farm
scope constants live.

Public read only. No auth, no credentials, no tokens anywhere in this project.
Rate limit is ~60 req/min and <10k/day, so every caller goes through get() which
paces itself at DELAY seconds and retries transient failures 3x.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

API = "https://api.inaturalist.org/v1"
UA = "BeetlewoodAtlas/1.0 (personal project; github.com/gfmcloud/beetlewood-north-atlas)"

# ── farm scope - the single definition every script and doc refers to ──────────
USER_LOGIN = "roymorrisii"
USER_ID = 764712
FARM_NAME = "Beetlewood Farms North"
PLACE_GUESS = "376 Lamar County Line Rd, Griffin, GA"
LAT = 33.18
LNG = -84.20

# TWO DIFFERENT SCOPES. Conflating them silently redefines what "the farm" means.
#
#   FARM_RADIUS_KM   - the property itself. Every one of his 1,393 farm records sits within
#                      0.64 km of the centre (bbox 0.55 x 0.32 km), and the next cluster of
#                      his records is ~10 km away, so anything in [0.7, 9] returns exactly
#                      the same 1,393. 2 km sits in the middle of that gap with margin on
#                      both sides. Measured, not guessed - see BUILD_SPEC section 11.
#   NEARBY_RADIUS_KM - "what other people record around here", for the gap pool only.
#                      Deliberately wide. 15 km returns 1,807 research-grade species.
#
# Using 15 km for the farm pulls in 1,747 observations instead of 1,393 - a 25% inflation
# of every headline number on the site, from a different site entirely.
FARM_RADIUS_KM = 2
NEARBY_RADIUS_KM = 15   # iNat's `radius` parameter is in kilometres

BATCH = 30              # API hard limit for /taxa/ID1,ID2,...
DELAY = 1.1             # ~55 req/min, under the ~60/min limit
PER_PAGE = 200          # max for /observations
COUNTS_PER_PAGE = 500   # max for /observations/species_counts


def get(path, params=None, retries=3, pace=True):
    """GET {API}{path}?{params} as JSON, with retries and rate-limit pacing."""
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                payload = json.load(r)
            if pace:
                time.sleep(DELAY)
            return payload
        except Exception as e:                      # noqa: BLE001 - report and retry
            last = e
            print(f"  retry {attempt + 1}/{retries}: {e}", file=sys.stderr, flush=True)
            time.sleep(3)
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last}")


def check(path, params=None):
    """One tiny request, printed raw-ish. Use this to validate an endpoint's shape
    before committing to a full paged pull:  python3 scripts/<script>.py --check
    """
    p = dict(params or {})
    p["per_page"] = 1
    payload = get(path, p, pace=False)
    print(f"GET {path}  ->  total_results={payload.get('total_results')}")
    results = payload.get("results") or []
    if not results:
        print("  no results - check the scope parameters")
        return payload
    first = results[0]
    print(f"  top-level keys: {sorted(first)}")
    taxon = first.get("taxon") or {}
    if taxon:
        print(f"  taxon keys:     {sorted(taxon)}")
        print(f"  ancestor_ids present: {'ancestor_ids' in taxon}")
        print(f"  sample: id={taxon.get('id')} name={taxon.get('name')!r} "
              f"rank={taxon.get('rank')!r} iconic={taxon.get('iconic_taxon_name')!r}")
    return payload


def load(name, default=None):
    p = DATA / name
    if p.exists():
        return json.loads(p.read_text())
    return default


def save(name, obj):
    p = DATA / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, separators=(",", ":")))
    print(f"wrote data/{name} ({p.stat().st_size // 1024} KB)")
    return p


def genus_of(name, rank):
    """Genus string used by farm_data observations.

    Only meaningful at genus rank or below. A family-level ID has no genus, and
    guessing one from the first token would invent 'Curculionidae' as a genus.
    """
    if rank in ("species", "subspecies", "variety", "form", "hybrid"):
        return name.split()[0]
    if rank == "genus":
        return name
    return ""
