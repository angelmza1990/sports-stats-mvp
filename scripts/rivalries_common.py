"""Shared helpers for build_rivalries.py and its source modules: page fetching, dates, scores, football boxes,
knockout ties and the finishing touches every rivalry file gets."""

from __future__ import annotations

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
RAW = ROOT / "data" / "raw"
OUT_DIR = ROOT / "football" / "rivalries" / "data"
CLUBS = ROOT / "data" / "football" / "clubs.json"
COUNTRY_NAMES = {"ARG": ("Argentina", "ar"), "URU": ("Uruguay", "uy"), "ESP": ("Spain", "es"), "ITA": ("Italy", "it"), "ENG": ("England", "gb-eng"),
                 "BRA": ("Brazil", "br"), "FRA": ("France", "fr"), "GER": ("Germany", "de")}
TODAY = date.today().isoformat()

ES_MONTHS = {m: i + 1 for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split())}
ES_MONTHS["setiembre"] = 9
IT_MONTHS = {m: i + 1 for i, m in enumerate(
    "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split())}
PT_MONTHS = {m: i + 1 for i, m in enumerate(
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split())}
PT_MONTHS["marco"] = 3
EN_MONTHS = {m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())}
EN_MONTHS.update({m[:3]: i for m, i in list(EN_MONTHS.items())})
EN_MONTHS["sept"] = 9


def page(title: str, refresh: bool, lang: str = "en", _suffix: str = "") -> str:
    """A Wikipedia page's wikitext, cached under data/raw; redirects are followed."""
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-") + _suffix
    name = f"{slug}.wiki" if lang == "en" else f"{lang}-{slug}.wiki"
    text = W.fetch_raw(title, CACHE / name, refresh, pause=1.5, lang=lang)
    target = re.match(r"\s*#(?:redirect|redirección|redirecionamento|weiterleitung)\s*\[\[([^\]|#]+)", text, re.I)
    if not target:
        return text
    # A redirect that differs only in case ("Fútbol" -> "fútbol") would share this cache file: keep it apart.
    same = fold(target.group(1).strip()) == fold(title)
    return page(target.group(1).strip(), refresh, lang, _suffix + "-r" if same else "")


def fetch_url(url: str, cache: Path, refresh: bool, encoding: str = "utf-8") -> str:
    """Any other source (RSSSF, engsoccerdata), cached on disk; the saved copy stands in when it can't be fetched."""
    if refresh or not cache.exists():
        print(f"downloading {url}", file=sys.stderr)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": W.USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode(encoding, "replace")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(body, encoding="utf-8")
            time.sleep(1)
        except OSError as err:
            if not cache.exists():
                raise
            print(f"warning: could not download {url} ({err}); using the saved copy", file=sys.stderr)
    return cache.read_text(encoding="utf-8")


def iso(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def parse_date(text: str) -> str | None:
    """Spanish, Portuguese, Italian and English dates, dd/mm/yyyy, dd.mm.yyyy and dd-mm-yyyy."""
    t = W.plain(text).lower().replace("º", "").replace("°", "")
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m:
        return iso(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", t)
    if m:
        return iso(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.search(r"(\d{1,2})\s+(?:de\s+)?([a-zçéã]+)\.?\s+(?:de\s+)?(\d{4})", t)
    if m:
        mon = ES_MONTHS.get(m.group(2)) or PT_MONTHS.get(m.group(2)) or IT_MONTHS.get(m.group(2)) or EN_MONTHS.get(m.group(2))
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
    m = re.search(r"(\d+)\s*(?:[–\-−:]|\b[xX]\b|×)\s*(\d+)", t)
    return (int(m.group(1)), int(m.group(2))) if m else None


def shootout(text: str) -> tuple[int, int] | None:
    """A penalty shoot-out in a score cell: "(4-2p.)", "(4–2 p)", "4–3 on penalties", "(4–3 pen.)"."""
    raw = re.sub(r"<[^>]+>", " ", text)
    m = re.search(r"\((\d+)\)\s*\d+\s*[–\-−:]\s*\d+\s*\((\d+)\)", raw)  # "(3) 0:0 (5)"
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"\(?(\d+)\s*[–\-−x]\s*(\d+)\s*(?:\[\[[^\]]*\|)?\s*(?:p\b|p\.|pen|on pen|penalties|pên)", raw, re.I)
    return (int(m.group(1)), int(m.group(2))) if m else None


def goals_text(text: str) -> str:
    t = W.plain(re.sub(r"<br\s*/?>", ", ", text))
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


def football_season(d: str) -> str:
    """The European season (August to July) a date falls in: "2026-10-25" -> "2026–27"."""
    y, mo = int(d[:4]), int(d[5:7])
    start = y if mo >= 7 else y - 1
    return f"{start}–{str(start + 1)[2:]}"


def en_team(text: str, a: tuple[str, ...], b: tuple[str, ...], ida: str, idb: str) -> str | None:
    t = W.plain(text).lower()
    if any(x in t for x in a):
        return ida
    if any(x in t for x in b):
        return idb
    return None


class Pair:
    """The two clubs of a rivalry, recognised in free text by their aliases (lowercase, accents dropped)."""

    def __init__(self, a: str, a_names: tuple[str, ...], b: str, b_names: tuple[str, ...]):
        self.a, self.b = a, b
        self.names = [(a, a_names), (b, b_names)]

    def team(self, text: str) -> str | None:
        for t in (fold(W.plain(text)), fold(text)):  # the raw text too: names inside templates ({{abbr|GI|Ganador Independiente}})
            hits = [(t.find(n), cid) for cid, names in self.names for n in names if n in t]
            if hits:
                return min(hits)[1]
        return None

    def other(self, cid: str) -> str:
        return self.b if cid == self.a else self.a


def fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()


def footballboxes(text: str) -> list[dict]:
    """Every {{Football box}} on a page with its main fields: date, round, team1, team2, score, goals, stadium."""
    out = []
    for m in re.finditer(r"\{\{\s*(?:football ?box(?: collapsible)?|footballbox(?:_collapsible)?)\b", text, re.I):
        block = text[m.end():m.end() + 6000]
        nxt = re.search(r"\{\{\s*(?:football ?box|footballbox)", block, re.I)
        block = block[:nxt.start()] if nxt else block
        fields = {}
        for f in ("date", "round", "team1", "team2", "score", "result", "goals1", "goals2", "stadium", "location",
                  "aet", "penaltyscore", "penalties1", "penalties2", "score1", "score2", "aggregate"):
            fm = re.search(r"(?:^|\||\n)\s*" + f + r"\s*=\s*([^\n]*)", block)
            if fm:
                fields[f] = W.split_outside(fm.group(1), "|")[0] if f not in ("goals1", "goals2") else fm.group(1)
        d = fields.get("date", "")
        sd = re.search(r"\{\{\s*(?:start date|dts)\s*\|(?:df=y\|)?\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})", d, re.I)
        when = iso(int(sd.group(1)), int(sd.group(2)), int(sd.group(3))) if sd else parse_date(d)
        box = {k: v for k, v in fields.items()}
        box.update({"date": when, "team1": fields.get("team1", ""), "team2": fields.get("team2", ""),
                    "score": score_of(fields.get("score", "")), "raw": block})
        out.append(box)
    return out


ES_ROUNDS = {
    "treintaidosavos de final": "Round of 64", "dieciseisavos de final": "Round of 32", "octavos de final": "Round of 16",
    "cuartos de final": "Quarter-finals", "semifinal": "Semi-finals", "semifinales": "Semi-finals", "final": "Final",
    "primera fase": "First stage", "segunda fase": "Second stage", "fase campeón": "Championship stage",
    "fase de grupos": "Group stage", "desempate": "Play-off", "fase final": "Final stage",
}
EN_ROUND_PATTERNS = [(r"semi[- ]?finals?", "Semi-finals"), (r"quarter[- ]?finals?", "Quarter-finals"), (r"\bfinal\b", "Final"),
                     (r"round of 16|last 16|r16", "Round of 16"), (r"round of 32|last 32|r32", "Round of 32"),
                     (r"(\d)(?:st|nd|rd|th) round", None), (r"(first|second|third|fourth|fifth|sixth) round", None),
                     (r"play-?off", "Play-off"), (r"group|league phase|league stage", "Group stage")]
ORD = ["", "First", "Second", "Third", "Fourth", "Fifth", "Sixth"]


def en_round(text: str) -> str:
    lo = W.plain(text).lower()
    for pat, name in EN_ROUND_PATTERNS:
        mm = re.search(pat, lo)
        if mm:
            if name:
                return name
            g = mm.group(1)
            return f"{ORD[int(g)] if g.isdigit() else g.capitalize()} round"
    return ""


# ---------------------------------------------------------------- Knockout ties


def build_ties(data: dict, overrides: dict | None = None) -> list[dict]:
    """Group knockout matches into ties (two legs, replays) and work out who went through."""
    overrides = overrides or {}
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for m in data["matches"]:
        rnd = m.get("round") or ""
        if m["stage"] == "league" or not rnd:
            continue
        if re.search(r"group|final group|championship stage|first stage|second stage|final stage|quadrangular|triangular|turno|returno|hexagonal|octogonal", rnd, re.I):
            continue
        groups[(m["comp"], m["season"], rnd)].append(m)
    ties = []
    a, b = (t["id"] for t in data["teams"])
    for (comp, season, rnd), legs in groups.items():
        legs.sort(key=lambda m: m["n"])
        goals = {a: 0, b: 0}
        played = [x for x in legs if x.get("leg") != "replay"]
        for x in played:
            goals[x["home"]] += x["hs"]
            goals[x["away"]] += x["as"]
        last = legs[-1]
        how = ""
        winner = overrides.get((data["id"], comp, season, rnd))
        if winner:
            how = overrides.get((data["id"], comp, season, rnd, "how"), "")
        elif goals[a] != goals[b] and last.get("leg") != "replay":
            winner = a if goals[a] > goals[b] else b
        else:
            # Level: a replay, a shoot-out or (for two legs) away goals decide it.
            win_of = lambda x: x["home"] if x["hs"] > x["as"] else x["away"] if x["as"] > x["hs"] else None  # noqa: E731
            if last.get("pens"):
                p = last["pens"]
                winner = last["home"] if p[0] > p[1] else last["away"]
                how = f"penalties {max(p)}–{min(p)}"
            elif last.get("advanced"):
                winner, how = last["advanced"], last.get("advancedHow", "penalties")
            elif win_of(last) and last.get("leg") == "replay":
                winner, how = win_of(last), "replay"
            elif len(played) == 2 and data.get("awayGoals", True):
                away = {x["away"]: (x["as"]) for x in played}
                if away.get(a, 0) != away.get(b, 0):
                    winner, how = (a if away.get(a, 0) > away.get(b, 0) else b), "away goals"
        if not winner and re.search(r"shield|charity", comp, re.I) and len(legs) == 1:
            winner, how = "shared", "shared"  # drawn Charity Shields were shared until 1993
        if not winner:
            print(f"warning: undecided tie {data['id']} {comp} {season} {rnd}", file=sys.stderr)
            continue
        ties.append({"comp": comp, "season": season, "round": rnd, "matches": [x["n"] for x in legs],
                     "winner": winner, "how": how, "final": rnd == "Final", "intl": legs[0]["stage"] == "intl",
                     "agg": [goals[a], goals[b]] if len(played) > 1 else None})
    ties.sort(key=lambda t: t["matches"][0])
    return ties


# ---------------------------------------------------------------- Output


def record(data: dict, matches: list[dict] | None = None) -> dict:
    a, b = (t["id"] for t in data["teams"])
    ms = data["matches"] if matches is None else matches
    wa = sum(1 for m in ms if (m["hs"] > m["as"] and m["home"] == a) or (m["as"] > m["hs"] and m["away"] == a))
    wb = sum(1 for m in ms if (m["hs"] > m["as"] and m["home"] == b) or (m["as"] > m["hs"] and m["away"] == b))
    ga = sum(m["hs"] if m["home"] == a else m["as"] for m in ms)
    gb = sum(m["hs"] if m["home"] == b else m["as"] for m in ms)
    return {"n": len(ms), "a": wa, "d": len(ms) - wa - wb, "b": wb, "ga": ga, "gb": gb}


def finish(data: dict) -> None:
    """Sort chronologically, number the matches and stamp the build."""
    for key in ("matches", "friendlies"):
        data[key].sort(key=lambda m: (m["date"] or "9999", m.get("_order", 0), m.get("leg") == "replay"))
        for i, m in enumerate(data[key], 1):
            m["n"] = i
    for key in ("matches", "friendlies", "recent"):
        for m in data.get(key, []):
            m.setdefault("season", m["date"][:4])
            for k in [k for k in m if k.startswith("_")]:
                m.pop(k)
            for k in ("round", "leg", "goalsHome", "goalsAway", "venue"):
                if k in m and not m[k]:
                    m.pop(k)
    clubs = {c["id"]: c for c in json.loads(CLUBS.read_text(encoding="utf-8"))["clubs"]}
    data["clubs"] = {t["id"]: {"name": t["name"], "country": data["country"], "crest": clubs[t["id"]]["espn"]} for t in data["teams"]}
    data["countries"] = {data["country"]: {"name": COUNTRY_NAMES[data["country"]][0], "flag": COUNTRY_NAMES[data["country"]][1]}}
    data["updated"] = TODAY
    if data["matches"]:
        data["dataThrough"] = data["matches"][-1]["date"]
    elif data.get("recent"):
        data["dataThrough"] = max(m["date"] for m in data["recent"])


def summary(data: dict) -> None:
    if data.get("mode") == "summary":
        t = data["summary"]["total"]
        print(f"{data['name']}: summary only, {t['n']} official ({t['a']}-{t['d']}-{t['b']}; goals {t['ga']}-{t['gb']})", file=sys.stderr)
        return
    r = record(data)
    a, b = (t["id"] for t in data["teams"])
    by = Counter(m["comp"] for m in data["matches"])
    print(f"{data['name']}: {r['n']} official ({a} {r['a']}, draws {r['d']}, {b} {r['b']}; goals {r['ga']}-{r['gb']}), "
          f"{len(data['friendlies'])} friendlies, {len(data['ties'])} ties, through {data.get('dataThrough')}", file=sys.stderr)
    print("  " + ", ".join(f"{k} {v}" for k, v in by.most_common()), file=sys.stderr)


def box_goals(text: str) -> str:
    """Scorers from a football box: "[[Georges Bereta|Bereta]] {{goal|54}}<br>[[François M'Pelé|M'Pelé]] {{goal|60|pen.|70}}"
    -> "Bereta (54), M'Pelé (60 pen, 70)"."""
    out = []
    for part in re.split(r"<br\s*/?>|\n|\*", text or ""):
        mins = []
        for tpl in re.findall(r"\{\{\s*(?:goal|gol|og|o\.g\.|own goal|pen\.?)\s*\|([^}]*)\}\}", part, re.I):
            for arg in tpl.split("|"):
                arg = arg.strip()
                if re.fullmatch(r"\d+(?:\+\d+)?'?", arg):
                    mins.append(arg.rstrip("'"))
                elif mins and re.match(r"pen|p\b", arg, re.I):
                    mins[-1] += " pen"
                elif mins and re.match(r"o\.?g|og", arg, re.I):
                    mins[-1] += " o.g."
        if re.search(r"\{\{\s*(?:og|o\.g\.|own goal)\b", part, re.I) and mins and "o.g." not in mins[-1]:
            mins = [m + " o.g." for m in mins]
        name = W.plain(re.sub(r"\{\{.*?\}\}", "", part)).strip(" ,;")
        if name:
            out.append(f"{name} ({', '.join(mins)})" if mins else name)
    return ", ".join(out)


# ---------------------------------------------------------------- Leaders counted from the match list


def scorer_entries(text: str, goals: int) -> list[tuple[str, int]]:
    """ "Lamas (10), B. Ferreyra (20, 82), Paredes (x2), Brown (2)" -> [(name, goals)], own goals left out.
    A lone number in brackets is a minute unless counting it as goals is what makes the side's total add up."""
    parts = re.split(r",\s*(?![^()]*\))", text or "")
    raw = []
    for p in parts:
        p = p.strip()
        m = re.match(r"^(.*?)\s*(?:\((.*)\))?\s*$", p)
        name, inside = m.group(1).strip(" .;"), (m.group(2) or "").strip()
        if not name or re.search(r"\bo\.?g\.?\b|own goal|e\.c\.|en contra", p, re.I):
            continue
        name = re.sub(r"\s*\b(?:pen|p|pk)\.?$", "", name).strip()
        times = re.match(r"^x\s*(\d+)$", inside, re.I)
        mins = [x for x in re.split(r"\s*,\s*", inside) if x and not re.search(r"o\.?g", x, re.I)] if inside else []
        raw.append((name, int(times.group(1)) if times else max(1, len(mins)), inside if re.fullmatch(r"\d", inside) else None))
    total = sum(n for _, n, _ in raw)
    if total < goals:
        as_counts = sum(int(single) if single else n for _, n, single in raw)
        if as_counts == goals:
            return [(name, int(single) if single else n) for name, n, single in raw]
    return [(name, n) for name, n, _ in raw]


def leaders_from_matches(data: dict, minimum: float = 0.97) -> list[dict] | None:
    """Top scorers counted from the scorers listed for each match, when nearly every match with goals has them.
    "Ferreyra" joins "B. Ferreyra" when he is the only player of that club with the surname."""
    ms = [m for m in data["matches"] if m["hs"] + m["as"] > 0]
    covered = [m for m in ms if (m["hs"] == 0 or m.get("goalsHome")) and (m["as"] == 0 or m.get("goalsAway"))]
    if not ms or len(covered) / len(ms) < minimum:
        return None
    tally: dict[tuple[str, str], int] = Counter()
    for m in covered:
        for side, team, n in (("goalsHome", m["home"], m["hs"]), ("goalsAway", m["away"], m["as"])):
            for name, g in scorer_entries(m.get(side, ""), n):
                tally[(team, name)] += g
    surname = lambda n: fold(n.split(". ")[-1] if ". " in n else n)  # noqa: E731
    merged: dict[tuple[str, str], int] = Counter()
    for (team, name), g in tally.items():
        if ". " not in name:
            full = [k for k in tally if k[0] == team and ". " in k[1] and surname(k[1]) == fold(name)]
            if len(full) == 1:
                merged[full[0]] += g
                continue
        merged[(team, name)] += g
    out = [{"name": name, "team": team, "goals": g} for (team, name), g in merged.items()]
    out.sort(key=lambda o: (-o["goals"], o["name"]))
    data["notes"].append(f"The top scorers are counted from the scorers listed for each match ({len(covered)} of the {len(ms)} "
                         "matches with goals have them), so they may differ slightly from other sources.")
    return out[:15]
