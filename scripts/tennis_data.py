"""Shared tennis data helpers: ATP/WTA match files and tournament draws from Wikipedia."""

from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"

SOURCE_URL = "https://raw.githubusercontent.com/Aneeshers/tennis-sackmann-archive/main/{tour}/{tour}_matches_{year}.csv"
WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "sports-stats-mvp/1.0 (https://github.com/angelmza1990/sports-stats-mvp)"

SLAMS = ["Australian Open", "Roland Garros", "Wimbledon", "US Open"]
SLAM_NAMES = {
    "Australian Open": "Australian Open",
    "Australian Open-2": "Australian Open",
    "Australian Open 2": "Australian Open",
    "Roland Garros": "Roland Garros",
    "Wimbledon": "Wimbledon",
    "US Open": "US Open",
    "Us Open": "US Open",
}
WIKI_SLAM_TITLES = {
    "Australian Open": "{year} Australian Open – {gender}'s singles",
    "Roland Garros": "{year} French Open – {gender}'s singles",
    "Wimbledon": "{year} Wimbledon Championships – {gender}'s singles",
    "US Open": "{year} US Open – {gender}'s singles",
}
GENDER = {"atp": "Men", "wta": "Women"}
# Rough (month, day) by which each Slam is over, used to decide what should exist.
SLAM_DONE_BY = {"Australian Open": (2, 5), "Roland Garros": (6, 15), "Wimbledon": (7, 20), "US Open": (9, 20)}
# Approximate start dates, used only for Slams rebuilt from Wikipedia.
SLAM_START = {"Australian Open": (1, 15), "Roland Garros": (5, 25), "Wimbledon": (6, 29), "US Open": (8, 31)}

OPEN_ERA_START = "19680401"


def download(first_year: int, last_year: int, refresh: bool = False, tour: str = "atp") -> list[Path]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for year in range(first_year, last_year + 1):
        path = RAW_DIR / f"{tour}_matches_{year}.csv"
        if refresh or not path.exists():
            print(f"downloading {tour} {year}...", file=sys.stderr)
            try:
                tmp = path.with_suffix(".part")
                urllib.request.urlretrieve(SOURCE_URL.format(tour=tour, year=year), tmp)
                tmp.replace(path)
            except urllib.error.HTTPError as err:
                # The source may not have a file for the current season yet.
                if err.code == 404 and year == last_year and not path.exists():
                    print(f"no data for {year} yet", file=sys.stderr)
                    continue
                if not path.exists():
                    raise
                print(f"warning: could not download {path.name} ({err}); using the saved copy", file=sys.stderr)
            except (urllib.error.URLError, TimeoutError, OSError) as err:
                if not path.exists():
                    raise
                print(f"warning: could not download {path.name} ({err}); using the saved copy", file=sys.stderr)
        paths.append(path)
    return paths


def read_matches(paths: list[Path], keep) -> list[dict]:
    rows = []
    for path in paths:
        with path.open(encoding="utf-8", errors="replace", newline="") as f:
            rows.extend(row for row in csv.DictReader(f) if keep(row))
    return rows


def start_date(row: dict) -> date:
    return datetime.strptime(row["tourney_date"], "%Y%m%d").date()


def final_date(row: dict) -> date:
    """Estimate the final's date: two-week events end on the second Sunday."""
    two_weeks = row["tourney_level"] == "G" or int(row["draw_size"] or 0) >= 96
    return start_date(row) + timedelta(days=13 if two_weeks else 6)


def is_walkover(score: str) -> bool:
    return "W/O" in score.upper()


def ascii_key(name: str) -> str:
    """Accent- and case-insensitive key for matching player names across sources."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", plain.lower())


# Countries that didn't exist yet: the match files list today's country for the whole career.
SUCCESSOR_STATES = [
    ({"CZE", "SVK"}, "TCH", date(1992, 12, 31)),
    ({"RUS", "UKR", "BLR", "GEO", "KAZ", "UZB", "LAT", "LTU", "EST", "ARM", "AZE", "MDA", "TJK", "TKM", "KGZ"}, "URS", date(1991, 12, 25)),
    ({"SRB", "CRO", "SLO", "BIH", "MKD", "MNE"}, "YUG", date(1991, 6, 24)),
]


def country_at(ioc: str, when: date) -> str:
    for successors, old, until in SUCCESSOR_STATES:
        if ioc in successors and when <= until:
            return old
    return ioc


def ascii_name(name: str) -> str:
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()


# ---------- Grand Slam draws from Wikipedia ----------

ROUND_CODES = {
    "first round": "R128", "second round": "R64", "third round": "R32", "fourth round": "R16",
    "quarterfinals": "QF", "quarterfinal": "QF", "semifinals": "SF", "semifinal": "SF", "final": "F",
}


def fetch_wikitext(title: str, cache: Path, refresh: bool) -> str:
    if refresh or not cache.exists():
        print(f"downloading Wikipedia: {title}", file=sys.stderr)
        query = urllib.parse.urlencode({
            "action": "parse", "page": title, "prop": "wikitext",
            "format": "json", "formatversion": "2", "redirects": "1",
        })
        req = urllib.request.Request(f"{WIKI_API}?{query}", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            if cache.exists():  # keep the saved snapshot
                print(f"warning: could not download {title} ({err}); using the saved copy", file=sys.stderr)
                return json.loads(cache.read_text(encoding="utf-8"))["parse"]["wikitext"]
            raise
        if "error" in body:
            if cache.exists():
                print(f"warning: {title} is no longer on Wikipedia; using the saved copy", file=sys.stderr)
                return json.loads(cache.read_text(encoding="utf-8"))["parse"]["wikitext"]
            raise LookupError(f"Wikipedia page not found: {title}")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(body), encoding="utf-8")
    return json.loads(cache.read_text(encoding="utf-8"))["parse"]["wikitext"]


def _templates(text: str, prefix_re: str) -> list[str]:
    """Bodies of every top-level {{...}} template whose name matches prefix_re."""
    out = []
    for m in re.finditer(r"\{\{\s*" + prefix_re, text):
        depth, i = 0, m.start()
        while i < len(text):
            if text.startswith("{{", i):
                depth += 1
                i += 2
            elif text.startswith("}}", i):
                depth -= 1
                i += 2
                if depth == 0:
                    out.append(text[m.start():i])
                    break
            else:
                i += 1
    return out


def _params(template: str) -> dict[str, str]:
    params = {}
    for m in re.finditer(r"\n\s*\|\s*([A-Za-z0-9\-]+)\s*=([^\n]*)", template):
        params[m.group(1).strip()] = m.group(2).strip()
    return params


def _player(cell: str) -> tuple[str, str] | None:
    link = re.search(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", cell)
    if not link:
        return None
    name = re.sub(r"\s*\([^)]*\)$", "", link.group(1)).strip()
    flag = re.search(r"\{\{\s*flag(?:icon|country)?\s*\|\s*([A-Z]{3})", cell)
    return name, flag.group(1) if flag else ""


def _games(cell: str) -> tuple[int | None, int | None]:
    """(games, tiebreak points) from a bracket score cell like '7<sup>8</sup>'."""
    plain = cell.replace("\'\'\'", "")
    tb = re.search(r"<sup>(\d+)</sup>", plain)
    games = re.search(r"\d+", re.sub(r"<sup>.*?</sup>", "", plain))
    return (int(games.group(0)) if games else None), (int(tb.group(1)) if tb else None)


def _set_part(cell_w: str, cell_l: str) -> str | None:
    gw, tw = _games(cell_w)
    gl, tl = _games(cell_l)
    if gw is None or gl is None:
        return None
    part = f"{gw}-{gl}"
    if tw is not None or tl is not None:
        # ATP notation keeps only the tiebreak points of the player who lost the set.
        loser_tb = tl if gw > gl else tw
        part += f"({loser_tb if loser_tb is not None else (tw if tw is not None else tl)})"
    return part


def parse_slam_draw(wikitext: str) -> list[dict]:
    """Every match in a Wikipedia singles draw page as dicts with winner/loser/score/round."""
    # Qualifying brackets share the page; some draws repeat the quarterfinals in two brackets.
    wikitext = re.split(r"\n==\s*Qualifying\s*==", wikitext)[0]
    matches, seen = [], set()
    for tpl in _templates(wikitext, r"\d+TeamBracket"):
        p = _params(tpl)
        rounds = sorted({int(k[2:]) for k in p if re.fullmatch(r"RD\d+", k)})
        for r in rounds:
            code = ROUND_CODES.get(re.sub(r"<[^>]+>|\[\[|\]\]", "", p[f"RD{r}"]).strip().lower())
            if not code:
                continue
            # Brackets number teams either "team01" or "team1".
            def cell(kind: str, n: int, suffix: str = "") -> str:
                return p.get(f"RD{r}-{kind}{n:02d}{suffix}", p.get(f"RD{r}-{kind}{n}{suffix}", ""))

            teams = sorted({int(k.split("team")[1]) for k in p if k.startswith(f"RD{r}-team")})
            for a in teams[::2]:
                b = a + 1
                cells = [cell("team", n) for n in (a, b)]
                players = [_player(c) for c in cells]
                if not all(players):
                    continue
                bold = ["'''" in c for c in cells]
                if bold[0] == bold[1]:
                    raise ValueError(f"cannot tell the winner of {players} ({code})")
                w, l = (0, 1) if bold[0] else (1, 0)
                nums = (a, b)
                sets_w = [cell("score", nums[w], f"-{s}") for s in range(1, 6)]
                sets_l = [cell("score", nums[l], f"-{s}") for s in range(1, 6)]
                raw = " ".join(sets_w + sets_l).lower()
                if "w/o" in raw or "walkover" in raw:
                    score = "W/O"
                else:
                    parts = [part for sw, sl in zip(sets_w, sets_l) if (part := _set_part(sw, sl))]
                    score = " ".join(parts) + (" RET" if "<sup>r</sup>" in raw else "")
                pair = frozenset((players[w][0], players[l][0]))
                if pair in seen:
                    continue
                seen.add(pair)
                matches.append({
                    "round": code,
                    "winner_name": players[w][0], "winner_ioc": players[w][1],
                    "loser_name": players[l][0], "loser_ioc": players[l][1],
                    "score": score,
                })
    return matches


def draw_from_wikipedia(title: str, base: dict, refresh: bool, known_names: dict[str, str],
                        known_iocs: dict[str, str] | None = None) -> list[dict]:
    """A whole singles draw as match-file-style rows, built from its Wikipedia draw page.

    base holds the tournament columns (tourney_name, tourney_level, tourney_date, surface...).
    Players are renamed to their match-file spelling; known_iocs fills flags the page leaves
    blank (players competing as neutrals)."""
    cache = RAW_DIR / "wikipedia" / f"{ascii_key(title)}.json"
    matches = parse_slam_draw(fetch_wikitext(title, cache, refresh))
    players = {m[f"{side}_name"] for m in matches for side in ("winner", "loser")}
    # A single-elimination draw has one match fewer than it has players.
    if not matches or len(matches) != len(players) - 1 or sum(m["round"] == "F" for m in matches) != 1:
        raise ValueError(f"{title}: parsed {len(matches)} matches for {len(players)} players")
    rows = []
    for m in matches:
        row = {"winner_age": "", "source": "wikipedia", **base, "draw_size": str(len(players)), **m}
        for side in ("winner", "loser"):
            name = known_names.get(ascii_key(row[f"{side}_name"]), ascii_name(row[f"{side}_name"]))
            row[f"{side}_name"] = name
            if not row[f"{side}_ioc"] and known_iocs:
                row[f"{side}_ioc"] = known_iocs.get(name, "")
        rows.append(row)
    return rows


def slam_from_wikipedia(slam: str, year: int, refresh: bool, known_names: dict[str, str], tour: str = "atp",
                        known_iocs: dict[str, str] | None = None) -> list[dict]:
    """A whole Slam as match-file-style rows, built from its Wikipedia draw page."""
    title = WIKI_SLAM_TITLES[slam].format(year=year, gender=GENDER[tour])
    month, day = SLAM_START[slam]
    base = {
        "tourney_name": slam, "tourney_level": "G", "tourney_date": f"{year}{month:02d}{day:02d}",
        "surface": {"Roland Garros": "Clay", "Wimbledon": "Grass"}.get(slam, "Hard"),
    }
    rows = draw_from_wikipedia(title, base, refresh, known_names, known_iocs)
    if len(rows) != 127:
        raise ValueError(f"{title}: parsed {len(rows)} matches, expected 127")
    return rows


def missing_slams(rows: list[dict], today: date | None = None) -> list[tuple[str, int]]:
    """Slams that should have been played by today but have no final in the ATP rows."""
    today = today or date.today()
    have = {(SLAM_NAMES.get(r["tourney_name"]), edition_year(r)) for r in rows if r["round"] == "F" and r["tourney_level"] == "G"}
    last_year = max(int(r["tourney_date"][:4]) for r in rows)
    missing = []
    for year in range(last_year, today.year + 1):
        for slam in SLAMS:
            month, day = SLAM_DONE_BY[slam]
            if date(year, month, day) <= today and (slam, year) not in have:
                missing.append((slam, year))
    return missing


def edition_year(row: dict) -> int:
    """Official year of a Slam edition.

    Australian Opens that started in late December up to 1975 are named after
    the following year; from 1977 they carry the year they started in.
    """
    start = start_date(row)
    if SLAM_NAMES.get(row["tourney_name"]) == "Australian Open" and start.month == 12 and start.year <= 1975:
        return start.year + 1
    return start.year
