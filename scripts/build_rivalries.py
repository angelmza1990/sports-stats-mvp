"""Build the datasets used by football/rivalries: every match of four of football's great rivalries.

- River Plate vs Boca Juniors (the Superclásico): Spanish Wikipedia, "Superclásico del fútbol argentino"
- Real Madrid vs Barcelona (El Clásico): English Wikipedia, "List of El Clásico matches" and "El Clásico";
  the dates of cup matches, which the list leaves out, come from each edition's own page
- Inter vs Milan (the Derby della Madonnina): English Wikipedia, "Derby della Madonnina" (results and rounds)
  and Italian Wikipedia, "Derby di Milano" (scorers, top scorers and appearances)
- Liverpool vs Manchester United (the North-West derby): English Wikipedia,
  "Liverpool F.C.–Manchester United F.C. rivalry", and LFChistory.net for the top scorers and appearances

Every source is Wikipedia (CC BY-SA 4.0) except LFChistory's player tables. Each rivalry is written to
football/rivalries/data/<id>.json: official matches, friendlies, knockout ties, finals and player leaders.

Usage:
    python3 scripts/build_rivalries.py            # cached pages
    python3 scripts/build_rivalries.py --refresh  # re-download them
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wikitables as W  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "raw" / "wikipedia" / "rivalries"
OUT_DIR = ROOT / "football" / "rivalries" / "data"
CLUBS = ROOT / "data" / "football" / "clubs.json"
COUNTRY_NAMES = {"ARG": ("Argentina", "ar"), "ESP": ("Spain", "es"), "ITA": ("Italy", "it"), "ENG": ("England", "gb-eng")}
TODAY = date.today().isoformat()

ES_MONTHS = {m: i + 1 for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split())}
IT_MONTHS = {m: i + 1 for i, m in enumerate(
    "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split())}
EN_MONTHS = {m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())}
EN_MONTHS.update({m[:3]: i for m, i in list(EN_MONTHS.items())})
EN_MONTHS["sept"] = 9


def page(title: str, refresh: bool, lang: str = "en") -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    name = f"{slug}.wiki" if lang == "en" else f"{lang}-{slug}.wiki"
    return W.fetch_raw(title, CACHE / name, refresh, pause=1.5, lang=lang)


def iso(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def parse_date(text: str) -> str | None:
    """Spanish, Italian and English dates, and dd/mm/yyyy."""
    t = W.plain(text).lower().replace("º", "").replace("°", "")
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:
        return iso(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.search(r"(\d{1,2})\s+(?:de\s+)?([a-zé]+)\.?\s+(?:de\s+)?(\d{4})", t)
    if m:
        mon = ES_MONTHS.get(m.group(2)) or IT_MONTHS.get(m.group(2)) or EN_MONTHS.get(m.group(2))
        if mon:
            return iso(int(m.group(3)), mon, int(m.group(1)))
    m = re.search(r"([a-z]+)\s+(\d{1,2}),?\s+(\d{4})", t)
    if m and EN_MONTHS.get(m.group(1)):
        return iso(int(m.group(3)), EN_MONTHS[m.group(1)], int(m.group(2)))
    return None


def bold(text: str) -> bool:
    return "'''" in text


def score_of(text: str) -> tuple[int, int] | None:
    t = W.plain(re.sub(r"<small>.*?</small>", "", html.unescape(text), flags=re.S))
    m = re.search(r"(\d+)\s*[–\-−]\s*(\d+)", t)
    return (int(m.group(1)), int(m.group(2))) if m else None


def shootout(text: str) -> tuple[int, int] | None:
    """A penalty shoot-out in a score cell: "(4-2p.)", "(4–2 p)", "4–3 on penalties"."""
    raw = re.sub(r"<[^>]+>", " ", text)
    m = re.search(r"\(?(\d+)\s*[–\-−]\s*(\d+)\s*(?:\[\[[^\]]*\|)?\s*(?:p\b|p\.|pen|on pen|penalties)", raw, re.I)
    return (int(m.group(1)), int(m.group(2))) if m else None


def goals_text(text: str) -> str:
    t = W.plain(text.replace("<br />", ", ").replace("<br/>", ", ").replace("<br>", ", "))
    t = t.replace("e. c.", "o.g.").replace("e.c.", "o.g.").replace("S/D", "")
    t = re.sub(r"\s*,\s*,+", ",", t).strip(" ,")
    return t


def label_index(header: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i, c in enumerate(header):
        lab = W.plain(c["text"]).lower()
        lab = re.sub(r"\s+", " ", lab).strip()
        out.setdefault(lab, i)
    return out


def find(labels: dict[str, int], *names: str) -> int | None:
    for n in names:
        for lab, i in labels.items():
            if lab.startswith(n):
                return i
    return None


# ---------------------------------------------------------------- Superclásico


RIVER, BOCA = "river-plate", "boca-juniors"
ES_ROUNDS = {
    "treintaidosavos de final": "Round of 64", "dieciseisavos de final": "Round of 32", "octavos de final": "Round of 16",
    "cuartos de final": "Quarter-finals", "semifinal": "Semi-finals", "semifinales": "Semi-finals", "final": "Final",
    "primera fase": "First stage", "segunda fase": "Second stage", "fase campeón": "Championship stage",
    "fase de grupos": "Group stage", "desempate": "Play-off", "fase final": "Final stage",
}
SUPER_COMPS = [
    (r"copa competencia jockey", "Copa de Competencia Jockey Club"), (r"adri[aá]n", "Copa Adrián C. Escobar"),
    (r"brit[aá]nica", "Copa de Competencia Británica"), (r"centenario", "Copa Centenario"),
    (r"supercopa argentina", "Supercopa Argentina"), (r"copa de la liga", "Copa de la Liga Profesional"),
    (r"copa argentina", "Copa Argentina"),
]


def es_team(text: str) -> str | None:
    t = W.plain(text).lower()
    if "boca" in t:
        return BOCA
    if "river" in t:
        return RIVER
    return None


def super_rows(text: str, heading: str, comp_fixed: str | None, stage: str, friendly: bool = False) -> list[dict]:
    grid = W.parse_table(W.find_table(text, heading))
    labels = label_index(grid[0])
    i_date = find(labels, "fecha")
    i_comp = find(labels, "torneo")
    i_round = find(labels, "ronda")
    i_venue = find(labels, "estadio")
    i_home, i_res, i_away = find(labels, "local"), find(labels, "resultado"), find(labels, "visitante")
    i_gh, i_ga = find(labels, "goles (l)", "goles (b)"), find(labels, "goles (v)", "goles (r)")
    by_team = "goles (b)" in labels
    out = []
    for r in grid[1:]:
        if len(r) <= max(i_home, i_res, i_away) or r[0]["header"]:
            continue
        num = W.plain(r[0]["text"])
        d = parse_date(r[i_date]["text"])
        sc = score_of(r[i_res]["text"])
        if not d or not sc:
            continue
        home, away = es_team(r[i_home]["text"]), es_team(r[i_away]["text"])
        if not home or not away or home == away:
            continue
        res_raw = r[i_res]["text"]
        if not friendly and num.strip() in ("-", "–"):
            continue  # 1919: the championship was annulled
        comp = comp_fixed
        tourn = W.plain(r[i_comp]["text"]) if i_comp is not None else ""
        if comp is None:
            comp = next((name for pat, name in SUPER_COMPS if re.search(pat, tourn, re.I)), tourn)
        rnd = ""
        if i_round is not None:
            # The Libertadores table splits "Ronda" in two: the stage, then the matchday ("R. 1"), which is dropped.
            rnd = W.plain(r[i_round]["text"])
            rnd = ES_ROUNDS.get(rnd.lower(), rnd)
            if stage == "league":
                rnd = ""
        venue_raw = r[i_venue]["text"] if i_venue is not None else ""
        m = {
            "date": d, "comp": comp, "season": tourn if stage == "league" else (re.search(r"\d{4}(?:[/-]\d{2,4})?", tourn).group(0) if re.search(r"\d{4}", tourn) else d[:4]),
            "round": rnd, "home": home, "away": away, "hs": sc[0], "as": sc[1],
            "venue": W.plain(venue_raw.replace("<br/>", " ").replace("<br />", " ")),
            "neutral": venue_raw.strip().startswith("''") and not venue_raw.strip().startswith("'''"),
        }
        if friendly:
            m["comp"] = "Friendly" if tourn.lower() in ("amistoso", "") else tourn
        if "t.s." in res_raw:
            m["aet"] = True
        pens = shootout(res_raw)
        if pens:
            m["pens"] = list(pens)
        if re.search(r"\(3-2\[\[saque", res_raw, re.I) or "c.]]" in res_raw:
            m["decided"] = "River won 3–2 on corner kicks"
        if "**" in res_raw and stage == "league":
            m["decided"] = "Abandoned at 1–1; awarded 2–1 to Boca"
        if (r[i_home]["text"].count("'''") and m["hs"] == m["as"]) or (r[i_away]["text"].count("'''") and m["hs"] == m["as"]):
            m["advanced"] = home if bold(r[i_home]["text"]) else away
        gh, ga = goals_text(r[i_gh]["text"]) if i_gh is not None else "", goals_text(r[i_ga]["text"]) if i_ga is not None else ""
        if by_team:  # friendlies list Boca's scorers first, then River's
            gh, ga = (gh, ga) if home == BOCA else (ga, gh)
        m["goalsHome"], m["goalsAway"] = gh, ga
        m["stage"] = stage
        out.append(m)
    return out


def super_leaders(text: str, heading: str, value_label: str) -> list[dict]:
    grid = W.parse_table(W.find_table(text, heading))
    out = []
    for r in grid:
        if r[0]["header"] or len(r) < 4:
            continue
        name = W.person(r[1]["text"])
        team_t = W.plain(r[2]["text"]).lower()
        team = "both" if "ambos" in team_t else BOCA if "boca" in team_t else RIVER if "river" in team_t else None
        if not name or not team:
            continue
        if value_label == "goals":
            # Total P.J. and G. are the 3rd and 2nd last columns (the last is the average).
            apps, goals = W.number(r[-3]["text"]), W.number(r[-2]["text"])
            out.append({"name": name, "team": team, "goals": goals, "apps": apps})
        else:
            out.append({"name": name, "team": team, "apps": W.number(r[-1]["text"])})
    key = "goals" if value_label == "goals" else "apps"
    return sorted((o for o in out if o.get(key)), key=lambda o: -o[key])


def super_ties(text: str) -> list[dict]:
    grid = W.parse_table(W.find_table(text, r"== Eliminaciones directas por torneos oficiales =="))
    out = []
    for r in grid[1:]:
        if len(r) < 5:
            continue
        tourn = W.plain(r[1]["text"])
        raw = r[4]["text"]
        result = W.plain(re.sub(r"\{\{color\|[^|]*\|", "", raw, flags=re.I).replace("}}", ""))
        winner = RIVER if re.search(r"(Ganador|Clasificó|Campeón) River", result) else BOCA
        legs = []
        for leg in W.plain(r[3]["text"]).split("/"):
            mm = re.match(r"\s*(\w+)\s+(\d+)\s*-\s*(\d+)\s+(\w+)", leg)
            if mm:
                legs.append({"home": es_team(mm.group(1)), "hs": int(mm.group(2)), "as": int(mm.group(3)), "away": es_team(mm.group(4))})
        intl = "90ee90" in r[0]["attrs"]
        rnd = ES_ROUNDS.get(W.plain(r[2]["text"]).lower(), W.plain(r[2]["text"]))
        rnd = {"Desempate de la 1.º Fase": "First-stage play-off", "Final rueda perdedores": "Losers' bracket final"}.get(rnd, rnd)
        year = re.search(r"\d{4}(?:-\d{2,4})?", tourn)
        comp = re.sub(r"\s*\d{4}(?:[-/]\d{2,4})?\s*", " ", tourn).strip()
        comp = {"Campeonato": "Primera División", "Metropolitano": "Metropolitano", "Nacional": "Nacional",
                "Liguilla Pre-Libertadores": "Liguilla Pre-Libertadores", "Supercopa": "Supercopa Libertadores",
                "Copa Competencia": "Copa de Competencia", "Copa Centenario": "Copa Centenario"}.get(comp, comp)
        how = ""
        if "penales" in result:
            how = "penalties " + re.search(r"\((\d+-\d+)\)", result).group(1).replace("-", "–")
        elif "esquina" in result:
            how = "corner kicks 3–2"
        elif "goles a favor" in result:
            how = "more goals scored in the tournament"
        elif "suspensión" in result or (year and year.group(0) == "2015"):
            how = "second leg abandoned"
        out.append({"comp": comp, "season": year.group(0) if year else "", "round": rnd, "intl": intl, "legs": legs,
                    "winner": winner, "how": how, "final": rnd == "Final"})
    return out


def build_superclasico(refresh: bool) -> dict:
    text = page("Superclásico del fútbol argentino", refresh, "es")
    official = (
        super_rows(text, r"=== Primera División ===", "Primera División", "league")
        + super_rows(text, r"=== Copas nacionales ===", None, "cup")
        + super_rows(text, r"=== Copa Libertadores de América ===", "Copa Libertadores", "intl")
        + super_rows(text, r"=== Otras copas internacionales ===", None, "intl")
    )
    for m in official:
        if m["comp"] == "Supercopa Sudamericana":
            m["comp"] = "Supercopa Libertadores"
        if m["stage"] == "league":
            m["season"] = re.sub(r"^(Campeonato|Torneo|Copa de Honor|Copa Campeonato)\s*", lambda x: x.group(0) if "Copa" in x.group(0) else "", m["season"]).strip() or m["date"][:4]
    friendlies = super_rows(text, r"=== Amistosos ===", None, "friendly", friendly=True)
    ties = super_ties(text)
    return {
        "id": "river-boca", "name": "Superclásico", "subtitle": "River Plate vs Boca Juniors", "country": "ARG",
        "teams": [{"id": RIVER, "name": "River Plate", "short": "River"}, {"id": BOCA, "name": "Boca Juniors", "short": "Boca"}],
        "matches": official, "friendlies": friendlies, "ties": ties,
        "scorers": super_leaders(text, r"=== Máximos goleadores ===", "goals"),
        "appearances": super_leaders(text, r"=== Mayor cantidad de partidos disputados ===", "apps"),
        "source": {"label": "Spanish Wikipedia, Superclásico del fútbol argentino",
                   "url": "https://es.wikipedia.org/wiki/Supercl%C3%A1sico_del_f%C3%BAtbol_argentino"},
        "notes": [
            "Official matches are those recognised by the AFA and CONMEBOL; the 1919 match is left out because that championship was annulled.",
            "The 1931 league match was abandoned at 1–1 and awarded 2–1 to Boca; the second leg of the 2015 Copa Libertadores round of 16 was abandoned at 0–0 and closed at that score, with Boca disqualified.",
            "Matches decided on penalties count as draws; the shoot-out decides only who went through.",
        ],
    }


# ---------------------------------------------------------------- El Clásico


MADRID, BARCA = "real-madrid", "barcelona"
CLASICO_SECTIONS = [
    (r"===Primera División matches===", "La Liga", "league"),
    (r"===Copa del Rey matches===", "Copa del Rey", "cup"),
    (r"===Copa de la Liga matches===", "Copa de la Liga", "cup"),
    (r"===Supercopa de España matches===", "Supercopa de España", "super"),
    (r"===Copa de la Coronación===", "Copa de la Coronación", "cup"),
    (r"===UEFA Champions League matches===", "European Cup / Champions League", "intl"),
]


def en_team(text: str, a: tuple[str, ...], b: tuple[str, ...], ida: str, idb: str) -> str | None:
    t = W.plain(text).lower()
    if any(x in t for x in a):
        return ida
    if any(x in t for x in b):
        return idb
    return None


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


def footballboxes(text: str) -> list[dict]:
    """Every {{Football box}} on a page: date, team1, team2 and score."""
    out = []
    for m in re.finditer(r"\{\{\s*(?:football ?box(?: collapsible)?|footballbox(?:_collapsible)?)\b", text, re.I):
        block = text[m.end():m.end() + 4000]
        nxt = re.search(r"\{\{\s*(?:football ?box|footballbox)", block, re.I)
        block = block[:nxt.start()] if nxt else block
        fields = {}
        for f in ("date", "team1", "team2", "score", "result"):
            fm = re.search(r"(?:^|\||\n)\s*" + f + r"\s*=\s*([^\n]*)", block)
            if fm:
                fields[f] = W.split_outside(fm.group(1), "|")[0]
        d = fields.get("date", "")
        sd = re.search(r"\{\{\s*(?:start date|dts)\s*\|(?:df=y\|)?\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})", d, re.I)
        when = iso(int(sd.group(1)), int(sd.group(2)), int(sd.group(3))) if sd else parse_date(d)
        sc = score_of(fields.get("score", ""))
        out.append({"date": when, "team1": fields.get("team1", ""), "team2": fields.get("team2", ""), "score": sc})
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


def football_season(d: str) -> str:
    """The European season (August to July) a date falls in: "2026-10-25" -> "2026–27"."""
    y, mo = int(d[:4]), int(d[5:7])
    start = y if mo >= 7 else y - 1
    return f"{start}–{str(start + 1)[2:]}"


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


# ---------------------------------------------------------------- Derby della Madonnina


INTER, MILAN = "inter-milan", "milan"
DERBY_ROUNDS = {"GS": "Group stage", "Final Group": "Final group", "R1": "First round", "R2": "Second round",
                "R32": "Round of 32", "R16": "Round of 16", "QF": "Quarter-finals", "SF": "Semi-finals", "final": "Final"}
DERBY_COMPS = [("Prima Categoria", "league"), ("Divisione Nazionale", "league"), ("Serie A", "league"),
               ("Campionato Alta Italia", "league"), ("Coppa Italia", "cup"), ("Supercoppa Italiana", "super"),
               ("UEFA Champions League", "intl")]


def derby_team(text: str) -> str | None:
    t = W.plain(text).lower()
    if "inter" in t or "ambrosiana" in t:
        return INTER
    if "milan" in t:
        return MILAN
    return None


def it_scorers(text: str) -> str:
    """ "25' [[Attilio Trerè]]<br />74' [[Pietro Lana]]" -> "Trerè (25), Lana (74)"; "(3)" hat-tricks without minutes kept."""
    parts = re.split(r"<br\s*/?>", text)
    out: dict[str, list[str]] = {}
    for p in parts:
        p = re.sub(r"\{\{TA\|(.*?)\}\}", r"\1", p)
        plain = W.plain(p)
        if not plain:
            continue
        mins = re.findall(r"(\d+(?:\+\d+)?)'\s*(\((?:rig|aut)\.?\))?", plain)
        name = re.sub(r"\d+(?:\+\d+)?'\s*(\((?:rig|aut)\.?\))?|,", "", plain).strip()
        count = re.search(r"\((\d)\)\s*$", name)
        name = re.sub(r"\s*\(\d\)\s*$", "", name).strip()
        name = re.sub(r"\s*\((?:rig|aut)\.?\)", "", name)
        if not name:
            continue
        marks = [m + (" pen" if "rig" in tag else " o.g." if "aut" in tag else "") for m, tag in mins]
        if not marks and count:
            marks = ["?"] * int(count.group(1))
        out.setdefault(name, []).extend(marks)
    return ", ".join(f"{n} ({', '.join(x for x in ms if x != '?')})" if any(x != "?" for x in ms) else (f"{n} ({len(ms)})" if len(ms) > 1 else n)
                     for n, ms in out.items())


def derby_scorers(text: str) -> dict[str, tuple[str, str]]:
    """Italian Wikipedia's full list: scorers of every derby, by date, as (Milan's, Inter's)."""
    grid = W.parse_table(W.find_table(text, r"== Risultati =="))
    out = {}
    for r in grid[1:]:
        if len(r) < 8:
            continue
        d = parse_date(re.sub(r"\{\{TA\|(.*?)\}\}", r"\1", r[1]["text"]))
        if d:
            out[d] = (it_scorers(r[6]["text"]), it_scorers(r[7]["text"]))
    return out


def it_leaders(text: str, heading: str, key: str) -> list[dict]:
    grid = W.parse_table(W.find_table(text, heading))
    out = []
    for r in grid[1:]:
        if len(r) < 4:
            continue
        name = W.person(r[1]["text"])
        raw = r[2]["text"]
        teams = {INTER for _ in [0] if "Calcio Inter" in raw} | {MILAN for _ in [0] if "Calcio Milan" in raw}
        team = "both" if len(teams) == 2 else next(iter(teams), None)
        val = W.number(r[3]["text"])
        if name and team and val:
            out.append({"name": name, "team": team, key: val})
    return sorted(out, key=lambda o: -o[key])


def build_derby(refresh: bool) -> dict:
    text = page("Derby della Madonnina", refresh)
    it = page("Derby di Milano", refresh, "it")
    start, end = text.index("== Official match results =="), text.index("== Statistics ==")
    scorers = derby_scorers(it)
    official = []
    for grid in W.all_tables(text[start:end]):
        for r in grid[1:]:
            if len(r) < 6:
                continue
            d = parse_date(r[2]["text"])
            sc = score_of(r[4]["text"])
            home, away = derby_team(r[3]["text"]), derby_team(r[5]["text"])
            if not d or not sc or not home or not away:
                continue  # fixtures not yet played have no score
            comp_raw = W.plain(r[1]["text"])
            comp, stage = next(((c, s) for c, s in DERBY_COMPS if comp_raw.lower().startswith(c.lower())), (comp_raw, "league"))
            rnd = comp_raw[len(comp):].strip()
            m = {"date": d, "season": W.plain(r[0]["text"]), "comp": comp, "stage": stage,
                 "round": DERBY_ROUNDS.get(rnd, rnd) if stage != "league" else "",
                 "home": home, "away": away, "hs": sc[0], "as": sc[1]}
            if comp == "Supercoppa Italiana":
                m["round"] = "Final"
                m["neutral"] = True  # Beijing 2011, Riyadh 2023 and 2025
            if comp == "Coppa Italia" and m["round"] == "Second round" and int(d[:4]) < 1980:
                m["round"] = "Second round (group)"  # the 1970s second rounds were groups of four
            if comp == "Campionato Alta Italia":
                m["comp"] = "Campionato Alta Italia (1944)"
            note = r[4]["text"]
            if re.search(r"extra time|after extra|a\.e\.t", note, re.I):
                m["aet"] = True
            pens = shootout(note)
            if pens:
                m["pens"] = list(pens)
            if re.search(r"awarded|abandon", note, re.I):
                m["decided"] = "Abandoned; awarded 3–0 to Milan" if d == "2005-04-12" else "Awarded"
            ms, isc = scorers.get(d, ("", ""))
            m["goalsHome"], m["goalsAway"] = (ms, isc) if home == MILAN else (isc, ms)
            official.append(m)
    for m in official:
        if m["date"] == "2005-04-12":
            m["decided"] = "Abandoned at 0–1 after flares from the stands; awarded 3–0 to Milan"
    return {
        "id": "inter-milan", "name": "Derby della Madonnina", "subtitle": "Inter vs Milan", "country": "ITA",
        "teams": [{"id": INTER, "name": "Inter", "short": "Inter"}, {"id": MILAN, "name": "Milan", "short": "Milan"}],
        "matches": official, "friendlies": [],
        "scorers": it_leaders(it, r"==== Marcatori ====", "goals"),
        "appearances": it_leaders(it, r"==== Presenze ====", "apps"),
        "source": {"label": "English Wikipedia, Derby della Madonnina; Italian Wikipedia, Derby di Milano",
                   "url": "https://en.wikipedia.org/wiki/Derby_della_Madonnina"},
        "notes": [
            "Friendlies are not listed match by match in the sources, so this rivalry has no friendlies tab.",
            "Inter's and Milan's scorers in each derby, and the scorer and appearance leaders, come from Italian Wikipedia.",
        ],
    }


# ---------------------------------------------------------------- North-West derby


LIVERPOOL, UNITED = "liverpool", "manchester-united"
EN_ROUNDS = [(r"semi-final", "Semi-finals"), (r"quarter-final", "Quarter-finals"), (r"\bfinal\b", "Final"),
             (r"round of 16", "Round of 16"), (r"(\d)(?:st|nd|rd|th) round", None), (r"test match", "Test match")]


def nwd_team(text: str) -> str | None:
    return en_team(text, ("liverpool",), ("manchester united", "newton heath"), LIVERPOOL, UNITED)


def nwd_comp(text: str) -> tuple[str, str, str, str]:
    """ "FA Cup 2nd round replay" -> ("FA Cup", "cup", "Second round", "replay")."""
    t = W.plain(text)
    lo = t.lower()
    leg = "replay" if "replay" in lo else ""
    if "charity shield" in lo or "community shield" in lo:
        return "FA Charity / Community Shield", "super", "Final", ""
    if lo.startswith("fa cup"):
        comp, stage = "FA Cup", "cup"
    elif "league cup" in lo:
        comp, stage = "League Cup", "cup"
    elif "europa league" in lo:
        comp, stage = "UEFA Europa League", "intl"
    elif "test match" in lo:
        comp, stage = "Football League test match", "league"
        return comp, stage, "", ""
    elif "premier league" in lo:
        return "Premier League", "league", "", ""
    elif "first division" in lo:
        return "First Division", "league", "", ""
    elif "second division" in lo:
        return "Second Division", "league", "", ""
    else:
        return t, "friendly", "", ""
    rnd = ""
    for pat, name in EN_ROUNDS:
        mm = re.search(pat, lo)
        if mm:
            rnd = name or f"{['', 'First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth'][int(mm.group(1))]} round"
            break
    return comp, stage, rnd, leg


def build_nwd(refresh: bool) -> dict:
    text = page("Liverpool F.C.–Manchester United F.C. rivalry", refresh)
    start, end = text.index("===All-time results==="), text.index("===Women's football results===")
    official, friendlies = [], []
    sections = re.split(r"\n(====[^=\n]+====)\s*\n", text[start:end])
    for heading, body in zip(sections[1::2], sections[2::2]):
        home_team = LIVERPOOL if "Liverpool in the league" in heading else UNITED if "Manchester United in the league" in heading else None
        friendly = "friendly" in heading.lower()
        for grid in W.all_tables("\n" + body):
            labels = [W.plain(c["text"]).lower() for c in grid[0]] if grid else []
            sub = [W.plain(c["text"]).lower() for c in grid[1]] if len(grid) > 1 else []
            if "date" not in labels:
                continue
            two_team = "team 1" in sub
            for r in grid[2 if two_team else 1:]:
                d = parse_date(r[0]["text"])
                if not d:
                    continue
                if two_team:
                    home, away, sc = nwd_team(r[2]["text"]), nwd_team(r[4]["text"]), score_of(r[3]["text"])
                    comp_cell = r[5]["text"]
                else:
                    home = home_team
                    away = UNITED if home_team == LIVERPOOL else LIVERPOOL
                    sc, comp_cell = score_of(r[2]["text"]), r[3]["text"]
                if not sc or not home or not away:
                    continue
                comp, stage, rnd, leg = nwd_comp(comp_cell)
                if re.search(r"war league|wartime|war cup", comp, re.I):
                    continue  # wartime matches are not official
                if friendly:
                    comp, stage, rnd, leg = (W.plain(comp_cell) or "Friendly"), "friendly", "", ""
                m = {"date": d, "comp": comp, "stage": stage, "round": rnd, "leg": leg, "home": home, "away": away,
                     "hs": sc[0], "as": sc[1], "venue": W.plain(r[1]["text"])}
                raw = " ".join(c["text"] for c in r)
                if re.search(r"a\.e\.t|aet|extra time", raw, re.I):
                    m["aet"] = True
                (friendlies if friendly else official).append(m)
    for m in official + friendlies:
        m["season"] = football_season(m["date"])
        grounds = {"Anfield", "Old Trafford", "Bank Street", "Clayton", "North Road"} | ({"Maine Road"} if m["date"] < "1950" else set())
        if m["venue"] not in grounds:
            m["neutral"] = True
    return {
        "id": "liverpool-united", "name": "North-West derby", "subtitle": "Liverpool vs Manchester United", "country": "ENG",
        "teams": [{"id": LIVERPOOL, "name": "Liverpool", "short": "Liverpool"}, {"id": UNITED, "name": "Manchester United", "short": "United"}],
        "matches": official, "friendlies": friendlies,
        "scorers": lfc_leaders(refresh, "Top scorers", "goals"),
        "appearances": lfc_leaders(refresh, "Top appearances", "apps"),
        "leadersByTeam": True,
        "source": {"label": "English Wikipedia, Liverpool F.C.–Manchester United F.C. rivalry",
                   "url": "https://en.wikipedia.org/wiki/Liverpool_F.C.%E2%80%93Manchester_United_F.C._rivalry"},
        "notes": [
            "Manchester United played as Newton Heath until 1902. Wartime matches are not counted.",
            "The sources publish only each club's top five scorers and appearance makers (LFChistory.net).",
            "Wikipedia lists only the friendlies played since 2014.",
        ],
    }


LFC_URL = "https://www.lfchistory.net/Opposition/Team/Profile/22"


def lfc_leaders(refresh: bool, title: str, key: str) -> list[dict]:
    """Each club's top five from LFChistory's head-to-head page ("Ryan Giggs 48 apps · 5 goals")."""
    cache = ROOT / "data" / "raw" / "lfchistory" / "opposition-22.html"
    if refresh or not cache.exists():
        try:
            req = urllib.request.Request(LFC_URL, headers={"User-Agent": W.USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", "replace")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(body, encoding="utf-8")
        except OSError as err:
            if not cache.exists():
                raise
            print(f"warning: LFChistory unavailable ({err}); using the saved copy", file=sys.stderr)
    t = cache.read_text(encoding="utf-8")
    t = html.unescape(re.sub(r"<[^>]+>", "\n", re.sub(r"<script.*?</script>", "", t, flags=re.S)))
    lines = [x.strip() for x in t.split("\n") if x.strip()]
    i = lines.index(title)
    out, team = [], None
    for j in range(i + 1, len(lines)):
        ln = lines[j]
        if ln in ("MANCHESTER UNITED", "LIVERPOOL"):
            if team and ln == "MANCHESTER UNITED" and any(o["team"] == UNITED for o in out):
                break
            team = UNITED if ln == "MANCHESTER UNITED" else LIVERPOOL
            continue
        mm = re.match(r"(\d+) apps · (\d+) goals?", ln)
        if mm and team:
            out.append({"name": lines[j - 1], "team": team, "apps": int(mm.group(1)), "goals": int(mm.group(2))})
        if ln in ("Top scorers", "Notes") and j > i + 1:
            break
    return sorted(out, key=lambda o: -o[key])


# ---------------------------------------------------------------- Knockout ties


def build_ties(data: dict) -> list[dict]:
    """Group knockout matches into ties (two legs, replays) and work out who went through."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for m in data["matches"]:
        rnd = m.get("round") or ""
        if m["stage"] == "league" or not rnd or re.search(r"group|stage|first round$", rnd, re.I) and m["comp"] in ("Coppa Italia",):
            continue
        if re.search(r"group|final group|championship stage|first stage", rnd, re.I):
            continue
        groups[(m["comp"], m["season"], rnd)].append(m)
    ties = []
    for (comp, season, rnd), legs in groups.items():
        legs.sort(key=lambda m: m["n"])
        a, b = (t["id"] for t in data["teams"])
        goals = {a: 0, b: 0}
        played = [x for x in legs if x.get("leg") != "replay"]
        for x in played:
            goals[x["home"]] += x["hs"]
            goals[x["away"]] += x["as"]
        last = legs[-1]
        how = ""
        if goals[a] != goals[b] and last.get("leg") != "replay":
            winner = a if goals[a] > goals[b] else b
        else:
            # Level: a replay, a shoot-out or (for two legs) away goals decide it.
            win_of = lambda x: x["home"] if x["hs"] > x["as"] else x["away"] if x["as"] > x["hs"] else None  # noqa: E731
            if last.get("pens"):
                p = last["pens"]
                winner = last["home"] if p[0] > p[1] else last["away"]
                how = f"penalties {max(p)}–{min(p)}"
            elif last.get("advanced"):
                winner, how = last["advanced"], "penalties"
            elif win_of(last) and last.get("leg") == "replay":
                winner, how = win_of(last), "replay"
            elif len(played) == 2:
                away = {x["away"]: (x["as"]) for x in played}
                if away.get(a, 0) != away.get(b, 0):
                    winner, how = (a if away.get(a, 0) > away.get(b, 0) else b), "away goals"
                else:
                    winner = TIE_OVERRIDES.get((data["id"], comp, season))
                    how = "penalties"
            else:
                winner = TIE_OVERRIDES.get((data["id"], comp, season, rnd)) or (win_of(last) if win_of(last) else None)
                if not winner:
                    winner = TIE_OVERRIDES.get((data["id"], comp, season))
        if not winner and "Shield" in comp and len(legs) == 1:
            winner, how = "shared", "shared"  # drawn Charity Shields were shared until 1993
        if not winner:
            print(f"warning: undecided tie {data['id']} {comp} {season} {rnd}", file=sys.stderr)
            continue
        if len(played) == 1 and not legs[0].get("leg") and len(legs) == 1 and goals[a] == goals[b] and not how:
            how = "penalties" if legs[0].get("pens") else ""
        ties.append({"comp": comp, "season": season, "round": rnd, "matches": [x["n"] for x in legs],
                     "winner": winner, "how": how, "final": rnd == "Final", "intl": legs[0]["stage"] == "intl",
                     "agg": [goals[a], goals[b]] if len(played) > 1 else None})
    ties.sort(key=lambda t: t["matches"][0])
    return ties


# Level ties the match data alone can't settle.
TIE_OVERRIDES: dict[tuple, str] = {}


def link_super_ties(data: dict) -> None:
    """The Superclásico's ties come from Wikipedia's own list: point each leg at its match."""
    for t in data["ties"]:
        ns = []
        y0 = int(t["season"][:4])
        for leg in t["legs"]:
            same = lambda m: (m["home"] == leg["home"] and (m["hs"], m["as"]) == (leg["hs"], leg["as"])) or \
                (m["home"] == leg["away"] and (m["hs"], m["as"]) == (leg["as"], leg["hs"]))  # noqa: E731
            cands = [m for m in data["matches"] if same(m) and y0 <= int(m["date"][:4]) <= y0 + 2 and m["n"] not in ns]
            league = t["comp"] in ("Primera División", "Metropolitano", "Nacional", "Liguilla Pre-Libertadores")
            cands = [m for m in cands if (m["comp"] == "Primera División") == league]
            if cands:
                ns.append(cands[0]["n"])
                leg["n"] = cands[0]["n"]
            else:
                print(f"note: {t['comp']} {t['season']} tie leg {leg} is not in the match list", file=sys.stderr)
        t["matches"] = ns
    dates = {m["n"]: m["date"] for m in data["matches"]}
    data["ties"].sort(key=lambda t: dates[t["matches"][0]] if t["matches"] else t["season"][:4])


# Official matches through October 2026. A rebuild that finds fewer means a source changed shape: fail and keep
# the previous data rather than publish a shorter history.
MIN_MATCHES = {"river-boca": 266, "madrid-barcelona": 265, "inter-milan": 246, "liverpool-united": 218}


def validate(data: dict) -> None:
    n = len(data["matches"])
    if n < MIN_MATCHES[data["id"]]:
        raise SystemExit(f"{data['name']}: only {n} official matches parsed (expected at least {MIN_MATCHES[data['id']]})")
    for m in data["matches"]:
        if not m.get("date") or m["home"] == m["away"]:
            raise SystemExit(f"{data['name']}: bad match {m}")
    if not data.get("scorers") or not data.get("appearances"):
        raise SystemExit(f"{data['name']}: no scorer or appearance leaders parsed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    built = []
    for build in (build_superclasico, build_clasico, build_derby, build_nwd):
        data = build(args.refresh)
        finish(data)
        if data["id"] == "river-boca":
            link_super_ties(data)
        else:
            data["ties"] = build_ties(data)
        validate(data)
        built.append(data)
    # Written only once every rivalry has passed, so a failed rebuild leaves all four files as they were.
    for data in built:
        (OUT_DIR / f"{data['id']}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        summary(data)


def finish(data: dict) -> None:
    """Sort chronologically, number the matches and stamp the build."""
    for key in ("matches", "friendlies"):
        data[key].sort(key=lambda m: (m["date"] or "9999", m.get("leg") == "replay"))
        for i, m in enumerate(data[key], 1):
            m["n"] = i
    for key in ("matches", "friendlies"):
        for m in data[key]:
            m.setdefault("season", m["date"][:4])
            m.pop("_page", None)
            m.pop("_pages", None)
    clubs = {c["id"]: c for c in json.loads(CLUBS.read_text(encoding="utf-8"))["clubs"]}
    data["clubs"] = {t["id"]: {"name": t["name"], "country": data["country"], "crest": clubs[t["id"]]["espn"]} for t in data["teams"]}
    data["countries"] = {data["country"]: {"name": COUNTRY_NAMES[data["country"]][0], "flag": COUNTRY_NAMES[data["country"]][1]}}
    data["updated"] = TODAY
    data["dataThrough"] = data["matches"][-1]["date"]


def summary(data: dict) -> None:
    a, b = (t["id"] for t in data["teams"])
    ms = data["matches"]
    wa = sum(1 for m in ms if (m["hs"] > m["as"] and m["home"] == a) or (m["as"] > m["hs"] and m["away"] == a))
    wb = sum(1 for m in ms if (m["hs"] > m["as"] and m["home"] == b) or (m["as"] > m["hs"] and m["away"] == b))
    ga = sum(m["hs"] if m["home"] == a else m["as"] for m in ms)
    gb = sum(m["hs"] if m["home"] == b else m["as"] for m in ms)
    by = Counter(m["comp"] for m in ms)
    print(f"{data['name']}: {len(ms)} official ({a} {wa}, draws {len(ms) - wa - wb}, {b} {wb}; goals {ga}-{gb}), "
          f"{len(data['friendlies'])} friendlies, {len(data['ties'])} ties, through {data['dataThrough']}", file=sys.stderr)
    print("  " + ", ".join(f"{k} {v}" for k, v in by.most_common()), file=sys.stderr)


if __name__ == "__main__":
    main()
