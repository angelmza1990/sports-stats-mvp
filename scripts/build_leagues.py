"""Build the national league datasets used by football/<league> (Italy, Spain, England, France, Germany, Brazil).

For each league, reads Wikipedia's list of national champions (checked club by
club against the same page's totals table), the top scorer of every season,
the all-time top scorers and, where one is published, the all-time table.
Clubs are mapped to crests through data/football/clubs.json.

Usage:
    python3 scripts/build_leagues.py                   # every league, cached pages
    python3 scripts/build_leagues.py serie-a la-liga   # some leagues
    python3 scripts/build_leagues.py --refresh         # re-download every page
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date

import wikitables as W
from build_football import CLUBS, COUNTRIES, RAW_DIR, ROOT, ClubIndex, slug

SEASON_RE = re.compile(r"^(\d{4})")
# A few pages use ISO codes in flag templates; the rest of the site uses FIFA/IOC codes.
CODE_FIX = {"CHE": "SUI", "NLD": "NED", "DEU": "GER"}


def nation_code(text: str) -> str | None:
    code = W.flag_code(text)
    return CODE_FIX.get(code, code)


LEAGUES = {
    "serie-a": {
        "name": "Serie A", "country": "ITA", "adjective": "Italian",
        "champions": {"page": "List of Italian football champions", "section": (r"==\s*Editions\s*==", r"==\s*Performances\s*==")},
        "eras": [{"key": "modern", "label": "Serie A era", "since": 1929, "tag": "Serie A", "early": "Before Serie A", "earlyTag": "Pre-Serie A"}],
        "expected": {"Juventus": 36, "Inter Milan": 21, "Milan": 19},
        "scorers": {"page": "Capocannoniere", "needles": ("season", "player", "club", "goals"), "tables": 1},
        "alltimeScorers": {"page": "Serie A", "needles": ("player", "goals", "apps", "ratio")},
        "alltime": {
            "lang": "it", "page": "Classifica perpetua della Serie A dal 1929", "needles": ("squadra", "punti"),
            "columns": {"Part.": "seasons", "3pv": "pts", "G": "pld", "V": "w", "N": "d", "P": "l", "GF": "gf", "GS": "ga"},
            "period": "Serie A, 1929–30 to date",
            "note": "Points recalculated at three per win for every season.",
        },
    },
    "la-liga": {
        "name": "La Liga", "country": "ESP", "adjective": "Spanish",
        "champions": {"page": "List of Spanish football champions", "section": (r"==\s*Champions\s*==", r"==\s*Total La Liga")},
        "eras": [],
        "expected": {"Real Madrid": 36, "Barcelona": 29, "Atlético Madrid": 11},
        "scorers": {"page": "Pichichi Trophy", "needles": ("season", "player", "club", "goals"), "tables": 1},
        "alltimeScorers": {"page": "La Liga", "needles": ("player", "goals", "apps", "ratio")},
        "alltime": {
            "lang": "es", "page": "Anexo:Clasificación histórica de la Primera División de España", "needles": ("equipo", "puntos"),
            "columns": {"Temp.": "seasons", "Puntos": "pts", "PJ": "pld", "PG": "w", "PE": "d", "PP": "l", "GF": "gf", "GC": "ga"},
            "period": "La Liga, 1929 to date",
            "note": "As published: two points per win until 1994–95 and three since.",
        },
    },
    "premier-league": {
        "name": "English top flight", "short": "England", "country": "ENG", "adjective": "English",
        "champions": {"page": "List of English football champions", "section": (r"==\s*List of champions by season", r"==\s*List of champion clubs")},
        "eras": [{"key": "modern", "label": "Premier League era", "since": 1992, "tag": "Premier League", "early": "Football League era", "earlyTag": "First Division"}],
        "expected": {"Manchester United": 20, "Liverpool": 20, "Arsenal": 14},
        "scorers": {"page": "List of English football first tier top scorers", "needles": ("season", "player", "club", "goals"), "tables": 1},
        "alltimeScorers": {"page": "List of English football first tier top scorers", "needles": ("player", "goals", "apps", "ratio")},
        "alltime": {
            "lang": "en", "page": "Premier League records and statistics", "needles": ("club", "seasons", "pld", "pts"),
            "columns": {"Seasons": "seasons", "Pts": "pts", "Pld": "pld", "W": "w", "D": "d", "L": "l", "GF": "gf", "GA": "ga"},
            "period": "Premier League only, 1992–93 to date",
            "note": "Premier League seasons only (since 1992–93), three points per win.",
        },
    },
    "ligue-1": {
        "name": "Ligue 1", "country": "FRA", "adjective": "French",
        "champions": {"page": "List of French football champions", "section": (r"==\s*List of champions\s*==", r"==\s*Performance\s*==")},
        "eras": [{"key": "modern", "label": "Professional era", "since": 1932, "tag": "Pro", "early": "Amateur era", "earlyTag": "Amateur"}],
        "expected": {"Paris Saint-Germain": 14, "Saint-Étienne": 10},
        # The totals table credits Rouen with the 1944–45 wartime title, which the season list (like the LFP) leaves out.
        "totalsExceptions": {"Rouen": 1},
        "scorers": {"page": "List of Ligue 1 top scorers", "needles": ("season", "player", "club", "goals"), "tables": 1},
        "alltimeScorers": {"page": "List of Ligue 1 top scorers", "needles": ("player", "goals", "apps", "first")},
        "alltime": None,
    },
    "bundesliga": {
        "name": "Bundesliga", "country": "GER", "adjective": "German",
        "champions": {"page": "List of German football champions", "section": (r"==\s*Champions\s*==", r"==\s*Performances\s*==")},
        "eras": [{"key": "modern", "label": "Bundesliga era", "since": 1963, "tag": "Bundesliga", "early": "Before the Bundesliga", "earlyTag": "Pre-Bundesliga"}],
        "expected": {"Bayern Munich": 35, "1. FC Nürnberg": 9, "Borussia Dortmund": 8},
        "scorers": {"page": "List of Bundesliga top scorers by season", "needles": ("season", "player", "club", "goals"), "tables": 1},
        "alltimeScorers": {"page": "Bundesliga", "needles": ("player", "goals", "apps", "ratio")},
        "alltime": {
            "lang": "en", "page": "All-time Bundesliga table", "needles": ("club", "pld", "pts"),
            "columns": {"Years": "seasons", "Pts": "pts", "Pld": "pld", "W": "w", "D": "d", "L": "l", "GF": "gf", "GA": "ga"},
            "period": "Bundesliga, 1963–64 to date",
            "note": "Bundesliga seasons only (since 1963–64), three points per win.",
        },
    },
    "brasileirao": {
        "name": "Brasileirão", "country": "BRA", "adjective": "Brazilian",
        "champions": {"page": "List of Brazilian football champions", "section": (r"==\s*List of champions\s*==", r"==\s*Performances\s*==")},
        "eras": [{"key": "modern", "label": "Since 1971", "since": 1971, "tag": "Série A", "early": "1937–1970", "earlyTag": "Pre-1971"}],
        "expected": {"Palmeiras": 12, "Santos": 8, "Flamengo": 8},
        "scorers": {"page": "List of Campeonato Brasileiro Série A top scorers", "needles": ("year", "footballer", "club", "goals"), "tables": 4},
        "alltimeScorers": {"page": "List of Campeonato Brasileiro Série A top scorers", "needles": ("player", "goals", "played")},
        "alltime": {
            "lang": "en", "page": "Campeonato Brasileiro Série A", "needles": ("team", "pts", "gp"),
            "columns": {"Pts": "pts", "GP": "pld", "W": "w", "D": "d", "L": "l", "GF": "gf", "GA": "ga"},
            "period": "1937 and every edition since 1959, through 2024",
            "note": "The 20 clubs with the most points, as published.",
        },
    },
}


def page(title: str, refresh: bool, lang: str = "en") -> str:
    prefix = "" if lang == "en" else f"{lang}-"
    return W.fetch_raw(title, RAW_DIR / f"{prefix}{slug(title)}.wiki", refresh, pause=3.0, lang=lang)


def tables_with(text: str, *needles: str) -> list[list[list[dict]]]:
    out = []
    for grid in W.all_tables(text):
        head = " ".join(W.header_labels(grid[0])).lower() if grid else ""
        if all(n in head for n in needles):
            out.append(grid)
    return out


def column(labels: list[str], *patterns: str) -> int | None:
    for pattern in patterns:
        for i, label in enumerate(labels):
            if re.search(pattern, label.strip("| "), re.I):
                return i
    return None


class LeagueClubs(ClubIndex):
    """A ClubIndex that also remembers each club's label, so unlinked repeats ("Genoa (2)")
    and alternative link targets with the same label resolve to the same club."""

    def __init__(self) -> None:
        super().__init__()
        self.labels: dict[str, str] = {}

    def resolve(self, cell: str, country: str | None) -> str | None:
        target, text = W.links(cell)[0]
        known = self.alias.get(target.lower()) or self.by_label(text, country)
        cid = known or self.labels.get(text.lower()) or super().resolve(cell, country)
        if cid in self.unmapped:
            self.clubs[cid]["name"] = W.plain(self.clubs[cid]["name"])  # labels like <span>CD Málaga</span>
        self.used.add(cid)
        self.labels.setdefault(text.lower(), cid)
        self.labels.setdefault(self.clubs[cid]["name"].lower(), cid)
        return cid


SKIP_CELL = re.compile(r"not (?:held|awarded|played)|no champion|suspended|cancel|abandon|revoked|unknown|\bwar\b|"
                       r"decoration|honorary|^[-–—]+$|^n/a$", re.I)


def club_from_cell(text: str, clubs: LeagueClubs, country: str) -> str | None:
    """A club id from a cell with a link (or plain name for clubs without an article)."""
    text = re.sub(r"\{\{\s*(?:efn|refn)[^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*\}\}", "", text)
    text = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", "", text)
    plain = W.plain(text)
    if not plain or SKIP_CELL.search(plain) or any(SKIP_CELL.search(t) for t, _ in W.links(text)[:1]):
        return None
    if W.links(text):
        return clubs.resolve(text, country)
    name = re.sub(r"\(\d+\)|[†‡*♦]", "", plain).strip()
    if not name:
        return None
    if clubs.by_label(name, country) or name.lower() in clubs.labels:
        cid = clubs.by_label(name, country) or clubs.labels[name.lower()]
        clubs.used.add(cid)
        return cid
    cid = slug(name)
    if cid not in clubs.clubs:
        clubs.clubs[cid] = {"id": cid, "name": name, "country": country, "espn": None, "aliases": []}
    clubs.used.add(cid)
    return cid


def parse_champions(cfg: dict, clubs: LeagueClubs, refresh: bool) -> tuple[list[dict], dict]:
    text = page(cfg["champions"]["page"], refresh)
    start, end = cfg["champions"]["section"]
    a = re.search(start, text).start()
    b = re.search(end, text[a:]).start() + a
    titles = []
    for grid in W.all_tables(text[a:b]):
        labels = W.header_labels(grid[0])
        season_i = column(labels, r"^season", r"^year")
        champ_i = column(labels, r"winner", r"champion")
        runner_i = column(labels, r"runner", r"second")
        if season_i is None or champ_i is None:
            continue
        for row in grid[1:]:
            if len(row) <= champ_i or any(c["header"] for c in row[:champ_i + 1]):
                continue
            season = re.sub(r"\s*\(.*$", "", W.plain(row[season_i]["text"])).strip()
            m = SEASON_RE.match(season)
            if not m or row[champ_i] is row[season_i]:
                continue
            champion = club_from_cell(row[champ_i]["text"], clubs, cfg["country"])
            if not champion:
                continue
            runner = club_from_cell(row[runner_i]["text"], clubs, cfg["country"]) if runner_i is not None and len(row) > runner_i else None
            titles.append({"season": season, "year": int(m.group(1)), "champion": champion, "runnerUp": runner})
    # The page's own count per club, for validation.
    official = {}
    for grid in W.all_tables(text[b:]):
        labels = W.header_labels(grid[0])
        club_i = column(labels, r"^club")
        won_i = column(labels, r"^winners?$", r"^champions$", r"^titles$")
        if club_i is None or won_i is None:
            continue
        for row in grid[1:]:
            cid = club_from_cell(row[club_i]["text"], clubs, cfg["country"]) if len(row) > won_i else None
            if cid:
                official[cid] = official.get(cid, 0) + (W.number(row[won_i]["text"]) or 0)
        break
    return titles, official


def split_cell(text: str, keep_flags: bool = False) -> list[str]:
    """One part per line of a cell; flag-only parts (no text) count when keep_flags is set."""
    return [p for p in re.split(r"<br\s*/?>|\n\*", text) if W.plain(p) or (keep_flags and W.flag_code(p))]


def parse_scorers(cfg: dict, clubs: LeagueClubs, refresh: bool) -> list[dict]:
    """The top scorer(s) of every season."""
    sc = cfg["scorers"]
    out = []
    for grid in tables_with(page(sc["page"], refresh), *sc["needles"])[:sc["tables"]]:
        labels = W.header_labels(grid[0])
        season_i, player_i = column(labels, r"season", r"year"), column(labels, r"player", r"footballer")
        nat_i, club_i = column(labels, r"nationality"), column(labels, r"club")
        goals_i, apps_i = column(labels, r"goals"), column(labels, r"^apps", r"^matches", r"^played")
        for row in grid[1:]:
            if len(row) <= goals_i:
                continue
            season = re.sub(r"\s*\(.*$", "", W.plain(row[season_i]["text"])).strip()
            goals = [int(n) for n in re.findall(r"\d+", W.plain(row[goals_i]["text"]))]
            if not SEASON_RE.match(season) or not goals:
                continue
            players = split_cell(row[player_i]["text"])
            nations = split_cell(row[nat_i]["text"], keep_flags=True) if nat_i is not None else []
            club_parts = split_cell(row[club_i]["text"])
            apps = [int(n) for n in re.findall(r"\d+", W.plain(row[apps_i]["text"]))] if apps_i is not None and len(row) > apps_i else []
            for k, cell in enumerate(players):
                name = W.person(cell)
                if not name or re.search(r"unknown", name, re.I):
                    continue
                parts = [club_parts[k]] if len(club_parts) == len(players) else club_parts
                ids = [cid for part in parts for cid in [club_from_cell(part, clubs, cfg["country"])] if cid]
                nation = nation_code(cell) or nation_code(nations[k] if len(nations) == len(players) else (nations[0] if nations else ""))
                out.append({
                    "season": season, "year": int(season[:4]),
                    "player": re.sub(r"\s*\(\d+\)$", "", name), "nation": nation,
                    "clubs": ids, "goals": goals[k] if len(goals) == len(players) else max(goals),
                    "matches": (apps[k] if len(apps) == len(players) else max(apps)) if apps else None,
                })
    return out


def parse_alltime_scorers(cfg: dict, refresh: bool) -> list[dict]:
    sc = cfg["alltimeScorers"]
    grid = tables_with(page(sc["page"], refresh), *sc["needles"])[0]
    labels = W.header_labels(grid[0])
    player_i, goals_i = column(labels, r"^player"), column(labels, r"goals")
    apps_i = column(labels, r"^apps", r"^games", r"^played")
    years_i, first_i, last_i = column(labels, r"years", r"period"), column(labels, r"^first"), column(labels, r"^last")
    out = []
    for row in grid[1:]:
        if len(row) <= goals_i or W.number(row[goals_i]["text"]) is None or W.plain(row[player_i]["text"]).lower() == "player":
            continue
        if years_i is not None:
            career = W.plain(re.sub(r"<br\s*/?>", ", ", row[years_i]["text"]))
        elif first_i is not None and last_i is not None:
            career = f"{W.plain(row[first_i]['text'])}–{W.plain(row[last_i]['text'])}"
        else:
            career = ""
        out.append({
            "player": re.sub(r"[†*]+$", "", W.person(row[player_i]["text"]) or "").strip(), "nation": nation_code(row[player_i]["text"]),
            "career": career.replace("-", "–"), "goals": W.number(row[goals_i]["text"]),
            "matches": W.number(row[apps_i]["text"]) if apps_i is not None else None,
        })
    return out


def parse_alltime(cfg: dict, clubs: LeagueClubs, refresh: bool) -> list[dict]:
    at = cfg["alltime"]
    grid = tables_with(page(at["page"], refresh, at["lang"]), *at["needles"])[0]
    labels = W.header_labels(grid[0])
    index = {key: labels.index(label) for label, key in at["columns"].items() if label in labels}
    club_i = column(labels, r"^club", r"^squadra", r"^equipo")
    if club_i is None:
        club_i = 1  # "Team | Team": rank, then club
    by_name = {c["name"].lower(): cid for cid, c in clubs.clubs.items() if cid in clubs.used}
    rows = []
    for row in grid[1:]:
        if len(row) < len(labels) or row[club_i]["header"]:
            continue
        values = {k: W.number(row[i]["text"]) for k, i in index.items()}
        if values.get("pts") is None or values.get("pld") is None:
            continue
        cell = row[club_i]["text"]
        tpl = re.search(r"\{\{\s*Calcio ([^|}]+)", cell)  # Italian Wikipedia's club templates
        if tpl:
            name = tpl.group(1).strip()
            name = ITALIAN_NAMES.get(name, name)
            cid = clubs.by_label(name, cfg["country"]) or clubs.labels.get(name.lower()) or by_name.get(name.lower()) or slug(name)
            if cid not in clubs.clubs:
                clubs.clubs[cid] = {"id": cid, "name": name, "country": cfg["country"], "espn": None, "aliases": []}
            clubs.used.add(cid)
        else:
            cid = clubs.resolve(cell, cfg["country"]) if W.links(cell) else club_from_cell(cell, clubs, cfg["country"])
            # Native-language Wikipedias link clubs under other titles: fall back to the club's name.
            if cid in clubs.unmapped:
                alias = by_name.get(W.plain(cell).lower()) or by_name.get(clubs.clubs[cid]["name"].lower())
                if alias:
                    clubs.unmapped.pop(cid)
                    cid = alias
        if cid:
            rows.append({"club": cid, **values})
    return rows


# Italian Wikipedia club templates ({{Calcio Inter}}) -> the name the champions list uses.
ITALIAN_NAMES = {"Inter": "Inter Milan"}


def build(key: str, refresh: bool) -> dict:
    cfg = LEAGUES[key]
    clubs = LeagueClubs()
    titles, official = parse_champions(cfg, clubs, refresh)
    eras = cfg["eras"]
    for t in titles:
        t["era"] = "modern" if eras and t["year"] >= eras[0]["since"] else "early"
    scorers = parse_scorers(cfg, clubs, refresh)
    alltime_scorers = parse_alltime_scorers(cfg, refresh)
    alltime = parse_alltime(cfg, clubs, refresh) if cfg["alltime"] else []

    used = {t["champion"] for t in titles} | {t["runnerUp"] for t in titles if t["runnerUp"]}
    used |= {r["club"] for r in alltime} | {c for sc in scorers for c in sc["clubs"]}
    important = {t["champion"] for t in titles} | {r["club"] for r in sorted(alltime, key=lambda r: -r["pts"])[:25]}
    unmapped = sorted(label for cid, label in clubs.unmapped.items() if cid in important)
    if unmapped:
        print(f"{key}: clubs shown without a crest mapping (add them to {CLUBS.name}): {unmapped}", file=sys.stderr)
    nations = {cfg["country"]} | {sc["nation"] for sc in scorers + alltime_scorers if sc["nation"]}
    at = cfg["alltime"]
    return {
        "meta": {
            "generated": date.today().isoformat(),
            "competition": cfg["name"],
            "country": cfg["country"],
            "through": titles[-1]["season"],
            "eras": eras,
            "sources": [f"https://en.wikipedia.org/wiki/{cfg['champions']['page'].replace(' ', '_')}"],
            "scorersSource": f"https://en.wikipedia.org/wiki/{cfg['scorers']['page'].replace(' ', '_')}",
            "alltimeScorersSource": f"https://en.wikipedia.org/wiki/{cfg['alltimeScorers']['page'].replace(' ', '_')}",
            "alltimeSource": f"https://{at['lang']}.wikipedia.org/wiki/{at['page'].replace(' ', '_')}" if at else None,
            "alltimePeriod": at["period"] if at else None,
            "alltimeNote": at["note"] if at else None,
        },
        "alltime": alltime,
        "scorers": scorers,
        "alltimeScorers": alltime_scorers,
        "countries": {c: {"name": COUNTRIES.get(c, (c, None))[0], "flag": COUNTRIES.get(c, (c, None))[1]} for c in sorted(nations)},
        "clubs": {c: {"name": clubs.clubs[c]["name"], "country": cfg["country"], "crest": clubs.clubs[c]["espn"]} for c in sorted(used)},
        "titles": titles,
        "_official": official,
    }


def validate(key: str, data: dict) -> list[str]:
    cfg = LEAGUES[key]
    errors = []
    official = data.pop("_official")
    counted = Counter(t["champion"] for t in data["titles"])
    names = lambda c: data["clubs"].get(c, {}).get("name", c)
    for c in official:
        official[c] -= cfg.get("totalsExceptions", {}).get(names(c), 0)
    diff = {names(c): (counted.get(c, 0), official.get(c, 0)) for c in set(counted) | set(official) if counted.get(c, 0) != official.get(c, 0)}
    if diff:
        errors.append(f"titles differ from the page's own totals table (got, expected): {diff}")
    by_name = Counter(names(t["champion"]) for t in data["titles"])
    for club, n in cfg["expected"].items():
        if by_name[club] < n:
            errors.append(f"{club}: {by_name[club]} titles, expected at least {n}")
    seasons = [t["year"] for t in data["titles"]]
    if seasons != sorted(seasons):
        errors.append("seasons out of order")
    if len(data["scorers"]) < 40 or len(data["alltimeScorers"]) < 10:
        errors.append(f"top scorers look incomplete ({len(data['scorers'])} seasons, {len(data['alltimeScorers'])} all-time)")
    if cfg["alltime"] and len(data["alltime"]) < 20:
        errors.append(f"all-time table looks incomplete ({len(data['alltime'])} rows)")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download the Wikipedia pages")
    parser.add_argument("league", nargs="*", choices=[*LEAGUES, []], help="default: all")
    args = parser.parse_args()
    failed = False
    for key in args.league or LEAGUES:
        data = build(key, args.refresh)
        errors = validate(key, data)
        if errors:
            print(f"{key}: validation failed:\n  " + "\n  ".join(errors), file=sys.stderr)
            failed = True
            continue
        out = ROOT / "football" / key / "data" / f"{key}.json"
        if out.exists():
            old = json.loads(out.read_text(encoding="utf-8"))
            strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}
            if strip(old) == strip(data):
                print(f"{out.relative_to(ROOT)} is up to date")
                continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}: {len(data['titles'])} titles, through {data['meta']['through']}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
