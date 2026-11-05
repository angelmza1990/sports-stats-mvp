"""Build the winners pages of the individual sports: cycling's Grand Tours, golf's majors, MotoGP and the Dakar Rally.

Every page has the same shape: a list of events (a year, a competition, the winner, his nation and, where the sport
has one, his team, make or constructor), read from Wikipedia (CC BY-SA 4.0) and checked against the totals table
the same page publishes. The front end (assets/champions.js) draws the race, the rankings and every winner.

  cycling/grand-tours   Tour de France, Giro d'Italia and Vuelta a España general classification winners
  golf/majors           the Masters, the U.S. Open, The Open and the PGA Championship
  motorsport/motogp     the premier-class (500cc, MotoGP) world champions and their constructors
  motorsport/dakar      the Dakar Rally winners of the cars, bikes, trucks and quads

Usage:
    python3 scripts/build_champions.py                 # every sport, cached pages
    python3 scripts/build_champions.py cycling golf    # some sports
    python3 scripts/build_champions.py --refresh       # re-download the pages
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

# Codes the shared country table lacks, and the names some flag templates use.
EXTRA_COUNTRIES = {
    "ZAF": ("South Africa", "za"), "SVN": ("Slovenia", "si"), "LTU": ("Lithuania", "lt"), "FIJ": ("Fiji", "fj"),
    "ZIM": ("Zimbabwe", "zw"), "SAU": ("Saudi Arabia", "sa"), "IND": ("India", "in"), "LUX": ("Luxembourg", "lu"),
    "TPE": ("Chinese Taipei", "tw"), "RHO": ("Rhodesia", "zw"), "JER": ("Jersey", "je"), "ETH": ("Ethiopia", "et"), "KEN": ("Kenya", "ke"), "TAN": ("Tanzania", "tz"), "NIR": ("Northern Ireland", "gb-nir"),
}
NAME_CODES = {"french third republic": "FRA", "france": "FRA", "kingdom of italy": "ITA", "italy": "ITA", "belgium": "BEL",
              "luxembourg": "LUX", "spain": "ESP", "francoist spain": "ESP", "switzerland": "SUI", "netherlands": "NED",
              "united states": "USA", "uk": "GBR", "united kingdom": "GBR", "great britain": "GBR", "west germany": "FRG",
              "germany": "GER", "ireland": "IRL", "colombia": "COL", "denmark": "DEN", "australia": "AUS", "slovenia": "SVN",
              "russia": "RUS", "soviet union": "URS", "kenya": "KEN", "ethiopia": "ETH", "japan": "JPN", "korea": "KOR", "south korea": "KOR",
              "republic of china": "TPE", "taiwan": "TPE", "romania": "ROU", "poland": "POL", "east germany": "GDR", "bulgaria": "BUL",
              "sweden": "SWE", "haiti": "HAI", "canada": "CAN", "ukraine": "UKR", "south africa": "ZAF", "finland": "FIN", "rhodesia and nyasaland": "RHO", "rhodesia": "RHO", "kazakhstan": "KAZ", "ecuador": "ECU", "portugal": "POR"}
CODE_FIX = {"IRE": "IRL", "ROM": "ROU", "SLO": "SVN", "LIT": "LTU", "RSA": "ZAF", "UK": "GBR", "DEU": "GER", "CHL": "CHI", "NLD": "NED"}


def country(code: str) -> tuple[str, str | None]:
    return EXTRA_COUNTRIES.get(code) or COUNTRIES.get(code) or (code, None)


def nation(text: str) -> str | None:
    """A country code from a flag template, a {{XXX}} code or a country name in the cell."""
    m = re.search(r"\{\{\s*flag(?:icon|country|u|deco)?\s*\|\s*([^|{}]+?)\s*(?:\|[^{}]*)?\}\}", text, re.I)
    if m:
        named = re.search(r"name\s*=\s*([^|}]+)", m.group(0))
        key = (named.group(1) if named else m.group(1)).strip().lower()
        if key in NAME_CODES:
            return NAME_CODES[key]
    m = re.search(r"\{\{\s*(?:flagathlete|flai)\s*\|(?:\[\[[^\]]*\]\]|\{\{[^{}]*\}\}|[^|{}])*\|\s*([A-Z]{3})\s*(?:\|[^{}]*)?\}\}", text)
    if m:
        return CODE_FIX.get(m.group(1), m.group(1))
    m = re.search(r"\{\{\s*(?:flagathlete|flai)\s*\|(?:\[\[[^\]]*\]\]|[^|{}])*\|\s*([A-Za-z ]+?)\s*(?:\|[^{}]*)?\}\}", text)
    if m and m.group(1).strip().lower() in NAME_CODES:
        return NAME_CODES[m.group(1).strip().lower()]
    if re.search(r"\{\{\s*ROC-TW\s*\}\}", text):
        return "TPE"
    if re.search(r"Korea under Japanese rule", text):
        return "JPN"  # Sohn Kee-chung ran for Japan, as Korea was then under Japanese rule
    m = re.search(r"\{\{\s*(UK)\s*\}\}", text)
    if m:
        return "GBR"
    m = re.search(r"\{\{\s*([A-Z]{3})\d\s*\}\}", text)  # {{GBR2}}
    if m:
        return CODE_FIX.get(m.group(1), m.group(1))
    code = W.flag_code(text)
    if not code:
        m = re.search(r"\{\{\s*([A-Z]{3})\s*\}\}", text)  # a bare {{RUS}} the shared parser doesn't know
        code = m.group(1) if m else None
    return CODE_FIX.get(code, code) if code else None


def year_of(cell: str) -> int | None:
    m = re.search(r"\b(18[5-9]\d|19\d\d|20\d\d)\b", W.plain(cell)) or re.search(r"\b(18[5-9]\d|19\d\d|20\d\d)\b", cell)
    return int(m.group(1)) if m else None


def page(title: str, refresh: bool) -> str:
    return W.fetch_raw(title, RAW_DIR / f"{slug(title)}.wiki", refresh, pause=3.0)


# The same person under another name on the totals pages.
SAME = {"James Anderson": "Jamie Anderson", "William Auchterlonie": "Willie Auchterlonie", "Miguel Indurain": "Miguel Induráin"}


def clean_name(name: str) -> str:
    name = re.sub(r",\s*Jnr$", "", name)
    return re.sub(r"\s*\((?:\d+|cyclist|golfer|motorcyclist|racing driver|rally driver|born \d{4})[^)]*\)$", "", name).strip()


# ---------- Cycling: the Grand Tours ----------

TOURS = [
    ("tour", "Tour de France", "List of Tour de France general classification winners", {"Eddy Merckx": 5, "Bernard Hinault": 5, "Jacques Anquetil": 5, "Miguel Induráin": 5}),
    ("giro", "Giro d'Italia", "List of Giro d'Italia general classification winners", {"Fausto Coppi": 5, "Alfredo Binda": 5, "Eddy Merckx": 5}),
    ("vuelta", "Vuelta a España", "List of Vuelta a España general classification winners", {"Roberto Heras": 4, "Primož Roglič": 4}),
]


def cycling(refresh: bool) -> tuple[list[dict], dict, dict]:
    events, official, notes = [], {}, {}
    for key, label, title, expected in TOURS:
        text = page(title, refresh)
        grid = W.table_with_headers(text, "year", "cyclist", "margin")
        labels = [W.plain(c["text"]).lower() for c in grid[0]]
        col = lambda needle: next(i for i, l in enumerate(labels) if l.startswith(needle))
        year_i, nat_i, rider_i, margin_i, stages_i = col("year"), col("country"), col("cyclist"), col("margin"), col("stage")
        for row in grid[1:]:
            if len(row) <= stages_i or row[rider_i] is row[year_i]:
                continue
            year = year_of(row[year_i]["text"])
            cell = re.sub(r"<s>.*?</s>", "", row[rider_i]["text"], flags=re.S)  # a winner stripped of the title, and who got it
            plain = W.plain(cell)
            if not year or not plain or re.search(r"no winner|not held|cancel|no race|stripped|vacated|\bwar\b|not contested|no tour|^[-–—~]+$", plain, re.I):
                continue
            name = clean_name(W.person(cell) or plain)
            events.append({"year": year, "comp": key, "winner": name, "nation": nation(row[nat_i]["text"]) or nation(cell),
                           "margin": W.plain(row[margin_i]["text"]).strip() or None,
                           "stages": W.number(row[stages_i]["text"])})
        # The page's own count per rider, for validation.
        totals = W.table_with_headers(text, "cyclist", "total", "years")
        official[key] = {clean_name(W.person(r[0]["text"]) or ""): W.number(r[1]["text"]) for r in totals[1:] if len(r) >= 2 and W.number(r[1]["text"])}
        stripped = re.findall(r"(\d{4})[^\n]{0,80}(?:stripped|no winner)", text)
        notes[key] = sorted(set(stripped))
    for key, _, _, expected in TOURS:
        for name, n in expected.items():
            official[key].setdefault(name, n)
    return events, official, notes


# ---------- Golf: the men's majors ----------

MAJORS = [("masters", "Masters Tournament", "Masters"), ("us-open", "U.S. Open", "U.S. Open"),
          ("open", "The Open Championship", "The Open"), ("pga", "PGA Championship", "PGA")]


def golf(refresh: bool) -> tuple[list[dict], dict, dict]:
    text = page("Chronological list of men's major golf champions", refresh)
    grid = W.table_with_headers(text, "year", "the open championship", "u.s. open", "masters")
    labels = [W.plain(c["text"]).lower() for c in grid[0]]
    events = []
    for row in grid[1:]:
        year = year_of(row[0]["text"])
        if not year or len(row) < len(labels):
            continue
        for key, header, _ in MAJORS:
            cell = row[labels.index(header.lower())]["text"]
            if not W.links(cell) or re.search(r"not held|cancel|started in|no championship|world war", W.plain(cell), re.I):
                continue
            name = clean_name(W.person(cell))
            if not name or re.search(r"\d{4}", name):
                continue
            events.append({"year": year, "comp": key, "winner": name, "nation": nation(cell)})
    # The page's count of majors per golfer (the list of winning golfers).
    winners = page("List of men's major championships winning golfers", refresh)
    totals = W.table_with_headers(winners, "golfer", "winning span", "masters", "total")
    labels = [W.plain(c["text"]).lower() for c in totals[0]]
    official = {}
    for r in totals[1:]:
        if len(r) < len(labels):
            continue
        name = clean_name(W.person(r[labels.index("golfer")]["text"]) or "")
        if not name or name.lower() == "totals":
            continue
        for key, _, short in MAJORS:
            n = W.number(r[labels.index(short.lower())]["text"]) or 0
            if n:
                official.setdefault(key, {})[name] = n
    return events, official, {}


# ---------- MotoGP: the premier class ----------

def motogp(refresh: bool) -> tuple[list[dict], dict, dict]:
    text = page("List of 500cc/MotoGP World Riders' Champions", refresh)
    grid = W.table_with_headers(text, "season", "rider", "constructor", "wins", "points")
    labels = [W.plain(c["text"]).lower() for c in grid[0]]
    col = lambda needle: next(i for i, l in enumerate(labels) if l.startswith(needle))
    events = []
    for row in grid[1:]:
        year = year_of(row[col("season")]["text"])
        if not year or len(row) < len(labels):
            continue
        cell = row[col("rider")]["text"]
        events.append({"year": year, "comp": "motogp", "winner": clean_name(W.person(cell)),
                       "nation": nation(row[col("country")]["text"]) or nation(cell),
                       "team": W.plain(row[col("constructor")]["text"]).strip(),
                       "wins": W.number(row[col("wins")]["text"]), "races": W.number(re.sub(r"\{\{efn.*", "", row[col("grands prix")]["text"]))})
    totals = W.table_with_headers(text, "rider", "titles", "seasons")
    official = {"motogp": {clean_name(W.person(r[0]["text"]) or ""): W.number(r[1]["text"]) for r in totals[1:] if len(r) >= 2 and W.number(r[1]["text"])}}
    return events, official, {}


# ---------- The Dakar Rally ----------

# Category tables on the Dakar Rally page, in order: (key, label, first year).
DAKAR = [("cars", "Cars", 1979), ("bikes", "Bikes", 1979), ("trucks", "Trucks", 1980), ("quads", "Quads", 2009)]
# The make of a vehicle, from the name the page gives it.
MAKES = ["Range Rover", "Land Rover", "Mercedes-Benz", "Mercedes", "Mitsubishi", "Peugeot", "Citroën", "Volkswagen", "Toyota",
         "Mini", "Audi", "Porsche", "Renault", "Lada", "Bowler", "Schlesser", "Nissan", "Yamaha", "Honda", "KTM", "BMW", "Cagiva",
         "Husqvarna", "Gas Gas", "GasGas", "Sherco", "Hero", "Kamaz", "KAMAZ", "MAN", "DAF", "Tatra", "Iveco", "Perlini", "Hino", "Mammoet",
         "Sonacome", "Can-Am", "Polaris", "Suzuki", "Ford", "Dacia", "Hummer", "Lada", "Liaz", "LIAZ", "Steyr", "Unimog", "Fiat", "Pinch",
         "Sunhill", "Hummer", "Ilia", "Overdrive", "Century", "Prodrive", "BRX", "Bahrain Raid Xtreme", "Raptor", "Monster"]
MAKE_NAMES = {"Mercedes": "Mercedes-Benz", "KAMAZ": "Kamaz", "GasGas": "Gas Gas", "LIAZ": "Liaz", "Bahrain Raid Xtreme": "Prodrive",
              "BRX": "Prodrive", "Raptor": "Yamaha", "Unimog": "Mercedes-Benz", "Range Rover": "Land Rover"}


def make_of(cell: str) -> str | None:
    text = " ".join([W.plain(cell)] + [t for t, _ in W.links(cell)])
    for m in MAKES:
        if re.search(rf"(?<![\w-]){re.escape(m)}(?![\w-])", text):
            return MAKE_NAMES.get(m, m)
    first = W.plain(cell).split(" ")[0]
    return first or None


def dakar(refresh: bool) -> tuple[list[dict], dict, dict]:
    text = page("Dakar Rally", refresh)
    grids = [g for g in W.all_tables(text) if W.header_labels(g[0])[:2] == ["Year", "1st"]]
    events = []
    for (key, _, first), grid in zip(DAKAR, grids):
        for row in grid[2:] if not re.match(r"\d{4}", W.plain(grid[1][0]["text"])) else grid[1:]:
            year = year_of(row[0]["text"])
            if not year or len(row) < 3 or row[1] is row[0]:
                continue
            cell = re.split(r"<br\s*/?>", row[1]["text"])[0]
            name = W.person(cell)
            if not name or re.search(r"cancel|not held", W.plain(row[1]["text"]), re.I):
                continue
            events.append({"year": year, "comp": key, "winner": clean_name(name), "nation": nation(cell),
                           "team": make_of(row[2]["text"]), "vehicle": W.plain(row[2]["text"]).strip()})
        assert int(min(e["year"] for e in events if e["comp"] == key)) == first, (key, first)
    expected = {"cars": {"Stéphane Peterhansel": 8, "Ari Vatanen": 4}, "bikes": {"Stéphane Peterhansel": 6, "Cyril Despres": 5, "Marc Coma": 5},
                "trucks": {"Vladimir Chagin": 7, "Karel Loprais": 6}, "quads": {"Marcos Patronelli": 3}}
    return events, expected, {}


SPORTS = {
    "cycling": {"dir": "cycling/grand-tours", "build": cycling, "competitions": [{"key": k, "label": l} for k, l, _, _ in TOURS],
                "unit": "wins", "person": "Rider", "team": None},
    "golf": {"dir": "golf/majors", "build": golf, "competitions": [{"key": k, "label": s} for k, _, s in MAJORS],
             "unit": "majors", "person": "Golfer", "team": None},
    "motogp": {"dir": "motorsport/motogp", "build": motogp, "competitions": [{"key": "motogp", "label": "Premier class"}],
               "unit": "titles", "person": "Rider", "team": "Constructor"},
    "dakar": {"dir": "motorsport/dakar", "build": dakar, "competitions": [{"key": k, "label": l} for k, l, _ in DAKAR],
              "unit": "wins", "person": "Winner", "team": "Make"},
}


def build(key: str, refresh: bool) -> tuple[dict, list[str]]:
    cfg = SPORTS[key]
    events, official, notes = cfg["build"](refresh)
    events.sort(key=lambda e: (e["year"], [c["key"] for c in cfg["competitions"]].index(e["comp"])))
    people, nations = {}, set()
    for e in events:
        pid = slug(e["winner"])
        people.setdefault(pid, {"name": e["winner"], "nation": e["nation"]})
        if not people[pid]["nation"]:
            people[pid]["nation"] = e["nation"]
        e["winner"] = pid
    for e in events:  # a flag the page left out on one row, from the same person's other wins
        e["nation"] = e["nation"] or people[e["winner"]]["nation"]
        nations.add(e["nation"])
    errors = []
    for comp, counts in official.items():
        got = Counter(slug(people[e["winner"]]["name"]) for e in events if e["comp"] == comp)
        diff = {n: (got.get(slug(SAME.get(n, n)), 0), want) for n, want in counts.items() if got.get(slug(SAME.get(n, n)), 0) != want}
        if diff:
            errors.append(f"{comp}: wins differ from the page's totals (got, expected): {diff}")
    missing = sorted({people[e["winner"]]["name"] for e in events if not e["nation"]})
    if missing:
        errors.append(f"no nation for {missing}")
    unknown = sorted(c for c in nations if c and country(c)[1] is None and c not in ("URS", "FRG", "TCH", "YUG"))
    if unknown:
        print(f"{key}: countries without a flag: {unknown}", file=sys.stderr)
    data = {
        "meta": {"generated": date.today().isoformat(), "through": events[-1]["year"], "unit": cfg["unit"],
                 "person": cfg["person"], "team": cfg["team"], "notes": notes},
        "competitions": cfg["competitions"],
        "countries": {c: {"name": country(c)[0], "flag": country(c)[1]} for c in sorted(n for n in nations if n)},
        "people": people,
        "events": events,
    }
    return data, errors


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("sport", nargs="*", choices=[*SPORTS, []])
    args = ap.parse_args()
    failed = False
    for key in args.sport or SPORTS:
        data, errors = build(key, args.refresh)
        if errors:
            print(f"{key}: validation failed:\n  " + "\n  ".join(errors), file=sys.stderr)
            failed = True
            continue
        out = ROOT / SPORTS[key]["dir"] / "data" / "champions.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}: {len(data['events'])} winners through {data['meta']['through']}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
