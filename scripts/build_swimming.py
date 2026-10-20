"""Build the Olympic swimming dataset used by swimming/olympics.

Reads Wikipedia's lists of Olympic medalists in swimming (men and women): one
table per event, current and discontinued, with every medalist, nation and
(where listed) time, relay swimmers included. The build checks the number
of pool events at each Games and the career medals of the most decorated
swimmers; each page's own medal table (kept by hand, and not always in step
with its lists) is only compared as a warning.

Usage:
    python3 scripts/build_swimming.py            # use cached pages
    python3 scripts/build_swimming.py --refresh  # re-download them
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict

import wikitables as W
from build_football import RAW_DIR, ROOT, slug
from olympic_events import MEDALS, check_athletes, nation_of, parse_by_event, summarize

OUTPUT = ROOT / "swimming" / "olympics" / "data" / "swimming-olympics.json"
PAGES = {"Men": "List of Olympic medalists in swimming (men)", "Women": "List of Olympic medalists in swimming (women)"}

# Pool events at each Games (the marathon swim is open water and not on these lists).
EVENTS_PER_GAMES = {1968: 29, 1972: 29, 1976: 26, 1980: 26, 1984: 29, 1988: 31, 1992: 31, 1996: 32, 2000: 32, 2004: 32,
                    2008: 32, 2012: 32, 2016: 32, 2020: 35, 2024: 35}

# Career medal totals (individual and relay), used as a sanity check. Relay medals follow the swimmers the lists
# name: for some early relays they leave out heat swimmers (Dara Torres's 1988 medley silver), so she isn't checked.
EXPECTED_SWIMMERS = {
    "Michael Phelps": (23, 3, 2), "Mark Spitz": (9, 1, 1), "Jenny Thompson": (8, 3, 1), "Ryan Lochte": (6, 3, 3),
    "Natalie Coughlin": (3, 4, 5), "Matt Biondi": (8, 2, 1), "Ian Thorpe": (5, 3, 1),
}
EXPECTED_MIN = {"Katie Ledecky": (9, 4, 1), "Emma McKeon": (6, 3, 2)}


def stroke_of(name: str) -> str:
    low = name.lower()
    if "relay" in low or "team race" in low:
        return "Relay"
    for stroke in ("freestyle", "backstroke", "breaststroke", "butterfly", "medley"):
        if stroke in low:
            return stroke.capitalize()
    return "Other"


def medal_table(text: str) -> dict[str, tuple[int, int, int]]:
    """The page's own all-time medal table ({{Medals table}} template)."""
    start = text.find("{{Medals table")
    body = text[start:text.find("\n}}", start)]
    out = {}
    for code in re.findall(r"gold_([A-Z]{3})\s*=", body):
        get = lambda medal: int(re.search(rf"{medal}_{code}\s*=\s*(\d+)", body).group(1))
        out[code] = (get("gold"), get("silver"), get("bronze"))
    return out


def build(refresh: bool) -> dict:
    events, official = [], {}
    for gender, title in PAGES.items():
        text = W.fetch_raw(title, RAW_DIR / "swimming" / f"{slug(title)}.wiki", refresh)
        official[gender] = medal_table(text)
        section, current = gender, True
        for m in re.finditer(r"\n(={2,3})\s*([^=\n]+?)\s*\1[ \t]*(?=\n)", text):
            level, heading = len(m.group(1)), W.plain(m.group(2))
            if level == 2:
                section = "Mixed" if heading.startswith("Mixed") else gender
                current = not heading.lower().startswith("discontinued")
                if "medal table" in heading.lower() or heading.lower().startswith(("youngest", "see also")):
                    break
                continue
            if section == "Mixed" and gender == "Women":
                continue  # the mixed relay is listed on both pages
            body = text[m.end():]
            nxt = re.search(r"\n==", body)
            tables = W.all_tables("\n" + (body[:nxt.start()] if nxt else body))
            results = parse_by_event(tables[0]) if tables else []
            if not results:
                continue
            name = heading[0].upper() + heading[1:]
            events.append({
                "key": slug(f"{section}-{name}"), "name": name, "gender": section, "group": stroke_of(name),
                "current": current, "results": results,
            })
    data = summarize(events, list(PAGES.values()))
    data["_official"] = official
    return data


def validate(data: dict) -> list[str]:
    errors = []
    official = data.pop("_official")
    # Wikipedia's medal tables merge every German team into Germany and include the mixed relay.
    merge = {"GDR": "GER", "FRG": "GER", "EUA": "GER"}
    for gender, table in official.items():
        got = defaultdict(Counter)
        for ev in data["events"]:
            if ev["gender"] in (gender, "Mixed"):
                for r in ev["results"]:
                    for medal in MEDALS:
                        for slot in r[medal]:
                            got[merge.get(nation_of(slot), nation_of(slot))][medal] += 1
        diff = {c: (tuple(got[c][m] for m in MEDALS), exp) for c, exp in table.items() if tuple(got[c][m] for m in MEDALS) != exp}
        if diff:
            print(f"warning: {gender} medals differ from the page's own medal table (got, table): {diff}", file=sys.stderr)
    per_games = Counter(r["year"] for ev in data["events"] for r in ev["results"])
    for year, n in EVENTS_PER_GAMES.items():
        if per_games[year] != n:
            errors.append(f"{year}: {per_games[year]} events, expected {n}")
    return errors + check_athletes(data, EXPECTED_SWIMMERS, EXPECTED_MIN)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download the Wikipedia pages")
    args = parser.parse_args()
    data = build(args.refresh)
    errors = validate(data)
    if errors:
        sys.exit("validation failed:\n  " + "\n  ".join(errors))
    if OUTPUT.exists():
        old = json.loads(OUTPUT.read_text(encoding="utf-8"))
        strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}
        if strip(old) == strip(data):
            print(f"{OUTPUT.relative_to(ROOT)} is up to date")
            return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(data['events'])} events, through {data['meta']['through']}")


if __name__ == "__main__":
    main()
