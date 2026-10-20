"""Build the Olympic tennis and boxing datasets used by tennis/olympics and boxing/olympics.

Tennis: the medal table of every event at each Games, from the "events" section of
each "Tennis at the YYYY Summer Olympics" page (outdoor and indoor events in 1908
and 1912). Boxing: Wikipedia's list of Olympic medalists in boxing, one table per
weight class, men's and women's, current and discontinued.

Usage:
    python3 scripts/build_olympic_sports.py                 # both, saved pages
    python3 scripts/build_olympic_sports.py tennis          # one sport
    python3 scripts/build_olympic_sports.py --refresh       # re-download the pages
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter

import wikitables as W
from build_football import RAW_DIR, ROOT, slug
from olympic_events import check_athletes, nation_of, parse_by_event, parse_by_games, summarize

CACHE = RAW_DIR / "olympics"
TENNIS_YEARS = [1896, 1900, 1904, 1908, 1912, 1920, 1924, 1988, 1992, 1996, 2000, 2004, 2008, 2012, 2016, 2020, 2024]
BOXING_PAGE = "List of Olympic medalists in boxing"


def page(title: str, refresh: bool, folder: str = "") -> str:
    return W.fetch_raw(title, CACHE / folder / f"{slug(title)}.wiki", refresh, pause=1.5)


def summer_cities() -> dict[int, str]:
    """Host city of each Summer Games, from the Olympic Games dataset."""
    games = json.loads((ROOT / "olympics" / "data" / "olympics.json").read_text(encoding="utf-8"))["games"]
    return {g["year"]: g["city"] for g in games if g["season"] == "Summer"}


# ---------- Tennis ----------

def tennis_name(name: str, section: str) -> str:
    """Event names as one key across Games: 'Men's singles', 'Men's indoor singles'..."""
    name = re.sub(r"\s+", " ", name).strip()
    name = name[0].upper() + name[1:]
    if section == "indoor" and "indoor" not in name.lower():
        name = re.sub(r"(Men's|Women's|Mixed) ", r"\1 indoor ", name)
    return name.replace(" outdoor", "")


def tennis_group(name: str) -> str:
    low = name.lower()
    if "indoor" in low:
        return "Indoor"
    if low.startswith("mixed"):
        return "Mixed doubles"
    return "Doubles" if "doubles" in low else "Singles"


def build_tennis(refresh: bool) -> dict:
    cities = summer_cities()
    events: dict[str, dict] = {}
    for year in TENNIS_YEARS:
        text = page(f"Tennis at the {year} Summer Olympics", refresh, "tennis")
        for section in ("events", "outdoor", "indoor"):
            m = re.search(rf'<section begin="?{section}"?\s*/>(.*?)<section end="?{section}"?\s*/>', text, re.S)
            if not m:
                continue
            grid = W.all_tables("\n" + m.group(1).strip())[0]
            rows = parse_by_games(grid, year, cities.get(year, ""), lambda n: "doubles" in n.lower())
            for raw, result in rows.items():
                name = tennis_name(raw, section)
                gender = "Mixed" if name.startswith("Mixed") else "Women" if name.startswith("Women") else "Men"
                ev = events.setdefault(name, {"key": slug(name), "name": name, "gender": gender, "group": tennis_group(name), "results": []})
                ev["results"].append(result)
    latest = max(TENNIS_YEARS)
    out = []
    order = ["Men's singles", "Men's doubles", "Women's singles", "Women's doubles", "Mixed doubles"]
    for name, ev in sorted(events.items(), key=lambda kv: (kv[0] not in order, order.index(kv[0]) if kv[0] in order else 0, kv[0])):
        ev["results"].sort(key=lambda r: r["year"])
        ev["current"] = ev["results"][-1]["year"] == latest
        out.append(ev)
    return summarize(out, [f"Tennis at the {y} Summer Olympics" for y in (TENNIS_YEARS[0], TENNIS_YEARS[-1])], min_medals=2)


def validate_tennis(data: dict) -> list[str]:
    errors = check_athletes(data, {
        "Venus Williams": (4, 1, 0), "Serena Williams": (4, 0, 0), "Andy Murray": (2, 1, 0), "Rafael Nadal": (2, 0, 0),
        "Reginald Doherty": (3, 0, 1), "Novak Djokovic": (1, 0, 1),
    })
    per_games = Counter(r["year"] for ev in data["events"] for r in ev["results"])
    for year, n in {1988: 4, 1992: 4, 1996: 4, 2000: 4, 2004: 4, 2008: 4, 2012: 5, 2016: 5, 2020: 5, 2024: 5, 1896: 2}.items():
        if per_games[year] != n:
            errors.append(f"tennis {year}: {per_games[year]} events, expected {n}")
    return errors


# ---------- Boxing ----------

LIGHT = ("light flyweight", "flyweight", "bantamweight")
MIDDLE = ("featherweight", "lightweight", "light welterweight", "welterweight")


def boxing_group(name: str) -> str:
    low = name.lower()
    if low in LIGHT:
        return "Flyweight to bantamweight"
    if low in MIDDLE:
        return "Featherweight to welterweight"
    return "Middleweight and up"


def build_boxing(refresh: bool) -> dict:
    text = page(BOXING_PAGE, refresh)
    events = []
    current, gender = True, "Men"
    for m in re.finditer(r"\n(={2,4})\s*([^=\n]+?)\s*\1[ \t]*(?=\n)", text):
        level, heading = len(m.group(1)), W.plain(m.group(2))
        if level == 2:
            if heading.lower().startswith(("multiple", "references", "see also")):
                break
            current = not heading.lower().startswith("discontinued")
            continue
        if level == 3:
            gender = "Women" if heading.lower().startswith("women") else "Men"
            continue
        body = text[m.end():]
        nxt = re.search(r"\n==", body)
        tables = W.all_tables("\n" + (body[:nxt.start()] if nxt else body))
        results = parse_by_event(tables[0]) if tables else []
        if not results:
            continue
        name = heading[0].upper() + heading[1:]
        events.append({
            "key": slug(f"{gender}-{name}"), "name": name, "gender": gender, "group": boxing_group(name),
            "current": current, "results": results,
        })
    return summarize(events, [BOXING_PAGE], min_medals=2)


def validate_boxing(data: dict) -> list[str]:
    errors = check_athletes(data, {"László Papp": (3, 0, 0), "Teófilo Stevenson": (3, 0, 0), "Félix Savón": (3, 0, 0)})
    golds = Counter(nation_of(s) for ev in data["events"] for r in ev["results"] for s in r["gold"])
    if golds["USA"] < 50 or golds["CUB"] < 41:
        errors.append(f"boxing golds look low: USA {golds['USA']}, Cuba {golds['CUB']}")
    # Since 1952 both losing semi-finalists get a bronze.
    short = [f"{ev['key']} {r['year']}" for ev in data["events"] for r in ev["results"] if r["year"] >= 1952 and len(r["bronze"]) != 2]
    if short:
        errors.append(f"events without two bronzes: {short[:8]}")
    if Counter(ev["gender"] for ev in data["events"])["Women"] < 6:
        errors.append("women's events missing")
    return errors


SPORTS = {
    "tennis": (build_tennis, validate_tennis, ROOT / "tennis" / "olympics" / "data" / "tennis-olympics.json"),
    "boxing": (build_boxing, validate_boxing, ROOT / "boxing" / "olympics" / "data" / "boxing-olympics.json"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download the Wikipedia pages")
    parser.add_argument("sport", nargs="*", choices=[*SPORTS, []], help="default: all")
    args = parser.parse_args()
    failed = False
    for key in args.sport or SPORTS:
        builder, validator, out = SPORTS[key]
        data = builder(args.refresh)
        errors = validator(data)
        if errors:
            print(f"{key}: validation failed:\n  " + "\n  ".join(errors), file=sys.stderr)
            failed = True
            continue
        if out.exists():
            old = json.loads(out.read_text(encoding="utf-8"))
            strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}
            if strip(old) == strip(data):
                print(f"{out.relative_to(ROOT)} is up to date")
                continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}: {len(data['events'])} events, through {data['meta']['through']}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
