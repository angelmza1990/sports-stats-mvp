"""Build the coaches and players datasets shown on the football competition pages: the coaches who won (and,
in the Champions League and Copa Libertadores, reached) the most finals or titles, and the players who
won the most titles.

Each competition writes football/<page>/data/people.json. Every coach's title is matched to the champion
of that season on the page's own dataset (same year and club), so the counts line up with the page.

Sources (Wikipedia, CC BY-SA 4.0):
  * Coaches: the lists of winning managers of the Champions League, Serie A, La Liga, the English
    championship, Ligue 1 and the Brasileirão (English Wikipedia); the Copa Libertadores finals with both
    coaches and the Argentine champions' coaches (Spanish Wikipedia). Champions League runners-up's
    coaches come from each final's line-ups (kept in data/raw/football/final_managers.json).
  * Players: the Champions League records page, the lists of Copa Libertadores and Premier League
    winning players, the players with most Serie A titles (Italian Wikipedia), the Brasileirão's most
    crowned players (Portuguese Wikipedia) and the Argentine players with most titles (Spanish Wikipedia).

Usage:
    python3 scripts/build_football_people.py            # cached pages
    python3 scripts/build_football_people.py --refresh  # re-download them
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wikitables as W  # noqa: E402
from build_football import COUNTRIES, ClubIndex  # noqa: E402
from build_tennis_ages import BY_NAME  # noqa: E402
from olympic_events import nation_info  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "raw" / "wikipedia" / "people"
FINAL_MANAGERS = ROOT / "data" / "raw" / "football" / "final_managers.json"
USER_AGENT = "sports-stats-mvp/1.0 (https://github.com/angelmza1990/sports-stats-mvp)"

COMPS = {
    "champions-league": {
        "name": "Champions League", "kind": "cup", "country": None,
        "coaches": ("en", "List of European Cup and UEFA Champions League winning managers"),
        "runnersUp": "articles",
        "players": ("en", "European Cup and UEFA Champions League records and statistics", r"==== Most wins ====", "table"),
        "expect": {"coach": ("Carlo Ancelotti", 5), "finals": ("Carlo Ancelotti", 6), "player": ("Paco Gento", 6)},
    },
    "copa-libertadores": {
        "name": "Copa Libertadores", "kind": "cup", "country": None,
        "coaches": ("es", "Anexo:Entrenadores campeones de la Copa Libertadores"),
        "runnersUp": "table",
        "players": ("en", "List of Copa Libertadores winning players", None, "table"),
        "expect": {"coach": ("Carlos Bianchi", 4)},
    },
    "premier-league": {
        "name": "English champions", "kind": "league", "country": "ENG",
        "coaches": ("en", "List of English football championship–winning managers"),
        "players": ("en", "List of Premier League winning players", r"==List of Premier League winning players==", "table"),
        "playersNote": "Premier League era only (since 1992–93).",
        "expect": {"coach": ("Alex Ferguson", 13), "player": ("Ryan Giggs", 13)},
    },
    "serie-a": {
        "name": "Serie A", "kind": "league", "country": "ITA",
        "coaches": ("en", "List of Serie A winning managers"),
        "players": ("it", "Statistiche della Serie A", r"==== Classifica per scudetti vinti ====", "list"),
        "playersNote": "Single-group Serie A only (since 1929–30).",
        "expect": {"coach": ("Giovanni Trapattoni", 7), "player": ("Gianluigi Buffon", 10)},
    },
    "la-liga": {
        "name": "La Liga", "kind": "league", "country": "ESP",
        "coaches": ("en", "List of La Liga winning managers"),
        "expect": {"coach": ("Miguel Muñoz", 9)},
    },
    "ligue-1": {
        "name": "Ligue 1", "kind": "league", "country": "FRA",
        "coaches": ("en", "List of Ligue 1 winning managers"),
        "expect": {"coach": ("Albert Batteux", 8)},
    },
    "brasileirao": {
        "name": "Brasileirão", "kind": "league", "country": "BRA",
        "coaches": ("en", "List of Campeonato Brasileiro Série A winning managers"),
        "players": ("pt", "Resultados e estatísticas do Campeonato Brasileiro de Futebol", r"=== Jogadores mais vezes campeões ===", "table"),
        "expect": {"coach": ("Vanderlei Luxemburgo", 5), "player": ("Pelé", 6)},
    },
    "argentine-primera": {
        "name": "Argentine Primera División", "kind": "league", "country": "ARG",
        "coaches": ("es", "Anexo:Entrenadores campeones de la Primera División de Argentina"),
        "players": ("es", "Anexo:Futbolistas con más títulos de la Primera División de Argentina", r"== Lista ==", "table"),
        "playersNote": "Professional era only (since 1931).",
        "coachesNote": "Professional era only (since 1931).",
        "expect": {"coach": ("Ramón Ángel Díaz", 7), "player": ("Leonardo Astrada", 10)},
    },
}

FLAG_NAMES = {**BY_NAME, "ENGLAND": "ENG", "SCOTLAND": "SCO", "WALES": "WAL", "NORTHERN IRELAND": "NIR", "SPAIN": "ESP",
              "ARGENTINA": "ARG", "URUGUAY": "URU", "BRAZIL": "BRA", "ITALY": "ITA", "FRANCE": "FRA", "GERMANY": "GER",
              "WEST GERMANY": "FRG", "HUNGARY": "HUN", "NETHERLANDS": "NED", "PORTUGAL": "POR", "AUSTRIA": "AUT",
              "PARAGUAY": "PAR", "CHILE": "CHI", "COLOMBIA": "COL", "SERBIA": "SRB", "YUGOSLAVIA": "YUG", "ROMANIA": "ROU",
              "CZECHOSLOVAKIA": "TCH", "BELGIUM": "BEL", "SWITZERLAND": "SUI", "IRELAND": "IRL", "SOVIET UNION": "URS",
              "PERU": "PER", "ECUADOR": "ECU", "MEXICO": "MEX", "SWEDEN": "SWE", "DENMARK": "DEN", "NORWAY": "NOR",
              "POLAND": "POL", "CROATIA": "CRO", "UNITED STATES": "USA", "BOLIVIA": "BOL", "VENEZUELA": "VEN"}
CODE_FIX = {"CSK": "TCH", "DDR": "GDR", "DEU": "GER", "NLD": "NED", "CHE": "SUI", "SER": "SRB", "URY": "URU", "PRY": "PAR", "CHL": "CHI", "PRT": "POR",
            "HRV": "CRO", "ROM": "ROU", "SVN": "SLO", "DNK": "DEN", "GRC": "GRE", "BGR": "BUL"}


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def page(lang: str, title: str, refresh: bool) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()).strip("-")
    return W.fetch_raw(title, CACHE / f"{lang}-{slug}.wiki", refresh, pause=1.5, lang=lang)


def key(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", plain)


def nation(text: str) -> str | None:
    player = re.search(r"\{\{\s*player\s*\|[^|{}]*\|\s*([A-Z]{3})\s*\|", text)  # {{player||AUS|[[Name]]}}
    if player:
        return CODE_FIX.get(player.group(1), player.group(1))
    bare = re.search(r"\{\{\s*([A-Z]{3})\s*(?:\|[^{}]*)?\}\}", text)  # {{URU}}
    if bare and not re.search(r"(?i)\{\{\s*(?:fba|fb|flagu|flagcountry|flagicon|flag|bandera|bandiera)\s*\|", text):
        return CODE_FIX.get(bare.group(1), bare.group(1))
    m = re.search(r"\{\{\s*(?:fba|fb|flagu|flagcountry|flagicon|flag|bandera|bandiera|flagathlete\s*\|[^|]*)\s*\|\s*([^|}]+)", text, re.I)
    if not m:
        return None
    raw = m.group(1).strip().upper()
    raw = CODE_FIX.get(raw, raw)
    if raw in ("", None):
        return None
    if raw in FLAG_NAMES:
        return FLAG_NAMES[raw]
    return raw if re.fullmatch(r"[A-Z]{3}", raw) else None


def strip(text: str) -> str:
    text = W.strip_refs(text)
    text = re.sub(r"<span[^>]*display:\s*none[^>]*>.*?</span>", "", text, flags=re.I)  # hidden sort keys
    text = re.sub(r"\{\{\s*nowrap\s*\|([^{}]*)\}\}", r"\1", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "; ", text, flags=re.I)
    text = re.sub(r"\{\{\s*(?:small|efn|sfn|refn|nota)\b[^{}]*\}\}", "", text, flags=re.I)
    text = re.sub(r"\[\[(?:File|Archivo|Image|Imagen):[^\]]*\]\]", "", text, flags=re.I)
    return text


def people_in(cell: str) -> list[tuple[str, str]]:
    """The people named in a cell, as (key, display name): sortname templates, links or plain text, possibly
    several (co-managers separated by "and", "/" or line breaks)."""
    text = strip(cell)
    text = re.sub(r"\{\{\s*(?:fba|fb|flagu|flagcountry|flagicon|flag|bandera|bandiera)\s*\|[^{}]*\}\}", "", text, flags=re.I)
    out = []
    for part in re.split(r"<br\s*/?>|;\s*|\s+/\s+|\s+and\s+|\s+y\s+|\s+&\s+", text):
        m = re.search(r"\{\{\s*sortname\s*\|([^{}]*)\}\}", part, re.I)
        if m:
            args = [a.strip() for a in m.group(1).split("|")]
            pos = [a for a in args if "=" not in a]  # named arguments (dab=, nolink=) aren't names
            name = " ".join(pos[:2]).strip()
            dab = next((a.split("=", 1)[1].strip() for a in args if a.startswith("dab=")), None)
            target = pos[2] if len(pos) > 2 and pos[2] else f"{name} ({dab})" if dab else name
            out.append((target, name))
            continue
        link = [l for l in W.links(part) if not re.match(r"(?i)(file|archivo|image|imagen):", l[0])]
        if link:  # Several links in one part ("[[A]]-[[B]]") are co-coaches.
            out.extend((t, W.plain(x or t)) for t, x in link)
            continue
        name = re.sub(r"\(\d+\)|\s+", " ", W.plain(part)).strip(" '*†‡")
        if name and not re.fullmatch(r"[\W\d]*|n/?a|—|–|-|unknown|desconocido", name, re.I):
            out.append((name, name))
    return [(t, re.sub(r"\s*\(\d+\)\s*$", "", n).strip()) for t, n in out if n]


def header_labels(table: list[list[dict]]) -> list[str]:
    heads = [r for r in table if r and all(c["header"] for c in r)]
    width = max(len(r) for r in table)
    labels = [""] * width
    for r in heads:
        for i, label in enumerate(W.header_labels(r)):  # reads {{abbr|No.|...}} as "No."
            labels[i] = (labels[i] + " " + label).strip().lower()
    return labels


def find_col(labels: list[str], *needles: str) -> int | None:
    for n in needles:
        for i, l in enumerate(labels):
            if re.search(n, l):
                return i
    return None


# ---------------------------------------------------------------- coaches


def coach_rows(text: str, comp: dict) -> list[dict]:
    """Every (year, coach, club) row from the season tables of a winning-managers list."""
    rows = []
    for table in W.all_tables(text):
        if not table or len(table) < 2:
            continue
        labels = header_labels(table)
        season = find_col(labels, r"^season|^final|^edici|^temporada|^year")
        coach = find_col(labels, r"winning manager|manager name|^manager|name|entrenador")
        club = find_col(labels, r"^club|^equipo|club ")
        nat = find_col(labels, r"nationality|^country$|^nation$|país")
        runner_coach = None
        if comp.get("runnersUp") == "table":
            ents = [i for i, l in enumerate(labels) if "entrenador" in l]
            clubs = [i for i, l in enumerate(labels) if "club" in l]
            if len(ents) >= 2 and len(clubs) >= 2:
                coach, runner_coach, club, runner_club = ents[0], ents[1], clubs[0], clubs[1]
        if season is None or coach is None or club is None:
            continue
        torneo = find_col(labels, r"torneo")
        for r in table:
            if all(c["header"] for c in r) or len(r) <= max(season, coach, club):
                continue
            stext = W.plain(r[season]["text"])
            y = re.search(r"\b(18|19|20)\d\d\b", stext)
            if not y:
                continue
            # Summary tables list several years in one cell ("2003, 2007, 2014"): only season rows count.
            if len(re.findall(r"\b(?:18|19|20)\d\d(?:\s*[–-]\s*\d{2,4})?", stext)) > 1:
                continue
            ppl = people_in(r[coach]["text"])
            if not ppl:
                continue
            year = int(y.group())
            tourn = W.plain(r[torneo]["text"]) if torneo is not None and torneo < len(r) else ""
            # Argentina's split seasons ("1996-97 Clausura") end the next year: the page calls it Clausura 1997.
            if re.search(r"\d{4}\s*[-–/]\s*\d{2}", W.plain(r[season]["text"])) and re.search(r"clausura|final", tourn, re.I):
                year += 1
            row = {"year": year, "seasonText": W.plain(r[season]["text"]).strip(), "coaches": ppl,
                   "nation": nation(r[nat]["text"]) if nat is not None and nat < len(r) else nation(r[coach]["text"]),
                   "clubCell": r[club]["text"], "link": (W.links(r[season]["text"]) or [(None, None)])[0][0],
                   "tournament": W.plain(r[torneo]["text"]).strip() if torneo is not None and torneo < len(r) else None}
            if runner_coach is not None and runner_coach < len(r):
                row["runner"] = {"coaches": people_in(r[runner_coach]["text"]), "nation": nation(r[runner_coach]["text"]),
                                 "clubCell": r[runner_club]["text"]}
            rows.append(row)
    return rows


def final_managers(pages: list[str], refresh: bool) -> dict[str, list[list[str]]]:
    """Both managers of each final, from the line-ups in the final's article (saved; only missing ones are read)."""
    saved = json.loads(FINAL_MANAGERS.read_text(encoding="utf-8")) if FINAL_MANAGERS.exists() else {}
    missing = [p for p in pages if p and (refresh or p not in saved)]
    for n, title in enumerate(missing):
        url = f"https://en.wikipedia.org/w/index.php?title={urllib.parse.quote(title.replace(' ', '_'))}&action=raw"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            log(f"warning: could not read {title} ({err}); keeping the saved copy")
            continue
        found = []
        for m in re.finditer(r"'''\s*(?:Manager|Head coach|Coach)s?\s*:?\s*'''[^\n]*\n(?:\|-\s*\n)?\|[^\n]*?((?:\{\{[^{}]*\}\}\s*)?\[\[[^\]]+\]\][^\n]*)", text, re.I):
            cell = m.group(1)
            ppl = people_in(cell)
            if ppl:
                found.append([ppl[0][0], ppl[0][1], nation(cell) or ""])
        saved[title] = found
        if n % 10 == 9:
            FINAL_MANAGERS.parent.mkdir(parents=True, exist_ok=True)
            FINAL_MANAGERS.write_text(json.dumps(saved, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        time.sleep(0.6)
    FINAL_MANAGERS.parent.mkdir(parents=True, exist_ok=True)
    FINAL_MANAGERS.write_text(json.dumps(dict(sorted(saved.items())), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return saved


def same_person(a: tuple[str, str], b: tuple[str, str]) -> bool:
    if key(a[0]) == key(b[0]) or key(a[1]) == key(b[1]):
        return True
    sa, sb = a[1].split()[-1], b[1].split()[-1]
    return key(sa) == key(sb) and len(key(sa)) > 3


# ---------------------------------------------------------------- players


def player_table(text: str, anchor: str | None) -> list[dict]:
    body = text[re.search(anchor, text).start():] if anchor else text
    table = W.parse_table(W.find_table(body, anchor or r"\{\|")) if anchor else next(t for t in W.all_tables(text) if len(t) > 10)
    labels = header_labels(table)
    who = find_col(labels, r"^player|jugador|jogador")
    num = find_col(labels, r"no\. of wins|^no\.?$|titles|títulos|t[ií]tulos")
    clubs = find_col(labels, r"club|campeonatos|anos dos")
    years = find_col(labels, r"years|season|anos|campeonatos")
    nat = find_col(labels, r"nationality|^nat")
    out = []
    for r in table:
        if all(c["header"] for c in r) or who is None or num is None or len(r) <= max(who, num):
            continue
        ppl = people_in(r[who]["text"])
        n = re.search(r"\d+", W.plain(r[num]["text"]))
        if not ppl or not n:
            continue
        detail = W.plain(strip(r[clubs]["text"])) if clubs is not None and clubs < len(r) else ""
        if years is not None and years != clubs and years < len(r):
            detail = f"{detail} ({W.plain(strip(r[years]['text']))})".strip()
        out.append({"key": ppl[0][0], "name": ppl[0][1], "titles": int(n.group()),
                    "nation": nation(r[nat]["text"]) if nat is not None and nat < len(r) else nation(r[who]["text"]),
                    "detail": re.sub(r",\s*;", ";", re.sub(r",(?=\S)", ", ", re.sub(r"\s+", " ", detail))).strip().removeprefix("(").strip()})
    return out


def player_list(text: str, anchor: str) -> list[dict]:
    """A numbered list such as '# {{Bandiera|ITA}} [[A]], [[B]] 9'."""
    body = text[re.search(anchor, text).end():]
    out = []
    for line in body.splitlines()[1:]:
        if line.startswith("="):
            break
        if not line.startswith("#"):
            continue
        n = re.search(r"(\d+)\s*$", W.strip_refs(line))
        if not n:
            continue
        current = None
        for part in re.split(r",\s*", line.lstrip("# ")):
            current = nation(part) or current
            link = W.links(part)
            if link:
                out.append({"key": link[0][0], "name": W.plain(link[0][1] or link[0][0]), "titles": int(n.group(1)),
                            "nation": current, "detail": ""})
    return out


# ---------------------------------------------------------------- build


def page_titles(folder: str) -> tuple[list[dict], dict]:
    path = next((ROOT / "football" / folder / "data").glob(f"{folder}.json"))
    d = json.loads(path.read_text(encoding="utf-8"))
    rows = d.get("finals") or d.get("titles")
    return rows, d


def build_comp(folder: str, comp: dict, refresh: bool, clubs: ClubIndex) -> tuple[dict, list[str]]:
    errors, notes = [], []
    titles, pdata = page_titles(folder)
    lang, title = comp["coaches"]
    raw = coach_rows(page(lang, title, refresh), comp)
    by_year = defaultdict(list)
    for t in titles:
        if t.get("champion"):
            by_year[t["year"]].append(t)
    club_name = lambda cid: (pdata["clubs"].get(cid) or {}).get("name", cid)  # noqa: E731

    def match(row: dict, used: set) -> dict | None:
        cands = [t for t in by_year.get(row["year"], []) if id(t) not in used]
        if not cands:
            return None
        cid = clubs.resolve(row["clubCell"], comp["country"]) if W.links(row["clubCell"]) else None
        exact = [t for t in cands if t["champion"] == cid]
        if exact:
            return exact[0]
        label = key(W.plain(strip(row["clubCell"])))
        fuzzy = [t for t in cands if label and (key(club_name(t["champion"])) in label or label in key(club_name(t["champion"])))]
        if fuzzy:
            return fuzzy[0]
        return cands[0] if len(cands) == 1 else None

    used: set = set()
    seasons = []
    unmatched = []
    for row in raw:
        t = match(row, used)
        if not t:
            unmatched.append(f"{row['seasonText']} {W.plain(strip(row['clubCell']))}")
            continue
        used.add(id(t))
        seasons.append({"season": t["season"], "year": t["year"], "club": t["champion"],
                        "coaches": [{"key": k, "name": n} for k, n in row["coaches"]], "nation": row["nation"],
                        "runnerUp": t.get("runnerUp"), "link": row.get("link"), "runner": row.get("runner")})
    first = min((r["year"] for r in raw), default=0)
    era = [t for t in titles if t.get("champion") and t["year"] >= first]
    covered = len({(s["season"], s["club"]) for s in seasons})
    if unmatched:
        notes.append(f"{len(unmatched)} coach rows not matched to a champion: {unmatched[:6]}")
    if covered < 0.95 * len(era):
        errors.append(f"{folder}: coaches for {covered} of {len(era)} titles")

    # Finals reached (the cups).
    finals = []
    if comp.get("runnersUp") == "articles":
        mgrs = final_managers([s["link"] for s in seasons if s["link"]], refresh)
        missing = 0
        for s in seasons:
            found = mgrs.get(s["link"] or "", [])
            win = [(c["key"], c["name"]) for c in s["coaches"]]
            other = [m for m in found if not any(same_person((m[0], m[1]), w) for w in win)]
            if other:
                finals.append({"season": s["season"], "year": s["year"], "club": s["runnerUp"],
                               "coaches": [{"key": other[0][0], "name": other[0][1]}], "nation": other[0][2] or None})
            else:
                missing += 1
        if missing > 2:
            errors.append(f"{folder}: no runner-up coach for {missing} finals")
        elif missing:
            notes.append(f"{missing} finals without the runner-up's coach")
    elif comp.get("runnersUp") == "table":
        for s in seasons:
            r = s.get("runner")
            if r and r["coaches"]:
                finals.append({"season": s["season"], "year": s["year"], "club": s["runnerUp"],
                               "coaches": [{"key": k, "name": n} for k, n in r["coaches"][:1]], "nation": r["nation"]})
        if len(finals) < len(seasons) - 2:
            errors.append(f"{folder}: runner-up coaches for {len(finals)} of {len(seasons)} finals")

    # Coaches, aggregated by person.
    coaches: dict[str, dict] = {}

    def add(entry: dict, won: bool) -> None:
        for c in entry["coaches"]:
            k = key(c["key"])
            p = coaches.setdefault(k, {"name": c["name"], "nation": None, "titles": [], "lost": []})
            p["nation"] = p["nation"] or entry["nation"]
            (p["titles"] if won else p["lost"]).append({"season": entry["season"], "club": entry["club"]})
    for s in seasons:
        add(s, True)
    for f in finals:
        add(f, False)
    coach_list = sorted(coaches.values(), key=lambda p: (-len(p["titles"]), -len(p["lost"]), p["name"]))

    # Players.
    players = []
    if comp.get("players"):
        plang, ptitle, anchor, kind = comp["players"]
        text = page(plang, ptitle, refresh)
        rows = player_list(text, anchor) if kind == "list" else player_table(text, anchor)
        agg: dict[str, dict] = {}
        for r in rows:
            k = key(r["key"])
            p = agg.setdefault(k, {"name": r["name"], "nation": r["nation"], "titles": 0, "detail": r["detail"]})
            p["titles"] = max(p["titles"], r["titles"])
            p["nation"] = p["nation"] or r["nation"]
        players = sorted(agg.values(), key=lambda p: (-p["titles"], p["name"]))
        if players:
            cut = players[min(24, len(players) - 1)]["titles"]
            players = [p for p in players if p["titles"] >= cut][:40]

    # Checks.
    exp = comp["expect"]
    name, n = exp["coach"]
    got = next((len(p["titles"]) for p in coach_list if key(p["name"]) == key(name)), 0)
    if got != n:
        errors.append(f"{folder}: {name} has {got} titles as coach, expected {n}")
    if "finals" in exp:
        name, n = exp["finals"]
        got = next((len(p["titles"]) + len(p["lost"]) for p in coach_list if key(p["name"]) == key(name)), 0)
        if got != n:
            errors.append(f"{folder}: {name} reached {got} finals as coach, expected {n}")
    if "player" in exp:
        name, n = exp["player"]
        got = next((p["titles"] for p in players if key(p["name"]) == key(name)), 0)
        if got != n:
            errors.append(f"{folder}: {name} has {got} titles as a player, expected {n}")

    nations = {}
    for c in [p["nation"] for p in coach_list + players if p["nation"]]:
        name_, flag = COUNTRIES.get(c) or (nation_info(c)["name"], nation_info(c)["flag"])
        nations[c] = {"name": name_, "flag": flag}
    sources = [f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"]
    if comp.get("players"):
        sources.append(f"https://{comp['players'][0]}.wikipedia.org/wiki/{urllib.parse.quote(comp['players'][1].replace(' ', '_'))}")
    data = {
        "meta": {"generated": date.today().isoformat(), "sources": sources, "kind": comp["kind"], "notes": notes,
                 "coachesNote": comp.get("coachesNote"), "playersNote": comp.get("playersNote")},
        "coaches": [{"name": p["name"], "nation": p["nation"], "titles": p["titles"], "lost": p["lost"]} for p in coach_list],
        "players": players,
        "nations": dict(sorted(nations.items())),
    }
    return data, errors


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="re-download the Wikipedia pages")
    ap.add_argument("--only", help="build one competition (its page folder)")
    args = ap.parse_args()
    clubs = ClubIndex()
    failed = False
    for folder, comp in COMPS.items():
        if args.only and folder != args.only:
            continue
        data, errors = build_comp(folder, comp, args.refresh, clubs)
        for n in data["meta"]["notes"]:
            log(f"note: {folder}: {n}")
        if errors:
            failed = True
            for e in errors:
                log(f"error: {e}")
            continue
        out = ROOT / "football" / folder / "data" / "people.json"
        old = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
        strip_gen = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}  # noqa: E731
        if old and strip_gen(old) == strip_gen(data):
            print(f"{out.relative_to(ROOT)} is up to date")
            continue
        out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}: {len(data['coaches'])} coaches, {len(data['players'])} players")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
