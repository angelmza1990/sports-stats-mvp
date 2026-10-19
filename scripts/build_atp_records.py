"""Build the Open Era career records datasets used by tennis/atp-records and tennis/wta-records.

Counts titles and match wins (overall and by surface) for every player from
Jeff Sackmann's ATP and WTA match files since April 1968, adds the Grand Slams
the files don't cover yet (from Wikipedia draws) and the manual ATP title
supplement, and reads weeks at No. 1 and year-end No. 1s from Wikipedia.

Usage:
    python3 scripts/build_atp_records.py              # both tours, cached files
    python3 scripts/build_atp_records.py --tour wta   # WTA only
    python3 scripts/build_atp_records.py --refresh    # re-download everything
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime

import wikitables as W
from build_grand_slams import COUNTRIES, load_overrides, nationality
from tennis_data import (
    OPEN_ERA_START, ROOT, RAW_DIR, SLAM_NAMES, ascii_key, download, final_date, is_walkover, missing_slams,
    read_matches, slam_from_wikipedia,
)

SUPPLEMENT = ROOT / "data" / "manual" / "big_three_supplement.csv"
SURFACES = ["Hard", "Clay", "Grass", "Carpet"]
TEAM_EVENTS = ("atp cup", "united cup", "laver cup")
TOP_N = 60

TOURS = {
    "atp": {
        "output": ROOT / "tennis" / "atp-records" / "data" / "atp-records.json",
        "no1": "List of ATP number 1 ranked singles tennis players",
        # Davis Cup (D) counts for match records only; team events are not titles.
        "levels": {"G", "M", "A", "F", "O", "D"},
        "title_levels": set("GMAFO"),
        "titles": {"Roger Federer": 103, "Rafael Nadal": 92},
        # Counted from match data, a few pre-1990 totals can differ by one from the ATP's own tally.
        "near": {"John McEnroe": (77, 1), "Ivan Lendl": (94, 1), "Jimmy Connors": (109, 1)},
        "active": {"Novak Djokovic": 101},
        "weeks": {"Novak Djokovic": 428, "Roger Federer": 310, "Pete Sampras": 286},
        "record": ("Roger Federer", 1251, 275),
    },
    "wta": {
        "output": ROOT / "tennis" / "wta-records" / "data" / "wta-records.json",
        "no1": "List of WTA number 1 ranked singles tennis players",
        # W: tour events before 2000; T1-T5: the tiers (1988-2008); PM/P/I: Premier and International (2009-2020)
        # and WTA 1000/500/250 since 2021. Billie Jean King Cup (D) counts for match records only.
        "levels": {"G", "F", "O", "W", "T1", "T2", "T3", "T4", "T5", "PM", "P", "I", "D"},
        "title_levels": {"G", "F", "O", "W", "T1", "T2", "T3", "T4", "T5", "PM", "P", "I"},
        "titles": {"Serena Williams": 73, "Venus Williams": 49, "Martina Hingis": 43, "Justine Henin": 43,
                   "Kim Clijsters": 41, "Maria Sharapova": 36},
        # The WTA's early records are incomplete in the match data.
        "near": {"Martina Navratilova": (167, 3), "Steffi Graf": (107, 2), "Chris Evert": (157, 12)},
        "active": {},
        "weeks": {"Steffi Graf": 377, "Martina Navratilova": 332, "Serena Williams": 319, "Chris Evert": 260},
        "record": None,
    },
}


def load(refresh: bool, tour: str) -> tuple[list[dict], list[str]]:
    cfg = TOURS[tour]
    paths = download(1968, date.today().year, refresh, tour)
    rows = read_matches(paths, lambda r: r["tourney_date"] >= OPEN_ERA_START and r["tourney_level"] in cfg["levels"])
    rows = [r for r in rows if "qual" not in r["tourney_name"].lower()]
    known = {ascii_key(r[f"{s}_name"]): r[f"{s}_name"] for r in rows for s in ("winner", "loser")}
    iocs = {r[f"{s}_name"]: r[f"{s}_ioc"] for r in rows for s in ("winner", "loser")}
    added = []
    slam_rows = [r for r in rows if r["tourney_level"] == "G" and r["tourney_name"] in SLAM_NAMES]
    for slam, year in missing_slams(slam_rows):
        try:
            rows.extend(slam_from_wikipedia(slam, year, refresh, known, tour, iocs))
            added.append(f"{slam} {year}")
        except LookupError as err:
            print(f"skipping {slam} {year}: {err}", file=sys.stderr)
    return rows, added


def build(refresh: bool, tour: str) -> dict:
    cfg = TOURS[tour]
    rows, added = load(refresh, tour)
    overrides = load_overrides(tour)
    stats: dict[str, Counter] = defaultdict(Counter)
    iocs: dict[str, Counter] = defaultdict(Counter)
    title_years: dict[str, list] = defaultdict(list)
    last_date = max(r["tourney_date"] for r in rows if r.get("source") != "wikipedia")

    for r in rows:
        when = final_date(r)
        surface = r["surface"] if r["surface"] in SURFACES else None
        for side in ("winner", "loser"):
            name = r[f"{side}_name"]
            iocs[name][nationality(name, r[f"{side}_ioc"], when, overrides)] += 1
        if r["round"] == "F" and r["tourney_level"] in cfg["title_levels"] and not r["tourney_name"].lower().startswith(TEAM_EVENTS):
            w = r["winner_name"]
            stats[w]["titles"] += 1
            if surface:
                stats[w][f"titles_{surface}"] += 1
            stats[w][f"level_{r['tourney_level']}"] += 1
            title_years[w].append(when.year)
        if is_walkover(r["score"]):
            continue
        for side, key in (("winner", "won"), ("loser", "lost")):
            name = r[f"{side}_name"]
            stats[name][key] += 1
            if surface:
                stats[name][f"{key}_{surface}"] += 1

    # Titles newer than the match files (e.g. Djokovic's 2026 Beijing title).
    with SUPPLEMENT.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f) if tour == "atp" else []:
            year = int(r["final_date"][:4])
            if r["round"] == "F" and str(year) > last_date[:4] or (r["round"] == "F" and r["final_date"] > last_date):
                w = r["winner_name"]
                stats[w]["titles"] += 1
                stats[w][f"titles_{r['surface']}"] += 1
                stats[w][f"level_{r['tourney_level']}"] += 1
                title_years[w].append(year)

    # The WTA's level codes don't mark its top tier consistently: count WTA 1000 titles (and Tier I,
    # Premier Mandatory and Premier 5) from the WTA 1000 dataset, limited to finals in the match files.
    if tour == "wta":
        thousand = json.loads((ROOT / "tennis" / "wta-1000" / "data" / "wta-1000.json").read_text(encoding="utf-8"))
        for c in stats.values():
            c["level_M"] = 0
        for e in thousand["editions"]:
            if e["source"] == "match data":
                stats[e["champion"]]["level_M"] += 1

    # Weeks at No. 1 and year-end No. 1s.
    text = W.fetch_raw(cfg["no1"], RAW_DIR / "wikipedia" / f"{cfg['no1'].lower().replace(' ', '-')}.wiki", refresh)
    by_key = {ascii_key(n): n for n in stats}
    winners = sorted((n for n in stats if stats[n]["titles"]), key=lambda n: -stats[n]["titles"])

    def lookup(name: str) -> str:
        """Match-file spelling; married names on Wikipedia ("Evonne Goolagong Cawley") match the name they extend."""
        key = ascii_key(name)
        return by_key.get(key) or next((n for n in winners if key.startswith(ascii_key(n))), name)
    weeks = {}
    totals = next(g for g in W.all_tables(text) if W.header_labels(g[0])[:3] in (["No.", "Player", "Total"], ["No.", "Player", "Weeks"]))
    for row in totals[1:]:
        if len(row) < 3 or W.number(row[2]["text"]) is None:
            continue
        name = W.person(row[1]["text"])
        key = lookup(name)
        weeks[key] = W.number(row[2]["text"])
        iocs[key][W.flag_code(row[1]["text"])] += 0
    year_end = []
    for grid in W.all_tables(text):
        head = " ".join(W.header_labels(grid[0])).lower()
        if head.startswith("year player"):
            for row in grid[1:]:
                year = W.number(row[0]["text"]) if row else None
                cell = re.sub(r"\{\{(?:flagicon|small)[^{}]*\}\}", "", row[1]["text"]) if len(row) > 1 else ""
                name = re.sub(r"\s*\(\d+\)\s*$", "", W.person(cell) or "").strip()
                # The current season's year-end No. 1 isn't decided until the season ends.
                if year and name and 1973 <= year < date.today().year:
                    year_end.append({"year": year, "player": lookup(name)})
    year_end = sorted({y["year"]: y for y in year_end}.values(), key=lambda y: y["year"])

    def nation(name: str) -> str | None:
        c = iocs.get(name)
        return c.most_common(1)[0][0] if c and c.most_common(1)[0][1] else (W.flag_code("") or None)

    # Keep the leaders of every metric.
    keep = set(weeks)
    for metric in ("titles", "won", *[f"titles_{s}" for s in SURFACES], *[f"won_{s}" for s in SURFACES]):
        keep |= {n for n, _ in sorted(stats.items(), key=lambda kv: -kv[1][metric])[:TOP_N] if stats[n][metric]}
    keep |= {n for n, c in stats.items() if c["won"] + c["lost"] >= 500}
    players = []
    for name in sorted(keep):
        c = stats[name]
        players.append({
            "name": name, "nation": nation(name), "titles": c["titles"], "won": c["won"], "lost": c["lost"],
            "weeks": weeks.get(name, 0),
            "surface": {s: {"titles": c[f"titles_{s}"], "won": c[f"won_{s}"], "lost": c[f"lost_{s}"]} for s in SURFACES},
            "levels": {lvl: c[f"level_{lvl}"] for lvl in "GMFO"},
            "firstTitle": min(title_years[name]) if title_years[name] else None,
            "lastTitle": max(title_years[name]) if title_years[name] else None,
        })

    # Every titlist (not just the leaders) feeds the nations breakdown and the race.
    titlists = {n: c["titles"] for n, c in stats.items() if c["titles"]}
    nations = defaultdict(lambda: {"titles": 0, "players": 0, "won": 0, "no1": 0, "weeks": 0})
    for name, c in stats.items():
        code = nation(name)
        if not code:
            continue
        nations[code]["titles"] += c["titles"]
        nations[code]["players"] += 1 if c["titles"] else 0
        nations[code]["won"] += c["won"]
    for name, w in weeks.items():
        code = nation(name)
        if code:
            nations[code]["no1"] += 1
            nations[code]["weeks"] += w
    titles_by_year = defaultdict(Counter)
    for name, ys in title_years.items():
        for y in ys:
            titles_by_year[y][name] += 1

    codes = {p["nation"] for p in players} | set(nations)
    codes.discard(None)
    return {
        "meta": {
            "generated": date.today().isoformat(),
            "through": f"{tour.upper()} match data through {datetime.strptime(last_date, '%Y%m%d').strftime('%B %Y')}" + (f", plus {', '.join(added)}" if added else ""),
            "sources": [
                f"Jeff Sackmann / Tennis Abstract {tour.upper()} match data (CC BY-NC-SA 4.0)",
                f"https://en.wikipedia.org/wiki/{cfg['no1'].replace(' ', '_')}",
            ],
            "tour": tour,
        },
        "countries": {c: {"name": COUNTRIES.get(c, (c, None))[0], "flag": COUNTRIES.get(c, (c, None))[1]} for c in sorted(codes)},
        "players": players,
        "nations": [{"nation": k, **v} for k, v in sorted(nations.items(), key=lambda kv: -kv[1]["titles"])],
        "yearEnd": year_end,
        "titlesByYear": {str(y): dict(c) for y, c in sorted(titles_by_year.items())},
        "titlistNations": {n: nation(n) for n in titlists},
    }


def validate(data: dict, tour: str) -> list[str]:
    cfg = TOURS[tour]
    errors = []
    by = {p["name"]: p for p in data["players"]}
    for name, n in cfg["titles"].items():
        if by.get(name, {}).get("titles") != n:
            errors.append(f"{name}: {by.get(name, {}).get('titles')} titles, expected {n}")
    for name, (n, tolerance) in cfg["near"].items():
        if abs(by.get(name, {}).get("titles", 0) - n) > tolerance:
            errors.append(f"{name}: {by.get(name, {}).get('titles')} titles, expected about {n}")
    for name, n in cfg["active"].items():
        if by.get(name, {}).get("titles", 0) < n:
            errors.append(f"{name}: fewer than {n} titles")
    for name, n in cfg["weeks"].items():
        if by.get(name, {}).get("weeks", 0) < n:
            errors.append(f"{name}: {by.get(name, {}).get('weeks')} weeks at No. 1, expected at least {n}")
    if cfg["record"]:
        name, won, lost = cfg["record"]
        p = by.get(name, {})
        if (p.get("won"), p.get("lost")) != (won, lost):
            errors.append(f"{name} win-loss {p.get('won')}-{p.get('lost')}, expected {won}-{lost}")
    if len(data["yearEnd"]) < 49:
        errors.append("year-end No. 1 list incomplete")
    if any(not p["nation"] for p in data["players"]):
        errors.append(f"players without nationality: {[p['name'] for p in data['players'] if not p['nation']][:5]}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download raw files")
    parser.add_argument("--tour", choices=list(TOURS), action="append", help="default: both")
    args = parser.parse_args()
    failed = False
    for tour in args.tour or list(TOURS):
        output = TOURS[tour]["output"]
        data = build(args.refresh, tour)
        errors = validate(data, tour)
        if errors:
            print(f"{tour}: validation failed:\n  " + "\n  ".join(errors), file=sys.stderr)
            failed = True
            continue
        if output.exists():
            old = json.loads(output.read_text(encoding="utf-8"))
            strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}
            if strip(old) == strip(data):
                print(f"{output.relative_to(ROOT)} is up to date")
                continue
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print(f"wrote {output.relative_to(ROOT)}: {len(data['players'])} players")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
