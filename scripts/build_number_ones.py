"""Build the tennis world No. 1 dataset used by tennis/number-one: every spell at No. 1 in the ATP and WTA
rankings, with its dates, weeks and the player's nation at the time.

Source: Wikipedia's lists of ATP and WTA No. 1 ranked singles players (the table of every spell, checked
against the same page's table of total weeks per player).

Usage:
    python3 scripts/build_number_ones.py            # cached pages
    python3 scripts/build_number_ones.py --refresh  # re-download them
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wikitables as W  # noqa: E402
from build_tennis_ages import nation  # noqa: E402
from olympic_events import nation_info  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "raw" / "wikipedia"
OUTPUT = ROOT / "tennis" / "number-one" / "data" / "number-one.json"
PAGES = {
    "atp": "List of ATP number 1 ranked singles tennis players",
    "wta": "List of WTA number 1 ranked singles tennis players",
}
# Known records the build must reproduce.
EXPECT = {
    "atp": {"players": 29, "streak": ("Roger Federer", 237), "weeks": {"Novak Djokovic": 428, "Roger Federer": 310, "Pete Sampras": 286}},
    "wta": {"players": 30, "streak": ("Steffi Graf", 186), "weeks": {"Steffi Graf": 377, "Martina Navratilova": 332, "Serena Williams": 319}},
}
NATION_FIX = {"FRY": "YUG", "SCG": "YUG"}


def page(title: str, refresh: bool) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return W.fetch_raw(title, CACHE / f"{slug}.wiki", refresh, pause=1.5)


def dts(text: str) -> date | None:
    m = re.search(r"\{\{\s*dts\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})", text, re.I)
    return date(*map(int, m.groups())) if m else None


def weeks_cell(text: str, start: date, end: date) -> int:
    """The Weeks column: a number, {{age in weeks|start|end}}, or {{sum|{{age in weeks|start}}+1}} for the current spell."""
    plain = W.strip_refs(text).strip(" '")
    if re.fullmatch(r"\d+", plain):
        return int(plain)
    m = re.search(r"age in weeks\s*\|\s*(\d{4})\|(\d{1,2})\|(\d{1,2})\s*\|\s*(\d{4})\|(\d{1,2})\|(\d{1,2})", text, re.I)
    if m:
        a, b = date(*map(int, m.groups()[:3])), date(*map(int, m.groups()[3:]))
        return (b - a).days // 7
    m = re.search(r"age in weeks\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})\s*\}\}\s*\+\s*(\d+)", text, re.I)
    if m:
        return (date.today() - date(*map(int, m.groups()[:3]))).days // 7 + int(m.group(4))
    return (end - start).days // 7 + 1


def spells(text: str) -> list[dict]:
    start = re.search(r"^==\s*(?:ATP|WTA) No\. 1 ranked singles players\s*==", text, re.M)
    table = W.parse_table(W.find_table(text[start.start():], r"ranked singles players"))
    out = []
    for row in table:
        cells = [c["text"] for c in row]
        pi = next((i for i, c in enumerate(cells) if re.search(r"sortname|\{\{\s*sort\s*\|", c, re.I)), None)
        if pi is None:
            continue
        dates = [i for i, c in enumerate(cells) if i > pi and (dts(c) or re.search(r"present", c, re.I))]
        if len(dates) < 2:
            continue
        cell = cells[pi]
        name = W.person(cell) if "sortname" in cell.lower() else None
        if not name:
            inner = re.search(r"\{\{\s*sort\s*\|[^|]*\|(.*)\}\}", cell, re.S)
            body = re.sub(r"\{\{\s*small[^{}]*\}\}|<ref.*?(?:/>|</ref>)|\{\{#tag:ref.*?\}\}", "", inner.group(1) if inner else cell, flags=re.S)
            name = W.plain(body)
        name = re.sub(r"\s*\(\d+\)\s*$", "", name.split("|")[0]).strip(" '/")
        code = nation(cell)
        code = NATION_FIX.get(code, code)
        if re.search(r"\{\{\s*flagathlete", cell, re.I):
            m = re.search(r"\|\s*([A-Z]{3})\s*(?:\||\}\})", cell)
            code = m.group(1) if m else code
        s = dts(cells[dates[0]])
        if s is None:
            continue
        current = bool(re.search(r"present", cells[dates[1]], re.I))
        e = date.today() if current else dts(cells[dates[1]])
        weeks = weeks_cell(cells[dates[1] + 1], s, e) if len(cells) > dates[1] + 1 else (e - s).days // 7 + 1
        if re.search(r"rankings.*frozen", W.plain(cell), re.I):  # COVID-19: no rankings, no weeks for anyone.
            out.append({"name": None, "nation": None, "start": s.isoformat(), "end": e.isoformat(), "weeks": weeks, "frozen": True})
            continue
        out.append({"name": name, "nation": code, "start": s.isoformat(), "end": e.isoformat(), "weeks": weeks, "current": current})
    return out


def total_weeks(text: str) -> dict[str, int]:
    """The 'Weeks at No. 1 → Total' table: weeks per player, for checking."""
    start = text.index("== Weeks at No. 1 ==")
    out = {}
    for row in W.parse_table(W.find_table(text[start:], r"=== ?Total ?===")):
        link = next((W.links(c["text"]) for c in row if W.links(c["text"])), None)
        if not link:
            continue
        nums = [W.plain(c["text"]) for c in row]
        m = re.search(r"ageinweeks\|(\d{4})\|(\d+)\|(\d+)\}\}\+(\d+)", row[-1]["text"].replace(" ", ""), re.I)
        base = re.search(r"sum\|(\d+)\+", row[-1]["text"].replace(" ", ""), re.I)
        if m:
            n = (int(base.group(1)) if base else 0) + (date.today() - date(*map(int, m.groups()[:3]))).days // 7 + int(m.group(4))
        elif re.fullmatch(r"\d+", nums[-1].strip(" '")):
            n = int(nums[-1].strip(" '"))
        else:
            continue
        out[link[0][1] or link[0][0]] = n
    return out


def build(refresh: bool) -> tuple[dict, list[str]]:
    data = {"meta": {"generated": date.today().isoformat(), "sources": [f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}" for t in PAGES.values()]},
            "tours": {}, "nations": {}}
    errors = []
    for tour, title in PAGES.items():
        text = page(title, refresh)
        rows = spells(text)
        data["tours"][tour] = {"spells": rows}
        for r in rows:
            if r["nation"]:
                data["nations"].setdefault(r["nation"], nation_info(r["nation"]))
        # Checks.
        exp = EXPECT[tour]
        players = {r["name"] for r in rows if r["name"]}
        if len(players) < exp["players"]:
            errors.append(f"{tour}: {len(players)} players at No. 1, expected {exp['players']}")
        longest = max((r for r in rows if r["name"]), key=lambda r: r["weeks"])
        if (longest["name"], longest["weeks"]) != exp["streak"]:
            errors.append(f"{tour}: longest streak {longest['name']} {longest['weeks']}, expected {exp['streak']}")
        sums = {}
        for r in rows:
            if r["name"]:
                sums[r["name"]] = sums.get(r["name"], 0) + r["weeks"]
        for name, n in exp["weeks"].items():
            if sums.get(name, 0) < n:
                errors.append(f"{tour}: {name} {sums.get(name)} weeks, expected at least {n}")
        totals = total_weeks(text)
        if len(totals) < exp["players"]:
            errors.append(f"{tour}: read {len(totals)} rows of the totals table")
        for name, n in totals.items():
            got = sums.get(name)
            if got is None or abs(got - n) > 1:
                errors.append(f"{tour}: {name} has {got} weeks in the spells but {n} in the totals table")
        for a, b in zip(rows, rows[1:]):
            if date.fromisoformat(b["start"]) - date.fromisoformat(a["end"]) > timedelta(days=60):
                errors.append(f"{tour}: gap between {a['name']} ({a['end']}) and {b['name']} ({b['start']})")
        unknown = sorted({r["nation"] for r in rows if r["nation"] and data["nations"][r["nation"]]["name"] == r["nation"]})
        if unknown:
            errors.append(f"{tour}: unknown nations {unknown}")
    data["nations"] = dict(sorted(data["nations"].items()))
    return data, errors


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="re-download the Wikipedia pages")
    args = ap.parse_args()
    data, errors = build(args.refresh)
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    old = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else None
    strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}  # noqa: E731
    if old and strip(old) == strip(data):
        print(f"{OUTPUT.relative_to(ROOT)} is up to date")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    t = data["tours"]
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(t['atp']['spells'])} ATP and {len(t['wta']['spells'])} WTA spells at No. 1")


if __name__ == "__main__":
    main()
