"""Build the FIFA World Cup dataset used by football/world-cup.

Reads Wikipedia's World Cup pages (results by edition, finals, records and
statistics, top goalscorers, team and player appearances) and writes one
JSON file for the front end.

Usage:
    python3 scripts/build_world_cup.py            # use cached pages if present
    python3 scripts/build_world_cup.py --refresh  # re-download every page
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date

import wikitables as W
from build_football import COUNTRIES, RAW_DIR, ROOT, confederation, slug

OUTPUT = ROOT / "football" / "world-cup" / "data" / "world-cup.json"
PAGES = {
    "main": "FIFA World Cup",
    "finals": "List of FIFA World Cup finals",
    "records": "FIFA World Cup records and statistics",
    "scorers": "List of FIFA World Cup top goalscorers",
    "teams": "National team appearances in the FIFA World Cup",
    "players": "List of players who have appeared in the most FIFA World Cups",
}

# National teams that are not in the shared COUNTRIES table: (name, flagcdn code or None).
TEAMS = {
    "FRG": ("West Germany", "de"), "GDR": ("East Germany", None), "URS": ("Soviet Union", None), "YUG": ("Yugoslavia", None),
    "FRY": ("FR Yugoslavia", None), "SCG": ("Serbia and Montenegro", None), "TCH": ("Czechoslovakia", "cz"),
    "DEI": ("Dutch East Indies", None), "ZAI": ("Zaire", "cd"), "CIS": ("CIS", None), "CUB": ("Cuba", "cu"),
    "PRK": ("North Korea", "kp"), "HAI": ("Haiti", "ht"), "SLV": ("El Salvador", "sv"), "KUW": ("Kuwait", "kw"),
    "IRQ": ("Iraq", "iq"), "ANG": ("Angola", "ao"), "TRI": ("Trinidad and Tobago", "tt"), "CPV": ("Cape Verde", "cv"),
    "CUW": ("Curaçao", "cw"), "JOR": ("Jordan", "jo"), "UZB": ("Uzbekistan", "uz"), "IRL": ("Republic of Ireland", "ie"),
    "NIR": ("Northern Ireland", "gb-nir"), "WAL": ("Wales", "gb-wls"), "SCO": ("Scotland", "gb-sct"), "ENG": ("England", "gb-eng"),
    "TOG": ("Togo", "tg"), "ISR": ("Israel", "il"), "BIH": ("Bosnia and Herzegovina", "ba"), "SVK": ("Slovakia", "sk"),
    "SVN": ("Slovenia", "si"), "ISL": ("Iceland", "is"), "PAN": ("Panama", "pa"), "HON": ("Honduras", "hn"),
    "CRC": ("Costa Rica", "cr"), "JAM": ("Jamaica", "jm"), "NZL": ("New Zealand", "nz"), "GHA": ("Ghana", "gh"),
    "NOR": ("Norway", "no"), "BUL": ("Bulgaria", "bg"), "IDN": ("Indonesia", "id"), "RSA": ("South Africa", "za"),
}
EXTRA_CONFED = {"FRG": "UEFA", "GDR": "UEFA", "URS": "UEFA", "YUG": "UEFA", "FRY": "UEFA", "SCG": "UEFA", "TCH": "UEFA",
                "DEI": "AFC", "ZAI": "CAF", "CIS": "UEFA", "CUB": "CONCACAF", "PRK": "AFC", "HAI": "CONCACAF",
                "SLV": "CONCACAF", "KUW": "AFC", "IRQ": "AFC", "ANG": "CAF", "TRI": "CONCACAF", "CPV": "CAF",
                "CUW": "CONCACAF", "JOR": "AFC", "UZB": "AFC", "TOG": "CAF", "ISR": "AFC", "NZL": "OFC", "GHA": "CAF",
                "IDN": "AFC", "RSA": "CAF"}

# Titles through 2026, frozen; later editions may only add to them.
HISTORY_THROUGH = 2026
HISTORY = {"BRA": 5, "GER": 1, "FRG": 3, "ITA": 4, "ARG": 3, "FRA": 2, "URU": 2, "ESP": 2, "ENG": 1}


def team_name(code: str) -> tuple[str, str | None]:
    if code in TEAMS:
        return TEAMS[code]
    return COUNTRIES.get(code, (code, None))


def team_confed(code: str) -> str:
    return EXTRA_CONFED.get(code) or confederation(code)


def fetch(key: str, refresh: bool) -> str:
    title = PAGES[key]
    return W.fetch_raw(title, RAW_DIR / f"{slug(title)}.wiki", refresh)


def year_of(cell: str) -> int | None:
    m = re.match(r"\s*(\d{4})", W.plain(cell))
    return int(m.group(1)) if m else None


def score(cell: str) -> tuple[str | None, str | None, str | None]:
    """Final score, how it was decided ('extra time' / 'penalties') and the shoot-out score."""
    text = W.strip_refs(cell)
    m = re.search(r"(\d+)\s*[–-]\s*(\d+)", text)
    if not m:
        return None, None, None
    low = text.lower()
    pso = re.search(r"\{\{\s*pso\s*\|\s*(\d+)\s*[–-]\s*(\d+)", text, re.I)
    if pso:
        return f"{m.group(1)}–{m.group(2)}", "penalties", f"{pso.group(1)}–{pso.group(2)}"
    if "{{aet" in low or "a.e.t" in low or "dagger" in low or "FBCEB1" in cell.upper():
        return f"{m.group(1)}–{m.group(2)}", "extra time", None
    return f"{m.group(1)}–{m.group(2)}", None, None


def best_result(cell: str) -> str | None:
    label = re.search(r"Awards table sorting\|([^|}]+)", cell)
    years = re.findall(r"\[\[(\d{4}) FIFA World Cup", cell)
    text = label.group(1).strip() if label else W.plain(re.sub(r"^[^{\[]*?=\S+\s*", "", cell)).strip()
    if not text:
        return None
    return f"{text} ({', '.join(years)})" if years else text


def num(text: str) -> float | None:
    t = W.plain(text).replace(",", "").replace("−", "-")
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    return float(m.group(0)) if m else None


def build(refresh: bool) -> dict:
    main, finals_page, records = fetch("main", refresh), fetch("finals", refresh), fetch("records", refresh)
    scorers_page, teams_page, players_page = fetch("scorers", refresh), fetch("teams", refresh), fetch("players", refresh)

    # Editions: host(s), final, third place and number of teams.
    editions = {}
    for row in W.table_with_headers(main, "year", "host", "final", "third place", "teams"):
        if len(row) < 10:
            continue
        year = year_of(row[1]["text"])
        champion = W.flag_code(row[3]["text"])
        if not year or not champion:
            continue
        s, note, shootout = score(row[4]["text"] + row[4]["attrs"])
        editions[year] = {
            "year": year,
            "hosts": W.flag_codes(row[2]["text"]),
            "champion": champion, "runnerUp": W.flag_code(row[5]["text"]),
            "finalScore": s, "finalNote": note, "shootout": shootout,
            "third": W.flag_code(row[6]["text"]), "fourth": W.flag_code(row[8]["text"]),
            "teams": int(num(row[9]["text"]) or 0),
        }

    # Final venue and attendance.
    for row in W.table_with_headers(finals_page, "year", "winners", "runners-up", "venue"):
        year = year_of(row[0]["text"])
        if year in editions and len(row) >= 7:
            editions[year]["finalVenue"] = W.plain(row[4]["text"])
            editions[year]["finalCity"] = W.plain(row[5]["text"])
            editions[year]["finalAttendance"] = int(num(row[6]["text"]) or 0) or None

    # Matches and goals per tournament.
    for row in W.table_with_headers(records, "year", "matches", "goals", "average goals"):
        year = year_of(row[0]["text"])
        if year in editions and num(row[1]["text"]):
            editions[year]["matches"] = int(num(row[1]["text"]))
            editions[year]["goals"] = int(num(row[2]["text"]))

    # Attendance per tournament.
    for row in W.table_with_headers(records, "year", "hosts", "venues", "attendance"):
        year = year_of(row[0]["text"])
        if year in editions and len(row) >= 6 and num(row[3]["text"]):
            editions[year]["attendance"] = int(num(row[3]["text"]))
            editions[year]["avgAttendance"] = int(num(row[5]["text"]) or 0) or None

    # Top scorer(s), best player and winning coach per tournament.
    for row in W.table_with_headers(records, "year", "host", "champions", "winning coach", "most goals"):
        year = year_of(row[0]["text"])
        if year not in editions or len(row) < 7:
            continue
        editions[year]["coach"] = W.person(row[3]["text"])
        best = W.person(row[6]["text"])
        editions[year]["bestPlayer"] = None if not best or "not awarded" in best.lower() else best

    # Top scorer(s) of each tournament (joint winners share a tournament).
    for row in W.table_with_headers(scorers_page, "world cup", "player", "team", "goals"):
        m = re.search(r"(\d{4})", W.plain(row[0]["text"]))
        if not m or int(m.group(1)) not in editions or num(row[3]["text"]) is None:
            continue
        e = editions[int(m.group(1))]
        e.setdefault("topScorers", []).append({"player": W.person(row[1]["text"]), "team": W.flag_code(row[2]["text"])})
        e["topScorerGoals"] = int(num(row[3]["text"]))

    # All-time team records (3 points per win).
    alltime = []
    for row in W.table_with_headers(records, "rank", "team")[1:]:
        code = W.flag_code(row[1]["text"]) if len(row) > 10 else None
        if not code or num(row[3]["text"]) is None:
            continue
        v = [int(num(row[i]["text"]) or 0) for i in range(2, 11)]
        alltime.append({"team": code, "part": v[0], "pld": v[1], "w": v[2], "d": v[3], "l": v[4], "gf": v[5], "ga": v[6], "pts": v[8]})
        if len(alltime) >= 120:
            break

    # Team appearances, debut and best result.
    appearances = []
    for row in W.table_with_headers(teams_page, "team", "appearances", "debut"):
        code = W.flag_code(row[0]["text"])
        if not code or num(row[1]["text"]) is None or len(row) < 7:
            continue
        appearances.append({
            "team": code, "apps": int(num(row[1]["text"])), "streak": int(num(row[2]["text"]) or 0),
            "debut": year_of(row[4]["text"]), "best": best_result(row[6]["attrs"] + " " + row[6]["text"]),
        })

    # Players: all-time top scorers, most matches, most tournaments.
    scorers = []
    for row in W.table_with_headers(scorers_page, "rank", "player", "team", "goals", "matches"):
        if len(row) < 7 or num(row[3]["text"]) is None:
            continue
        scorers.append({
            "player": W.person(row[1]["text"]), "team": W.flag_code(row[2]["text"]),
            "goals": int(num(row[3]["text"])), "matches": int(num(row[4]["text"]) or 0),
            "tournaments": W.plain(row[6]["text"]),
        })
    matches = []
    for row in W.table_with_headers(players_page, "rank", "team", "player", "matches", "tournaments"):
        if len(row) < 5 or num(row[3]["text"]) is None:
            continue
        matches.append({"player": W.person(row[2]["text"]), "team": W.flag_code(row[1]["text"]),
                        "matches": int(num(row[3]["text"])), "tournaments": W.plain(row[4]["text"])})
    tournaments = []
    for row in W.table_with_headers(players_page, "team", "player", "in squad", "played"):
        if len(row) < 5 or num(row[2]["text"]) is None:
            continue
        tournaments.append({"player": W.person(row[1]["text"]), "team": W.flag_code(row[0]["text"]),
                            "squads": int(num(row[2]["text"])), "played": int(num(row[3]["text"]) or 0),
                            "tournaments": W.plain(row[4]["text"])})

    eds = [editions[y] for y in sorted(editions)]
    codes = set()
    for e in eds:
        codes |= {e["champion"], e["runnerUp"], e["third"], e["fourth"], *e["hosts"]}
        codes |= {s["team"] for s in e.get("topScorers", [])}
    codes |= {r["team"] for r in alltime} | {a["team"] for a in appearances}
    codes |= {p["team"] for p in scorers + matches + tournaments}
    codes.discard(None)
    unknown = sorted(c for c in codes if c not in TEAMS and c not in COUNTRIES)
    if unknown:
        print(f"teams without a name/flag mapping: {unknown}", file=sys.stderr)

    return {
        "meta": {
            "generated": date.today().isoformat(),
            "through": str(eds[-1]["year"]),
            "sources": [f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}" for t in PAGES.values()],
            "pointsRule": "3 points per win, 1 per draw (applied to every tournament); shoot-outs count as draws",
        },
        "teams": {c: {"name": team_name(c)[0], "flag": team_name(c)[1], "confederation": team_confed(c)} for c in sorted(codes)},
        "editions": eds,
        "alltime": alltime,
        "appearances": appearances,
        "scorers": scorers,
        "playerMatches": matches,
        "playerTournaments": tournaments,
    }


def validate(data: dict) -> list[str]:
    errors = []
    years = [e["year"] for e in data["editions"]]
    expected = [y for y in range(1930, years[-1] + 1, 4) if y not in (1942, 1946)]
    if years != expected:
        errors.append(f"editions are not the expected years: missing {sorted(set(expected) - set(years))}")
    titles = Counter(e["champion"] for e in data["editions"] if e["year"] <= HISTORY_THROUGH)
    if titles != Counter(HISTORY):
        errors.append(f"titles through {HISTORY_THROUGH} differ: got {dict(titles)}")
    for e in data["editions"]:
        for key in ("runnerUp", "third", "finalScore", "matches", "goals", "teams", "topScorers"):
            if not e.get(key):
                errors.append(f"{e['year']}: missing {key}")
        if not e["hosts"]:
            errors.append(f"{e['year']}: no host")
    if len(data["alltime"]) < 60 or data["alltime"][0]["team"] != "BRA":
        errors.append("all-time table looks wrong")
    for label, rows in (("scorers", data["scorers"]), ("player matches", data["playerMatches"])):
        if len(rows) < 20 or any(not r["player"] for r in rows):
            errors.append(f"{label} table incomplete")
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
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(data['editions'])} tournaments, through {data['meta']['through']}")


if __name__ == "__main__":
    main()
