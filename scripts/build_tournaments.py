"""Build datasets for international team tournaments (rugby, basketball, volleyball, field hockey).

Every competition is described by a config: the Wikipedia page and table that
list its editions (champion, runner-up, third, fourth, hosts, teams), plus
optional all-time tables, participation tables and player records. One JSON
file is written per competition and gender.

Usage:
    python3 scripts/build_tournaments.py                 # all competitions, cached pages
    python3 scripts/build_tournaments.py --refresh       # re-download every page
    python3 scripts/build_tournaments.py rugby-wc-men     # just one
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date

import wikitables as W
from build_football import COUNTRIES, RAW_DIR, ROOT, slug
from build_world_cup import TEAMS

# Extra national teams seen in these sports: (name, flagcdn code or None).
MORE_TEAMS = {
    "EUN": ("Unified Team", None), "ROC": ("ROC", None), "TPE": ("Chinese Taipei", "tw"), "IOA": ("Independent Olympians", None),
    "PUR": ("Puerto Rico", "pr"), "PHI": ("Philippines", "ph"), "LTU": ("Lithuania", "lt"), "LAT": ("Latvia", "lv"), "SSD": ("South Sudan", "ss"),
    "FIJ": ("Fiji", "fj"), "SAM": ("Samoa", "ws"), "TGA": ("Tonga", "to"), "NAM": ("Namibia", "na"), "GEO": ("Georgia", "ge"),
    "ZIM": ("Zimbabwe", "zw"), "CIV": ("Ivory Coast", "ci"), "KEN": ("Kenya", "ke"), "MAS": ("Malaysia", "my"), "PAK": ("Pakistan", "pk"),
    "IND": ("India", "in"), "IRL": ("Ireland", "ie"), "HKG": ("Hong Kong", "hk"), "RUS": ("Russia", "ru"), "SRB": ("Serbia", "rs"),
    "SCG": ("Serbia and Montenegro", None), "BOH": ("Bohemia", None), "RHO": ("Rhodesia", None), "ANZ": ("Australasia", None),
    "SUD": ("Sudan", "sd"), "SEN": ("Senegal", "sn"), "DOM": ("Dominican Republic", "do"), "PAN": ("Panama", "pa"),
    "THA": ("Thailand", "th"), "KAZ": ("Kazakhstan", "kz"), "BLR": ("Belarus", "by"), "UKR": ("Ukraine", "ua"), "CZE": ("Czech Republic", "cz"),
    "SVK": ("Slovakia", "sk"), "TUN": ("Tunisia", "tn"), "EGY": ("Egypt", "eg"), "CMR": ("Cameroon", "cm"), "ALG": ("Algeria", "dz"),
    "IRE": ("Ireland", "ie"), "ROM": ("Romania", "ro"), "TON": ("Tonga", "to"), "LIB": ("Lebanon", "lb"),
    "CAF": ("Central African Republic", "cf"), "DRC": ("DR Congo", "cd"), "PRC": ("China", "cn"), "OAR": ("Olympic Athletes from Russia", None),
    "CIS": ("Unified Team", None), "LBA": ("Libya", "ly"), "BGR": ("Bulgaria", "bg"), "GRC": ("Greece", "gr"),
    "MAR": ("Morocco", "ma"), "NGR": ("Nigeria", "ng"), "NGA": ("Nigeria", "ng"), "ANG": ("Angola", "ao"), "CUB": ("Cuba", "cu"),
    "GBR": ("Great Britain", "gb"), "WAL": ("Wales", "gb-wls"), "SCO": ("Scotland", "gb-sct"), "ENG": ("England", "gb-eng"),
    "URU": ("Uruguay", "uy"), "CHI": ("Chile", "cl"), "VEN": ("Venezuela", "ve"), "MEX": ("Mexico", "mx"), "CAN": ("Canada", "ca"),
    "USA": ("United States", "us"), "JPN": ("Japan", "jp"), "KOR": ("South Korea", "kr"), "PRK": ("North Korea", "kp"),
    "CHN": ("China", "cn"), "IRI": ("Iran", "ir"), "IRN": ("Iran", "ir"), "QAT": ("Qatar", "qa"), "JOR": ("Jordan", "jo"),
    "LBN": ("Lebanon", "lb"), "NZL": ("New Zealand", "nz"), "AUS": ("Australia", "au"), "RSA": ("South Africa", "za"),
    "ROU": ("Romania", "ro"), "POR": ("Portugal", "pt"), "ITA": ("Italy", "it"), "ESP": ("Spain", "es"), "FRA": ("France", "fr"),
    "GER": ("Germany", "de"), "NED": ("Netherlands", "nl"), "BEL": ("Belgium", "be"), "POL": ("Poland", "pl"), "BUL": ("Bulgaria", "bg"),
    "HUN": ("Hungary", "hu"), "GRE": ("Greece", "gr"), "TUR": ("Turkey", "tr"), "CRO": ("Croatia", "hr"), "SLO": ("Slovenia", "si"),
    "SVN": ("Slovenia", "si"), "MNE": ("Montenegro", "me"), "BIH": ("Bosnia and Herzegovina", "ba"), "FIN": ("Finland", "fi"),
    "SWE": ("Sweden", "se"), "DEN": ("Denmark", "dk"), "NOR": ("Norway", "no"), "ISR": ("Israel", "il"), "BRA": ("Brazil", "br"),
    "ARG": ("Argentina", "ar"), "PER": ("Peru", "pe"), "COL": ("Colombia", "co"), "ECU": ("Ecuador", "ec"), "PAR": ("Paraguay", "py"),
    "BOL": ("Bolivia", "bo"), "SUI": ("Switzerland", "ch"), "AUT": ("Austria", "at"), "LUX": ("Luxembourg", "lu"),
    "EST": ("Estonia", "ee"), "AZE": ("Azerbaijan", "az"), "TTO": ("Trinidad and Tobago", "tt"), "CRC": ("Costa Rica", "cr"),
    "BAR": ("Barbados", "bb"), "GHA": ("Ghana", "gh"), "INA": ("Indonesia", "id"), "SGP": ("Singapore", "sg"), "SIN": ("Singapore", "sg"),
    "BAN": ("Bangladesh", "bd"), "SRI": ("Sri Lanka", "lk"), "KSA": ("Saudi Arabia", "sa"), "UAE": ("United Arab Emirates", "ae"),
    "KUW": ("Kuwait", "kw"), "BRN": ("Bahrain", "bh"), "IRQ": ("Iraq", "iq"), "SYR": ("Syria", "sy"), "MGL": ("Mongolia", "mn"),
    "CPV": ("Cape Verde", "cv"), "MOZ": ("Mozambique", "mz"), "MLI": ("Mali", "ml"), "COD": ("DR Congo", "cd"), "RWA": ("Rwanda", "rw"),
}

CONTINENTS = {
    "Europe": "BGR GRC CIS IRE ROM ENG SCO WAL IRL NIR FRA ITA ESP POR GER FRG GDR NED BEL LUX SUI AUT POL CZE TCH SVK HUN ROU BUL GRE TUR YUG FRY SCG SRB CRO SLO SVN MNE BIH MKD ALB URS RUS UKR BLR EUN ROC LTU LAT EST FIN SWE NOR DEN ISL GEO ARM AZE ISR GBR BOH",
    "Americas": "USA CAN MEX CUB PUR DOM PAN CRC HON SLV GUA JAM TRI TTO HAI BAR BRA ARG URU PAR CHI PER BOL ECU COL VEN",
    "Asia": "LIB PRC JPN KOR PRK CHN TPE HKG PHI THA MAS SIN SGP INA IND PAK BAN SRI IRN IRI IRQ KUW KSA QAT UAE BRN JOR LBN SYR KAZ UZB MGL DEI",
    "Africa": "LBA CAF DRC RSA EGY MAR ALG TUN NGR NGA SEN CIV CMR ANG ZIM RHO KEN GHA NAM CPV MOZ MLI COD ZAI SSD SUD RWA",
    "Oceania": "TON AUS NZL FIJ SAM TGA PNG ANZ",
}
CONTINENT_OF = {code: cont for cont, codes in CONTINENTS.items() for code in codes.split()}

OLYMPIC_HOSTS = {
    1908: "GBR", 1920: "BEL", 1928: "NED", 1932: "USA", 1936: "GER", 1948: "GBR", 1952: "FIN", 1956: "AUS", 1960: "ITA",
    1964: "JPN", 1968: "MEX", 1972: "FRG", 1976: "CAN", 1980: "URS", 1984: "USA", 1988: "KOR", 1992: "ESP", 1996: "USA",
    2000: "AUS", 2004: "GRE", 2008: "CHN", 2012: "GBR", 2016: "BRA", 2020: "JPN", 2024: "FRA", 2028: "USA",
}

P = {  # Wikipedia pages
    "rwc": "Rugby World Cup", "rwc_rec": "Records and statistics of the Rugby World Cup", "rwc_all": "Rugby World Cup all-time table",
    "wrwc": "Women's Rugby World Cup", "wrwc_rec": "Records and statistics of the Women's Rugby World Cup",
    "fiba": "FIBA Basketball World Cup", "fiba_rec": "FIBA Basketball World Cup records", "wfiba": "FIBA Women's Basketball World Cup",
    "olybask": "Basketball at the Summer Olympics",
    "vb": "FIVB Men's Volleyball World Cup", "wvb": "FIVB Women's Volleyball World Cup", "olyvb": "Volleyball at the Summer Olympics",
    "hk": "Men's FIH Hockey World Cup", "whk": "Women's FIH Hockey World Cup", "olyhk": "Field hockey at the Summer Olympics",
}


def ed(page, *needles, nth=0, olympics=False):
    return {"page": page, "needles": needles, "nth": nth, "olympics": olympics}


COMPETITIONS = {
    # ---------- Rugby ----------
    "rugby-wc-men": {
        "sport": "rugby", "label": "Rugby World Cup", "gender": "Men", "unit": "points",
        "editions": ed(P["rwc"], "year", "host", "first place game"),
        "participation": (P["rwc"], ("#team", "1987", "1991"), 0),
        "participation_token": "Q",  # this table marks each qualification with "Q"
        "stats": (P["rwc"], ("year", "host(s)", "teams", "matches", "total attendance"), 0),
        "alltime": (P["rwc_all"], ("country", "apps", "pld"), 0,
                    {"Country": "team", "Apps": "apps", "Pld": "pld", "W": "w", "D": "d", "L": "l", "PF": "pf", "PA": "pa", "Pts": "pts"}),
        "players": [
            ("Most points", P["rwc_rec"], ("points", "name", "team", "app.", "tries"), 0, {"Points": "value", "Name": "name", "Team": "team", "App.": "apps"}),
            ("Most tries", P["rwc_rec"], ("tries", "name", "team", "tournaments"), 0, {"Tries": "value", "Name": "name", "Team": "team", "Tournaments": "years"}),
            ("Most appearances", P["rwc_rec"], ("app.", "name", "team", "tournaments"), 0, {"App.": "value", "Name": "name", "Team": "team", "Tournaments": "years"}),
        ],
        "history": {"RSA": 4, "NZL": 3, "AUS": 2, "ENG": 1}, "history_through": 2023,
    },
    "rugby-wc-women": {
        "sport": "rugby", "label": "Women's Rugby World Cup", "gender": "Women", "unit": "points",
        "editions": ed(P["wrwc"], "year", "hosts", "final"),
        "participation": (P["wrwc"], ("#team", "1991", "1994"), 0),
        "players": [
            ("Most points", P["wrwc_rec"], ("rank", "name", "team", "points", "tries"), 0, {"Points": "value", "Name": "name", "Team": "team", "Tournaments": "years"}),
            ("Most tries", P["wrwc_rec"], ("rank", "name", "team", "tries", "tournaments"), 0, {"Tries": "value", "Name": "name", "Team": "team", "Tournaments": "years"}),
            ("Most appearances", P["wrwc_rec"], ("rank", "name", "team", "appearances"), 0, {"Appearances": "value", "Name": "name", "Team": "team", "Tournaments": "years"}),
        ],
        "history": {"NZL": 6, "ENG": 2, "USA": 1}, "history_through": 2021,
    },
    # ---------- Basketball ----------
    "basketball-wc-men": {
        "sport": "basketball", "label": "FIBA World Cup", "gender": "Men", "unit": "points",
        "editions": ed(P["fiba"], "year", "hosts", "final", "number of teams"),
        "alltime": (P["fiba_rec"], ("team", "games played", "wins", "losses", "points for"), 0,
                    {"Team": "team", "Games played": "pld", "Wins": "w", "Losses": "l", "Points for": "pf", "Points against": "pa"}),
        "players": [
            ("Most career points", P["fiba_rec"], ("player", "games played", "points scored"), 0, {"Points Scored": "value", "Player": "name", "Games Played": "apps"}),
            ("Most World Cups", P["fiba_rec"], ("player", "number of world cups", "games played"), 0, {"Number of World Cups": "value", "Player": "name", "Games Played": "apps", "Years played": "years"}),
            ("Most medals", P["fiba"], ("rank", "player", "country", "gold"), 0, {"Total": "value", "Player": "name", "Country": "team", "Gold": "gold"}),
        ],
        "history": {"USA": 5, "URS": 3, "YUG": 3, "FRY": 2, "BRA": 2, "ESP": 2, "ARG": 1, "GER": 1}, "history_through": 2023,
    },
    "basketball-wc-women": {
        "sport": "basketball", "label": "FIBA Women's World Cup", "gender": "Women", "unit": "points",
        "editions": ed(P["wfiba"], "year", "hosts", "final", "number of teams"),
        "players": [
            ("Most medals", P["wfiba"], ("rank", "player", "country", "gold"), 0, {"Total": "value", "Player": "name", "Country": "team", "Gold": "gold"}),
        ],
        "history": {"USA": 11, "URS": 6, "AUS": 1}, "history_through": 2022,
    },
    "basketball-olympics-men": {
        "sport": "basketball", "label": "Olympic Games", "gender": "Men", "unit": "points",
        "editions": ed(P["olybask"], "year", "hosts", "gold medal game", nth=0, olympics=True),
        "participation": (P["olybask"], ("#nation", "1936", "1948"), 0),
        "alltime": (P["olybask"], ("team", "games played", "wins", "losses"), 0, {"Team": "team", "Games played": "pld", "Wins": "w", "Losses": "l"}),
        "players": [("Most points", P["olybask"], ("player", "pts"), 0, {"PTS": "value", "Player": "name"})],
        "history": {"USA": 17, "URS": 2, "YUG": 1, "ARG": 1}, "history_through": 2024,
    },
    "basketball-olympics-women": {
        "sport": "basketball", "label": "Olympic Games", "gender": "Women", "unit": "points",
        "editions": ed(P["olybask"], "year", "hosts", "gold medal game", nth=1, olympics=True),
        "participation": (P["olybask"], ("#nation", "1976", "1980"), 1),
        "alltime": (P["olybask"], ("team", "games played", "wins", "losses"), 1, {"Team": "team", "Games played": "pld", "Wins": "w", "Losses": "l"}),
        "players": [("Most points", P["olybask"], ("player", "pts"), 2, {"PTS": "value", "Player": "name"})],
        "history": {"USA": 10, "URS": 2, "EUN": 1}, "history_through": 2024,
    },
    # ---------- Volleyball ----------
    "volleyball-wc-men": {
        "sport": "volleyball", "label": "World Championship", "gender": "Men", "unit": "sets",
        "editions": ed(P["vb"], "year", "host", "final", "3rd place match"),
        "players": [("Most medals", P["vb"], ("rank", "player", "country", "gold"), 0, {"Total": "value", "Player": "name", "Country": "team", "Gold": "gold"})],
        "history": {"URS": 6, "ITA": 3}, "history_min": True, "history_through": 2022,
    },
    "volleyball-wc-women": {
        "sport": "volleyball", "label": "World Championship", "gender": "Women", "unit": "sets",
        "editions": ed(P["wvb"], "year", "host", "final", "3rd place match"),
        "players": [("Most medals", P["wvb"], ("rank", "player", "country", "gold"), 0, {"Total": "value", "Player": "name", "Country": "team", "Gold": "gold"})],
        "history": {"URS": 5, "CUB": 3, "CHN": 2}, "history_min": True, "history_through": 2022,
    },
    "volleyball-olympics-men": {
        "sport": "volleyball", "label": "Olympic Games", "gender": "Men", "unit": "sets",
        "editions": ed(P["olyvb"], "year", "host", "gold medal match", nth=0, olympics=True),
        "participation": (P["olyvb"], ("#team", "1964", "1968"), 0),
        "alltime": (P["olyvb"], ("team", "matches played", "wins", "losses"), 0, {"Team": "team", "Matches played": "pld", "Wins": "w", "Losses": "l"}),
        "history": {"URS": 3, "USA": 3, "BRA": 3, "FRA": 2}, "history_through": 2024,
    },
    "volleyball-olympics-women": {
        "sport": "volleyball", "label": "Olympic Games", "gender": "Women", "unit": "sets",
        "editions": ed(P["olyvb"], "year", "host", "gold medal match", nth=1, olympics=True),
        "participation": (P["olyvb"], ("#team", "1964", "1968"), 1),
        "alltime": (P["olyvb"], ("team", "matches played", "wins", "losses"), 1, {"Team": "team", "Matches played": "pld", "Wins": "w", "Losses": "l"}),
        "history": {"URS": 4, "CHN": 3, "CUB": 3, "BRA": 2, "JPN": 1, "ITA": 1}, "history_min": True, "history_through": 2024,
    },
    # ---------- Field hockey ----------
    "hockey-wc-men": {
        "sport": "hockey", "label": "World Cup", "gender": "Men", "unit": "goals",
        "editions": ed(P["hk"], "year", "host", "final", "third place match"),
        "participation": (P["hk"], ("#team", "1971", "1973"), 0),
        "history": {"PAK": 4, "NED": 3, "AUS": 3, "GER": 3, "IND": 1, "BEL": 1}, "history_through": 2023,
    },
    "hockey-wc-women": {
        "sport": "hockey", "label": "World Cup", "gender": "Women", "unit": "goals",
        "editions": ed(P["whk"], "year", "host", "final", "third place match"),
        "participation": (P["whk"], ("#team", "1974", "1976"), 0),
        "history": {"NED": 9, "AUS": 2, "ARG": 2}, "history_min": True, "history_through": 2022,
    },
    "hockey-olympics-men": {
        "sport": "hockey", "label": "Olympic Games", "gender": "Men", "unit": "goals",
        "editions": ed(P["olyhk"], "year", "host", "gold medal match", nth=0, olympics=True),
        "participation": (P["olyhk"], ("#team", "1908", "1920"), 0),
        "history": {"IND": 8, "PAK": 3, "AUS": 1, "ARG": 1, "BEL": 1}, "history_min": True, "history_through": 2024,
    },
    "hockey-olympics-women": {
        "sport": "hockey", "label": "Olympic Games", "gender": "Women", "unit": "goals",
        "editions": ed(P["olyhk"], "year", "host", "gold medal match", nth=1, olympics=True),
        "participation": (P["olyhk"], ("#team", "1980", "1984"), 1),
        "history": {"NED": 4, "AUS": 3}, "history_min": True, "history_through": 2024,
    },
}


# Let flag templates that use country names ({{bk-big|United States}}) resolve to codes.
for _code, (_name, _) in {**COUNTRIES, **TEAMS, **MORE_TEAMS}.items():
    W.COUNTRY_NAMES.setdefault(_name.lower(), _code)
W.COUNTRY_NAMES.update({
    "united kingdom": "GBR", "great britain": "GBR", "soviet union": "URS", "west germany": "FRG", "east germany": "GDR",
    "russia": "RUS", "unified team": "EUN", "czechoslovakia": "TCH", "yugoslavia": "YUG", "fr yugoslavia": "FRY",
    "serbia and montenegro": "SCG", "republic of china": "ROC", "chinese taipei": "TPE", "united states": "USA",
    "south korea": "KOR", "korea": "KOR", "north korea": "PRK", "iran": "IRI", "netherlands": "NED", "germany": "GER",
    "argentina": "ARG", "new zealand": "NZL", "south africa": "RSA", "australia": "AUS", "india": "IND", "pakistan": "PAK",
    "spain": "ESP", "belgium": "BEL", "england": "ENG", "scotland": "SCO", "wales": "WAL", "ireland": "IRL",
    "philippines": "PHI", "puerto rico": "PUR", "lithuania": "LTU", "rhodesia": "RHO", "zimbabwe": "ZIM",
    "russian olympic committee": "ROC", "roc": "ROC", "us": "USA", "usa": "USA", "brazil": "BRA", "italy": "ITA", "japan": "JPN", "china": "CHN",
})


def team_info(code: str) -> dict:
    name, flag = MORE_TEAMS.get(code) or TEAMS.get(code) or COUNTRIES.get(code) or (code, None)
    return {"name": name, "flag": flag, "continent": CONTINENT_OF.get(code)}


def page(title: str, refresh: bool) -> str:
    return W.fetch_raw(title, RAW_DIR / f"{slug(title)}.wiki", refresh, pause=2)


def nth_table(text: str, needles: tuple, nth: int, exact_years: bool = False) -> list[list[dict]]:
    """The nth table whose first two rows mention every needle (years must be whole header cells if exact_years)."""
    found = []
    for grid in W.all_tables(text):
        labels = [l.lower() for row in grid[:2] for l in W.header_labels(row)]
        head = " ".join(labels + [W.plain(c["text"]).lower() for row in grid[:2] for c in row])
        first = W.header_labels(grid[0])[0].lstrip("|").strip().lower() if grid and grid[0] else ""
        ok = all((first == n[1:].lower()) if n.startswith("#") else (n.lower() in head) for n in needles)
        if ok and exact_years:
            ok = all(n in labels for n in needles if n.isdigit())
        if ok:
            found.append(grid)
    if len(found) <= nth:
        raise LookupError(f"table {needles} #{nth} not found")
    return found[nth]


SCORE = re.compile(r"(\d+)\s*[–-]\s*(\d+)")


def parse_editions(cfg: dict, refresh: bool) -> list[dict]:
    spec = cfg["editions"]
    grid = nth_table(page(spec["page"], refresh), spec["needles"], spec["nth"])
    head = [W.plain(c["text"]).lower() for c in grid[0]]
    head2 = [W.plain(c["text"]).lower() for c in grid[1]] if len(grid) > 1 else head
    host_col = next((i for i, h in enumerate(head) if "host" in h), 1)
    teams_col = next((i for i, h in enumerate(head) if "teams" in h or "number" in h), None)
    editions = {}
    for row in grid[1:]:
        year = None
        for c in row[: host_col + 1]:
            m = re.search(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)", W.plain(c["text"]))
            if m:
                year = int(m.group(1))
                break
        if not year or year in editions:
            continue
        rest = row[host_col + 1:]
        if teams_col is not None and teams_col < len(row):
            rest = row[host_col + 1:teams_col]
        teams, scores = [], []
        for c in rest:
            codes = W.flag_codes(c["text"])
            if not codes and "olympic flag" in c["text"].lower():
                # Teams that competed under the Olympic flag.
                codes = [{1992: "EUN", 2018: "OAR", 2020: "ROC"}.get(year, "IOA")]
            if codes:
                teams.append(codes[0])
            else:
                m = SCORE.search(W.plain(c["text"]))
                if m:
                    scores.append(f"{m.group(1)}–{m.group(2)}")
        if len(teams) < 2:
            continue  # cancelled / not yet played
        hosts = W.flag_codes(row[host_col]["text"]) if host_col < len(row) else []
        if not hosts and spec["olympics"]:
            hosts = [OLYMPIC_HOSTS[year]] if year in OLYMPIC_HOSTS else []
        if not hosts and host_col < len(row):
            text = W.plain(row[host_col]["text"])
            code = W.COUNTRY_NAMES.get(text.split(",")[-1].strip().lower())
            hosts = [code] if code else []
        raw_final = " ".join(c["text"] for c in rest[:3]).lower()
        note = "penalties" if ("pso" in raw_final or "penalt" in raw_final or "shoot" in raw_final) else (
            "extra time" if ("aet" in raw_final or "a.e.t" in raw_final or "overtime" in raw_final or "(ot)" in raw_final) else None)
        round_robin = "round-robin" in raw_final or "round robin" in raw_final
        editions[year] = {
            "year": year, "hosts": hosts, "hostText": W.plain(row[host_col]["text"]) if host_col < len(row) else "",
            "champion": teams[0], "runnerUp": teams[1], "third": teams[2] if len(teams) > 2 else None,
            "fourth": teams[3] if len(teams) > 3 else None,
            "score": None if round_robin else (scores[0] if scores else None), "note": note, "roundRobin": round_robin,
            "teams": W.number(row[teams_col]["text"]) if teams_col is not None and teams_col < len(row) else None,
        }
    return [editions[y] for y in sorted(editions)]


def parse_stats(cfg: dict, refresh: bool) -> dict[int, dict]:
    """Optional per-edition numbers (teams, matches, attendance) from a dedicated table."""
    if "stats" not in cfg:
        return {}
    title, needles, nth = cfg["stats"]
    grid = nth_table(page(title, refresh), needles, nth)
    labels = [l.lower() for l in W.header_labels(grid[0])]
    col = lambda name: next((i for i, l in enumerate(labels) if l.startswith(name)), None)
    out = {}
    for row in grid[1:]:
        year = W.number(row[0]["text"]) if row else None
        if not year or year < 1800:
            continue
        rec = {}
        for key, name in (("teams", "teams"), ("matches", "matches"), ("attendance", "total attendance")):
            i = col(name)
            if i is not None and i < len(row) and W.number(row[i]["text"]):
                rec[key] = W.number(row[i]["text"])
        out[year] = rec
    return out


def parse_participation(cfg: dict, refresh: bool) -> list[dict] | None:
    if "participation" not in cfg:
        return None
    title, needles, nth = cfg["participation"]
    try:
        grid = nth_table(page(title, refresh), needles, nth, exact_years=True)
    except LookupError:
        return None
    years = [W.number(c["text"]) for c in grid[0]]
    out = []
    for row in grid[1:]:
        code = W.flag_code(row[0]["text"]) if row else None
        if not code:
            continue
        results = {}
        for c, y in zip(row[1:], years[1:]):
            if not y or y > date.today().year:
                continue
            text = W.plain(c["text"]).strip()
            token = cfg.get("participation_token")
            if token:
                if text == token:
                    results[str(y)] = "Qualified"
                continue
            if text and text not in ("–", "—", "-", "•", "×", "Q", "q", "DNQ", "WD") and "part of" not in text.lower() and "did not" not in text.lower():
                results[str(y)] = text
        if results:
            out.append({"team": code, "apps": len(results), "results": results})
    return out or None


def parse_alltime(cfg: dict, refresh: bool) -> list[dict] | None:
    if "alltime" not in cfg:
        return None
    title, needles, nth, columns = cfg["alltime"]
    try:
        grid = nth_table(page(title, refresh), needles, nth)
    except LookupError:
        return None
    labels = [l.lstrip("|").strip() for l in W.header_labels(grid[0])]
    index = {columns[l]: i for i, l in enumerate(labels) if l in columns}
    out = []
    for row in grid[1:]:
        code = W.flag_code(row[index["team"]]["text"]) if len(row) > index["team"] else None
        if not code:
            continue
        rec = {"team": code}
        for key, i in index.items():
            if key != "team" and i < len(row):
                rec[key] = W.number(row[i]["text"])
        if rec.get("pld"):
            out.append(rec)
    return out or None


def parse_players(cfg: dict, refresh: bool) -> list[dict]:
    out = []
    for label, title, needles, nth, columns in cfg.get("players", []):
        value_label = next(k for k, v in columns.items() if v == "value")
        text = page(title, refresh)
        try:
            grid = nth_table(text, needles, nth)
        except LookupError:
            continue
        if nth == 0:
            # Several record tables can share columns; prefer the one that leads with the requested stat.
            candidates = []
            for i in range(10):
                try:
                    g = nth_table(text, needles, i)
                except LookupError:
                    break
                labs = [W.plain(l).strip() for l in W.header_labels(g[0])]
                if value_label in labs:
                    candidates.append((labs.index(value_label), i, g))
            if candidates:
                grid = min(candidates, key=lambda c: (c[0], c[1]))[2]
        labels = [W.plain(l).strip() for l in W.header_labels(grid[0])]
        index = {columns[l]: i for i, l in enumerate(labels) if l in columns}
        if "value" not in index or "name" not in index:
            continue
        rows = []
        for row in grid[1:]:
            if len(row) <= max(index.values()):
                continue
            cell = row[index["name"]]["text"]
            name = W.person(re.sub(r"\{\{(?:flagicon|flagathlete)[^{}]*\}\}", "", cell))
            value = W.number(row[index["value"]]["text"])
            if not name or value is None:
                continue
            team = W.flag_code(row[index["team"]]["text"]) if "team" in index else None
            team = team or W.flag_code(cell)
            rec = {"name": name.strip(), "team": team, "value": value}
            for key in ("apps", "gold"):
                if key in index:
                    rec[key] = W.number(row[index[key]]["text"])
            if "years" in index:
                rec["years"] = W.plain(row[index["years"]]["text"])
            rows.append(rec)
        if rows:
            out.append({"label": label, "rows": rows[:25]})
    return out


def build(key: str, refresh: bool) -> dict:
    cfg = COMPETITIONS[key]
    editions = parse_editions(cfg, refresh)
    participation = parse_participation(cfg, refresh)
    for e in editions:
        e.update(parse_stats(cfg, refresh).get(e["year"], {}))
    if participation:
        # Fill the number of teams from the participation table where the editions table doesn't say.
        for e in editions:
            if not e["teams"]:
                e["teams"] = sum(1 for p in participation if str(e["year"]) in p["results"]) or None
    alltime = parse_alltime(cfg, refresh)
    players = parse_players(cfg, refresh)
    codes = set()
    for e in editions:
        codes |= {e["champion"], e["runnerUp"], e["third"], e["fourth"], *e["hosts"]}
    codes |= {p["team"] for p in participation or []} | {r["team"] for r in alltime or []}
    codes |= {r["team"] for t in players for r in t["rows"]}
    codes.discard(None)
    unknown = sorted(c for c in codes if team_info(c)["name"] == c)
    if unknown:
        print(f"{key}: teams without a name/flag: {unknown}", file=sys.stderr)
    pages = {cfg["editions"]["page"]} | {cfg[k][0] for k in ("participation", "alltime") if k in cfg} | {p[1] for p in cfg.get("players", [])}
    return {
        "meta": {
            "generated": date.today().isoformat(), "key": key, "sport": cfg["sport"], "label": cfg["label"], "gender": cfg["gender"],
            "unit": cfg["unit"], "through": str(editions[-1]["year"]),
            "sources": [f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}" for t in sorted(pages)],
        },
        "teams": {c: team_info(c) for c in sorted(codes)},
        "editions": editions,
        "participation": participation,
        "alltime": alltime,
        "players": players,
    }


def validate(key: str, data: dict) -> list[str]:
    cfg = COMPETITIONS[key]
    errors = []
    titles = Counter(e["champion"] for e in data["editions"] if e["year"] <= cfg["history_through"])
    for team, n in cfg["history"].items():
        ok = titles[team] >= n if cfg.get("history_min") else titles[team] == n
        if not ok:
            errors.append(f"{team}: {titles[team]} titles through {cfg['history_through']}, expected {'at least ' if cfg.get('history_min') else ''}{n}")
    if len(data["editions"]) < 8:
        errors.append(f"only {len(data['editions'])} editions")
    for e in data["editions"]:
        # 1908 Olympic hockey: England, Ireland and Scotland all medalled for Great Britain.
        if e["champion"] == e["runnerUp"] and e["year"] != 1908:
            errors.append(f"{e['year']}: champion and runner-up are the same")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download the Wikipedia pages")
    parser.add_argument("competition", nargs="*", choices=[*COMPETITIONS, []], help="default: all")
    args = parser.parse_args()
    failed = False
    for key in args.competition or COMPETITIONS:
        data = build(key, args.refresh)
        errors = validate(key, data)
        if errors:
            print(f"{key}: validation failed:\n  " + "\n  ".join(errors), file=sys.stderr)
            failed = True
            continue
        out = ROOT / data["meta"]["sport"] / "international" / "data" / f"{key}.json"
        if out.exists():
            old = json.loads(out.read_text(encoding="utf-8"))
            strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}
            if strip(old) == strip(data):
                print(f"{out.relative_to(ROOT)} is up to date")
                continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}: {len(data['editions'])} editions, through {data['meta']['through']}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
