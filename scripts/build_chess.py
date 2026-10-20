"""Build the chess dataset used by chess/.

From Wikipedia: every World Championship match and tournament (with the
pre-1886 matches and the 1993-2006 split title), the women's World
Championship, the World Rapid and Blitz Championships (open and women), the
FIDE world number ones by month (classical, rapid and blitz; open and women),
peak ratings, the Chess Olympiad, Candidates, World Cup, Chess960 and the
youngest grandmasters. From PGN Mentor's game files: head-to-head records
between the greatest players, split into classical, rapid and blitz games.

Usage:
    python3 scripts/build_chess.py            # use saved pages and game files
    python3 scripts/build_chess.py --refresh  # re-download them
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import date

import wikitables as W
from build_football import RAW_DIR, ROOT, slug
from olympic_events import nation_info

OUTPUT = ROOT / "chess" / "data" / "chess.json"
CACHE = RAW_DIR / "chess"
PGN_DIR = ROOT / "data" / "raw" / "chess" / "pgn"
PGN_URL = "https://www.pgnmentor.com/players/{file}.zip"
USER_AGENT = "sports-stats-mvp/1.0 (https://github.com/angelmza1990/sports-stats-mvp)"

# Federation codes (FIDE uses IOC-style codes) -> (name, flagcdn code or None).
FEDERATIONS = {
    "USA": ("United States", "us"), "RUS": ("Russia", "ru"), "URS": ("Soviet Union", None), "IND": ("India", "in"),
    "CHN": ("China", "cn"), "NOR": ("Norway", "no"), "GER": ("Germany", "de"), "FRA": ("France", "fr"), "NED": ("Netherlands", "nl"),
    "CUB": ("Cuba", "cu"), "GBR": ("Great Britain", "gb"), "ENG": ("England", "gb-eng"), "HUN": ("Hungary", "hu"),
    "UKR": ("Ukraine", "ua"), "ARM": ("Armenia", "am"), "BUL": ("Bulgaria", "bg"), "ESP": ("Spain", "es"), "ITA": ("Italy", "it"),
    "AUT": ("Austria", "at"), "POL": ("Poland", "pl"), "CZE": ("Czech Republic", "cz"), "TCH": ("Czechoslovakia", None),
    "YUG": ("Yugoslavia", None), "SRB": ("Serbia", "rs"), "GEO": ("Georgia", "ge"), "AZE": ("Azerbaijan", "az"), "UZB": ("Uzbekistan", "uz"),
    "KAZ": ("Kazakhstan", "kz"), "ISR": ("Israel", "il"), "ARG": ("Argentina", "ar"), "BRA": ("Brazil", "br"), "CAN": ("Canada", "ca"),
    "SWE": ("Sweden", "se"), "DEN": ("Denmark", "dk"), "SUI": ("Switzerland", "ch"), "IRI": ("Iran", "ir"), "PHI": ("Philippines", "ph"),
    "LAT": ("Latvia", "lv"), "LTU": ("Lithuania", "lt"), "EST": ("Estonia", "ee"), "BLR": ("Belarus", "by"), "ROU": ("Romania", "ro"),
    "SLO": ("Slovenia", "si"), "CRO": ("Croatia", "hr"), "PER": ("Peru", "pe"), "VIE": ("Vietnam", "vn"), "MGL": ("Mongolia", "mn"),
    "BIH": ("Bosnia and Herzegovina", "ba"), "MNE": ("Montenegro", "me"), "SVK": ("Slovakia", "sk"), "FIN": ("Finland", "fi"),
    "GRE": ("Greece", "gr"), "TUR": ("Turkey", "tr"), "BEL": ("Belgium", "be"), "AUS": ("Australia", "au"), "MEX": ("Mexico", "mx"),
    "CHI": ("Chile", "cl"), "COL": ("Colombia", "co"), "FID": ("FIDE (neutral)", None), "AHU": ("Austria-Hungary", None),
    "RU1": ("Russian Empire", None), "PRU": ("Prussia", None), "SCO": ("Scotland", "gb-sct"), "IRL": ("Ireland", "ie"),
    "MDA": ("Moldova", "md"), "QAT": ("Qatar", "qa"), "UAE": ("United Arab Emirates", "ae"), "SLV": ("El Salvador", "sv"), "SRI": ("Sri Lanka", "lk"), "EGY": ("Egypt", "eg"), "KGZ": ("Kyrgyzstan", "kg"), "TPE": ("Chinese Taipei", "tw"),
}
# Flag template names Wikipedia uses for chess federations (historical states included).
FLAG_NAMES = {
    "us": "USA", "united states": "USA", "uk": "GBR", "united kingdom": "GBR", "great britain": "GBR", "england": "ENG",
    "ussr": "URS", "soviet union": "URS", "russia": "RUS", "russian empire": "RU1", "austria-hungary": "AHU", "transleithania": "HUN",
    "india": "IND", "china": "CHN", "norway": "NOR", "germany": "GER", "german empire": "GER", "nazi germany": "GER", "weimar republic": "GER",
    "west germany": "GER", "france": "FRA", "netherlands": "NED", "cuba": "CUB", "hungary": "HUN", "ukraine": "UKR", "armenia": "ARM",
    "bulgaria": "BUL", "spain": "ESP", "spanish empire": "ESP", "italy": "ITA", "austria": "AUT", "poland": "POL", "czech republic": "CZE",
    "czechoslovakia": "TCH", "yugoslavia": "YUG", "serbia": "SRB", "georgia": "GEO", "azerbaijan": "AZE", "uzbekistan": "UZB",
    "kazakhstan": "KAZ", "israel": "ISR", "argentina": "ARG", "brazil": "BRA", "canada": "CAN", "sweden": "SWE", "denmark": "DEN",
    "switzerland": "SUI", "iran": "IRI", "philippines": "PHI", "latvia": "LAT", "lithuania": "LTU", "estonia": "EST", "belarus": "BLR",
    "romania": "ROU", "slovenia": "SLO", "croatia": "CRO", "peru": "PER", "vietnam": "VIE", "mongolia": "MGL", "fide": "FID",
    "prussia": "PRU", "scotland": "SCO", "kingdom of prussia": "PRU", "russian sfsr": "URS", "moldova": "MDA", "qatar": "QAT",
    "egypt": "EGY", "slovakia": "SVK", "finland": "FIN", "greece": "GRE", "turkey": "TUR", "belgium": "BEL", "australia": "AUS",
    "kingdom of serbs, croats and slovenes": "YUG", "kingdom of yugoslavia": "YUG", "kingdom of romania": "ROU",
    "kingdom of hungary": "HUN", "second polish republic": "POL", "estonia": "EST",
    "german confederation": "GER", "austrian empire": "AHU", "uae": "UAE", "kazakhstan": "KAZ", "sri lanka": "SRI",
}


def page(title: str, refresh: bool) -> str:
    return W.fetch_raw(title, CACHE / f"{slug(title)}.wiki", refresh, pause=1.5)


def drop_templates(text: str, names: tuple[str, ...]) -> str:
    """Remove every {{name ...}} template (balanced braces), e.g. multi-line venue lists and footnotes."""
    out, i = [], 0
    pattern = re.compile(r"\{\{\s*(?:" + "|".join(names) + r")\b", re.I)
    while True:
        m = pattern.search(text, i)
        if not m:
            out.append(text[i:])
            return "".join(out)
        out.append(text[i:m.start()])
        depth, j = 0, m.start()
        while j < len(text):
            if text.startswith("{{", j):
                depth, j = depth + 1, j + 2
            elif text.startswith("}}", j):
                depth, j = depth - 1, j + 2
                if depth == 0:
                    break
            else:
                j += 1
        i = j


def federation(cell: str) -> str | None:
    """Federation code from the first flag template in a cell: {{flagicon|USSR|1936}}, {{flagathlete|[[X]]|NOR}},
    {{flagdeco|Russia}}, the FIDE flag image for neutral players..."""
    if re.search(r"FIDE flag icon|flagicon\|FIDE\b", cell, re.I):
        return "FID"
    if re.search(r"flagicon image\|CFR Russia", cell, re.I):
        return "RUS"  # the Russian Chess Federation's flag, used while Russia's was barred
    for m in re.finditer(r"\{\{\s*(flagathlete|flagicon|flagdeco|flagu|flag|flagcountry)\s*\|([^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*)\}\}", cell, re.I):
        args = [a.strip() for a in re.split(r"\|(?![^\[]*\]\])", m.group(2))]
        candidates = args[1:2] if m.group(1).lower() == "flagathlete" else args[:1]
        for arg in candidates:
            arg = W.plain(arg).strip()
            if re.fullmatch(r"[A-Z]{3}", arg):
                return {"URS": "URS"}.get(arg, arg)
            code = FLAG_NAMES.get(arg.lower())
            if code:
                return code
    return None


def person(cell: str) -> str:
    """A player's name: {{sortname|First|Last}}, the first article link, or the name inside {{flagathlete|Name|FED}}."""
    if re.search(r"\{\{\s*sortname", cell, re.I):
        return W.person(cell)
    for target, label in W.links(cell):
        if not re.match(r"(World|Women's|FIDE|Chess|List of)\b", target):
            return re.sub(r"\s*\(\d+\)\s*$", "", W.plain(label)).strip()
    m = re.search(r"\{\{\s*flagathlete\s*\|\s*([^|{}]+)", cell, re.I)
    name = W.plain(m.group(1)) if m else W.plain(re.sub(r"\{\{[^{}]*\}\}", "", cell))
    return re.sub(r"\s*\(\d+\)\s*$", "", name).strip()


def people(cell: str) -> list[tuple[str, str | None]]:
    """Every player in a cell (shared titles list two), with their federations."""
    parts = [p for p in re.split(r"<br\s*/?>", cell) if W.plain(p) or W.links(p)]
    out = [(person(p), federation(p)) for p in parts]
    return [(n, f) for n, f in out if n and n.lower() not in ("n/a", "not held", "tba")]


def score_text(cell: str) -> str:
    text = cell.replace("{{2pd}}", "–").replace("{{Dashed rule}}", " · tiebreak ")
    return re.sub(r"\s+", " ", W.plain(text)).strip(" ·")


# ---------- World Championship ----------

WCC_PAGE = "List of World Chess Championships"
WCC_SECTIONS = [  # (heading, era, title)
    (r"== Predecessor events", "unofficial", "Before 1886"),
    (r"== Privately organized matches", "official", "Undisputed"),
    (r"== FIDE World Championships \(1948", "official", "Undisputed"),
    (r"== Split title", "classical", "Classical (PCA/Braingames)"),
    (r"== FIDE World Championships \(2006", "official", "Undisputed"),
]


def parse_wcc(refresh: bool) -> list[dict]:
    text = drop_templates(page(WCC_PAGE, refresh), ("csl", "efn", "efn-ua", "sfn", "sfnm"))
    text = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    events = []
    for heading, era, title in WCC_SECTIONS:
        start = re.search(heading, text).start()
        end = re.search(r"\n== ", text[start + 3:]).start() + start + 3
        for n, grid in enumerate(W.all_tables(text[start:end])):
            labels = W.header_labels(grid[0])
            if "Winner" not in labels:
                continue
            col = {l: labels.index(l) for l in labels}
            this_era = era
            if era == "classical" and n > 0:
                this_era = "fide"  # the second table of the split-title section holds the FIDE knockout events
            for row in grid[1:]:
                if len(row) < len(labels) or all(c["header"] for c in row):
                    continue
                date_cell = row[col["Date"]]["text"]
                label = W.plain(date_cell)
                year = re.search(r"(\d{4})", label)  # "1894", "Jan–Feb 1910"
                win_cell, run_cell = row[col["Winner"]]["text"], row[col["Runner-up"]]["text"]
                if not year or " vs " in W.plain(win_cell) or not W.plain(win_cell) or "vacant" in label.lower():
                    continue
                events.append({
                    "year": int(year.group(1)), "label": re.sub(r"[†‡#✻*]", "", label).strip(),
                    "era": this_era, "kind": "aborted" if "✻" in label else "tournament" if "†" in label else "match", "drawn": "‡" in label,
                    "location": W.plain(row[col["Location"]]["text"]),
                    "winner": person(win_cell), "winnerFed": federation(win_cell),
                    "runnerUp": person(run_cell), "runnerUpFed": federation(run_cell),
                    "score": score_text(row[col["Score"]]["text"]),
                    "format": W.plain(row[col["Format"]]["text"]) if "Format" in col else "",
                })
    return events


def clean(text: str) -> str:
    text = drop_templates(text, ("efn", "efn-ua", "sfn", "sfnm", "refn", "csl"))
    return re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", text, flags=re.S)


def section(text: str, heading: str) -> str:
    """The text under a heading, up to the next heading of the same or a higher level."""
    m = re.search(r"\n(=+)\s*" + heading, text)
    if not m:
        raise LookupError(f"section not found: {heading}")
    level = len(m.group(1))
    nxt = re.search(r"\n={2," + str(level) + r"}[^=]", text[m.end():])
    return text[m.start():m.end() + (nxt.start() if nxt else len(text))]


def champion_rows(grid: list[list[dict]], champion_col: str = "Champion") -> list[dict]:
    """Year, champion(s), runner-up and third from a "Year | ... | Champion | Runner-up" table."""
    labels = W.header_labels(grid[0])
    col = {l: i for i, l in enumerate(labels)}
    champ = next(i for l, i in col.items() if l.startswith(champion_col) or l in ("World champion",))
    runner = col.get("Runner-up")
    third = col.get("Third place")
    out = []
    for row in grid[1:]:
        if len(row) <= champ or all(c["header"] for c in row):
            continue
        year = re.match(r"(\d{4})", W.plain(row[0]["text"]))
        champs = people(row[champ]["text"])
        if not year or not champs or " vs" in W.plain(row[champ]["text"]):
            continue
        rec = {"year": int(year.group(1)), "champions": [{"name": n, "fed": f} for n, f in champs]}
        if runner is not None and runner < len(row):
            rec["runnerUp"] = [{"name": n, "fed": f} for n, f in people(row[runner]["text"])]
        if third is not None and third < len(row):
            rec["third"] = [{"name": n, "fed": f} for n, f in people(row[third]["text"])]
        out.append(rec)
    return out


def title_years(grid: list[list[dict]], player_col: int = 1, years_col: int = 2) -> list[tuple[int, str, str | None]]:
    """A records table's (year, player, federation) list: every title it credits, shared ones included."""
    out = []
    for row in grid[1:]:
        if len(row) <= max(player_col, years_col) or all(c["header"] for c in row):
            continue
        cell = row[player_col]["text"]
        name, fed = person(cell), federation(cell)
        for y in re.findall(r"\b(19\d\d|20\d\d)\b", W.plain(row[years_col]["text"])):
            out.append((int(y), name, fed))
    return out


def merge_titles(rows: list[dict], credited: list[tuple[int, str, str | None]]) -> list[dict]:
    """Add the titles a records table credits but the editions tables don't list (early or one-off events)."""
    have = {(r["year"], c["name"]) for r in rows for c in r["champions"]}
    for year, name, fed in credited:
        if (year, name) not in have:
            rows.append({"year": year, "champions": [{"name": name, "fed": fed}], "fromRecords": True})
            have.add((year, name))
    return sorted(rows, key=lambda r: r["year"])


def title_counts(grid: list[list[dict]], player_col: int = 1, count_cols: tuple[int, ...] = (0,)) -> dict[str, int]:
    """A records table ("Titles | Player | Years") as {player: titles}."""
    out = {}
    for row in grid[1:]:
        if len(row) <= max(player_col, *count_cols):
            continue
        name = person(row[player_col]["text"])
        n = sum(W.number(row[c]["text"]) or 0 for c in count_cols)
        if name and n:
            out[name] = n
    return out


# ---------- Women's World Championship ----------

WOMEN_PAGE = "Women's World Chess Championship"


def parse_women(refresh: bool) -> list[dict]:
    text = clean(page(WOMEN_PAGE, refresh))
    grid = next(g for g in W.all_tables(text) if W.header_labels(g[0])[:5] == ["Year", "Host country", "Host city", "World champion", "Runner-up"])
    labels = W.header_labels(grid[0])
    col = {l: i for i, l in enumerate(labels)}
    out = []
    for row in grid[1:]:
        if len(row) < len(labels) or all(c["header"] for c in row) or row[0] is row[1]:
            continue
        year = re.match(r"(\d{4})", W.plain(row[0]["text"]))
        champ, runner = row[col["World champion"]]["text"], row[col["Runner-up"]]["text"]
        if not year or " vs" in W.plain(champ):
            continue
        out.append({
            "year": int(year.group(1)), "city": W.plain(row[col["Host city"]]["text"]),
            "winner": person(champ), "winnerFed": federation(champ), "runnerUp": person(runner), "runnerUpFed": federation(runner),
            "w": W.number(row[col["W"]]["text"]), "l": W.number(row[col["L"]]["text"]), "d": W.number(row[col["D"]]["text"]),
            "format": W.plain(row[col["Format"]]["text"]) if "Format" in col else "",
        })
    return out


# ---------- Rapid and blitz ----------

RAPID_PAGE = "World Rapid Chess Championship"
BLITZ_PAGE = "World Blitz Chess Championship"


def parse_fast(refresh: bool) -> tuple[dict, dict]:
    """FIDE-recognized rapid and blitz champions (open and women), and the pages' own title counts."""
    out, official = {}, {}
    rapid = clean(page(RAPID_PAGE, refresh))
    blitz = clean(page(BLITZ_PAGE, refresh))
    pre = W.all_tables(section(rapid, r"Pre-2012"))[0]
    out["rapid-open"] = champion_rows(pre) + champion_rows(W.all_tables(section(rapid, r"Open"))[0])
    out["rapid-women"] = champion_rows(W.all_tables(section(rapid, r"Women"))[0])
    out["blitz-open"] = (champion_rows(W.all_tables(section(blitz, r"Editions and medallists"))[0])
                         + champion_rows(W.all_tables(section(blitz, r"Open"))[0], "Champion"))
    out["blitz-women"] = champion_rows(W.all_tables(section(blitz, r"Women"))[0])
    # Records tables: rapid open counts "FIDE" titles in columns 4-5; blitz open "Times won"; women "Titles won".
    # They also credit events the editions tables leave out (Fischer at Herceg Novi 1970, the 1992 women's events).
    rec = W.all_tables(section(rapid, r"Titles \(open\)"))[0]
    records = {
        "rapid-open": ([rec[0]] + rec[2:], (4,), 5),
        "rapid-women": (W.all_tables(section(rapid, r"Titles \(women\)"))[0], (0,), 2),
        "blitz-open": (W.all_tables(section(blitz, r"Titles \(open\)"))[0], (0,), 2),
        "blitz-women": (W.all_tables(section(blitz, r"Titles \(women\)"))[0], (0,), 2),
    }
    for key, (grid, counts, years) in records.items():
        official[key] = title_counts(grid, 1, counts)
        out[key] = merge_titles(out[key], title_years(grid, 1, years))
    return out, official


# ---------- World number ones ----------

NO1_PAGE = "List of FIDE chess world number ones"
NO1_SECTIONS = {
    "classical-open": r"Top players \(list\)", "classical-women": r"List of world female number ones",
    "rapid-open": r"Top players ====", "rapid-women": r"Top women ====",
    "blitz-open": r"Top players \(blitz\)", "blitz-women": r"Top women \(blitz\)",
}


def month_grid(grid: list[list[dict]]) -> list[dict]:
    """[{year, month, player, fed}] from a Year x month grid. An empty month keeps the previous number one
    (no new list was published); a cell with only a rating repeats the previous player."""
    short_to_full: dict[str, tuple[str, str | None]] = {}
    out, holder, prev = [], None, None
    for row in grid[1:]:
        year = W.number(row[0]["text"]) if row else None
        if not year or year < 1960:
            continue
        for month, cell in enumerate(row[1:13], start=1):
            raw = cell["text"]
            if cell is prev and holder is not None:
                pass  # colspan: the same holder carries on
            else:
                text = W.plain(raw)
                if re.search(r"before official|N/A|no list|not published", text, re.I):
                    holder = None
                elif re.search(r"[A-Za-zÀ-ž]", re.sub(r"\(.*?\)", "", text)):
                    links = [(t, l) for t, l in W.links(raw) if not t.lower().startswith(("file:", "list of"))]
                    fed = federation(raw)
                    if links:
                        full = re.sub(r"\s*\(.*?\)$", "", links[0][0]).strip()
                        short_to_full[W.plain(links[0][1]).strip()] = (full, fed)
                        holder = (full, fed)
                    else:
                        short = re.sub(r"\s*\(.*?\)", "", text).strip()
                        known = short_to_full.get(short)
                        holder = (known[0], fed or known[1]) if known else (short, fed)
                        short_to_full.setdefault(short, holder)
            prev = cell
            if holder and (year, month) <= (date.today().year, date.today().month):
                out.append({"year": year, "month": month, "player": holder[0], "fed": holder[1]})
    return out


def parse_number_ones(refresh: bool) -> tuple[dict, dict]:
    text = clean(page(NO1_PAGE, refresh))
    lists, official = {}, {}
    for key, heading in NO1_SECTIONS.items():
        lists[key] = month_grid(W.all_tables(section(text, heading))[0])
    for key, heading in (("classical-open", r"Player statistics"), ("classical-women", r"Women statistics")):
        grid = W.all_tables(section(text, heading))[0]
        official[key] = {person(r[0]["text"]): W.number(r[1]["text"]) for r in grid[1:] if len(r) > 1 and W.number(r[1]["text"])}
    return lists, official


# ---------- Peak ratings, team events and other titles ----------

PEAK_PAGE = "List of chess players by peak FIDE rating"


def parse_peaks(refresh: bool) -> dict:
    text = clean(page(PEAK_PAGE, refresh))
    decades = {}
    for grid in W.all_tables(text):
        labels = W.header_labels(grid[0])
        if len(labels) >= 5 and labels[3].startswith("Peak rating in"):
            decade = labels[3].split("in ")[-1]
            decades[decade] = [{"name": person(r[2]["text"]), "fed": federation(r[1]["text"]), "rating": W.number(r[3]["text"]),
                                "achieved": W.plain(r[4]["text"])} for r in grid[1:] if len(r) > 4 and W.number(r[3]["text"])]
    history = next(g for g in W.all_tables(text) if W.header_labels(g[0])[:3] == ["Player", "Rating", "Achieved"])
    record = [{"name": person(r[0]["text"]), "rating": W.number(r[1]["text"]), "achieved": W.plain(r[2]["text"])} for r in history[1:] if len(r) > 2]
    return {"decades": decades, "recordProgression": record}


OLYMPIAD_PAGE = "Chess Olympiad"


def olympiad_rows(grid: list[list[dict]]) -> list[dict]:
    out = []
    for row in grid[1:]:
        year = re.match(r"(\d{4})", W.plain(row[0]["text"])) if row else None
        if not year or len(row) < 6:
            continue
        medals = [federation(row[i]["text"]) or W.flag_code(row[i]["text"]) for i in (3, 4, 5)]
        label = W.plain(row[1]["text"]).lower()  # unofficial events, and the 1976 "Against Chess Olympiad" in Tripoli
        out.append({"year": int(year.group(1)), "official": "unofficial" not in label and "against" not in label,
                    "gold": medals[0], "silver": medals[1], "bronze": medals[2]})
    return [r for r in out if r["gold"]]


def medal_template(text: str) -> dict[str, list[int]]:
    start = text.find("{{Medals table")
    body = text[start:text.find("\n}}", start)]
    return {code: [int((re.search(rf"\b{m}_{code}\s*=\s*(\d+)", body) or [0, 0])[1]) for m in ("gold", "silver", "bronze")]
            for code in dict.fromkeys(re.findall(r"gold_([A-Z]{3})\s*=", body))}


def parse_olympiad(refresh: bool) -> dict:
    """Open-event podiums year by year, and the all-time medal tables (official events) of both sections."""
    text = clean(page(OLYMPIAD_PAGE, refresh))
    results = section(text, r"Results")
    tables = section(text, r"Medal tables")
    return {
        # The section opens with a map of host cities; the results table is the one headed "Year".
        "open": olympiad_rows(next(g for g in W.all_tables(section(results, r"Open event")) if W.header_labels(g[0])[0].startswith("Year"))),
        "medalsOpen": medal_template(section(tables, r"Open event")),
        "medalsWomen": medal_template(section(tables, r"Women's event")),
    }


def simple_winners(refresh: bool, title: str, heading: str, winner: str, runner: str = "Runner-up") -> list[dict]:
    text = clean(page(title, refresh))
    grid = W.all_tables(section(text, heading))[0]
    labels = W.header_labels(grid[0])
    wi, ri = labels.index(winner), labels.index(runner) if runner in labels else None
    out = []
    for row in grid[1:]:
        year = re.match(r"(\d{4})", W.plain(row[0]["text"])) if row else None
        if not year or len(row) <= wi or not W.links(row[wi]["text"]):
            continue
        out.append({"year": int(year.group(1)), "winner": person(row[wi]["text"]), "winnerFed": federation(row[wi]["text"]),
                    "runnerUp": person(row[ri]["text"]) if ri is not None else None,
                    "runnerUpFed": federation(row[ri]["text"]) if ri is not None else None})
    return out


PRODIGY_PAGE = "Chess prodigy"


def parse_prodigies(refresh: bool) -> dict:
    text = clean(page(PRODIGY_PAGE, refresh))
    def table(heading):
        grid = W.all_tables(section(text, heading))[0]
        labels = W.header_labels(grid[0])
        col = {l: i for i, l in enumerate(labels)}
        rows = []
        for r in grid[1:]:
            if len(r) < len(labels):
                continue
            cell = r[col["Player"]]["text"]
            rows.append({"name": person(cell), "fed": federation(cell) or (federation(r[col["Country"]]["text"]) if "Country" in col else None),
                         "age": W.plain(r[col["Age"]]["text"]), "year": W.plain(r[col["Year"]]["text"]) if "Year" in col else W.plain(r[col.get("Earned", col.get("Date", 0))]["text"])})
        return rows
    return {
        "gmRecord": table(r"List of record-holders"),
        "gmRecordWomen": table(r"List of female record-holders"),
        "youngestGM": table(r"Grandmasters younger than 14"),
    }


# ---------- Head to head (PGN Mentor game files) ----------

# The players in the head-to-head matrix: key, name, federation, PGN Mentor file, and a pattern
# matching their name in PGN headers ("Carlsen,M", "Carlsen, Magnus"...).
H2H_PLAYERS = [
    ("steinitz", "Wilhelm Steinitz", "AHU", "Steinitz", r"Steinitz,\s*W"), ("chigorin", "Mikhail Chigorin", "RU1", "Chigorin", r"Chigorin,\s*M"),
    ("tarrasch", "Siegbert Tarrasch", "GER", "Tarrasch", r"Tarrasch,\s*S"), ("lasker", "Emanuel Lasker", "GER", "Lasker", r"Lasker,\s*Em(?:anuel)?$"),
    ("rubinstein", "Akiba Rubinstein", "POL", "Rubinstein", r"Rubinstein,\s*A"), ("capablanca", "José Raúl Capablanca", "CUB", "Capablanca", r"Capablanca"),
    ("alekhine", "Alexander Alekhine", "FRA", "Alekhine", r"Alekhine,\s*A"), ("euwe", "Max Euwe", "NED", "Euwe", r"Euwe,\s*M"),
    ("botvinnik", "Mikhail Botvinnik", "URS", "Botvinnik", r"Botvinnik,\s*M"), ("keres", "Paul Keres", "URS", "Keres", r"Keres,\s*P"),
    ("smyslov", "Vasily Smyslov", "URS", "Smyslov", r"Smyslov,\s*V"), ("bronstein", "David Bronstein", "URS", "Bronstein", r"Bronstein,\s*D"),
    ("tal", "Mikhail Tal", "URS", "Tal", r"Tal,\s*M"), ("petrosian", "Tigran Petrosian", "URS", "Petrosian", r"Petrosian,\s*Tigran\s*V|Petrosian,\s*T$"),
    ("spassky", "Boris Spassky", "URS", "Spassky", r"Spassky,\s*B"), ("korchnoi", "Viktor Korchnoi", "SUI", "Korchnoi", r"Korchnoi,\s*V"),
    ("fischer", "Bobby Fischer", "USA", "Fischer", r"Fischer,\s*R"), ("karpov", "Anatoly Karpov", "URS", "Karpov", r"Karpov,\s*An"),
    ("kasparov", "Garry Kasparov", "URS", "Kasparov", r"Kasparov,\s*(?:G$|G\.|Gar)"), ("ivanchuk", "Vasyl Ivanchuk", "UKR", "Ivanchuk", r"Ivanchuk,\s*V"),
    ("anand", "Viswanathan Anand", "IND", "Anand", r"Anand,\s*(?:V$|Vis)"), ("kramnik", "Vladimir Kramnik", "RUS", "Kramnik", r"Kramnik,\s*V"),
    ("polgar", "Judit Polgár", "HUN", "PolgarJ", r"Polgar,\s*(?:Ju|J$|Judit)"), ("topalov", "Veselin Topalov", "BUL", "Topalov", r"Topalov,\s*V"),
    ("aronian", "Levon Aronian", "ARM", "Aronian", r"Aronian,\s*L"), ("grischuk", "Alexander Grischuk", "RUS", "Grischuk", r"Grischuk,\s*A"),
    ("mamedyarov", "Shakhriyar Mamedyarov", "AZE", "Mamedyarov", r"Mamedyarov,\s*S"), ("carlsen", "Magnus Carlsen", "NOR", "Carlsen", r"Carlsen,\s*M"),
    ("caruana", "Fabiano Caruana", "USA", "Caruana", r"Caruana,\s*F"), ("mvl", "Maxime Vachier-Lagrave", "FRA", "VachierLagrave", r"Vachier[- ]Lagrave"),
    ("nakamura", "Hikaru Nakamura", "USA", "Nakamura", r"Nakamura,\s*H"), ("so", "Wesley So", "USA", "So", r"So,\s*W"),
    ("nepomniachtchi", "Ian Nepomniachtchi", "RUS", "Nepomniachtchi", r"Nepomniachtchi,\s*I"), ("giri", "Anish Giri", "NED", "Giri", r"Giri,\s*A"),
    ("ding", "Ding Liren", "CHN", "Ding", r"Ding,?\s*Liren|Ding,\s*L$"), ("hou", "Hou Yifan", "CHN", "Hou", r"Hou,?\s*Yifan|Hou,\s*Y$"),
    ("firouzja", "Alireza Firouzja", "FRA", "Firouzja", r"Firouzja,\s*A"), ("gukesh", "Gukesh Dommaraju", "IND", "Gukesh", r"Gukesh"),
    ("praggnanandhaa", "Praggnanandhaa", "IND", "Praggnanandhaa", r"Praggnanandhaa"), ("erigaisi", "Arjun Erigaisi", "IND", "Erigaisi", r"Erigaisi"),
]

# Event names that mark fast games. Online series of the 2020s that don't say "rapid" are rapid unless marked blitz.
BLITZ_RE = re.compile(r"blitz|bullet|speed ?chess|speedchess|banter|armageddon|titled tue|\bblz\b|lightning|5-?min|3-?min|1-?min|hyperbullet|chess\.com speed", re.I)
RAPID_RE = re.compile(r"rapid|\brpd\b|active|quick|25-?min|15-?min|champions chess tour|\bcct\b|meltwater|airthings|ftx|legends of chess|carlsen inv|"
                      r"magnus carlsen inv|chessable|opera euro|skilling|goldmoney|aimchess|charity cup|julius baer|nic classic|clutch|"
                      r"global chess league|\bgcl\b|pro league|pro chess|oslo esports|crypto cup|chess24|lindores|tata steel india|"
                      r"grand chess tour.*(?:paris|croatia|leuven|bucharest|superbet).*(?:r&b|rapid)|r&b|rapid & blitz|esports|online|"
                      r"giants|chess classics?\b(?! giants)|mainz|intel|pca-gp|credit suisse|ccas|immopar|melody amber|amber", re.I)
SKIP_RE = re.compile(r"960|fischer random|freestyle|casablanca|man\+comp|advanced|\bleon\b|blind|simul|exhib|consultation|odds|handicap|thematic|computer|engine|"
                     r"correspondence|\bcorr\b", re.I)
ONLINE_RE = re.compile(r"\bINT\b|\.com|\.org|chess24|lichess|internet|online", re.I)
CLOCK_RE = re.compile(r"\b[1-5]\s*[-+|]\s*[0-3]\b")  # "3-0", "1+1": blitz and bullet time controls
MINUTES_RE = re.compile(r"\b(\d{1,2})'")  # "Kosmos m 5'", "Budapest m 30'": the minutes per player
KO_RE = re.compile(r"world cup|wch ko|fide wch|\bko\b|knockout|candidates?.*(?:sf|qf|match)|grand swiss|tiebreak", re.I)


def game_mode(event: str, round_: str, site: str = "") -> str | None:
    """classical, rapid or blitz from the event name, the site (online games are never classical here) and,
    in knockout events, the game's number in its round."""
    if SKIP_RE.search(event):
        return None
    minutes = MINUTES_RE.search(event)
    if minutes:
        return "blitz" if int(minutes.group(1)) <= 10 else "rapid" if int(minutes.group(1)) <= 60 else "classical"
    if BLITZ_RE.search(event) or CLOCK_RE.search(event):
        return "blitz"
    if RAPID_RE.search(event) or ONLINE_RE.search(site):
        return "rapid"
    m = re.match(r"\d+\.(\d+)", round_)
    if m and KO_RE.search(event):
        n = int(m.group(1))
        return "classical" if n <= 2 else "rapid" if n <= 6 else "blitz"
    return "classical"


def load_pgn(name: str, refresh: bool) -> str:
    path = PGN_DIR / f"{name}.zip"
    if refresh or not path.exists():
        req = urllib.request.Request(PGN_URL.format(file=name), headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
            if not body.startswith(b"PK"):  # An error page instead of the zip: keep the saved copy.
                raise OSError("the download is not a zip file")
            PGN_DIR.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            if not path.exists():
                raise
            print(f"warning: could not download {name}.zip ({err}); using the saved copy", file=sys.stderr)
    with zipfile.ZipFile(path) as z:
        return "\n".join(z.read(n).decode("latin-1") for n in z.namelist() if n.lower().endswith(".pgn"))


def parse_h2h(refresh: bool) -> dict:
    patterns = [(key, re.compile(r"^(?:" + pat + r")", re.I)) for key, _, _, _, pat in H2H_PLAYERS]
    who = lambda name: None if "/" in name else next((k for k, p in patterns if p.search(name.strip())), None)
    games = {}
    for key, _, _, file, _ in H2H_PLAYERS:
        for block in re.split(r"\n(?=\[Event )", load_pgn(file, refresh)):
            tags = dict(re.findall(r'\[(\w+) "([^"]*)"\]', block[:2000]))
            white, black = who(tags.get("White", "")), who(tags.get("Black", ""))
            if not white or not black or white == black or tags.get("Result") not in ("1-0", "0-1", "1/2-1/2"):
                continue
            mode = game_mode(tags.get("Event", ""), tags.get("Round", ""), tags.get("Site", ""))
            if not mode:
                continue
            moves = re.sub(r"\{[^}]*\}|\[[^\]]*\]|\s+", " ", block.split("]\n", 1)[-1])[:120]
            uid = (tags.get("Date", "")[:10], white, black, tags.get("Round", ""), moves)
            games[uid] = (white, black, tags["Result"], mode, int((tags.get("Date") or "0")[:4] or 0))
    table = defaultdict(lambda: Counter())
    for white, black, result, mode, year in games.values():
        a, b = sorted((white, black))
        score = {"1-0": white, "0-1": black}.get(result)
        rec = table[(a, b, mode)]
        rec["games"] += 1
        rec["aWins" if score == a else "bWins" if score == b else "draws"] += 1
        rec["first"] = min(rec["first"] or year, year) if year else rec["first"]
        rec["last"] = max(rec["last"], year)
    pairs = [{"a": a, "b": b, "mode": mode, **{k: v for k, v in rec.items()}} for (a, b, mode), rec in sorted(table.items())]
    return {
        "players": [{"key": k, "name": n, "fed": f} for k, n, f, _, _ in H2H_PLAYERS],
        "pairs": pairs,
        "games": len(games),
    }


# ---------- Build and checks ----------

def reigns(events: list[dict], eras: tuple[str, ...], until: int | None = None) -> list[dict]:
    """Title reigns along a lineage: each winner holds the title from the event until the next winner."""
    line = sorted((e for e in events if e["era"] in eras and e["kind"] != "aborted"), key=lambda e: e["year"])
    out = []
    for e in line:
        if not out or out[-1]["name"] != e["winner"]:
            if out:
                out[-1]["to"] = e["year"]
            out.append({"name": e["winner"], "fed": e["winnerFed"], "from": e["year"], "to": None, "events": 0})
        out[-1]["events"] += 1
    if out and until:  # The lineage ended (FIDE's split title was reunified in 2006).
        out[-1]["to"] = until
    elif out:
        out[-1]["to"] = date.today().year
        out[-1]["current"] = True
    return out


def build(refresh: bool) -> dict:
    wcc = parse_wcc(refresh)
    for e in wcc:
        if not e["location"]:
            e["location"] = "Several cities"
        if e["year"] == 1975:
            e["score"] = "Forfeit"
    lineage = reigns(wcc, ("official", "classical"))
    for r in lineage:  # Alekhine died as champion in 1946; the title was vacant until 1948.
        if r["name"] == "Alexander Alekhine" and r["to"] == 1948:
            r["to"] = 1946
    fide_line = reigns(wcc, ("fide",), until=2006)
    women = parse_women(refresh)
    fast, fast_official = parse_fast(refresh)
    number_ones, no1_official = parse_number_ones(refresh)
    data = {
        "meta": {
            "generated": date.today().isoformat(),
            "through": str(max(e["year"] for e in wcc)),
            "sources": [f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}" for t in
                        (WCC_PAGE, WOMEN_PAGE, RAPID_PAGE, BLITZ_PAGE, NO1_PAGE, PEAK_PAGE, OLYMPIAD_PAGE, PRODIGY_PAGE)],
        },
        "worldChampionships": wcc,
        "reigns": lineage,
        "fideReigns": fide_line,
        "women": women,
        "fast": fast,
        "numberOnes": number_ones,
        "peaks": parse_peaks(refresh),
        "olympiad": parse_olympiad(refresh),
        "candidates": simple_winners(refresh, "Candidates Tournament", r"Winners \(since 2011\)", "Winner"),
        "worldCup": simple_winners(refresh, "Chess World Cup", r"Winners", "Winner"),
        "prodigies": parse_prodigies(refresh),
        "h2h": parse_h2h(refresh),
        "_official": {"fast": fast_official, "no1": no1_official},
    }
    feds = set()
    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if k in ("fed", "winnerFed", "runnerUpFed", "gold", "silver", "bronze") and isinstance(x, str):
                    feds.add(x)
                else:
                    walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(data)
    # Codes outside the chess list (Olympiad medallists) fall back to the Olympic nation directory.
    data["federations"] = {c: ({"name": FEDERATIONS[c][0], "flag": FEDERATIONS[c][1]} if c in FEDERATIONS else nation_info(c)) for c in sorted(feds)}
    return data


def validate(data: dict) -> list[str]:
    errors = []
    official = data.pop("_official")
    # Titles per player in rapid and blitz must match the pages' own records tables.
    for key, expected in official["fast"].items():
        got = Counter(c["name"] for r in data["fast"][key] for c in r["champions"])
        diff = {n: (got.get(n, 0), v) for n, v in expected.items() if got.get(n, 0) != v}
        if diff:
            errors.append(f"{key} titles differ from the records table (got, expected): {diff}")
    for key, expected in official["no1"].items():
        got = Counter(m["player"] for m in data["numberOnes"][key])
        # FIDE left Kasparov off its 1994 lists (the PCA split), so the official lists give those 12 months to Karpov;
        # Wikipedia's statistics still count them for Kasparov. Shared months can differ by a few.
        allow = {"Garry Kasparov": 12}
        diff = {n: (got.get(n, 0), v) for n, v in expected.items() if abs(got.get(n, 0) - v) > allow.get(n, 3)}
        if diff:
            errors.append(f"{key} months at No. 1 differ from the statistics table (got, expected): {diff}")
    reign = {r["name"]: r for r in data["reigns"]}
    if reign.get("Emanuel Lasker", {}).get("to") != 1921 or reign.get("Emanuel Lasker", {}).get("from") != 1894:
        errors.append(f"Lasker's reign: {reign.get('Emanuel Lasker')}")
    wins = Counter(e["winner"] for e in data["worldChampionships"] if e["era"] in ("official", "classical") and e["kind"] != "aborted")
    for name, n in {"Garry Kasparov": 6, "Anatoly Karpov": 3, "Magnus Carlsen": 5, "Mikhail Botvinnik": 5, "Emanuel Lasker": 6}.items():
        if wins[name] != n:
            errors.append(f"{name}: {wins[name]} world championship events won, expected {n}")
    women = Counter(e["winner"] for e in data["women"])
    if women["Vera Menchik"] != 8 or women["Ju Wenjun"] < 5:
        errors.append(f"women's titles: Menchik {women['Vera Menchik']}, Ju Wenjun {women['Ju Wenjun']}")
    pairs = {(p["a"], p["b"], p["mode"]): p for p in data["h2h"]["pairs"]}
    kk = pairs.get(("karpov", "kasparov", "classical"))
    # Kasparov 28 wins, Karpov 21, 129 draws in classical games (some exhibitions in the files may add a few).
    if not kk or abs(kk["bWins"] - 28) > 4 or abs(kk["aWins"] - 21) > 4 or abs(kk["draws"] - 129) > 12:
        errors.append(f"Karpov–Kasparov classical: {kk and (kk['aWins'], kk['bWins'], kk['draws'])}, expected about 21–28 with 129 draws")
    unknown = [c for c, f in data["federations"].items() if f["name"] == c]
    if unknown:
        errors.append(f"federations without a name: {unknown}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download the pages and game files")
    args = parser.parse_args()
    data = build(args.refresh)
    errors = validate(data)
    if errors:
        sys.exit("validation failed:\n  " + "\n  ".join(errors))
    if OUTPUT.exists():
        old = json.loads(OUTPUT.read_text(encoding="utf-8"))
        strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}
        if strip(old) == strip(data):
            print(f"{OUTPUT.relative_to(ROOT)} is up to date")
            return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(data['worldChampionships'])} title events, {data['h2h']['games']} head-to-head games")


if __name__ == "__main__":
    main()
