#!/usr/bin/env python3
"""Verification helper - screenshot pages and report console errors.

Not part of the pipeline. This exists so "show evidence" has one obvious tool and every
check produces the same artifacts, rather than each session inventing its own.

    pip3 install --user playwright && python3 -m playwright install chromium
    python3 scripts/screenshot.py explore/*.html
    python3 scripts/screenshot.py --tabs atlas.html          # click each [data-tab] first

Note: use `python3 -m playwright`, not a bare `playwright` - pip installs the CLI into a
user bin that is usually not on PATH.

Writes PNGs to shots/ (gitignored). Exits non-zero if any real error is found, so it can
gate a build.

Remote taxon photos are expected to fail when offline; those are reported separately and do
not count as errors. See BUILD_SPEC section 9 for why the pages hotlink them.
"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOTS = ROOT / "shots"
PHOTO_HOSTS = ("inaturalist-open-data.s3.amazonaws.com", "static.inaturalist.org")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pages", nargs="+", help="HTML files to load")
    ap.add_argument("--tabs", action="store_true",
                    help="click every [data-tab] element and shoot each one")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--settle", type=int, default=2500, help="ms to wait after load")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright is not installed. Run:\n"
                 "  pip3 install --user playwright && python3 -m playwright install chromium")

    SHOTS.mkdir(exist_ok=True)
    failures = 0

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for page_path in args.pages:
            path = pathlib.Path(page_path).resolve()
            if not path.exists():
                print(f"MISSING  {page_path}")
                failures += 1
                continue

            page = browser.new_page(viewport={"width": args.width, "height": args.height})
            errors, photo_misses = [], []
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
            # Console echoes every failed resource as an error, but without the URL, so it
            # cannot be told apart from a real fault. requestfailed carries the URL and is
            # the authoritative signal - classify there and drop the console duplicate,
            # otherwise offline photo loads drown the output in false alarms.
            page.on("console",
                    lambda m: errors.append(f"console.{m.type}: {m.text}")
                    if m.type == "error" and "Failed to load resource" not in m.text
                    else None)
            page.on("requestfailed",
                    lambda r: (photo_misses if any(h in r.url for h in PHOTO_HOSTS)
                               else errors).append(f"requestfailed: {r.url[:110]}"))

            page.goto(path.as_uri(), wait_until="load")
            page.wait_for_timeout(args.settle)

            shots = [(path.stem, None)]
            if args.tabs:
                labels = page.eval_on_selector_all(
                    "[data-tab]", "els => els.map(e => e.getAttribute('data-tab'))")
                shots = [(f"{path.stem}-{label}", label) for label in labels] or shots

            for name, tab in shots:
                if tab:
                    # A real click first, so a tab covered by an overlay still fails. Nested
                    # controls (the Tree of Life view toggle lives inside its own panel) are
                    # hidden until their panel is active, and DOM order means we reach them
                    # after some other panel is showing - fall back to dispatching the click
                    # through the DOM, which their handler self-heals from by activating the
                    # containing tab.
                    sel = f"[data-tab='{tab}']"
                    try:
                        page.click(sel, timeout=2000)
                    except Exception:
                        page.eval_on_selector(sel, "e => e.click()")
                    page.wait_for_timeout(args.settle)
                page.screenshot(path=str(SHOTS / f"{name}.png"))

            # a page that renders nothing is a failure even with a clean console
            painted = page.evaluate(
                "() => document.querySelectorAll('svg path, canvas, li, tr, .card').length")
            if painted == 0:
                errors.append("rendered no marks at all - blank page")

            status = "FAIL" if errors else "ok  "
            print(f"{status} {page_path}  marks={painted}  errors={len(errors)}"
                  f"  photos-offline={len(photo_misses)}"
                  f"  -> shots/{'|'.join(n for n, _ in shots)}.png")
            for e in errors[:10]:
                print(f"       {e[:160]}")
            failures += bool(errors)
            page.close()
        browser.close()

    print(f"\n{len(args.pages)} page(s), {failures} with errors")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
