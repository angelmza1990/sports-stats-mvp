"""The great rivalries of Mexico, MLS, Colombia and Chile, read from the match tables of Wikipedia's rivalry articles
(English and Spanish). One generic reader handles their layouts: a row per match with the date, the two teams and the
score in columns named in either language, tables where the home side is implied ("América in the league at home"),
results that carry the team names ("Cruz Azul 4–1 América") and dates without a year (taken from the season column).
Rivalries whose articles only publish head-to-head totals are kept as summaries."""

from __future__ import annotations

import re

from rivalries_common import EN_MONTHS, W, Pair, en_round, fold, iso, page, parse_date, score_of, shootout

# Header labels (folded to lowercase ASCII) and the field each one holds.
FIELDS = [
    ("home", ("local team", "home team", "local", "home")),
    ("away", ("visiting team", "away team", "visitante", "visita", "away")),
    ("score", ("resultado", "result", "score", "res")),
    ("date", ("fecha", "date")),
    ("comp", ("competicion", "competition", "tournament", "motivo")),
    ("round", ("jornada", "instancia", "phase", "fase")),
    ("season", ("season", "temporada", "torneo")),
    ("venue", ("estadio", "stadium", "venue", "location", "cancha")),
]


def field_index(header: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i, label in enumerate(header):
        lab = fold(label).strip(" .:")
        for name, words in FIELDS:
            if name not in out and any(lab == w or lab.startswith(w + " ") for w in words):
                out[name] = i
                break
    return out


def section(text: str, heading: str) -> str:
    """The text of a section (up to the next heading of the same or a higher level)."""
    m = re.search(r"^(=+)\s*" + heading + r"\s*=+\s*$", text, re.M)
    if not m:
        raise SystemExit(f"no section {heading!r}")
    level = len(m.group(1))
    nxt = re.search(r"^={1,%d}[^=]" % level, text[m.end():], re.M)
    return text[m.end(): m.end() + nxt.start() if nxt else len(text)]


def clean_score(text: str) -> str:
    return re.sub(r"\{\{\s*center\s*\|\s*1\s*=", "{{center|", text).replace("1=", "")


def serial_date(text: str) -> str | None:
    """A date pasted as a spreadsheet serial number ("19860" is 16 May 1954)."""
    m = re.fullmatch(r"\s*(\d{5})\s*", W.plain(text))
    if not m or not 7000 < int(m.group(1)) < 60000:
        return None
    from datetime import date, timedelta
    return (date(1899, 12, 30) + timedelta(days=int(m.group(1)))).isoformat()


def year_date(text: str, season: str) -> str | None:
    """"March 31" with the year from the season column ("2018")."""
    m = re.search(r"([A-Za-z]+)\.?\s+(\d{1,2})\b", W.plain(text))
    y = re.search(r"\b(19|20)\d\d\b", season or "")
    if m and y and EN_MONTHS.get(m.group(1).lower()):
        return iso(int(y.group()), EN_MONTHS[m.group(1).lower()], int(m.group(2)))
    return None


def every_table(text: str) -> list[list[list[dict]]]:
    """Every table in the text, including tables nested inside a layout table (a title row holding the match list)."""
    out = []
    for m in re.finditer(r"\n\{\|", "\n" + text):
        try:
            out.append(W.parse_table(W.find_table(("\n" + text)[m.start():], r"^", 0)))
        except LookupError:
            continue
    return out


def table_matches(text: str, pair: Pair, *, home: str | None = None, comp: str = "", stage: str = "") -> list[dict]:
    """Every match row of every table in `text`. `home` fixes the home side for tables that leave it out;
    `comp`/`stage` label tables that have no competition column."""
    out = []
    for grid in every_table(text):
        idx, start = {}, 0
        for k, row in enumerate(grid[:3]):  # the header can sit under a title row
            idx = field_index([W.plain(c["text"]) for c in row])
            if "date" in idx and "score" in idx:
                start = k + 1
                break
        if "date" not in idx or "score" not in idx:
            continue
        for r in grid[start:]:
            if len(r) <= max(idx.values()) or all(c["header"] for c in r):
                continue
            get = lambda f: r[idx[f]]["text"] if f in idx else ""  # noqa: E731
            raw = clean_score(get("score"))
            season = W.plain(get("season")).strip()
            d = parse_date(get("date")) or year_date(get("date"), season) or serial_date(get("date"))
            sc = score_of(raw)
            if "home" in idx and "away" in idx:
                h, a = pair.team(get("home")), pair.team(get("away"))
            elif home:  # "América in the league at home"
                h = home
                a = pair.other(home)
            else:  # "Cruz Azul 4–1 América": the first team named is at home
                named = sorted((fold(W.plain(raw)).find(n), cid) for cid, names in pair.names for n in names if n in fold(W.plain(raw)))
                h = named[0][1] if named else None
                a = pair.other(h) if h else None
            if not d or not sc or not h or not a or h == a:
                continue
            m = {"date": d, "home": h, "away": a, "hs": sc[0], "as": sc[1], "_comp": W.plain(get("comp")).strip() or comp,
                 "_round": W.plain(get("round")).strip(), "season": season.strip("†*^‡ "), "_stage": stage}
            venue = W.plain(get("venue")).strip(" |")
            if venue and venue.lower() not in ("unknown", "estadio"):
                m["venue"] = venue
            pens = shootout(raw)
            if pens:
                m["pens"] = list(pens)
            if re.search(r"a\.?e\.?t|tiempo extra|pr[oó]rroga", raw, re.I):
                m["aet"] = True
            m["_raw_season"] = get("season")
            out.append(m)
    return out


def finalize(matches: list[dict], classify) -> tuple[list[dict], list[dict]]:
    """(official, friendlies) after `classify(match) -> (comp, stage, round)`; duplicates of the same date are dropped."""
    official, friendlies, seen = [], [], set()
    for m in sorted(matches, key=lambda m: m["date"]):
        key = (m["date"], m["home"], m["away"])
        if key in seen:
            continue
        seen.add(key)
        comp, stage, rnd = classify(m)
        if not stage:
            continue
        m.update({"comp": comp, "stage": stage})
        if rnd:
            m["round"] = rnd
        for k in [k for k in m if k.startswith("_")]:
            m.pop(k)
        (friendlies if stage == "friendly" else official).append(m)
    return official, friendlies


def knockout(text: str) -> str:
    """A round name from text like "Clausura 2025 Semi-finals", "Colombia Cup (Final)", "Cuartos de final"."""
    t = fold(text)
    for pat, name in ((r"semi|semifinal", "Semi-finals"), (r"quarter|cuartos", "Quarter-finals"), (r"round of 16|octavos", "Round of 16"),
                      (r"\bfinal", "Final"), (r"play-?off|repechaje|reclasif", "Play-off")):
        if re.search(pat, t):
            return name
    return ""


# ---------------------------------------------------------------- Mexico

def mx_classify(liguilla_words=("liguilla", "playoff", "play-off", "quarter", "semi", "final", "cuartos", "reclasificacion")):
    def classify(m):
        t = fold(f"{m['_comp']} {m['_round']} {m['_raw_season']} {m['_stage']}")
        if "amistos" in t or "friendl" in t:
            return "Friendly", "friendly", ""
        if "copa mx" in t or "copa mexico" in t or "*" in m["_raw_season"]:
            return "Copa MX", "cup", knockout(t)
        if "campeon de campeones" in t or "campeones cup" in t:
            return "Campeón de Campeones", "super", "Final"
        if "libertadores" in t or "pre libertadores" in t or "pre-libertadores" in t or "interliga" in t or "^" in m["_raw_season"]:
            name = "Copa Libertadores" if "libertadores" in t and "pre" not in t else "Pre-Libertadores"
            return name, "intl" if name == "Copa Libertadores" else "cup", knockout(t)
        if "concacaf" in t or "leagues cup" in t or "sudamericana" in t:
            return ("Leagues Cup" if "leagues cup" in t else "CONCACAF Champions Cup"), "intl", knockout(t)
        if "2nd division" in t or "segunda" in t:
            return "Segunda División", "league", ""
        if m["_stage"] == "playoff" or any(w in t for w in liguilla_words) and not re.search(r"regular|round-robin|jornada \d", t):
            return "Liga MX", "playoff", knockout(t) or "Liguilla"
        return "Liga MX", "league", ""
    return classify


AMERICA_CHIVAS = Pair("club-america", ("america",), "guadalajara", ("guadalajara", "chivas"))


def build_super_clasico(refresh: bool) -> dict:
    es = page("Clásico del fútbol mexicano", refresh, lang="es")
    ms = []
    for heading, stage in (("Liga y Liguilla", ""), ("Copa México", ""), ("Campeón de Campeones", ""), ("Copa Libertadores de América", ""),
                           ("Copa de Campeones de la Concacaf", ""), ("Selectivo Pre-Libertadores e Interliga", ""), ("Partidos amistosos", "friendly")):
        body = section(es, re.escape(heading))
        label = "" if heading == "Liga y Liguilla" else heading
        ms += [{**m, "_comp": m["_comp"] or label, "_stage": stage} for m in table_matches(body, AMERICA_CHIVAS)]
    for m in ms:
        if m["_stage"] == "friendly":
            m["_comp"] = "amistoso"
        elif re.search(r"liguilla|cuartos|semifinal|final", fold(m["_round"])):
            m["_stage"] = "playoff"
    official, friendlies = finalize(ms, mx_classify())
    return {"matches": official, "friendlies": friendlies,
            "source": {"label": "Spanish Wikipedia, Clásico del fútbol mexicano", "url": "https://es.wikipedia.org/wiki/Cl%C3%A1sico_del_f%C3%BAtbol_mexicano"},
            "notes": ["Liguilla (play-off) matches count with the league and are also grouped into ties.",
                      "The Pre-Libertadores and InterLiga qualifiers are counted as domestic cups."]}


AMERICA_CRUZ_AZUL = Pair("club-america", ("america",), "cruz-azul", ("cruz azul",))


def build_clasico_joven(refresh: bool) -> dict:
    en = page("Clásico Joven", refresh)
    ms = []
    ms += table_matches(section(en, re.escape("América in the league at home")), AMERICA_CRUZ_AZUL, home="club-america")
    ms += table_matches(section(en, re.escape("Cruz Azul in the league at home")), AMERICA_CRUZ_AZUL, home="cruz-azul")
    ms += [{**m, "_stage": "playoff"} for m in table_matches(section(en, re.escape("Liguilla matches")), AMERICA_CRUZ_AZUL)]
    for heading in ("Copa MX", "Campeón de Campeones", "CONCACAF Champions Cup"):
        ms += [{**m, "_comp": m["_comp"] or heading} for m in table_matches(section(en, re.escape(heading)), AMERICA_CRUZ_AZUL)]
    official, friendlies = finalize(ms, mx_classify())
    return {"matches": official, "friendlies": friendlies,
            "source": {"label": "English Wikipedia, Clásico Joven", "url": "https://en.wikipedia.org/wiki/Cl%C3%A1sico_Joven"},
            "notes": ["Liguilla (play-off) matches count with the league and are also grouped into ties.",
                      "The source lists league matches by home side, the Liguilla, the Copa MX, the Campeón de Campeones and CONCACAF; "
                      "the four Pre-Libertadores and InterLiga qualifiers in its totals have no match list, and friendlies are not listed."]}


AMERICA_PUMAS = Pair("club-america", ("america",), "pumas-unam", ("pumas", "unam", "universidad"))


def build_capitalino(refresh: bool) -> dict:
    en = page("Clásico Capitalino", refresh)
    ms = table_matches(section(en, "Results"), AMERICA_PUMAS)
    for m in ms:
        if re.search(r"play-?off|quarter|semi|final(?! stage)", fold(m["_round"])) and "*" not in m["_raw_season"] and "^" not in m["_raw_season"]:
            m["_stage"] = "playoff"
        if "campeon" in fold(m["_raw_season"] + m["_round"]):
            m["_comp"] = "Campeón de Campeones"
    official, friendlies = finalize(ms, mx_classify())
    return {"matches": official, "friendlies": friendlies,
            "source": {"label": "English Wikipedia, Clásico Capitalino", "url": "https://en.wikipedia.org/wiki/Cl%C3%A1sico_Capitalino"},
            "notes": ["The source marks each season by competition (Liga MX †, Copa MX *, Pre Pre Libertadores ^); Liguilla matches "
                      "count with the league and are also grouped into ties.",
                      "The source's list stops in early 2022, so later meetings are missing."]}


MONTERREY_TIGRES = Pair("monterrey", ("monterrey", "rayados"), "uanl", ("uanl", "tigres"))


def build_regiomontano(refresh: bool) -> dict:
    en = page("Clásico Regiomontano", refresh)
    ms = table_matches(section(en, "List of matches"), MONTERREY_TIGRES)
    for m in ms:
        if re.search(r"playoff|liguilla|final", fold(m["_comp"])) and not re.search(r"copa|concacaf|leagues|campeon", fold(m["_comp"])):
            m["_stage"] = "playoff"
    official, friendlies = finalize(ms, mx_classify())
    return {"matches": official, "friendlies": friendlies,
            "source": {"label": "English Wikipedia, Clásico Regiomontano", "url": "https://en.wikipedia.org/wiki/Cl%C3%A1sico_Regiomontano"},
            "notes": ["Includes the 1960 meeting in the second division. Liguilla (play-off) matches count with the league and are also grouped into ties."]}


# ---------------------------------------------------------------- MLS

def mls_classify(m):
    t = fold(f"{m['_comp']} {m['_round']}")
    if "friendl" in t or "indoor" in t:
        return "Friendly", "friendly", ""
    if "open cup" in t:
        return "U.S. Open Cup", "cup", knockout(t) or ""
    if "leagues cup" in t:
        return "Leagues Cup", "intl", knockout(t)
    if "concacaf" in t or "champions" in t:
        return "CONCACAF Champions Cup", "intl", knockout(t)
    if "playoff" in t or "mls cup" in t or "is back" in t and "knockout" in t:
        name = "MLS" if "mls" in t or not t.strip() else re.sub(r"\s*playoffs?.*$", "", m["_comp"]).strip()
        return name, "playoff", knockout(t) or "Playoffs"
    if "mls is back" in t:
        return "MLS is Back Tournament", "cup", ""
    if t.startswith("mls"):
        return "MLS", "league", ""
    for league in ("A-League", "USL", "NASL", "APSL", "WSA"):
        if fold(league) in t:
            return league, "league", ""
    return (m["_comp"] or "MLS"), "league", ""


GALAXY_LAFC = Pair("la-galaxy", ("galaxy",), "los-angeles-fc", ("los angeles fc", "lafc"))


def build_trafico(refresh: bool) -> dict:
    en = page("El Tráfico", refresh)
    official, friendlies = finalize(table_matches(section(en, "Matches"), GALAXY_LAFC), mls_classify)
    return {"matches": official, "friendlies": friendlies,
            "source": {"label": "English Wikipedia, El Tráfico", "url": "https://en.wikipedia.org/wiki/El_Tr%C3%A1fico"},
            "notes": ["LAFC joined MLS in 2018; the 2020 meeting was played at the MLS is Back Tournament."]}


SEATTLE_PORTLAND = Pair("seattle-sounders-fc", ("seattle",), "portland-timbers", ("portland",))


def build_cascadia(refresh: bool) -> dict:
    en = section(page("Portland Timbers–Seattle Sounders rivalry", refresh), "Results")
    ms = []
    for heading in ("NASL era", "Alliance era", "A-League/USL era", "MLS era"):
        body = section(en, re.escape(heading))
        body = re.split(r"^====\s*NASL Indoor", body, flags=re.M)[0]
        ms += table_matches(body, SEATTLE_PORTLAND)
    official, friendlies = finalize(ms, mls_classify)
    return {"matches": official, "friendlies": friendlies,
            "source": {"label": "English Wikipedia, Portland Timbers–Seattle Sounders rivalry",
                       "url": "https://en.wikipedia.org/wiki/Portland_Timbers%E2%80%93Seattle_Sounders_rivalry"},
            "notes": ["Counts every era of the two clubs, as the source does: the NASL (1975–1982), the Alliance and A-League/USL "
                      "years and MLS since 2011. Indoor matches and friendlies are left out."]}


RED_BULLS_NYCFC = Pair("new-york-red-bulls", ("red bulls", "nyrb"), "new-york-city-fc", ("new york city", "nycfc"))


def build_hudson(refresh: bool) -> dict:
    en = page("Hudson River Derby", refresh)
    official, friendlies = finalize(table_matches(section(en, "Results"), RED_BULLS_NYCFC), mls_classify)
    return {"matches": official, "friendlies": friendlies,
            "source": {"label": "English Wikipedia, Hudson River Derby", "url": "https://en.wikipedia.org/wiki/Hudson_River_Derby"},
            "notes": ["NYCFC joined MLS in 2015.", "Three meetings the source lists without a date are left out."]}


# ---------------------------------------------------------------- Colombia

def co_classify(m):
    t = fold(f"{m['_comp']} {m['_round']} {m['_stage']}")
    if "amistos" in t or "friendl" in t:
        return "Friendly", "friendly", ""
    if "copa colombia" in t or "colombia cup" in t or "copa de colombia" in t:
        return "Copa Colombia", "cup", knockout(t)
    if "superliga" in t:
        return "Superliga", "super", "Final"
    if "libertadores" in t:
        return "Copa Libertadores", "intl", knockout(t)
    if "sudamericana" in t or "merconorte" in t or "conmebol" in t:
        return "CONMEBOL", "intl", knockout(t)
    if re.search(r"\bfinal(es)?\b|cuadrangular|semifinal|cuartos|play-?off", t) and not re.search(r"round-robin|todos contra todos", t):
        rnd = knockout(t) if not re.search(r"cuadrangular|octogonal|hexagonal", t) else "Final group"
        return "Primera A", "playoff", rnd or "Final group"
    return "Primera A", "league", ""


NACIONAL_MEDELLIN = Pair("atletico-nacional", ("nacional", "municipal"), "independiente-medellin", ("medellin", "dim"))


def build_paisa(refresh: bool) -> dict:
    en = page("El Clásico Paisa", refresh)
    ms = table_matches(section(en, re.escape("Official matches by first division")), NACIONAL_MEDELLIN)
    ms += [{**m, "_comp": m["_comp"] or "Colombia Cup"} for m in table_matches(section(en, re.escape("Official matches for the colombian cup")), NACIONAL_MEDELLIN)]
    official, friendlies = finalize(ms, co_classify)
    published = summary_from_table(en, re.escape("Head-to-head"), NACIONAL_MEDELLIN, NACIONAL_MEDELLIN.a)["total"]
    return {"matches": official, "friendlies": friendlies, "published": published,
            "source": {"label": "English Wikipedia, El Clásico Paisa", "url": "https://en.wikipedia.org/wiki/El_Cl%C3%A1sico_Paisa"},
            "notes": ["Atlético Nacional played as Atlético Municipal until 1950. The final rounds of each season (quadrangulars, "
                      "home-and-away semi-finals and finals) are shown as play-offs."]}


AMERICA_CALI = Pair("america-de-cali", ("america",), "deportivo-cali", ("deportivo cali",))


def build_vallecaucano(refresh: bool) -> dict:
    es = page("Clásico vallecaucano", refresh, lang="es")
    ms = []
    for decade in re.findall(r"^===\s*(Resultados entre \d{4}-\d{4})\s*===", es, re.M):
        ms += table_matches(section(es, re.escape(decade)), AMERICA_CALI)
    official, friendlies = finalize(ms, co_classify)
    return {"matches": official, "friendlies": friendlies,
            "source": {"label": "Spanish Wikipedia, Clásico vallecaucano", "url": "https://es.wikipedia.org/wiki/Cl%C3%A1sico_vallecaucano"},
            "notes": ["The final rounds of each season (quadrangulars, semi-finals and finals) are shown as play-offs."]}


NACIONAL_MILLONARIOS = Pair("atletico-nacional", ("nacional", "municipal"), "millonarios", ("millonarios",))


def build_nacional_millonarios(refresh: bool) -> dict:
    es = page("Rivalidad entre Atlético Nacional y Millonarios", refresh, lang="es")
    ms = []
    for heading, comp in (("En Liga", ""), ("En competiciones internacionales", ""), ("En Superliga", "Superliga"),
                          ("En Copa Colombia", "Copa Colombia"), ("En competiciones amistosas", "amistoso")):
        ms += [{**m, "_comp": (comp if comp in ("amistoso", "Superliga", "Copa Colombia") else m["_comp"])}
               for m in table_matches(section(es, re.escape(heading)), NACIONAL_MILLONARIOS)]
    official, friendlies = finalize(ms, co_classify)
    return {"matches": official, "friendlies": friendlies,
            "source": {"label": "Spanish Wikipedia, Rivalidad entre Atlético Nacional y Millonarios",
                       "url": "https://es.wikipedia.org/wiki/Rivalidad_entre_Atl%C3%A9tico_Nacional_y_Millonarios"},
            "notes": ["Atlético Nacional played as Atlético Municipal until 1950. The final rounds of each season are shown as play-offs."]}


# ---------------------------------------------------------------- Chile

def cl_classify(m):
    t = fold(f"{m['_comp']} {m['_round']} {m['_stage']}")
    if "amistos" in t or "verano" in t or "friendl" in t:
        return "Friendly", "friendly", ""
    if "supercopa" in t:
        return "Supercopa", "super", "Final"
    if "copa chile" in t or "copa de chile" in t or "campeonato de apertura" in t:
        return ("Campeonato de Apertura" if "apertura" in t else "Copa Chile"), "cup", knockout(t)
    if "liguilla" in t:
        return "Liguilla Pre-Libertadores", "cup", ""
    if "libertadores" in t or "sudamericana" in t or "mercosur" in t:
        return ("Copa Mercosur" if "mercosur" in t else "Copa Libertadores" if "libertadores" in t else "Copa Sudamericana"), "intl", knockout(t)
    if re.search(r"semifinal|cuartos|\bfinal\b|play-?off|definicion", t):
        return "Primera División", "playoff", knockout(t)
    return "Primera División", "league", ""


COLO_U = Pair("colo-colo", ("colo-colo", "colo colo"), "universidad-de-chile", ("universidad de chile", "u. de chile", "u de chile"))


def build_superclasico_chile(refresh: bool) -> dict:
    es = page("Clásico del fútbol chileno", refresh, lang="es")
    body = section(es, re.escape("Detalle partidos jugados"))
    ms, label = [], ""
    for chunk in re.split(r"\n(?=\{\|)", body):
        title = re.search(r"\A\{\|[^\n]*\n\|-\n!\s*(?:colspan=\"?\d+\"?\s*\|)?\s*([^\n|<]+)", chunk)
        if title and not re.search(r"\d|fecha", title.group(1), re.I):
            label = title.group(1).strip()
        # Only this chunk's own rows: a layout table's nested list comes in the next chunk.
        own = chunk if chunk.count("{|") <= 1 else chunk[:chunk.find("{|", 2)]
        ms += [{**m, "_comp": m["_comp"] or label} for m in table_matches(own, COLO_U)]
    official, friendlies = finalize(ms, cl_classify)
    return {"matches": official, "friendlies": friendlies,
            "source": {"label": "Spanish Wikipedia, Clásico del fútbol chileno", "url": "https://es.wikipedia.org/wiki/Cl%C3%A1sico_del_f%C3%BAtbol_chileno"},
            "notes": ["The Argentine summer tournaments and other friendlies are listed separately."]}


def summary_from_table(text: str, heading: str, pair: Pair, first: str) -> dict:
    """A head-to-head table (Competition, played, wins of the first club, draws, wins of the second, goals) as a summary."""
    rows = []
    for grid in W.all_tables("\n" + section(text, heading)):
        for r in grid[1:]:
            label = W.plain(r[0]["text"]).strip()
            nums = [W.number(c["text"]) for c in r[1:7]]
            if len(nums) < 4 or None in nums[:4] or not label:
                continue
            row = {"comp": label, "n": nums[0], "a": nums[1], "d": nums[2], "b": nums[3],
                   "ga": nums[4] if len(nums) > 4 else None, "gb": nums[5] if len(nums) > 5 else None}
            if first == pair.b:
                row["a"], row["b"], row["ga"], row["gb"] = row["b"], row["a"], row["gb"], row["ga"]
            rows.append(row)
        if rows:
            break
    total = next((r for r in rows if re.match(r"(?i)total", r["comp"])), None)
    comps = [r for r in rows if not re.match(r"(?i)total", r["comp"])]
    if total is None:
        total = {"comp": "Total", **{k: sum(r[k] for r in comps) if all(r[k] is not None for r in comps) else None
                                    for k in ("n", "a", "d", "b", "ga", "gb")}}
    total["comp"] = "Total"
    return {"comps": comps, "total": total}


COLO_UC = Pair("colo-colo", ("colo-colo", "colo colo"), "universidad-catolica", ("universidad catolica", "u. catolica", "catolica"))
U_UC = Pair("universidad-de-chile", ("universidad de chile", "u. de chile"), "universidad-catolica", ("universidad catolica", "u. catolica", "catolica"))


def recent_of(text: str, heading: str, pair: Pair) -> list[dict]:
    official, _ = finalize(table_matches(section(text, heading), pair), cl_classify)
    return official[-12:]


def build_colo_uc(refresh: bool) -> dict:
    es = page("Clásico Colo-Colo - Universidad Católica", refresh, lang="es")
    return {"mode": "summary", "summary": summary_from_table(es, "Historial Estadístico", COLO_UC, COLO_UC.a),
            "recent": recent_of(es, re.escape("Últimos 20 partidos oficiales"), COLO_UC),
            "source": {"label": "Spanish Wikipedia, Clásico Colo-Colo - Universidad Católica",
                       "url": "https://es.wikipedia.org/wiki/Cl%C3%A1sico_Colo-Colo_-_Universidad_Cat%C3%B3lica"},
            "notes": ["Wikipedia publishes this rivalry's totals but not every match, so there is no match-by-match history."]}


def build_universitario(refresh: bool) -> dict:
    es = page("Clásico Universitario", refresh, lang="es")
    return {"mode": "summary", "summary": summary_from_table(es, "Historial estadístico", U_UC, U_UC.a),
            "recent": recent_of(es, re.escape("Últimos 20 partidos oficiales"), U_UC),
            "source": {"label": "Spanish Wikipedia, Clásico Universitario", "url": "https://es.wikipedia.org/wiki/Cl%C3%A1sico_Universitario"},
            "notes": ["Wikipedia publishes this rivalry's totals but not every match, so there is no match-by-match history."]}
