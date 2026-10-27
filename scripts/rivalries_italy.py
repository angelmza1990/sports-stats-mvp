"""Italian rivalries between Inter, Milan and Juventus (English and Italian Wikipedia)."""

from __future__ import annotations

import html
import re
import sys
import time
import urllib.request

from rivalries_common import (ES_ROUNDS, ROOT, W, bold, en_team, find, football_season, footballboxes, goals_text, label_index,  # noqa: F401
                              page, parse_date, score_of, shootout)


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
