"""Shared parsing for Olympic sports listed event by event (swimming, tennis, boxing).

Wikipedia lists medalists with {{flagIOCmedalist|[[Name]]|USA|...}} for individuals and
{{flagIOC|USA|...}} followed by the team members' names for relays and doubles. Every
medal becomes a "slot": {"athletes": [{"name", "nation"}], "team": code or None, "mark": time}.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date

import wikitables as W
from build_grand_slams import COUNTRIES as TENNIS_COUNTRIES
from build_tournaments import MORE_TEAMS

MEDALS = ("gold", "silver", "bronze")

# Olympic delegations that no longer exist, or competed under another name.
HISTORIC = {
    "EUA": ("United Team of Germany", None), "FRG": ("West Germany", "de"), "GDR": ("East Germany", None),
    "URS": ("Soviet Union", None), "EUN": ("Unified Team", None), "ROC": ("ROC (Russian Olympic Committee)", None),
    "ANZ": ("Australasia", None), "TCH": ("Czechoslovakia", "cz"), "YUG": ("Yugoslavia", None), "BOH": ("Bohemia", None),
    "AIN": ("Individual Neutral Athletes", None), "IOA": ("Independent Olympic Athletes", None), "ZZX": ("Mixed team", None),
    "SCG": ("Serbia and Montenegro", None), "RU1": ("Russian Empire", None), "RAU": ("United Arab Republic", None),
    "SUR": ("Suriname", "sr"), "ZIM": ("Zimbabwe", "zw"), "CRC": ("Costa Rica", "cr"), "KAZ": ("Kazakhstan", "kz"),
    "LTU": ("Lithuania", "lt"), "ISL": ("Iceland", "is"), "IRL": ("Ireland", "ie"), "SGP": ("Singapore", "sg"),
    "HKG": ("Hong Kong", "hk"), "TPE": ("Chinese Taipei", "tw"), "PHI": ("Philippines", "ph"), "VEN": ("Venezuela", "ve"),
    "MEX": ("Mexico", "mx"), "TUN": ("Tunisia", "tn"), "ALG": ("Algeria", "dz"), "EGY": ("Egypt", "eg"), "SRB": ("Serbia", "rs"),
    "SVK": ("Slovakia", "sk"), "SLO": ("Slovenia", "si"), "CRO": ("Croatia", "hr"), "BLR": ("Belarus", "by"), "UKR": ("Ukraine", "ua"),
    "POL": ("Poland", "pl"), "ROU": ("Romania", "ro"), "BUL": ("Bulgaria", "bg"), "SUI": ("Switzerland", "ch"), "DEN": ("Denmark", "dk"),
    "NOR": ("Norway", "no"), "FIN": ("Finland", "fi"), "MDA": ("Moldova", "md"), "PUR": ("Puerto Rico", "pr"), "IRI": ("Iran", "ir"),
    "TRI": ("Trinidad and Tobago", "tt"), "UZB": ("Uzbekistan", "uz"), "AZE": ("Azerbaijan", "az"), "ARM": ("Armenia", "am"),
    "GEO": ("Georgia", "ge"), "MGL": ("Mongolia", "mn"), "THA": ("Thailand", "th"), "PRK": ("North Korea", "kp"),
    "KOR": ("South Korea", "kr"), "TJK": ("Tajikistan", "tj"), "KGZ": ("Kyrgyzstan", "kg"), "UGA": ("Uganda", "ug"),
    "NIG": ("Niger", "ne"), "ZAM": ("Zambia", "zm"), "TAN": ("Tanzania", "tz"), "SUD": ("Sudan", "sd"), "SYR": ("Syria", "sy"),
    "DOM": ("Dominican Republic", "do"), "GUY": ("Guyana", "gy"), "BER": ("Bermuda", "bm"), "MRI": ("Mauritius", "mu"),
    "NAM": ("Namibia", "na"), "LAT": ("Latvia", "lv"), "EST": ("Estonia", "ee"), "MKD": ("North Macedonia", "mk"),
    "PAK": ("Pakistan", "pk"), "SAM": ("Samoa", "ws"), "TGA": ("Tonga", "to"), "ECU": ("Ecuador", "ec"), "COL": ("Colombia", "co"),
    "GRE": ("Greece", "gr"), "LIE": ("Liechtenstein", "li"), "EOR": ("Refugee Olympic Team", None),
}
CODE_FIX = {"SAF": "RSA"}  # South Africa's old IOC code


def nation_info(code: str) -> dict:
    name, flag = HISTORIC.get(code) or MORE_TEAMS.get(code) or TENNIS_COUNTRIES.get(code) or (code, None)
    return {"name": name, "flag": flag}


def _code(c: str) -> str:
    c = c.upper()
    return CODE_FIX.get(c, c)


def medal_cell(cell: str, pairs: bool = False) -> list[dict] | None:
    """The medal slots in one cell (several when medals are shared or two bronzes share a cell), or None
    if the cell isn't a medal cell. With pairs, consecutive individual medalists form one team (doubles)."""
    text = W.strip_refs(cell)
    solo = re.findall(r"\{\{\s*flagIOC(?:medalist|athlete)\s*\|\s*(\[\[[^\]]*\]\]|[^|{}]+)\s*\|\s*([A-Za-z]{3})", text, re.I)
    if solo:
        people = [{"name": W.person(n) or W.plain(n), "nation": _code(c)} for n, c in solo]
        if pairs:
            groups = [people[i:i + 2] for i in range(0, len(people), 2)]
            return [{"athletes": g, "team": g[0]["nation"] if len({p["nation"] for p in g}) == 1 else "ZZX"} for g in groups]
        return [{"athletes": [p], "team": None} for p in people]
    teams = list(re.finditer(r"\{\{\s*flag ?IOC\s*\|\s*([A-Za-z]{3})", text, re.I))
    if teams:
        slots = []
        for i, t in enumerate(teams):
            rest = text[t.end():teams[i + 1].start() if i + 1 < len(teams) else len(text)]
            rest = rest[rest.find("}}") + 2:] if "}}" in rest else rest
            names = []
            for part in re.split(r"<br\s*/?>|\n", rest):
                if W.links(part):
                    names += [W.person(f"[[{a}|{b}]]") for a, b in W.links(part)]
                elif W.plain(part):
                    names.append(W.plain(part))
            code = _code(t.group(1))
            slots.append({"athletes": [{"name": n, "nation": code} for n in names if n], "team": code})
        return slots
    return None


TIME_RE = re.compile(r"^\s*(?:\d+:)?\d{1,2}\.\d{1,2}|^\s*\d+:\d{2}(?:\.\d)?")
EMPTY_RE = re.compile(r"not awarded|none awarded|no bronze|vacant|^—$|^–$", re.I)


def medal_slots(cells: list[dict], pairs: bool = False) -> list[list[dict] | None]:
    """Gold, silver and bronze from a row's medal cells (times after a medal cell are attached to it)."""
    out: list[list[dict] | None] = []
    prev = None
    for c in cells:
        if c is prev:
            continue  # a colspan repeats the same cell
        prev = c
        found = medal_cell(c["text"], pairs)
        plain = W.plain(c["text"])
        if found is not None:
            out.append(found)
        elif EMPTY_RE.search(plain):
            out.append(None)
        elif TIME_RE.match(plain) and out and out[-1]:
            for slot in out[-1]:
                slot["mark"] = re.match(r"[\d:.]+", plain.strip()).group(0)
    return out


def _merge(entry: dict, slots: list) -> None:
    """A second row of a rowspan only adds medalists (a tie, or a second bronze)."""
    names = lambda s: tuple(a["name"] for a in s["athletes"])
    for medal, cell in zip(MEDALS, slots):
        for slot in cell or []:
            if all(names(slot) != names(o) for o in entry[medal]):
                entry[medal].append(slot)


def parse_by_event(grid: list[list[dict]], pairs: bool = False) -> list[dict]:
    """One event's table: a row per Games ("1896 Athens"), then the medal cells."""
    results = []
    for row in grid:
        # The Games label is the first cell, or the second when a stray "||" left an empty cell before it.
        label = lambda c: W.plain(re.split(r"<br", c["text"])[0]).lstrip("| ")
        start = next((i for i, c in enumerate(row[:2]) if re.match(r"\d{4}\s", label(c))), None)
        if start is None:
            continue
        m = re.match(r"(\d{4})\s+(.+)", label(row[start]))
        year, city = int(m.group(1)), m.group(2).strip()
        slots = medal_slots(row[start + 1:], pairs)
        if not any(slots):
            continue
        if results and results[-1]["year"] == year:
            _merge(results[-1], slots)
            continue
        entry = {"year": year, "city": city}
        for medal, cell in zip(MEDALS, slots + [None] * 3):
            entry[medal] = list(cell or [])
        results.append(entry)
    return results


def parse_by_games(grid: list[list[dict]], year: int, city: str, pairs_for) -> dict[str, dict]:
    """One Games' table: a row per event, then the medal cells. Returns {event name: result}."""
    out: dict[str, dict] = {}
    last = None
    for row in grid:
        if not row or row[0]["header"]:
            continue
        name = W.plain(row[0]["text"])
        slots = medal_slots(row[1:], pairs_for(name))
        if not any(slots):
            continue
        if name in out or (row[0] is last):
            _merge(out[name], slots)
            continue
        last = row[0]
        entry = {"year": year, "city": city}
        for medal, cell in zip(MEDALS, slots + [None] * 3):
            entry[medal] = list(cell or [])
        out[name] = entry
    return out


def nation_of(slot: dict) -> str:
    return slot["team"] or slot["athletes"][0]["nation"]


def summarize(events: list[dict], sources: list[str], min_medals: int = 3) -> dict:
    """Nations, the most decorated athletes and the metadata, for the events."""
    nations = set()
    athletes = defaultdict(lambda: {"nation": None, "gold": 0, "silver": 0, "bronze": 0, "years": set(), "gender": None})
    for ev in events:
        for r in ev["results"]:
            for medal in MEDALS:
                for slot in r[medal]:
                    nations.add(nation_of(slot))
                    for a in slot["athletes"]:
                        nations.add(a["nation"])
                        # An athlete can medal for two delegations (Popov: Unified Team, then Russia): keep the latest.
                        rec = athletes[a["name"]]
                        if not rec["years"] or r["year"] >= max(rec["years"]):
                            rec["nation"] = a["nation"]
                        rec[medal] += 1
                        rec["years"].add(r["year"])
                        if ev["gender"] in ("Men", "Women"):
                            rec["gender"] = ev["gender"]
    top = sorted(athletes.items(), key=lambda kv: (-(kv[1]["gold"] + kv[1]["silver"] + kv[1]["bronze"]), -kv[1]["gold"]))
    leaders = [{"name": n, **{k: v for k, v in rec.items() if k != "years"}, "first": min(rec["years"]), "last": max(rec["years"])}
               for n, rec in top if rec["gold"] + rec["silver"] + rec["bronze"] >= min_medals or rec["gold"] >= 2]
    years = sorted({r["year"] for ev in events for r in ev["results"]})
    return {
        "meta": {
            "generated": date.today().isoformat(),
            "through": f"{years[-1]} Olympics",
            "sources": [f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}" for t in sources],
        },
        "nations": {c: nation_info(c) for c in sorted(nations)},
        "events": events,
        "athletes": leaders,
    }


def check_athletes(data: dict, exact: dict, minimum: dict | None = None) -> list[str]:
    errors = []
    by = {a["name"]: a for a in data["athletes"]}
    for name, (g, s, b) in exact.items():
        rec = by.get(name, {})
        if (rec.get("gold"), rec.get("silver"), rec.get("bronze")) != (g, s, b):
            errors.append(f"{name}: {rec.get('gold')}-{rec.get('silver')}-{rec.get('bronze')}, expected {g}-{s}-{b}")
    for name, (g, s, b) in (minimum or {}).items():
        rec = by.get(name, {})
        if rec.get("gold", 0) < g or rec.get("silver", 0) < s or rec.get("bronze", 0) < b:
            errors.append(f"{name}: {rec.get('gold')}-{rec.get('silver')}-{rec.get('bronze')}, expected at least {g}-{s}-{b}")
    unknown = [c for c, n in data["nations"].items() if n["name"] == c]
    if unknown:
        errors.append(f"nations without a name: {unknown}")
    for ev in data["events"]:
        for r in ev["results"]:
            if not r["gold"]:
                errors.append(f"{ev['key']} {r['year']}: no gold medalist")
    return errors
