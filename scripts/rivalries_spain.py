"""El Clásico: Real Madrid vs Barcelona (English Wikipedia, with Spanish Wikipedia for some cup dates)."""

from __future__ import annotations

import html
import re
import sys
import time
import urllib.request

from rivalries_common import (ES_ROUNDS, ROOT, W, bold, en_team, find, football_season, footballboxes, goals_text, label_index,  # noqa: F401
                              page, parse_date, score_of, shootout)


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


def clasico_rows(text: str, heading: str, comp: str, stage: str, friendly: bool = False) -> list[dict]:
    grid = W.parse_table(W.find_table(text, heading))
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
        home, away = clasico_team(r[i_home]["text"]), clasico_team(r[i_away]["text"])
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
