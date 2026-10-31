"""Build the TC2000 dataset used by motorsport/tc2000: every champion of Argentina's touring-car
championship since 1979, titles by driver, make and team, and the all-time race wins and poles.

The top class was the Turismo Competición 2000 from 1979 to 2011, the Súper TC2000 from 2012 to 2021
and is again called TC2000 since 2022. Like the category's own statistics, the page counts the three
as one championship.

Sources:
- Spanish Wikipedia (CC BY-SA 4.0): "Turismo Competición 2000" (champions 1979-2011 and since 2022,
  titles by make) and "Súper TC2000" (champions, team and make champions 2012-2021).
- tc2000.com.ar, "Estadísticas históricas": champions since 1980 with their wins that season, and
  every driver's race wins and poles with the first and the last; "Estadísticas <year>": the current
  season's wins and poles.

Usage:
    python3 scripts/build_tc2000.py            # cached pages
    python3 scripts/build_tc2000.py --refresh  # re-download them
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.request
from collections import Counter
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wikitables as W  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WIKI_CACHE = ROOT / "data" / "raw" / "wikipedia" / "tc2000"
SITE_CACHE = ROOT / "data" / "raw" / "tc2000"
OUTPUT = ROOT / "motorsport" / "tc2000" / "data" / "tc2000.json"
PAGES = {"tc2000": "Turismo Competición 2000", "super": "Súper TC2000"}
SITE = "https://tc2000.com.ar/estadisticas.php?accion="
USER_AGENT = "sports-stats-mvp/1.0 (https://github.com/angelmza1990/sports-stats-mvp)"

FIRST, SUPER = 1979, range(2012, 2022)
# Title counts the build must reproduce (the category's statistics, Súper TC2000 included).
TITLES = {"Juan María Traverso": 7, "Matías Rossi": 6, "Leonel Pernía": 4, "José María López": 3,
          "Gabriel Ponce de León": 3, "Jorge Omar del Río": 3}
WINS = {"Juan María Traverso": 68}

# The official statistics write some names short or without accents.
NAMES = {
    "jorge o. del rio": "Jorge Omar del Río", "ruben l. di palma": "Luis Rubén Di Palma", "ruben daray": "Rubén Daray",
    "gabriel p. de leon": "Gabriel Ponce de León", "matias rossi": "Matías Rossi", "leonel pernia": "Leonel Pernía",
    "agustin canapino": "Agustín Canapino", "jose maria lopez": "José María López", "nestor girolami": "Néstor Girolami",
    "omar martinez": "Omar Martínez", "julian santero": "Julián Santero", "martin basso": "Martín Basso",
    "osvaldo lopez": "Osvaldo López", "fabian yannantuoni": "Fabián Yannantuoni", "miguel a. guerra": "Miguel Ángel Guerra",
    "damian fineschi": "Damián Fineschi", "tiago pernia": "Tiago Pernía", "gabriel furlan": "Gabriel Furlán",
    "jose manuel urcera": "José Manuel Urcera", "nelson garcia": "Nelson García", "anibal zaniratto": "Aníbal Zaniratto",
    "matias munoz marchesi": "Matías Muñoz Marchesi", "mariano pernia": "Mariano Pernía", "nicolas vuyovich": "Nicolás Vuyovich",
    "ernesto bessone": "Ernesto Bessone II", "hernandez": "Walter Hernández", "fernandino": "Esteban Fernandino II",
    "p. di palma": "Patricio Di Palma", "l. burti": "Luciano Burti", "diego aventin": "Diego Aventín",
    "menu alain": "Alain Menu", "osvaldo abel lopez": "Osvaldo López", "reid, anthony": "Anthony Reid", "facundo marques": "Facundo Marques",
    "esteban guerrieri": "Esteban Guerrieri", "valentin yankelevich": "Valentín Yankelevich", "tomas fernandez": "Tomás Fernández",
    "matias rodriguez": "Matías Rodríguez", "nicolas traut": "Nicolás Traut", "nicolas palau": "Nicolás Palau",
    "benjamin squaglia": "Benjamín Squaglia", "ignacio montenegro": "Ignacio Montenegro", "lucas carabajal": "Lucas Carabajal",
}
# Several entrant names of the same outfit, folded into one team for the title count.
TEAMS = {
    "Berta Sport": "Berta", "Berta Motorsport": "Berta", "Oreste Berta": "Berta", "Pianetto Competición": "Pianetto",
    "Pro Racing": "Pro Racing", "Ambrogio Racing": "Ambrogio Racing", "Axion Energy Sport": "Ambrogio Racing",
    "Toyota Gazoo Racing Argentina": "Toyota Gazoo Racing Argentina", "Toyota Gazoo Racing YPF Infinia": "Toyota Gazoo Racing Argentina",
    "Toyota Team Argentina": "Toyota Gazoo Racing Argentina", "DTA Racing": "DTA Racing", "PSG-16 Team": "PSG-16 Team",
    "HAZ Racing Team": "HAZ Racing", "Honda Racing Petrobras": "Petrobras Honda",
}
BRANDS = {"VW": "Volkswagen", "Volkswagen": "Volkswagen", "Chevrolet": "Chevrolet", "Ford": "Ford", "Renault": "Renault", "Honda": "Honda",
          "Toyota": "Toyota", "Peugeot": "Peugeot", "Dodge": "Dodge", "Fiat": "Fiat", "Citroën": "Citroën", "Nissan": "Nissan"}


def key(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def canonical(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    return NAMES.get(key(name), name)


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", key(name)).strip("-")


# ---------------------------------------------------------------- downloads
def wiki(name: str, refresh: bool) -> str:
    title = PAGES[name]
    return W.fetch_raw(title, WIKI_CACHE / f"{slug(title)}.wiki", refresh, pause=1.5, lang="es")


def site(action: str, refresh: bool) -> str:
    cache = SITE_CACHE / f"{slug(action)}.html"
    if refresh or not cache.exists():
        print(f"downloading tc2000.com.ar: {action}", file=sys.stderr)
        try:
            req = urllib.request.Request(SITE + action, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(text, encoding="utf-8")
            time.sleep(1.5)
        except OSError as err:
            if not cache.exists():
                raise
            print(f"warning: could not download {action} ({err}); using the saved copy", file=sys.stderr)
    return cache.read_text(encoding="utf-8")


class Tabs(HTMLParser):
    """Rows of the tables (and the <ul class="puntajes"> lists) inside each jQuery UI tab of the page."""

    def __init__(self):
        super().__init__()
        self.tabs: dict[str, list[list[str]]] = {}
        self.tab = None
        self.row = None
        self.cell = None
        self.brand = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "div" and (a.get("id") or "").startswith("tabs-"):
            self.tab = a["id"]
            self.tabs.setdefault(self.tab, [])
        elif tag in ("tr", "ul") and self.tab and (tag == "tr" or "puntajes" in (a.get("class") or "")):
            self.row = []
        elif tag in ("td", "li") and self.row is not None:
            self.cell = []
        elif tag == "img" and self.cell is not None and a.get("title"):
            self.cell.append(a["title"])

    def handle_endtag(self, tag):
        if tag in ("td", "li") and self.cell is not None and self.row is not None:
            self.row.append(re.sub(r"\s+", " ", "".join(self.cell)).strip())
            self.cell = None
        elif tag in ("tr", "ul") and self.row is not None:
            if self.row:
                self.tabs[self.tab].append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def tabs(html: str) -> dict[str, list[list[str]]]:
    # Commented-out tables would otherwise be read as live ones.
    p = Tabs()
    p.feed(re.sub(r"<!--.*?-->", "", html, flags=re.S))
    return p.tabs


# ---------------------------------------------------------------- Wikipedia
def province(cell: str) -> str | None:
    m = re.search(r"\{\{\s*bandera\s*\|\s*([^|}]+)", cell, re.I)
    if not m:
        return None
    p = re.sub(r"^Provincia del? |\s*\(Argentina\)$", "", m.group(1).strip())
    return "Buenos Aires" if p == "Buenos Aires" else p


def team_of(cell: str, driver: str = "") -> tuple[str, str]:
    """(entrant name as shown, the outfit behind it) from a team cell."""
    found = W.links(cell)
    shown = W.plain(W.strip_refs(cell)).strip()
    # A driver's own team sometimes links to the driver's article.
    outfit = found[0][0] if found and canonical(found[0][0]) != driver else shown
    return shown, TEAMS.get(outfit, outfit)


def champion_rows(table: list[list[dict]]) -> list[tuple[int, list[dict]]]:
    out = []
    for r in table:
        if not r or not r[0]["header"]:
            continue
        m = re.search(r"\b(19|20)\d\d\b", W.plain(r[0]["text"]))
        if m and len(r) >= 4 and not r[1]["header"]:
            out.append((int(m.group()), r))
    return out


def parse_wikipedia(tc: str, sup: str) -> dict[int, dict]:
    seasons = {}
    rows = champion_rows(W.parse_table(W.find_table(tc, r"== Campeones ==")))
    rows += champion_rows(W.parse_table(W.find_table(sup, r"=== Pilotos ===")))
    for year, r in rows:
        if "No se disputó" in r[1]["text"]:
            continue
        driver = canonical(W.person(r[1]["text"]) or W.plain(r[1]["text"]))
        shown, outfit = team_of(r[3]["text"], driver)
        seasons[year] = {
            "season": year, "driver": driver,
            "province": province(r[1]["text"]), "car": W.plain(W.strip_refs(r[2]["text"])).replace(" y ", " & ").strip(),
            "team": shown, "outfit": outfit, "era": "Súper TC2000" if year in SUPER else "TC2000",
        }
    # Makes: the category's own tables (they settle the Dodge/Volkswagen 1500 of the early 1980s).
    brand_rows = W.parse_table(W.find_table(tc, r"=== Marcas ==="))
    for r in brand_rows:
        if len(r) < 4 or r[0]["header"] or "Clase secundaria" in r[0]["text"]:
            if r and "Clase secundaria" in r[0]["text"]:
                break
            continue
        brand = W.plain(r[1]["text"]).strip()
        for y in re.findall(r"\b(?:19|20)\d\d\b", r[3]["text"]):
            if int(y) in seasons:
                seasons[int(y)]["brand"] = BRANDS.get(brand, brand)
    sup_brands = W.parse_table(W.find_table(sup, r"=== Marcas ==="))
    for r in sup_brands:
        m = re.search(r"\b20\d\d\b", W.plain(r[0]["text"])) if r and r[0]["header"] else None
        if m and len(r) >= 2 and int(m.group()) in seasons:
            seasons[int(m.group())]["brand"] = BRANDS.get(W.plain(r[1]["text"]).strip(), W.plain(r[1]["text"]).strip())
    return seasons


def team_champions(sup: str) -> list[dict]:
    out = []
    for r in W.parse_table(W.find_table(sup, r"=== Equipos ===")):
        m = re.search(r"\b20\d\d\b", W.plain(r[0]["text"])) if r and r[0]["header"] else None
        if m and len(r) >= 3 and not r[1]["header"]:
            shown, outfit = team_of(r[1]["text"])
            out.append({"season": int(m.group()), "team": shown, "outfit": outfit, "car": W.plain(r[2]["text"]).strip()})
    return out


# ---------------------------------------------------------------- the category's statistics
def when(d: str, place: str) -> dict | None:
    if not re.match(r"\d{4}-\d\d-\d\d$", d) or d < "1979":
        return None
    return {"date": d, "place": re.sub(r"\s+\d$", "", place).strip()}


def parse_site(html: str) -> tuple[dict[int, int], list[dict], list[dict], dict[int, str]]:
    t = tabs(html)
    season_wins, official = {}, {}
    for r in t.get("tabs-1", []):
        if len(r) == 5 and r[0].strip().isdigit():
            season_wins[int(r[0])] = int(r[4])
            official[int(r[0])] = canonical(r[1])

    def ranking(rows, field):
        out = []
        for r in rows:
            if len(r) == 6 and r[1].isdigit():
                out.append({"driver": canonical(r[0]), field: int(r[1]), "first": when(r[4], r[5]), "last": when(r[2], r[3])})
        return out

    return season_wins, ranking(t.get("tabs-2", []), "wins"), ranking(t.get("tabs-4", []), "poles"), official


def parse_current(html: str) -> dict:
    t = tabs(html)

    def entries(rows):
        out = []
        for r in rows:
            if len(r) >= 3 and r[-1].isdigit():
                name, _, places = r[1].partition(" / ")
                out.append({"driver": canonical(name), "brand": BRANDS.get(r[0], r[0]), "n": int(r[-1]),
                            "places": [p.strip(" -") for p in places.split(" - ") if p.strip(" -")]})
        return out

    return {"wins": entries(t.get("tabs-1", [])), "poles": entries(t.get("tabs-2", []))}


# ---------------------------------------------------------------- checks
def check(seasons: list[dict], official: dict[int, str], wins: list[dict]) -> None:
    years = [s["season"] for s in seasons]
    assert years == list(range(FIRST, years[-1] + 1)), f"missing seasons: {sorted(set(range(FIRST, years[-1] + 1)) - set(years))}"
    for s in seasons:
        assert s.get("brand"), f"{s['season']}: no make"
        o = official.get(s["season"])
        if o and key(o).split()[-1] != key(s["driver"]).split()[-1]:
            raise ValueError(f"{s['season']}: Wikipedia says {s['driver']}, the category says {o}")
    titles = Counter(s["driver"] for s in seasons)
    for name, n in TITLES.items():
        assert titles[name] == n, f"{name}: {titles[name]} titles, expected {n}"
    by = {w["driver"]: w["wins"] for w in wins}
    for name, n in WINS.items():
        assert by.get(name) == n, f"{name}: {by.get(name)} wins, expected {n}"
    assert sum(1 for s in seasons if s["era"] == "Súper TC2000") == len(SUPER)
    missing = {s["driver"] for s in seasons if s["season"] > FIRST} - set(by)
    assert not missing, f"champions without race wins in the statistics (names differ?): {missing}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    this_year = date.today().year

    seasons = parse_wikipedia(wiki("tc2000", args.refresh), wiki("super", args.refresh))
    season_wins, wins, poles, official = parse_site(site("historicas", args.refresh))
    current = parse_current(site(str(this_year), args.refresh))
    champions = [seasons[y] for y in sorted(seasons)]
    for c in champions:
        c["wins"] = season_wins.get(c["season"])
    check(champions, official, wins)

    names = {c["driver"] for c in champions} | {w["driver"] for w in wins} | {p["driver"] for p in poles}
    names |= {e["driver"] for k in ("wins", "poles") for e in current[k]}
    drivers = {slug(n): {"name": n} for n in sorted(names)}
    for c in champions:
        if c["province"]:
            drivers[slug(c["driver"])]["province"] = c["province"]
    ref = lambda rows: [{**r, "driver": slug(r["driver"])} for r in rows]  # noqa: E731

    out = {
        "meta": {
            "generated": date.today().isoformat(), "through": champions[-1]["season"], "current": this_year,
            "sources": [f"https://es.wikipedia.org/wiki/{p.replace(' ', '_')}" for p in PAGES.values()]
            + [SITE + "historicas", SITE + str(this_year)],
        },
        "drivers": drivers,
        "champions": [{**c, "driver": slug(c["driver"])} for c in champions],
        "teamChampions": team_champions(wiki("super", False)),
        "wins": ref(wins),
        "poles": ref(poles),
        "currentSeason": {"year": this_year, "wins": ref(current["wins"]), "poles": ref(current["poles"])},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    top = Counter(c["driver"] for c in out["champions"]).most_common(3)
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(champions)} champions ({champions[0]['season']}-{champions[-1]['season']}), "
          f"{len(wins)} race winners, {sum(w['wins'] for w in wins)} wins, {len(poles)} pole sitters; most titles {top}")


if __name__ == "__main__":
    main()
