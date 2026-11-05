"""Build football/national-teams: every men's international match since 1872, head to head and Elo ratings.

Reads Mart Jürisoo's international results database (https://github.com/martj42/international_results, CC0):
every full international with its date, teams, score, tournament and venue, plus the penalty shoot-outs. Keeps the
national teams of FIFA and of the confederations (and historical ones such as East Germany), and writes:

  data/matches.json  every match, compacted, for the head-to-head explorer and the all-time table
  data/elo.json      World Football Elo ratings worked out here, match by match (eloratings.net's formula)
  data/goals.json    the scorers of the competitive matches (the database has no scorers for friendlies) and the shoot-outs

Usage:
    python3 scripts/build_national_teams.py            # use the saved copy if present
    python3 scripts/build_national_teams.py --refresh  # download the database again
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import urllib.request
from collections import Counter
from datetime import date

from build_football import COUNTRIES, ROOT
from build_tournaments import MORE_TEAMS
from build_world_cup import TEAMS

BASE = "https://raw.githubusercontent.com/martj42/international_results/master/"
RAW = ROOT / "data" / "raw" / "international"
OUT = ROOT / "football" / "national-teams" / "data"
DAY0 = date(1872, 1, 1).toordinal()

# Names in the database -> flagcdn codes, for teams the site's other tables don't name (None: no flag today).
EXTRA_FLAGS = {
    "Malawi": "mw", "Tanzania": "tz", "Oman": "om", "Malta": "mt", "Botswana": "bw", "Mauritius": "mu", "Benin": "bj", "Madagascar": "mg",
    "Guyana": "gy", "Cambodia": "kh", "Moldova": "md", "Sierra Leone": "sl", "Lesotho": "ls", "Faroe Islands": "fo", "Eswatini": "sz",
    "Mauritania": "mr", "Nepal": "np", "Yemen": "ye", "Gambia": "gm", "Grenada": "gd", "Niger": "ne", "Liechtenstein": "li", "Palestine": "ps",
    "Taiwan": "tw", "Tahiti": "pf", "Saint Vincent and the Grenadines": "vc", "Maldives": "mv", "Antigua and Barbuda": "ag", "Saint Lucia": "lc",
    "Andorra": "ad", "Laos": "la", "Saint Kitts and Nevis": "kn", "San Marino": "sm", "Burundi": "bi", "Vanuatu": "vu", "Dominica": "dm",
    "Solomon Islands": "sb", "Tajikistan": "tj", "Bermuda": "bm", "Kyrgyzstan": "kg", "Guinea-Bissau": "gw", "Seychelles": "sc",
    "Turkmenistan": "tm", "Gibraltar": "gi", "Papua New Guinea": "pg", "Aruba": "aw", "Comoros": "km", "Macau": "mo", "Afghanistan": "af",
    "Chad": "td", "Brunei": "bn", "Somalia": "so", "British Virgin Islands": "vg", "Guam": "gu", "Cayman Islands": "ky", "Djibouti": "dj",
    "Bhutan": "bt", "Anguilla": "ai", "Timor-Leste": "tl", "United States Virgin Islands": "vi", "Eritrea": "er", "São Tomé and Príncipe": "st",
    "Bahamas": "bs", "Montserrat": "ms", "Turks and Caicos Islands": "tc", "Cook Islands": "ck", "American Samoa": "as",
    "German DR": None, "Vietnam Republic": None, "Yemen DPR": None,
    # Members of a confederation that are not FIFA members (they play the Gold Cup, the Nations League or the AFC's cups).
    "Martinique": "mq", "Guadeloupe": "gp", "French Guiana": "gf", "Saint Martin": "mf", "Sint Maarten": "sx", "Bonaire": "bq",
    "New Caledonia": "nc", "Northern Mariana Islands": "mp", "Zanzibar": None, "Réunion": "re",
}
# Tournament weights (eloratings.net): K 60 World Cup, 50 continental championships and the Confederations Cup,
# 40 their qualifiers and the Nations Leagues, 30 other tournaments, 20 friendlies.
MAJOR = ("Copa América", "UEFA Euro", "African Cup of Nations", "AFC Asian Cup", "Gold Cup", "CONCACAF Championship",
         "Confederations Cup", "Oceania Nations Cup")
ELO_START, ELO_HOME = 1500, 100
# A team's first match: 1500 for the first twenty teams, then the 25th percentile of the teams already rated. Starting
# every newcomer at 1500 hands points to the established teams as the newcomers lose, and inflates the ratings over time.
NEWCOMER_QUANTILE = 0.25
CHART_MIN = 300  # teams with fewer matches get no line in the Elo chart
TEAM_SCORERS_MIN = 100  # teams with this many matches get their own top-scorer list
SHOOTOUT_MIN = 5  # shoot-outs a team needs for the best-record ranking


def scope(t: str) -> str:
    """The goals section's competitions: the World Cup, the continental championships, qualifiers and the rest."""
    if t == "FIFA World Cup":
        return "wc"
    if t in MAJOR and t != "Confederations Cup":
        return "cont"
    if "qualification" in t:
        return "qual"
    return "other"


def weight(t: str) -> int:
    if t == "FIFA World Cup":
        return 60
    if "qualification" in t:
        return 40
    if t in MAJOR:
        return 50
    if "Nations League" in t:
        return 40
    return 20 if t == "Friendly" else 30


def fetch(name: str, refresh: bool) -> list[dict]:
    path = RAW / f"{name}.csv"
    if refresh or not path.exists():
        try:
            with urllib.request.urlopen(BASE + f"{name}.csv", timeout=60) as resp:
                body = resp.read()
            RAW.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        except OSError as err:
            if not path.exists():
                raise
            print(f"warning: could not download {name}.csv ({err}); using the saved copy", file=sys.stderr)
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def team_table() -> dict[str, str | None]:
    """Every national team the page keeps: name -> flagcdn code (None for historical teams)."""
    out = {}
    for table in (COUNTRIES, TEAMS, MORE_TEAMS):
        for name, flag in table.values():
            out.setdefault(name, flag)
    out.update({"Ivory Coast": "ci", "DR Congo": "cd", "Czech Republic": "cz", "North Macedonia": "mk", "Kosovo": "xk",
                "Republic of Ireland": "ie", "Northern Ireland": "gb-nir", "Wales": "gb-wls", "Scotland": "gb-sct", "England": "gb-eng",
                "Germany": "de", "Russia": "ru", "Serbia": "rs", "Czechoslovakia": None, "Soviet Union": None, "Yugoslavia": None,
                "United States": "us", "South Korea": "kr", "North Korea": "kp", "Iran": "ir", "China PR": "cn", "Hong Kong": "hk",
                "Curaçao": "cw", "Suriname": "sr", "Kazakhstan": "kz", "Uzbekistan": "uz", "Armenia": "am", "Albania": "al",
                "Georgia": "ge", "Belarus": "by", "Latvia": "lv", "Lithuania": "lt", "Estonia": "ee", "Luxembourg": "lu",
                "Cyprus": "cy", "Montenegro": "me", "Ukraine": "ua", "Azerbaijan": "az", "Iceland": "is", "Cape Verde": "cv",
                "Gabon": "ga", "Guinea": "gn", "Equatorial Guinea": "gq", "Congo": "cg", "Central African Republic": "cf",
                "Burkina Faso": "bf", "Togo": "tg", "Mali": "ml", "Liberia": "lr", "Sudan": "sd", "South Sudan": "ss", "Libya": "ly",
                "Namibia": "na", "Zambia": "zm", "Zimbabwe": "zw", "Mozambique": "mz", "Angola": "ao", "Uganda": "ug", "Kenya": "ke",
                "Rwanda": "rw", "Ethiopia": "et", "Senegal": "sn", "Ghana": "gh", "Nigeria": "ng", "Cameroon": "cm", "Tunisia": "tn",
                "Morocco": "ma", "Algeria": "dz", "Egypt": "eg", "South Africa": "za", "Myanmar": "mm", "Vietnam": "vn",
                "Thailand": "th", "Malaysia": "my", "Singapore": "sg", "Indonesia": "id", "Philippines": "ph", "India": "in",
                "Pakistan": "pk", "Bangladesh": "bd", "Sri Lanka": "lk", "Mongolia": "mn", "Syria": "sy", "Lebanon": "lb",
                "Jordan": "jo", "Iraq": "iq", "Kuwait": "kw", "Bahrain": "bh", "Qatar": "qa", "Saudi Arabia": "sa",
                "United Arab Emirates": "ae", "Israel": "il", "Fiji": "fj", "Samoa": "ws", "Tonga": "to", "New Zealand": "nz",
                "Australia": "au", "Haiti": "ht", "Jamaica": "jm", "Trinidad and Tobago": "tt", "Barbados": "bb", "Belize": "bz",
                "Guatemala": "gt", "Honduras": "hn", "El Salvador": "sv", "Nicaragua": "ni", "Costa Rica": "cr", "Panama": "pa",
                "Cuba": "cu", "Dominican Republic": "do", "Puerto Rico": "pr", "Canada": "ca", "Mexico": "mx", "Venezuela": "ve",
                "Bolivia": "bo", "Paraguay": "py", "Uruguay": "uy", "Argentina": "ar", "Brazil": "br", "Chile": "cl", "Peru": "pe",
                "Ecuador": "ec", "Colombia": "co"})
    out.update(EXTRA_FLAGS)
    return out


def build(refresh: bool) -> None:
    flags = team_table()
    results = fetch("results", refresh)
    shootouts = {(r["date"], r["home_team"], r["away_team"]): r["winner"] for r in fetch("shootouts", refresh)}
    rows = [r for r in results if r["home_score"] not in ("NA", "") and r["home_team"] in flags and r["away_team"] in flags]
    rows.sort(key=lambda r: r["date"])
    played = Counter(t for r in rows for t in (r["home_team"], r["away_team"]))
    names = sorted(played, key=lambda n: (-played[n], n))
    idx = {n: i for i, n in enumerate(names)}
    tourneys = [t for t, _ in Counter(r["tournament"] for r in rows).most_common()]
    tidx = {t: i for i, t in enumerate(tourneys)}

    rating: dict[str, float] = {}
    yearly: dict[str, dict[int, int]] = {}
    peaks: dict[str, dict] = {}
    upsets, matches = [], []
    for r in rows:
        h, a = r["home_team"], r["away_team"]
        hs, as_ = int(r["home_score"]), int(r["away_score"])
        neutral = r["neutral"] == "TRUE"
        so = shootouts.get((r["date"], h, a))
        day = date.fromisoformat(r["date"]).toordinal() - DAY0
        matches.append([day, idx[h], idx[a], hs, as_, tidx[r["tournament"]], 1 if neutral else 0, 1 if so == h else 2 if so == a else 0])
        # World Football Elo: W 1/0.5/0, K by tournament, times 1.5 for a two-goal win, (11 + N) / 8 for N >= 3.
        for t in (h, a):
            if t not in rating:
                rating[t] = ELO_START if len(rating) < 20 else min(ELO_START, statistics.quantiles(rating.values(), n=4)[0])
        rh, ra = rating[h], rating[a]
        dr = rh - ra + (0 if neutral else ELO_HOME)
        we = 1 / (10 ** (-dr / 400) + 1)
        w = 1 if hs > as_ else 0 if hs < as_ else 0.5
        n = abs(hs - as_)
        g = 1 if n <= 1 else 1.5 if n == 2 else (11 + n) / 8
        delta = weight(r["tournament"]) * g * (w - we)
        if w != 0.5 and played[h] >= 100 and played[a] >= 100:
            pw = we if w == 1 else 1 - we
            upsets.append({"date": r["date"], "winner": idx[h] if w == 1 else idx[a], "loser": idx[a] if w == 1 else idx[h],
                           "score": f"{max(hs, as_)}–{min(hs, as_)}", "tournament": r["tournament"], "p": round(pw, 3),
                           "rw": round(rh if w == 1 else ra), "rl": round(ra if w == 1 else rh)})
        rating[h], rating[a] = rh + delta, ra - delta
        year = int(r["date"][:4])
        for t in (h, a):
            yearly.setdefault(t, {})[year] = round(rating[t])
            if rating[t] > peaks.get(t, {"rating": 0})["rating"]:
                peaks[t] = {"team": idx[t], "rating": round(rating[t]), "date": r["date"]}

    last_year = int(rows[-1]["date"][:4])
    # The top-rated team at the end of every year (among teams that played that year).
    best = []
    end_of = {}
    for year in range(int(rows[0]["date"][:4]), last_year + 1):
        for t, ys in yearly.items():
            if year in ys:
                end_of[t] = ys[year]
        active = {t for t, ys in yearly.items() if year in ys and played[t] >= 50}
        if active:
            top = max(active, key=lambda t: end_of[t])
            best.append({"year": year, "team": idx[top], "rating": end_of[top]})
    year_ago = date.fromisoformat(rows[-1]["date"]).toordinal() - 365
    recent = {t for r in rows if date.fromisoformat(r["date"]).toordinal() >= year_ago for t in (r["home_team"], r["away_team"])}
    current = sorted(({"team": idx[t], "rating": round(rating[t]), "change": round(rating[t] - yearly[t].get(last_year - 1, round(rating[t])))}
                      for t in recent), key=lambda c: -c["rating"])[:40]

    OUT.mkdir(parents=True, exist_ok=True)
    goals = goals_and_shootouts(rows, fetch("goalscorers", refresh), fetch("shootouts", refresh), idx, played)
    meta = {"generated": date.today().isoformat(), "day0": "1872-01-01", "through": rows[-1]["date"],
            "source": {"label": "Mart Jürisoo, international football results from 1872", "url": "https://github.com/martj42/international_results"}}
    (OUT / "matches.json").write_text(json.dumps({
        "meta": meta, "teams": [{"name": n, "flag": flags[n]} for n in names], "tournaments": tourneys, "matches": matches,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "elo.json").write_text(json.dumps({
        "meta": {**meta, "start": ELO_START, "home": ELO_HOME, "chartMin": CHART_MIN, "newcomer": NEWCOMER_QUANTILE},
        "teams": [{"name": n, "flag": flags[n]} for n in names],
        "series": {idx[t]: sorted(ys.items()) for t, ys in yearly.items() if played[t] >= CHART_MIN},
        "peaks": sorted(peaks.values(), key=lambda p: -p["rating"])[:25],
        "best": best,
        "current": current,
        "upsets": sorted(upsets, key=lambda u: u["p"])[:20],
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "goals.json").write_text(json.dumps({"meta": meta, "teams": [{"name": n, "flag": flags[n]} for n in names], **goals},
                                               ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    top = sorted(peaks.values(), key=lambda p: -p["rating"])[:5]
    print(f"{len(matches)} matches of {len(names)} teams through {rows[-1]['date']}; dropped {len(results) - len(rows)}; "
          f"peaks {[(names[p['team']], p['rating'], p['date'][:4]) for p in top]}; now {[(names[c['team']], c['rating']) for c in current[:5]]}",
          file=sys.stderr)
    for path in ("matches.json", "elo.json", "goals.json"):
        print(f"wrote {(OUT / path).relative_to(ROOT)} ({(OUT / path).stat().st_size // 1024} KB)", file=sys.stderr)


def goals_and_shootouts(rows: list[dict], scorers: list[dict], shootouts: list[dict], idx: dict[str, int], played: Counter) -> dict:
    """Top scorers by competition and by team, goals by minute, hat-tricks, and every team's shoot-out record."""
    by_match = {(r["date"], r["home_team"], r["away_team"]): r for r in rows}
    goals = [g for g in scorers if (g["date"], g["home_team"], g["away_team"]) in by_match and g["team"] in idx]
    named = lambda g: g["scorer"] not in ("NA", "")  # a few goals have no scorer on record
    covered = {(g["date"], g["home_team"], g["away_team"]) for g in goals}
    players: dict[tuple, dict] = {}
    minutes = {k: [0] * 121 for k in ("all", "wc", "cont", "qual")}
    hat_tricks = []
    per_match = Counter()
    for g in goals:
        r = by_match[(g["date"], g["home_team"], g["away_team"])]
        sc = scope(r["tournament"])
        if g["minute"].isdigit() and 0 < int(g["minute"]) <= 120:
            for k in ("all", sc):
                if k in minutes:
                    minutes[k][int(g["minute"])] += 1
        if g["own_goal"] == "TRUE" or not named(g):
            continue
        key = (g["scorer"], g["team"])
        p = players.setdefault(key, {"name": g["scorer"], "team": idx[g["team"]], "goals": Counter(), "pens": 0, "hat": 0,
                                     "first": g["date"][:4], "last": g["date"][:4]})
        p["goals"]["all"] += 1
        p["goals"][sc] += 1
        p["pens"] += g["penalty"] == "TRUE"
        p["last"] = g["date"][:4]
        per_match[(key, g["date"])] += 1
    for (key, day), n in per_match.items():
        if n >= 3:
            players[key]["hat"] += 1
            r = next(r for k, r in by_match.items() if k[0] == day and key[1] in k[1:])
            hat_tricks.append({"date": day, "name": key[0], "team": idx[key[1]], "goals": n, "tournament": r["tournament"],
                               "opponent": idx[r["away_team"] if r["home_team"] == key[1] else r["home_team"]],
                               "score": f"{r['home_score']}–{r['away_score']}" if r["home_team"] == key[1] else f"{r['away_score']}–{r['home_score']}"})

    def row(p: dict, k: str) -> dict:
        return {"name": p["name"], "team": p["team"], "goals": p["goals"][k], "pens": p["pens"], "hat": p["hat"], "years": f"{p['first']}–{p['last']}"}
    top = {k: [row(p, k) for p in sorted(players.values(), key=lambda p: (-p["goals"][k], p["name"])) if p["goals"][k]][:30]
           for k in ("all", "wc", "cont", "qual")}
    by_team: dict[int, list] = {}
    for p in sorted(players.values(), key=lambda p: -p["goals"]["all"]):
        if played[next(n for n, i in idx.items() if i == p["team"])] >= TEAM_SCORERS_MIN and len(by_team.setdefault(p["team"], [])) < 10:
            by_team[p["team"]].append(row(p, "all"))

    # Shoot-outs: every team's record, overall and in the World Cup and continental championships.
    record: dict[str, dict] = {}
    so_list, first_known, first_won = [], 0, 0
    for s in shootouts:
        r = by_match.get((s["date"], s["home_team"], s["away_team"]))
        if not r or s["winner"] not in (r["home_team"], r["away_team"]):
            continue
        major = scope(r["tournament"]) in ("wc", "cont")
        for t in (r["home_team"], r["away_team"]):
            rec = record.setdefault(t, {"team": idx[t], "all": [0, 0], "major": [0, 0]})
            won = s["winner"] == t
            rec["all"][0 if won else 1] += 1
            if major:
                rec["major"][0 if won else 1] += 1
        if s["first_shooter"] in (r["home_team"], r["away_team"]):
            first_known += 1
            first_won += s["first_shooter"] == s["winner"]
        if major:
            loser = r["away_team"] if s["winner"] == r["home_team"] else r["home_team"]
            so_list.append({"date": s["date"], "winner": idx[s["winner"]], "loser": idx[loser], "score": f"{r['home_score']}–{r['away_score']}",
                            "tournament": r["tournament"]})
    return {
        "coverage": {"matches": len(covered), "competitive": sum(1 for r in rows if r["tournament"] != "Friendly"),
                     "goals": len(goals), "pens": sum(g["penalty"] == "TRUE" for g in goals), "own": sum(g["own_goal"] == "TRUE" for g in goals)},
        "scorers": top,
        "byTeam": by_team,
        "minutes": minutes,
        "hatTricks": sorted(hat_tricks, key=lambda h: (-h["goals"], h["date"]))[:20],
        "shootouts": {"teams": sorted(record.values(), key=lambda r: -sum(r["all"])), "major": so_list[::-1],
                      "firstKnown": first_known, "firstWon": first_won, "min": SHOOTOUT_MIN},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    build(ap.parse_args().refresh)


if __name__ == "__main__":
    main()
