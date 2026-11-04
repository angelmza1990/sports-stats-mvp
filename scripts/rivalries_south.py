"""The great rivalries of Portugal, Paraguay, Bolivia, Ecuador and Peru, from Wikipedia's rivalry articles.

Bolivia's two clásicos and Peru's Universitario vs Alianza Lima publish every match (with the home side) and get a
match-by-match history. The others publish complete totals but no dated match list (Portugal's lists give the season
and round only, Ecuador's the year), so they are kept as summaries, with the latest matches where they are listed."""

from __future__ import annotations

import re

from rivalries_americas import every_table, finalize, knockout, section, summary_from_table, table_matches
from rivalries_common import ES_MONTHS, W, Pair, fold, iso, page, score_of

# ---------------------------------------------------------------- Shared


def stage_matches(text: str, heading: str, pair: Pair, comp: str, stage: str) -> list[dict]:
    # Some header lines open with "!!" ("!!width=13%|Fecha"): read them as ordinary header cells.
    body = re.sub(r"^!!", "!", section(text, heading), flags=re.M)
    return [{**m, "_comp": comp, "_stage": stage} for m in table_matches(body, pair)]


def south_classify(m):
    """(comp, stage, round) from the comp and stage set per section; league rows with a knockout round are play-offs."""
    stage, comp = m["_stage"], m["_comp"]
    if stage == "league":
        rnd = knockout(m["_round"])
        return (comp, "playoff", rnd) if rnd else (comp, "league", "")
    if stage in ("cup", "intl"):
        # The tournament is named in the season column ("Copa Libertadores 1985", "Torneo Play Off 2008").
        named = re.sub(r"\s*\d{4}(?:[-–/]\d{2,4})?\s*$", "", W.plain(m["_raw_season"])).strip()
        return (named or comp), stage, knockout(m["_round"])
    return comp, stage, ""


def wiki(lang: str, title: str) -> dict:
    return {"label": f"{'Spanish' if lang == 'es' else 'English'} Wikipedia, {title}",
            "url": f"https://{lang}.wikipedia.org/wiki/" + title.replace(" ", "_")}


def official_rows(summary: dict, notes: list[str]) -> dict:
    """Drops subtotal and friendly rows and the years after each competition's name; a gap between the competitions
    and the published total is noted."""
    summary["comps"] = [r for r in summary["comps"] if not re.match(r"(?i)sub-?total|amistos|friendl", r["comp"])]
    for r in summary["comps"]:
        r["comp"] = re.sub(r"\s*\(\s*\d{4}(?:\s*[-–]\s*(?:\d{4}|presente|actualidad))?\s*\)", "", r["comp"]).strip()
    n = sum(r["n"] for r in summary["comps"])
    if n != summary["total"]["n"]:
        notes.append(f"The source's competition rows add up to {n} matches and its total to {summary['total']['n']}; the total is shown as published.")
    return summary


# ---------------------------------------------------------------- Bolivia

BOLIVAR_STRONGEST = Pair("bolivar", ("bolivar",), "the-strongest", ("the strongest", "strongest"))


def build_paceno(refresh: bool) -> dict:
    es = page("Clásico paceño", refresh, lang="es")
    ms = stage_matches(es, "Campeonato paceño", BOLIVAR_STRONGEST, "Campeonato Paceño", "local")
    ms += stage_matches(es, "Campeonato Boliviano", BOLIVAR_STRONGEST, "Primera División", "league")
    ms += stage_matches(es, re.escape("Torneo Play Off/Torneo de Invierno"), BOLIVAR_STRONGEST, "Torneo Play Off", "cup")
    ms += stage_matches(es, "Torneos internacionales", BOLIVAR_STRONGEST, "International", "intl")
    official, friendlies = finalize(ms, south_classify)
    return {"matches": official, "friendlies": friendlies, "source": wiki("es", "Clásico paceño"),
            "notes": ["Includes the La Paz championship (Campeonato Paceño) of the 1950s and 1960s, played alongside the first national "
                      "championships. The final rounds of each season (semi-finals and finals) are shown as play-offs.",
                      "The match list starts with the first national championship in 1950; the source also counts the amateur-era "
                      "meetings of 1927–1949, which it does not list."]}


BLOOMING_ORIENTE = Pair("club-blooming", ("blooming",), "oriente-petrolero", ("oriente petrolero", "oriente"))


def build_cruceno(refresh: bool) -> dict:
    es = page("Clásico cruceño", refresh, lang="es")
    ms = stage_matches(es, "Asociación Cruceña", BLOOMING_ORIENTE, "Asociación Cruceña", "local")
    ms += stage_matches(es, "Primera División", BLOOMING_ORIENTE, "Primera División", "league")
    ms += stage_matches(es, "Copas nacionales", BLOOMING_ORIENTE, "Copa", "cup")
    ms += stage_matches(es, "Copas internacionales", BLOOMING_ORIENTE, "International", "intl")
    ms += stage_matches(es, "Liguilla Pre-Sudamericana", BLOOMING_ORIENTE, "Liguilla Pre-Sudamericana", "cup")
    ms += stage_matches(es, "Play-Offs", BLOOMING_ORIENTE, "Torneo Play-Off", "cup")
    ms += stage_matches(es, "Torneos amistosos", BLOOMING_ORIENTE, "Friendly", "friendly")
    official, friendlies = finalize(ms, south_classify)
    for m in official:
        if m["comp"] == "Liguilla Pre-Sudamericana" or m["comp"].startswith("Play-Offs"):
            m["comp"] = "Liguilla Pre-Sudamericana" if m["comp"].startswith("Liguilla") else "Torneo Play-Off"
    return {"matches": official, "friendlies": friendlies, "source": wiki("es", "Clásico cruceño"),
            "notes": ["Includes the Santa Cruz championship (Asociación Cruceña) before the professional league of 1977. "
                      "The final rounds of each season are shown as play-offs.",
                      "The source lists only a few of the Santa Cruz championship matches (it counts 47), so the record of that era is partial."]}


# ---------------------------------------------------------------- Peru

U_ALIANZA = Pair("universitario", ("universitario", "federacion universitaria"), "alianza-lima", ("alianza",))
ANNEX = "Anexo:Estadísticas del Clásico del fútbol peruano"


def build_peru_clasico(refresh: bool) -> dict:
    es = page(ANNEX, refresh, lang="es")
    ms = stage_matches(es, re.escape("Primera División del Perú"), U_ALIANZA, "Primera División", "league")
    ms += stage_matches(es, "Copa Libertadores", U_ALIANZA, "Copa Libertadores", "intl")
    ms += stage_matches(es, "Copa Sudamericana", U_ALIANZA, "Copa Sudamericana", "intl")
    ms += stage_matches(es, "Campeonato de Apertura", U_ALIANZA, "Campeonato de Apertura", "cup")
    ms += stage_matches(es, "Amistoso", U_ALIANZA, "Friendly", "friendly")
    official, friendlies = finalize(ms, lambda m: (m["_comp"], m["_stage"], ""))
    # The annex's own totals (Alianza first), friendlies left out.
    rows = summary_from_table(es, "Historial", U_ALIANZA, U_ALIANZA.b)["comps"]
    rows = [r for r in rows if not re.search(r"(?i)amistoso|total", r["comp"])]
    published = {k: sum(r[k] for r in rows) for k in ("n", "a", "d", "b", "ga", "gb")}
    return {"matches": official, "friendlies": friendlies, "published": published, "source": wiki("es", ANNEX),
            "notes": ["The Campeonato de Apertura (1941–1969), whose official standing is debated, is counted as a domestic cup, as the source does.",
                      "The source gives no rounds, so the play-off matches of each season count with the league."]}


ALIANZA_CRISTAL = Pair("alianza-lima", ("alianza",), "sporting-cristal", ("cristal",))


def peru_recent(text: str, heading: str, pair: Pair) -> list[dict]:
    def classify(m):
        t = fold(f"{m['_comp']} {m['_round']}")
        if "libertadores" in t or "sudamericana" in t:
            return ("Copa Libertadores" if "libertadores" in t else "Copa Sudamericana"), "intl", knockout(t)
        if "amistos" in t:
            return "Friendly", "friendly", ""
        rnd = knockout(t)
        return ("Primera División", "playoff", rnd) if rnd else ("Primera División", "league", "")
    official, _ = finalize(table_matches(section(text, heading), pair), classify)
    return official[-12:]


def build_alianza_cristal(refresh: bool) -> dict:
    title = "Rivalidad entre Alianza Lima y Sporting Cristal"
    es = page(title, refresh, lang="es")
    return {"mode": "summary", "summary": summary_from_table(es, "Historial", ALIANZA_CRISTAL, ALIANZA_CRISTAL.a),
            "recent": peru_recent(es, re.escape("Últimos 10 partidos"), ALIANZA_CRISTAL), "source": wiki("es", title),
            "notes": ["Wikipedia publishes this rivalry's totals but not every match, so there is no match-by-match history."]}


# ---------------------------------------------------------------- Paraguay

OLIMPIA_CERRO = Pair("olimpia", ("olimpia",), "cerro-porteno", ("cerro porteno", "cerro"))
PARAGUAY = "Clásico del fútbol paraguayo"


def paraguay_recent(text: str) -> list[dict]:
    """The list of every official match since 1991: tournament ("Clausura 2026"), day and month, home, "0:2", away."""
    out = []
    for grid in every_table(section(text, "Historial de los últimos partidos")):
        for r in grid[1:]:
            cells = [W.plain(c["text"]).strip() for c in r]
            if len(cells) < 6:
                continue
            _, comp, day, home, score, away = cells[:6]
            y = re.search(r"\b(19|20)\d\d\b", comp)
            d = re.match(r"(\d{1,2})\s+de\s+([a-záéíóú]+)", day.lower())
            sc = score_of(score)
            h, a = OLIMPIA_CERRO.team(home), OLIMPIA_CERRO.team(away)
            if not (y and d and sc and h and a and h != a and ES_MONTHS.get(d.group(2))):
                continue
            t = fold(comp)
            name, stage = (("Copa Libertadores", "intl") if "libertadores" in t else ("Copa Sudamericana", "intl") if "sudamericana" in t
                           else ("Copa Paraguay", "cup") if "copa paraguay" in t or "supercopa" in t else ("Primera División", "league"))
            out.append({"date": iso(int(y.group()), ES_MONTHS[d.group(2)], int(d.group(1))), "home": h, "away": a,
                        "hs": sc[0], "as": sc[1], "comp": name, "stage": stage, "season": re.sub(r"\s*\d{4}$", "", comp).strip() + f" {y.group()}"})
    return sorted(out, key=lambda m: m["date"])[-12:]


def build_paraguay(refresh: bool) -> dict:
    es = page(PARAGUAY, refresh, lang="es")
    notes = ["Wikipedia publishes this rivalry's totals but lists its matches only since 1991, so there is no match-by-match history.",
             "The source notes that the early league results are disputed; its totals follow the most complete count."]
    return {"mode": "summary", "summary": official_rows(summary_from_table(es, "Todos los enfrentamientos", OLIMPIA_CERRO, OLIMPIA_CERRO.b), notes),
            "recent": paraguay_recent(es), "source": wiki("es", PARAGUAY), "notes": notes}


# ---------------------------------------------------------------- Ecuador

BARCELONA_EMELEC = Pair("barcelona-sc", ("barcelona",), "emelec", ("emelec",))


def build_astillero(refresh: bool) -> dict:
    title = "Clásico del Astillero"
    es = page(title, refresh, lang="es")
    notes = ["Wikipedia lists every match of this rivalry by year but without dates, so the page shows its totals only.",
             "Includes the Guayaquil championships (amateur and professional) played before and alongside the national league."]
    return {"mode": "summary", "summary": official_rows(summary_from_table(es, "Resumen estadístico", BARCELONA_EMELEC, BARCELONA_EMELEC.a), notes),
            "recent": [], "source": wiki("es", title), "notes": notes}


# ---------------------------------------------------------------- Portugal

PORTUGAL_COMPS = [("Championship of Lisbon", "Campeonato de Lisboa"), ("League matches", "Primeira Liga"), ("Cup matches", "Taça de Portugal"),
                  ("Portuguese Cup matches", "Taça de Portugal"), ("League Cup matches", "Taça da Liga"),
                  ("Super Cup matches", "Supertaça"), ("Campeonato de Portugal matches", "Campeonato de Portugal"),
                  ("Championship of Portugal matches", "Campeonato de Portugal")]


def head_to_head(body: str, a_name: str, b_name: str) -> dict | None:
    """The "Benfica wins || 61 / Draws || 51 / Porto wins || 73 / goals / Total matches" box of a section."""
    grid = next(iter(every_table(body)), None)
    if not grid:
        return None
    kv = {}
    for r in grid:
        if len(r) >= 2:
            kv[fold(W.plain(r[0]["text"])).strip()] = W.number(r[1]["text"])
    get = lambda key: next((v for k, v in kv.items() if k.startswith(key)), None)  # noqa: E731
    row = {"n": get("total matches"), "a": get(f"{fold(a_name)} wins"), "d": get("draws"), "b": get(f"{fold(b_name)} wins"),
           "ga": get(f"{fold(a_name)} goals"), "gb": get(f"{fold(b_name)} goals")}
    return row if None not in (row["n"], row["a"], row["d"], row["b"]) else None


def portugal_summary(title: str, a_name: str, b_name: str):
    def builder(refresh: bool) -> dict:
        en = page(title, refresh)
        comps = []
        for heading, label in PORTUGAL_COMPS:
            m = re.search(r"^==\s*" + re.escape(heading) + r"\s*==\s*$", en, re.M)
            if not m:
                continue
            row = head_to_head(section(section(en[m.start():], re.escape(heading)), "Head-to-head results"), a_name, b_name)
            if row and row["n"]:
                comps.append({"comp": label, **row})
        total = head_to_head(section(en, "All-time head-to-head results"), a_name, b_name)
        summed = {k: sum(r[k] or 0 for r in comps) for k in ("n", "a", "d", "b", "ga", "gb")}
        notes = ["Wikipedia lists these matches by season and round but without dates, so the page shows the totals only.",
                 "Includes the Campeonato de Portugal (1922–1938), the national knockout championship before the league"
                 + (", and the Lisbon championship (Campeonato de Lisboa)" if any(r["comp"] == "Campeonato de Lisboa" for r in comps) else "")
                 + "; reserve-team matches and friendlies are left out."]
        if total and summed["n"] != total["n"]:
            notes.append(f"The competition tables add up to {summed['n']} matches; the source's all-time total is {total['n']}.")
        return {"mode": "summary", "summary": {"comps": comps, "total": {"comp": "Total", **(total or summed)}},
                "recent": [], "source": wiki("en", title), "notes": notes}
    return builder


PORTUGAL_NAMES = {"Portuguese League": "Primeira Liga", "Portuguese Cup": "Taça de Portugal", "Portuguese League Cup": "Taça da Liga",
                  "Portuguese Super Cup": "Supertaça", "Championship of Portugal": "Campeonato de Portugal"}
PORTO_SPORTING = Pair("porto", ("porto",), "sporting-cp", ("sporting",))


def build_porto_sporting(refresh: bool) -> dict:
    title = "FC Porto–Sporting CP rivalry"
    en = page(title, refresh)
    notes = ["Wikipedia lists these matches by season and round but without dates, so the page shows the totals only.",
             "Includes the Campeonato de Portugal (1922–1938), the national knockout championship before the league; "
             "reserve-team matches and friendlies are left out."]
    summary = official_rows(summary_from_table(en, "All-time head-to-head results", PORTO_SPORTING, PORTO_SPORTING.a), notes)
    for r in summary["comps"]:
        r["comp"] = PORTUGAL_NAMES.get(r["comp"], r["comp"])
    return {"mode": "summary", "summary": summary, "recent": [], "source": wiki("en", title), "notes": notes}


BARCELONA_LDU = Pair("barcelona-sc", ("barcelona",), "ldu-quito", ("liga deportiva universitaria", "ldu", "liga de quito"))


def build_barcelona_ldu(refresh: bool) -> dict:
    title = "Rivalidad entre Barcelona Sporting Club y Liga Deportiva Universitaria"
    es = page(title, refresh, lang="es")
    notes = ["Wikipedia publishes this rivalry's totals but not every match, so there is no match-by-match history."]
    summary = official_rows(summary_from_table(es, "Balance de enfrentamientos", BARCELONA_LDU, BARCELONA_LDU.a), notes)
    summary["comps"] = [r for r in summary["comps"] if r["n"]]
    return {"mode": "summary", "summary": summary, "recent": [], "source": wiki("es", title), "notes": notes}
