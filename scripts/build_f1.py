"""Build the Formula One dataset used by motorsport/formula-1.

Reads Wikipedia's lists of World Drivers' and Constructors' Champions and of
Grand Prix winners (by driver, constructor and country), and writes one JSON
file for the front end.

Usage:
    python3 scripts/build_f1.py            # use cached pages if present
    python3 scripts/build_f1.py --refresh  # re-download every page
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date

import wikitables as W
from build_football import COUNTRIES, RAW_DIR, ROOT, slug

OUTPUT = ROOT / "motorsport" / "formula-1" / "data" / "formula-1.json"
PAGES = {
    "drivers": "List of Formula One World Drivers' Champions",
    "constructors": "List of Formula One World Constructors' Champions",
    "wins": "List of Formula One Grand Prix winners",
    "constructorWins": "List of Formula One Grand Prix winners (constructors)",
    "circuits": "List of Formula One circuits",
}
# Read rendered: their numbers for active drivers come from templates ({{F1stat|VER|wins}}) that the wikitext doesn't expand.
RECORD_PAGES = {"Drivers": "List of Formula One driver records", "Constructors": "List of Formula One constructor records"}
# (group, the table's heading on the page, the label shown)
RECORDS = [
    ("Drivers", "Total wins", "Wins"),
    ("Drivers", "Percentage wins (at least 15 starts)", "Win rate"),
    ("Drivers", "Total pole positions", "Pole positions"),
    ("Drivers", "Total podium finishes", "Podiums"),
    ("Drivers", "Total fastest laps", "Fastest laps"),
    ("Drivers", "Total starts", "Starts"),
    ("Drivers", "Total career points", "Points"),
    ("Drivers", "Total laps led", "Laps led"),
    ("Drivers", "Most wins in a season", "Wins in a season"),
    ("Drivers", "Most consecutive wins", "Wins in a row"),
    ("Drivers", "Most consecutive podium finishes", "Podiums in a row"),
    ("Drivers", "Most consecutive pole positions", "Poles in a row"),
    ("Drivers", "Most wins at the same Grand Prix", "Wins at one Grand Prix"),
    ("Drivers", "Youngest winners", "Youngest winners"),
    ("Drivers", "Oldest winners", "Oldest winners"),
    ("Drivers", "Wins from farthest back on the starting grid", "Wins from farthest back"),
    ("Drivers", "Most wins without a World Championship", "Wins without a title"),
    ("Drivers", "Most races without a win", "Races without a win"),
    ("Drivers", "Pole, win, fastest lap, and led every lap", "Grand slams"),
    ("Constructors", "Total wins", "Wins"),
    ("Constructors", "Total pole positions", "Pole positions"),
    ("Constructors", "Total 1–2 finishes", "One-two finishes"),
    ("Constructors", "Total podiums", "Podiums"),
    ("Constructors", "Most wins in a season", "Wins in a season"),
    ("Constructors", "Highest percentage of wins in a season", "Best win rate in a season"),
    ("Constructors", "Most consecutive wins", "Wins in a row"),
    ("Constructors", "Most races started without a win", "Races without a win"),
]
RECORD_ROWS = 10

# The F1 pages mix IOC, ISO and short codes; fold them into one set.
CODE_ALIASES = {"UK": "GBR", "DEU": "GER", "CHE": "SUI", "ZAF": "RSA", "NLD": "NED", "MCO": "MON", "JPN": "JPN", "IRL": "IRL",
                "PRT": "POR", "MYS": "MAS", "SAU": "KSA", "SGP": "SIN"}
EXTRA_COUNTRIES = {"MON": ("Monaco", "mc"), "RSA": ("South Africa", "za"), "RHO": ("Rhodesia", None), "THA": ("Thailand", "th"),
                   "MAS": ("Malaysia", "my"), "KSA": ("Saudi Arabia", "sa"), "SIN": ("Singapore", "sg"), "AZE": ("Azerbaijan", "az"),
                   "BHR": ("Bahrain", "bh"), "IND": ("India", "in"), "POR": ("Portugal", "pt"), "QAT": ("Qatar", "qa"),
                   "UAE": ("United Arab Emirates", "ae"), "CHN": ("China", "cn"), "KOR": ("South Korea", "kr"), "TUR": ("Turkey", "tr"),
                   "RUS": ("Russia", "ru"), "HUN": ("Hungary", "hu"), "MAR": ("Morocco", "ma"), "SWE": ("Sweden", "se")}

HISTORY_THROUGH = 2025
DRIVER_TITLES = {"Lewis Hamilton": 7, "Michael Schumacher": 7, "Juan Manuel Fangio": 5, "Alain Prost": 4,
                 "Sebastian Vettel": 4, "Max Verstappen": 4}
CONSTRUCTOR_TITLES = {"Ferrari": 16, "McLaren": 10, "Williams": 9, "Mercedes": 8, "Lotus": 7, "Red Bull": 6}


def code(text: str) -> str | None:
    m = re.search(r"\{\{\s*(?:flagicon\s*\|\s*)?([A-Z]{2,3})\s*(?:\|[^{}]*)?\}\}", text)
    if not m:
        c = W.flag_code(text)
    else:
        c = m.group(1)
    return CODE_ALIASES.get(c, c) if c else None


def country(c: str) -> dict:
    name, flag = EXTRA_COUNTRIES.get(c) or COUNTRIES.get(c, (c, None))
    return {"name": name, "flag": flag}


def constructor_name(cell: str) -> str | None:
    found = W.links(cell)
    label = found[0][1] if found else W.plain(cell)
    label = re.sub(r"[*†‡]", "", W.plain(label)).strip()
    # "Team Lotus" / "Lotus-Climax" style labels fold into the constructor's common name.
    return {"Team Lotus": "Lotus", "Red Bull Racing": "Red Bull", "Scuderia Ferrari": "Ferrari", "Brawn GP": "Brawn"}.get(label, label) or None


def name_code(name: str | None) -> str | None:
    """A country from a flag file's name ("United Kingdom", "Canada (Pantone)") as the site's code."""
    if not name:
        return None
    name = re.sub(r"\s*\(.*\)$", "", name).strip()
    fixed = {"United Kingdom": "GBR", "United States": "USA", "Netherlands": "NED", "Germany": "GER", "West Germany": "GER",
             "Rhodesia": "RHO", "Monaco": "MON", "South Africa": "RSA", "Thailand": "THA", "Russia": "RUS"}
    if name in fixed:
        return fixed[name]
    return next((c for c, (n, _) in {**COUNTRIES, **EXTRA_COUNTRIES}.items() if n == name), None)


def parse_records(refresh: bool) -> list[dict]:
    tables = {group: W.html_tables(W.fetch_html(title, RAW_DIR / f"{slug(title)}.html", refresh)) for group, title in RECORD_PAGES.items()}
    out = []
    for group, heading, label in RECORDS:
        found = [rows for h, rows in tables[group] if h == heading]
        if not found:
            print(f"warning: no '{heading}' table on the {group.lower()} records page", file=sys.stderr)
            continue
        rows = found[0]
        head = [c["text"] for c in rows[0]]
        body = []
        for r in rows[1:]:
            cells = [c["text"] for c in r]
            if len(cells) != len(head) or not any(cells[1:]):
                continue
            # The rank column repeats for ties; the first cell with a flag is the driver (or constructor).
            flagged = next((c for c in r if c["flag"]), None)
            body.append({"cells": cells, "nation": name_code(flagged["flag"]) if flagged else None})
            if len(body) >= RECORD_ROWS:
                break
        if body:
            out.append({"group": group, "label": label, "heading": heading, "columns": head, "rows": body})
    return out


def parse_circuits(text: str) -> list[dict]:
    out = []
    for row in W.table_with_headers(text, "circuit", "type", "location", "country", "grands prix held"):
        if len(row) < 11 or not W.links(row[0]["text"]):
            continue
        n = W.number(row[10]["text"])
        if not n:
            continue
        out.append({"name": W.plain(row[0]["text"]).strip(" *"), "type": W.plain(row[2]["text"]), "location": W.plain(row[4]["text"]),
                    "nation": code(row[5]["text"]) or name_code(W.plain(row[5]["text"])),
                    "grandsPrix": [W.plain(x).strip(" ,") for x in re.split(r"<br\s*/?>|,\s*(?=\[\[)", row[8]["text"]) if W.plain(x).strip(" ,")],
                    "seasons": W.plain(row[9]["text"]), "races": n})
    return sorted(out, key=lambda c: -c["races"])


def fetch(key: str, refresh: bool) -> str:
    return W.fetch_raw(PAGES[key], RAW_DIR / f"{slug(PAGES[key])}.wiki", refresh)


def build(refresh: bool) -> dict:
    drivers_page, constructors_page = fetch("drivers", refresh), fetch("constructors", refresh)
    wins_page, cwins_page = fetch("wins", refresh), fetch("constructorWins", refresh)

    drivers, constructors = {}, {}

    def driver(cell: str) -> str | None:
        name = W.person(cell)
        if not name:
            return None
        name = re.sub(r"[*†‡]", "", name).strip()
        did = slug(name)
        drivers.setdefault(did, {"name": name, "nation": code(cell)})
        if not drivers[did]["nation"]:
            drivers[did]["nation"] = code(cell)
        return did

    def constructor(cell: str, nation: str | None = None) -> str | None:
        name = constructor_name(cell)
        if not name:
            return None
        cid = slug(name)
        constructors.setdefault(cid, {"name": name, "nation": nation})
        if nation and not constructors[cid]["nation"]:
            constructors[cid]["nation"] = nation
        return cid

    champions = []
    for row in W.table_with_headers(drivers_page, "season", "driver", "age", "constructor"):
        year = W.number(row[0]["text"]) if row else None
        if not year or year < 1950 or len(row) < 11 or not W.person(row[1]["text"]):
            continue
        cid = constructor(row[3]["text"], code(row[3]["text"]))
        if champions and champions[-1]["season"] == year:
            # 1954: Fangio won the title driving for Maserati and then Mercedes.
            if cid not in champions[-1]["constructors"]:
                champions[-1]["constructors"].append(cid)
            continue
        champions.append({
            "season": year, "driver": driver(row[1]["text"]), "age": W.number(row[2]["text"]),
            "constructors": [cid], "engine": W.plain(row[4]["text"]),
            "poles": W.number(row[6]["text"]), "wins": W.number(row[7]["text"]), "podiums": W.number(row[8]["text"]),
            "points": W.number(row[10]["text"]),
            # How the title was won: the round it was clinched, rounds left, and the margin over the runner-up.
            **({"clinched": W.plain(row[12]["text"]), "roundsLeft": W.number(row[13]["text"]),
                "margin": float(m.group(0)) if (m := re.search(r"\d+(?:\.\d+)?", W.plain(row[14]["text"]))) else None,
                "marginPct": float(m.group(0)) if (m := re.search(r"\d+(?:\.\d+)?", W.plain(row[15]["text"]))) else None}
               if len(row) >= 16 else {}),
        })

    constructor_champions = []
    for row in W.table_with_headers(constructors_page, "season", "constructor", "tyre", "drivers"):
        year = W.number(row[0]["text"]) if row else None
        if not year or year < 1958 or len(row) < 7 or not constructor_name(row[1]["text"]):
            continue
        constructor_champions.append({
            "season": year, "constructor": constructor(row[1]["text"]), "engine": W.plain(row[2]["text"]),
            "drivers": [W.person(part) for part in re.split(r"<br\s*/?>", row[4]["text"]) if W.person(part)],
            "wins": W.number(row[6]["text"]),
        })

    driver_wins = []
    for row in W.table_with_headers(wins_page, "rank", "country", "driver", "wins", "first win"):
        if len(row) < 7 or W.number(row[3]["text"]) is None:
            continue
        did = driver(row[2]["text"])
        if not drivers[did]["nation"]:
            drivers[did]["nation"] = code(row[1]["text"])
        driver_wins.append({"driver": did, "wins": W.number(row[3]["text"]), "active": W.plain(row[4]["text"]),
                            "first": W.plain(row[5]["text"]), "last": W.plain(row[6]["text"])})

    country_wins = []
    for row in W.table_with_headers(wins_page, "rank", "country", "wins", "driver(s)"):
        c = code(row[1]["text"]) if len(row) > 3 else None
        if not c or W.number(row[2]["text"]) is None:
            continue
        country_wins.append({"nation": c, "wins": W.number(row[2]["text"]), "drivers": W.number(row[4]["text"]) if len(row) > 4 else None})

    constructor_wins = []
    for row in W.table_with_headers(cwins_page, "rank", "constructor", "licensed", "wins"):
        if len(row) < 7 or W.number(row[3]["text"]) is None:
            continue
        cid = constructor(row[1]["text"], code(row[2]["text"]))
        constructor_wins.append({"constructor": cid, "wins": W.number(row[3]["text"]), "active": W.plain(row[4]["text"]),
                                 "first": W.plain(row[5]["text"]), "last": W.plain(row[6]["text"])})

    records = parse_records(refresh)
    circuits = parse_circuits(fetch("circuits", refresh))
    codes = {d["nation"] for d in drivers.values()} | {c["nation"] for c in constructors.values()} | {c["nation"] for c in country_wins}
    codes |= {r["nation"] for rec in records for r in rec["rows"]} | {c["nation"] for c in circuits}
    codes.discard(None)
    return {
        "meta": {
            "generated": date.today().isoformat(),
            "through": str(champions[-1]["season"]),
            "sources": [f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}" for t in [*PAGES.values(), *RECORD_PAGES.values()]],
        },
        "countries": {c: country(c) for c in sorted(codes)},
        "drivers": drivers,
        "constructors": constructors,
        "champions": champions,
        "constructorChampions": constructor_champions,
        "driverWins": driver_wins,
        "constructorWins": constructor_wins,
        "countryWins": country_wins,
        "records": records,
        "circuits": circuits,
    }


def validate(data: dict) -> list[str]:
    errors = []
    seasons = [c["season"] for c in data["champions"]]
    if seasons != list(range(1950, seasons[-1] + 1)) or seasons[-1] < HISTORY_THROUGH:
        errors.append("drivers' champions are not one per season since 1950")
    cseasons = [c["season"] for c in data["constructorChampions"]]
    if cseasons != list(range(1958, cseasons[-1] + 1)):
        errors.append("constructors' champions are not one per season since 1958")
    name = lambda d: data["drivers"][d]["name"]
    titles = Counter(name(c["driver"]) for c in data["champions"] if c["season"] <= HISTORY_THROUGH)
    for n, k in DRIVER_TITLES.items():
        if titles[n] != k:
            errors.append(f"{n}: {titles[n]} titles, expected {k}")
    ctitles = Counter(data["constructors"][c["constructor"]]["name"] for c in data["constructorChampions"] if c["season"] <= HISTORY_THROUGH)
    for n, k in CONSTRUCTOR_TITLES.items():
        if ctitles[n] != k:
            errors.append(f"{n}: {ctitles[n]} constructors' titles, expected {k}")
    for c in data["champions"]:
        if not data["drivers"][c["driver"]]["nation"] or not all(c["constructors"]):
            errors.append(f"{c['season']}: missing nationality or constructor")
    if len(data["records"]) < len(RECORDS) - 3:
        errors.append(f"only {len(data['records'])} of {len(RECORDS)} record tables found")
    if len(data["circuits"]) < 60 or sum(c["races"] for c in data["circuits"]) < 1000:
        errors.append("circuits table looks incomplete")
    if sum(1 for c in data["champions"] if c.get("margin") is not None) < len(data["champions"]) - 2:
        errors.append("title margins missing")
    if len(data["driverWins"]) < 100 or len(data["constructorWins"]) < 30:
        errors.append("wins tables look incomplete")
    return errors


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
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(data['champions'])} seasons, through {data['meta']['through']}")


if __name__ == "__main__":
    main()
