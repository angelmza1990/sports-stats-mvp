"""Build the EuroLeague dataset used by basketball/euroleague.

Reads English Wikipedia's "EuroLeague Championship Game" (every final since 1958 with its scores, the finals' top scorer,
MVP and champion coach, the titles by club, the coaches' finals and the players with the most titles) and every game since
2000–01 from Euroleague Basketball's own API (the all-time table of the EuroLeague era, the clubs' crests and five great
rivalries game by game). Real Madrid vs Barcelona and Panathinaikos vs Olympiacos also get the head-to-head in every
competition that their Wikipedia articles publish. Titles by club are worked out from the finals and checked against the
article's own table.

Usage:
    python3 scripts/build_euroleague.py            # use the cached pages if present
    python3 scripts/build_euroleague.py --refresh  # re-download them
"""

from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

import wikitables as W
from rivalries_common import parse_date

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "raw" / "wikipedia" / "euroleague"
OUTPUT = ROOT / "basketball" / "euroleague" / "data" / "euroleague.json"
FINALS_PAGE = "EuroLeague Championship Game"
GAMES = ROOT / "data" / "raw" / "euroleague"
GAMES_URL = "https://api-live.euroleague.net/v2/competitions/E/seasons/E{season}/games"
FIRST_SEASON = 2000  # the first season of Euroleague Basketball, 2000–01

# Country names and codes as the pages write them -> (code, name, flag file). The Soviet Union and Yugoslavia have no flag file.
COUNTRIES = {
    "ESP": ("Spain", "es"), "ITA": ("Italy", "it"), "GRE": ("Greece", "gr"), "ISR": ("Israel", "il"), "RUS": ("Russia", "ru"),
    "URS": ("Soviet Union", None), "YUG": ("Yugoslavia", None), "TUR": ("Turkey", "tr"), "LTU": ("Lithuania", "lt"),
    "SRB": ("Serbia", "rs"), "CRO": ("Croatia", "hr"), "FRA": ("France", "fr"), "GER": ("Germany", "de"), "LAT": ("Latvia", "lv"),
    "GEO": ("Georgia", "ge"), "BUL": ("Bulgaria", "bg"), "TCH": ("Czechoslovakia", "cz"), "CZE": ("Czech Republic", "cz"),
    "BEL": ("Belgium", "be"), "POL": ("Poland", "pl"), "SLO": ("Slovenia", "si"), "MNE": ("Montenegro", "me"), "BIH": ("Bosnia and Herzegovina", "ba"),
    "FRY": ("Yugoslavia", None), "UKR": ("Ukraine", "ua"), "NED": ("Netherlands", "nl"), "SUI": ("Switzerland", "ch"), "AUT": ("Austria", "at"),
    "HUN": ("Hungary", "hu"), "ROU": ("Romania", "ro"), "POR": ("Portugal", "pt"), "FIN": ("Finland", "fi"), "SWE": ("Sweden", "se"),
    "GBR": ("Great Britain", "gb"), "ENG": ("England", "gb-eng"), "MKD": ("North Macedonia", "mk"), "USA": ("United States", "us"),
    "EGY": ("Egypt", "eg"), "LIB": ("Lebanon", "lb"), "CYP": ("Cyprus", "cy"), "LUX": ("Luxembourg", "lu"), "DEN": ("Denmark", "dk"),
    "BLR": ("Belarus", "by"), "KAZ": ("Kazakhstan", "kz"), "SVK": ("Slovakia", "sk"), "EST": ("Estonia", "ee"), "SCO": ("Scotland", "gb-sct"),
    "ARG": ("Argentina", "ar"), "BRA": ("Brazil", "br"), "AUS": ("Australia", "au"), "MON": ("Monaco", "mc"), "PUR": ("Puerto Rico", "pr"),
    "CAN": ("Canada", "ca"), "DOM": ("Dominican Republic", "do"), "NGR": ("Nigeria", "ng"), "SEN": ("Senegal", "sn"), "ISL": ("Iceland", "is"), "CPV": ("Cape Verde", "cv"),
}
NAME_CODES = {
    "latvia": "LAT", "ussr": "URS", "soviet union": "URS", "yugoslavia": "YUG", "spain": "ESP", "italy": "ITA", "greece": "GRE",
    "israel": "ISR", "russia": "RUS", "turkey": "TUR", "lithuania": "LTU", "serbia": "SRB", "croatia": "CRO", "france": "FRA",
    "germany": "GER", "west germany": "GER", "georgia": "GEO", "bulgaria": "BUL", "czechoslovakia": "TCH", "belgium": "BEL",
    "poland": "POL", "slovenia": "SLO", "montenegro": "MNE", "usa": "USA", "united states": "USA", "monaco": "MON",
    # Spanish Wikipedia's {{bandera|...}} names
    "espana": "ESP", "italia": "ITA", "grecia": "GRE", "rusia": "RUS", "turquia": "TUR", "lituania": "LTU", "croacia": "CRO",
    "francia": "FRA", "alemania": "GER", "union sovietica": "URS", "urss": "URS", "checoslovaquia": "TCH", "belgica": "BEL",
    "polonia": "POL", "eslovenia": "SLO", "bulgaria": "BUL", "letonia": "LAT", "israel": "ISR", "serbia": "SRB",
    "republica checa": "CZE", "paises bajos": "NED", "suiza": "SUI", "austria": "AUT", "hungria": "HUN", "rumania": "ROU",
    "rumanía": "ROU", "portugal": "POR", "finlandia": "FIN", "suecia": "SWE", "reino unido": "GBR", "inglaterra": "ENG",
    "macedonia del norte": "MKD", "ucrania": "UKR", "chipre": "CYP", "luxemburgo": "LUX", "dinamarca": "DEN", "bielorrusia": "BLR",
    "kazajistan": "KAZ", "eslovaquia": "SVK", "estonia": "EST", "escocia": "SCO", "egipto": "EGY", "libano": "LIB", "monaco": "MON",
    "georgia": "GEO", "montenegro": "MNE", "bosnia y herzegovina": "BIH", "yugoslavia": "YUG", "islandia": "ISL",
}
CODE_FIX = {"HRV": "CRO", "FRG": "GER", "SCG": "SRB", "DEU": "GER", "CHE": "SUI", "NLD": "NED"}


def fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode().strip()


def country_of(cell: str) -> str | None:
    m = re.search(r"\{\{\s*(?:flagicon|flag|fb|bandera)\s*\|\s*(?:tamaño=[^|]*\|\s*)?([^|}]+)", cell, re.I)
    if not m:
        return None
    raw = m.group(1).strip()
    code = raw.upper() if re.fullmatch(r"[A-Za-z]{3}", raw) else NAME_CODES.get(fold(raw))
    return CODE_FIX.get(code, code) if code else None


def page(title: str, refresh: bool, lang: str = "en") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", fold(title)).strip("-")
    return W.fetch_raw(title, CACHE / f"{'' if lang == 'en' else lang + '-'}{slug}.wiki", refresh, pause=1.5, lang=lang)


def section(text: str, heading: str) -> str:
    m = re.search(r"^(=+)\s*" + heading + r"\s*=+\s*$", text, re.M)
    if not m:
        raise SystemExit(f"no section {heading!r}")
    nxt = re.search(r"^={1,%d}[^=]" % len(m.group(1)), text[m.end():], re.M)
    return text[m.end(): m.end() + nxt.start() if nxt else len(text)]


def cells(row: list[dict]) -> list[str]:
    return [c["text"].lstrip("| ").strip() for c in row]


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", W.plain(text.lstrip("| "))).strip()


def years(text: str) -> list[int]:
    """Season years as the year each final was played: "1963–64" and "1964" both -> 1964."""
    out = []
    for m in re.finditer(r"\b(19|20)(\d\d)(?:\s*[–-]\s*(\d\d))?\b", W.plain(text)):
        y = int(m.group(1) + m.group(2))
        out.append(y + 1 if m.group(3) else y)
    return out


# ---------------------------------------------------------------- Clubs


# Article titles that name the same club.
SAME_CLUB = {"virtus-bologna": "virtus-pallacanestro-bologna"}


class Clubs:
    """Clubs keyed by the article their links point to; the display name is the one the titles table uses today."""

    def __init__(self) -> None:
        self.clubs: dict[str, dict] = {}

    def of(self, cell: str) -> str | None:
        found = [(t, d) for t, d in W.links(cell) if not t.lower().startswith(("file:", "image:"))]
        if not found:
            return None
        target, label = found[0]
        cid = re.sub(r"[^a-z0-9]+", "-", fold(target)).strip("-")
        cid = SAME_CLUB.get(cid, cid)
        c = self.clubs.setdefault(cid, {"name": label, "country": country_of(cell), "names": Counter()})
        c["names"][label] += 1
        c["country"] = c["country"] or country_of(cell)
        return cid


def score_pair(text: str) -> tuple[int, int] | None:
    m = re.search(r"(\d+)\s*[–\-]\s*\*?\s*(\d+)", W.plain(text).replace("*", ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def parse_finals(text: str, clubs: Clubs) -> list[dict]:
    body = section(text, "EuroLeague Finals")
    out = []
    for grid in W.all_tables(body):
        labels = [plain(c["text"]).lower() for c in grid[0]]
        if "champion" not in labels:
            continue
        for row in grid[1:]:
            c = cells(row)
            if len(c) < 5 or re.search(r"(?i)cancel", " ".join(c)):
                continue
            season = re.search(r"(?<!\d)(?:19|20)\d\d(?:[–-]\d\d(?!\d))?", W.plain(c[0]))
            champ, runner = clubs.of(c[2]), clubs.of(c[3])
            if not season or not champ or not runner:
                continue
            games = []
            for g in c[4:9]:
                sc = score_pair(g)
                if sc:
                    # Finals over several games mark the home side with "*"; one-game finals list the champion first.
                    games.append(list(sc))
            out.append({"season": season.group(), "year": years(season.group())[0], "host": plain(c[1]),
                        "champion": champ, "runnerUp": runner, "games": games})
    return out


def parse_awards(text: str, finals: list[dict], clubs: Clubs) -> None:
    """Top scorer, MVP and champion coach of every final, from the awards table."""
    by_season = {f["season"]: f for f in finals}
    body = text[text.index("! Season !! Top scorer !! Team"):]
    grid = W.parse_table(W.find_table("\n{|\n" + body, r"^", 0))
    for row in grid[1:]:
        c = cells(row)
        if len(c) < 7:
            continue
        season = re.search(r"(?<!\d)(?:19|20)\d\d(?:[–-]\d\d(?!\d))?", W.plain(c[0]))
        f = by_season.get(season.group()) if season else None
        if not f:
            continue
        person = lambda cell: (re.sub(r"\s*\(\d+×\)", "", W.person(cell) or plain(cell)).strip() or None)  # noqa: E731
        pts = re.search(r"(\d+(?:\.\d+)?)", W.plain(c[3]))
        if person(c[1]) and not re.search(r"n/a", c[1], re.I):
            f["topScorer"] = {"name": person(c[1]), "nation": country_of(c[1]), "club": clubs.of(c[2]),
                              "points": float(pts.group(1)) if pts else None, "average": "average" in c[3].lower()}
        if person(c[4]) and not re.search(r"n/a", c[4], re.I):
            f["mvp"] = {"name": person(c[4]), "nation": country_of(c[4]), "club": clubs.of(c[5])}
        if person(c[6]):
            f["coach"] = {"name": person(c[6]), "nation": country_of(c[6])}


def official_titles(text: str, clubs: Clubs) -> dict[str, int]:
    grid = next(g for g in W.all_tables(section(text, "Titles by club")))
    out = {}
    for row in grid[1:]:
        c = cells(row)
        cid = clubs.of(c[1]) if len(c) > 2 else None
        if cid and W.number(c[2]) is not None:
            out[cid] = W.number(c[2])
            clubs.clubs[cid]["current"] = plain(c[1])  # today's name
            # The last flag of the cell is today's country (Žalgiris: Soviet Union, then Lithuania).
            flags = re.findall(r"\{\{\s*flagicon[^}]*\}\}", c[1])
            clubs.clubs[cid]["country"] = (country_of(flags[-1]) if flags else None) or clubs.clubs[cid]["country"]
    return out


def parse_coaches(text: str) -> list[dict]:
    grid = next(g for g in W.all_tables(section(text, "Finals appearances by head coach")))
    out = []
    for row in grid[1:]:
        c = cells(row)
        if len(c) < 4:
            continue
        bold = " ".join(W.plain(s) for s in re.findall(r"'''(.*?)'''", c[3], re.S))
        won = [int(y) for y in re.findall(r"\b(?:19|20)\d\d\b", bold)]
        name = W.person(c[0]) or plain(c[0])
        out.append({"name": name, "nation": country_of(c[0]), "titles": W.number(re.sub(r"\D", "", W.plain(c[1])) or "0"),
                    "finalsLost": W.number(re.sub(r"\D", "", W.plain(c[2])) or "0"), "won": sorted(set(won))})
    return out


def parse_players(text: str) -> list[dict]:
    grid = next(g for g in W.all_tables(section(text, "Players with the most championships")))
    out = []
    for row in grid[1:]:
        c = cells(row)
        if len(c) < 4:
            continue
        out.append({"name": W.person(c[0]) or plain(c[0]), "nation": country_of(c[0]), "titles": W.number(W.plain(c[1])),
                    "finalsLost": W.number(W.plain(c[2])), "won": [int(y) for y in re.findall(r"\b(?:19|20)\d\d\b", W.plain(c[3]))]})
    return out


# ---------------------------------------------------------------- EuroLeague games (2000–01 on)


def season_games(season: int, refresh: bool) -> list[dict]:
    """Every played game of a season from Euroleague Basketball's own API, cached compactly (data/raw/euroleague)."""
    path = GAMES / f"games-E{season}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    req = urllib.request.Request(GAMES_URL.format(season=season), headers={"User-Agent": W.USER_AGENT})
    try:
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = json.load(resp)
                break
            except urllib.error.HTTPError as err:
                if err.code == 404:
                    return []
                if attempt == 2:
                    raise
                time.sleep(5)
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        if path.exists():
            print(f"warning: could not read the {season} games ({err}); using the saved copy", file=sys.stderr)
            return json.loads(path.read_text(encoding="utf-8"))
        raise
    out = []
    for g in body.get("data", []):
        if not g.get("played"):
            continue
        side = lambda s: {"code": g[s]["club"]["code"], "name": g[s]["club"]["name"],  # noqa: E731
                          "crest": (g[s]["club"].get("images") or {}).get("crest"), "score": g[s].get("score")}
        out.append({"id": g["identifier"], "date": g["date"][:10], "phase": g["phaseType"]["code"], "round": g.get("round"),
                    "group": (g.get("group") or {}).get("rawName", "").strip(), "home": side("local"), "away": side("road")})
    GAMES.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    time.sleep(1)
    return out


def all_games(refresh: bool) -> dict[int, list[dict]]:
    """Seasons by the year they start; a refresh reads the last two again (the current one is in progress)."""
    today = date.today()
    current = today.year if today.month >= 9 else today.year - 1
    return {s: season_games(s, refresh and s >= current - 1) for s in range(FIRST_SEASON, current + 1)}


def club_codes(games: dict[int, list[dict]], finals: list[dict]) -> dict[str, str]:
    """The API's club codes -> the finals' club ids, from the two sides of each season's last Final Four game."""
    by_year = {f["year"]: f for f in finals}
    out: dict[str, str] = {}
    for season, gs in games.items():
        f = by_year.get(season + 1)
        last = sorted((g for g in gs if g["phase"] in ("FF", "PO") and g["home"]["score"] is not None), key=lambda g: (g["date"], g["id"]))
        if not f or not last:
            continue
        g = last[-1]
        won, lost = (g["home"], g["away"]) if g["home"]["score"] > g["away"]["score"] else (g["away"], g["home"])
        out.setdefault(won["code"], f["champion"])
        out.setdefault(lost["code"], f["runnerUp"])
        if out[won["code"]] != f["champion"]:
            raise SystemExit(f"{season + 1}: the API's champion {won['name']} is not the finals' {f['champion']}")
    return out


def match_names(games: dict[int, list[dict]], codes: dict[str, str], clubs: dict) -> None:
    """Finalists from before 2000 that later played the EuroLeague (Žalgiris, Partizan...): matched by name."""
    names: dict[str, set[str]] = {}
    for gs in games.values():
        for g in gs:
            for s in ("home", "away"):
                names.setdefault(g[s]["code"], set()).add(fold(g[s]["name"]))
    taken = set(codes.values())
    for cid, c in clubs.items():
        if cid in taken:
            continue
        key = fold(c["name"])
        hits = [code for code, ns in names.items() if code not in codes and any(re.search(r"\b" + re.escape(key) + r"\b", n) for n in ns)]
        if len(hits) == 1:
            codes[hits[0]] = cid


def alltime_table(games: dict[int, list[dict]], codes: dict[str, str], titles: Counter) -> list[dict]:
    rows: dict[str, dict] = {}
    for season, gs in sorted(games.items()):
        for g in gs:
            h, a = g["home"], g["away"]
            if h["score"] is None or a["score"] is None:
                continue
            for me, other in ((h, a), (a, h)):
                r = rows.setdefault(me["code"], {"code": me["code"], "seasons": set(), "pld": 0, "w": 0, "l": 0, "pf": 0, "pa": 0})
                r.setdefault("names", set()).add(me["name"])
                r["crest"] = me["crest"] or r.get("crest")
                r["seasons"].add(season)
                r["pld"] += 1
                r["w" if me["score"] > other["score"] else "l"] += 1
                r["pf"] += me["score"]
                r["pa"] += other["score"]
    out = []
    for r in rows.values():
        r["seasons"] = len(r["seasons"])
        # The shortest name a club has played under is usually the one without a sponsor ("Baskonia", "Unicaja").
        r["name"] = CODE_NAMES.get(r["code"]) or min(r.pop("names"), key=lambda n: (len(n), n))
        r.pop("names", None)
        r["club"] = codes.get(r["code"])
        r["titles"] = titles.get(r["club"], 0) if r["club"] else 0
        out.append(r)
    return sorted(out, key=lambda r: (-r["w"], r["l"]))


# ---------------------------------------------------------------- Rivalries


def h2h_rows(grid: list[list[dict]], skip_total: bool = True) -> list[dict]:
    """Rows of a "Competition | GP | A wins | (D) | B wins" table."""
    labels = [plain(c["text"]).lower() for c in grid[0]]
    has_d = len(labels) >= 5 or any(lab in ("d", "draws") for lab in labels)
    out = []
    for row in grid[1:]:
        c = [plain(x["text"]) for x in row]
        nums = [W.number(x) for x in c[1:]]
        if not c[0] or None in nums[: 4 if has_d else 3]:
            continue
        n, a = nums[0], nums[1]
        d, b = (nums[2], nums[3]) if has_d else (0, nums[2])
        if skip_total and re.match(r"(?i)total", c[0]):
            continue
        out.append({"comp": c[0], "n": n, "a": a, "d": d, "b": b})
    return out


def clasico_totals(refresh: bool) -> tuple[list[dict], dict, dict]:
    title = "El Clásico (basketball)"
    rows = h2h_rows(W.all_tables(section(page(title, refresh), "Head-to-head statistics"))[0], skip_total=False)
    total = next(r for r in rows if re.match(r"(?i)total", r["comp"]))
    return [r for r in rows if r is not total], {**total, "comp": "Total"}, {"label": f"English Wikipedia, {title}",
                                                                           "url": "https://en.wikipedia.org/wiki/El_Cl%C3%A1sico_(basketball)"}


def eternal_totals(refresh: bool) -> tuple[list[dict], dict, dict]:
    title = "Derby of the Eternal Enemies (basketball)"
    body = section(page(title, refresh), "Head-to-head")
    comps, comp = [], None
    for row in W.parse_table(W.find_table(body, r"^", 0))[1:]:
        c = [plain(x["text"]) for x in row]
        if len(row) == 1 or len(set(c)) == 1:
            comp = re.sub(r"\s*\(.*?\)\s*$", "", c[0]).strip()
            continue
        if re.match(r"(?i)total", c[0]) and comp:
            a, b = W.number(c[1]), W.number(c[2])
            comps.append({"comp": comp, "n": a + b, "a": a, "d": 0, "b": b})
    total = {"comp": "Total", **{k: sum(r[k] for r in comps) for k in ("n", "a", "d", "b")}}
    return comps, total, {"label": f"English Wikipedia, {title}", "url": "https://en.wikipedia.org/wiki/Derby_of_the_Eternal_Enemies_(basketball)"}


# Clubs whose every API name carries a sponsor.
CODE_NAMES = {"BAS": "Baskonia", "PAM": "Valencia Basket", "SIE": "Mens Sana Siena", "RED": "Crvena Zvezda", "TRE": "Benetton Treviso",
              "MUN": "Bayern Munich", "BAM": "Brose Bamberg", "GAL": "Galatasaray", "DAR": "Darüşşafaka", "LOK": "Lokomotiv Kuban",
              "HTA": "Hapoel Tel Aviv", "ROM": "Virtus Roma", "PROK": "Prokom Gdynia", "ZEN": "Zenit St Petersburg", "FOR": "Fortitudo Bologna", "ARI": "Aris", "WRO": "Śląsk Wrocław", "TIV": "Lokomotiv Kuban", "LIE": "Rytas Vilnius", "SOP": "Prokom Gdynia"}
# API codes the names don't match ("Armani Olimpia Milan" for Olimpia Milano).
SAME_CODE = {"MIL": "pallacanestro-olimpia-milano"}
PHASES = {"RS": "Regular season", "TS": "Top 16", "PI": "Play-in", "PO": "Playoffs", "FF": "Final Four"}
# (id, name, code a, code b, light colors, dark colors, Wikipedia totals in every competition)
RIVALRIES = [
    ("real-madrid-barcelona", "El Clásico", "MAD", "BAR", ("#245fd4", "#d33a3c"), ("#245fd4", "#e54c4a"), clasico_totals),
    ("panathinaikos-olympiacos", "Derby of the Eternal Enemies", "PAN", "OLY", ("#067e3f", "#fd736d"), ("#029d50", "#b71824"), eternal_totals),
    ("fenerbahce-efes", "Istanbul derby", "ULK", "IST", ("#ce9707", "#245fd4"), ("#b68611", "#245fd4"), None),
    ("real-madrid-olympiacos", "Real Madrid vs Olympiacos", "MAD", "OLY", ("#824fcf", "#d33a3c"), ("#824fcf", "#e54c4a"), None),
    ("panathinaikos-maccabi", "Panathinaikos vs Maccabi", "PAN", "TEL", ("#067e3f", "#ce9707"), ("#029d50", "#b68611"), None),
]


def build_rivalry(cfg: tuple, games: dict[int, list[dict]], clubs: dict, codes: dict[str, str], refresh: bool) -> dict:
    rid, name, a, b, light, dark, totals = cfg
    meets = []
    for season, gs in sorted(games.items()):
        for g in gs:
            if {g["home"]["code"], g["away"]["code"]} == {a, b} and g["home"]["score"] is not None:
                meets.append({"date": g["date"], "season": f"{season}–{(season + 1) % 100:02d}", "phase": PHASES.get(g["phase"], g["phase"]),
                              "home": "a" if g["home"]["code"] == a else "b", "hs": g["home"]["score"], "as": g["away"]["score"]})
    meets.sort(key=lambda m: m["date"])
    side = lambda code: {"code": code, "id": codes.get(code), "name": clubs[codes[code]]["name"] if codes.get(code) in clubs else code}  # noqa: E731
    out = {"id": rid, "name": name, "teams": [side(a), side(b)], "colors": {"light": list(light), "dark": list(dark)}, "games": meets,
           "finals": [{"season": f["season"], "winner": "a" if codes.get(a) == f["champion"] else "b"} for f in raw_finals
                      if {f["champion"], f["runnerUp"]} == {codes.get(a), codes.get(b)}],
           "comps": [], "total": None, "source": None}
    if totals:
        out["comps"], out["total"], out["source"] = totals(refresh)
    return out


# ---------------------------------------------------------------- Elo ratings and home advantage

# Tuned on every game since 2003–04 for the lowest log loss of the pre-game win probability (0.587):
# K 25 with a margin-of-victory multiplier, 100 points for playing at home (none at the Final Four, a neutral venue),
# 90% of a rating kept from one season to the next and new clubs starting at 1450.
ELO = {"k": 25, "hfa": 100, "carry": 0.9, "start": 1450, "mean": 1500}
ELO_MIN_GAMES = 100  # clubs with fewer EuroLeague games get no line in the chart


def season_label(season: int) -> str:
    return f"{season}–{(season + 1) % 100:02d}"


def elo_ratings(games: dict[int, list[dict]], alltime: list[dict], finals: list[dict]) -> dict:
    """Game-by-game Elo ratings of every EuroLeague club, their peaks, each season's best team, the biggest upsets and
    the current ranking. Clubs go by their API code, as in the all-time table."""
    k, hfa, carry, start, mean = (ELO[x] for x in ("k", "hfa", "carry", "start", "mean"))
    rating: dict[str, float] = {}
    series: dict[str, list] = {}
    upsets, before_playoffs, season_end, peaks = [], {}, {}, {}
    day0 = date(2000, 1, 1).toordinal()
    for season, gs in sorted(games.items()):
        for c in rating:
            rating[c] = mean + (rating[c] - mean) * carry
        for g in sorted(gs, key=lambda g: (g["date"], g["id"])):
            if g["phase"] in ("PI", "PO", "FF") and season not in before_playoffs:
                before_playoffs[season] = dict(rating)
            h, a = g["home"], g["away"]
            if h["score"] is None or a["score"] is None or h["score"] == a["score"]:
                continue
            rh, ra = rating.setdefault(h["code"], start), rating.setdefault(a["code"], start)
            edge = rh - ra + (0 if g["phase"] == "FF" else hfa)
            p_home = 1 / (1 + 10 ** (-edge / 400))
            home_won = h["score"] > a["score"]
            p_winner = p_home if home_won else 1 - p_home
            # Bigger wins move ratings more, damped when the favourite wins (FiveThirtyEight's NBA formula).
            mult = (abs(h["score"] - a["score"]) + 3) ** 0.8 / (7.5 + 0.006 * (edge if home_won else -edge))
            delta = k * mult * ((1 if home_won else 0) - p_home)
            rating[h["code"]] += delta
            rating[a["code"]] -= delta
            day = date.fromisoformat(g["date"]).toordinal() - day0
            for side in (h, a):
                r = rating[side["code"]]
                series.setdefault(side["code"], []).append([day, round(r)])
                if r > peaks.get(side["code"], {"rating": 0})["rating"]:
                    peaks[side["code"]] = {"code": side["code"], "rating": round(r, 1), "date": g["date"], "season": season_label(season)}
            win, lose = (h, a) if home_won else (a, h)
            upsets.append({"date": g["date"], "season": season_label(season), "phase": PHASES.get(g["phase"], g["phase"]),
                           "winner": win["code"], "loser": lose["code"], "score": f"{win['score']}–{lose['score']}",
                           "home": h["code"], "p": round(p_winner, 3)})
        if season not in before_playoffs and season != max(games):
            before_playoffs[season] = dict(rating)  # 2019–20: cancelled before the playoffs
        season_end[season] = dict(rating)
    by_code = {r["code"]: r for r in alltime}
    champion_code = {}
    for code, r in by_code.items():
        for f in finals:
            if r["club"] and f["champion"] == r["club"]:
                champion_code.setdefault(f["year"] - 1, code)
    last = max(games)
    played_last = {s["code"] for g in games[last] for s in (g["home"], g["away"])}
    # The best-rated team going into the playoffs (or the Final Four, in seasons without playoffs), against the champion.
    best = []
    for season, snap in sorted(before_playoffs.items()):
        top = max((c for c in snap if any(c in (g["home"]["code"], g["away"]["code"]) for g in games[season])), key=snap.get)
        best.append({"season": season_label(season), "code": top, "rating": round(snap[top], 1), "champion": champion_code.get(season)})
    prev = season_end.get(last - 1, {})
    current = sorted(({"code": c, "rating": round(rating[c], 1), "change": round(rating[c] - (mean + (prev.get(c, start) - mean) * carry), 1)}
                      for c in played_last), key=lambda r: -r["rating"])
    keep = {c for c, s in series.items() if len(s) >= ELO_MIN_GAMES}
    return {
        **ELO, "minGames": ELO_MIN_GAMES, "day0": "2000-01-01", "through": season_label(last),
        "series": {c: s for c, s in series.items() if c in keep},
        "peaks": sorted(peaks.values(), key=lambda p: -p["rating"])[:20],
        "seasonBest": best,
        "upsets": sorted(upsets, key=lambda u: u["p"])[:20],
        "current": current,
    }


def home_advantage(games: dict[int, list[dict]]) -> dict:
    """Home wins and the home side's average margin, season by season and by stage (the Final Four is neutral)."""
    def tally(list_):
        list_ = [g for g in list_ if g["home"]["score"] is not None and g["away"]["score"] is not None]
        return {"games": len(list_), "homeWins": sum(g["home"]["score"] > g["away"]["score"] for g in list_),
                "margin": round(sum(g["home"]["score"] - g["away"]["score"] for g in list_) / max(1, len(list_)), 2)}
    every = [g for gs in games.values() for g in gs if g["phase"] != "FF"]
    return {
        "seasons": [{"season": season_label(s), **tally([g for g in gs if g["phase"] != "FF"])} for s, gs in sorted(games.items()) if gs],
        "phases": [{"phase": PHASES[p], **tally([g for g in every if g["phase"] == p])} for p in ("RS", "TS", "PI", "PO")
                   if any(g["phase"] == p for g in every)],
        "total": tally(every),
    }


# ---------------------------------------------------------------- Build

raw_finals: list[dict] = []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    text = page(FINALS_PAGE, args.refresh)
    clubs = Clubs()
    finals = parse_finals(text, clubs)
    raw_finals.extend(finals)
    parse_awards(text, finals, clubs)
    official = official_titles(text, clubs)
    counted = Counter(f["champion"] for f in finals)
    diff = {clubs.clubs[c]["name"]: (counted.get(c, 0), official.get(c, 0)) for c in set(counted) | set(official) if counted.get(c, 0) != official.get(c, 0)}
    if diff:
        raise SystemExit(f"titles differ from the article's titles-by-club table (got, expected): {diff}")
    if len(finals) < 68 or counted.most_common(1)[0][1] < 11:
        raise SystemExit(f"finals look incomplete: {len(finals)}")
    coaches, players = parse_coaches(text), parse_players(text)

    games = all_games(args.refresh)
    if sum(len(g) for g in games.values()) < 6000:
        raise SystemExit("the EuroLeague games look incomplete")
    codes = club_codes(games, finals)
    codes.update({k: v for k, v in SAME_CODE.items() if k not in codes})
    match_names(games, codes, {cid: {"name": c.get("current") or c["names"].most_common(1)[0][0]} for cid, c in clubs.clubs.items()})
    alltime = alltime_table(games, codes, counted)
    crest = {r["club"]: r["crest"] for r in alltime if r["club"]}
    for r in alltime:  # today's name, as the titles table gives it
        if r["club"] and clubs.clubs[r["club"]].get("current"):
            r["name"] = clubs.clubs[r["club"]]["current"]
    used = {f[k] for f in finals for k in ("champion", "runnerUp")} | {f[k]["club"] for f in finals for k in ("mvp", "topScorer") if f.get(k)}
    club_out = {cid: {"name": c.get("current") or c["names"].most_common(1)[0][0], "country": c["country"], "crest": crest.get(cid)}
                for cid, c in sorted(clubs.clubs.items()) if cid in used}
    rivalries = [build_rivalry(cfg, games, club_out, codes, args.refresh) for cfg in RIVALRIES]
    for r in rivalries:
        if len(r["games"]) < 25:
            raise SystemExit(f"{r['name']}: only {len(r['games'])} EuroLeague games")
    nations = {c["country"] for c in club_out.values() if c["country"]}
    nations |= {p["nation"] for p in coaches + players if p["nation"]} | {f[k]["nation"] for f in finals for k in ("mvp", "topScorer", "coach") if f.get(k) and f[k]["nation"]}
    out = {
        "updated": date.today().isoformat(),
        "finals": finals, "clubs": club_out, "coaches": coaches, "players": players,
        "alltime": alltime, "alltimeFrom": f"{FIRST_SEASON}–{(FIRST_SEASON + 1) % 100:02d}",
        "gamesThrough": max(g["date"] for gs in games.values() for g in gs),
        "rivalries": rivalries,
        "elo": elo_ratings(games, alltime, finals),
        "home": home_advantage(games),
        "countries": {k: {"name": COUNTRIES.get(k, (k, None))[0], "flag": COUNTRIES.get(k, (k, None))[1]} for k in sorted(nations)},
    }
    unknown = sorted(n for n in nations if n not in COUNTRIES)
    if unknown:
        print(f"note: countries without a name: {unknown}", file=sys.stderr)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(finals)} finals ({finals[0]['season']}–{finals[-1]['season']}), "
          f"{[(club_out[c]['name'], n) for c, n in counted.most_common(3)]}, {len(alltime)} clubs since 2000–01, "
          f"{len(coaches)} coaches, {len(players)} players, rivalries {[(r['name'], len(r['games']), len(r['finals'])) for r in rivalries]}", file=sys.stderr)


if __name__ == "__main__":
    main()
