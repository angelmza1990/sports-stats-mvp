"""Build the Open Era men's Grand Slam dataset used by tennis/grand-slams.

Reads every Grand Slam match since Roland Garros 1968 from Jeff Sackmann's ATP
match files. Slams the files don't cover yet are rebuilt from their Wikipedia
draw pages. Writes every final plus per-player match records for the front end.

Usage:
    python3 scripts/build_grand_slams.py            # use cached raw files
    python3 scripts/build_grand_slams.py --refresh  # re-download everything
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

from tennis_data import (
    OPEN_ERA_START, ROOT, SLAM_NAMES, SLAMS, ascii_key, download, edition_year, final_date,
    is_walkover, missing_slams, read_matches, slam_from_wikipedia,
)

OVERRIDES = ROOT / "data" / "manual" / "slam_nationality_overrides.csv"
OUTPUT = ROOT / "tennis" / "grand-slams" / "data" / "grand-slams.json"
FIRST_YEAR = 1968
TOP_N = 25  # players kept per match-record list

# IOC code -> (country name, ISO 3166 alpha-2 for flags; None = no modern flag).
COUNTRIES = {
    "ARG": ("Argentina", "ar"), "AUS": ("Australia", "au"), "AUT": ("Austria", "at"), "BEL": ("Belgium", "be"),
    "BLR": ("Belarus", "by"), "BRA": ("Brazil", "br"), "BUL": ("Bulgaria", "bg"), "CAN": ("Canada", "ca"),
    "CHI": ("Chile", "cl"), "CHN": ("China", "cn"), "COL": ("Colombia", "co"), "CRO": ("Croatia", "hr"),
    "CYP": ("Cyprus", "cy"), "CZE": ("Czech Republic", "cz"), "DEN": ("Denmark", "dk"), "ECU": ("Ecuador", "ec"),
    "ESP": ("Spain", "es"), "FIN": ("Finland", "fi"), "FRA": ("France", "fr"), "GBR": ("Great Britain", "gb"),
    "GER": ("Germany", "de"), "GRE": ("Greece", "gr"), "HUN": ("Hungary", "hu"), "IND": ("India", "in"),
    "ISR": ("Israel", "il"), "ITA": ("Italy", "it"), "JPN": ("Japan", "jp"), "KAZ": ("Kazakhstan", "kz"),
    "KOR": ("South Korea", "kr"), "MEX": ("Mexico", "mx"), "NED": ("Netherlands", "nl"), "NOR": ("Norway", "no"),
    "NZL": ("New Zealand", "nz"), "PAR": ("Paraguay", "py"), "PER": ("Peru", "pe"), "POL": ("Poland", "pl"),
    "POR": ("Portugal", "pt"), "ROU": ("Romania", "ro"), "RSA": ("South Africa", "za"), "RUS": ("Russia", "ru"),
    "SRB": ("Serbia", "rs"), "SUI": ("Switzerland", "ch"), "SVK": ("Slovakia", "sk"), "SWE": ("Sweden", "se"),
    "TCH": ("Czechoslovakia", "cz"), "UKR": ("Ukraine", "ua"), "URS": ("Soviet Union", None), "URU": ("Uruguay", "uy"),
    "USA": ("United States", "us"), "YUG": ("Yugoslavia", None), "ZIM": ("Zimbabwe", "zw"),
}

# Open Era titles through 2026, used as a sanity check. Active players are minimums.
EXPECTED_TITLES = {
    "Novak Djokovic": 24, "Rafael Nadal": 22, "Roger Federer": 20, "Pete Sampras": 14, "Bjorn Borg": 11,
    "Jimmy Connors": 8, "Ivan Lendl": 8, "Andre Agassi": 8, "John McEnroe": 7, "Mats Wilander": 7,
    "Boris Becker": 6, "Stefan Edberg": 6, "Rod Laver": 5, "John Newcombe": 5, "Ken Rosewall": 4,
    "Jim Courier": 4, "Guillermo Vilas": 4, "Carlos Alcaraz": 7, "Jannik Sinner": 5,
}
ACTIVE = {"Novak Djokovic", "Carlos Alcaraz", "Jannik Sinner"}
EXPECTED_EDITIONS_2026 = {"Australian Open": 58, "Roland Garros": 59, "Wimbledon": 58, "US Open": 59}  # no Wimbledon in 2020


def load_overrides() -> dict[str, list[tuple[str, date | None]]]:
    out = defaultdict(list)
    with OVERRIDES.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            until = datetime.strptime(row["until"], "%Y-%m-%d").date() if row["until"] else None
            out[row["player"]].append((row["ioc"], until))
    return out


def nationality(name: str, ioc: str, when: date, overrides: dict) -> str:
    for code, until in overrides.get(name, []):
        if until is None or when <= until:
            return code
    return ioc


def load_rows(refresh: bool) -> tuple[list[dict], list[str]]:
    paths = download(FIRST_YEAR, date.today().year, refresh)
    rows = read_matches(paths, lambda r: r["tourney_level"] == "G" and r["tourney_date"] >= OPEN_ERA_START)
    rows = [r for r in rows if r["tourney_name"] in SLAM_NAMES]

    known = {ascii_key(r[f"{side}_name"]): r[f"{side}_name"] for r in rows for side in ("winner", "loser")}
    added = []
    for slam, year in missing_slams(rows):
        try:
            extra = slam_from_wikipedia(slam, year, refresh, known)
        except LookupError as err:
            print(f"skipping {slam} {year}: {err}", file=sys.stderr)
            continue
        rows.extend(extra)
        added.append(f"{slam} {year}")
    return rows, added


def build(rows: list[dict], added: list[str]) -> dict:
    overrides = load_overrides()
    for r in rows:
        r["_slam"] = SLAM_NAMES[r["tourney_name"]]
        r["_year"] = edition_year(r)
        # A final estimated past New Year belongs to the edition's own year (the Dec 1977 AO ended Dec 31).
        r["_date"] = min(final_date(r), date(r["_year"], 12, 31))
        for side in ("winner", "loser"):
            r[f"_{side}_ioc"] = nationality(r[f"{side}_name"], r[f"{side}_ioc"], r["_date"], overrides)

    # Finals -> editions. Two Australian Opens were played in 1977 (January and December).
    finals = sorted((r for r in rows if r["round"] == "F"), key=lambda r: r["_date"])
    per_year = Counter((r["_slam"], r["_year"]) for r in finals)
    editions = []
    for r in finals:
        label = str(r["_year"])
        if per_year[(r["_slam"], r["_year"])] > 1:
            label += " (Dec)" if r["tourney_date"][4:6] == "12" else " (Jan)"
        editions.append({
            "slam": r["_slam"], "year": r["_year"], "label": label, "date": r["_date"].isoformat(),
            "champion": r["winner_name"], "championIoc": r["_winner_ioc"],
            "runnerUp": r["loser_name"], "runnerUpIoc": r["_loser_ioc"],
            "score": r["score"], "source": r.get("source", "atp"),
        })

    # Match records per player (walkovers excluded), per Slam and overall.
    record: dict[str, Counter] = defaultdict(Counter)
    player_iocs: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        if is_walkover(r["score"]):
            continue
        for side, result in (("winner", "won"), ("loser", "lost")):
            name = r[f"{side}_name"]
            record[name][(r["_slam"], result)] += 1
            record[name][("All", result)] += 1
            player_iocs[name][r[f"_{side}_ioc"]] += 1

    def top(scope: str) -> list[dict]:
        entries = [
            {"player": name, "ioc": player_iocs[name].most_common(1)[0][0],
             "won": c[(scope, "won")], "lost": c[(scope, "lost")]}
            for name, c in record.items() if c[(scope, "won")] + c[(scope, "lost")] > 0
        ]
        by_won = sorted(entries, key=lambda e: (-e["won"], e["lost"]))[:TOP_N]
        by_played = sorted(entries, key=lambda e: (-(e["won"] + e["lost"]), -e["won"]))[:TOP_N]
        keep = {e["player"]: e for e in by_won + by_played}
        return sorted(keep.values(), key=lambda e: -e["won"])

    used = {e["championIoc"] for e in editions} | {e["runnerUpIoc"] for e in editions}
    match_records = {scope: top(scope) for scope in ["All", *SLAMS]}
    used |= {e["ioc"] for lst in match_records.values() for e in lst}

    last = editions[-1]
    return {
        "meta": {
            "generated": date.today().isoformat(),
            "through": f"{last['slam']} {last['label']}",
            "sources": [
                "Jeff Sackmann / Tennis Abstract ATP match data (CC BY-NC-SA 4.0)",
                "Wikipedia draw pages (CC BY-SA 4.0)" + (f" for {', '.join(added)}" if added else ""),
            ],
            "fromWikipedia": added,
            "notes": [
                "Open Era men's singles, from Roland Garros 1968.",
                "Nationality is the one represented when each match was played.",
                "Walkovers are excluded from match records.",
            ],
        },
        "slams": SLAMS,
        "countries": {code: {"name": COUNTRIES[code][0], "flag": COUNTRIES[code][1]} for code in sorted(used) if code in COUNTRIES},
        "editions": editions,
        "matchRecords": match_records,
    }


def validate(data: dict) -> list[str]:
    errors = []
    eds = data["editions"]
    titles = Counter(e["champion"] for e in eds)
    for name, n in EXPECTED_TITLES.items():
        ok = titles[name] >= n if name in ACTIVE else titles[name] == n
        if not ok:
            errors.append(f"{name}: {titles[name]} titles, expected {'at least ' if name in ACTIVE else ''}{n}")
    counts = Counter(e["slam"] for e in eds if e["year"] <= 2026)
    for slam, n in EXPECTED_EDITIONS_2026.items():
        if counts[slam] != n:
            errors.append(f"{slam}: {counts[slam]} editions through 2026, expected {n}")
    unknown = {e[k] for e in eds for k in ("championIoc", "runnerUpIoc")} - set(data["countries"])
    if unknown:
        errors.append(f"countries missing from COUNTRIES: {sorted(unknown)}")
    for e in eds:
        if e["champion"] == e["runnerUp"] or not e["champion"]:
            errors.append(f"bad final: {e}")
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
    parser.add_argument("--refresh", action="store_true", help="re-download raw files")
    args = parser.parse_args()

    data = build(*load_rows(args.refresh))
    errors = validate(data)
    if errors:
        sys.exit("validation failed:\n  " + "\n  ".join(errors))
    if unchanged(data):
        print(f"{OUTPUT.relative_to(ROOT)} is up to date")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(data['editions'])} finals, through {data['meta']['through']}")


if __name__ == "__main__":
    main()
