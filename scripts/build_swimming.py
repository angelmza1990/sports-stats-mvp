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
from datetime import date

import wikitables as W
from build_football import RAW_DIR, ROOT, slug
from build_grand_slams import COUNTRIES as TENNIS_COUNTRIES
from build_tournaments import MORE_TEAMS

OUTPUT = ROOT / "swimming" / "olympics" / "data" / "swimming-olympics.json"
PAGES = {"Men": "List of Olympic medalists in swimming (men)", "Women": "List of Olympic medalists in swimming (women)"}
MEDALS = ("gold", "silver", "bronze")

# Olympic delegations that no longer exist, or competed under another name.
HISTORIC = {
    "EUA": ("United Team of Germany", None), "FRG": ("West Germany", "de"), "GDR": ("East Germany", None),
    "URS": ("Soviet Union", None), "EUN": ("Unified Team", None), "ROC": ("ROC", None), "ANZ": ("Australasia", None),
    "TCH": ("Czechoslovakia", "cz"), "YUG": ("Yugoslavia", None), "BOH": ("Bohemia", None), "AIN": ("Individual Neutral Athletes", None),
    "SUR": ("Suriname", "sr"), "ZIM": ("Zimbabwe", "zw"), "CRC": ("Costa Rica", "cr"), "KAZ": ("Kazakhstan", "kz"),
    "LTU": ("Lithuania", "lt"), "ISL": ("Iceland", "is"), "IRL": ("Ireland", "ie"), "SGP": ("Singapore", "sg"),
    "HKG": ("Hong Kong", "hk"), "TPE": ("Chinese Taipei", "tw"), "PHI": ("Philippines", "ph"), "VEN": ("Venezuela", "ve"),
    "MEX": ("Mexico", "mx"), "TUN": ("Tunisia", "tn"), "ALG": ("Algeria", "dz"), "EGY": ("Egypt", "eg"), "SRB": ("Serbia", "rs"),
    "SVK": ("Slovakia", "sk"), "SLO": ("Slovenia", "si"), "CRO": ("Croatia", "hr"), "BLR": ("Belarus", "by"), "UKR": ("Ukraine", "ua"),
    "POL": ("Poland", "pl"), "ROU": ("Romania", "ro"), "BUL": ("Bulgaria", "bg"), "SUI": ("Switzerland", "ch"), "DEN": ("Denmark", "dk"),
    "NOR": ("Norway", "no"), "FIN": ("Finland", "fi"), "MDA": ("Moldova", "md"), "PUR": ("Puerto Rico", "pr"), "IRI": ("Iran", "ir"),
    "TRI": ("Trinidad and Tobago", "tt"), "ROC": ("ROC (Russian Olympic Committee)", None),
}
CODE_FIX = {"SAF": "RSA"}  # South Africa's old IOC code

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


def nation_info(code: str) -> dict:
    name, flag = HISTORIC.get(code) or MORE_TEAMS.get(code) or TENNIS_COUNTRIES.get(code) or (code, None)
    return {"name": name, "flag": flag}


def medalists(cell: str) -> tuple[list[dict], str | None] | None:
    """The swimmers (and nation) in a medal cell, or None if the cell isn't a medal cell."""
    text = W.strip_refs(cell)
    solo = re.findall(r"\{\{\s*flagIOCmedalist\s*\|\s*(\[\[[^\]]*\]\]|[^|{}]+)\s*\|\s*([A-Z]{3})", text, re.I)
    if solo:
        return [{"name": W.person(n) or W.plain(n), "nation": CODE_FIX.get(c, c)} for n, c in solo], None
    team = re.search(r"\{\{\s*flagIOC\s*\|\s*([A-Z]{3})", text)
    if team:
        rest = text[team.end():]
        names = [W.person(f"[[{t}|{x}]]") for t, x in W.links(rest)]
        names += [W.plain(p) for p in re.split(r"<br\s*/?>", rest) if W.plain(p) and not W.links(p) and "}}" not in p[:3]]
        code = CODE_FIX.get(team.group(1), team.group(1))
        return [{"name": n, "nation": code} for n in names if n], code
    return None


TIME_RE = re.compile(r"^\s*(?:\d+:)?\d{1,2}\.\d{1,2}|^\s*\d+:\d{2}(?:\.\d)?")


def parse_event(grid: list[list[dict]], gender: str) -> list[dict]:
    results = []
    for row in grid:
        games = W.plain(re.split(r"<br", row[0]["text"])[0]) if row else ""
        m = re.match(r"(\d{4})\s+(.+)", games)
        if not m:
            continue
        year, city = int(m.group(1)), m.group(2).strip()
        slots: list[dict] = []
        prev = None
        for c in row[1:]:
            if c is prev:
                continue  # a colspan repeats the same cell
            prev = c
            found = medalists(c["text"])
            plain = W.plain(c["text"])
            if found is not None:
                swimmers, team = found
                slots.append({"swimmers": swimmers, "team": team})
            elif re.search(r"not awarded|none awarded|no bronze|^—$|^–$", plain, re.I):
                slots.append(None)
            elif TIME_RE.match(plain) and slots and slots[-1] is not None:
                slots[-1]["time"] = re.match(r"[\d:.]+", plain.strip()).group(0)
        if not slots:
            continue
        if results and results[-1]["year"] == year:
            # A tie written over two rows (rowspan): the second row only adds the tied medalist.
            last = results[-1]
            for medal, slot in zip(MEDALS, slots):
                names = lambda x: tuple(sw["name"] for sw in x["swimmers"])
                if slot and all(names(slot) != names(o) for o in last[medal]):
                    last[medal].append(slot)
            continue
        entry = {"year": year, "city": city}
        for medal, slot in zip(MEDALS, slots + [None] * 3):
            entry[medal] = [] if slot is None else [slot]
        # Ties: two swimmers in one cell share the medal (the next one is "not awarded").
        for medal in MEDALS:
            for slot in list(entry[medal]):
                if not slot["team"] and len(slot["swimmers"]) > 1:
                    entry[medal] = [{"swimmers": [s], "team": None, "time": slot.get("time")} for s in slot["swimmers"]]
        results.append(entry)
    return results


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
            chunk = body[:nxt.start()] if nxt else body
            tables = W.all_tables("\n" + chunk)
            if not tables:
                continue
            results = parse_event(tables[0], section)
            if not results:
                continue
            name = heading[0].upper() + heading[1:]
            events.append({
                "key": slug(f"{section}-{name}"), "name": name, "gender": section, "stroke": stroke_of(name),
                "current": current, "results": results,
            })
    return {"events": events, "_official": official}


def finish(data: dict) -> dict:
    events = data["events"]
    nations, swimmers = set(), defaultdict(lambda: {"nation": None, "gold": 0, "silver": 0, "bronze": 0, "years": set(), "gender": None})
    for ev in events:
        for r in ev["results"]:
            for medal in MEDALS:
                for slot in r[medal]:
                    nation = slot["team"] or slot["swimmers"][0]["nation"]
                    nations.add(nation)
                    for s in slot["swimmers"]:
                        # One swimmer can medal for two delegations (Popov: Unified Team, then Russia): keep the latest.
                        rec = swimmers[s["name"]]
                        if not rec["years"] or r["year"] >= max(rec["years"]):
                            rec["nation"] = s["nation"]
                        rec[medal] += 1
                        rec["years"].add(r["year"])
                        rec["gender"] = ev["gender"] if ev["gender"] != "Mixed" else rec["gender"]
    top = sorted(swimmers.items(), key=lambda kv: (-(kv[1]["gold"] + kv[1]["silver"] + kv[1]["bronze"]), -kv[1]["gold"]))
    leaders = [{"name": n, **{k: v for k, v in rec.items() if k != "years"}, "first": min(rec["years"]), "last": max(rec["years"])}
               for n, rec in top if rec["gold"] + rec["silver"] + rec["bronze"] >= 3 or rec["gold"] >= 2]
    years = sorted({r["year"] for ev in events for r in ev["results"]})
    return {
        "meta": {
            "generated": date.today().isoformat(),
            "through": f"{years[-1]} Olympics",
            "sources": [f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}" for t in PAGES.values()],
        },
        "nations": {c: nation_info(c) for c in sorted(nations)},
        "events": events,
        "swimmers": leaders,
        "_official": data["_official"],
    }


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
                            code = slot["team"] or slot["swimmers"][0]["nation"]
                            got[merge.get(code, code)][medal] += 1
        diff = {c: (tuple(got[c][m] for m in MEDALS), exp) for c, exp in table.items() if tuple(got[c][m] for m in MEDALS) != exp}
        if diff:
            print(f"warning: {gender} medals differ from the page's own medal table (got, table): {diff}", file=sys.stderr)
    per_games = Counter(r["year"] for ev in data["events"] for r in ev["results"])
    for year, n in EVENTS_PER_GAMES.items():
        if per_games[year] != n:
            errors.append(f"{year}: {per_games[year]} events, expected {n}")
    by = {s["name"]: s for s in data["swimmers"]}
    for name, (g, s, b) in EXPECTED_SWIMMERS.items():
        rec = by.get(name, {})
        if (rec.get("gold"), rec.get("silver"), rec.get("bronze")) != (g, s, b):
            errors.append(f"{name}: {rec.get('gold')}-{rec.get('silver')}-{rec.get('bronze')}, expected {g}-{s}-{b}")
    for name, (g, s, b) in EXPECTED_MIN.items():
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download the Wikipedia pages")
    args = parser.parse_args()
    data = finish(build(args.refresh))
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
