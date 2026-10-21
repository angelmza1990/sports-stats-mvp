"""Build the tennis age records used by tennis/age-records: the youngest and oldest world No. 1s, Grand Slam
champions (every Slam, all time and Open Era), ATP and WTA Finals champions, and the age at which each
player completed the career Grand Slam.

Sources:
  * Wikipedia: the lists of ATP and WTA No. 1s (first and last date at No. 1, with birth dates), the lists
    of Grand Slam singles champions (every champion since 1877, the career Grand Slam tables), the ATP and
    WTA Finals pages, and each tournament's own page for the day it ended.
  * Wikidata: champions' dates of birth.
Birth dates and tournament end dates never change, so they're kept in data/raw/tennis/ and only the
missing ones are looked up, even with --refresh.

Ages are counted on the tournament's last day (the singles final is played on or just before it).

Usage:
    python3 scripts/build_tennis_ages.py            # cached pages
    python3 scripts/build_tennis_ages.py --refresh  # re-download the Wikipedia lists
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wikitables as W  # noqa: E402
from olympic_events import HISTORIC, MORE_TEAMS, TENNIS_COUNTRIES, nation_info  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
WIKI_CACHE = RAW / "wikipedia"
TENNIS_RAW = RAW / "tennis"
BIRTHS = TENNIS_RAW / "birth_dates.json"
END_DATES = TENNIS_RAW / "tournament_end_dates.json"
OUTPUT = ROOT / "tennis" / "age-records" / "data" / "age-records.json"
USER_AGENT = "sports-stats-mvp/1.0 (https://github.com/angelmza1990/sports-stats-mvp)"

TOURS = {
    "atp": {
        "no1": "List of ATP number 1 ranked singles tennis players",
        "slams": "List of Grand Slam men's singles champions",
        "finals": "ATP Finals",
        "finalsName": "ATP Finals",
    },
    "wta": {
        "no1": "List of WTA number 1 ranked singles tennis players",
        "slams": "List of Grand Slam women's singles champions",
        "finals": "WTA Finals",
        "finalsName": "WTA Finals",
    },
}
SLAMS = [("AO", "Australian Open"), ("FR", "Roland Garros"), ("WB", "Wimbledon"), ("US", "US Open")]
MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"])}
MONTH_RE = "|".join(MONTHS)

# Flag names and old codes used in the lists -> IOC codes.
FLAG_FIX = {
    "UK": "GBR", "UKGBI": "GBR", "UNITED KINGDOM OF GREAT BRITAIN AND IRELAND": "GBR", "GREAT BRITAIN": "GBR",
    "UNITED KINGDOM": "GBR", "SER": "SRB", "USA": "USA", "UNITED STATES": "USA", "AUSTRALASIA": "ANZ", "BOHEMIA": "BOH",
    "WEST GERMANY": "FRG", "GERMANY": "GER", "CZECHOSLOVAKIA": "TCH", "SOVIET UNION": "URS", "YUGOSLAVIA": "YUG",
    "SOUTH AFRICA": "RSA", "FRANCE": "FRA", "SPAIN": "ESP", "AUSTRALIA": "AUS", "EGYPT": "EGY", "IRELAND": "IRL",
    "ROMANIA": "ROU", "RUSSIA": "RUS", "NAZI GERMANY": "GER", "WEIMAR REPUBLIC": "GER", "GER1935": "GER",
    "ROM": "ROU", "SWI": "SUI", "NLD": "NED", "CHL": "CHI", "DEU": "GER", "CHE": "SUI", "NZ": "NZL",
}
# Country names (as some flag templates give them) -> IOC codes.
BY_NAME = {name.upper(): code for table in (TENNIS_COUNTRIES, MORE_TEAMS, HISTORIC) for code, (name, _) in table.items()}
# Names written differently where a champion appears without a link.
NAME_ALIASES = {}


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def wiki(title: str, refresh: bool) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return W.fetch_raw(title, WIKI_CACHE / f"{slug}.wiki", refresh, pause=1.5)


def http_json(url: str, data: bytes | None = None) -> dict:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            if err.code not in (429, 503) or attempt == 3:
                raise
            time.sleep(15 * (attempt + 1))
    raise RuntimeError("unreachable")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(data.items())), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def iso(y: int | str, m: int | str, d: int | str) -> str:
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def nation(text: str) -> str | None:
    """IOC code from the first flag template in a cell ({{#invoke:flag|icon|GBR}}, {{flagicon|USA|1912}})."""
    m = re.search(r"\{\{\s*(?:#invoke:flag\s*\|\s*icon|flagicon|flag\s*icon|flagcountry|flag)\s*\|\s*([^|}]*)", text, re.I)
    if not m or not m.group(1).strip():
        return None
    raw = m.group(1).strip().upper()
    return FLAG_FIX.get(raw) or BY_NAME.get(raw) or (raw if len(raw) == 3 else None)


# ---------------------------------------------------------------- birth dates (Wikidata) and end dates


def birth_dates(titles: set[str]) -> dict[str, str | None]:
    """Date of birth by Wikipedia article title; missing ones are looked up and added to the saved copy."""
    saved = load_json(BIRTHS)
    missing = sorted(t for t in titles if t not in saved)
    for i in range(0, len(missing), 50):
        batch = missing[i:i + 50]
        log(f"looking up {len(batch)} birth dates on Wikidata")
        try:
            q = http_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
                "action": "query", "format": "json", "redirects": 1, "prop": "pageprops", "ppprop": "wikibase_item",
                "titles": "|".join(batch)}))["query"]
            alias = {n["from"]: n["to"] for n in q.get("normalized", []) + q.get("redirects", [])}
            qids = {p["title"]: p.get("pageprops", {}).get("wikibase_item") for p in q["pages"].values()}

            def target(t: str) -> str:
                while t in alias:
                    t = alias[t]
                return t

            ids = sorted({v for v in qids.values() if v})
            births = {}
            if ids:
                sparql = ("SELECT ?p ?dob ?prec WHERE { VALUES ?p { " + " ".join(f"wd:{x}" for x in ids) +
                          " } ?p p:P569/psv:P569 [ wikibase:timeValue ?dob; wikibase:timePrecision ?prec ] }")
                res = http_json("https://query.wikidata.org/sparql", urllib.parse.urlencode({"query": sparql, "format": "json"}).encode())
                for b in res["results"]["bindings"]:
                    qid = b["p"]["value"].rsplit("/", 1)[1]
                    if int(b["prec"]["value"]) >= 11:  # Day precision only.
                        births.setdefault(qid, b["dob"]["value"][:10])
            for t in batch:
                saved[t] = births.get(qids.get(target(t)) or "")
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            log(f"warning: could not look up birth dates ({err}); they stay missing")
            break
        save_json(BIRTHS, saved)
        time.sleep(1)
    return {t: saved.get(t) for t in titles}


def parse_end_date(text: str, year: int) -> str | None:
    """The last day of an infobox 'date' such as '21 June – 3 July', 'June 21 – July 3' or 'January 10–14, 1979'."""
    m = re.search(r"^\s*\|\s*dates?\s*=\s*(.+)", text, re.M)
    if not m:
        return None
    s = re.split(r"<ref|<!--", m.group(1))[0]
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\{\{\s*(?:nowrap|nobr)\s*\|", "", s, flags=re.I).replace("}}", " ")
    s = s.replace("&nbsp;", " ").lower()
    years = [int(y) for y in re.findall(r"\b(1[89]\d\d|20\d\d)\b", s)]
    s = re.sub(r"\b(1[89]\d\d|20\d\d)\b", " ", s)
    days = list(re.finditer(r"\b(\d{1,2})\b", s))
    months = [(x.start(), MONTHS[x.group(1)]) for x in re.finditer(rf"\b({MONTH_RE})\b", s)]
    if not days or not months:
        return None
    last = days[-1]
    after = [mo for pos, mo in months if pos > last.start()]
    before = [mo for pos, mo in months if pos < last.start()]
    month = after[0] if after else before[-1]
    return iso(years[-1] if years else year, month, int(last.group(1)))


def fetch_page(title: str) -> str | None:
    """Raw wikitext, following redirects; None if the page doesn't exist."""
    for _ in range(3):
        url = f"https://en.wikipedia.org/w/index.php?title={urllib.parse.quote(title.replace(' ', '_'))}&action=raw"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8")
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return None
            raise
        r = re.match(r"\s*#redirect\s*\[\[([^\]|#]+)", text, re.I)
        if not r:
            return text
        title = r.group(1)
    return None


def end_dates(pages: set[str]) -> dict[str, str | None]:
    """Last day of each tournament page; missing ones are read from Wikipedia and added to the saved copy."""
    saved = load_json(END_DATES)
    missing = sorted(p for p in pages if p not in saved)
    if missing:
        log(f"reading the dates of {len(missing)} tournaments")
    for n, page in enumerate(missing):
        try:
            found = None
            # "2024 US Open" is a disambiguation page; the tennis event is "2024 US Open (tennis)".
            for title in (page, f"{page} (tennis)"):
                text = fetch_page(title)
                found = parse_end_date(text, int(page[:4])) if text else None
                if found:
                    break
            saved[page] = found
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            log(f"warning: could not read {page} ({err}); it stays missing")
            break
        if n % 20 == 19:
            save_json(END_DATES, saved)
        time.sleep(0.5)
    save_json(END_DATES, saved)
    return {p: saved.get(p) for p in pages}


# ---------------------------------------------------------------- Wikipedia lists


def slam_page(ev: str, year: int, december: bool = False) -> str:
    """Wikipedia title of a Slam's page for a given year."""
    if ev == "AO":
        if year == 1977:
            return f"1977 Australian Open ({'December' if december else 'January'})"
        name = "Australasian Championships" if year <= 1926 else "Australian Championships" if year <= 1968 else "Australian Open"
    elif ev == "FR":
        name = "French Championships" if year <= 1967 else "French Open"
    elif ev == "WB":
        name = "Wimbledon Championships"
    else:
        name = "U.S. National Championships" if year <= 1967 else "US Open"
    return f"{year} {name}"


def slam_champions(text: str) -> list[dict]:
    """Every Grand Slam singles champion from the 'Champions by year' table."""
    # Cells written as `rowspan="27" {{n/a|...}}` lack the attribute separator; add it so rowspans apply.
    text = re.sub(r'(^\||\|\|)(\s*rowspan="?\d+"?)\s*(\{\{n/a)', r"\1\2 | \3", text, flags=re.M)
    table = W.table_with_headers(text, "Year", "Wimbledon", "US Open")
    out, seen, labels = [], set(), {}
    ao_1977 = 0
    for row in table:
        if all(c["header"] for c in row):
            continue
        y = re.search(r"\b(18|19|20)\d\d\b", W.plain(row[0]["text"]))
        if not y:
            continue
        year = int(y.group())
        if year == 1977:
            ao_1977 += 1
        for ev, cell in zip([s for s, _ in SLAMS], row[1:5]):
            raw = cell["text"]
            body = re.sub(r"\{\{\s*(?:small|efn)[^{}]*\}\}", "", raw)
            if "n/a" in raw.lower() or "Open Era" in raw or not W.plain(body).strip():
                continue
            link = W.links(body)
            label = re.sub(r"[*†$‡◊§#]", "", W.plain(body)).strip(" '")
            if link:
                labels.setdefault(label, link[0][0])
            if ev == "FR" and (year < 1925 or 1940 <= year <= 1945):  # Club-only and wartime French titles don't count.
                continue
            dec = ev == "AO" and year == 1977 and ao_1977 == 2
            key = (year, ev, dec)
            if key in seen:  # A rowspan repeats the cell on the second 1977 row.
                continue
            seen.add(key)
            out.append({"event": ev, "year": year, "december": dec, "name": label, "article": link[0][0] if link else None,
                        "nation": nation(raw)})
    for c in out:
        if not c["article"]:
            c["article"] = labels.get(c["name"]) or labels.get(NAME_ALIASES.get(c["name"], "")) or NAME_ALIASES.get(c["name"])
    return out


def career_slams(text: str) -> list[dict]:
    """Rows of the 'Career Grand Slam' table: who, the four titles, and the one that completed the set."""
    start = text.index("=== Career Grand Slam ===")
    table = W.parse_table(W.find_table(text[start:], r"Career Grand Slam"))
    rows = []
    for row in table:
        if any(c["header"] for c in row) or len(row) < 5:
            continue
        times = re.search(r"\((\d)\)", W.plain(row[0]["text"]))
        name = re.sub(r"\s*\(\d\)", "", W.plain(re.sub(r"\{\{\s*small\s*\|([^{}]*)\}\}", r"\1", row[0]["text"]))).strip()
        titles, completed = {}, None
        for ev, cell in zip([s for s, _ in SLAMS], row[1:5]):
            link = W.links(cell["text"])
            if not link:
                continue
            page = link[0][0].split(" – ")[0]
            titles[ev] = page
            if "'''" in cell["text"]:
                completed = ev
        link = W.links(row[0]["text"])
        rows.append({"name": name, "article": link[0][0] if link else None, "nation": nation(row[0]["text"]),
                     "set": int(times.group(1)) if times else 1, "titles": titles, "completed": completed})
    return rows


def number_ones(text: str) -> list[dict]:
    """First and last dates at No. 1 with the player's age, from the 'Time span' table."""
    start = text.index("Time span between first and last dates")
    table = W.parse_table(W.find_table(text[start:], r"Time span"))
    out = []
    for row in table:
        if any(c["header"] for c in row) or len(row) < 6:
            continue
        cell = row[1]["text"]
        link = W.links(cell)
        first = re.search(r"\{\{\s*ayd\s*\|\s*(\d{4})\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d{4})\s*\|\s*(\d+)\s*\|\s*(\d+)", row[3]["text"])
        last = re.search(r"\{\{\s*ayd\s*\|\s*(\d{4})\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d{4})\s*\|\s*(\d+)\s*\|\s*(\d+)", row[5]["text"])
        if not link or not first:
            continue
        current = "#ddfddd" in "".join(c.get("attrs", "") if isinstance(c.get("attrs"), str) else "" for c in row) or not last
        last_date = iso(*last.groups()[3:]) if last else None
        if not last:  # The current No. 1: the last date is the list's own "as of" date.
            m = re.search(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4})", W.plain(row[4]["text"]))
            if not m:  # {{date}}: the list is current as of when it was read.
                last_date = date.today().isoformat()
            else:
                mo = [v for k, v in MONTHS.items() if k.startswith(m.group(1).lower())][0]
                last_date = iso(m.group(3), mo, m.group(2))
        out.append({"name": W.plain(link[0][1] or link[0][0]), "article": link[0][0], "nation": nation(cell),
                    "born": iso(*first.groups()[:3]), "first": iso(*first.groups()[3:]), "last": last_date, "current": current})
    return out


def finals_champions(text: str) -> list[dict]:
    """Every singles champion of the ATP or WTA Finals, with the tournament page of each edition."""
    head = re.search(r"^==\s*(?:Past finals|List of finals)\s*==", text, re.M)
    if not head:
        raise ValueError("no finals section")
    table = W.parse_table(W.find_table(text[head.start():], r"Singles"))
    out = []
    for row in table:
        if any(c["header"] for c in row) or len(row) < 3:
            continue
        ylink = W.links(row[0]["text"])
        champ = W.links(row[1]["text"])
        if not ylink or not champ or not nation(row[1]["text"]) and re.search(r"cancel|pandemic", row[1]["text"], re.I):
            continue
        page = re.sub(r"\s+–\s+Singles$", "", ylink[0][0])
        y = re.search(r"\d{4}", page)
        runner = W.links(row[2]["text"]) if len(row) > 2 else []
        out.append({"year": int(y.group()), "page": page, "name": W.plain(champ[0][1] or champ[0][0]), "article": champ[0][0],
                    "nation": nation(row[1]["text"]),
                    "runnerUp": W.plain(runner[0][1] or runner[0][0]) if runner else None,
                    "runnerUpNation": nation(row[2]["text"]) if len(row) > 2 else None,
                    "score": W.plain(row[3]["text"]).replace("–", "-").strip() if len(row) > 3 else None})
    return out


# ---------------------------------------------------------------- build


def build(refresh: bool) -> dict:
    nations: dict[str, dict] = {}
    data = {"meta": {"generated": date.today().isoformat(), "sources": []}, "tours": {}}
    problems = []
    for tour, cfg in TOURS.items():
        no1 = number_ones(wiki(cfg["no1"], refresh))
        slams_text = wiki(cfg["slams"], refresh)
        champs = slam_champions(slams_text)
        careers = career_slams(slams_text)
        finals = finals_champions(wiki(cfg["finals"], refresh))
        data["meta"]["sources"] += [f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}" for t in (cfg["no1"], cfg["slams"], cfg["finals"])]

        for c in champs:
            c["page"] = slam_page(c["event"], c["year"], c["december"])
        pages = {c["page"] for c in champs} | {f["page"] for f in finals} | {p for r in careers for p in r["titles"].values()}
        ends = end_dates(pages)
        births = birth_dates({c["article"] for c in champs + finals + careers if c["article"]})
        for p in no1:  # The No. 1 list gives birth dates itself.
            births.setdefault(p["article"], p["born"])

        def dated(rows: list[dict]) -> list[dict]:
            out = []
            for r in rows:
                born, end = births.get(r["article"] or ""), ends.get(r["page"])
                if not born or not end:
                    problems.append(f"{tour}: no {'birth date' if not born else 'end date'} for {r['name']} ({r['page']})")
                    continue
                out.append({**r, "born": born, "date": end})
            return out

        slam_rows = []
        for c in dated(champs):
            open_era = c["year"] > 1968 or (c["year"] == 1968 and c["event"] != "AO")
            slam_rows.append({"event": c["event"], "year": c["year"], "name": c["name"], "nation": c["nation"],
                              "born": c["born"], "date": c["date"], "openEra": open_era})
        finals_rows = [{"year": f["year"], "name": f["name"], "nation": f["nation"], "born": f["born"], "date": f["date"]}
                       for f in dated(finals)]
        career_rows = []
        for r in careers:
            born = births.get(r["article"] or "")
            if not born:
                # Repeat rows ("Roy Emerson (2)") have no link: reuse the player's first row.
                first = next((x for x in careers if x["name"] == r["name"] and x["article"]), None)
                r["article"], r["nation"] = (first["article"], r["nation"] or first["nation"]) if first else (None, r["nation"])
                born = births.get(r["article"] or "")
            titles = {ev: {"year": int(p[:4]), "date": ends.get(p)} for ev, p in r["titles"].items()}
            if not born or not r["completed"] or any(t["date"] is None for t in titles.values()):
                problems.append(f"{tour}: career Grand Slam row for {r['name']} is incomplete")
                continue
            career_rows.append({"name": r["name"], "nation": r["nation"], "born": born, "set": r["set"], "titles": titles,
                                "completed": r["completed"], "date": titles[r["completed"]]["date"]})
        for r in no1 + slam_rows + finals_rows + career_rows:
            if r["nation"]:
                nations.setdefault(r["nation"], nation_info(r["nation"]))
        data["tours"][tour] = {
            "finalsName": cfg["finalsName"],
            "numberOnes": [{k: p[k] for k in ("name", "nation", "born", "first", "last", "current")} for p in no1],
            "slams": slam_rows,
            "finals": finals_rows,
            "careerSlams": career_rows,
        }
    data["slams"] = [{"key": k, "name": n} for k, n in SLAMS]
    data["nations"] = dict(sorted(nations.items()))
    data["meta"]["problems"] = problems
    return data


def validate(data: dict) -> list[str]:
    errors = []

    def age(born: str, on: str) -> int:
        b, d = date.fromisoformat(born), date.fromisoformat(on)
        return d.year - b.year - ((d.month, d.day) < (b.month, b.day))

    def extreme(rows, key, fn):
        return fn(rows, key=lambda r: (date.fromisoformat(r[key]) - date.fromisoformat(r["born"])).days)

    atp, wta = data["tours"]["atp"], data["tours"]["wta"]
    checks = [
        (extreme(atp["numberOnes"], "first", min)["name"], "Carlos Alcaraz", "youngest ATP No. 1"),
        (extreme(atp["numberOnes"], "last", max)["name"], "Novak Djokovic", "oldest ATP No. 1"),
        (extreme(wta["numberOnes"], "first", min)["name"], "Martina Hingis", "youngest WTA No. 1"),
        (extreme(wta["numberOnes"], "last", max)["name"], "Serena Williams", "oldest WTA No. 1"),
        (extreme(atp["slams"], "date", min)["name"], "Michael Chang", "youngest men's Slam champion"),
        (extreme(atp["slams"], "date", max)["name"], "Arthur Gore", "oldest men's Slam champion"),
        (extreme([r for r in atp["slams"] if r["openEra"]], "date", max)["name"], "Ken Rosewall", "oldest Open Era men's champion"),
        (extreme(wta["slams"], "date", min)["name"], "Lottie Dod", "youngest women's Slam champion"),
        (extreme([r for r in wta["slams"] if r["openEra"]], "date", min)["name"], "Martina Hingis", "youngest Open Era women's champion"),
        (extreme([r for r in wta["slams"] if r["openEra"]], "date", max)["name"], "Serena Williams", "oldest Open Era women's champion"),
        (extreme(atp["finals"], "date", min)["name"], "John McEnroe", "youngest ATP Finals champion"),
        (extreme(atp["finals"], "date", max)["name"], "Novak Djokovic", "oldest ATP Finals champion"),
    ]
    for got, want, what in checks:
        if got != want:
            errors.append(f"{what}: {got}, expected {want}")
    if age(extreme(atp["numberOnes"], "first", min)["born"], extreme(atp["numberOnes"], "first", min)["first"]) != 19:
        errors.append("Alcaraz should have been 19 when he first reached No. 1")
    men = {r["name"] for r in atp["careerSlams"]}
    women = {r["name"] for r in wta["careerSlams"]}
    want_men = {"Fred Perry", "Don Budge", "Rod Laver", "Roy Emerson", "Andre Agassi", "Roger Federer", "Rafael Nadal", "Novak Djokovic",
                "Carlos Alcaraz"}
    if not want_men <= men:
        errors.append(f"career Grand Slam (men) missing {sorted(want_men - men)}")
    want_women = {"Maureen Connolly", "Doris Hart", "Shirley Fry", "Margaret Court", "Billie Jean King", "Chris Evert",
                  "Martina Navratilova", "Steffi Graf", "Serena Williams", "Maria Sharapova"}
    missing = {w for w in want_women if not any(w.split()[-1] in n for n in women)}
    if missing:
        errors.append(f"career Grand Slam (women) missing {sorted(missing)}")
    # Open Era champions must match the Grand Slams pages, which are built from match data.
    for tour, path in (("atp", "tennis/grand-slams/data/grand-slams.json"), ("wta", "tennis/grand-slams-women/data/grand-slams-women.json")):
        names = {"AO": "Australian Open", "FR": "Roland Garros", "WB": "Wimbledon", "US": "US Open"}
        theirs = json.loads((ROOT / path).read_text(encoding="utf-8"))["editions"]
        for ev, label in names.items():
            a = sum(1 for e in theirs if e["event"] == label)
            b = sum(1 for r in data["tours"][tour]["slams"] if r["event"] == ev and r["openEra"])
            if abs(a - b) > 0:
                errors.append(f"{tour} {label}: {b} Open Era champions here, {a} on the Grand Slams page")
    if len(data["meta"]["problems"]) > 6:
        errors.append(f"{len(data['meta']['problems'])} champions without dates: {data['meta']['problems'][:6]}")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="re-download the Wikipedia lists")
    args = ap.parse_args()
    data = build(args.refresh)
    for p in data["meta"]["problems"]:
        log(f"note: {p}")
    errors = validate(data)
    if errors:
        for e in errors:
            log(f"error: {e}")
        sys.exit(1)
    old = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else None
    strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}  # noqa: E731
    if old and strip(old) == strip(data):
        print(f"{OUTPUT.relative_to(ROOT)} is up to date")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    t = data["tours"]
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(t['atp']['slams'])} + {len(t['wta']['slams'])} Slam titles, "
          f"{len(t['atp']['careerSlams'])} + {len(t['wta']['careerSlams'])} career Grand Slams")


if __name__ == "__main__":
    main()
