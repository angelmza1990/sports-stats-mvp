"""Build football/<league>/data/honours.json: every major trophy won by the clubs of each league page.

For each league page, three kinds of titles, club by club:

- League titles: from the page's own data (football/<league>/data/<league>.json), counted the way the governing body
  counts them (data/manual/professionalism.json: where only professional titles count, the amateur ones are left out).
- National cups: the main cup, the league cup and the super cup of the country, from the "by club" table of each
  cup's English Wikipedia article (CC BY-SA 4.0). Each table's wins are checked against the years it lists.
- International titles: the UEFA and CONMEBOL competitions from "List of UEFA club competition winners" and "List of
  CONMEBOL club competition winners", the CONCACAF Champions Cup and the world titles (Intercontinental Cup, Club
  World Cup and FIFA Intercontinental Cup) from this site's own data, and for Uruguay the Río de la Plata cups the
  AUF and the AFA count as official (Spanish Wikipedia, "Campeonatos rioplatenses de fútbol"). The two lists are
  checked against this site's Champions League and Copa Libertadores data.

The Argentine page has its own, fuller section built by scripts/build_argentine_titles.py.

Usage:
    python3 scripts/build_honours.py            # cached pages
    python3 scripts/build_honours.py --refresh  # re-download them
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date

import wikitables as W
from build_football import RAW_DIR, ROOT, slug
from build_leagues import LEAGUES, LeagueClubs, club_from_cell

PROFESSIONALISM = ROOT / "data" / "manual" / "professionalism.json"

# Per league page: its cups as (key, label, short label, Wikipedia page, index of the by-club table on the page).
CUPS = {
    "premier-league": [("fa-cup", "FA Cup", "FA Cup", "List of FA Cup finals", 2),
                       ("league-cup", "EFL Cup", "EFL Cup", "List of EFL Cup finals", 2),
                       ("community-shield", "FA Community Shield", "Shield", "List of FA Community Shield matches", 2)],
    "la-liga": [("copa-del-rey", "Copa del Rey", "Copa", "List of Copa del Rey finals", 1),
                ("supercopa", "Supercopa de España", "Supercopa", "Supercopa de España", 4)],
    "serie-a": [("coppa-italia", "Coppa Italia", "Coppa", "List of Coppa Italia finals", 2),
                ("supercoppa", "Supercoppa Italiana", "Supercoppa", "Supercoppa Italiana", 3)],
    "bundesliga": [("dfb-pokal", "DFB-Pokal", "Pokal", "List of DFB-Pokal finals", 1),
                   ("supercup", "German Super Cup", "Supercup", "Franz Beckenbauer Supercup", 1),
                   ("ligapokal", "DFL-Ligapokal (1972–2007)", "Ligapokal", "DFL-Ligapokal", 1)],
    "ligue-1": [("coupe-de-france", "Coupe de France", "Coupe", "List of Coupe de France finals", 1),
                ("coupe-de-la-ligue", "Coupe de la Ligue (1994–2020)", "C. Ligue", "List of Coupe de la Ligue finals", 5),
                ("trophee", "Trophée des Champions", "Trophée", "Trophée des Champions", 1)],
    "primeira-liga": [("taca", "Taça de Portugal", "Taça", "Taça de Portugal", 3),
                      ("campeonato", "Campeonato de Portugal (1922–1938)", "Camp.", "Taça de Portugal", 1),
                      ("taca-da-liga", "Taça da Liga", "T. Liga", "Taça da Liga", 1),
                      ("supertaca", "Supertaça Cândido de Oliveira", "Supertaça", "Supertaça Cândido de Oliveira", 3)],
    "eredivisie": [("knvb-cup", "KNVB Cup", "Cup", "KNVB Cup", 1),
                   ("shield", "Johan Cruyff Shield", "Shield", "Johan Cruyff Shield", 2)],
    "scottish-premiership": [("scottish-cup", "Scottish Cup", "Cup", "List of Scottish Cup finals", 2),
                             ("league-cup", "Scottish League Cup", "L. Cup", "List of Scottish League Cup finals", 2)],
    "super-lig": [("turkish-cup", "Turkish Cup", "Cup", "Turkish Cup", 5),
                  ("super-cup", "Turkish Super Cup", "Super Cup", "Turkish Super Cup", 4)],
    "brasileirao": [("copa-do-brasil", "Copa do Brasil", "Copa", "Copa do Brasil", 4),
                    ("supercopa", "Supercopa do Brasil", "Supercopa", "Supercopa do Brasil", 1)],
    "uruguayan-primera": [("copa", "Copa AUF Uruguay", "Copa", "Copa Uruguay", 1),
                          ("supercopa", "Supercopa Uruguaya", "Supercopa", "Supercopa Uruguaya", 1)],
    "paraguayan-primera": [("copa", "Copa Paraguay", "Copa", "Copa Paraguay", 1),
                           ("supercopa", "Supercopa Paraguay", "Supercopa", "Supercopa Paraguay", 1)],
    "chilean-primera": [("copa", "Copa Chile", "Copa", "Copa Chile", 1),
                        ("supercopa", "Supercopa de Chile", "Supercopa", "Supercopa de Chile", 3)],
    "colombian-primera": [("copa", "Copa Colombia", "Copa", "Copa Colombia", 2),
                          ("superliga", "Superliga Colombiana", "Superliga", "Superliga Colombiana", 1)],
    "ecuadorian-serie-a": [("copa", "Copa Ecuador", "Copa", "Copa Ecuador", 1),
                           ("supercopa", "Supercopa Ecuador", "Supercopa", "Supercopa Ecuador", 1)],
    "peruvian-primera": [("supercopa", "Supercopa Peruana", "Supercopa", "Supercopa Peruana", 1)],
    "bolivian-primera": [],
    "liga-mx": [("copa-mx", "Copa MX", "Copa", "Copa MX", 2),
                ("campeon", "Campeón de Campeones", "C. de C.", "Campeón de Campeones", 2)],
    "mls": [("supporters-shield", "Supporters' Shield", "Shield", "Supporters' Shield", 1),
            ("open-cup", "U.S. Open Cup (MLS clubs)", "Open Cup", "U.S. Open Cup", 2),
            ("canadian", "Canadian Championship", "Can. Ch.", "Canadian Championship", 4)],
}
# The Supporters' Shield goes to the best regular season: a league title, not a cup.
LEAGUE_KIND = {"supporters-shield"}

UEFA_PAGE = "List of UEFA club competition winners"
UEFA = [("ucl", "European Cup / Champions League", "UCL", "UCL"), ("uel", "UEFA Cup / Europa League", "UEL", "UEL"),
        ("uecl", "Conference League", "UECL", "UEC"), ("cwc", "Cup Winners' Cup", "CWC", "CWC"),
        ("usc", "UEFA Super Cup", "UEFA SC", "USC"), ("uic", "Intertoto Cup", "Intertoto", "UIC")]
CONMEBOL_PAGE = "List of CONMEBOL club competition winners"
CONMEBOL = [("libertadores", "Copa Libertadores", "Lib.", "CL"), ("sudamericana", "Copa Sudamericana", "Sud.", "CS"),
            ("recopa", "Recopa Sudamericana", "Recopa", "RS"), ("supercopa-lib", "Supercopa Libertadores", "Sup. Lib.", "SL"),
            ("conmebol", "Copa CONMEBOL", "CONMEBOL", "CC"), ("mercosur", "Copa Mercosur", "Mercosur", "MS"),
            ("merconorte", "Copa Merconorte", "Merconorte", "MN"), ("oro", "Copa de Oro", "Oro", "CO"),
            ("master-supercopa", "Copa Master de Supercopa", "Master S.", "CMS"), ("master-conmebol", "Copa Master de CONMEBOL", "Master C.", "CMC"),
            ("ganadores", "Copa Ganadores de Copa", "Ganadores", "CGC"), ("interamericana", "Copa Interamericana", "Interam.", "IA"),
            ("suruga", "Suruga Bank Championship", "Suruga", "SB"), ("supercup-ic", "Intercontinental Champions' Supercup", "Int. Sup.", "SCI")]
WORLD = ("world", "World titles (Intercontinental Cup, Club World Cup)", "World")
CONCACAF = ("concacaf", "CONCACAF Champions Cup", "CONCACAF")
RIO = ("rioplatense", "Río de la Plata cups (1905–1946)", "Río de la Plata")
RIOPLATENSE_PAGE = "Campeonatos rioplatenses de fútbol"

EUROPE = {"ENG", "ESP", "ITA", "GER", "FRA", "POR", "NED", "SCO", "TUR"}
SOUTH_AMERICA = {"BRA", "URU", "PAR", "CHI", "COL", "ECU", "PER", "BOL"}
NORTH_AMERICA = {"MEX", "USA"}
# Old country codes in the lists, as the league pages know them.
COUNTRY = {"FRG": "GER"}
# Ids the pages give to one club under two names (River Plate FC of Montevideo, champion 1908-1914).
SAME_ID = {"river-plate-football-club": "river-plate-f-c"}
YEARS = re.compile(r"\b(1[89]\d\d|20\d\d)\b")


def page(title: str, refresh: bool, lang: str = "en") -> str:
    prefix = "" if lang == "en" else f"{lang}-"
    return W.fetch_raw(title, RAW_DIR / f"{prefix}{slug(title)}.wiki", refresh, pause=3.0, lang=lang)


def labels_of(grid: list[list[dict]]) -> list[str]:
    return [re.sub(r"\s+", " ", W.plain(c["text"])).strip().lower() for c in grid[0]]


def cup_counts(title: str, index: int, clubs: LeagueClubs, country: str, refresh: bool) -> tuple[Counter, list[str]]:
    """Wins by club from a cup's by-club table, checked against the years each row lists."""
    grid = W.all_tables(page(title, refresh))[index]
    labels = labels_of(grid)
    club_i = next(i for i, l in enumerate(labels) if l in ("club", "team"))
    won_i = next(i for i, l in enumerate(labels) if l in ("wins", "winners", "winner", "won", "titles"))
    years_i = next((i for i, l in enumerate(labels) if re.fullmatch(r"(years?|year\(s\)|winning years|seasons ?won)( won)?", l)), None)
    counts, errors = Counter(), []
    for row in grid[1:]:
        if len(row) <= max(club_i, won_i) or row[club_i] is row[won_i]:
            continue
        n = W.number(row[won_i]["text"]) or 0
        cid = club_from_cell(row[club_i]["text"], clubs, country) if n else None
        if not cid:
            continue
        if years_i is not None and len(row) > years_i:
            listed = len(YEARS.findall(W.plain(re.sub(r"<ref.*?(?:</ref>|/>)", "", row[years_i]["text"], flags=re.S))))
            if listed != n:
                errors.append(f"{title}: {W.plain(row[club_i]['text'])} has {n} wins but {listed} years listed")
        counts[cid] += n
    if not counts:
        errors.append(f"{title}: no clubs read from table {index}")
    return counts, errors


def list_counts(text: str, cols: list[tuple], clubs: LeagueClubs, country: str) -> tuple[dict[str, Counter], list[str]]:
    """Titles by club and competition from the UEFA or CONMEBOL list, for one country's clubs."""
    grid = W.table_with_headers(text, "club", "country", "total")
    labels = [W.plain(c["text"]).strip() for c in grid[0]]
    club_i, country_i = labels.index("Club"), labels.index("Country")
    out: dict[str, Counter] = {key: Counter() for key, *_ in cols}
    errors = []
    for row in grid[1:]:
        if len(row) < len(labels):
            continue
        code = W.flag_code(row[country_i]["text"]) or W.flag_code(row[club_i]["text"])
        if COUNTRY.get(code, code) != country:
            continue
        cid = club_from_cell(row[club_i]["text"], clubs, country)
        values = {code: W.number(row[i]["text"]) or 0 for i, code in enumerate(labels)}
        total = sum(v for k, v in values.items() if k not in ("Rank.", "Rank", "Club", "Country", "Total"))
        if total != values["Total"]:
            errors.append(f"{W.plain(row[club_i]['text'])}: the competitions add up to {total}, the list's total is {values['Total']}")
        for key, _, _, code in cols:
            if values.get(code):
                out[key][cid] += values[code]
    return out, errors


def finals_by_club(folder: str, country: str) -> Counter:
    data = json.loads((ROOT / "football" / folder / "data" / f"{folder}.json").read_text(encoding="utf-8"))
    return Counter(f["champion"] for f in data["finals"] if COUNTRY.get(f["championCountry"], f["championCountry"]) == country)


def rioplatense(clubs: LeagueClubs, refresh: bool) -> Counter:
    text = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", page(RIOPLATENSE_PAGE, refresh, "es"), flags=re.S)
    uru = re.compile(r"(?:bandera2?|flagicon|flag|fba)\s*\|\s*(?:URU|Uruguay)\b|\{\{\s*URU\s*\}\}")
    out = Counter()
    for row in W.table_with_headers(text, "club", "títulos", "ediciones ganadas")[1:]:
        if len(row) >= 2 and uru.search(row[0]["text"]):
            out[club_from_cell(row[0]["text"], clubs, "URU")] += W.number(row[1]["text"]) or 0
    return out


def build(key: str, refresh: bool, pro: dict) -> tuple[dict, list[str]]:
    cfg = LEAGUES[key]
    country = cfg["country"]
    league = json.loads((ROOT / "football" / key / "data" / f"{key}.json").read_text(encoding="utf-8"))
    clubs = LeagueClubs(cfg.get("sameClub"))
    for cid, c in league["clubs"].items():  # the league page's own names first, so the same club gets the same id
        clubs.labels.setdefault(c["name"].lower(), cid)
        if cid not in clubs.clubs:
            clubs.clubs[cid] = {"id": cid, "name": c["name"], "country": country, "espn": c.get("crest"), "aliases": []}
    errors: list[str] = []
    comps: list[dict] = []
    counts: dict[str, Counter] = {}

    rule = pro.get(key, {})
    official = [t for t in league["titles"] if rule.get("treatment") != "pro-only" or t["year"] >= rule["since"]]
    comps.append({"key": "league", "label": "MLS Cups" if key == "mls" else f"{cfg['name']} titles",
                  "short": "League", "kind": "league"})
    counts["league"] = Counter(t["champion"] for t in official)

    for ckey, label, short, title, index in CUPS[key]:
        got, errs = cup_counts(title, index, clubs, country, refresh)
        errors += errs
        comps.append({"key": ckey, "label": label, "short": short, "kind": "league" if ckey in LEAGUE_KIND else "cup",
                      "source": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"})
        counts[ckey] = got

    intl = []
    if country in EUROPE:
        got, errs = list_counts(page(UEFA_PAGE, refresh), UEFA, clubs, country)
        errors += errs
        intl += [(k, l, s, got[k], UEFA_PAGE) for k, l, s, _ in UEFA]
        check = ("ucl", "champions-league")
    elif country in SOUTH_AMERICA:
        got, errs = list_counts(page(CONMEBOL_PAGE, refresh), CONMEBOL, clubs, country)
        errors += errs
        intl += [(k, l, s, got[k], CONMEBOL_PAGE) for k, l, s, _ in CONMEBOL]
        check = ("libertadores", "copa-libertadores")
    else:
        intl.append((*CONCACAF, finals_by_club("concacaf-champions-cup", country), None))
        check = None
    if check:  # the list against this site's own finals
        mine = finals_by_club(check[1], country)
        theirs = next(c for k, _, _, c, _ in intl if k == check[0])
        for cid in set(mine) | set(theirs):
            if mine[cid] != theirs[cid]:
                errors.append(f"{check[0]}, {cid}: the list has {theirs[cid]}, this site's {check[1]} data {mine[cid]}")
    intl.append((*WORLD, finals_by_club("world-club-champions", country), None))
    if country == "URU":
        intl.append((*RIO, rioplatense(clubs, refresh), None))
    for k, label, short, got, source in intl:
        if not got:
            continue  # a competition none of the country's clubs has won
        comps.append({"key": k, "label": label, "short": short, "kind": "intl",
                      **({"source": f"https://en.wikipedia.org/wiki/{source.replace(' ', '_')}"} if source else {})})
        counts[k] = got

    for k, c in counts.items():
        counts[k] = Counter()
        for cid, n in c.items():
            counts[k][SAME_ID.get(cid, cid)] += n
    ids = sorted({cid for c in counts.values() for cid, n in c.items() if n and cid})
    world_clubs = json.loads((ROOT / "football" / "world-club-champions" / "data" / "world-club-champions.json").read_text(encoding="utf-8"))["clubs"]
    out_clubs = {}
    for cid in ids:
        if cid in league["clubs"]:
            c = league["clubs"][cid]
            out_clubs[cid] = {"name": c["name"], "crest": c.get("crest")}
        elif cid in clubs.clubs:
            c = clubs.clubs[cid]
            out_clubs[cid] = {"name": W.plain(c["name"]), "crest": c.get("espn")}
        else:
            c = world_clubs.get(cid, {"name": cid})
            out_clubs[cid] = {"name": c["name"], "crest": c.get("crest")}
    rows = [{"club": cid, "titles": {k: counts[k][cid] for k in counts if counts[k][cid]}} for cid in ids]
    rows.sort(key=lambda r: (-sum(r["titles"].values()), out_clubs[r["club"]]["name"]))
    notes = []
    if rule.get("treatment") == "pro-only":
        notes.append(f"League titles count from {rule['since']}, as the league counts them; the amateur championships before are left out.")
    data = {
        "meta": {"generated": date.today().isoformat(), "country": country, "notes": notes,
                 "sources": [c["source"] for c in comps if c.get("source")]},
        "competitions": [c for c in comps if c["key"] in counts],
        "clubs": out_clubs,
        "rows": rows,
    }
    return data, errors


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("leagues", nargs="*", help="league page keys (default: all)")
    args = ap.parse_args()
    pro = json.loads(PROFESSIONALISM.read_text(encoding="utf-8"))["leagues"]
    failed = False
    for key in args.leagues or list(CUPS):
        data, errors = build(key, args.refresh, pro)
        if errors:
            failed = True
            print(f"{key}: validation failed:\n  " + "\n  ".join(errors), file=sys.stderr)
            continue
        out = ROOT / "football" / key / "data" / "honours.json"
        out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        top = [(data["clubs"][r["club"]]["name"], sum(r["titles"].values())) for r in data["rows"][:5]]
        print(f"wrote {out.relative_to(ROOT)}: {len(data['rows'])} clubs; {top}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
