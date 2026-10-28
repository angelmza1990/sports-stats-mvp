"""Argentine rivalries: the Superclásico and the other matches between the big five (Spanish Wikipedia, RSSSF)."""

from __future__ import annotations

import html
import re
import sys
import time
import urllib.request

from rivalries_common import (ES_ROUNDS, RAW, ROOT, W, Pair, bold, en_team, fetch_url, find, fold, football_season,  # noqa: F401
                              footballboxes, goals_text, iso, label_index, page, parse_date, record, score_of, shootout)


# ---------------------------------------------------------------- Superclásico


RIVER, BOCA = "river-plate", "boca-juniors"
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


# ---------------------------------------------------------------- The rest of the big five

# Spanish Wikipedia has an article for each of the ten rivalries. Four list every official match (without dates);
# RSSSF lists, with dates, six of them. Each rivalry takes its matches from the fullest source, its dates from
# RSSSF where it can, and its knockout ties, finals and totals from Wikipedia.

INDEPENDIENTE, RACING, SAN_LORENZO = "independiente", "racing", "san-lorenzo"
ALIASES = {RIVER: ("river",), BOCA: ("boca",), INDEPENDIENTE: ("independiente",), RACING: ("racing",),
           SAN_LORENZO: ("san lorenzo",)}
GROUNDS = {
    RIVER: ("monumental", "river", "alvear y tagle", "liberti"),
    BOCA: ("bombonera", "boca", "brandsen", "armando", "wilde"),
    INDEPENDIENTE: ("independiente", "doble visera", "libertadores de america", "cordero"),
    RACING: ("racing", "cilindro", "presidente peron", "mozart"),
    SAN_LORENZO: ("san lorenzo", "gasometro", "bidegain", "avenida la plata"),
}
BIG_FIVE = {
    "independiente-racing": {"es": "Clásico de Avellaneda", "list": "es", "rsssf": "tablesi/indepracing",
                             "codes": {"I": INDEPENDIENTE, "RC": RACING}},
    "river-racing": {"es": "Clásico Racing Club-River Plate", "list": "rsssf", "rsssf": "tablesr/racingriver",
                     "codes": {"RC": RACING, "RP": RIVER}},
    "boca-racing": {"es": "Clásico Boca Juniors-Racing Club", "list": "es"},
    "racing-san-lorenzo": {"es": "Clásico Racing Club-San Lorenzo", "list": "es"},
    "boca-independiente": {"es": "Clásico Boca Juniors-Independiente", "list": "rsssf", "rsssf": "tablesb/bocaindep",
                           "codes": {"BJ": BOCA, "I": INDEPENDIENTE}},
    "river-san-lorenzo": {"es": "Clásico River Plate-San Lorenzo", "list": "rsssf", "rsssf": "tablesr/riverlorenzo",
                          "codes": {"RP": RIVER, "SL": SAN_LORENZO}},
    "boca-san-lorenzo": {"es": "Clásico Boca Juniors-San Lorenzo", "list": "rsssf", "rsssf": "tablesb/bocalorenzo",
                         "codes": {"BJ": BOCA, "SL": SAN_LORENZO}},
    "river-independiente": {"es": "Clásico Independiente-River Plate", "list": None},
    "independiente-san-lorenzo": {"es": "Clásico Independiente-San Lorenzo", "list": None},
}
AR_CUPS = [
    (r"jockey", "Copa de Competencia Jockey Club"), (r"brit[aá]nica", "Copa de Competencia Británica"),
    (r"copa (?:de )?competencia", "Copa de Competencia"), (r"copa de honor", "Copa de Honor"),
    (r"beccar", "Copa Beccar Varela"), (r"adri[aá]n|escobar", "Copa Adrián C. Escobar"),
    (r"rep[uú]blica", "Copa de la República"), (r"centenario", "Copa Centenario"), (r"copa de oro", "Copa de Oro"),
    (r"ibarguren", "Copa Ibarguren"), (r"supercopa argentina", "Supercopa Argentina"),
    (r"trofeo de campeones|copa campeonato", "Trofeo de Campeones"),
    (r"copa (?:de la )?liga", "Copa de la Liga Profesional"), (r"copa argentina", "Copa Argentina"),
    (r"supercopa (?:sudamericana|libertadores|joão|joao)|^supercopa(?: \d{4})?$", "Supercopa Libertadores"),
    (r"recopa", "Recopa Sudamericana"), (r"libertadores", "Copa Libertadores"), (r"sudamericana", "Copa Sudamericana"),
    (r"mercosur", "Copa Mercosur"), (r"conmebol", "Copa Conmebol"), (r"aldao", "Copa Aldao"),
]
INTL = {"Supercopa Libertadores", "Recopa Sudamericana", "Copa Libertadores", "Copa Sudamericana", "Copa Mercosur",
        "Copa Conmebol", "Copa Aldao"}


def ar_comp(tourn: str, section: str = "") -> tuple[str, str]:
    """(competition, stage) from a tournament name ("Copa de Honor 1917", "Apertura 1995", "Copa Libertadores 1997")."""
    t = W.plain(tourn)
    for pat, name in AR_CUPS:
        if re.search(pat, t, re.I):
            return name, "intl" if name in INTL else "cup"
    if "segunda" in section.lower() or re.search(r"segunda|second division", t, re.I):
        return "Segunda División", "league"
    if section and not re.search(r"primera|first", section, re.I):
        name = re.sub(r"\s*\d{4}(?:[-/]\d{2,4})?\s*", " ", t).strip() or t
        return name, "intl" if "internacional" in section.lower() else "cup"
    return "Primera División", "league"


LEAGUE_NAMES = r"playoff|desempate|first division|campeonato|apertura|clausura|metropolitano|nacional|liguilla|inicial|^final|transici|superliga|liga profesional|primera"


def ar_season(tourn: str) -> str:
    t = re.sub(r"\(.*?\)", "", W.plain(tourn)).strip()
    t = re.sub(r"^(Campeonato de Primera División|Campeonato|Torneo|Primera División|Segunda División|First Division|Liga Profesional)\s+", "", t, flags=re.I)
    m = re.search(r"(\d{4})\s*[-/]\s*(\d{2,4})", t)
    if m:
        return re.sub(r"(\d{4})\s*[-/]\s*(\d{2,4})", lambda x: f"{x.group(1)}–{x.group(2)[-2:]}", t).strip()
    m = re.search(r"\b(\d{2})/(\d{2})\b", t)  # RSSSF's "88/89"
    if m:
        y = int(m.group(1))
        y += 1900 if y > 30 else 2000
        return re.sub(r"\b\d{2}/\d{2}\b", f"{y}–{m.group(2)}", t).strip()
    return t


def ar_round(text: str) -> str:
    text = re.sub(r"\{\{\s*ord\s*\|\s*(\d+)\.?\s*\|\s*(\w+)\s*\}\}", r"\1\2", text, flags=re.I)  # {{ord|8.|vos}} -> 8vos
    t = W.plain(text).lower()
    t = re.sub(r"[{}|]|ord", "", t)
    if not t or re.fullmatch(r"[\d\s.ªº°r]+", t) or t.startswith(("fecha", "jornada")):
        return ""
    for pat, name in [(r"32|treintaidos", "Round of 64"), (r"16|dieciseis", "Round of 32"), (r"\b8|octavo", "Round of 16"),
                      (r"\b4|cuarto", "Quarter-finals"), (r"semi", "Semi-finals"), (r"final", "Final"),
                      (r"desempate", "Play-off"), (r"primera ronda|primera fase|1\.ª ronda", "First round"),
                      (r"segunda ronda|segunda fase", "Second round"),
                      (r"tercera ronda|tercera fase", "Third round"), (r"cuarta ronda", "Fourth round"), (r"grupo|zona", "Group stage")]:
        if re.search(pat, t):
            return name
    return W.plain(text)


def year_of(tourn: str) -> int | None:
    m = re.search(r"(1[89]\d{2}|20\d{2})", W.plain(tourn))
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{2})/(\d{2})\b", tourn)
    return (int(m.group(1)) + (1900 if int(m.group(1)) > 30 else 2000)) if m else None


def neutral_venue(venue: str, home: str, away: str) -> bool:
    v = fold(W.plain(venue))
    return bool(v) and not any(g in v for g in GROUNDS[home] + GROUNDS[away])


def es_section(text: str, heading: str) -> str:
    """The text of a section (any level) up to the next heading of the same or a higher level."""
    m = re.search(r"^(=+)\s*" + heading + r"\s*=+\s*$", text, re.M)
    if not m:
        return ""
    level = len(m.group(1))
    rest = text[m.end():]
    end = re.search(r"^={1," + str(level) + r"}[^=]", rest, re.M)
    return rest[:end.start()] if end else rest


def es_match_rows(grid: list[list[dict]], pair: Pair, section: str, comp_fixed: str | None = None) -> list[dict]:
    """Rows of a Spanish Wikipedia match table: #, Torneo, [Ronda], Estadio, [Fecha], Local, Resultado, Visitante, goals."""
    labels = label_index(grid[0])
    i_num, i_tourn, i_round = 0, find(labels, "torneo"), find(labels, "ronda")
    i_venue, i_date = find(labels, "estadio"), find(labels, "fecha")
    i_home, i_res, i_away = find(labels, "local"), find(labels, "resultado"), find(labels, "visitante")
    i_gh, i_ga = find(labels, "goles (l)"), find(labels, "goles (v)")
    if None in (i_home, i_res, i_away):
        return []
    out = []
    for order, r in enumerate(grid[1:]):
        if len(r) <= max(i_home, i_res, i_away) or r[i_home]["header"]:
            continue
        sc = score_of(r[i_res]["text"])
        home, away = pair.team(r[i_home]["text"]), pair.team(r[i_away]["text"])
        if not sc or not home or not away or home == away:
            continue
        def cell(i: int | None, r: list[dict] = r) -> str:
            return r[i]["text"] if i is not None and i < len(r) else ""

        tourn = cell(i_tourn)
        comp, stage = (comp_fixed, "league") if comp_fixed else ar_comp(tourn, section)
        venue = W.plain(re.sub(r"<br\s*/?>", " ", cell(i_venue)))
        m = {"comp": comp, "stage": stage, "season": ar_season(tourn) if stage == "league" else (str(year_of(tourn) or "")),
             "round": ar_round(cell(i_round)) if stage != "league" else "",
             "home": home, "away": away, "hs": sc[0], "as": sc[1], "venue": venue,
             "neutral": neutral_venue(cell(i_venue), home, away),
             "goalsHome": goals_text(cell(i_gh)),
             "goalsAway": goals_text(cell(i_ga)),
             "_year": year_of(tourn), "_tourn": W.plain(tourn), "_num": r[i_num], "_order": order,
             "_bold": home if bold(r[i_home]["text"]) else away if bold(r[i_away]["text"]) else None}
        if stage == "league" and i_round is not None:
            rd = W.plain(cell(i_round))
            m["_matchday"] = int(rd) if rd.isdigit() else None
            if not rd.isdigit() and ar_round(rd) not in ("", rd):
                m["round"] = ar_round(rd)  # league play-offs ("Desempate") and title deciders
        if i_date is not None:
            m["date"] = parse_date(cell(i_date))
        pens = shootout(r[i_res]["text"] + " " + r[i_home]["text"] + " " + r[i_away]["text"])
        if pens:
            m["pens"] = list(pens)
        if re.search(r"t\.\s?s\.|tiempo suplementario|pr[óo]rroga|a\.e\.t", r[i_res]["text"], re.I):
            m["aet"] = True
        out.append(m)
    return out


def es_full_list(text: str, pair: Pair) -> list[dict]:
    """Every official match from the "Partidos oficiales" section, one table per competition group."""
    body = es_section(text, "Partidos oficiales")
    out = []
    parts = re.split(r"^(={3,4})\s*([^=\n]+?)\s*={3,4}\s*$", body, flags=re.M)
    for name, sub in zip(parts[2::3], parts[3::3]):
        if name.lower().startswith("estadísticas"):
            continue
        for grid in W.all_tables("\n" + sub):
            if grid and any("local" in W.plain(c["text"]).lower() for c in grid[0]):
                out += es_match_rows(grid, pair, name, "Segunda División" if "segunda" in name.lower() else None)
    return out


def es_last_matches(text: str, pair: Pair) -> list[dict]:
    """The dated "Últimos 10 partidos" table: Fecha, Torneo, Estadio, Local, Resultado, Visitante."""
    m = re.search(r"^=+\s*Últimos 10 partidos[^=\n]*=+\s*$", text, re.M)
    if not m:
        return []
    grid = W.parse_table(W.find_table(text[m.start():], r"Últimos"))
    out = []
    for r in grid[1:]:
        if len(r) < 6 or r[0]["header"]:
            continue
        d, sc = parse_date(r[0]["text"]), score_of(r[4]["text"])
        home, away = pair.team(r[3]["text"]), pair.team(r[5]["text"])
        if not d or not sc or not home or not away or home == away:
            continue
        tourn = r[1]["text"]
        comp, stage = ar_comp(re.sub(r"\{\{small\|.*?\}\}", "", tourn))
        rnd = re.search(r"\{\{small\|\(?([^)}]*)\)?\}\}", tourn)
        mm = {"date": d, "comp": comp, "stage": stage, "season": ar_season(re.sub(r"\{\{small\|.*?\}\}", "", tourn)) if stage == "league" else d[:4],
              "round": ar_round(rnd.group(1)) if rnd else "", "home": home, "away": away, "hs": sc[0], "as": sc[1],
              "venue": W.plain(r[2]["text"]), "neutral": neutral_venue(r[2]["text"], home, away)}
        pens = shootout(r[3]["text"] + " " + r[5]["text"] + " " + r[4]["text"])
        if pens:
            mm["pens"] = list(pens)
            mm["advanced"] = home if bold(r[3]["text"]) else away if bold(r[5]["text"]) else None
        out.append(mm)
    return out


def es_totals(text: str, heading: str, pair: Pair) -> dict | None:
    """A head-to-head totals table (Competición, PJ, wins, draws, wins, goals, goals) as rows and a total."""
    m = re.search(r"^=+\s*" + heading + r"\s*=+\s*$", text, re.M)
    if not m:
        return None
    tables = W.all_tables(es_section(text, heading))
    if not tables:
        return None
    grid = tables[0]
    head = grid[0]
    # The columns are always: competition, played, wins, draws, wins, goals, goals.
    if len(head) < 5:
        return None
    played, wins, draws, goals = 1, [2, 4], 3, [5, 6] if len(head) >= 7 else []
    first = pair.team(head[2]["text"]) or (pair.team(head[5]["text"]) if goals else None)
    flip = first == pair.b
    rows = []
    for r in grid[1:]:
        if len(r) <= max(wins[1], draws, played):
            continue
        label = W.plain(r[0]["text"]).strip("* ")
        nums = [W.number(r[i]["text"]) for i in (played, wins[0], draws, wins[1])]
        gl = [W.number(r[i]["text"]) for i in goals[:2]] if len(goals) >= 2 and len(r) > goals[1] else [None, None]
        if None in nums or not label:
            continue
        n, wa, d, wb = nums
        ga, gb = gl
        if flip:
            wa, wb, ga, gb = wb, wa, gb, ga
        rows.append({"comp": label, "n": n, "a": wa, "d": d, "b": wb, "ga": ga, "gb": gb})
    total = next((x for x in rows if x["comp"].lower().startswith("total")), None)
    rows = [x for x in rows if x is not total]
    if not total and rows:
        total = {"comp": "Total", **{k: sum(x[k] or 0 for x in rows) for k in ("n", "a", "d", "b", "ga", "gb")}}
    return {"comps": rows, "total": total}


def es_ties(text: str, pair: Pair) -> list[dict]:
    """Knockout ties and finals from Wikipedia's own tables: rows grouped by their # cell."""
    ties = []
    for heading, final in ((r"(?:Enfrentamientos|Listado de partidos|Duelos) de eliminación directa", False),
                           (r"Veces que el rival eliminó al otro", False), (r"Finales disputadas entre ambos", True)):
        m = re.search(r"^=+\s*" + heading + r"\s*=+\s*$", text, re.M)
        if not m:
            continue
        for grid in W.all_tables(es_section(text, W.plain(m.group(0)).strip("= ").replace("(", r"\(").replace(")", r"\)")))[:1]:
            rows = es_match_rows(grid, pair, "Copas")
            groups: list[list[dict]] = []
            for r in rows:
                if groups and groups[-1][0]["_num"] is r["_num"]:
                    groups[-1].append(r)
                else:
                    groups.append([r])
            for legs in groups:
                first = legs[0]
                tourn = first["_tourn"]
                comp, stage = ar_comp(tourn)
                if comp == "Primera División":
                    comp = re.sub(r"\s*\d{4}.*$", "", tourn) or comp
                    comp = {"Campeonato": "Primera División", "Nacional": "Nacional", "Metropolitano": "Metropolitano"}.get(comp, comp)
                rnd = first["round"] or ar_round(tourn) or ""
                if final:
                    rnd = "Final"
                tie = {"comp": comp, "season": str(first["_year"] or ""), "round": rnd, "intl": stage == "intl",
                       "legs": [{k: x[k] for k in ("home", "away", "hs", "as")} | ({"pens": x["pens"]} if x.get("pens") else {}) for x in legs],
                       "final": final or rnd == "Final", "_legs": legs}
                goals = {pair.a: 0, pair.b: 0}
                for x in legs:
                    goals[x["home"]] += x["hs"]
                    goals[x["away"]] += x["as"]
                last = legs[-1]
                if goals[pair.a] != goals[pair.b] and len(legs) <= 2:
                    tie["winner"], tie["how"] = (pair.a if goals[pair.a] > goals[pair.b] else pair.b), ""
                elif last["hs"] != last["as"] and len(legs) > 2:
                    tie["winner"], tie["how"] = (last["home"] if last["hs"] > last["as"] else last["away"]), "replay"
                elif last.get("pens"):
                    p = last["pens"]
                    tie["winner"] = last["_bold"] or (last["home"] if p[0] > p[1] else last["away"])
                    tie["how"] = f"penalties {max(p)}–{min(p)}"
                else:
                    tie["winner"] = last["_bold"] or next((x["_bold"] for x in reversed(legs) if x["_bold"]), None)
                    tie["how"] = "penalties" if goals[pair.a] == goals[pair.b] else ""
                if not tie["winner"]:
                    print(f"warning: no winner for tie {comp} {tie['season']}", file=sys.stderr)
                    continue
                same = next((t for t in ties if t["comp"] == tie["comp"] and t["season"] == tie["season"] and t["legs"] == tie["legs"]), None)
                if same:
                    same["final"] = same["final"] or tie["final"]
                    if tie["final"]:
                        same["round"] = "Final"
                else:
                    ties.append(tie)
    return ties


def rsssf_matches(path: str, codes: dict[str, str], refresh: bool) -> tuple[list[dict], list[dict]]:
    """Official matches and friendlies from an RSSSF head-to-head list ("12.12.1915  First Division 1915  RC-I  1-2 ...")."""
    text = fetch_url(f"https://www.rsssf.org/{path}.html", RAW / "rsssf" / f"{path.split('/')[-1]}.html", refresh, "latin-1")
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    code = "|".join(sorted(map(re.escape, codes), key=len, reverse=True))
    line_re = re.compile(r"^\s*\d+\.\s+(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(.+?)\s+(" + code + r")\s*-\s*(" + code + r")\s*"
                         r"(?:\[(\d+)\])?\s*(\d+)\s*-\s*(\d+)\s*(?:\[\*+\])?(?:\[(\d+)\])?\s*(.*)$")
    official, friendlies, section = [], [], ""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        s = line.strip()
        if re.fullmatch(r"[A-Z][A-Z ]{5,}", s):
            section = s if s not in ("AMATEUR ERA", "PROFESSIONAL ERA", "OFFICIAL MATCHES") else section
            if s == "FRIENDLIES":
                section = s
            continue
        mm = line_re.match(line)
        if not mm:
            continue
        rest = mm.group(11)
        if re.search(r"annul", rest, re.I):
            continue
        d = iso(int(mm.group(3)), int(mm.group(2)), int(mm.group(1)))
        home, away = codes[mm.group(5)], codes[mm.group(6)]
        tourn = mm.group(4).strip()
        venue = re.split(r"\t+|\s{2,}", rest.strip())[0] if rest.strip() else ""
        m = {"date": d, "home": home, "away": away, "hs": int(mm.group(8)), "as": int(mm.group(9)), "venue": venue,
             "neutral": neutral_venue(venue, home, away), "_tourn": tourn, "_line": line}
        if mm.group(7) and mm.group(10):
            m["pens"] = [int(mm.group(7)), int(mm.group(10))]
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        inline = re.search(r"\[([^\]]*[a-z][^\]]*)\]\s*$", rest)
        sc = nxt if nxt.startswith("[") else (f"[{inline.group(1)}]" if inline and not re.search(r"susp|contin|award|\?\?\?", inline.group(1), re.I) else "")
        if sc:
            parts = sc.strip("[] \t").split(";")
            m["goalsHome"] = rsssf_scorers(parts[0]) if m["hs"] else ""
            m["goalsAway"] = rsssf_scorers(parts[-1] if len(parts) > 1 else (parts[0] if not m["hs"] else "")) if m["as"] else ""
        if section == "FRIENDLIES":
            m.update({"comp": "Friendly" if tourn.lower() == "friendly" else tourn, "stage": "friendly", "season": d[:4]})
            friendlies.append(m)
        else:
            comp, stage = ar_comp(tourn)
            if stage == "league" and "CUPS" in section and not re.search(LEAGUE_NAMES, tourn, re.I):
                comp, stage = ar_comp(tourn, "Copas Internacionales" if "INTERNATIONAL" in section else "Copas")
            m.update({"comp": comp, "stage": stage, "season": ar_season(tourn) if stage == "league" else (str(year_of(tourn) or d[:4]))})
            if stage == "league" and re.search(r"playoff|desempate", tourn, re.I):
                m["season"], m["round"] = d[:4], "Play-off"
            if re.search(r"award", rest, re.I):
                m["decided"] = "Awarded"
            official.append(m)
    return official, friendlies


def rsssf_scorers(text: str) -> str:
    """ "B.Ferreyra 5, 27, Peucelle 26" -> "B. Ferreyra (5, 27), Peucelle (26)"."""
    out, cur = [], None
    for tok in [t.strip() for t in text.split(",") if t.strip()]:
        mm = re.match(r"^(.*?)\s*((?:\d+(?:\+\d+)?)(?:\s*(?:pen|o/?g))?)?$", tok)
        name, minute = (mm.group(1).strip(), mm.group(2)) if mm else (tok, None)
        if name and not re.fullmatch(r"\d+.*", name):
            cur = [re.sub(r"\.(?=[A-ZÁÉÍÓÚ])", ". ", name), []]
            out.append(cur)
        if minute and cur:
            cur[1].append(minute.replace("o/g", "o.g.").replace("og", "o.g."))
    return ", ".join(f"{n} ({', '.join(ms)})" if ms else n for n, ms in out)


# League months by tournament, for the matches no source dates: (first month, last month) of the season.
SEASON_MONTHS = [(r"apertura|inicial|nacional|clausura 19[89]\d|superliga|\d{4}–\d{2}", (8, 12)),
                 (r"clausura|final|metropolitano|transici[oó]n", (2, 7))]


def approx_dates(matches: list[dict]) -> None:
    """A date for each undated match: its year, then spread through the season by matchday (marked approximate)."""
    for m in matches:
        if m.get("date") or not m.get("_year"):
            continue
        months = (3, 11)
        season = m.get("season", "")
        for pat, rng in SEASON_MONTHS:
            if m["stage"] == "league" and re.search(pat, season, re.I):
                months = rng
                break
        year = m["_year"]
        split = re.search(r"(\d{4})–\d{2}", season)
        if m["stage"] == "league" and split:
            year = int(split.group(1))
        frac = min(1, (m.get("_matchday") or 0) / 40) if m["stage"] == "league" and m.get("_matchday") else 0.5
        month = round(months[0] + frac * (months[1] - months[0]))
        m["date"] = iso(year, month, 15 if m["stage"] == "league" else 28)
        m["approxDate"] = "year"


def match_dates(matches: list[dict], dated: list[dict]) -> int:
    """Copy each match's date from a dated list of the same rivalry: same home side and score, same or next year."""
    pool = sorted(dated, key=lambda x: x["date"])
    used: set[int] = set()
    found = 0
    for stage_first in (True, False):
        for m in matches:
            if m.get("date") or not m.get("_year"):
                continue
            for i, x in enumerate(pool):
                if i in used or x["home"] != m["home"] or (x["hs"], x["as"]) != (m["hs"], m["as"]):
                    continue
                y = int(x["date"][:4])
                if not (m["_year"] <= y <= m["_year"] + 1):
                    continue
                if stage_first and (x["stage"] == "league") != (m["stage"] == "league"):
                    continue
                m["date"] = x["date"]
                if not m.get("goalsHome") and not m.get("goalsAway"):
                    m["goalsHome"], m["goalsAway"] = x.get("goalsHome", ""), x.get("goalsAway", "")
                used.add(i)
                found += 1
                break
    return found


def es_leaders(text: str, pair: Pair) -> list[dict]:
    """Top scorers ("Máximos goleadores" or "Goleadores históricos"): name, club, goals."""
    for heading in (r"Máximos goleadores", r"Goleadores históricos", r"Goleadores"):
        sec = es_section(text, heading)
        for grid in W.all_tables(sec)[:1]:
            labels = label_index(grid[0])
            i_name = find(labels, "jugador", "nombre", "futbolista")
            i_team = find(labels, "club", "equipo")
            i_goals = find(labels, "goles", "total", "g")
            if i_name is None or i_goals is None:
                continue
            out = []
            for r in grid[1:]:
                if len(r) <= max(i_name, i_goals):
                    continue
                name = W.person(r[i_name]["text"])
                team_text = r[i_team]["text"] if i_team is not None else r[i_name]["text"]
                teams = {t for t in (pair.a, pair.b) if any(n in fold(W.plain(team_text)) for n in ALIASES[t])}
                team = "both" if len(teams) == 2 else next(iter(teams), None)
                goals = W.number(r[i_goals]["text"])
                if name and team and goals:
                    out.append({"name": name, "team": team, "goals": goals})
            if out:
                return sorted(out, key=lambda o: -o["goals"])
    return []


def link_ties(data: dict, ties: list[dict]) -> list[dict]:
    """Point each leg of Wikipedia's ties at its match; ties keep their own legs when a match isn't in the list."""
    taken: set[int] = set()
    for t in ties:
        ns = []
        for leg in t.pop("_legs"):
            cands = [m for m in data["matches"] if leg.get("date") and m["date"] == leg["date"] and m["home"] == leg["home"]]
            cands = cands or [m for m in data["matches"] if m["home"] == leg["home"] and (m["hs"], m["as"]) == (leg["hs"], leg["as"])
                              and leg["_year"] and abs(int(m["date"][:4]) - leg["_year"]) <= 1 and m["n"] not in taken]
            if ar_comp(t["comp"])[1] != "league" and t["comp"] != "Copa de la Liga Profesional":
                cands = [m for m in cands if m["stage"] != "league"]  # a cup tie is never a league match
            # The same competition first, then cup matches, then the closest year.
            cands.sort(key=lambda m: (m["comp"] != t["comp"], m["stage"] == "league" and t["comp"] not in ("Primera División", "Segunda División"),
                                      abs(int(m["date"][:4]) - (leg["_year"] or 0)), m["n"]))
            if cands:
                ns.append(cands[0]["n"])
                taken.add(cands[0]["n"])
        if len(ns) == len(t["legs"]):
            for leg, n in zip(t["legs"], ns):
                leg["n"] = n
            t["legs"].sort(key=lambda leg: leg["n"])
        t["matches"] = sorted(ns)
    dates = {m["n"]: m["date"] for m in data["matches"]}
    ties.sort(key=lambda t: dates[t["matches"][0]] if t["matches"] else t["season"])
    return ties


def big_five(key: str, a: str, b: str):
    """A builder for one of the big-five rivalries."""
    cfg = BIG_FIVE[key]

    def builder(refresh: bool) -> dict:
        pair = Pair(a, ALIASES[a], b, ALIASES[b])
        text = page(cfg["es"], refresh, "es")
        totals = es_totals(text, r"Enfrentamientos oficiales", pair)
        friendly_totals = es_totals(text, r"Enfrentamientos amistosos", pair)
        recent = es_last_matches(text, pair)
        ties = es_ties(text, pair)
        rsssf, friendlies = rsssf_matches(cfg["rsssf"], cfg["codes"], refresh) if cfg.get("rsssf") else ([], [])
        url = "https://es.wikipedia.org/wiki/" + cfg["es"].replace(" ", "_")
        source = {"label": f"Spanish Wikipedia, {cfg['es']}", "url": url}
        notes = ["Matches decided on penalties count as draws; the shoot-out decides only who went through."]
        data = {"source": source, "notes": notes, "friendlies": friendlies, "pair": pair}
        if friendly_totals and not friendlies:
            data["friendlySummary"] = friendly_totals["total"]
        scorers = es_leaders(text, pair)
        if scorers:
            data["scorers"] = scorers
        if cfg["list"] is None:
            for t in ties:
                t.pop("_legs")
                t["matches"] = []
            data.update({"mode": "summary", "summary": totals, "recent": recent, "ties": ties})
            notes.insert(0, "Wikipedia publishes this rivalry's totals by competition but not every match, so there is no "
                            "match-by-match history; the latest matches and the knockout ties are listed.")
            return data
        if cfg["list"] == "es":
            matches = es_full_list(text, pair)
            if rsssf:
                n = match_dates(matches, rsssf)
                source["label"] += "; dates from RSSSF"
                notes.insert(0, f"Matches and scorers come from Spanish Wikipedia; their dates from RSSSF's list "
                                f"(found for {n} of {len(matches)}).")
            match_dates(matches, recent)
            match_dates(matches, [x for t in ties for x in t["_legs"] if x.get("date")])
            approx = [m for m in matches if not m.get("date")]
            approx_dates(matches)
            if approx:
                notes.append(f"No source gives the exact date of {len(approx)} matches; they are placed in their season "
                             "by matchday and marked ≈ with the year only.")
        else:
            matches = rsssf
            last = max(m["date"] for m in matches)
            newer = [m for m in recent if m["date"] > last]
            matches += newer
            # RSSSF leaves out the second-division meetings of the 1910s; Wikipedia's list has them.
            second = [m for m in es_full_list(text, pair) if m["comp"] == "Segunda División"]
            if second and not any(m["comp"] == "Segunda División" for m in matches):
                approx_dates(second)
                matches += second
            source["label"] = f"RSSSF, {data_title(cfg)}; Spanish Wikipedia, {cfg['es']}"
            source["url"] = f"https://www.rsssf.org/{cfg['rsssf']}.html"
            notes.insert(0, f"Matches come from RSSSF's list (updated to {last[:4]})"
                            + (f", with the {len(newer)} played since from Spanish Wikipedia" if newer else "") + "; knockout ties and totals from Wikipedia.")
        if totals:
            data["published"] = totals["total"]
        data.update({"matches": matches, "_ties": ties})
        return data

    builder.ties = True
    return builder


def data_title(cfg: dict) -> str:
    names = {RIVER: "River Plate", BOCA: "Boca Juniors", INDEPENDIENTE: "Independiente", RACING: "Racing Club", SAN_LORENZO: "San Lorenzo"}
    a, b = cfg["codes"].values()
    return f"{names[a]} vs {names[b]}"


# ---------------------------------------------------------------- The provincial and southern derbies

# Spanish Wikipedia lists every match of these four, section by section: the local league (Rosario, Santa Fe,
# Córdoba) and its cups, the AFA's championships and cups, CONMEBOL cups and friendlies. Each section's own
# "Victorias de …" summary is checked against the rows read from it.

NEWELLS, CENTRAL = "newell-s-old-boys", "rosario-central"
LANUS, BANFIELD = "lanus", "banfield"
COLON, UNION = "colon", "union"
TALLERES, BELGRANO = "talleres-c", "belgrano"
DERBY_ALIASES = {NEWELLS: ("newell",), CENTRAL: ("central",), LANUS: ("lanus",), BANFIELD: ("banfield",),
                 COLON: ("colon",), UNION: ("union",), TALLERES: ("talleres",), BELGRANO: ("belgrano",)}
# (heading, stage): "local" for the city leagues and their cups, None to classify each row by its competition.
DERBIES = {
    "newells-central": {"es": "Clásico rosarino", "sections": [
        (r"==== Campeonatos locales ====", "local"), (r"==== Copas locales ====", "local"),
        (r"=== Partidos oficiales por torneos de la Federación Santafesina de Fútbol ===", "local"),
        (r"==== Campeonatos nacionales ====", None), (r"==== Copas nacionales ====", "cup"),
        (r"=== Partidos oficiales por torneos de la Confederación Sudamericana de Fútbol ===", "intl")],
        "friendlies": r"=== Amistosos ===", "scorers": r"=== Máximos goleadores ===",
        "apps": r"=== Mayor cantidad de partidos disputados ==="},
    "lanus-banfield": {"es": "Clásico del Sur (Argentina)", "sections": [
        (r"==== Amateurismo ====", None), (r"==== Profesionalismo ====", None)],
        "scorers": r"== Goleadores =="},
    "colon-union": {"es": "Clásico santafesino", "sections": [
        (r"=== Liga Santafesina \(1913-1939\) ===[\s\S]*?==== Campeonatos de Primera División ====", "local"),
        (r"==== Torneos de Copa ====", "local"),
        (r"==== Campeonatos de Segunda División ====", "league"), (r"==== Torneos de Copa de Segunda División ====", "cup"),
        (r"=== Asociación del Fútbol Argentino \(1948-\) ===[\s\S]*?==== Campeonatos de Primera División ====", "league"),
        (r"==== Torneos de Copa de Primera División ====", "cup")],
        "friendlies": r"=== Amistosos", "scorers": r"==== Tabla histórica de goleadores ====",
        "apps": r"==== Jugadores con mayor cantidad"},
    "talleres-belgrano": {"es": "Clásico cordobés", "sections": [
        (r"===== Campeonatos de Primera División =====", "local"), (r"===== Torneos Extras =====", "local"),
        (r"==== Asociación del Fútbol Argentino \(1974-act\.\) ====", None)],
        "scorers": r"==== Máximos goleadores \(oficiales\) ====", "apps": r"==== Más presencias ===="},
}
LOCAL_NAMES = {"newells-central": "Liga Rosarina", "colon-union": "Liga Santafesina", "talleres-belgrano": "Liga Cordobesa"}


def section_text(text: str, heading: str) -> str:
    m = re.search(heading, text)
    if not m:
        raise LookupError(f"section not found: {heading}")
    rest = text[m.end():]
    end = re.search(r"\n=+\s*[^=\n]+?\s*=+\s*\n", rest)
    return rest[:end.start()] if end else rest


def derby_stage(comp: str) -> str:
    c = fold(comp)
    if re.search(r"libertadores|sudamericana|conmebol|mercosur|supercopa sud", c):
        return "intl"
    if re.search(r"^copa|torneo de honor|trofeo", c) and not re.search(r"copa campeonato|copa de la liga", c):
        return "cup"
    return "league"


def derby_rows(text: str, pair: Pair, stage: str | None, friendly: bool = False) -> tuple[list[dict], dict, int]:
    """Rows of every table in a section, read by their headers; also the section's own summary and the rows
    without a result (walkovers, missing data)."""
    out, summary, skipped = [], {}, 0
    for grid in W.all_tables("\n" + text):
        if grid and W.plain(grid[0][0]["text"]).lower().startswith("victorias"):
            for r in grid:
                lab, val = fold(W.plain(r[0]["text"])), W.number(r[1]["text"]) if len(r) > 1 else None
                key = "d" if lab.startswith("empate") else pair.team(lab)
                if key and val is not None:
                    summary[key] = val
            continue
        head = grid[0]
        labels = [re.sub(r"^[!|\s]+", "", W.plain(c["text"])).strip().lower() for c in head]
        if not any(lab.startswith("local") for lab in labels):
            continue
        idx = lambda *names: next((i for i, lab in enumerate(labels) if lab.startswith(names)), None)  # noqa: E731
        i_home, i_away, i_score = idx("local"), idx("visitante"), idx("resultado")
        i_comp = idx("competencia", "torneo", "competición")
        i_round = idx("instancia", "ronda")
        # The date is the first column unless that is a running number; another "Fecha" is the matchday.
        fechas = [i for i, lab in enumerate(labels) if lab.startswith("fecha")]
        numbered = labels[0] in ("#", "n.º", "nº", "no.", "n°")
        i_date = fechas[0] if numbered and fechas else 0
        matchday = [i for i in fechas if i != i_date]
        if i_round is None and matchday:
            i_round = matchday[0]
        i_leg = i_round + 1 if i_round is not None and i_round + 1 < len(labels) and labels[i_round + 1] == labels[i_round] else None
        i_venue, i_gh, i_ga = idx("estadio"), idx("goles (l)"), idx("goles (v)")
        for r in grid[1:]:
            if len(r) <= max(i_home, i_away, i_score):
                continue
            d = parse_date(r[i_date]["text"])
            home, away = pair.team(r[i_home]["text"]), pair.team(r[i_away]["text"])
            sc = score_of(r[i_score]["text"])
            if not home or not away or home == away:
                continue
            # A walkover: "GP–PP" (the home side won the points) or "PP–GP"; "PP–PP" means both lost them.
            wo = re.search(r"\b([GP]P)\s*[–-]\s*([GP]P)\b", W.plain(r[i_score]["text"]))
            if wo and wo.group(1) != wo.group(2):
                sc = (1, 0) if wo.group(1) == "GP" else (0, 1)
            if not d or not sc:
                skipped += 1
                continue
            comp = W.plain(r[i_comp]["text"]) if i_comp is not None else ""
            comp = re.sub(r"\s*\(\s*\)|\s*\d{4}(?:[-–/]\d{2,4})?\s*$", "", comp).strip() or comp
            comp = re.sub(r"\s*\d{4}(?:[-–/]\d{2,4})?\s*$", "", comp).strip() or comp
            rnd = W.plain(r[i_round]["text"]) if i_round is not None else ""
            leg = W.plain(r[i_leg]["text"]) if i_leg is not None and r[i_leg] is not r[i_round] else ""
            st = "friendly" if friendly else stage or derby_stage(comp)
            m = {"date": d, "comp": comp or "Friendly", "stage": st, "home": home, "away": away, "hs": sc[0], "as": sc[1],
                 "goalsHome": goals_text(r[i_gh]["text"]) if i_gh is not None else "",
                 "goalsAway": goals_text(r[i_ga]["text"]) if i_ga is not None else ""}
            if i_venue is not None:
                m["venue"] = W.plain(r[i_venue]["text"])
            low = fold(rnd).replace("8avos", "octavos").replace("4tos", "cuartos")
            matchday = re.search(r"fecha|rueda|^f\.\s*\d|^\d+\.?(?:ª|a)?$", low)
            if st in ("cup", "intl", "local") and not matchday and rnd:
                m["round"] = ES_ROUNDS.get(low, next((v for k, v in ES_ROUNDS.items() if low.startswith(k)), rnd))
                if "ida" == fold(leg) or low.endswith(" ida"):
                    m["leg"] = "first leg"
                elif "vuelta" == fold(leg) or low.endswith(" vuelta"):
                    m["leg"] = "second leg"
                elif "desempate" in fold(leg) or "desempate" in low:
                    m["leg"] = "replay"
            pens = shootout(r[i_score]["text"])
            p_first = re.search(r"\(\s*p\.?\s*(\d+)\s*[-–]\s*(\d+)\s*\)", W.plain(r[i_score]["text"]))  # "0–0 (p. 3-5)"
            if p_first:
                pens = (int(p_first.group(1)), int(p_first.group(2)))
            if pens:
                m["pens"] = list(pens)
            if wo and wo.group(1) != wo.group(2):
                m["decided"] = "Walkover: the points were awarded, counted as a 1–0 win"
            out.append(m)
    return out, summary, skipped


def derby_leaders(text: str, heading: str, key: str, pair: Pair) -> list[dict]:
    """#, Jugador, Equipo, then per-competition columns and a Total: a triple of Total columns is
    (games, goals, average); a single one is the value. Smaller tables give it as Goles, Cantidad or Partidos."""
    try:
        grid = W.parse_table(W.find_table(text, heading))
    except LookupError:
        return []
    labels = [W.plain(c["text"]).strip().lower() for c in grid[0]]
    i_name = next((i for i, lab in enumerate(labels) if lab.startswith("jugador")), None)
    i_team = next((i for i, lab in enumerate(labels) if lab.startswith("equipo")), None)
    totals = [i for i, lab in enumerate(labels) if lab.startswith("total")]
    if len(totals) >= 3:
        i_val = totals[1] if key == "goals" else totals[0]
    elif totals:
        i_val = totals[0]
    else:
        i_val = next((i for i, lab in enumerate(labels) if lab.startswith(("goles", "cantidad", "partidos"))), None)
    if None in (i_name, i_team, i_val):
        return []
    out = []
    for r in grid[1:]:
        if len(r) <= max(i_name, i_team, i_val):
            continue
        name = W.person(re.sub(r"\{\{\s*(?:bandera|flagicon|band)[^{}]*\}\}|\[\[(?:Archivo|File|Imagen):[^\]]*\]\]", "", r[i_name]["text"]))
        raw = fold(W.plain(r[i_team]["text"]) + " " + r[i_team]["text"])
        teams = {cid for cid, names in pair.names if any(n in raw for n in names)}
        val = W.number(r[i_val]["text"])
        if name and teams and val:
            out.append({"name": name.replace("''", "").strip(), "team": "both" if len(teams) == 2 else teams.pop(), key: val})
    return sorted(out, key=lambda o: -o[key])


def derby(key: str, a: str, b: str):
    cfg = DERBIES[key]

    def builder(refresh: bool) -> dict:
        pair = Pair(a, DERBY_ALIASES[a], b, DERBY_ALIASES[b])
        text = page(cfg["es"], refresh, "es")
        matches, missing, since = [], 0, []
        for heading, stage in cfg["sections"]:
            rows, summary, skipped = derby_rows(section_text(text, heading), pair, stage)
            missing += skipped
            since += rows
            # A section's summary covers every section since the previous summary.
            if summary:
                got = record({"teams": [{"id": a}, {"id": b}], "matches": since})
                if (summary.get(a), summary.get("d"), summary.get(b)) != (got["a"], got["d"], got["b"]):
                    print(f"note: {cfg['es']} up to {heading[:40]}: summary {summary}, rows {got['a']}-{got['d']}-{got['b']}",
                          file=sys.stderr)
                since = []
            if stage == "local":
                for m in rows:
                    m["comp"] = m["comp"] if re.search(r"liga|copa|torneo", m["comp"], re.I) else f"{LOCAL_NAMES[key]}: {m['comp']}"
            matches += rows
        for m in matches:
            if m["stage"] == "league":
                m["comp"] = "Segunda División" if re.search(r"segunda|intermedia|ascenso|nacional b|primera b", m["comp"], re.I) else "Primera División"
            if m["stage"] == "local" and (not re.search(r"copa|torneo|trofeo", m["comp"], re.I) or re.match(r"copa campeonato", m["comp"], re.I)):
                m["comp"] = LOCAL_NAMES[key]
        friendlies = []
        if cfg.get("friendlies"):
            friendlies, _, _ = derby_rows(section_text(text, cfg["friendlies"]), pair, None, friendly=True)
        url = "https://es.wikipedia.org/wiki/" + cfg["es"].replace(" ", "_")
        notes = ["Matches decided on penalties count as draws; the shoot-out decides only who went through."]
        if missing:
            notes.append(f"{missing} official matches the source lists without a date or a result (walkovers, awarded points or "
                         "missing data) are left out.")
        if key in LOCAL_NAMES:
            notes.append(f"Official matches include the {LOCAL_NAMES[key]}'s championships and cups, as the source counts them.")
        data = {"matches": matches, "friendlies": friendlies, "source": {"label": f"Spanish Wikipedia, {cfg['es']}", "url": url},
                "notes": notes}
        if cfg.get("scorers"):
            data["scorers"] = derby_leaders(text, cfg["scorers"], "goals", pair)
        if cfg.get("apps"):
            data["appearances"] = derby_leaders(text, cfg["apps"], "apps", pair)
        return data

    return builder
