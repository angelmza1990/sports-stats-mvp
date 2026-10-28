"""Brazilian rivalries: São Paulo's and Rio de Janeiro's big four, the Grenal and the Clássico Mineiro.

Portuguese Wikipedia lists every match of seven of them, each article in its own table layout; English Wikipedia
lists every Clássico Mineiro. The rest keep the head-to-head totals the articles publish.
"""

from __future__ import annotations

import re
import sys

from rivalries_common import W, Pair, bold, fold, footballboxes, label_index, page, parse_date, score_of, shootout

PALMEIRAS, SAO_PAULO, CORINTHIANS, SANTOS = "palmeiras", "sao-paulo", "corinthians", "santos"
FLAMENGO, FLUMINENSE, VASCO, BOTAFOGO = "flamengo", "fluminense", "vasco-da-gama", "botafogo"
INTERNACIONAL, GREMIO, CRUZEIRO, ATLETICO = "internacional", "gremio", "cruzeiro", "atletico-mineiro"
ALIASES = {
    PALMEIRAS: ("palmeiras", "palestra"), SAO_PAULO: ("sao paulo", "spfc"), CORINTHIANS: ("corinthians", "corinthains"),
    SANTOS: ("santos",), FLAMENGO: ("flamengo",), FLUMINENSE: ("fluminense",), VASCO: ("vasco",), BOTAFOGO: ("botafogo",),
    INTERNACIONAL: ("internacional", "inter"), GREMIO: ("gremio",), CRUZEIRO: ("cruzeiro", "palestra"),
    ATLETICO: ("atletico", "galo"),
}
GROUNDS = {
    PALMEIRAS: ("palestra italia", "parque antarctica", "allianz", "nubank parque", "jardim america"),
    SAO_PAULO: ("morumbi", "morumbis", "canindé", "caninde", "chacara da floresta"),
    CORINTHIANS: ("parque sao jorge", "fazendinha", "alfredo schurig", "itaquerao", "neo quimica", "arena corinthians", "ponte grande"),
    SANTOS: ("vila belmiro", "urbano caldeira"),
    FLAMENGO: ("gavea", "rua paysandu", "jose bastos padilha"),
    FLUMINENSE: ("laranjeiras", "rua guanabara", "manoel schwartz"),
    VASCO: ("sao januario", "figueira de melo", "moraes e silva"),
    BOTAFOGO: ("general severiano", "nilton santos", "engenhao", "caio martins", "marechal hermes"),
    INTERNACIONAL: ("beira-rio", "beira rio", "eucaliptos"), GREMIO: ("olimpico", "arena do gremio", "baixada"),
    CRUZEIRO: ("barro preto",), ATLETICO: ("lourdes", "arena mrv", "antonio carlos"),
}


def section(text: str, heading: str) -> str:
    m = re.search(r"^(=+)\s*" + heading + r"\s*(?:<ref.*?(?:/>|</ref>))?\s*=+\s*$", text, re.M)  # a heading may end in a reference
    if not m:
        return ""
    rest = text[m.end():]
    end = re.search(r"^={1," + str(len(m.group(1))) + r"}[^=]", rest, re.M)
    return rest[:end.start()] if end else rest


def pt_rows(text: str, pair: Pair) -> list[dict]:
    """Every row of a match list, whatever its layout, as {date, home, away, hs, as, comp, venue, counted}."""
    out = []
    for grid in W.all_tables("\n" + text):
        head = next((r for r in grid if any(re.search(r"mandante|data|placar", W.plain(c["text"]), re.I) for c in r)), None)
        labels = label_index(head) if head else {}
        col = lambda *names: next((i for lab, i in labels.items() for n in names if lab.startswith(n)), None)  # noqa: E731
        i_num, i_date, i_home, i_score, i_away = col("nº", "#"), col("data"), col("mandante"), col("placar"), col("visitante")
        i_comp, i_venue = col("competição", "torneio", "campeonato"), col("estádio")
        # Derby Paulista: one column per club and an "x" between them; Clássico Alvinegro: "Corinthians 0 x 1 Santos".
        team_cols = [i for lab, i in labels.items() if pair.team(lab) and i not in (i_home, i_away)]
        i_x = labels.get("x")
        for r in grid:
            if r is head or len(r) < 3 or all(c["header"] for c in r) and len(r) < 5:
                continue
            texts = [c["text"] for c in r]
            get = lambda i: texts[i] if i is not None and i < len(texts) else ""  # noqa: E731
            d = parse_date(get(i_date)) if i_date is not None else next((parse_date(t) for t in texts if parse_date(t)), None)
            if not d:
                continue
            m = None
            if i_home is not None and i_score is not None and i_away is not None:
                home, away, sc = pair.team(get(i_home)), pair.team(get(i_away)), score_of(get(i_score))
                if home and away and sc and home != away:
                    m = {"home": home, "away": away, "hs": sc[0], "as": sc[1], "_raw": get(i_score) + get(i_home) + get(i_away)}
            elif i_x is not None and len(team_cols) >= 2:
                a, b = pair.team(next(lab for lab, i in labels.items() if i == team_cols[0])), pair.team(next(lab for lab, i in labels.items() if i == team_cols[1]))
                ga, gb = W.number(get(team_cols[0])), W.number(get(team_cols[1]))
                if ga is not None and gb is not None:
                    m = {"home": a, "away": b, "hs": ga, "as": gb, "_raw": get(i_x), "_homeUnknown": True}
            else:
                for t in texts:
                    mm = re.match(r"^\s*(.+?)\s+(\d+)\s*[xX×–-]\s*(\d+)\s+(.+?)\s*$", W.plain(t))
                    if mm and pair.team(mm.group(1)) and pair.team(mm.group(4)) and pair.team(mm.group(1)) != pair.team(mm.group(4)):
                        m = {"home": pair.team(mm.group(1)), "away": pair.team(mm.group(4)), "hs": int(mm.group(2)), "as": int(mm.group(3)), "_raw": t}
                        break
            if not m:
                continue
            comp = W.plain(get(i_comp)) if i_comp is not None else ""
            venue = W.plain(re.sub(r"\{\{\s*(?:nota de rodapé|nota)\b.*?\}\}", "", get(i_venue), flags=re.I | re.S)) if i_venue is not None else ""
            if i_comp is None or i_venue is None:
                # Layouts without headers: the competition is the last text cell, the venue the one after the match.
                rest = [W.plain(t) for t in texts if not parse_date(t) and not re.search(r"\d+\s*[xX×–-]\s*\d+", W.plain(t)) and W.plain(t)]
                rest = [t for t in rest if not pair.team(t) or len(t) > 25]
                comp = comp or (rest[-1] if rest else "")
                venue = venue or (rest[0] if len(rest) > 1 else "")
            num = W.plain(get(i_num)) if i_num is not None else "1"
            m.update({"date": d, "comp": comp, "venue": venue,
                      "counted": not (i_num is not None and not re.search(r"\d", num))})
            if m.pop("_homeUnknown", False):
                v = fold(venue)
                if any(g in v for g in GROUNDS[m["away"]]):
                    m["home"], m["away"], m["hs"], m["as"] = m["away"], m["home"], m["as"], m["hs"]
            pens = shootout(m["_raw"])
            if pens:
                m["pens"] = list(pens)
            out.append(m)
    return out


# ---------------------------------------------------------------- Competitions

# Official competitions: (pattern, name, stage). Anything else between the first teams is a friendly; reserve,
# amateur and youth games are left out.
BR_COMPS = [
    (r"aspirantes|amadores|juvenis|times mistos|jogo-treino", None, None),
    (r"supercopa do brasil", "Supercopa do Brasil", "super"),
    (r"sul-brasileiro", "Campeonato Sul-Brasileiro", "regional"),
    (r"brasileir|brasieiro|brasieliro|copa uni[aã]o|jo[aã]o havelange|roberto gomes pedrosa|ta[cç]a de prata|robert[aã]o|s[ée]rie a\b",
     "Campeonato Brasileiro", "league"),
    (r"s[ée]rie b", "Campeonato Brasileiro Série B", "league"),
    (r"ta[cç]a brasil\b", "Taça Brasil", "cup"), (r"copa do brasil", "Copa do Brasil", "cup"),
    (r"seletiva", "Seletiva da Libertadores", "cup"),
    (r"supercopa (?:da )?(?:sul|sud|libertadores)", "Supercopa Libertadores", "intl"), (r"libertadores", "Copa Libertadores", "intl"),
    (r"recopa", "Recopa Sudamericana", "intl"), (r"sul-americana|sudamericana", "Copa Sudamericana", "intl"),
    (r"rio[- ]?s[aã]o paulo", "Torneio Rio–São Paulo", "regional"), (r"sul[- ]minas|copa sul\b(?!-)", "Copa Sul-Minas", "regional"),
    (r"primeira liga", "Primeira Liga", "regional"),
    (r"mercosul|mercosur", "Copa Mercosur", "intl"), (r"copa conmebol", "Copa Conmebol", "intl"),
    (r"campeonato paulista|paulista extra|paulist[aã]o|^paulista", "Campeonato Paulista", "state"),
    (r"campeonato carioca|ta[cç]a guanabara|ta[cç]a rio\b|^carioca|campeonato da capital|copa rio\b", "Campeonato Carioca", "state"),
    (r"torneio municipal|torneio extra|torneio rel[aâ]mpago|torneio aberto", "Other state tournaments", "state"),
    (r"ga[uú]cho|gauch[aã]o", "Campeonato Gaúcho", "state"), (r"citadino", "Campeonato Citadino", "state"),
    (r"campeonato mineiro|mineiro\b", "Campeonato Mineiro", "state"),
]


def classify(comp: str) -> tuple[str | None, str | None]:
    """(official name, stage) for a competition, ("<as given>", "friendly") for anything else, (None, None) to drop."""
    c = W.plain(comp)
    if re.search(r"torneio in[ií]cio", c, re.I):
        return c, "friendly"  # short matches of a one-day knockout tournament
    for pat, name, stage in BR_COMPS:
        if re.search(pat, c, re.I):
            return name, stage
    return (c or "Friendly"), "friendly"


ROUNDS_PT = [(r"final", "Final"), (r"semi", "Semi-finals"), (r"quartas", "Quarter-finals"), (r"oitavas", "Round of 16"),
             (r"primeira fase|fase classificat|primeira etapa|1\.ª fase", "First round"), (r"segunda fase", "Second round"),
             (r"terceira fase", "Third round"), (r"desempate|jogo[- ]extra|melhor de tr[eê]s", "Play-off")]


def pt_round(text: str) -> str:
    t = fold(W.plain(text))
    if re.search(r"semi", t):
        return "Semi-finals"
    for pat, name in ROUNDS_PT:
        if re.search(fold(pat), t):
            return name
    return "Knockout round"


# ---------------------------------------------------------------- Knockout ties and finals


def tie(pair: Pair, comp_text: str, year: str, rnd: str, winner: str | None, final: bool = False) -> dict | None:
    comp, stage = classify(comp_text)
    if not winner or not comp or stage == "friendly" or not year:
        return None
    return {"comp": comp, "season": year, "round": "Final" if final else rnd, "winner": winner, "how": "",
            "final": final or rnd == "Final", "intl": stage == "intl", "legs": [], "matches": []}


def text_ties(text: str, pair: Pair) -> list[dict]:
    """Ties from the free-text lists: "Copa do Brasil de 2015: Vasco elimina o Flamengo nas oitavas", "1998 – Palmeiras
    elimina o Santos na semifinal da Copa do Brasil", "; Flamengo campeão, Vasco vice / : Taça Rio de 2011."."""
    out = []
    text = re.sub(r"<ref[^>]*/>|<ref.*?</ref>|\{\{nota de rodapé.*?\}\}", "", text, flags=re.S | re.I)
    unofficial = False
    champion = None
    for line in text.split("\n"):
        s = line.strip()
        if re.match(r"^;", s):
            unofficial = bool(re.search(r"n[aã]o[- ]oficia|amistos", s, re.I))
            mm = re.match(r";\s*'*(.+?)'*\s+campe[aã]o,\s*(.+?)\s+vice", W.plain(s))
            champion = pair.team(mm.group(1)) if mm else None
            continue
        if unofficial or not s:
            continue
        plain = W.plain(s.lstrip("*:# "))
        mm = re.match(r"^(.+?)\s+de\s+(\d{4})\.?\s*$", plain)
        if champion and mm and s.startswith(":"):
            t = tie(pair, mm.group(1), mm.group(2), "Final", champion, final=True)
            if t:
                out.append(t)
            continue
        mm = re.search(r"(?:^|\s)(?:o\s+|a\s+)?(\S.*?)\s+(?:elimina|eliminou|derrota|derrotou|supera|superou)\s+(?:o\s+|a\s+)?(\S+(?:\s\S+)?)\s+(na|nas|no|nos)\s+(.+)$", plain, re.I)
        if mm and pair.team(mm.group(1)) and pair.team(mm.group(2)):
            winner = pair.team(mm.group(1))
            rest = mm.group(4)
            year = re.search(r"(1[89]\d{2}|20\d{2})", plain)
            comp_m = re.search(r"\b(?:do|da|de)\s+((?:Campeonato|Copa|Ta[cç]a|Torneio|Supercopa|Rio|Paulist|Brasileir|Libertadores|Recopa)[^.;,]*)", rest, re.I)
            head = re.match(r"^(.+?)\s+de\s+\d{4}\s*[:–-]", plain)
            comp = comp_m.group(1) if comp_m else (head.group(1) if head else "")
            t = tie(pair, comp, year.group(1) if year else "", pt_round(rest), winner, final=bool(re.search(r"\bfinal\b", rest, re.I) and not re.search(r"semi|quartas|oitavas", rest, re.I)))
            if t:
                out.append(t)
    return out


def years_ties(text: str, pair: Pair, state: str = "") -> list[dict]:
    """Finals listed as years: "O '''Cruzeiro''' superou o Atlético na final do estadual em 15 oportunidades: em 1940, 1967..."
    or "Flamengo campeão em oito ocasiões: 1963, 1972..."."""
    out = []
    comp = ""
    for line in text.split("\n"):
        s = line.strip()
        head = re.match(r"^'''\s*\[\[([^\]|]+)(?:\|([^\]]+))?\]\]\s*'''$", s) or re.match(r"^'''([^']+)'''$", s)
        if head:
            comp = head.group(2) or head.group(1) if head.lastindex and head.lastindex >= 2 else head.group(1)
            continue
        plain = W.plain(s.lstrip("*:# "))
        mm = re.match(r"^(?:o\s+|a\s+)?'*(\S+(?:\s\S+)?)'*\s+(?:campe[aã]o em|superou .*? na final .*? em|venceu .*? na final .*? em)\s+(.*)$", plain, re.I)
        if mm and pair.team(mm.group(1)):
            years = re.findall(r"\b(1[89]\d{2}|20\d{2})\b", mm.group(2).split(".")[0])
            where = comp or (state if "estadua" in (plain + text).lower() else "")
            if "estadua" in plain.lower():
                where = state
            for y in years:
                t = tie(pair, where, y, "Final", pair.team(mm.group(1)), final=True)
                if t:
                    out.append(t)
    return out


def table_ties(text: str, pair: Pair) -> list[dict]:
    """Tables of decisions: (Ano, Competição, Fase, Quem levou) or (Season, Competition, Date, Match, Score, Winner)."""
    out = []
    for grid in W.all_tables("\n" + text):
        labels = label_index(grid[0])
        i_year = next((i for lab, i in labels.items() if lab.startswith(("ano", "season"))), None)
        i_comp = next((i for lab, i in labels.items() if lab.startswith(("competi", "torneio"))), None)
        i_round = next((i for lab, i in labels.items() if lab.startswith(("fase", "round"))), None)
        i_win = next((i for lab, i in labels.items() if lab.startswith(("quem", "winner", "vencedor", "campe"))), None)
        if None in (i_year, i_comp, i_win):
            continue
        seen = set()
        for r in grid[1:]:
            if len(r) <= max(i_year, i_comp, i_win) or id(r[i_win]) in seen:
                continue
            seen.add(id(r[i_win]))
            year = re.search(r"(1[89]\d{2}|20\d{2})", W.plain(r[i_year]["text"]))
            rnd = pt_round(r[i_round]["text"]) if i_round is not None else "Final"
            t = tie(pair, r[i_comp]["text"], year.group(1) if year else "", rnd, pair.team(r[i_win]["text"]), final=rnd == "Final")
            if t:
                out.append(t)
    return out


def defeat_lists(text: str, pair: Pair) -> list[dict]:
    """The Choque-Rei layout: "Veja a relação de derrotas do Palmeiras para o São Paulo" and '''1977 Semifinal do Paulistão'''."""
    out = []
    winner = None
    for line in text.split("\n"):
        s = line.strip()
        mm = re.search(r"derrotas d[oa] (.+?) para o (.+?) em", s)
        if mm:
            winner = pair.team(mm.group(2))
            continue
        mm = re.match(r"^'''(\d{4})\s+(.+?)'''$", s)
        if mm and winner:
            rest = mm.group(2)
            comp = re.sub(r"^.*?\b(?:do|da|de)\s+", "", rest)
            t = tie(pair, comp, mm.group(1), pt_round(rest), winner, final=pt_round(rest) == "Final")
            if t:
                out.append(t)
    return out


def final_bullets(text: str, pair: Pair) -> list[dict]:
    """Final lists with dated results: "* 3 de maio de 2009 Corinthians 1x1 Santos - '''Corinthians campeão''' ", under a
    competition heading ("'''[[Copa Libertadores da América]]'''", "TAÇA SÃO PAULO (1962)", "; Campeonato Paulista")."""
    out = []
    comp = ""
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            continue
        if not s.startswith("*"):
            if re.match(r"^(;|''')", s) or (s.isupper() and len(s) < 90) or re.match(r"^\[\[[^\]]+\]\]\s*$", s):
                comp = re.sub(r"\(.*?\)", "", W.plain(s.lstrip(";"))).strip(" -")
            continue
        plain = W.plain(s.lstrip("* "))
        mm = re.search(r"'*\s*(?:-|–)?\s*'*\s*(\S+(?:\s\S+)?)'*\s+campe[aã]o(?:\s+de\s+(\d{4}))?", re.sub(r"'''", "", plain), re.I)
        d = parse_date(plain) or parse_date(s)
        if mm and pair.team(mm.group(1)):
            year = mm.group(2) or (d[:4] if d else None)
            t = tie(pair, comp or plain, year or "", "Final", pair.team(mm.group(1)), final=True)
            if t:
                out.append(t)
    return out


def ties_from(text: str, pair: Pair, sections: list[str], state: str = "") -> list[dict]:
    found: list[dict] = []
    for h in sections:
        body = section(text, h)
        if not body:
            continue
        for fn in (table_ties, defeat_lists, text_ties, years_ties, final_bullets):
            for t in (fn(body, pair, state) if fn is years_ties else fn(body, pair)):
                if not any(x["comp"] == t["comp"] and x["season"] == t["season"] and x["round"] == t["round"] for x in found):
                    found.append(t)
    found.sort(key=lambda t: (t["season"], t["comp"]))
    return found


# ---------------------------------------------------------------- Players


def leaders(text: str, pair: Pair) -> list[dict]:
    """Top scorers from a table (Player, Club, Goals) or from the article's sentences."""
    text = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", "", text, flags=re.S)
    out: list[dict] = []
    for grid in W.all_tables("\n" + text):
        labels = label_index(grid[0])
        i_name = next((i for lab, i in labels.items() if lab.startswith(("player", "jogador", "nome"))), None)
        i_club = next((i for lab, i in labels.items() if lab.startswith(("club", "clube", "time"))), None)
        i_goals = next((i for lab, i in labels.items() if lab.startswith(("goals", "gols"))), None)
        if None in (i_name, i_goals):
            continue
        for r in grid[1:]:
            if len(r) <= max(i_name, i_goals):
                continue
            name, goals = W.person(r[i_name]["text"]), W.number(r[i_goals]["text"])
            team = pair.team(r[i_club]["text"]) if i_club is not None else None
            if name and goals and team:
                out.append({"name": re.sub(r"^:?pt:", "", name), "team": team, "goals": goals})
    if out:
        return sorted(out, key=lambda o: -o["goals"])
    for para in re.split(r"\n\s*\n|(?<=\.)\s+(?=[A-Z\[])", text):
        if re.search(r"s[ée]culo|decis|m[ée]dia|aspirantes", para, re.I):
            continue
        # "[[Pelé]] (Santos): 50 gols"; "Cláudio, Neco e [[Teleco]] (Corinthians): 21 gols"
        for mm in re.finditer(r"([^\n:]+?)\s*\(([^)]+)\):\s*(\d+)\s+gols", para):
            team = pair.team(mm.group(2))
            for name in re.split(r",\s*|\s+e\s+", W.plain(mm.group(1))):
                if team and name.strip():
                    out.append({"name": name.strip(), "team": team, "goals": int(mm.group(3))})
        # "Maior Artilheiro do Vasco: [[Roberto Dinamite]], 25 gols"; "Artilheiro do Flamengo''' ||[[Zico]] (19 gols)"
        for mm in re.finditer(r"[Aa]rtilheiro d[oa] ([^:|']+?)['\s]*(?::|\|\|)\s*(\[\[[^\]]+\]\])[,\s(]*(\d+) gols", para):
            team = pair.team(mm.group(1))
            if team:
                out.append({"name": W.plain(mm.group(2)), "team": team, "goals": int(mm.group(3))})
        # "* Santos: [[Pelé]] (32 gols)"
        for mm in re.finditer(r"^\*\s*([^:\n]+):\s*(\[\[[^\]]+\]\])\s*\((\d+)\s+gols\)", para, re.M):
            team = pair.team(mm.group(1))
            if team:
                out.append({"name": W.plain(mm.group(2)), "team": team, "goals": int(mm.group(3))})
        # "[[Heleno de Freitas]], pelo Botafogo, é o maior artilheiro deste clássico, com 22 gols"
        for mm in re.finditer(r"(\[\[[^\]]+\]\])[^.\[]*?pel[oa]\s+(\w+)[^.\[]*?com\s+(\d+)\s+(?:gols|tentos)", para):
            team = pair.team(mm.group(2))
            if team:
                out.append({"name": W.plain(mm.group(1)), "team": team, "goals": int(mm.group(3))})
    seen, uniq = set(), []
    for o in sorted(out, key=lambda o: -o["goals"]):
        if o["name"] not in seen:
            seen.add(o["name"])
            uniq.append(o)
    return uniq


# ---------------------------------------------------------------- Totals for the rivalries without a full list


def kv_totals(text: str, pair: Pair) -> dict | None:
    """ "Número de jogos || 367", "Vitórias do Corinthians || 135", "Empates || 117", "Gols marcados pelo X || 520"."""
    vals = {}
    for mm in re.finditer(r"'''([^']+)'''\s*\|\|\s*([\d.]+)", text):
        vals[W.plain(mm.group(1)).lower()] = int(mm.group(2).replace(".", ""))
    n = vals.get("número de jogos")
    if not n:
        return None
    wins = {pair.team(k): v for k, v in vals.items() if k.startswith("vitórias")}
    goals = {pair.team(k): v for k, v in vals.items() if k.startswith("gols marcados")}
    return {"comp": "All matches", "n": n, "a": wins.get(pair.a), "d": vals.get("empates"), "b": wins.get(pair.b),
            "ga": goals.get(pair.a), "gb": goals.get(pair.b)}


def prose_totals(text: str, pair: Pair) -> list[dict]:
    """ "Pelo [[Campeonato Carioca]], foram 224 partidas, sendo 96 vitórias do Vasco, 63 do Botafogo, e 65 empates.
    O Vasco fez 330 gols, e o Botafogo fez 274." """
    out = []
    text = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", "", text, flags=re.S)
    for para in text.split("\n"):
        plain = W.plain(para)
        mm = re.match(r"^Pel[oa]s?\s+(.+?),\s+foram (?:disputad[ao]s )?(\d+) (?:jogos|partidas)", plain)
        if not mm:
            continue
        comp, n = mm.group(1), int(mm.group(2))
        wins = {}
        for w in re.finditer(r"(\d+) (?:vit[oó]rias? )?d[oa] (\w+)", plain):
            t = pair.team(w.group(2))
            if t and t not in wins:
                wins[t] = int(w.group(1))
        d = re.search(r"(\d+) empates?", plain)
        draws = int(d.group(1)) if d else (n - sum(wins.values()) if wins else None)
        for t in (pair.a, pair.b):
            wins.setdefault(t, n - draws - sum(wins.values()) if draws is not None and len(wins) == 1 else 0)
        goals = {}
        for g in re.finditer(r"(?:O|o|e o|a)\s+(\w+)\s+(?:fez|marcou)\s+(\d+)", plain):
            if pair.team(g.group(1)):
                goals[pair.team(g.group(1))] = int(g.group(2))
        out.append({"comp": classify(comp)[0] or comp, "n": n, "a": wins[pair.a], "d": draws, "b": wins[pair.b],
                    "ga": goals.get(pair.a), "gb": goals.get(pair.b)})
    return out


def table_totals(text: str, pair: Pair) -> tuple[list[dict], dict | None]:
    """English Wikipedia's "Head to head results" table: Competition, Matches, wins, wins, draws (and goals)."""
    for grid in W.all_tables("\n" + text):
        head = [W.plain(c["text"]).lower() for c in grid[0]]
        if not head or not head[0].startswith("competition"):
            continue
        sub = grid[1] if len(grid) > 1 and all(c["header"] for c in grid[1]) else None
        rows, friendly = [], None
        if sub:  # Grenal: Wins split in a second header row (GRE, INT)
            order = [pair.team(c["text"]) or {"gre": "gremio", "int": "internacional"}.get(W.plain(c["text"]).lower()) for c in sub]
            body, idx = grid[2:], {"n": 1, "w1": 2, "w2": 3, "d": 4, "g1": None, "g2": None}
            first = order[0]
        else:  # Saudade: Games, Palmeiras wins, Draws, Santos wins, Palmeiras goals, Santos goals
            body, idx = grid[1:], {"n": 1, "w1": 2, "d": 3, "w2": 4, "g1": 5 if len(head) > 5 else None, "g2": 6 if len(head) > 6 else None}
            first = pair.team(grid[0][2]["text"])
        for r in body:
            if len(r) < 5:
                continue
            label = W.plain(r[0]["text"]).strip()
            num = lambda k: W.number(r[idx[k]]["text"]) if idx[k] is not None and idx[k] < len(r) else None  # noqa: E731
            row = {"comp": label, "n": num("n"), "a": num("w1"), "d": num("d"), "b": num("w2"), "ga": num("g1"), "gb": num("g2")}
            if first == pair.b:
                row["a"], row["b"], row["ga"], row["gb"] = row["b"], row["a"], row["gb"], row["ga"]
            if None in (row["n"], row["a"], row["b"], row["d"]):
                continue
            if re.search(r"friendl", label, re.I):
                friendly = row
            elif not re.search(r"^(all|total)", label, re.I):
                row["comp"] = classify(label)[0] or label
                rows.append(row)
        merged: dict[str, dict] = {}
        for row in rows:  # "Copa Sul" and "Copa Sul-Minas" are one competition
            if row["comp"] in merged:
                m = merged[row["comp"]]
                for k in ("n", "a", "d", "b", "ga", "gb"):
                    m[k] = None if m[k] is None or row[k] is None else m[k] + row[k]
            else:
                merged[row["comp"]] = dict(row)
        return list(merged.values()), friendly
    return [], None


def total_of(rows: list[dict]) -> dict:
    t = {"comp": "Total"}
    for k in ("n", "a", "d", "b", "ga", "gb"):
        vals = [r[k] for r in rows]
        t[k] = sum(vals) if all(v is not None for v in vals) else None
    return t


# ---------------------------------------------------------------- Builders

STATE_LEAGUE = {(PALMEIRAS, SAO_PAULO, CORINTHIANS, SANTOS): "Campeonato Paulista",
                (FLAMENGO, FLUMINENSE, VASCO, BOTAFOGO): "Campeonato Carioca",
                (INTERNACIONAL, GREMIO): "Campeonato Gaúcho", (CRUZEIRO, ATLETICO): "Campeonato Mineiro"}

BR_RIVALRIES = {
    "palmeiras-corinthians": {"pt": "Derby Paulista", "list": "Todos os clássicos disputados", "ties": ["Mata-matas"]},
    "palmeiras-sao-paulo": {"pt": "Choque-Rei", "list": "Lista de jogos", "ties": ["Confrontos eliminatórios", "Decisões de títulos"]},
    "santos-sao-paulo": {"pt": "San-São", "list": "Lista de jogos",
                         "ties": ["Demais confrontos eliminatórios", "Decisões de títulos", "Confrontos em competições internacionais"]},
    "corinthians-santos": {"pt": "Clássico Alvinegro", "list": "Lista de confrontos completa", "ties": ["Finais"], "leaders": "Artilheiros"},
    "flamengo-fluminense": {"pt": "Fla-Flu", "list": "Todos os confrontos", "ties": ["Decisões e taças"]},
    # The article names the top scorers in a sentence, not always with their club: "Heleno pelo Botafogo e Waldo pelo
    # Fluminense, ambos com 16 gols ... Fred, com 14, Welfare pelo Flu, com 13, e Dino, pelo Bota, com 11".
    "botafogo-fluminense": {"pt": "Clássico Vovô", "list": "Todos os confrontos", "leaders": "Goleadores",
                            "scorers": [("Heleno de Freitas", "botafogo", 16), ("Waldo", "fluminense", 16), ("Fred", "fluminense", 14),
                                        ("Welfare", "fluminense", 13), ("Dino da Costa", "botafogo", 11)],
                            "ties": ["Decisões em finais diretas", "Demais jogos eliminatórios"]},
    "fluminense-vasco": {"pt": "Clássico dos Gigantes", "list": "Todos os confrontos",
                         "ties": ["Decisões em finais diretas", "Demais jogos eliminatórios"]},
    "corinthians-sao-paulo": {"pt": "Majestoso", "totals": ("kv", "Estatísticas do clássico"), "ties": ["Decisões diretas de títulos"],
                              "recent": "Confrontos"},
    "palmeiras-santos": {"pt": "Clássico da Saudade", "en": "Clássico da Saudade", "totals": ("en", "Head to head results"),
                         "ties": ["Finais diretas", "Confrontos eliminatórios"], "leaders": "Principais artilheiros"},
    "flamengo-vasco": {"pt": "Clássico dos Milhões", "totals": ("kv", "Números totais"), "leaders": "Números totais",
                       "ties": ["Decisões em finais diretas", "Demais jogos eliminatórios"], "recent": "Últimos confrontos"},
    "botafogo-flamengo": {"pt": "Clássico da Rivalidade", "totals": ("prose", "Principais competições"), "leaders": "Artilheiros",
                          "ties": ["Decisões em finais diretas", "Demais jogos eliminatórios"], "recent": "Confrontos"},
    "botafogo-vasco": {"pt": "Clássico da Amizade", "totals": ("prose", "Principais competições"), "leaders": "Maiores artilheiros",
                       "ties": ["Decisões em finais diretas", "Demais jogos eliminatórios"], "recent": "Confrontos"},
    "internacional-gremio": {"en": "Grenal", "totals": ("en", "Head to head results"), "leaders": "All-time top scorers",
                             "ties": ["List of finals between the clubs"]},
    "cruzeiro-atletico": {"en": "Clássico Mineiro", "pt": "Clássico Mineiro", "boxes": "List of games (Cruzeiro version)",
                          "leaders": "All-time top scorers", "ties": ["Confrontos eliminatórios", "Decisões de títulos"]},
}


def to_match(row: dict) -> dict | None:
    comp, stage = classify(row["comp"])
    if not comp:
        return None
    m = {"date": row["date"], "comp": comp, "stage": stage, "home": row["home"], "away": row["away"], "hs": row["hs"], "as": row["as"],
         "venue": row.get("venue", "")}
    m["season"] = m["date"][:4]
    if stage != "friendly" and row["comp"] != comp:
        m["round"] = ""
    v = fold(m["venue"])
    m["neutral"] = bool(v) and not any(g in v for g in GROUNDS[m["home"]])
    if row.get("pens"):
        m["pens"] = row["pens"]
    return m


def brazil(key: str, a: str, b: str):
    cfg = BR_RIVALRIES[key]

    def builder(refresh: bool) -> dict:
        pair = Pair(a, ALIASES[a], b, ALIASES[b])
        pt = page(cfg["pt"], refresh, "pt") if cfg.get("pt") else ""
        en = page(cfg["en"], refresh) if cfg.get("en") else ""
        main_lang = "en" if cfg.get("en") and (cfg.get("boxes") or not cfg.get("pt")) else "pt"
        title = cfg[main_lang]
        labels = [f"{'Portuguese' if main_lang == 'pt' else 'English'} Wikipedia, {title}"]
        other = "pt" if main_lang == "en" else "en"
        if cfg.get(other):
            labels.append(f"{'Portuguese' if other == 'pt' else 'English'} Wikipedia, {cfg[other]}")
        source = {"label": "; ".join(labels), "url": f"https://{main_lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"}
        notes = []
        state = STATE_LEAGUE[next(k for k in STATE_LEAGUE if a in k)]
        ties = ties_from(pt or en, pair, cfg.get("ties", []), state) or ties_from(en, pair, cfg.get("ties", []), state)
        lead_src = en if cfg.get("en") and cfg.get("leaders") and section(en, cfg["leaders"]) else pt
        scorers = leaders(section(lead_src, cfg["leaders"]), pair) if cfg.get("leaders") else []
        if not scorers and cfg.get("scorers"):
            scorers = [{"name": n, "team": t, "goals": g} for n, t, g in cfg["scorers"]]
        data = {"source": source, "notes": notes, "ties": ties, "scorers": scorers, "tiesFromText": True, "awayGoals": False}
        if cfg.get("list"):
            rows = pt_rows(section(pt, cfg["list"]), pair)
            official, friendlies = [], []
            for r in rows:
                if not r["counted"]:
                    continue  # games the article itself doesn't count (training games, reserve sides)
                m = to_match(r)
                if m:
                    (friendlies if m["stage"] == "friendly" else official).append(m)
            data.update({"matches": official, "friendlies": friendlies})
            notes.append("Official matches are those of the state championships, the national league and cups, the Rio–São Paulo "
                         "tournament and CONMEBOL competitions; every other game between the first teams is listed as a friendly.")
        elif cfg.get("boxes"):
            boxes = footballboxes(section(en, re.escape(cfg["boxes"])))
            ms = []
            for x in boxes:
                home, away = pair.team(x["team1"]), pair.team(x["team2"])
                if x["date"] and x["score"] and home and away and home != away:
                    venue = W.plain(x.get("location", ""))
                    ms.append({"date": x["date"], "comp": "Clássico Mineiro", "stage": "all", "home": home, "away": away,
                               "hs": x["score"][0], "as": x["score"][1], "venue": venue,
                               "neutral": not any(g in fold(venue) for g in GROUNDS[home])})
            data.update({"matches": ms, "allMeetings": True})
            notes.append("The source lists every meeting (Cruzeiro's count) without its competition, so friendlies are included "
                         "and there is no split by competition or a separate friendlies tab.")
        else:
            kind, heading = cfg["totals"]
            body = section(en if kind == "en" else pt, heading)
            if kind == "en":
                rows, friendly = table_totals(body, pair)
                total = total_of(rows)
                if friendly:
                    data["friendlySummary"] = friendly
            elif kind == "prose":
                rows = prose_totals(body, pair)
                total = total_of(rows)
                notes.append("The totals cover the main competitions the article breaks down, not every official match.")
            else:
                total = kv_totals(body, pair)
                rows = []
                notes.append("The article publishes a single total for every meeting, friendlies included.")
            recent = []
            if cfg.get("recent"):
                for r in pt_rows(section(pt, cfg["recent"]), pair):
                    m = to_match(r)
                    if m and m["stage"] != "friendly":
                        recent.append(m)
            recent.sort(key=lambda m: m["date"])
            data.update({"mode": "summary", "summary": {"comps": rows, "total": total}, "recent": recent[-12:]})
            notes.insert(0, "Wikipedia publishes this rivalry's totals but not every match, so there is no match-by-match history.")
        if ties:
            notes.append("Knockout ties and finals come from the article's own lists, which name who went through but not every leg.")
        return data

    return builder
