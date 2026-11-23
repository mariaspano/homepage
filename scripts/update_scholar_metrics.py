#!/usr/bin/env python3
"""Update data/metrics.yml with citations / h-index / i10-index from Google Scholar.

Run it from your own computer (Google Scholar blocks requests from cloud servers):
    python3 scripts/update_scholar_metrics.py
then commit and push data/metrics.yml: the website rebuilds automatically.
"""
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

USER = "kh_hGT0AAAAJ"
OUT = Path(__file__).resolve().parent.parent / "data" / "metrics.yml"

req = urllib.request.Request(
    f"https://scholar.google.com/citations?user={USER}&hl=en",
    headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"},
)
try:
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
except Exception as exc:
    sys.exit(f"Could not reach Google Scholar: {exc}")

# The metrics table has 6 cells: citations (all, since), h-index (all, since), i10 (all, since)
cells = re.findall(r'class="gsc_rsb_std">(\d+)<', html)
if len(cells) < 6:
    sys.exit("Metrics not found (Scholar may be asking for a CAPTCHA). Try again later or update "
             "data/metrics.yml by hand.")
citations, h_index, i10 = int(cells[0]), int(cells[2]), int(cells[4])

OUT.write_text(
    "# Citation metrics shown on the home page.\n"
    "# Update with:  python3 scripts/update_scholar_metrics.py   (run from your own computer)\n"
    f"source: Google Scholar\nupdated: {date.today().isoformat()}\n"
    f"citations: {citations}\nh_index: {h_index}\ni10_index: {i10}\n",
    encoding="utf-8",
)
print(f"Google Scholar: {citations} citations, h-index {h_index}, i10-index {i10} -> {OUT.name}")
