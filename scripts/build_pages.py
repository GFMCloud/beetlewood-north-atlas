#!/usr/bin/env python3
"""Step 3 of 3 - inline data (and D3) into the templates to produce the wireframes.

The shipped HTML files are GENERATED. Edit scripts/templates/*.html, then re-run this;
do not hand-edit the 600 KB files in explore/, your changes will be overwritten.

Each template carries two placeholders:
    /*__DATA__*/  -> contents of data/tree_data.json
    /*__D3__*/    -> scripts/vendor/d3.v7.min.js   (sunburst + icicle only)

Inlining both is what keeps the project convention: self-contained single files that
open by double-click and work offline, with no CDN and no build step to *view*.

Usage:  python3 scripts/build_pages.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "scripts" / "templates"

# (template, output, needs D3)
PAGES = [
    ("tpl_explorer.html", "explore/explorer-2pane.html", False),
    ("tpl_sunburst.html", "explore/sunburst-zoom.html", True),
]


def main():
    data = (ROOT / "data" / "tree_data.json").read_text()
    d3 = (ROOT / "scripts" / "vendor" / "d3.v7.min.js").read_text()

    for tpl_name, out_rel, needs_d3 in PAGES:
        src = (TPL / tpl_name).read_text()

        if "/*__DATA__*/" not in src:
            sys.exit(f"ERROR: {tpl_name} is missing the /*__DATA__*/ placeholder")
        src = src.replace("/*__DATA__*/", data)

        if needs_d3:
            if "/*__D3__*/" not in src:
                sys.exit(f"ERROR: {tpl_name} is missing the /*__D3__*/ placeholder")
            src = src.replace("/*__D3__*/", d3)

        # the offline-safe convention, enforced rather than assumed.
        # CHECK BEFORE WRITING - a failed assertion must not leave a bad artifact on disk.
        assert "<script src=" not in src, f"{out_rel} references an external script"
        assert "localStorage" not in src and "sessionStorage" not in src, \
            f"{out_rel} uses web storage (breaks in some sandboxes)"

        out = ROOT / out_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(src)

        print(f"{out_rel:34s} {out.stat().st_size // 1024:5d} KB   d3={needs_d3}")

    print("\nall pages self-contained: no external scripts, no web storage")


if __name__ == "__main__":
    main()
