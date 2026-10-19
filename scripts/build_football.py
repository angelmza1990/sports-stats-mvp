"""Build the Copa Libertadores and UEFA Champions League datasets used by football/.

Reads Wikipedia's lists of finals, all-time club tables, all-time top scorers
and most-appearance tables, maps clubs to crests (data/football/clubs.json)
and writes one JSON file per competition.

Usage:
    python3 scripts/build_football.py            # use cached pages if present
    python3 scripts/build_football.py --refresh  # re-download every page
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

import wikitables as W

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "wikipedia"
CLUBS = ROOT / "data" / "football" / "clubs.json"

# Country code -> (name, flagcdn code or None).
COUNTRIES = {
    "ARG": ("Argentina", "ar"), "BRA": ("Brazil", "br"), "URU": ("Uruguay", "uy"), "PAR": ("Paraguay", "py"),
    "CHI": ("Chile", "cl"), "COL": ("Colombia", "co"), "ECU": ("Ecuador", "ec"), "PER": ("Peru", "pe"),
    "BOL": ("Bolivia", "bo"), "VEN": ("Venezuela", "ve"), "MEX": ("Mexico", "mx"),
    "ESP": ("Spain", "es"), "ITA": ("Italy", "it"), "ENG": ("England", "gb-eng"), "GER": ("Germany", "de"),
    "FRG": ("West Germany", "de"), "NED": ("Netherlands", "nl"), "POR": ("Portugal", "pt"), "FRA": ("France", "fr"),
    "SCO": ("Scotland", "gb-sct"), "WAL": ("Wales", "gb-wls"), "NIR": ("Northern Ireland", None),
    "IRL": ("Ireland", "ie"), "ROU": ("Romania", "ro"), "YUG": ("Yugoslavia", None), "SRB": ("Serbia", "rs"),
    "BEL": ("Belgium", "be"), "GRE": ("Greece", "gr"), "SWE": ("Sweden", "se"), "TUR": ("Turkey", "tr"),
    "UKR": ("Ukraine", "ua"), "CRO": ("Croatia", "hr"), "POL": ("Poland", "pl"), "DEN": ("Denmark", "dk"),
    "NOR": ("Norway", "no"), "SUI": ("Switzerland", "ch"), "AUT": ("Austria", "at"), "CZE": ("Czech Republic", "cz"),
    "TCH": ("Czechoslovakia", "cz"), "RUS": ("Russia", "ru"), "URS": ("Soviet Union", None), "HUN": ("Hungary", "hu"),
    "BUL": ("Bulgaria", "bg"), "GHA": ("Ghana", "gh"), "CMR": ("Cameroon", "cm"), "CIV": ("Ivory Coast", "ci"),
    "EGY": ("Egypt", "eg"), "SEN": ("Senegal", "sn"), "NGA": ("Nigeria", "ng"), "USA": ("United States", "us"),
    "SVN": ("Slovenia", "si"), "SVK": ("Slovakia", "sk"), "BIH": ("Bosnia and Herzegovina", "ba"),
    "GEO": ("Georgia", "ge"), "FIN": ("Finland", "fi"), "ISR": ("Israel", "il"), "ALG": ("Algeria", "dz"),
    "MAR": ("Morocco", "ma"), "GAB": ("Gabon", "ga"), "GUI": ("Guinea", "gn"), "MLI": ("Mali", "ml"),
    "TOG": ("Togo", "tg"), "CRC": ("Costa Rica", "cr"), "JPN": ("Japan", "jp"), "KOR": ("South Korea", "kr"),
    "AUS": ("Australia", "au"), "CAN": ("Canada", "ca"), "ALB": ("Albania", "al"), "MNE": ("Montenegro", "me"),
    "ARM": ("Armenia", "am"), "BLR": ("Belarus", "by"), "GDR": ("East Germany", None), "COD": ("DR Congo", "cd"),
    "CYP": ("Cyprus", "cy"), "KAZ": ("Kazakhstan", "kz"), "ISL": ("Iceland", "is"), "HON": ("Honduras", "hn"),
    "PAN": ("Panama", "pa"), "JAM": ("Jamaica", "jm"), "MKD": ("North Macedonia", "mk"), "KOS": ("Kosovo", "xk"),
    "KSA": ("Saudi Arabia", "sa"), "UAE": ("United Arab Emirates", "ae"), "QAT": ("Qatar", "qa"), "TUN": ("Tunisia", "tn"),
    "NZL": ("New Zealand", "nz"), "CHN": ("China", "cn"), "IRN": ("Iran", "ir"),
}

CONFEDERATIONS = {
    "CONMEBOL": {"ARG", "BRA", "URU", "PAR", "CHI", "COL", "ECU", "PER", "BOL", "VEN"},
    "CONCACAF": {"MEX", "CRC", "USA", "HON", "PAN", "JAM", "CAN", "SLV", "GUA", "TRI"},
    "AFC": {"JPN", "KOR", "KSA", "UAE", "QAT", "CHN", "IRN", "AUS"},
    "CAF": {"EGY", "MAR", "COD", "TUN", "RSA", "ALG", "NGA", "CMR", "GHA", "CIV", "SEN"},
    "OFC": {"NZL"},
}


def confederation(code: str | None) -> str:
    for name, codes in CONFEDERATIONS.items():
        if code in codes:
            return name
    return "UEFA"

LEG_NOTES = {"CEDFF2": "penalties", "FBCEB1": "extra time", "D0F0C0": "playoff", "D1F7A5": "replay"}

COMPETITIONS = {
    "copa-libertadores": {
        "name": "Copa Libertadores",
        "output": ROOT / "football" / "copa-libertadores" / "data" / "copa-libertadores.json",
        "finals": ("List of Copa Libertadores finals", r"==\s*List of finals\s*==", 1),
        "alltime": ("Historical table of the Copa Libertadores", r"==\s*Ranking\s*==", 0,
                    {"club": 1, "country": 2, "part": 3, "pld": 5, "w": 6, "d": 7, "l": 8, "gf": 9, "ga": 10, "pts": 12}),
        "scorers": ("List of Copa Libertadores top scorers", r"==\s*All-time top scorers\s*==", 0,
                    {"nation": 1, "player": 2, "goals": 3, "apps": 4, "clubs": 7}),
        "appearances": ("Copa Libertadores records and statistics", r"===\s*Appearances\s*===", 0,
                        {"nation": 1, "player": 2, "apps": 3, "goals": 4, "from": 5, "to": 6, "clubs": 7}),
        "season_year": lambda s: int(s[:4]),
        # Titles through the 2025 final, frozen; later seasons may only add to them.
        "history_through": 2025,
        "history": {
            "Independiente": 7, "Boca Juniors": 6, "Peñarol": 5, "River Plate": 4, "Estudiantes": 4, "Flamengo": 4,
            "Olimpia": 3, "Nacional": 3, "São Paulo": 3, "Grêmio": 3, "Santos": 3, "Palmeiras": 3, "Cruzeiro": 2,
            "Internacional": 2, "Atlético Nacional": 2, "Racing": 1, "Argentinos Juniors": 1, "Vélez Sarsfield": 1,
            "San Lorenzo": 1, "Colo-Colo": 1, "Once Caldas": 1, "LDU Quito": 1, "Corinthians": 1,
            "Atlético Mineiro": 1, "Vasco da Gama": 1, "Fluminense": 1, "Botafogo": 1,
        },
        "pointsRule": "3 points per win, 1 per draw",
        "notes": [
            "All-time club records come from Wikipedia's historical table and include every stage of the competition.",
        ],
    },
    "champions-league": {
        "name": "UEFA Champions League",
        "output": ROOT / "football" / "champions-league" / "data" / "champions-league.json",
        "finals": ("List of European Cup and UEFA Champions League finals", r"==\s*List of finals\s*==", 1),
        "alltime": ("European Cup and UEFA Champions League records and statistics", r"===\s*All-time points table\s*===", 0,
                    {"club": 1, "country": 1, "part": 2, "pld": 3, "w": 4, "d": 5, "l": 6, "gf": 7, "ga": 8, "pts": 10}),
        "scorers": ("List of UEFA Champions League top scorers", r"==\s*All-time top scorers\s*==", 0,
                    {"nation": 1, "player": 1, "goals": 2, "apps": 3, "years": 5, "clubs": 6}),
        "appearances": ("List of footballers with 100 or more UEFA Champions League appearances", r"==\s*Players\s*==", 0,
                        {"player": 1, "nation": 2, "apps": 3, "years": 4, "clubs": 5}),
        "season_year": lambda s: int(s[:4]) + 1,  # "1955–56" ends in 1956
        "history_through": 2026,
        "history": {
            "Real Madrid": 15, "Milan": 7, "Bayern Munich": 6, "Liverpool": 6, "Barcelona": 5, "Ajax": 4,
            "Inter Milan": 3, "Manchester United": 3, "Juventus": 2, "Benfica": 2, "Nottingham Forest": 2,
            "Porto": 2, "Chelsea": 2, "Paris Saint-Germain": 2, "Celtic": 1, "Hamburger SV": 1,
            "Steaua București": 1, "Marseille": 1, "Borussia Dortmund": 1, "Manchester City": 1, "Feyenoord": 1,
            "Aston Villa": 1, "PSV Eindhoven": 1, "Red Star Belgrade": 1,
        },
        "pointsRule": "2 points per win, 1 per draw; ties won on penalties count as draws",
        "notes": [
            "Includes the European Cup (1955–1992). Seasons are labelled by the year of the final.",
            "All-time club records list Wikipedia's top 25, including qualifying rounds.",
            "Player records exclude qualifying rounds.",
        ],
    },
}


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


class ClubIndex:
    """Resolves Wikipedia links to curated clubs (crest + country)."""

    def __init__(self) -> None:
        self.clubs = {c["id"]: c for c in json.loads(CLUBS.read_text(encoding="utf-8"))["clubs"]}
        self.alias = {}
        for c in self.clubs.values():
            for a in c["aliases"]:
                self.alias.setdefault(a.lower(), c["id"])
        self.unmapped: dict[str, str] = {}
        self.used: set[str] = set()

    def resolve(self, cell: str, country: str | None) -> str | None:
        found = W.links(cell)
        if not found:
            return None
        target, text = found[0]
        cid = self.alias.get(target.lower()) or self.alias.get(text.lower())
        if not cid:
            cid = slug(target)  # the linked article identifies the club even when labels differ
            if cid not in self.clubs:
                self.clubs[cid] = {"id": cid, "name": text, "country": country, "espn": None, "aliases": []}
                self.unmapped[cid] = f"{text} ({target})"
        self.used.add(cid)
        return cid


def table(cfg: tuple, refresh: bool) -> list[list[dict]]:
    title, anchor, nth = cfg[:3]
    text = W.fetch_raw(title, RAW_DIR / f"{slug(title)}.wiki", refresh)
    return W.parse_table(W.find_table(text, anchor, nth))


def cell(row: list[dict], i: int) -> str:
    return row[i]["text"] if i < len(row) else ""


def parse_finals(rows: list[list[dict]], comp: dict, clubs: ClubIndex) -> list[dict]:
    seasons: dict[str, dict] = {}
    for row in rows:
        if len(row) < 6:
            continue
        season = W.plain(cell(row, 0))
        if not re.match(r"^\d{4}", season):
            continue
        champion_cell, runner_cell = cell(row, 2), cell(row, 4)
        if not W.links(champion_cell):
            continue  # upcoming final
        c_country, r_country = W.flag_code(cell(row, 1)), W.flag_code(cell(row, 5))
        score_attrs = row[3]["attrs"].upper()
        note = next((v for k, v in LEG_NOTES.items() if k in score_attrs), None)
        score = re.sub(r"[*†‡&]", "", W.plain(cell(row, 3))).strip()
        leg = {"score": score, **({"note": note} if note else {})}
        if season not in seasons:
            seasons[season] = {
                "season": season,
                "year": comp["season_year"](season),
                "champion": clubs.resolve(champion_cell, c_country),
                "championCountry": c_country,
                "runnerUp": clubs.resolve(runner_cell, r_country),
                "runnerUpCountry": r_country,
                "legs": [leg],
            }
        else:
            seasons[season]["legs"].append(leg)
    return sorted(seasons.values(), key=lambda s: s["year"])


def parse_alltime(rows: list[list[dict]], cols: dict, clubs: ClubIndex) -> list[dict]:
    out = []
    for row in rows:
        if row[0]["header"] or len(row) <= max(cols.values()) or W.number(cell(row, cols["pld"])) is None:
            continue
        country = W.flag_code(cell(row, cols["country"]))
        out.append({
            "club": clubs.resolve(cell(row, cols["club"]), country),
            "country": country,
            **{k: W.number(cell(row, cols[k])) for k in ("part", "pld", "w", "d", "l", "gf", "ga", "pts")},
        })
    return out


def parse_players(rows: list[list[dict]], cols: dict) -> list[dict]:
    out = []
    for row in rows:
        if row[0]["header"] and not W.links(cell(row, cols["player"])):
            continue
        found = W.links(cell(row, cols["player"]))
        if not found or len(row) <= max(cols.values()):
            continue
        entry = {
            "player": re.sub(r"\s*\([^)]*\)$", "", found[0][0]) if found[0][1] != found[0][0] and "(" in found[0][0] else found[0][1],
            "nation": W.flag_code(cell(row, cols["nation"])),
            "clubs": [text for _, text in W.links(cell(row, cols["clubs"]))],
        }
        for key in ("goals", "apps"):
            if key in cols:
                entry[key] = W.number(cell(row, cols[key]))
        if "years" in cols:
            entry["years"] = W.plain(cell(row, cols["years"]))
        elif "from" in cols:
            entry["years"] = f"{W.plain(cell(row, cols['from']))}–{W.plain(cell(row, cols['to']))}"
        out.append(entry)
    return out


def build(key: str, refresh: bool) -> dict:
    comp = COMPETITIONS[key]
    clubs = ClubIndex()
    finals = parse_finals(table(comp["finals"], refresh), comp, clubs)
    alltime = parse_alltime(table(comp["alltime"], refresh), comp["alltime"][3], clubs)
    scorers = parse_players(table(comp["scorers"], refresh), comp["scorers"][3])
    appearances = parse_players(table(comp["appearances"], refresh), comp["appearances"][3])

    # Keep the clubs that lead any all-time metric, plus every finalist.
    keep = set()
    for metric, n in (("w", 20), ("gf", 20), ("part", 20), ("pld", 20), ("pts", 30)):
        keep |= {r["club"] for r in sorted(alltime, key=lambda r: -(r[metric] or 0))[:n]}
    alltime = [r for r in alltime if r["club"] in keep]
    used = {f["champion"] for f in finals} | {f["runnerUp"] for f in finals} | keep

    codes = {f["championCountry"] for f in finals} | {f["runnerUpCountry"] for f in finals}
    codes |= {r["country"] for r in alltime} | {p["nation"] for p in scorers + appearances}
    codes |= {clubs.clubs[c]["country"] for c in used}
    codes.discard(None)

    unmapped = sorted(label for cid, label in clubs.unmapped.items() if cid in used)
    if unmapped:
        print(f"{key}: clubs shown without a crest mapping (add them to {CLUBS.name}): {unmapped}", file=sys.stderr)

    return {
        "meta": {
            "generated": date.today().isoformat(),
            "competition": comp["name"],
            "through": finals[-1]["season"],
            "sources": [f"https://en.wikipedia.org/wiki/{t[0].replace(' ', '_')}" for t in
                        (comp["finals"], comp["alltime"], comp["scorers"], comp["appearances"])],
            "notes": comp["notes"],
            "pointsRule": comp["pointsRule"],
        },
        "countries": {c: {"name": COUNTRIES[c][0], "flag": COUNTRIES[c][1]} if c in COUNTRIES else {"name": c, "flag": None}
                      for c in sorted(codes)},
        "clubs": {c: {"name": clubs.clubs[c]["name"], "country": clubs.clubs[c]["country"], "crest": clubs.clubs[c]["espn"]}
                  for c in sorted(used)},
        "finals": finals,
        "alltime": alltime,
        "scorers": scorers,
        "appearances": appearances,
    }


def validate(key: str, data: dict) -> list[str]:
    comp = COMPETITIONS[key]
    errors = []
    years = [f["year"] for f in data["finals"]]
    if years != list(range(years[0], years[-1] + 1)):
        errors.append("finals are not one per consecutive season")
    names = {cid: c["name"] for cid, c in data["clubs"].items()}
    history = Counter(names[f["champion"]] for f in data["finals"] if f["year"] <= comp["history_through"])
    if history != Counter(comp["history"]):
        diff = {k: (history.get(k, 0), comp["history"].get(k, 0)) for k in set(history) | set(comp["history"])
                if history.get(k, 0) != comp["history"].get(k, 0)}
        errors.append(f"titles through {comp['history_through']} differ (got, expected): {diff}")
    for f in data["finals"]:
        if not f["champion"] or not f["runnerUp"] or f["champion"] == f["runnerUp"]:
            errors.append(f"bad final {f['season']}")
        if not f["championCountry"] or not f["runnerUpCountry"]:
            errors.append(f"missing country in final {f['season']}")
    if len(data["alltime"]) < 20:
        errors.append(f"all-time table too short ({len(data['alltime'])} clubs)")
    for r in data["alltime"]:
        if r["pts"] is None or r["w"] is None:
            errors.append(f"all-time row without points: {r}")
    for label in ("scorers", "appearances"):
        if len(data[label]) < 10 or any(p.get("goals" if label == "scorers" else "apps") is None for p in data[label]):
            errors.append(f"{label} table incomplete")
    return errors


# ---------- World club champions (Intercontinental Cup + Club World Cup + FIFA Intercontinental Cup) ----------

WORLD_PAGE = "List of world champion football clubs"
WORLD_COMPETITIONS = [
    # key, label, anchor, table index after anchor, columns
    ("IC", "Intercontinental Cup", r"===\s*Intercontinental Cup \(1960", 1, {"year": 0, "champion": 1, "score": 2, "runnerUp": 3}),
    ("CWC", "FIFA Club World Cup", r"===\s*FIFA Club World Cup \(2000", 1, {"year": 1, "champion": 3, "score": 4, "runnerUp": 5}),
    ("FIC", "FIFA Intercontinental Cup", r"===\s*FIFA Intercontinental Cup \(2024", 0,
     {"year": 0, "championCountry": 1, "champion": 2, "score": 3, "runnerUp": 4, "runnerUpCountry": 5}),
]
# Month each final was played, to order finals within a year (most were in December).
WORLD_MONTHS = {("CWC", 2000): 1, ("CWC", 2021): 2, ("CWC", 2025): 7}
WORLD_HISTORY_THROUGH = 2025
WORLD_HISTORY = {
    "Real Madrid": 9, "Milan": 4, "Bayern Munich": 4, "Barcelona": 3, "Boca Juniors": 3, "Peñarol": 3, "Nacional": 3,
    "Inter Milan": 3, "São Paulo": 3, "Corinthians": 2, "Juventus": 2, "Ajax": 2, "Porto": 2, "Independiente": 2,
    "Santos": 2, "Manchester United": 2, "Chelsea": 2, "Liverpool": 1, "Manchester City": 1, "Paris Saint-Germain": 1,
    "Internacional": 1, "Grêmio": 1, "Flamengo": 1, "Vélez Sarsfield": 1, "River Plate": 1, "Racing": 1, "Estudiantes": 1,
    "Olimpia": 1, "Feyenoord": 1, "Atlético Madrid": 1, "Borussia Dortmund": 1, "Red Star Belgrade": 1,
}
OUTPUTS = {
    "world-club-champions": ROOT / "football" / "world-club-champions" / "data" / "world-club-champions.json",
    "argentine-primera": ROOT / "football" / "argentine-primera" / "data" / "argentine-primera.json",
}


def first_score(text: str) -> str:
    m = re.search(r"\d+\s*[–-]\s*\d+", W.strip_refs(text))
    return m.group(0).replace("-", "–").replace(" ", "") if m else W.plain(text)


def build_world(key: str, refresh: bool) -> dict:
    text = W.fetch_raw(WORLD_PAGE, RAW_DIR / f"{slug(WORLD_PAGE)}.wiki", refresh)
    clubs = ClubIndex()
    finals: dict[tuple, dict] = {}
    for comp, label, anchor, nth, cols in WORLD_COMPETITIONS:
        for row in W.parse_table(W.find_table(text, anchor, nth)):
            if len(row) <= max(cols.values()):
                continue
            year_text = W.plain(cell(row, cols["year"]))
            if not re.fullmatch(r"\d{4}", year_text) or not W.links(cell(row, cols["champion"])):
                continue
            if not re.search(r"\d+\s*[–-]\s*\d+", cell(row, cols["score"])):
                continue  # final not played (1975, 1978)
            year = int(year_text)
            c_cell, r_cell = cell(row, cols["champion"]), cell(row, cols["runnerUp"])
            c_country = W.flag_code(cell(row, cols.get("championCountry", cols["champion"])))
            r_country = W.flag_code(cell(row, cols.get("runnerUpCountry", cols["runnerUp"])))
            attrs = row[cols["score"]]["attrs"].upper()
            note = next((v for k, v in LEG_NOTES.items() if k in attrs), None)
            leg = {"score": first_score(cell(row, cols["score"])), **({"note": note} if note else {})}
            k = (comp, year)
            if k not in finals:
                finals[k] = {
                    "competition": comp, "season": str(year), "year": year, "month": WORLD_MONTHS.get(k, 12),
                    "champion": clubs.resolve(c_cell, c_country), "championCountry": c_country,
                    "runnerUp": clubs.resolve(r_cell, r_country), "runnerUpCountry": r_country,
                    "legs": [leg],
                }
            elif comp == "IC":
                finals[k]["legs"].append(leg)  # two-legged ties and play-offs
    order = {c[0]: i for i, c in enumerate(WORLD_COMPETITIONS)}
    rows = sorted(finals.values(), key=lambda f: (f["year"], f["month"], order[f["competition"]]))
    for f in rows:
        f["championConfederation"] = confederation(f["championCountry"])
        f["runnerUpConfederation"] = confederation(f["runnerUpCountry"])
    used = {f["champion"] for f in rows} | {f["runnerUp"] for f in rows}
    unmapped = sorted(label for cid, label in clubs.unmapped.items() if cid in used)
    if unmapped:
        print(f"{key}: clubs shown without a crest mapping (add them to {CLUBS.name}): {unmapped}", file=sys.stderr)
    codes = {f["championCountry"] for f in rows} | {f["runnerUpCountry"] for f in rows} | {clubs.clubs[c]["country"] for c in used}
    codes.discard(None)
    return {
        "meta": {
            "generated": date.today().isoformat(),
            "competition": "World club champions",
            "through": f"{rows[-1]['year']}",
            "sources": [f"https://en.wikipedia.org/wiki/{WORLD_PAGE.replace(' ', '_')}"],
            "competitions": {c[0]: c[1] for c in WORLD_COMPETITIONS},
        },
        "countries": {c: {"name": COUNTRIES.get(c, (c, None))[0], "flag": COUNTRIES.get(c, (c, None))[1]} for c in sorted(codes)},
        "clubs": {c: {"name": clubs.clubs[c]["name"], "country": clubs.clubs[c]["country"], "crest": clubs.clubs[c]["espn"]} for c in sorted(used)},
        "finals": rows,
    }


def validate_world(key: str, data: dict) -> list[str]:
    errors = []
    names = {cid: c["name"] for cid, c in data["clubs"].items()}
    history = Counter(names[f["champion"]] for f in data["finals"] if f["year"] <= WORLD_HISTORY_THROUGH)
    if history != Counter(WORLD_HISTORY):
        diff = {k: (history.get(k, 0), WORLD_HISTORY.get(k, 0)) for k in set(history) | set(WORLD_HISTORY)
                if history.get(k, 0) != WORLD_HISTORY.get(k, 0)}
        errors.append(f"world titles through {WORLD_HISTORY_THROUGH} differ (got, expected): {diff}")
    per_comp = Counter(f["competition"] for f in data["finals"] if f["year"] <= 2025)
    if per_comp != Counter({"IC": 43, "CWC": 21, "FIC": 2}):
        errors.append(f"unexpected number of finals per competition: {dict(per_comp)}")
    for f in data["finals"]:
        if not f["championCountry"] or not f["runnerUpCountry"] or f["champion"] == f["runnerUp"]:
            errors.append(f"bad final {f['competition']} {f['year']}")
    return errors


# ---------- Argentine Primera División ----------

ARG_PAGE = "List of Argentine Primera División champions"
DISSIDENT = {
    "FAF": "Federación Argentina de Football",
    "AAmF": "Asociación Amateurs de Football",
    "LAF": "Liga Argentina de Football",
}


def club_from_cell(text: str, clubs: ClubIndex) -> str | None:
    """Champion cells link the club; a few early clubs are plain text."""
    if W.plain(text).startswith("(") or "not held" in text.lower():
        return None
    if W.links(text):
        return clubs.resolve(text, "ARG")
    name = re.sub(r"\(\d+\)", "", W.plain(text)).strip()
    if not name or name.startswith("("):
        return None
    cid = slug(name)
    if cid not in clubs.clubs:
        clubs.clubs[cid] = {"id": cid, "name": name, "country": "ARG", "espn": None, "aliases": []}
    clubs.used.add(cid)
    return cid


def build_argentina(key: str, refresh: bool) -> dict:
    text = W.fetch_raw(ARG_PAGE, RAW_DIR / f"{slug(ARG_PAGE)}.wiki", refresh)
    clubs = ClubIndex()
    titles = []
    seen = set()
    for row in W.parse_table(W.find_table(text, r"==\s*Primera División champions", 0)):
        if len(row) < 4 or row[0]["header"]:
            continue
        label = W.plain(cell(row, 1))
        m = re.match(r"(\d{4})", label)
        if not m:
            continue
        year = int(m.group(1))
        champion = club_from_cell(cell(row, 2), clubs)
        if not champion:
            continue
        key_row = (label, champion)
        if key_row in seen:
            continue
        seen.add(key_row)
        assoc = next((a for a in DISSIDENT if re.search(rf"\b{a}\b", label)), None)
        professional = year >= 1935 or assoc == "LAF"
        runner = club_from_cell(cell(row, 3), clubs) if W.plain(cell(row, 3)) not in ("", "–") else None
        titles.append({
            "season": label, "year": year, "champion": champion, "runnerUp": runner,
            "era": "professional" if professional else "amateur",
            "association": assoc,
        })
    # Mark the years with rival associations (each crowned its own champion).
    split_years = {t["year"] for t in titles if t["association"]}
    for t in titles:
        t["split"] = t["year"] in split_years

    # Official count per club from the same page, for validation.
    official = {}
    for row in W.parse_table(W.find_table(text, r"==\s*Titles by club", 0)):
        if len(row) < 3 or row[0]["header"]:
            continue
        cid = club_from_cell(cell(row, 1), clubs)
        n = W.number(cell(row, 2))
        if cid and n:
            official[cid] = official.get(cid, 0) + n

    used = {t["champion"] for t in titles} | {t["runnerUp"] for t in titles if t["runnerUp"]}
    unmapped = sorted(label for cid, label in clubs.unmapped.items() if cid in used)
    if unmapped:
        print(f"{key}: clubs shown without a crest mapping (add them to {CLUBS.name}): {unmapped}", file=sys.stderr)
    return {
        "meta": {
            "generated": date.today().isoformat(),
            "competition": "Argentine Primera División",
            "through": titles[-1]["season"],
            "sources": [f"https://en.wikipedia.org/wiki/{ARG_PAGE.replace(' ', '_')}"],
            "associations": DISSIDENT,
        },
        "countries": {"ARG": {"name": "Argentina", "flag": "ar"}},
        "clubs": {c: {"name": clubs.clubs[c]["name"], "country": "ARG", "crest": clubs.clubs[c]["espn"]} for c in sorted(used)},
        "titles": titles,
        "_official": official,
    }


def validate_argentina(key: str, data: dict) -> list[str]:
    errors = []
    official = data.pop("_official")
    counted = Counter(t["champion"] for t in data["titles"])
    diff = {data["clubs"].get(c, {}).get("name", c): (counted.get(c, 0), official.get(c, 0))
            for c in set(counted) | set(official) if counted.get(c, 0) != official.get(c, 0)}
    if diff:
        errors.append(f"titles differ from the page's own 'Titles by club' table (got, expected): {diff}")
    names = {cid: c["name"] for cid, c in data["clubs"].items()}
    leaders = Counter(names[t["champion"]] for t in data["titles"])
    if leaders["River Plate"] < 38 or leaders["Boca Juniors"] < 35:
        errors.append(f"River/Boca totals look wrong: {leaders['River Plate']}, {leaders['Boca Juniors']}")
    return errors


EXTRA = {
    "world-club-champions": (build_world, validate_world),
    "argentine-primera": (build_argentina, validate_argentina),
}


def write(key: str, data: dict) -> None:
    out = COMPETITIONS[key]["output"] if key in COMPETITIONS else OUTPUTS[key]
    if out.exists():
        old = json.loads(out.read_text(encoding="utf-8"))
        strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}
        if strip(old) == strip(data):
            print(f"{out.relative_to(ROOT)} is up to date")
            return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}: {len(data.get('finals') or data.get('titles'))} rows, through {data['meta']['through']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download the Wikipedia pages")
    parser.add_argument("competition", nargs="*", choices=[*COMPETITIONS, *EXTRA, []], help="default: all")
    args = parser.parse_args()

    failed = False
    for key in args.competition or [*COMPETITIONS, *EXTRA]:
        builder, validator = EXTRA.get(key, (build, validate))
        data = builder(key, args.refresh)
        errors = validator(key, data)
        if errors:
            print(f"{key}: validation failed:\n  " + "\n  ".join(errors), file=sys.stderr)
            failed = True
            continue
        write(key, data)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
