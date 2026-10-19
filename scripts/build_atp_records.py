"""Build the Open Era ATP records dataset used by tennis/atp-records.

Counts titles and match wins (overall and by surface) for every player from
Jeff Sackmann's ATP match files since April 1968, adds the Grand Slams the
files don't cover yet (from Wikipedia draws) and the manual title supplement,
and reads weeks at No. 1 and year-end No. 1s from Wikipedia.

Usage:
    python3 scripts/build_atp_records.py            # use cached files
    python3 scripts/build_atp_records.py --refresh  # re-download everything
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

OUTPUT = ROOT / "tennis" / "atp-records" / "data" / "atp-records.json"
SUPPLEMENT = ROOT / "data" / "manual" / "big_three_supplement.csv"
NO1_PAGE = "List of ATP number 1 ranked singles tennis players"
SURFACES = ["Hard", "Clay", "Grass", "Carpet"]
TITLE_LEVELS = set("GMAFO")  # Davis Cup (D) and team events are not titles
TEAM_EVENTS = ("atp cup", "united cup", "laver cup")
TOP_N = 60

EXPECTED_TITLES = {"Roger Federer": 103, "Rafael Nadal": 92}
# Counted from match data, a few pre-1990 totals can differ by one from the ATP's own tally.
NEAR_TITLES = {"John McEnroe": 77, "Ivan Lendl": 94, "Jimmy Connors": 109}
ACTIVE_MIN = {"Novak Djokovic": 101}
EXPECTED_WEEKS = {"Novak Djokovic": 428, "Roger Federer": 310, "Pete Sampras": 286}


def load(refresh: bool) -> tuple[list[dict], list[str]]:
    paths = download(1968, date.today().year, refresh)
    rows = read_matches(paths, lambda r: r["tourney_date"] >= OPEN_ERA_START and r["tourney_level"] in "GMAFOD")
    known = {ascii_key(r[f"{s}_name"]): r[f"{s}_name"] for r in rows for s in ("winner", "loser")}
    added = []
    slam_rows = [r for r in rows if r["tourney_level"] == "G" and r["tourney_name"] in SLAM_NAMES]
    for slam, year in missing_slams(slam_rows):
        try:
            rows.extend(slam_from_wikipedia(slam, year, refresh, known))
            added.append(f"{slam} {year}")
        except LookupError as err:
            print(f"skipping {slam} {year}: {err}", file=sys.stderr)
    return rows, added


def build(refresh: bool) -> dict:
    rows, added = load(refresh)
    overrides = load_overrides()
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
        if r["round"] == "F" and r["tourney_level"] in TITLE_LEVELS and not r["tourney_name"].lower().startswith(TEAM_EVENTS):
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
        for r in csv.DictReader(f):
            year = int(r["final_date"][:4])
            if r["round"] == "F" and str(year) > last_date[:4] or (r["round"] == "F" and r["final_date"] > last_date):
                w = r["winner_name"]
                stats[w]["titles"] += 1
                stats[w][f"titles_{r['surface']}"] += 1
                stats[w][f"level_{r['tourney_level']}"] += 1
                title_years[w].append(year)

    # Weeks at No. 1 and year-end No. 1s.
    text = W.fetch_raw(NO1_PAGE, RAW_DIR / "wikipedia" / "list-of-atp-number-1-ranked-singles-tennis-players.wiki", refresh)
    by_key = {ascii_key(n): n for n in stats}
    weeks = {}
    totals = next(g for g in W.all_tables(text) if W.header_labels(g[0])[:3] == ["No.", "Player", "Total"])
    for row in totals[1:]:
        if len(row) < 3 or W.number(row[2]["text"]) is None:
            continue
        name = W.person(row[1]["text"])
        key = by_key.get(ascii_key(name), name)
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
                    year_end.append({"year": year, "player": by_key.get(ascii_key(name), name)})
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
            "through": f"ATP match data through {datetime.strptime(last_date, '%Y%m%d').strftime('%B %Y')}" + (f", plus {', '.join(added)}" if added else ""),
            "sources": [
                "Jeff Sackmann / Tennis Abstract ATP match data (CC BY-NC-SA 4.0)",
                f"https://en.wikipedia.org/wiki/{NO1_PAGE.replace(' ', '_')}",
            ],
        },
        "countries": {c: {"name": COUNTRIES.get(c, (c, None))[0], "flag": COUNTRIES.get(c, (c, None))[1]} for c in sorted(codes)},
        "players": players,
        "nations": [{"nation": k, **v} for k, v in sorted(nations.items(), key=lambda kv: -kv[1]["titles"])],
        "yearEnd": year_end,
        "titlesByYear": {str(y): dict(c) for y, c in sorted(titles_by_year.items())},
        "titlistNations": {n: nation(n) for n in titlists},
    }


def validate(data: dict) -> list[str]:
    errors = []
    by = {p["name"]: p for p in data["players"]}
    for name, n in EXPECTED_TITLES.items():
        if by.get(name, {}).get("titles") != n:
            errors.append(f"{name}: {by.get(name, {}).get('titles')} titles, expected {n}")
    for name, n in NEAR_TITLES.items():
        if abs(by.get(name, {}).get("titles", 0) - n) > 1:
            errors.append(f"{name}: {by.get(name, {}).get('titles')} titles, expected about {n}")
    for name, n in ACTIVE_MIN.items():
        if by.get(name, {}).get("titles", 0) < n:
            errors.append(f"{name}: fewer than {n} titles")
    for name, n in EXPECTED_WEEKS.items():
        if by.get(name, {}).get("weeks", 0) < n:
            errors.append(f"{name}: {by.get(name, {}).get('weeks')} weeks at No. 1, expected at least {n}")
    fed = by.get("Roger Federer", {})
    if (fed.get("won"), fed.get("lost")) != (1251, 275):
        errors.append(f"Federer win-loss {fed.get('won')}-{fed.get('lost')}, expected 1251-275")
    if len(data["yearEnd"]) < 50:
        errors.append("year-end No. 1 list incomplete")
    if any(not p["nation"] for p in data["players"]):
        errors.append(f"players without nationality: {[p['name'] for p in data['players'] if not p['nation']][:5]}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download raw files")
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
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(data['players'])} players")


if __name__ == "__main__":
    main()
