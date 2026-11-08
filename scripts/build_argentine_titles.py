"""Build football/argentine-primera/data/international.json: every international title won by an Argentine club.

Two sources, both checked club by club against a totals table:

- CONMEBOL and FIFA competitions. The Copa Libertadores, the Copa Sudamericana and the world titles come from the
  datasets of those pages; the other CONMEBOL cups (Supercopa, Recopa, Copa CONMEBOL, Copa Mercosur, Copa de Oro,
  Copa Master de Supercopa, Copa Interamericana and the J.League Cup / Copa Sudamericana Championship) from the
  "by club" table of each English Wikipedia article. Checked against "List of CONMEBOL club competition winners".
- The Río de la Plata cups the AFA counts as official, played against the Uruguayan clubs from 1905 to 1946 (the
  second stage of the Cup Tie Competition, the Copa de Honor Cusenier, the Copa Aldao, the Copa Campeonato del Río de
  la Plata and the Copa Escobar-Gerona), from Spanish Wikipedia's "Campeonatos rioplatenses de fútbol". The first
  stage of the Cup Tie Competition (1900-1906) is a national cup on the Argentine page, so it isn't counted here;
  nor is San Lorenzo's 1941 Escobar-Gerona, whose second leg was never played, so the title was not awarded.

Usage:
    python3 scripts/build_argentine_titles.py            # cached pages
    python3 scripts/build_argentine_titles.py --refresh  # re-download them
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date

import wikitables as W
from build_football import RAW_DIR, ROOT, ClubIndex, club_from_cell, slug

OUT = ROOT / "football" / "argentine-primera" / "data" / "international.json"
FROM_DATA = [
    ("libertadores", "Copa Libertadores", "CL", "copa-libertadores"),
    ("sudamericana", "Copa Sudamericana", "CS", "copa-sudamericana"),
    ("intercontinental", "Intercontinental Cup and Club World Cup", "IC", "world-club-champions"),
]
FROM_PAGES = [
    ("supercopa", "Supercopa Libertadores", "SL", "Supercopa Libertadores"),
    ("recopa", "Recopa Sudamericana", "RS", "Recopa Sudamericana"),
    ("conmebol", "Copa CONMEBOL", "CC", "Copa CONMEBOL"),
    ("mercosur", "Copa Mercosur", "MS", "Copa Mercosur"),
    ("oro", "Copa de Oro", "CO", "Copa de Oro"),
    ("master", "Copa Master de Supercopa", "CMS", "Copa Master de Supercopa"),
    ("interamericana", "Copa Interamericana", "IA", "Copa Interamericana"),
    ("suruga", "J.League Cup / Copa Sudamericana Championship", "SB", "J.League Cup / Copa Sudamericana Championship"),
]
RIOPLATENSE_PAGE = "Campeonatos rioplatenses de fútbol"
# The editions tables on that page, in order, with the key and name of each cup.
RIOPLATENSE = [
    (r"==\s*Segunda etapa", "tie-cup", "Cup Tie Competition (Río de la Plata)"),
    (r"==\s*Copa de Honor Cusenier", "cusenier", "Copa de Honor Cusenier"),
    (r"==\s*Copa Aldao", "aldao", "Copa Aldao"),
    (r"==\s*Copa Campeonato del Río de la Plata", "rio-de-la-plata", "Copa Campeonato del Río de la Plata"),
    (r"==\s*Copa Confraternidad Escobar-Gerona", "escobar-gerona", "Copa Confraternidad Escobar-Gerona"),
]
ARG = re.compile(r"(?:bandera2?|flagicon|flag|fba)\s*\|\s*(?:ARG|Argentina)\b|\{\{\s*ARG\s*\}\}")
PRO_START = 1931  # the professional league began in 1931


def page(title: str, refresh: bool, lang: str = "en") -> str:
    prefix = "" if lang == "en" else f"{lang}-"
    return W.fetch_raw(title, RAW_DIR / f"{prefix}{slug(title)}.wiki", refresh, pause=3.0, lang=lang)


def by_club_table(text: str) -> list[list[dict]]:
    """The table of titles by club: a club (or team) column and the seasons (or years) won."""
    for grid in W.all_tables(text):
        labels = [W.plain(c["text"]).lower() for c in grid[0]]
        if any(l in ("club", "team") for l in labels) and any(re.match(r"(seasons|years) won", l) for l in labels):
            return grid
    raise LookupError("no titles-by-club table")


def build(refresh: bool) -> tuple[dict, list[str]]:
    clubs = ClubIndex()
    names: dict[str, dict] = {}
    titles = []
    errors = []

    for key, label, _, folder in FROM_DATA:
        data = json.loads((ROOT / "football" / folder / "data" / f"{folder}.json").read_text(encoding="utf-8"))
        for f in data["finals"]:
            if f["championCountry"] == "ARG":
                titles.append({"year": f["year"], "season": f["season"], "comp": key, "club": f["champion"]})
                names[f["champion"]] = {"name": data["clubs"][f["champion"]]["name"], "crest": data["clubs"][f["champion"]].get("crest")}

    for key, label, _, title in FROM_PAGES:
        grid = by_club_table(page(title, refresh))
        labels = [W.plain(c["text"]).lower() for c in grid[0]]
        club_i = next(i for i, l in enumerate(labels) if l in ("club", "team"))
        won_i = next(i for i, l in enumerate(labels) if re.match(r"(seasons|years) won", l))
        for row in grid[1:]:
            if len(row) <= won_i or not ARG.search(row[club_i]["text"]):
                continue
            cid = club_from_cell(row[club_i]["text"], clubs)
            for year in re.findall(r"\b(19[5-9]\d|20[0-4]\d)\b", W.plain(row[won_i]["text"])):
                titles.append({"year": int(year), "season": year, "comp": key, "club": cid})

    # The page's totals for the Argentine clubs, by competition.
    conmebol = page("List of CONMEBOL club competition winners", refresh)
    grid = W.table_with_headers(conmebol, "rank", "club", "country", "cl", "total")
    labels = [W.plain(c["text"]) for c in grid[0]]
    for row in grid[1:]:
        if len(row) < len(labels) or not ARG.search(row[2]["text"] + row[1]["text"]):
            continue
        cid = club_from_cell(row[1]["text"], clubs) if W.links(row[1]["text"]) else clubs.by_label(W.plain(row[1]["text"]), "ARG")
        for key, _, code, *_ in FROM_DATA + FROM_PAGES:
            want = W.number(row[labels.index(code)]["text"]) or 0
            got = sum(1 for t in titles if t["comp"] == key and t["club"] == cid)
            if got != want:
                errors.append(f"{W.plain(row[1]['text'])} {code}: {got} titles, the CONMEBOL list has {want}")

    # The Río de la Plata cups.
    # References hold citation templates whose pipes would split the table cells.
    text = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", page(RIOPLATENSE_PAGE, refresh, "es"), flags=re.S)
    rio = []
    for anchor, key, label in RIOPLATENSE:
        grid = W.parse_table(W.find_table(text, anchor, 0))
        for row in grid[1:]:
            if len(row) < 4:
                continue
            year = re.search(r"\b(19\d\d)\b", W.plain(row[0]["text"]))
            winner = row[1]["text"]
            # A final whose second leg was never played (1941) was not awarded.
            if year and ARG.search(winner) and not re.search(r"no se disputó la revancha", W.plain(row[2]["text"]), re.I):
                cid = club_from_cell(re.split(r"<br\s*/?>", winner)[0] if W.links(winner.split("<br")[0]) else winner, clubs)
                rio.append({"year": int(year.group(1)), "season": year.group(1), "comp": key, "club": cid})
    official = Counter()
    for row in W.table_with_headers(text, "club", "títulos", "ediciones ganadas")[1:]:
        if len(row) >= 2 and ARG.search(row[0]["text"]):
            official[club_from_cell(row[0]["text"], clubs)] += W.number(row[1]["text"]) or 0
    got = Counter(t["club"] for t in rio)
    for cid in set(got) | set(official):
        if got[cid] != official[cid]:
            errors.append(f"Río de la Plata cups, {cid}: {got[cid]} titles, the page's totals say {official[cid]}")
    titles += rio

    for t in titles:
        t["era"] = "professional" if t["year"] >= PRO_START else "amateur"
        if t["club"] not in names:
            c = clubs.clubs[t["club"]]
            names[t["club"]] = {"name": c["name"], "crest": c["espn"]}
    titles.sort(key=lambda t: (t["year"], t["comp"]))
    comps = [{"key": k, "label": l, "kind": "conmebol"} for k, l, *_ in FROM_DATA + FROM_PAGES]
    comps[2]["kind"] = "fifa"
    comps += [{"key": k, "label": l, "kind": "rioplatense"} for _, k, l in RIOPLATENSE]
    data = {
        "meta": {"generated": date.today().isoformat(), "proStart": PRO_START,
                 "sources": ["https://en.wikipedia.org/wiki/List_of_CONMEBOL_club_competition_winners",
                             f"https://es.wikipedia.org/wiki/{RIOPLATENSE_PAGE.replace(' ', '_')}"]},
        "competitions": comps,
        "clubs": names,
        "titles": titles,
    }
    return data, errors


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true")
    data, errors = build(ap.parse_args().refresh)
    if errors:
        print("validation failed:\n  " + "\n  ".join(errors), file=sys.stderr)
        sys.exit(1)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    by = Counter(data["clubs"][t["club"]]["name"] for t in data["titles"])
    print(f"wrote {OUT.relative_to(ROOT)}: {len(data['titles'])} titles; {by.most_common(8)}")


if __name__ == "__main__":
    main()
