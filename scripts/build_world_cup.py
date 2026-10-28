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
import csv
import io
import json
import re
import sys
import urllib.request
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


# Every match: Joshua Fjelstul's World Cup Database (CC BY-SA 4.0) through 2022, then each tournament's Wikipedia
# group and knockout pages, whose football boxes name the teams by FIFA code.
FJELSTUL_URL = "https://raw.githubusercontent.com/jfjelstul/worldcup/master/data-csv/matches.csv"
FJELSTUL_CACHE = ROOT / "data" / "raw" / "fjelstul" / "world-cup-men-matches.csv"
FJELSTUL_LAST = 2022
FJELSTUL_NAMES = {"West Germany": "FRG", "East Germany": "GDR", "Soviet Union": "URS", "Czechoslovakia": "TCH",
                  "Yugoslavia": "YUG", "FR Yugoslavia": "FRY", "Serbia and Montenegro": "SCG", "Dutch East Indies": "DEI",
                  "Zaire": "ZAI", "Republic of Ireland": "IRL", "United States": "USA", "South Korea": "KOR",
                  "North Korea": "PRK", "Ivory Coast": "CIV", "Iran": "IRN", "China": "CHN", "Czech Republic": "CZE",
                  "Bosnia and Herzegovina": "BIH", "United Arab Emirates": "UAE", "Trinidad and Tobago": "TRI"}
STAGES = {"group stage": "Group stage", "first group stage": "Group stage", "second group stage": "Second group stage",
          "final round": "Final round", "round of 32": "Round of 32", "round of 16": "Round of 16",
          "quarter-final": "Quarter-finals", "quarter-finals": "Quarter-finals", "semi-final": "Semi-finals",
          "semi-finals": "Semi-finals", "third-place match": "Third place", "final": "Final"}


def fjelstul_matches(refresh: bool, codes: dict[str, str]) -> list[list]:
    """Men's World Cup matches through 2022, kept on disk as just those rows."""
    if refresh or not FJELSTUL_CACHE.exists():
        print(f"downloading {FJELSTUL_URL}", file=sys.stderr)
        try:
            req = urllib.request.Request(FJELSTUL_URL, headers={"User-Agent": W.USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                rows = list(csv.reader(io.StringIO(resp.read().decode("utf-8"))))
            head, body = rows[0], [r for r in rows[1:] if "Men's" in r[2]]
            FJELSTUL_CACHE.parent.mkdir(parents=True, exist_ok=True)
            with FJELSTUL_CACHE.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows([head, *body])
        except OSError as err:
            if not FJELSTUL_CACHE.exists():
                raise
            print(f"warning: could not download the World Cup Database ({err}); using the saved copy", file=sys.stderr)
    by_name = {name: code for code, name in codes.items()}
    by_name.update(FJELSTUL_NAMES)
    out = []
    with FJELSTUL_CACHE.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            home, away = by_name.get(r["home_team_name"]), by_name.get(r["away_team_name"])
            if not home or not away:
                raise SystemExit(f"World Cup Database: no code for {r['home_team_name']} or {r['away_team_name']}")
            out.append(match_row(int(r["tournament_id"][3:]), STAGES[r["stage_name"]], r["match_date"], home, away,
                                 int(r["home_team_score"]), int(r["away_team_score"]), r["extra_time"] == "1",
                                 (int(r["home_team_score_penalties"]), int(r["away_team_score_penalties"])) if r["penalty_shootout"] == "1" else None))
    return out


def match_row(year, stage, day, home, away, hs, as_, aet, pens) -> list:
    """[year, stage, date, home, away, home goals, away goals, extra time (0/1), shoot-out or null]."""
    return [year, stage, day, home, away, hs, as_, int(aet), list(pens) if pens else None]


def wiki_matches(year: int, refresh: bool) -> list[list]:
    """A tournament's matches from its Wikipedia group pages, round-of-32 page, knockout stage page and final."""
    titles = [f"{year} FIFA World Cup Group {g}" for g in "ABCDEFGHIJKL"]
    titles += [f"{year} FIFA World Cup round of 32", f"{year} FIFA World Cup knockout stage", f"{year} FIFA World Cup final"]
    out, seen = [], set()
    for title in titles:
        try:
            text = W.fetch_raw(title, RAW_DIR / f"{slug(title)}.wiki", refresh)
        except Exception as err:  # noqa: BLE001 - fewer groups, or no round of 32
            print(f"note: {title}: {err}", file=sys.stderr)
            continue
        heads = [(m.start(), m.group(1).strip()) for m in re.finditer(r"^==\s*([^=].*?)\s*==\s*$", text, re.M)]
        for m in re.finditer(r"\{\{\s*#invoke:\s*football box\s*\|\s*main(.*?)\n\}\}", text, re.S | re.I):
            box = m.group(1)
            field = lambda k: (re.search(r"^\|\s*" + k + r"\s*=\s*(.*)$", box, re.M) or [None, ""])[1].strip()  # noqa: E731
            t1, t2 = re.search(r"\|\s*([A-Z]{3})\s*\}\}", field("team1")), re.search(r"\|\s*([A-Z]{3})\s*\}\}", field("team2"))
            d = re.search(r"(\d{4})\|(\d{1,2})\|(\d{1,2})", field("date"))
            sc = re.findall(r"(\d+)\s*[–-]\s*(\d+)", W.plain(field("score")) or field("score"))
            if not (t1 and t2 and d and sc):
                continue  # not played yet
            heading = next((h for pos, h in reversed(heads) if pos < m.start()), "")
            if title.endswith("final"):
                stage = "Final"
            elif "Group" in title:
                stage = "Group stage"
            elif "round of 32" in title:
                stage = "Round of 32"
            else:
                stage = next((v for k, v in STAGES.items() if heading.lower().replace("quarterfinals", "quarter-finals")
                              .replace("semifinals", "semi-finals").replace("match for third place", "third-place match") == k), None)
                if not stage:
                    continue
            day = f"{d.group(1)}-{int(d.group(2)):02d}-{int(d.group(3)):02d}"
            key = (day, t1.group(1), t2.group(1))
            if key in seen:
                continue
            seen.add(key)
            ps = re.search(r"(\d+)\s*[–-]\s*(\d+)", field("penaltyscore"))
            out.append(match_row(year, stage, day, t1.group(1), t2.group(1), int(sc[-1][0]), int(sc[-1][1]),
                                 field("aet").lower() in ("yes", "y"), (int(ps.group(1)), int(ps.group(2))) if ps else None))
    return out


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
    matches_played = []
    for row in W.table_with_headers(players_page, "rank", "team", "player", "matches", "tournaments"):
        if len(row) < 5 or num(row[3]["text"]) is None:
            continue
        matches_played.append({"player": W.person(row[2]["text"]), "team": W.flag_code(row[1]["text"]),
                        "matches": int(num(row[3]["text"])), "tournaments": W.plain(row[4]["text"])})
    tournaments = []
    for row in W.table_with_headers(players_page, "team", "player", "in squad", "played"):
        if len(row) < 5 or num(row[2]["text"]) is None:
            continue
        tournaments.append({"player": W.person(row[1]["text"]), "team": W.flag_code(row[0]["text"]),
                            "squads": int(num(row[2]["text"])), "played": int(num(row[3]["text"]) or 0),
                            "tournaments": W.plain(row[4]["text"])})

    eds = [editions[y] for y in sorted(editions)]
    known = {c: team_name(c)[0] for c in set(TEAMS) | set(COUNTRIES)}
    matches = fjelstul_matches(refresh, known)
    for y in sorted(y for y in editions if y > FJELSTUL_LAST):
        matches += wiki_matches(y, refresh)
    matches.sort(key=lambda m: (m[2], m[0]))
    codes = set()
    for e in eds:
        codes |= {e["champion"], e["runnerUp"], e["third"], e["fourth"], *e["hosts"]}
        codes |= {s["team"] for s in e.get("topScorers", [])}
    codes |= {r["team"] for r in alltime} | {a["team"] for a in appearances}
    codes |= {p["team"] for p in scorers + matches_played + tournaments}
    codes |= {m[3] for m in matches} | {m[4] for m in matches}
    codes.discard(None)
    unknown = sorted(c for c in codes if c not in TEAMS and c not in COUNTRIES)
    if unknown:
        print(f"teams without a name/flag mapping: {unknown}", file=sys.stderr)

    return {
        "meta": {
            "generated": date.today().isoformat(),
            "through": str(eds[-1]["year"]),
            "sources": [f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}" for t in PAGES.values()],
            "matchSource": {"label": "The Fjelstul World Cup Database", "url": "https://github.com/jfjelstul/worldcup",
                            "through": FJELSTUL_LAST},
            "matchFields": ["year", "stage", "date", "home", "away", "homeGoals", "awayGoals", "extraTime", "shootout"],
            "pointsRule": "3 points per win, 1 per draw (applied to every tournament); shoot-outs count as draws",
        },
        "teams": {c: {"name": team_name(c)[0], "flag": team_name(c)[1], "confederation": team_confed(c)} for c in sorted(codes)},
        "editions": eds,
        "alltime": alltime,
        "appearances": appearances,
        "scorers": scorers,
        "playerMatches": matches_played,
        "matches": matches,
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
    per_year = Counter(m[0] for m in data["matches"])
    for e in data["editions"]:
        if per_year[e["year"]] != e["matches"]:
            errors.append(f"{e['year']}: {per_year[e['year']]} matches listed, the records page counts {e['matches']}")
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
