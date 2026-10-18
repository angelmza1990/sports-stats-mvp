"""Build the Big Three dataset used by tennis/big-three.

Downloads Jeff Sackmann's ATP match files (via an archival mirror), extracts
every title won by Federer, Nadal and Djokovic plus every match they played
against each other, and writes a compact JSON file for the front end.

Usage:
    python3 scripts/build_big_three.py            # use cached raw files
    python3 scripts/build_big_three.py --refresh  # re-download raw files
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
SUPPLEMENT = ROOT / "data" / "manual" / "big_three_supplement.csv"
OUTPUT = ROOT / "tennis" / "big-three" / "data" / "big-three.json"

SOURCE_URL = "https://raw.githubusercontent.com/Aneeshers/tennis-sackmann-archive/main/atp/atp_matches_{year}.csv"
FIRST_YEAR, LAST_YEAR = 1998, 2026

PLAYERS = {
    "Novak Djokovic": {"id": "djokovic", "name": "Novak Djokovic", "short": "Djokovic", "country": "Serbia", "born": "1987-05-22", "retired": None},
    "Rafael Nadal": {"id": "nadal", "name": "Rafael Nadal", "short": "Nadal", "country": "Spain", "born": "1986-06-03", "retired": "2024-11-19"},
    "Roger Federer": {"id": "federer", "name": "Roger Federer", "short": "Federer", "country": "Switzerland", "born": "1981-08-08", "retired": "2022-09-23"},
}

# Team competitions: their "finals" are rubbers, not titles.
TEAM_EVENTS = ("atp cup", "united cup", "laver cup")

TOURNEY_NAMES = {
    "Us Open": "US Open",
    "Roland Garros": "Roland Garros",
    "Australian Open": "Australian Open",
    "Wimbledon": "Wimbledon",
    "Masters Cup": "Tour Finals",
    "Atp Cup": "ATP Cup",
}

# Players who can still add to their totals; their checks are minimums.
ACTIVE = {"djokovic"}

# Known official totals (October 2026), used as a sanity check on every build.
EXPECTED = {
    "titles": {"djokovic": 102, "federer": 103, "nadal": 92},
    "G": {"djokovic": 24, "nadal": 22, "federer": 20},
    "M": {"djokovic": 40, "nadal": 36, "federer": 28},
    "F": {"djokovic": 7, "federer": 6, "nadal": 0},
    "O": {"djokovic": 1, "nadal": 1, "federer": 0},
    "h2h": {
        ("djokovic", "nadal"): (31, 29),
        ("djokovic", "federer"): (27, 23),
        ("nadal", "federer"): (24, 16),
    },
}


def download(refresh: bool) -> list[Path]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        path = RAW_DIR / f"atp_matches_{year}.csv"
        if refresh or not path.exists():
            print(f"downloading {year}...", file=sys.stderr)
            urllib.request.urlretrieve(SOURCE_URL.format(year=year), path)
        paths.append(path)
    return paths


def final_date(row: dict) -> date:
    """Estimate the final's date from the tournament start date.

    Two-week events (Slams, 96/128 draws) end on the second Sunday,
    everything else on the first Sunday.
    """
    start = datetime.strptime(row["tourney_date"], "%Y%m%d").date()
    two_weeks = row["tourney_level"] == "G" or int(row["draw_size"] or 0) >= 96
    return start + timedelta(days=13 if two_weeks else 6)


def clean_name(name: str) -> str:
    return TOURNEY_NAMES.get(name, name)


def clean_level(row: dict) -> str:
    """Fix the few events whose level code is inconsistent in the source."""
    name = clean_name(row["tourney_name"])
    if name == "Tour Finals":
        return "F"
    if "Olympics" in name:
        return "O"
    return row["tourney_level"]


def is_walkover(score: str) -> bool:
    return "W/O" in score.upper()


def load_rows(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        with path.open(encoding="utf-8", errors="replace", newline="") as f:
            for row in csv.DictReader(f):
                if row["winner_name"] in PLAYERS or row["loser_name"] in PLAYERS:
                    row["_date"] = final_date(row)
                    rows.append(row)
    return rows


def load_supplement() -> list[dict]:
    with SUPPLEMENT.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["_date"] = datetime.strptime(row["final_date"], "%Y%m%d").date()
    return rows


def build(rows: list[dict], supplement: list[dict]) -> dict:
    titles, h2h = [], []
    record: dict[str, Counter] = {p["id"]: Counter() for p in PLAYERS.values()}

    for row in rows:
        w, l = row["winner_name"], row["loser_name"]
        if is_walkover(row["score"]):
            continue
        year = str(row["_date"].year)
        if w in PLAYERS:
            record[PLAYERS[w]["id"]][year + ":w"] += 1
        if l in PLAYERS:
            record[PLAYERS[l]["id"]][year + ":l"] += 1
        if w in PLAYERS and l in PLAYERS:
            h2h.append({
                "date": row["_date"].isoformat(),
                "tourney": clean_name(row["tourney_name"]),
                "level": clean_level(row),
                "surface": row["surface"],
                "round": row["round"],
                "winner": PLAYERS[w]["id"],
                "loser": PLAYERS[l]["id"],
                "score": row["score"],
            })

    # Supplement rows fill the gap until the source data catches up; drop any it now covers.
    covered = {(r["winner_name"], clean_name(r["tourney_name"]), r["_date"].year) for r in rows if r["round"] == "F"}
    supplement = [r for r in supplement if (r["winner_name"], clean_name(r["tourney_name"]), r["_date"].year) not in covered]

    for row in rows + supplement:
        w = row["winner_name"]
        if row["round"] != "F" or w not in PLAYERS:
            continue
        if row["tourney_name"].lower().startswith(TEAM_EVENTS) or row["tourney_level"] == "D":
            continue
        titles.append({
            "date": row["_date"].isoformat(),
            "player": PLAYERS[w]["id"],
            "level": clean_level(row),
            "tourney": clean_name(row["tourney_name"]),
            "surface": row["surface"],
            "opponent": row["loser_name"],
            "score": row["score"],
            "age": round(float(row["winner_age"]), 2) if row["winner_age"] else None,
        })

    titles.sort(key=lambda t: (t["date"], t["player"]))
    h2h.sort(key=lambda m: m["date"])

    seasons = {}
    for pid, counter in record.items():
        years = sorted({k.split(":")[0] for k in counter})
        seasons[pid] = [{"year": int(y), "w": counter[y + ":w"], "l": counter[y + ":l"]} for y in years]

    # Last tournament week covered by the source files (supplement rows excluded).
    data_through = datetime.strptime(max(r["tourney_date"] for r in rows), "%Y%m%d").date().isoformat()
    return {
        "meta": {
            "generated": date.today().isoformat(),
            "dataThrough": data_through,
            "source": "Jeff Sackmann / Tennis Abstract ATP match data (CC BY-NC-SA 4.0), plus manual supplement",
            "notes": [
                "Dates are the estimated day of the final.",
                "Walkovers are excluded from head-to-head and win-loss records.",
                "Team events (ATP Cup, United Cup, Laver Cup, Davis Cup) do not count as titles.",
            ],
        },
        "players": list(PLAYERS.values()),
        "titles": titles,
        "h2h": h2h,
        "seasons": seasons,
    }


def validate(data: dict) -> list[str]:
    errors = []

    def check(label: str, pid: str, got: int, expected: int) -> None:
        ok = got >= expected if pid in ACTIVE else got == expected
        if not ok:
            errors.append(f"{label} {pid}: got {got}, expected {'at least ' if pid in ACTIVE else ''}{expected}")

    totals = Counter(t["player"] for t in data["titles"])
    for pid, n in EXPECTED["titles"].items():
        check("titles", pid, totals[pid], n)
    for level in ("G", "M", "F", "O"):
        counts = Counter(t["player"] for t in data["titles"] if t["level"] == level)
        for pid, n in EXPECTED[level].items():
            check(level, pid, counts[pid], n)
    wins = Counter((m["winner"], m["loser"]) for m in data["h2h"])
    for (a, b), (wa, wb) in EXPECTED["h2h"].items():
        if (wins[(a, b)], wins[(b, a)]) != (wa, wb):
            errors.append(f"h2h {a}-{b}: got {wins[(a, b)]}-{wins[(b, a)]}, expected {wa}-{wb}")
    return errors


def unchanged(data: dict) -> bool:
    """True if the output already holds the same data (ignoring the build date)."""
    if not OUTPUT.exists():
        return False
    old = json.loads(OUTPUT.read_text(encoding="utf-8"))
    strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}
    return strip(old) == strip(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download raw CSV files")
    args = parser.parse_args()

    data = build(load_rows(download(args.refresh)), load_supplement())
    errors = validate(data)
    if errors:
        sys.exit("validation failed:\n  " + "\n  ".join(errors))

    if unchanged(data):
        print(f"{OUTPUT.relative_to(ROOT)} is up to date")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(data['titles'])} titles, {len(data['h2h'])} h2h matches")


if __name__ == "__main__":
    main()
