"""The Uruguayan Clásico: Peñarol vs Nacional (RSSSF's full list, with Spanish Wikipedia for the latest matches and the
top scorers)."""

from __future__ import annotations

import html
import re

from rivalries_common import RAW, W, Pair, fetch_url, page, parse_date, score_of, shootout

PENAROL, NACIONAL = "penarol", "nacional"
PAIR = Pair(PENAROL, ("penarol", "curcc"), NACIONAL, ("nacional",))
RSSSF_URL = "https://www.rsssf.org/tablesu/uru-derbies.html"

# RSSSF's official competitions, as it totals them: the league and the other Uruguayan tournaments, the CONMEBOL cups
# and the cups played with Argentina's clubs. Everything else (named cups, pre-season tournaments, the 1968 and 2005
# special championships) is with the friendlies, as in RSSSF's totals.
COMPS = [
    (r"^Uruguayan Championship", "Uruguayan Primera División", "league"),
    (r"^Liguilla", "Liguilla Pre-Libertadores", "cup"),
    (r"^Uruguayan Supercopa", "Supercopa Uruguaya", "super"),
    (r"^Liga Mayor", "Liga Mayor", "cup"),
    (r"^Interzonal", "Torneo Competencia", "cup"),
    (r"^Copa Libertadores", "Copa Libertadores", "intl"),
    (r"^Super Copa", "Supercopa Sudamericana", "intl"),
    (r"^Copa Mercosur", "Copa Mercosur", "intl"),
    (r"^Copa Sudamericana", "Copa Sudamericana", "intl"),
    (r"^Nocturno Rioplatense", "Copa Nocturna Rioplatense", "cup"),
]
AET = set("dhiqsv")  # RSSSF's note letters for extra time
ABANDONED = {"k": "Suspended after 75 minutes; the last 15 were played on 24 December",
             "l": "Abandoned after 78 minutes; the result stood",
             "m": "Abandoned after 70 minutes; the rest was played on 25 August",
             "n": "Nacional left the field at half-time; the result stood",
             "p": "Abandoned after 55 minutes, Nacional down to six players; the result stood",
             "r": "Abandoned after 80 minutes following 20 sendings off; the result stood",
             "t": "Stopped for 13 minutes after bottles were thrown at Nacional's goalkeeper",
             "v": "Abandoned in the 111th minute after riots; the result stood",
             "z": "Abandoned after 81 minutes because of the weather; the result stood"}
ROW = re.compile(r"\s*(\d+)\s+(\d\d/\d\d/\d{4})\s+(\S.{13})(.{25})(.{6})(.*)$")


def classify(comp: str, year: int) -> tuple[str, str]:
    """(name, stage) of an official competition, or ("", "friendly")."""
    if comp.startswith("Competition Cup"):
        return ("Copa de Competencia", "cup") if year < 1920 else ("Torneo Competencia", "cup")
    if comp.startswith("Honour Cup"):
        return ("Copa de Honor", "cup") if year < 1930 else ("Torneo de Honor", "cup")
    for pat, name, stage in COMPS:
        if re.search(pat, comp):
            return name, stage
    return "", "friendly"


def round_of(phase: str) -> tuple[str, str]:
    """(round, leg) from RSSSF's note in brackets: "Final", "Clausura final", "replay", "3rd place match"..."""
    p = phase.lower()
    if "replay" in p:
        return "Play-off", "replay"
    if "place match" in p or "preliminary" in p:
        return "Play-off", ""
    if "semifinal" in p:
        return "Semi-finals", ""
    if "final" in p:
        for stage in ("Clausura", "Intermedio"):
            if stage.lower() in p:
                return f"{stage} final", ""
        return "Final", ""
    return "", ""


def penalties(text: str) -> dict[str, tuple[int, int, str]]:
    """RSSSF's shoot-out notes ("o" and "q"): date -> (winner's, loser's, winner)."""
    out = {}
    for d, who, w, l in re.findall(r"(\d\d/\d\d/\d{4}):\s+(Peñarol|Nacional) won (\d+)-(\d+)", text):
        out[parse_date(d)] = (int(w), int(l), PENAROL if who == "Peñarol" else NACIONAL)
    return out


def rsssf_matches(refresh: bool) -> tuple[list[dict], list[dict], dict]:
    raw = fetch_url(RSSSF_URL, RAW / "rsssf" / "uru-derbies.html", refresh, encoding="latin-1")
    text = html.unescape(re.sub(r"<[^>]+>", "", raw))
    pens = penalties(text)
    official, friendlies = [], []
    for line in text.splitlines():
        m = ROW.match(line)
        if not m:
            continue
        num, d, venue, game, score, rest = (g.strip() for g in m.groups())
        note = ""
        nm = re.match(r"^([a-z])\s+(.*)$", rest) or re.match(r"^([a-z])$", rest)
        if nm:
            note, rest = nm.group(1), (nm.group(2) if nm.lastindex > 1 else "")
        sm = re.match(r"^(.*?)\s+([a-z])$", score)
        if sm and not re.fullmatch(r"a/wo|wo:a", score):
            score, note = sm.group(1), sm.group(2) or note
        date = parse_date(d)
        home_txt, away_txt = re.split(r"-(?=[A-ZN])", game, maxsplit=1)
        home, away = PAIR.team(home_txt), PAIR.team(away_txt)
        if note == "a" or "cancelled" in rest:
            continue  # results annulled; RSSSF leaves them out of its totals
        comp_raw = re.sub(r"\s+", " ", rest).strip()
        phase = re.search(r"\((.*)\)", comp_raw)
        phase = phase.group(1) if phase else ""
        base = re.sub(r"\s*\(.*", "", comp_raw)
        year = int(date[:4])
        comp, stage = classify(base, year)
        x = {"date": date, "home": home, "away": away, "_order": int(num)}
        if score in ("a/wo", "wo:a"):
            winner_home = score == "wo:a"
            x.update({"hs": 1 if winner_home else 0, "as": 0 if winner_home else 1,
                      "decided": f"Walkover: awarded to {'Peñarol' if (home if winner_home else away) == PENAROL else 'Nacional'}"})
        else:
            sc = score_of(score)
            x.update({"hs": sc[0], "as": sc[1]})
        if note in AET:
            x["aet"] = True
        if note in ABANDONED:
            x["decided"] = ABANDONED[note]
        if date in pens and x["hs"] == x["as"]:
            w, l, who = pens[date]
            x["pens"] = [w, l] if who == home else [l, w]
        if venue != "Montevideo":
            x["venue"], x["neutral"] = re.sub(r",\s*(\w+)$", lambda c: ", " + {"Arg": "Argentina", "Esp": "Spain", "USA": "USA"}.get(c.group(1), c.group(1)), venue), True
        if stage == "friendly":
            x.update({"comp": base or "Friendly", "stage": "friendly", "season": str(year)})
            if phase and not re.search(r"teams|superderbies", phase, re.I):
                x["round"] = phase
            friendlies.append(x)
            continue
        season = re.search(r"\b(1[89]\d\d|20\d\d)\b", phase)
        rnd, leg = round_of(phase)
        if comp == "Copa Sudamericana":
            rnd = "Knockout round"
        x.update({"comp": comp, "stage": stage, "season": season.group(1) if season else str(year), "round": rnd, "leg": leg})
        if comp == "Uruguayan Primera División" and not rnd and phase and not season and not re.search(r"cancel", phase):
            x["phase"] = phase
        official.append(x)
    totals = re.search(r"\nTotal\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", text)
    return official, friendlies, {"text": text, "total": totals}


def wiki_latest(es: str) -> list[dict]:
    """Spanish Wikipedia's ten latest clásicos: Fecha, Torneo, Estadio, home, score, away."""
    out = []
    for r in W.parse_table(W.find_table(es, r"=== Últimos 10 partidos clásicos ==="))[1:]:
        if len(r) < 6:
            continue
        d, sc = parse_date(r[0]["text"]), score_of(r[4]["text"])
        home, away = PAIR.team(r[3]["text"]), PAIR.team(r[5]["text"])
        if not d or not sc or not home or not away:
            continue
        tourn = W.plain(r[1]["text"])
        if re.search(r"apertura|clausura|intermedio|liga auf|primera división", tourn, re.I):
            comp, stage = "Uruguayan Primera División", "league"
        elif re.search(r"supercopa", tourn, re.I):
            comp, stage = "Supercopa Uruguaya", "super"
        else:
            comp, stage = tourn, "friendly"
        x = {"date": d, "home": home, "away": away, "hs": sc[0], "as": sc[1], "comp": comp, "stage": stage, "season": d[:4]}
        p = shootout(r[4]["text"].replace(":", "–"))
        if p:
            x["pens"] = list(p)
        out.append(x)
    return out


def leaders(es: str) -> list[dict]:
    """Spanish Wikipedia's all-time scorers: #, Jugador, Equipo ("CURCC (9) Nacional (9)"), Goles."""
    out = []
    for r in W.parse_table(W.find_table(es, r"=== Tabla histórica de goleadores"))[1:]:
        if len(r) < 4:
            continue
        cells = r[-4:] if len(r) >= 5 else r
        name, club, goals = W.person(cells[0]["text"]), W.plain(cells[1]["text"]).lower(), W.number(cells[2]["text"])
        teams = {t for t, keys in ((PENAROL, ("peñarol", "curcc")), (NACIONAL, ("nacional",))) if any(k in club for k in keys)}
        if name and teams and goals:
            out.append({"name": name, "team": "both" if len(teams) == 2 else teams.pop(), "goals": goals})
    return sorted(out, key=lambda o: -o["goals"])


def build_clasico(refresh: bool) -> dict:
    official, friendlies, extra = rsssf_matches(refresh)
    es = page("Clásico del fútbol uruguayo", refresh, "es")
    last = max(m["date"] for m in official + friendlies)
    for m in wiki_latest(es):
        if m["date"] > last:
            (friendlies if m["stage"] == "friendly" else official).append(m)
    for m in official:
        m.pop("phase", None)
    return {
        "matches": official, "friendlies": friendlies,
        "scorers": leaders(es), "appearances": [],
        "awayGoals": True,
        "source": {"label": "RSSSF, Uruguayan Derby: Peñarol vs. Nacional (Martín Tabeira)", "url": RSSSF_URL,
                   "extra": [{"what": "the latest matches and the top scorers", "label": "Spanish Wikipedia, Clásico del fútbol uruguayo",
                              "url": "https://es.wikipedia.org/wiki/Cl%C3%A1sico_del_f%C3%BAtbol_uruguayo"}]},
        "notes": [
            "Peñarol's matches as CURCC (1900–1913) are included, as RSSSF counts them. Annulled matches are left out; walkovers count as a 1–0 win.",
            "Official matches are the Uruguayan league and tournaments, the CONMEBOL cups and the cups played with Argentina's clubs, as RSSSF totals them. "
            "Named cups and pre-season tournaments, such as the Copa Bimbo and the Serie Río de la Plata, are under friendlies.",
            "Scorers in each match are not listed by the source; the all-time scorers come from Spanish Wikipedia and include goals in annulled matches.",
        ],
        "friendliesNote": "Many of them were played for a trophy.",
    }
