"""Build the NHL rivalries dataset used by ice-hockey/nhl-rivalries.

Every regular-season and playoff game between the two teams, from the NHL's own schedule API (api-web.nhle.com), read
from the schedules of the side that has kept one name. Playoff games are grouped into their series. Only the pair's
games are cached (data/raw/nhl/rivalries/<id>.json, with the seasons already read); a refresh reads the last two
seasons again, and any season never read.

Usage:
    python3 scripts/build_nhl_rivalries.py            # use the cached games, fetching seasons never read
    python3 scripts/build_nhl_rivalries.py --refresh  # also re-read the last two seasons
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from rivalries_us import season_rows, write

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "raw" / "nhl" / "rivalries"
FRANCHISES = ROOT / "data" / "nhl" / "franchises.json"
OUTPUT = ROOT / "ice-hockey" / "nhl-rivalries" / "data" / "nhl-rivalries.json"
SCHEDULE = "https://api-web.nhle.com/v1/club-schedule-season/{team}/{season}"
USER_AGENT = "sports-stats-mvp/1.0 (https://github.com/angelmza1990/sports-stats-mvp)"

# The API's abbreviation of each era -> the franchise in data/nhl/franchises.json.
ABBREV = {"TAN": "TOR", "TSP": "TOR", "DCG": "DET", "DFL": "DET", "QUE": "COL", "NJD": "NJ", "LAK": "LA"}
# (id, name, team a, team b, the schedules read (one name throughout), first season, validated light/dark colors).
# Colors are the validated pairs of the football and NBA rivalries; black-and-white sides take gold or purple.
RIVALRIES = [
    ("bruins-canadiens", "Bruins–Canadiens", "BOS", "MTL", "MTL", 1924, ("#ce9707", "#d33a3c", "#b68611", "#b71824")),
    ("canadiens-maple-leafs", "Canadiens–Maple Leafs", "MTL", "TOR", "MTL", 1917, ("#d33a3c", "#245fd4", "#e54c4a", "#245fd4")),
    ("blackhawks-red-wings", "Blackhawks–Red Wings", "CHI", "DET", "CHI", 1926, ("#ce9707", "#d33a3c", "#b68611", "#b71824")),
    ("bruins-maple-leafs", "Bruins–Maple Leafs", "BOS", "TOR", "BOS", 1924, ("#ce9707", "#245fd4", "#b68611", "#245fd4")),
    ("bruins-rangers", "Bruins–Rangers", "BOS", "NYR", "BOS", 1926, ("#ce9707", "#245fd4", "#b68611", "#245fd4")),
    ("flyers-penguins", "Flyers–Penguins", "PHI", "PIT", "PHI", 1967, ("#d9471b", "#ce9707", "#b23308", "#b68611")),
    ("flyers-rangers", "Flyers–Rangers", "PHI", "NYR", "PHI", 1967, ("#d9471b", "#245fd4", "#d9471b", "#245fd4")),
    ("blackhawks-blues", "Blackhawks–Blues", "CHI", "STL", "CHI", 1967, ("#d33a3c", "#245fd4", "#e54c4a", "#245fd4")),
    ("islanders-rangers", "Islanders–Rangers", "NYI", "NYR", "NYI", 1972, ("#d9471b", "#245fd4", "#d9471b", "#245fd4")),
    ("devils-rangers", "Devils–Rangers", "NJ", "NYR", "NYR", 1982, ("#d33a3c", "#245fd4", "#e54c4a", "#245fd4")),
    ("canadiens-nordiques", "Canadiens–Nordiques", "MTL", "COL", "MTL", 1979, ("#d33a3c", "#0a96d6", "#e54c4a", "#0a96d6")),
    ("battle-of-alberta", "Oilers–Flames", "EDM", "CGY", "EDM", 1980, ("#245fd4", "#d33a3c", "#245fd4", "#e54c4a")),
    ("avalanche-red-wings", "Avalanche–Red Wings", "COL", "DET", "DET", 1995, ("#824fcf", "#d33a3c", "#824fcf", "#e54c4a")),
    ("capitals-penguins", "Capitals–Penguins", "WSH", "PIT", "WSH", 1974, ("#d33a3c", "#ce9707", "#b71824", "#b68611")),
    ("maple-leafs-senators", "Maple Leafs–Senators", "TOR", "OTT", "OTT", 1992, ("#245fd4", "#d33a3c", "#245fd4", "#e54c4a")),
    ("kings-ducks", "Kings–Ducks", "LA", "ANA", "LAK", 1993, ("#824fcf", "#d9471b", "#824fcf", "#d9471b")),
]
# A Quebec–Montreal game counts for the Nordiques only: the Avalanche left Quebec in 1995.
ONLY_ABBREV = {"canadiens-nordiques": {"QUE"}}


def schedule(team: str, season: int) -> list[dict]:
    url = SCHEDULE.format(team=team, season=f"{season}{season + 1}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.load(resp)
            time.sleep(0.25)
            return body.get("games", [])
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return []  # a season the club didn't play (the 2004–05 lockout, or before it joined)
            if err.code not in (429, 500, 502, 503) or attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    return []


def franchise(abbrev: str) -> str:
    return ABBREV.get(abbrev, abbrev)


def game(g: dict, a: str, b: str, only: set[str] | None) -> dict | None:
    if g.get("gameType") not in (2, 3) or g.get("gameState") not in ("OFF", "FINAL"):
        return None
    h, v = g["homeTeam"], g["awayTeam"]
    teams = {franchise(h["abbrev"]), franchise(v["abbrev"])}
    if teams != {a, b} or "score" not in h:
        return None
    if only and not ({h["abbrev"], v["abbrev"]} & only):
        return None
    m = {"date": g["gameDate"], "season": g["season"] // 10000, "home": franchise(h["abbrev"]), "away": franchise(v["abbrev"]),
         "hs": h["score"], "as": v["score"], "playoff": g["gameType"] == 3}
    last = (g.get("gameOutcome") or {}).get("lastPeriodType")
    if last in ("OT", "SO"):
        m["end"] = last
    if g.get("neutralSite"):
        m["neutral"] = True
    s = g.get("seriesStatus")
    if m["playoff"] and s:
        m["series"] = {"round": s.get("round"), "title": s.get("seriesTitle"), "letter": s.get("seriesLetter"), "need": s.get("neededToWin")}
    return m


def games_of(cfg: tuple, refresh: bool) -> list[dict]:
    rid, _, a, b, fetch, first, _ = cfg
    path = CACHE / f"{rid}.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"seasons": [], "games": {}}
    this = date.today().year if date.today().month >= 9 else date.today().year - 1  # the season that started last
    todo = [s for s in range(first, this + 1) if s not in saved["seasons"] or refresh and s >= this - 1]
    def save() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        saved["seasons"].sort()
        path.write_text(json.dumps(saved, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")

    try:
        # A few seasons at a time; a long first download keeps what it has read as it goes.
        with ThreadPoolExecutor(6) as pool:
            for i, (s, games) in enumerate(zip(todo, pool.map(lambda season: schedule(fetch, season), todo))):
                for g in games:
                    m = game(g, a, b, ONLY_ABBREV.get(rid))
                    if m:
                        saved["games"][str(g["id"])] = m
                if s < this - 1 and s not in saved["seasons"]:
                    saved["seasons"].append(s)
                if i % 20 == 19:
                    save()
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        if not saved["games"]:
            raise
        print(f"warning: could not read the NHL schedules for {rid} ({err}); using the saved games", file=sys.stderr)
    save()
    return sorted(saved["games"].values(), key=lambda m: m["date"])


def playoff_series(games: list[dict], a: str, b: str) -> list[dict]:
    """The pair's playoff series: games grouped by season and series; the winner took the most games (or, in the
    total-goals series of the early decades, the most goals)."""
    groups = defaultdict(list)
    for m in games:
        if m["playoff"]:
            s = m.get("series") or {}
            groups[(m["season"], s.get("letter") or s.get("round") or "")].append(m)
    out = []
    for (season, _), ms in sorted(groups.items()):
        wins = {a: 0, b: 0}
        goals = {a: 0, b: 0}
        for m in ms:
            goals[m["home"]] += m["hs"]
            goals[m["away"]] += m["as"]
            if m["hs"] != m["as"]:
                wins[m["home"] if m["hs"] > m["as"] else m["away"]] += 1
        title = (ms[0].get("series") or {}).get("title") or "Playoffs"
        if wins[a] != wins[b]:
            winner = a if wins[a] > wins[b] else b
        else:
            winner = a if goals[a] > goals[b] else b
        item = {"season": f"{season}–{(season + 1) % 100:02d}", "year": season, "round": title, "a": wins[a], "b": wins[b],
                "ties": sum(1 for m in ms if m["hs"] == m["as"]), "winner": winner}
        if wins[a] == wins[b]:
            item["onGoals"] = [goals[a], goals[b]]
        out.append(item)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    franchises = {f["id"]: f for f in json.loads(FRANCHISES.read_text(encoding="utf-8"))["franchises"]}
    built = []
    for cfg in RIVALRIES:
        rid, name, a, b, _, first, colors = cfg
        games = games_of(cfg, args.refresh)
        if len(games) < 40:
            raise SystemExit(f"{rid}: only {len(games)} games")
        seasons = season_rows(games, a, b, lambda m: m["season"], regular=lambda m: not m["playoff"])
        series = playoff_series(games, a, b)
        r = {"id": rid, "name": name, "teams": [a, b], "colors": {"light": list(colors[:2]), "dark": list(colors[2:])},
             "seasons": seasons, "series": series, "games": [{k: v for k, v in m.items() if k != "series"} for m in games],
             "notes": [], "source": {"label": "NHL schedules (api-web.nhle.com)", "url": "https://www.nhl.com/schedule"}}
        built.append(r)
        print(f"{name}: {len(games)} games since {games[0]['date'][:4]}, {len(series)} playoff series", file=sys.stderr)
    write(OUTPUT, built, franchises, "nhl")


if __name__ == "__main__":
    main()
