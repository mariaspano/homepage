#!/usr/bin/env python3
"""Find works on the ORCID record that are not yet on the website.

New works are appended to data/publications.yml with `review: true`.
Citations are built from Crossref when the work has a DOI, otherwise from ORCID.

Usage:
  python3 scripts/sync_orcid.py                # add new works
  python3 scripts/sync_orcid.py --dry-run      # only report
  python3 scripts/sync_orcid.py --init-ignore  # mark every unmatched ORCID work as known
                                               # (stored in data/orcid-ignore.yml)
Only the Python standard library and PyYAML are needed.
"""
import argparse
import difflib
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ORCID = "0000-0002-3103-2342"
ROOT = Path(__file__).resolve().parent.parent
PUBS = ROOT / "data" / "publications.yml"
IGNORE = ROOT / "data" / "orcid-ignore.yml"
UA = {"User-Agent": "homepage-publication-sync/1.0 (personal academic website)"}

TYPE_MAP = {
    "journal-article": "article",
    "book-chapter": "chapter",
    "conference-paper": "proceedings",
    "conference-abstract": "proceedings",
    "book": "book",
    "edited-book": "book",
    "preprint": "working",
    "working-paper": "working",
    "report": "other",
    "software": "other",
}

HEADER = """# Publications shown on the website (single source of truth).
# Each entry: type (working | article | book | chapter | proceedings | other),
# year, optional doi, and the citation in Markdown exactly as it appears on the site.
# Entries with "review: true" were added automatically from ORCID and still need a check:
# fix the citation if needed, then delete the "review" line.
"""


# ----------------------------------------------------------------- helpers
def get_json(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def norm(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def title_of(citation):
    # titles are in *italics*; software entries have the name in **bold** instead
    m = re.search(r"(?<!\*)\*(?!\*)([^*]+?)\*(?!\*)", citation) or re.search(r"\*\*([^*]+?)\*\*", citation)
    return m.group(1) if m else citation


def same_title(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if len(a) > 25 and len(b) > 25 and (a in b or b in a):
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def initials(given):
    parts = re.split(r"[\s]+", given.strip())
    out = []
    for p in parts:
        if not p:
            continue
        out.append("-".join(s[0].upper() + "." for s in p.split("-") if s))
    return " ".join(out)


def join_authors(names):
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + ", & " + names[-1]


# ----------------------------------------------------------------- ORCID
def orcid_works():
    data = get_json(f"https://pub.orcid.org/v3.0/{ORCID}/works", {"Accept": "application/json"})
    works = []
    for g in data.get("group", []):
        s = g["work-summary"][0]
        ids = s.get("external-ids") or {}
        doi = next((e["external-id-value"].lower() for e in ids.get("external-id", [])
                    if e["external-id-type"] == "doi"), None)
        year = ((s.get("publication-date") or {}).get("year") or {}).get("value")
        works.append({
            "put_code": s["put-code"],
            "title": " ".join(s["title"]["title"]["value"].split()),
            "type": s["type"],
            "year": int(year) if year else None,
            "doi": doi,
            "journal": (s.get("journal-title") or {}).get("value"),
        })
    return works


def orcid_authors(put_code):
    try:
        w = get_json(f"https://pub.orcid.org/v3.0/{ORCID}/work/{put_code}", {"Accept": "application/json"})
    except Exception:
        return []
    names = []
    for c in ((w.get("contributors") or {}).get("contributor") or []):
        n = ((c.get("credit-name") or {}).get("value") or "").strip()
        if not n:
            continue
        if "," in n:
            fam, giv = [x.strip() for x in n.split(",", 1)]
        else:
            bits = n.split()
            fam, giv = bits[-1], " ".join(bits[:-1])
        names.append(f"{fam}, {initials(giv)}" if giv else fam)
    return names


# ----------------------------------------------------------------- Crossref
def crossref(doi):
    try:
        return get_json("https://api.crossref.org/works/" + urllib.parse.quote(doi))["message"]
    except Exception:
        return None


def citation_from_crossref(m, doi, fallback_year):
    authors = [f'{a.get("family", "").strip()}, {initials(a.get("given", ""))}'.strip(", ")
               for a in m.get("author", [])]
    parts = (m.get("published-print") or m.get("published-online") or m.get("issued") or {}).get("date-parts", [[None]])
    year = parts[0][0] or fallback_year
    title = " ".join((m.get("title") or [""])[0].split())
    container = (m.get("container-title") or [""])[0]
    vol, issue = m.get("volume"), m.get("issue")
    pages = m.get("page") or m.get("article-number")
    tail = ""
    if vol:
        tail += f", {vol}" + (f"({issue})" if issue else "")
    if pages:
        tail += f", {pages.replace('-', '–')}"
    venue = f" **{container}**{tail}." if container else ""
    return year, f"{join_authors(authors)} ({year}). *{title}*.{venue} [DOI](https://doi.org/{doi})"


def citation_from_orcid(w):
    names = orcid_authors(w["put_code"])
    who = join_authors(names) if names else "Spano, M."
    venue = f' **{w["journal"]}**.' if w.get("journal") else ""
    title = " ".join(w["title"].split())
    return f'{who} ({w["year"] or "n.d."}). *{title}*.{venue}'


# ----------------------------------------------------------------- YAML io
class Dumper(yaml.SafeDumper):
    pass


Dumper.add_representer(
    str, lambda d, v: d.represent_scalar("tag:yaml.org,2002:str", v, style=">" if len(v) > 90 else None))


def save_pubs(pubs):
    PUBS.write_text(HEADER + yaml.dump({"publications": pubs}, Dumper=Dumper, allow_unicode=True,
                                       sort_keys=False, width=100), encoding="utf-8")


def load_ignore():
    if IGNORE.exists():
        return yaml.safe_load(IGNORE.read_text(encoding="utf-8")) or {"ignore": []}
    return {"ignore": []}


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--init-ignore", action="store_true")
    args = ap.parse_args()

    pubs = yaml.safe_load(PUBS.read_text(encoding="utf-8"))["publications"]
    ign = load_ignore()
    ignored = {int(i["put_code"]) for i in ign.get("ignore", [])}
    site_dois = {p["doi"].lower() for p in pubs if p.get("doi")}
    site_titles = [title_of(p["citation"]) for p in pubs]

    new = []
    for w in orcid_works():
        if w["put_code"] in ignored:
            continue
        if w["doi"] and w["doi"] in site_dois:
            continue
        if any(same_title(w["title"], t) for t in site_titles):
            continue
        new.append(w)

    if args.init_ignore:
        ign.setdefault("ignore", [])
        for w in new:
            ign["ignore"].append({"put_code": w["put_code"], "title": w["title"][:120], "year": w["year"]})
        IGNORE.write_text(
            "# ORCID works deliberately NOT shown on the website (duplicates, variants, other).\n"
            "# Remove a line to let the sync propose that work again.\n"
            + yaml.dump(ign, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
        print(f"Marked {len(new)} unmatched ORCID works as known in {IGNORE.name}")
        return

    lines = []
    for w in new:
        typ = TYPE_MAP.get(w["type"], "other")
        year = w["year"]
        if w["doi"] and (m := crossref(w["doi"])):
            year, cit = citation_from_crossref(m, w["doi"], year)
        else:
            cit = citation_from_orcid(w)
        entry = {"type": typ, "year": year}
        if w["doi"]:
            entry["doi"] = w["doi"]
        entry["citation"] = cit
        entry["review"] = True
        entry["orcid_put_code"] = w["put_code"]
        pubs.append(entry)
        lines.append(f"- **{typ}** ({year}): {cit}")

    report = ROOT / "sync-report.md"
    if not new:
        print("No new ORCID works.")
        report.unlink(missing_ok=True)
        return
    body = ("New works found on ORCID and added to `data/publications.yml` with `review: true`.\n\n"
            "Check each citation (authors, venue, volume, pages), edit it if needed, delete the "
            "`review: true` line, then merge. To hide a work, delete its entry and add its "
            "`orcid_put_code` to `data/orcid-ignore.yml`.\n\n" + "\n".join(lines) + "\n")
    print(body)
    if not args.dry_run:
        save_pubs(pubs)
        report.write_text(body, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(body)


if __name__ == "__main__":
    sys.exit(main())
