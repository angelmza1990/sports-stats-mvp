"""Spanish rivalries: El Clásico (English Wikipedia, with Spanish Wikipedia for some cup dates), the Seville derby and
the Derbi de la Comunitat."""

from __future__ import annotations

import csv
import html
import io
import re
import sys
import time
import urllib.request

from rivalries_common import (ES_ROUNDS, RAW, ROOT, W, Pair, bold, box_goals, en_round, en_team, fetch_url, find, fold,  # noqa: F401
                              football_season, footballboxes, goals_text, label_index, page, parse_date, score_of, shootout)


MADRID, BARCA = "real-madrid", "barcelona"
CLASICO_SECTIONS = [
    (r"===Primera División matches===", "La Liga", "league"),
    (r"===Copa del Rey matches===", "Copa del Rey", "cup"),
    (r"===Copa de la Liga matches===", "Copa de la Liga", "cup"),
    (r"===Supercopa de España matches===", "Supercopa de España", "super"),
    (r"===Copa de la Coronación===", "Copa de la Coronación", "cup"),
    (r"===UEFA Champions League matches===", "European Cup / Champions League", "intl"),
]


def clasico_team(text: str) -> str | None:
    return en_team(text, ("real madrid", "madrid fc", "madrid"), ("barcelona",), MADRID, BARCA)


def leg_of(text: str) -> str:
    t = W.plain(text).lower()
    if "replay" in t or re.search(r"\(r\)", t):
        return "replay"
    if "first leg" in t or "1st leg" in t:
        return "first leg"
    if "second leg" in t or "2nd leg" in t:
        return "second leg"
    return ""


def clasico_rows(text: str, heading: str, comp: str, stage: str, friendly: bool = False, team=None, nth: int = 0) -> list[dict]:
    team = team or clasico_team
    grid = W.parse_table(W.find_table(text, heading, nth))
    head = grid[0]
    labels = label_index(head)
    i_date, i_season = find(labels, "date"), find(labels, "season")
    i_round, i_tourn = find(labels, "round"), find(labels, "tournament")
    i_venue = find(labels, "stadium")
    i_home, i_away, i_score = find(labels, "home team"), find(labels, "away team"), find(labels, "score")
    i_gh, i_ga = find(labels, "goals (home)"), find(labels, "goals (away)")
    two_round = i_round is not None and i_round + 1 < len(head) and head[i_round + 1] is head[i_round]
    out = []
    for r in grid[1:]:
        if len(r) <= i_score or all(c["header"] for c in r):
            continue
        sc = score_of(r[i_score]["text"])
        home, away = team(r[i_home]["text"]), team(r[i_away]["text"])
        if not sc or not home or not away or home == away:
            continue
        rnd = W.plain(r[i_round]["text"]) if i_round is not None else ""
        leg = W.plain(r[i_round + 1]["text"]) if two_round else ""
        if two_round and r[i_round + 1] is r[i_round]:
            leg = ""
        season_cell = r[i_season]["text"] if i_season is not None else ""
        m = {
            "comp": comp, "stage": stage, "home": home, "away": away, "hs": sc[0], "as": sc[1],
            "round": "" if stage == "league" else rnd, "leg": leg_of(leg or rnd),
            "goalsHome": goals_text(r[i_gh]["text"]) if i_gh is not None else "",
            "goalsAway": goals_text(r[i_ga]["text"]) if i_ga is not None else "",
        }
        if m["leg"] and m["round"].lower() in ("first leg", "second leg"):
            m["round"] = ""
        if comp == "Supercopa de España" and not m["round"]:
            m["round"] = "Final"  # played over two legs until 2018
        if i_date is not None:
            m["date"] = parse_date(r[i_date]["text"])
        if i_season is not None:
            m["season"] = W.plain(season_cell)
            link = W.links(season_cell)
            m["_page"] = link[0][0] if link else None
            # A link on the round or score cell (e.g. "1990 Copa del Rey final") is a better place to find the date.
            for cell in (r[i_round]["text"] if i_round is not None else "", leg if two_round else "", r[i_score]["text"]):
                more = [t for t, _ in W.links(cell) if not t.lower().startswith(("penalty", "replay", "extra time", "overtime", "away goals"))]
                if more:
                    m["_pages"] = more
        if i_venue is not None:
            m["venue"] = W.plain(r[i_venue]["text"])
        raw = r[i_score]["text"] + " " + " ".join(c["text"] for c in r[i_score + 1:])
        if re.search(r"a\.?e\.?t|extra time", r[i_score]["text"], re.I):
            m["aet"] = True
        pens = shootout(raw)
        if pens:
            m["pens"] = list(pens)
        if sc[0] == sc[1] and (bold(r[i_home]["text"]) or bold(r[i_away]["text"])):
            m["advanced"] = home if bold(r[i_home]["text"]) else away
        if friendly:
            tourn = W.plain(r[i_tourn]["text"]) if i_tourn is not None else ""
            m["comp"] = "Friendly" if not tourn or re.search(r"exhibition|friendly|amistoso", tourn, re.I) else tourn
            m["round"] = "" if r[i_round] is r[i_tourn] else W.plain(r[i_round]["text"])
        out.append(m)
    return out


def clasico_dates(matches: list[dict], refresh: bool) -> None:
    """Cup matches in the list have a season but no date: read it from the edition's page."""
    cache: dict[str, str] = {}
    for m in matches:
        if m.get("date"):
            continue
        found = None
        extra = []
        if m["comp"].startswith("European Cup") and m.get("_page"):
            extra = [m["_page"] + " knockout stage", m["_page"] + " knockout phase"]
        for title in (m.get("_pages") or []) + [m.get("_page")] + extra:
            if not title:
                continue
            if title not in cache:
                try:
                    cache[title] = page(title, refresh)
                except Exception as err:  # noqa: BLE001
                    print(f"warning: {title}: {err}", file=sys.stderr)
                    cache[title] = ""
                if cache[title].lstrip().lower().startswith("#redirect"):
                    target = re.search(r"\[\[([^\]|#]+)", cache[title])
                    cache[title] = page(target.group(1), refresh) if target else ""
                if refresh:
                    time.sleep(0.5)
            text = cache[title]
            infobox = re.search(r"\{\{\s*Infobox football match.*?\|\s*date\s*=\s*([^\n]*)", text, re.S | re.I)
            if infobox and title.lower().endswith("final") and m["round"] == "Final":
                found = parse_date(re.sub(r"\{\{\s*(?:start date|dts)\s*\|(?:df=y\|)?\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})[^}]*\}\}",
                                          lambda x: f"{x.group(3)}/{x.group(2)}/{x.group(1)}", infobox.group(1), flags=re.I))
                if found:
                    break
            for box in footballboxes(text):
                if box["score"] == (m["hs"], m["as"]) and clasico_team(box["team1"]) == m["home"] and clasico_team(box["team2"]) == m["away"]:
                    found = box["date"]
                    break
            if found:
                break
        if not found:
            found = es_partidos_date(m, refresh)
        if not found and (m["comp"], m["season"], m["home"], m["hs"], m["as"]) in CLASICO_APPROX:
            found = CLASICO_APPROX[(m["comp"], m["season"], m["home"], m["hs"], m["as"])]
            m["approxDate"] = True
        m["date"] = found
        if not m["date"]:
            print(f"warning: no date for {m['comp']} {m['season']} {m['round']} {m['home']} {m['hs']}-{m['as']}", file=sys.stderr)


def es_cup_title(m: dict) -> str | None:
    """Spanish Wikipedia's page for a Spanish cup edition ("Copa del Generalísimo de fútbol 1959")."""
    years = re.findall(r"\d{4}|\d{2}$", m["season"])
    if not years:
        return None
    start = int(years[0])
    end = start + 1 if len(years) > 1 else start
    if m["comp"] == "Copa de la Liga":
        return f"Copa de la Liga de Primera División {end}"
    if m["comp"] != "Copa del Rey":
        return None
    if 1939 <= end <= 1976:
        return f"Copa del Generalísimo de fútbol {end}"
    if end < 1939:
        return f"Copa del Rey de fútbol {start}"
    return f"Copa del Rey de fútbol {start}-{str(end)[2:]}"


def es_partidos_date(m: dict, refresh: bool) -> str | None:
    """The date from Spanish Wikipedia's {{Partidos}} boxes (local, visita, resultado, fecha)."""
    title = es_cup_title(m)
    if not title:
        return None
    try:
        text = page(title, refresh, "es")
    except Exception as err:  # noqa: BLE001
        print(f"warning: {title}: {err}", file=sys.stderr)
        return None
    for box in re.finditer(r"\{\{\s*Partidos\b(.*?)\n\}\}", text, re.S | re.I):
        f = {k.strip(): v.strip() for k, v in re.findall(r"\|\s*(local|visita|resultado|fecha)\s*=\s*([^\n]*)", box.group(1))}
        if clasico_team(f.get("local", "")) == m["home"] and clasico_team(f.get("visita", "")) == m["away"] \
                and score_of(f.get("resultado", "")) == (m["hs"], m["as"]):
            return parse_date(f.get("fecha", ""))
    return None


# Cup Clásicos that no source we can read dates to the day. Spanish cup rounds of the time were played after
# the league season (May and June); these estimates keep each match in the right season and order, and the
# page marks them as approximate.
CLASICO_APPROX: dict[tuple, str] = {
    ("Copa del Rey", "1926", MADRID, 1, 5): "1926-04-11", ("Copa del Rey", "1926", BARCA, 3, 0): "1926-04-18",
    ("Copa del Rey", "1943", BARCA, 3, 0): "1943-06-06",
    ("Copa del Rey", "1954", MADRID, 1, 0): "1954-06-13", ("Copa del Rey", "1954", BARCA, 3, 1): "1954-06-20",
    ("Copa del Rey", "1957", MADRID, 2, 2): "1957-05-12", ("Copa del Rey", "1957", BARCA, 6, 1): "1957-05-19",
    ("Copa del Rey", "1958–59", MADRID, 2, 4): "1959-06-14", ("Copa del Rey", "1958–59", BARCA, 3, 1): "1959-06-21",
    ("Copa del Rey", "1961–62", MADRID, 0, 1): "1962-06-03", ("Copa del Rey", "1961–62", BARCA, 1, 3): "1962-06-10",
    ("Copa del Rey", "1969–70", MADRID, 2, 0): "1970-05-24", ("Copa del Rey", "1969–70", BARCA, 1, 1): "1970-05-31",
    ("Copa de la Liga", "1984–85", BARCA, 2, 2): "1985-05-22", ("Copa de la Liga", "1984–85", MADRID, 1, 1): "1985-05-29",
    ("Copa de la Liga", "1985–86", BARCA, 2, 2): "1986-05-14", ("Copa de la Liga", "1985–86", MADRID, 0, 4): "1986-05-21",
}


def clasico_leaders(text: str) -> tuple[list[dict], list[dict]]:
    """Top scorers (official matches) and most appearances from the "El Clásico" article."""
    scorers, apps = [], []
    grid = W.parse_table(W.find_table(text, r"=====Top goalscorers====="))
    for r in grid[1:]:
        if len(r) < 9:
            continue
        name, team = W.person(r[1]["text"]), clasico_team(r[2]["text"])
        goals = W.number(r[-1]["text"])
        if "/" in W.plain(r[2]["text"]) or "both" in W.plain(r[2]["text"]).lower():
            team = "both"
        if name and team and goals:
            scorers.append({"name": name, "team": team, "goals": goals})
    grid = W.parse_table(W.find_table(text, r"====Most appearances===="))
    for r in grid[1:]:
        if len(r) < 3:
            continue
        n, name, team = W.number(r[0]["text"]), W.person(r[1]["text"]), clasico_team(r[2]["text"])
        if n and name and team:
            apps.append({"name": name, "team": team, "apps": n})
    return sorted(scorers, key=lambda o: -o["goals"]), sorted(apps, key=lambda o: -o["apps"])


def build_clasico(refresh: bool) -> dict:
    text = page("List of El Clásico matches", refresh)
    official = []
    for heading, comp, stage in CLASICO_SECTIONS:
        official += clasico_rows(text, heading, comp, stage)
    friendlies = clasico_rows(text, r"==Friendlies and other matches==", "Friendly", "friendly", friendly=True)
    clasico_dates(official, refresh)
    for m in official:
        if m["comp"] == "La Liga":
            # Seasons played within one calendar year (1929 to 1939) keep that year.
            m["season"] = m["date"][:4] if m["date"] < "1940-07-01" else football_season(m["date"])
        # Cup finals and the one-match Supercopas (in Saudi Arabia since 2020) are played at neutral venues.
        if (m["round"] == "Final" and not m.get("leg")) or (m["comp"] == "Supercopa de España" and not m.get("leg")):
            m["neutral"] = True
    scorers, apps = clasico_leaders(page("El Clásico", refresh))
    return {
        "id": "madrid-barcelona", "name": "El Clásico", "subtitle": "Real Madrid vs Barcelona", "country": "ESP",
        "teams": [{"id": MADRID, "name": "Real Madrid", "short": "Madrid"}, {"id": BARCA, "name": "Barcelona", "short": "Barça"}],
        "matches": official, "friendlies": friendlies, "ties": [], "scorers": scorers, "appearances": apps,
        "source": {"label": "English Wikipedia, List of El Clásico matches", "url": "https://en.wikipedia.org/wiki/List_of_El_Cl%C3%A1sico_matches"},
        "notes": [
            "Official matches include the 1902 Copa de la Coronación semi-final, as the source does; the Spanish federation recognises the tournament but not as a Copa del Rey.",
            "The list gives no exact date for some cup matches before 1987; those are placed in the right season by estimate and marked ≈.",
            "Scorer and appearance leaders come from the El Clásico article and count official matches only.",
        ],
    }


# ---------------------------------------------------------------- Derbies listed season by season, with dates

SEVILLA, BETIS = "sevilla", "real-betis"
VALENCIA, VILLARREAL = "valencia", "villarreal-cf"
EURO_COMPS = [(r"europa league", "UEFA Europa League"), (r"uefa cup", "UEFA Cup"), (r"champions", "UEFA Champions League")]


def en_comp(text: str) -> tuple[str, str]:
    """(competition, stage) from a cell: "Copa del Generalísimo" -> ("Copa del Rey", "cup")."""
    t = W.plain(text).lower()
    for pat, name in EURO_COMPS:
        if re.search(pat, t):
            return name, "intl"
    if re.search(r"copa del rey|generalísimo|generalisimo|copa de españa", t):
        return "Copa del Rey", "cup"
    if "supercopa" in t:
        return "Supercopa de España", "super"
    if "segunda" in t:
        return "Segunda División", "league"
    return "La Liga", "league"


def half_league_rows(text: str, heading: str, pair: Pair) -> list[dict]:
    """League tables with one row per season and two halves, "A vs B" then "B vs A": Date, Venue, Score, Attendance."""
    grid = W.parse_table(W.find_table(text, heading))
    first_home = pair.team(" ".join(c["text"] for c in grid[0][2:]))
    other = pair.other(first_home)
    out = []
    for r in grid[2:]:
        if len(r) < 10:
            continue
        comp, stage = en_comp(r[1]["text"])
        for home, i in ((first_home, 2), (other, 6)):
            d, sc = parse_date(r[i]["text"]), score_of(r[i + 2]["text"])
            if not d or not sc:
                continue  # not played yet
            out.append({"date": d, "season": W.plain(r[0]["text"]), "comp": comp, "stage": stage, "home": home,
                        "away": pair.other(home), "hs": sc[0], "as": sc[1], "venue": W.plain(r[i + 1]["text"])})
    return out


def cup_rows(text: str, heading: str, pair: Pair, grounds: dict[str, str]) -> list[dict]:
    """Season, Competition, Round, Date, Stadium/Venue, [Home team, Result, Away team | Score], Attendance, [Outcome].
    Without home and away columns, the ground says who was at home."""
    grid = W.parse_table(W.find_table(text, heading))
    labels = label_index(grid[0])
    i_round, i_date = find(labels, "round"), find(labels, "date")
    i_venue = find(labels, "stadium", "venue")
    i_home, i_away = find(labels, "home team"), find(labels, "away team")
    i_score = find(labels, "result", "score")
    i_out = find(labels, "outcome")
    out = []
    for r in grid[1:]:
        if len(r) <= i_score:
            continue
        d, sc = parse_date(r[i_date]["text"]), score_of(r[i_score]["text"])
        venue = W.plain(r[i_venue]["text"])
        if i_home is not None:
            home, away = pair.team(r[i_home]["text"]), pair.team(r[i_away]["text"])
        else:
            home = next((club for ground, club in grounds.items() if ground in venue.lower()), None)
            away = pair.other(home) if home else None
        if not d or not sc or not home or not away or home == away:
            continue
        comp, stage = en_comp(r[1]["text"])
        raw_round = W.plain(r[i_round]["text"])
        m = {"date": d, "season": W.plain(r[0]["text"]), "comp": comp, "stage": stage,
             "round": en_round(raw_round) or raw_round, "leg": leg_of(raw_round.replace("leg 1", "first leg").replace("leg 2", "second leg")),
             "home": home, "away": away, "hs": sc[0], "as": sc[1], "venue": venue}
        note = r[i_score]["text"] + " " + (r[i_out]["text"] if i_out is not None else "")
        if re.search(r"a\.?e\.?t|extra time", r[i_score]["text"], re.I):
            m["aet"] = True
        pso = re.search(r"\{\{\s*pso\s*\|\s*(\d+)\s*[–-]\s*(\d+)", r[i_score]["text"], re.I)
        pens = (int(pso.group(1)), int(pso.group(2))) if pso else shootout(r[i_score]["text"])
        won = re.search(r"(\w[\w ]+?) won (\d+)\s*[–-]\s*(\d+) on penalties", W.plain(note))
        if pens:
            m["pens"] = list(pens)
        elif won and m["leg"] != "first leg":  # a level single match, or the second leg of a level tie
            w = pair.team(won.group(1))
            hi, lo = int(won.group(2)), int(won.group(3))
            m["pens"] = [hi, lo] if w == home else [lo, hi]
        if re.search(r"abandon|suspend", W.plain(note), re.I):
            m["decided"] = "Abandoned and completed later; the result stood"
        if m["round"] == "Final" and not m["leg"]:
            m["neutral"] = True
        out.append(m)
    return out


def table_leaders(text: str, heading: str, key: str, pair: Pair) -> list[dict]:
    """A leaders table with Player, Team(s)/Club(s) and a Total (or Goals/Appearances) column."""
    grid = W.parse_table(W.find_table(text, heading))
    labels = label_index(grid[0])
    i_name, i_team = find(labels, "player"), find(labels, "team", "club")
    i_val = find(labels, "total", "goals", "appearances")
    out = []
    for r in grid[1:]:
        if len(r) <= max(i_name, i_team, i_val):
            continue
        name, raw, val = W.person(r[i_name]["text"]), W.plain(r[i_team]["text"]), W.number(r[i_val]["text"])
        teams = {cid for cid, names in pair.names if any(n in fold(raw) for n in names)}
        if name and teams and val:
            out.append({"name": name, "team": "both" if len(teams) == 2 else teams.pop(), key: val})
    return sorted(out, key=lambda o: -o[key])


# Dates the source gets wrong: the 1962–63 cup tie repeats the 1961–62 dates; Spanish Wikipedia's edition page has them.
DATE_FIXES = {("1962–63", "Copa del Rey", BETIS, 2, 1): "1963-05-12", ("1962–63", "Copa del Rey", SEVILLA, 1, 1): "1963-05-19"}


def build_seville(refresh: bool) -> dict:
    text = page("Seville derby", refresh)
    pair = Pair(BETIS, ("betis",), SEVILLA, ("sevilla",))
    matches = half_league_rows(text, r"==League matches==", pair)
    matches += cup_rows(text, r"==Cup matches==", pair, {})
    matches += cup_rows(text, r"==European matches==", pair, {})
    for m in matches:
        m["date"] = DATE_FIXES.get((m["season"], m["comp"], m["home"], m["hs"], m["as"]), m["date"])
    return {
        "matches": matches,
        "scorers": table_leaders(text, r"==Goalscorer records==", "goals", pair),
        "awayGoals": True,
        "source": {"label": "English Wikipedia, Seville derby", "url": "https://en.wikipedia.org/wiki/Seville_derby"},
        "notes": ["Official matches are the league (including the Segunda División), the Copa del Rey and European cups. "
                  "Regional championships and friendlies are not listed by the source.",
                  "The source publishes no appearance leaders."],
    }


def build_valencia_villarreal(refresh: bool) -> dict:
    text = page("Derbi de la Comunitat", refresh)
    pair = Pair(VALENCIA, ("valencia",), VILLARREAL, ("villarreal",))
    grounds = {"mestalla": VALENCIA, "madrigal": VILLARREAL, "ceramica": VILLARREAL, "cerámica": VILLARREAL}
    matches = half_league_rows(text, r"===League===", pair)
    matches += cup_rows(text, r"===Copa del Rey===", pair, grounds)
    matches += cup_rows(text, r"===Europe===", pair, grounds)
    return {
        "matches": matches,
        "scorers": table_leaders(text, r"===Top goalscorers===", "goals", pair),
        "appearances": table_leaders(text, r"===Appearances===", "apps", pair),
        "awayGoals": True,
        "source": {"label": "English Wikipedia, Derbi de la Comunitat", "url": "https://en.wikipedia.org/wiki/Derbi_de_la_Comunitat"},
        "notes": ["Friendlies are not listed by the source."],
    }


# ---------------------------------------------------------------- Madrid derby and Barcelona vs Atlético Madrid

ATLETICO = "atletico-madrid"
# Exact names only: "Atlético Bilbao" (Athletic Club, 1941–1972) and "Español (Barcelona)" must not match.
CLUB_NAMES = {
    MADRID: ("real madrid", "madrid fc", "madrid f.c", "madrid cf", "madrid c.f", "madrid foot"),
    ATLETICO: ("atletico madrid", "atletico de madrid", "athletic madrid", "athletic de madrid", "athletic club de madrid",
               "atletico aviacion", "athletic aviacion", "aviacion"),
    BARCA: ("barcelona",),
}
NOT_CLUB = ("espanol", "espanyol", "bilbao", "tetuan", "baleares", "barcelona atletic", "barcelona b", "barcelona amateur",
            "castilla")
SEASON_COMPS = [
    (r"international champions|pre-?season|friendl|trofeo|tournament|challenge|tour\b|exhibition", "Friendly", "friendly"),
    (r"copa de la liga", "Copa de la Liga", "cup"),
    (r"eva duarte", "Copa Eva Duarte", "super"),
    (r"uefa super cup|european super cup", "UEFA Super Cup", "intl"),
    (r"supercopa|spanish super cup", "Supercopa de España", "super"),
    (r"copa del rey|general[ií]simo|copa de espa|copa del presidente de la rep", "Copa del Rey", "cup"),
    (r"european cup|champions league", "European Cup / Champions League", "intl"),
    (r"cup winners", "Cup Winners' Cup", "intl"),
    (r"uefa cup|europa league|fairs cup", "UEFA Cup / Europa League", "intl"),
    (r"intercontinental|club world", "", "skip"),
    (r"la liga|primera divisi|^league$", "La Liga", "league"),
]
ESD_URL = "https://raw.githubusercontent.com/jalapic/engsoccerdata/master/data-raw/spain.csv"
ESD_NAMES = {"Real Madrid": MADRID, "Atletico Madrid": ATLETICO, "FC Barcelona": BARCA}
MONTHS = {m: i + 1 for i, m in enumerate("january february march april may june july august september october november december".split())}


def big_club(text: str, clubs: tuple[str, str]) -> str | None:
    """Which of the two clubs a name or link is, or None for anyone else."""
    for t in (fold(W.plain(text)), fold(text)):
        t = t.replace("é", "e")
        hits = [(t.find(n), cid) for cid in clubs for n in CLUB_NAMES[cid] if n in t]
        if hits:
            pos, cid = min(hits)
            if not any(x in t for x in NOT_CLUB) or cid == MADRID and "real madrid" in t:
                return cid
    return None


def season_label(start: int) -> str:
    return "1999–2000" if start == 1999 else f"{start}–{str(start + 1)[2:]}"


def esd_league(refresh: bool, clubs: tuple[str, str]) -> list[dict]:
    """engsoccerdata's La Liga results between the big three (1928–29 to 2024–25), cached as just those rows."""
    cache = RAW / "engsoccerdata" / "spain-big-three.csv"
    if refresh or not cache.exists():
        print(f"downloading {ESD_URL}", file=sys.stderr)
        try:
            req = urllib.request.Request(ESD_URL, headers={"User-Agent": W.USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                rows = list(csv.reader(io.StringIO(resp.read().decode("utf-8"))))
            keep = [rows[0]] + [r for r in rows[1:] if r[2] in ESD_NAMES and r[3] in ESD_NAMES]
            cache.parent.mkdir(parents=True, exist_ok=True)
            with cache.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows(keep)
        except OSError as err:
            if not cache.exists():
                raise
            print(f"warning: engsoccerdata Spain unavailable ({err}); using the saved copy", file=sys.stderr)
    out = []
    with cache.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            home, away = ESD_NAMES.get(r["home"]), ESD_NAMES.get(r["visitor"])
            if {home, away} != set(clubs):
                continue
            start = int(r["Season"])
            out.append({"date": r["Date"], "season": season_label(start), "comp": "La Liga", "stage": "league",
                        "home": home, "away": away, "hs": int(r["hgoal"]), "as": int(r["vgoal"]), "_start": start})
    return out


ESD_LAST = 2024  # the last season start engsoccerdata covers


def season_boxes(article: str, starts: range, clubs: tuple[str, str], refresh: bool) -> list[dict]:
    """Every football box between the two clubs in a club's season articles ("1985–86 FC Barcelona season"),
    with the competition from the nearest heading above it."""
    out = []
    for start in starts:
        title = f"{season_label(start)} {article} season"
        try:
            text = page(title, refresh)
        except Exception as err:  # noqa: BLE001 - no article for that season
            print(f"note: {title}: {err}", file=sys.stderr)
            continue
        if text.lstrip().upper().startswith("#REDIRECT"):
            continue
        heads = [(m.start(), len(m.group(1)), W.plain(m.group(2))) for m in re.finditer(r"^(=+)\s*(.+?)\s*=+\s*$", text, re.M)]
        starts_at = [m.start() for m in re.finditer(r"\{\{\s*(?:football ?box(?: collapsible)?|footballbox(?:_collapsible)?)\b", text, re.I)]
        for pos, box in zip(starts_at, footballboxes(text)):
            home, away = big_club(box["team1"], clubs), big_club(box["team2"], clubs)
            if not home or not away or home == away or not box["date"] or not box["score"]:
                continue
            above = [h for h in heads if h[0] < pos]
            # Only headings inside the box's own top-level section ("Competitions", not one before "Results").
            top = max((i for i, h in enumerate(above) if h[1] <= 2), default=0)
            above = above[top:]
            comp, stage = "", ""
            # Some articles mark friendlies with a banner row ('''Friendly''') rather than a heading.
            if re.search(r"'''\s*(?:friendl|pre-season)", text[above[-1][0] if above else 0:pos], re.I):
                above, comp, stage = [], "Friendly", "friendly"
            for _, level, h in reversed(above):
                hit = next(((c, s) for pat, c, s in SEASON_COMPS if re.search(pat, h, re.I)), None)
                if hit:
                    comp, stage = hit
                    break
            if not stage:
                comp, stage = next(((c, s) for pat, c, s in SEASON_COMPS if re.search(pat, box.get("round", ""), re.I)), ("", ""))
            if stage in ("", "skip"):
                continue
            sub = next((h for _, level, h in reversed(above) if level >= 4), "")
            raw_round = W.plain(box.get("round", "")) or sub
            m = {"date": box["date"], "season": football_season(box["date"]) if box["date"] >= "1940" else season_label(start), "comp": comp, "stage": stage,
                 "round": "" if stage in ("league", "friendly") else (en_round(raw_round) or en_round(sub) or ("Final" if stage == "super" else "")),
                 "leg": leg_of(raw_round + " " + sub), "home": home, "away": away, "hs": box["score"][0], "as": box["score"][1],
                 "venue": W.plain(box.get("stadium", "")), "goalsHome": box_goals(box.get("goals1", "")),
                 "goalsAway": box_goals(box.get("goals2", ""))}
            if stage == "friendly":
                m["comp"] = W.plain(box.get("round", "")) if re.search(r"trofeo|cup|copa|tournament", box.get("round", ""), re.I) else "Friendly"
            ps = score_of(box.get("penaltyscore", ""))
            if ps:
                m["pens"] = list(ps)
            score_field = re.search(r"\|\s*score\s*=\s*([^\n]*)", box["raw"])
            if re.search(r"\|\s*aet\s*=\s*(?:yes|y)\b", box["raw"], re.I) or (score_field and re.search(r"a\.e\.t|\baet\b|extra time", score_field.group(1), re.I)):
                m["aet"] = True
            out.append(m)
    seen, unique = set(), []
    for m in out:  # a match can sit in two seasons' articles
        if (m["date"], m["home"]) not in seen:
            seen.add((m["date"], m["home"]))
            unique.append(m)
    return unique


def rsssf_dates(text: str, month_hint: int | None, year: int) -> list[str]:
    """ "May 23rd and 26th" / "November 22th and March 13th 1959" -> ISO dates; the edition year fills a missing year."""
    out, month = [], month_hint
    explicit = re.search(r"\b(19\d\d|20\d\d)\b", text)
    months = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
    for mm, day in re.findall(months[:-11] + r")?[a-z]*\.?\s*(\d{1,2})(?:st|nd|rd|th)?\b(?!-)", text.lower()):
        if mm:
            month = next(i for name, i in MONTHS.items() if name.startswith(mm))
        if not month:
            continue
        y = int(explicit.group(1)) if explicit else year
        if not explicit and month >= 8 and year > 1930:
            y = year - 1  # autumn rounds of a cup that ends in spring
        out.append(f"{y:04d}-{month:02d}-{int(day):02d}")
    return out


def rsssf_cup(year: int, clubs: tuple[str, str], refresh: bool) -> list[dict]:
    """The Copa del Rey edition of a year from RSSSF, as matches between the two clubs. Two-legged ties take the
    round's two dates; group games and rounds without dates get the year only."""
    path = RAW / "rsssf" / "spain-cup" / f"spancup{year}.html"
    if not refresh and not path.exists():
        return []  # RSSSF has no page for that year (no cup, or a season page instead)
    try:
        raw = fetch_url(f"https://www.rsssf.org/tabless/spancup{year}.html", path, refresh, encoding="latin-1")
    except OSError:
        return []
    text = html.unescape(re.sub(r"<[^>]+>", "", raw))
    lines = text.splitlines()
    out, rnd, dates, leg_tag = [], "", [], ""
    for i, line in enumerate(lines):
        s = line.strip()
        if re.fullmatch(r"[A-Z][A-Z0-9 .'/-]{3,40}", s) and not re.search(r"\d-\d", s):
            if "LIGA" in s:
                break  # the Copa de la Liga (1983–1986) follows on the same page
            rnd, leg_tag = en_round(s.title()) or s.title(), ""
            nxt = next((x.strip() for x in lines[i + 1:i + 3] if x.strip()), "")
            dates = rsssf_dates(nxt, None, year) if not re.search(r"\s-\s|\d-\d", nxt) else []
            continue
        # Older pages: "Semifinals [May 9]", "First Legs [Apr 19]", "Replay [May 3, Zaragoza]".
        h = re.fullmatch(r"([A-Z][A-Za-z ]{2,30}?)\s*(?:\[([^\]]*)\])?", s)
        if h and not re.search(r"\d-\d", s) and re.search(r"final|round|leg|replay|playoff|play-off|group|stage", h.group(1), re.I):
            name = h.group(1).strip()
            if re.search(r"leg|replay|playoff|play-off", name, re.I):
                leg_tag = "first leg" if "first" in name.lower() else "second leg" if "second" in name.lower() else "replay"
            else:
                rnd, leg_tag = ("Group stage" if name.lower().startswith("group") else en_round(name) or name), ""
            dates = rsssf_dates(h.group(2) or "", None, year)
            continue
        b = re.match(r"^(.+?)\s+-\s+(.+?)\s{2,}((?:\d+-\d+\*?(?:\s*(?:aet|p))?\s*,?\s*)+)(.*)$", s)
        a = re.match(r"^(.+?)\s{2,}(\d+)-(\d+)\s{2,}(.+?)\s*(\[.*\])?$", s)
        if b:
            t1, t2 = big_club(b.group(1), clubs), big_club(b.group(2), clubs)
            scores = re.findall(r"(\d+)-(\d+)", b.group(3))
        elif a:
            t1, t2 = big_club(a.group(1), clubs), big_club(a.group(4), clubs)
            scores = [(a.group(2), a.group(3))]
        else:
            continue
        if not t1 or not t2 or t1 == t2:
            continue
        playoff = re.search(r"\[([^\]]*?),\s*([A-Za-z]+ \d{1,2})", lines[i - 1]) if i else None
        for k, (x, y) in enumerate(scores):
            two_legs = len(scores) >= 2 and rnd != "Final"
            # RSSSF gives every leg from the first-named team's side: "Las Palmas - Betis 0-1, 1-4" is Betis 4–1 at home.
            second = two_legs and k == 1
            home, away = (t2, t1) if second else (t1, t2)
            hs, as_ = (int(y), int(x)) if second else (int(x), int(y))
            m = {"season": str(year), "comp": "Copa del Rey", "stage": "cup", "round": rnd,
                 "leg": ("first leg", "second leg")[k] if two_legs and k < 2 else ("replay" if k >= 2 else leg_tag),
                 "home": home, "away": away, "hs": hs, "as": as_, "_source": "rsssf"}
            if k < len(dates) and two_legs:
                m["date"] = dates[k]
            elif len(scores) == 1 and dates:
                m["date"] = dates[0]
            elif playoff:
                m["date"] = rsssf_dates(playoff.group(2), None, year)[0]
            if k >= 2 or rnd == "Final" or m["leg"] == "replay":
                m["neutral"] = True
            if re.search(r"aet", s, re.I) and k == len(scores) - 1:
                m["aet"] = True
            if not m.get("date"):
                m["date"], m["approxDate"] = f"{year}-05-01", "year"
            out.append(m)
    return out


def efn_notes(text: str) -> dict[str, str]:
    """Named footnotes ({{efn|name=QF|Quarter-final}}), so a later {{efn|name=QF}} can be read."""
    return {n.strip(): t.strip() for n, t in re.findall(r"\{\{\s*efn\s*\|\s*name\s*=\s*([^|}]+)\|([^{}]*)\}\}", text)}


def derby_round(cell: str, notes: dict[str, str]) -> tuple[str, bool]:
    """(round, neutral venue) from a season cell's footnotes and its "Final" link."""
    texts = [x for x, _ in re.findall(r"\{\{\s*efn\s*\|\s*name\s*=\s*[^|}]+\|([^{}]*)\}\}()", cell)]
    texts += [notes.get(n.strip(), "") for n in re.findall(r"\{\{\s*efn\s*\|\s*name\s*=\s*([^|}]+)\}\}", cell)]
    texts += re.findall(r"\{\{\s*efn\s*\|([^=|{}]*)\}\}", cell)
    joined = " ".join(texts)
    rnd = "Final" if re.search(r"\|\s*Final\]\]", cell) else en_round(joined) or ("Group stage" if "group" in joined.lower() else "")
    return rnd, bool(re.search(r"neutral", joined, re.I)) or rnd == "Final"


def two_leg_order(matches: list[dict]) -> None:
    """Legs of the knockout ties in a season-by-season list: first, second, then a replay."""
    groups: dict[tuple, list[dict]] = {}
    for m in matches:
        if m["stage"] != "league" and m.get("round") and m["round"] != "Group stage":
            groups.setdefault((m["comp"], m["season"], m["round"]), []).append(m)
    for legs in groups.values():
        if len(legs) >= 2 and not any(x.get("leg") for x in legs):
            for i, x in enumerate(legs):
                x["leg"] = "first leg" if i == 0 else "second leg" if i == 1 else "replay"
                if i >= 2:
                    x["neutral"] = True


def season_keys(season: str) -> list[str]:
    """A season as the sources may label it: "1927–28" is also the "1928" cup; "2014" may be "2013–14" or "2014–15"."""
    y = [int(x) for x in re.findall(r"\d{4}", season)]
    if not y:
        return [season]
    start = y[0]
    if "–" in season:
        return [season, str(start + 1), str(start)]
    return [season, season_label(start - 1), season_label(start)]


def date_from(m: dict, pools: list[dict[tuple, dict]]) -> dict | None:
    for pool in pools:
        for season in season_keys(m["season"]):
            hit = pool.get((season, m["home"], m["hs"], m["as"]))
            if hit:
                return hit
    return None


def cup_season(year: int) -> str:
    """RSSSF's edition year as a season label: the 1926 cup is "1926", the 1960 cup "1959–60"."""
    return str(year) if year < 1940 else season_label(year - 1)


def rsssf_cups(clubs: tuple[str, str], refresh: bool, last: int = 1997) -> list[dict]:
    out = []
    for y in range(1902, last + 1):
        for m in rsssf_cup(y, clubs, refresh):
            m["season"] = cup_season(y)
            out.append(m)
    return out


def es_derby_leaders(text: str) -> tuple[list[dict], list[dict]]:
    """Spanish Wikipedia's derby tables: #, Jugador, Equipo, then games and goals per competition and in total."""
    clubs = (MADRID, ATLETICO)

    def who(cell: str) -> str | None:
        name = W.person(re.sub(r"\{\{\s*(?:bandera|flagicon|band)[^{}]*\}\}|\[\[(?:Archivo|File|Imagen):[^\]]*\]\]", "", cell))
        return name.replace("''", "").strip() if name else None

    def team(cell: str) -> str | None:
        if re.search(r"ambos", cell, re.I):
            return "both"
        found = {big_club(part, clubs) for part in re.split(r"<br\s*/?>|/|,|\sy\s", cell)} - {None}
        return "both" if len(found) == 2 else next(iter(found), None)

    scorers, apps = [], []
    for r in W.parse_table(W.find_table(text, r"=== Tabla histórica de goleadores ==="))[2:]:
        if len(r) < 17:
            continue
        name, side, goals, games = who(r[1]["text"]), team(r[2]["text"]), W.number(r[16]["text"]), W.number(r[15]["text"])
        if name and side and goals:
            scorers.append({"name": name, "team": side, "goals": goals, **({"apps": games} if games else {})})
    for r in W.parse_table(W.find_table(text, r"=== Jugadores con mayor cantidad"))[2:]:
        if len(r) < 5:
            continue
        name, side, n = who(r[1]["text"]), team(r[2]["text"]), W.number(r[3]["text"])
        if name and side and n:
            apps.append({"name": name, "team": side, "apps": n})
    return sorted(scorers, key=lambda o: -o["goals"]), sorted(apps, key=lambda o: -o["apps"])


MADRID_DERBY_SECTIONS = [
    (r"==Primera División matches==", "La Liga", "league"),
    (r"===Copa del Rey matches===", "Copa del Rey", "cup"),
    (r"===Copa de la Liga matches ===", "Copa de la Liga", "cup"),
    (r"===Supercopa de España matches===", "Supercopa de España", "super"),
    (r"===Champions League matches===", "European Cup / Champions League", "intl"),
    (r"===Super Cup matches===", "UEFA Super Cup", "intl"),
]


def build_madrid_derby(refresh: bool) -> dict:
    """The English article lists every official derby season by season; the dates come from engsoccerdata (league),
    Real Madrid's season articles and RSSSF's cup pages."""
    clubs = (MADRID, ATLETICO)
    team = lambda t: big_club(t, clubs)  # noqa: E731
    text = page("Madrid derby", refresh)
    notes = efn_notes(text)
    official = []
    for heading, comp, stage in MADRID_DERBY_SECTIONS:
        grid = W.parse_table(W.find_table(text, heading, 1))
        rows = clasico_rows(text, heading, comp, stage, team=team, nth=1)
        cells = [r for r in grid[1:] if len(r) >= 4 and score_of(r[2]["text"]) and team(r[1]["text"]) and team(r[3]["text"])]
        for m, r in zip(rows, cells):
            m["season"] = re.match(r"\d{4}(?:–\d{2,4})?", W.plain(r[0]["text"])).group(0)
            if stage != "league":
                m["round"], neutral = derby_round(r[0]["text"], notes)
                if neutral:
                    m["neutral"] = True
                if re.search(r"tiebreak|play-?off", r[2]["text"], re.I):
                    m["leg"], m["neutral"] = "replay", True
            if comp == "Supercopa de España" and not m["round"]:
                m["round"] = "Final"
        official += rows
    two_leg_order(official)
    esd = {(m["season"], m["home"], m["hs"], m["as"]): m for m in esd_league(refresh, clubs)}
    boxes = season_boxes("Real Madrid CF", range(1928, CURRENT_SEASON + 1), clubs, refresh)
    box_pool = {(m["season"], m["home"], m["hs"], m["as"]): m for m in boxes if m["stage"] != "friendly"}
    cup_pool = {(m["season"], m["home"], m["hs"], m["as"]): m for m in rsssf_cups(clubs, refresh)}
    # engsoccerdata and the list disagree on a few scores (1940–41): the league date is then found by season and home side.
    esd_home = {(m["season"], m["home"], None, None): m for m in esd.values()}
    for m in official:
        hit = date_from(m, [esd, box_pool] if m["stage"] == "league" else [box_pool, cup_pool])
        if not hit and m["stage"] == "league":
            hit = esd_home.get((m["season"], m["home"], None, None))
        if hit:
            m["date"] = hit["date"]
            for k in ("goalsHome", "goalsAway", "aet", "pens"):
                if hit.get(k) and not m.get(k):
                    m[k] = hit[k]
            if hit.get("approxDate"):
                m["approxDate"] = hit["approxDate"]
        else:
            y = re.findall(r"\d{4}|\d{2}$", m["season"])
            end = int(y[0]) + (1 if len(y) > 1 else 0) if y else 1900
            m["date"], m["approxDate"] = f"{end}-05-01", "year"
            print(f"note: Madrid derby {m['comp']} {m['season']} {m['home']} {m['hs']}-{m['as']}: no date found", file=sys.stderr)
    # The list's league section can lag a few weeks behind: add league derbies the season articles already have.
    have = {(m["season"], m["home"]) for m in official if m["stage"] == "league"}
    for b in boxes:
        if b["stage"] == "league" and (b["season"], b["home"]) not in have and b["season"] >= season_label(ESD_LAST + 1):
            official.append(b)
    friendlies = []
    for heading, comp in ((r"===Campeonato Regional Centro===", "Campeonato Regional Centro"),
                          (r"===Copa Rodriguez Arzuaga===", "Copa Rodríguez Arzuaga"), (r"===Friendlies===", "Friendly")):
        for r in W.parse_table(W.find_table(text, heading))[1:]:
            if len(r) < 4:
                continue
            d, sc, home, away = parse_date(r[0]["text"]), score_of(r[2]["text"]), team(r[1]["text"]), team(r[3]["text"])
            if d and sc and home and away and home != away:
                friendlies.append({"date": d, "season": d[:4], "comp": comp, "stage": "friendly", "home": home, "away": away,
                                   "hs": sc[0], "as": sc[1]})
    scorers, apps = es_derby_leaders(page("Derbi madrileño", refresh, "es"))
    return {
        "matches": official, "friendlies": friendlies, "scorers": scorers, "appearances": apps,
        "source": {"label": "English Wikipedia, Madrid derby", "url": "https://en.wikipedia.org/wiki/Madrid_derby",
                   "extra": [{"what": "dates from", "label": "engsoccerdata", "url": "https://github.com/jalapic/engsoccerdata"},
                             {"what": "cup dates from", "label": "RSSSF, Spain Cup", "url": "https://www.rsssf.org/tabless/spancuphist.html"},
                             {"what": "leaders from", "label": "Spanish Wikipedia, Derbi madrileño",
                              "url": "https://es.wikipedia.org/wiki/Derbi_madrile%C3%B1o"}]},
        "notes": [
            "The match list comes from the English article, which gives each match's season but not its date: league dates come from "
            "engsoccerdata and Real Madrid's season articles, cup dates from those articles and RSSSF. Dates RSSSF gives only by round are "
            "the round's scheduled day; matches without one are marked ≈.",
            "The Campeonato Regional Centro and the Copa Rodríguez Arzuaga are listed with the friendlies; the English article's list of them is incomplete.",
            "The scorer and appearance leaders come from Spanish Wikipedia and count the regional championship too.",
        ],
    }


CURRENT_SEASON = 2026  # the latest season start with a season article


def build_barcelona_atletico(refresh: bool) -> dict:
    """No source lists every Barcelona–Atlético match, so the list is put together: engsoccerdata's La Liga results,
    RSSSF's cup pages through 1972 and Barcelona's season articles (every competition) since 1973."""
    clubs = (BARCA, ATLETICO)
    league = esd_league(refresh, clubs)
    boxes = season_boxes("FC Barcelona", range(1928, CURRENT_SEASON + 1), clubs, refresh)
    boxes = [b for b in boxes if b["stage"] != "friendly"]
    matches = [m for m in league]
    matches += [b for b in boxes if b["stage"] == "league" and int(b["season"][:4]) > ESD_LAST]
    others = [b for b in boxes if b["stage"] != "league"]
    # RSSSF's cup pages (to 1997) fill the editions the season articles don't cover.
    # Through 1997 RSSSF's cup pages are the list (an article can carry a wrong year); a season article's box for the
    # same match, in the same season, adds the exact date and the scorers.
    cups = rsssf_cups(clubs, refresh)
    early = [b for b in others if b["comp"] == "Copa del Rey" and b["date"] < "1997-07-01"]
    for m in cups:
        box = next((b for b in early if (b["home"], b["hs"], b["as"]) == (m["home"], m["hs"], m["as"])
                    and b["season"] in season_keys(m["season"])), None)
        if box:
            early.remove(box)
            m.pop("approxDate", None)
            m.update({k: box[k] for k in ("date", "goalsHome", "goalsAway", "aet", "pens", "venue") if box.get(k)})
    others = [b for b in others if not (b["comp"] == "Copa del Rey" and b["date"] < "1997-07-01")] + cups
    two_leg_order(others)
    matches += others
    for m in matches:
        m.pop("_start", None)
        if m["stage"] != "league" and m["round"] == "Final" and not m.get("leg"):
            m["neutral"] = True
    return {
        "matches": matches, "friendlies": [],
        "source": {"label": "engsoccerdata (La Liga results to 2024–25)", "url": "https://github.com/jalapic/engsoccerdata",
                   "extra": [{"what": "cup matches through 1972 from", "label": "RSSSF, Spain Cup", "url": "https://www.rsssf.org/tabless/spancuphist.html"},
                             {"what": "every competition since 1973, and the league since 2025, from",
                              "label": "English Wikipedia, FC Barcelona season articles",
                              "url": "https://en.wikipedia.org/wiki/List_of_FC_Barcelona_seasons"}]},
        "notes": [
            "No source lists every Barcelona–Atlético match, so this list is assembled from three sources and may miss a few. "
            "LaLiga's own count, as of March 2026, is 254 official matches (116 Barcelona wins, 57 draws, 81 Atlético wins), "
            "including three matches in the Copa Eva Duarte and the Copa Presidente FEF, which aren't listed here.",
            "Cup dates RSSSF gives only by round are the round's scheduled day; group games of the 1920s without one are marked ≈.",
            "Friendlies are not listed by the sources, and no source publishes the scorer or appearance leaders.",
        ],
    }
