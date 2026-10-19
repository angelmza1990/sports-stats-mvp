"""Build the Open Era Grand Slam datasets used by tennis/grand-slams (men) and tennis/grand-slams-women.

Reads every Grand Slam match since Roland Garros 1968 from Jeff Sackmann's ATP
and WTA match files. Slams the files don't cover yet are rebuilt from their
Wikipedia draw pages. Writes every final plus per-player match records.

Usage:
    python3 scripts/build_grand_slams.py              # both tours, cached raw files
    python3 scripts/build_grand_slams.py --tour wta   # women only
    python3 scripts/build_grand_slams.py --refresh    # re-download everything
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
    OPEN_ERA_START, ROOT, SLAM_NAMES, SLAMS, ascii_key, country_at, download, edition_year, final_date,
    is_walkover, missing_slams, read_matches, slam_from_wikipedia,
)

OVERRIDES = {
    "atp": ROOT / "data" / "manual" / "slam_nationality_overrides.csv",
    "wta": ROOT / "data" / "manual" / "wta_nationality_overrides.csv",
}
OUTPUTS = {
    "atp": ROOT / "tennis" / "grand-slams" / "data" / "grand-slams.json",
    "wta": ROOT / "tennis" / "grand-slams-women" / "data" / "grand-slams-women.json",
}
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
    "ARM": ("Armenia", "am"), "BIH": ("Bosnia and Herzegovina", "ba"), "EGY": ("Egypt", "eg"), "EST": ("Estonia", "ee"),
    "GEO": ("Georgia", "ge"), "INA": ("Indonesia", "id"), "IRL": ("Ireland", "ie"), "LAT": ("Latvia", "lv"),
    "LTU": ("Lithuania", "lt"), "LUX": ("Luxembourg", "lu"), "MAR": ("Morocco", "ma"), "MDA": ("Moldova", "md"),
    "MNE": ("Montenegro", "me"), "MON": ("Monaco", "mc"), "PHI": ("Philippines", "ph"), "PUR": ("Puerto Rico", "pr"),
    "SLO": ("Slovenia", "si"), "THA": ("Thailand", "th"), "TPE": ("Chinese Taipei", "tw"), "TUN": ("Tunisia", "tn"),
    "UZB": ("Uzbekistan", "uz"), "VEN": ("Venezuela", "ve"), "HKG": ("Hong Kong", "hk"), "BAH": ("Bahamas", "bs"),
    "POR": ("Portugal", "pt"), "RHO": ("Rhodesia", None), "FRG": ("West Germany", "de"), "IRI": ("Iran", "ir"),
    "ALG": ("Algeria", "dz"), "TUR": ("Turkey", "tr"), "ISL": ("Iceland", "is"), "SRI": ("Sri Lanka", "lk"),
    "PAK": ("Pakistan", "pk"), "LIB": ("Lebanon", "lb"), "BAR": ("Barbados", "bb"), "JAM": ("Jamaica", "jm"),
    "DOM": ("Dominican Republic", "do"), "ESA": ("El Salvador", "sv"), "BOL": ("Bolivia", "bo"), "CRC": ("Costa Rica", "cr"),
    "GUA": ("Guatemala", "gt"), "MKD": ("North Macedonia", "mk"), "KOS": ("Kosovo", "xk"), "QAT": ("Qatar", "qa"),
}

# Open Era titles through 2026, used as a sanity check. Active players are minimums.
EXPECTED_TITLES = {
    "atp": {
        "Novak Djokovic": 24, "Rafael Nadal": 22, "Roger Federer": 20, "Pete Sampras": 14, "Bjorn Borg": 11,
        "Jimmy Connors": 8, "Ivan Lendl": 8, "Andre Agassi": 8, "John McEnroe": 7, "Mats Wilander": 7,
        "Boris Becker": 6, "Stefan Edberg": 6, "Rod Laver": 5, "John Newcombe": 5, "Ken Rosewall": 4,
        "Jim Courier": 4, "Guillermo Vilas": 4, "Carlos Alcaraz": 7, "Jannik Sinner": 5,
    },
    "wta": {
        "Serena Williams": 23, "Steffi Graf": 22, "Chris Evert": 18, "Martina Navratilova": 18, "Margaret Court": 11,
        "Monica Seles": 9, "Billie Jean King": 8, "Evonne Goolagong": 7, "Justine Henin": 7, "Venus Williams": 7,
        "Martina Hingis": 5, "Maria Sharapova": 5, "Naomi Osaka": 4, "Kim Clijsters": 4, "Iga Swiatek": 6,
        "Aryna Sabalenka": 4, "Lindsay Davenport": 3, "Jennifer Capriati": 3, "Arantxa Sanchez Vicario": 4,
    },
}
ACTIVE = {"Novak Djokovic", "Carlos Alcaraz", "Jannik Sinner", "Naomi Osaka", "Iga Swiatek", "Aryna Sabalenka"}
EXPECTED_EDITIONS_2026 = {"Australian Open": 58, "Roland Garros": 59, "Wimbledon": 58, "US Open": 59}  # no Wimbledon in 2020


def load_overrides(tour: str = "atp") -> dict[str, list[tuple[str, date | None]]]:
    out = defaultdict(list)
    with OVERRIDES[tour].open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            until = datetime.strptime(row["until"], "%Y-%m-%d").date() if row["until"] else None
            out[row["player"]].append((row["ioc"], until))
    return out


def nationality(name: str, ioc: str, when: date, overrides: dict) -> str:
    for code, until in overrides.get(name, []):
        if until is None or when <= until:
            return code
    return "GER" if ioc == "FRG" else country_at(ioc, when)


def load_rows(refresh: bool, tour: str = "atp") -> tuple[list[dict], list[str]]:
    paths = download(FIRST_YEAR, date.today().year, refresh, tour)
    rows = read_matches(paths, lambda r: r["tourney_level"] == "G" and r["tourney_date"] >= OPEN_ERA_START)
    rows = [r for r in rows if r["tourney_name"] in SLAM_NAMES]

    known = {ascii_key(r[f"{side}_name"]): r[f"{side}_name"] for r in rows for side in ("winner", "loser")}
    iocs = {r[f"{side}_name"]: r[f"{side}_ioc"] for r in rows for side in ("winner", "loser")}
    added = []
    for slam, year in missing_slams(rows):
        try:
            extra = slam_from_wikipedia(slam, year, refresh, known, tour, iocs)
        except LookupError as err:
            print(f"skipping {slam} {year}: {err}", file=sys.stderr)
            continue
        rows.extend(extra)
        added.append(f"{slam} {year}")
    return rows, added


def build(rows: list[dict], added: list[str], tour: str = "atp") -> dict:
    overrides = load_overrides(tour)
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
            "event": r["_slam"], "year": r["_year"], "label": label, "date": r["_date"].isoformat(),
            "champion": r["winner_name"], "championIoc": r["_winner_ioc"],
            "runnerUp": r["loser_name"], "runnerUpIoc": r["_loser_ioc"],
            "score": r["score"], "surface": r["surface"], "source": r.get("source", "match data"),
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
            "through": f"{last['event']} {last['label']}",
            "tour": tour,
            "sources": [
                f"Jeff Sackmann / Tennis Abstract {tour.upper()} match data (CC BY-NC-SA 4.0)",
                "Wikipedia draw pages (CC BY-SA 4.0)" + (f" for {', '.join(added)}" if added else ""),
            ],
            "fromWikipedia": added,
            "notes": [
                f"Open Era {'men' if tour == 'atp' else 'women'}'s singles, from Roland Garros 1968.",
                "Nationality is the one represented when each match was played.",
                "Walkovers are excluded from match records.",
            ],
        },
        "events": [{"key": s, "current": True} for s in SLAMS],
        "tabs": [{"key": "All", "label": "All Slams"}] + [{"key": s, "label": s} for s in SLAMS],
        "colorBy": "event",
        "colors": SLAMS,
        "countries": {code: {"name": COUNTRIES[code][0], "flag": COUNTRIES[code][1]} for code in sorted(used) if code in COUNTRIES},
        "editions": editions,
        "matchRecords": match_records,
    }


def validate(data: dict, tour: str = "atp") -> list[str]:
    errors = []
    eds = data["editions"]
    titles = Counter(e["champion"] for e in eds)
    for name, n in EXPECTED_TITLES[tour].items():
        ok = titles[name] >= n if name in ACTIVE else titles[name] == n
        if not ok:
            errors.append(f"{name}: {titles[name]} titles, expected {'at least ' if name in ACTIVE else ''}{n}")
    counts = Counter(e["event"] for e in eds if e["year"] <= 2026)
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


def unchanged(data: dict, output: Path) -> bool:
    """True if the output already holds the same data (ignoring the build date)."""
    if not output.exists():
        return False
    old = json.loads(output.read_text(encoding="utf-8"))
    strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}
    return strip(old) == strip(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download raw files")
    parser.add_argument("--tour", choices=["atp", "wta"], action="append", help="default: both")
    args = parser.parse_args()

    failed = False
    for tour in args.tour or ["atp", "wta"]:
        output = OUTPUTS[tour]
        data = build(*load_rows(args.refresh, tour), tour)
        errors = validate(data, tour)
        if errors:
            print(f"{tour}: validation failed:\n  " + "\n  ".join(errors), file=sys.stderr)
            failed = True
            continue
        if unchanged(data, output):
            print(f"{output.relative_to(ROOT)} is up to date")
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print(f"wrote {output.relative_to(ROOT)}: {len(data['editions'])} finals, through {data['meta']['through']}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
