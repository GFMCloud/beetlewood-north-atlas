#!/usr/bin/env python3
"""Shared iNaturalist API helpers - politeness, retries, and the one place the farm
scope constants live.

Public read only. No auth, no credentials, no tokens anywhere in this project.
Rate limit is ~60 req/min and <10k/day, so every caller goes through get() which
paces itself at DELAY seconds and retries transient failures 3x.
"""
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

API = "https://api.inaturalist.org/v1"
UA = "BeetlewoodAtlas/1.0 (personal project; github.com/gfmcloud/beetlewood-north-atlas)"

# ── farm scope - the single definition every script and doc refers to ──────────
USER_LOGIN = "roymorrisii"
# Verified against GET /v1/users/roymorrisii on 2026-08-11. This was 764712 until then,
# which is the id of his CSV *export job* (`observations764712.csv`), not of him. Nothing
# read it, because every fetcher passes user_login - but the failure mode is silent and
# nasty: species_counts?user_id=764712 returns 0 results rather than an error, so any
# feature built on it would have looked correctly empty. Endpoints differ on which key
# they honour, so prefer USER_LOGIN for filtering and USER_ID only where a numeric id is
# required (`not_user_id` accepts no login form).
USER_ID = 532376
FARM_NAME = "Beetlewood Farms North"
PLACE_GUESS = "376 Lamar County Line Rd, Griffin, GA"
LAT = 33.18
LNG = -84.20

# ── administrative scope, for the county-records view ─────────────────────────
# DERIVED, never guessed: fetch_county.py reads the place_ids off his own observations
# and asserts these two match, so a wrong constant fails the run instead of quietly
# describing the wrong county. The address is "376 Lamar County Line Rd" and the town is
# Griffin, which is in Spalding - the farm is on the line and falls in LAMAR. An earlier
# draft of tpl_atlas.html offered "Spalding County, GA" in the gap scope selector.
COUNTY_PLACE_ID = 2527   # Lamar County, US, GA  (admin_level 20)
COUNTY_NAME = "Lamar County"
STATE_PLACE_ID = 23      # Georgia, US          (admin_level 10)
STATE_NAME = "Georgia"

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

# ── rate limits, per https://www.inaturalist.org/pages/api+recommended+practices ──
# iNat asks for "about 1 per second, and around 10k API requests a day". Over that you get
# HTTP 429, and they may block IPs that consistently exceed it. Their forum has repeated
# reports of 429s at exactly 60/min, with ~55/min given as the safe target - which is where
# DELAY lands before latency is even counted. Do not lower it to speed a run up.
BATCH = 30              # API hard limit for /taxa/ID1,ID2,...
DELAY = 1.1             # ~55 req/min, deliberately under the ~60/min cliff
MAX_RETRIES = 5
BACKOFF_BASE = 4        # seconds; doubles each attempt, plus jitter
BACKOFF_CAP = 120
REQUEST_BUDGET_WARN = 1000   # a full cold run is ~100; 1000 means something loops per-record

_requests = {"n": 0}
PER_PAGE = 200          # max for /observations
COUNTS_PER_PAGE = 500   # max for /observations/species_counts


def get(path, params=None, retries=MAX_RETRIES, pace=True):
    """GET {API}{path}?{params} as JSON, with rate-limit pacing and backoff.

    Retries are exponential with jitter rather than a flat sleep, for two reasons the
    original flat 3s could not handle:

      - A 429 means we are already going too fast. iNat explicitly asks you to add delays
        when you see one. Retrying 3s later three times makes it worse, not better. If the
        response carries Retry-After we honour it exactly.
      - A local network drop (DNS failure, wifi handover) routinely lasts longer than 9s.
        A three minute pull should ride that out, not die and discard its work.
    """
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    _requests["n"] += 1
    if _requests["n"] == REQUEST_BUDGET_WARN:
        print(f"\n  WARNING: {REQUEST_BUDGET_WARN} API requests in one run. A full cold run "
              f"is ~100. This usually means something is looping per-record instead of "
              f"batching 30 at a time. iNat's daily allowance is ~10k.\n",
              file=sys.stderr, flush=True)
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                payload = json.load(r)
            if pace:
                time.sleep(DELAY)
            return payload
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                wait = None
                try:
                    wait = float(e.headers.get("Retry-After") or 0) or None
                except (TypeError, ValueError):
                    wait = None
                wait = wait or min(BACKOFF_CAP, BACKOFF_BASE * 2 ** attempt)
                print(f"  429 Too Many Requests - backing off {wait:.0f}s "
                      f"(attempt {attempt + 1}/{retries})", file=sys.stderr, flush=True)
                time.sleep(wait)
                continue
            if 400 <= e.code < 500 and e.code != 408:
                raise RuntimeError(f"GET {url} -> HTTP {e.code} {e.reason}. "
                                   f"Client error, not retrying.") from e
            wait = min(BACKOFF_CAP, BACKOFF_BASE * 2 ** attempt) + random.uniform(0, 2)
            print(f"  HTTP {e.code}, retry {attempt + 1}/{retries} in {wait:.0f}s",
                  file=sys.stderr, flush=True)
            time.sleep(wait)
        except Exception as e:                      # noqa: BLE001 - network/DNS/timeout
            last = e
            wait = min(BACKOFF_CAP, BACKOFF_BASE * 2 ** attempt) + random.uniform(0, 2)
            print(f"  retry {attempt + 1}/{retries} in {wait:.0f}s: {e}",
                  file=sys.stderr, flush=True)
            time.sleep(wait)
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last}")


def species_counts(params, label="", page_cap=200):
    """Page through /observations/species_counts and return {taxon_id: record}.

    Deep paging is safe on this endpoint - verified 2026-08-11 by walking Georgia's 23,589
    taxa to page 48 of 48 and getting a well-formed tail - so there is no 10k offset cliff
    to work around here.

    Returns {tid: {"count", "name", "common", "rank"}}. The dict, rather than the raw list,
    is deliberate: callers compare these by SET MEMBERSHIP, not by count equality. iNat
    aggregates these live, so two pulls seconds apart can disagree on a count by one or two
    - comparing counts across two paged pulls invented 28 phantom results the first time it
    was tried. Membership is stable; counts are for display.
    """
    out, page, expected = {}, 1, None
    while True:
        p = dict(params, per_page=COUNTS_PER_PAGE, page=page)
        payload = get("/observations/species_counts", p)
        results = payload.get("results") or []
        if expected is None:
            expected = payload.get("total_results") or 0
        if not results:
            break
        for r in results:
            t = r.get("taxon") or {}
            if t.get("id") is None:
                continue
            out[t["id"]] = {
                "count": r.get("count", 0),
                "name": t.get("name") or "",
                "common": t.get("preferred_common_name") or "",
                "rank": t.get("rank") or "",
                # carried so callers can colour by palette class without a taxonomy join
                "iconic": t.get("iconic_taxon_name") or "Unknown",
                # REQUIRED for any set comparison between two species_counts pulls.
                # The endpoint reports the finest rank available *within each query*, so
                # one observer's genus-level record and another's species-level record of
                # the same lineage come back as two unrelated ids. Comparing ids alone
                # then counts them as different taxa. See fetch_county.py:sole_observers.
                "ancestors": tuple(t.get("ancestor_ids") or ()),
            }
        total = payload.get("total_results") or 0
        if page * COUNTS_PER_PAGE >= total or page >= page_cap:
            break
        page += 1

    # A SHORT WALK MUST FAIL LOUDLY. The loop above treats an empty page as end-of-data, so
    # one transient 200-with-empty-body mid-walk silently returns a partial set. That is not
    # symmetric in its consequences: callers subtracting one of these from another get a
    # SMALLER subtrahend and therefore an INFLATED difference. For the county comparison a
    # truncated "everyone but him" pull would overstate how much is uniquely his, and it
    # would slip past the union invariant in fetch_county.py, which only catches the
    # difference being too large relative to the county total, not both shrinking together.
    # Tolerance rather than equality because the dict collapses any taxon iNat repeats
    # across page boundaries, and because these aggregates shift between requests.
    if expected and len(out) < expected * 0.98:
        raise RuntimeError(
            f"species_counts walk returned {len(out)} taxa but the API reported "
            f"{expected} for {params}. Refusing a partial result - a short pull here "
            f"inflates every difference computed against it."
        )
    if label:
        print(f"  {label:34s} {len(out):>6} taxa")
    return out


def requests_made():
    """Total API calls this process has made. Print it at the end of every fetcher."""
    return _requests["n"]


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


def save(name, obj, quiet=False):
    p = DATA / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, separators=(",", ":")))
    if not quiet:
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
