"""Build the winning-coach datasets for the team sport pages: the FIFA World Cup, the world club champions
(Intercontinental Cup and Club World Cup), the NBA, and every competition on the international team
tournament pages (rugby, basketball, volleyball, field hockey, handball and Olympic football).

Each competition writes a people dataset (the same shape as build_football_people.py):
football/world-cup/data/people.json, football/world-club-champions/data/people.json,
basketball/nba-rings/data/people.json and <sport>/international/data/<key>-people.json.

Sources (Wikipedia, CC BY-SA 4.0):
  * Lists of winning coaches where Wikipedia keeps one: FIFA World Cup, Intercontinental Cup, FIFA Club
    World Cup, FIBA Basketball World Cup, Rugby World Cup (records page) and NBA championship head coaches.
  * Otherwise each edition's own pages: the competition's editions table links every edition; the
    edition's squads or rosters page (or the edition article itself, for older editions) names each
    team's head coach. Only what was found is saved (data/raw/football/team_coaches.json); editions
    already found aren't looked up again.

Every coach's title is matched to the champion of that edition in the page's own dataset.

Usage:
    python3 scripts/build_team_coaches.py            # cached pages; looks up only editions not found yet
    python3 scripts/build_team_coaches.py --refresh  # re-download the lists and retry every edition
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
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_tournaments as BT  # noqa: E402
import wikitables as W  # noqa: E402
from build_football import COUNTRIES, ClubIndex  # noqa: E402
from build_football_people import header_labels, key, nation, page, people_in, strip  # noqa: E402
from olympic_events import nation_info  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FOUND = ROOT / "data" / "raw" / "football" / "team_coaches.json"
USER_AGENT = "sports-stats-mvp/1.0 (https://github.com/angelmza1990/sports-stats-mvp)"

FOLDERS = {
    "rugby": "rugby/international", "basketball": "basketball/international", "volleyball": "volleyball/international",
    "hockey": "hockey/international", "handball": "handball/international", "football": "football/olympics",
}
# Lists of winning coaches: dataset -> (Wikipedia title, needles that identify the table).
LISTS = {
    "rugby-wc-men": ("Records and statistics of the Rugby World Cup", ("winning coach",)),
    "basketball-wc-men": ("FIBA Basketball World Cup winning head coaches", ("head coach",)),
}
# Known titles each dataset must reproduce: (coach, titles).
EXPECT = {
    "world-cup": ("Vittorio Pozzo", 2),
    "world-club-champions": ("Carlos Bianchi", 3),
    "nba": ("Phil Jackson", 11),
    "rugby-wc-men": ("Jake White", 1),
    "basketball-wc-men": ("Mike Krzyzewski", 2),
    "basketball-olympics-men": ("Mike Krzyzewski", 3),
    "handball-wc-men": ("Nikolaj Jacobsen", 4),
    "hockey-olympics-men": ("Shane McLeod", 1),
    "volleyball-olympics-men": ("Bernardo Rezende", 2),
}
# Other names teams go by in squads pages.
TEAM_NAMES = {
    "USA": ["United States", "USA"], "URS": ["Soviet Union", "USSR"], "FRG": ["West Germany", "Germany"], "GDR": ["East Germany"],
    "TCH": ["Czechoslovakia"], "YUG": ["Yugoslavia", "FR Yugoslavia", "Serbia and Montenegro"], "FRY": ["FR Yugoslavia", "Yugoslavia"],
    "SCG": ["Serbia and Montenegro"], "EUN": ["Unified Team"], "GBR": ["Great Britain"], "KOR": ["South Korea", "Korea"],
    "PRK": ["North Korea"], "CHN": ["China"], "ROC": ["ROC", "Russian Olympic Committee"], "RSA": ["South Africa"],
    "NED": ["Netherlands", "Holland"], "IRL": ["Ireland"], "CIS": ["CIS", "Unified Team"], "GER": ["Germany", "West Germany"],
}
VALUE = (r"\s*'*\s*(?::|=)\s*'*\s*\*?\s*(\{\{\s*player\s*\|[^{}]*\}\}|(?:\{\{[^{}]*\}\}\s*)*"
         r"(?:\[\[[^\]]+\]\]|\[https?://\S+\s+[^\]]+\]|[A-ZÀ-Þ][^\n|<(\[{}]{2,40}))")
# Most specific label first: "Head coach" beats "Coach", which beats "Manager" (but never a team or general manager).
COACH_RES = [re.compile(r"(?i)head[\s_]*coach" + VALUE), re.compile(r"(?i)(?<!assistant )(?<!assistant_)\bcoach" + VALUE),
             re.compile(r"(?i)(?<!team )(?<!general )\b(?:manager|trainer|selectionneur)" + VALUE)]
COACH_RE = re.compile(r"(?i)(?:head[\s_]*coach|coach|manager|trainer|selectionneur)" + VALUE)
TEAM_FLAG = re.compile(r"\{\{\s*(?:flagIOC|flagIOCteam|bk|bkw|vb|vbw|fh|fhw|hb|hbw|fb|fbw|ru|ruw)\s*\|\s*([A-Z]{3})\b")


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def fetch(title: str, lang: str = "en") -> str | None:
    """Raw wikitext, following redirects; None if missing."""
    for _ in range(3):
        url = f"https://{lang}.wikipedia.org/w/index.php?title={urllib.parse.quote(title.replace(' ', '_'))}&action=raw"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8")
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return None
            raise
        time.sleep(0.4)
        r = re.match(r"\s*#redirect\s*\[\[([^\]|#]+)", text, re.I)
        if not r:
            return text
        title = r.group(1)
    return None


# ---------------------------------------------------------------- coaches from edition pages


def coach_table(text: str, names: list[str], code: str) -> str | None:
    """A table of every team's coach ("Team | Coach"): the cell for this team."""
    for table in W.all_tables(text):
        labels = header_labels(table) if table else []
        ccol = next((i for i, l in enumerate(labels) if re.fullmatch(r"(head )?coach|manager", l.strip())), None)
        if ccol is None or len(labels) > 8:
            continue
        for r in table:
            if all(c["header"] for c in r) or len(r) <= ccol:
                continue
            row = " ".join(c["text"] for c in r[:ccol])
            if (re.search(rf"\|\s*{code}\b", row) or any(re.search(rf"\b{re.escape(n)}\b", W.plain(row)) for n in names)) \
                    and "(" not in W.plain(r[ccol]["text"]):
                return r[ccol]["text"]
    return None


def team_sections(text: str, names: list[str], code: str) -> list[str]:
    """Pieces of a squads page (or edition article) about one team: its section, its table row or its line."""
    pieces = []
    # Rosters kept in their own templates ("{{2018 ... United States team roster}}").
    for m in re.finditer(r"\{\{\s*([^{}|]*(?:team roster|squad)[^{}|]*)\}\}", text, re.I):
        if any(n.lower() in m.group(1).lower() for n in names):
            sub = fetch(f"Template:{m.group(1).strip()}")
            if sub:
                pieces.append(sub[:12000])
    alt = "|".join(re.escape(n) for n in names)
    for m in re.finditer(rf"^(=+)\s*[^\n]*?\b(?:{alt})\b[^\n]*?\1\s*$", text, re.M):
        if re.search(r"\bvs?\.?\s|\s[–—-]\s|\d", m.group(0)):  # a match ("Japan vs Soviet Union"), not the team
            continue
        end = re.search(r"^=+[^=\n]+=+\s*$", text[m.end():], re.M)
        piece = text[m.end(): m.end() + (end.start() if end else 6000)][:8000]
        pieces.append(piece)
        # A section that only points to the team's own article ({{main|1996 United States men's Olympic basketball team}}).
        for t in re.findall(r"\{\{\s*main\s*\|([^{}|]+)", piece[:400], re.I):
            if not re.search(r"\d{4}", t):  # the team's own article for that year, not the national team's
                continue
            sub = fetch(t.strip())
            if sub:
                pieces.append(sub[:6000])
    flag = rf"\{{\{{\s*(?:flagIOC|flagIOCteam|flagIOC2team|bk|bkw|vb|vbw|fh|fhw|hb|hbw|fb|fbw|fb-rt|ru|ruw|flag|flagcountry|flagicon|flagu|fba)\s*\|\s*{code}\b"
    for m in re.finditer(rf"(?im)(?:^#?\s*'''\s*\[?\[?(?:{alt})\b|{flag})", text):
        end = re.search(r"\n\|-|\n=+|\n#|<section begin|\n\|(?![-}])(?!\s*[a-z_0-9]+\s*=)|\|\|", text[m.end():])
        piece = text[m.start(): m.end() + (end.start() if end else 3000)][:4000]
        # Another team's flag before the coach means the piece ran into the next team.
        cm = COACH_RE.search(piece)
        if cm and any(c != code for c in TEAM_FLAG.findall(piece[: cm.start()])):
            continue
        pieces.append(piece)
    return pieces


def coach_in(pieces: list[str]) -> tuple[str, str, str | None] | None:
    for piece in pieces:
        m = next((x for x in (r.search(piece) for r in COACH_RES) if x), None)
        if m:
            cell = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", m.group(1))
            ppl = people_in(cell)
            linked = bool(W.links(cell))
            if ppl and len(ppl[0][1]) > 3 and not re.search(r"(?i)assistant|^coach", ppl[0][1]) and (linked or " " in ppl[0][1]):
                return ppl[0][0], ppl[0][1], nation(cell)
    return None


def edition_links(cfg: dict) -> dict[int, str]:
    spec = cfg["editions"]
    grid = BT.nth_table(BT.page(spec["page"], False), spec["needles"], spec["nth"])
    out = {}
    for row in grid[1:]:
        for c in row[:3]:
            m = re.search(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)", W.plain(c["text"]))
            if m:
                link = next((t for t, _ in W.links(c["text"]) if m.group(1) in t), None)
                if link and int(m.group(1)) not in out:
                    out[int(m.group(1))] = link
                break
    return out


def candidates(link: str, gender: str) -> list[tuple[str, str]]:
    """Pages that may name the coaches for an edition, most specific first: squads/rosters, tournament, edition."""
    out, seen = [], set()

    def add(title: str) -> str | None:
        if title in seen:
            return None
        seen.add(title)
        text = fetch(title)
        if text:
            out.append((title, text))
        return text

    other = "Women's" if gender == "Men" else "Men's"
    text = add(link)
    if not text:
        return out
    year = re.search(r"\d{4}", link).group()
    tourn = [t for t, _ in W.links(text) if re.search(rf"{gender}'s (?:tournament|competition)$", t) and year in t]
    for t in tourn[:1]:
        sub = add(t)
        if sub:
            text += "\n" + sub
    linked = [t for t, _ in W.links(text)]
    # {{Main|... squads}} and similar hatnotes aren't links.
    for m in re.finditer(r"\{\{\s*(?:main|see also|further|details)\s*\|([^{}]+)\}\}", text, re.I):
        linked += [a.strip() for a in m.group(1).split("|") if a.strip() and "=" not in a]
    rosters = [t for t in linked if re.search(r"(?i)squads?|rosters?", t) and other not in t and year in t
               and not re.search(r"(?i)qualif|category:", t)]
    base = re.sub(r" – (?:Men|Women)'s tournament$", "", link)
    guesses = [f"{link} squads", f"{base} – {gender}'s team rosters", f"{base} – {gender}'s team squads", f"{link} rosters"]
    for t in list(dict.fromkeys(rosters[:2] + guesses)):
        if len(out) >= 4:
            break
        add(t)
    # Most specific first.
    out.sort(key=lambda p: 0 if re.search(r"(?i)squad|roster", p[0]) else 1 if "tournament" in p[0] else 2)
    return out


SPORT_TEAM = {"handball": "national handball team", "basketball": "national basketball team", "volleyball": "national volleyball team",
              "hockey": "national field hockey team", "rugby": "national rugby union team", "football": "national football team"}
EXCLUDE_LINK = re.compile(r"(?i)national|team|olympi|championship|world cup|league|cup\b|federation|association|club|\bfc\b|"
                          r"^\d{4}|^(file|image|category|datei|fichier|bild):|games|tournament|^list of|nationalmannschaft|"
                          r"équipe|selección|nazionale|weltmeisterschaft|championnat|jeux|spiele|meisterschaft|coupe|liga")
COACH_HEADING = r"coach|manager|trainer|staff|sélectionneur|entraîneur|entrenador|allenator|técnico"
_history: dict[str, list] = {}


def tenure_rows(text: str) -> list[tuple[int, int, str, str, str | None]]:
    """(from, to, key, name, nation) for each coach in a national team article's coaching history section."""
    out = []
    for h in re.finditer(rf"^(=+)\s*([^=\n]*?(?:{COACH_HEADING})[^=\n]*?)\s*\1\s*$", text, re.M | re.I):
        level = len(h.group(1))
        end = re.search(rf"^={{1,{level}}}[^=\n]+=+\s*$", text[h.end():], re.M)
        body = text[h.end(): h.end() + (end.start() if end else len(text))]
        units = []
        # German articles sometimes put the period and coach in the heading: "1953–1958, Trainer: Alberto San Román".
        named = re.search(r"(?i)trainer\s*:\s*([^,\n]+)", h.group(2))
        if named and re.search(r"\d{4}", h.group(2)):
            units.append(f"{h.group(2).split('Trainer')[0]} [[{named.group(1).strip()}]]")
        for table in W.all_tables(body):
            units += ["||".join(c["text"] for c in r) for r in table if not all(c["header"] for c in r)]
        units += [l for l in body.splitlines() if l.lstrip().startswith(("*", "#"))]
        for u in units:
            plain = W.plain(strip(u))
            m = re.search(r"\b(19\d\d|20\d\d)\s*(?:[–—-]\s*(19\d\d|20\d\d|\d{2}|present|now|current|)?)?", plain, re.I)
            if not m:
                continue
            a = int(m.group(1))
            b_raw = m.group(2)
            if b_raw is None:
                b = a
            elif b_raw == "" or re.match(r"(?i)present|now|current", b_raw):
                b = 9999
            elif len(b_raw) == 2:
                b = int(str(a)[:2] + b_raw)
            else:
                b = int(b_raw)
            people = [(t, W.plain(x or t)) for t, x in W.links(strip(u)) if not EXCLUDE_LINK.search(t)]
            if people and b >= a:
                out.append((a, b, people[0][0], people[0][1], nation(u)))
    return out


def langlinks(title: str) -> dict[str, str]:
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "query", "format": "json", "prop": "langlinks", "lllimit": 500, "redirects": 1, "titles": title})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        pages = json.loads(resp.read().decode("utf-8"))["query"]["pages"]
    return {l["lang"]: l["*"] for p in pages.values() for l in p.get("langlinks", []) if l["lang"] in ("de", "fr", "es", "it")}


def english_titles(lang: str, titles: list[str]) -> dict[str, str]:
    """English article titles of pages on another Wikipedia (only those that have one)."""
    out = {}
    uniq = sorted(set(titles))
    for i in range(0, len(uniq), 50):
        url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "query", "format": "json", "prop": "langlinks", "lllang": "en", "lllimit": 500, "redirects": 1,
             "titles": "|".join(uniq[i:i + 50])})
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            q = json.loads(resp.read().decode("utf-8"))["query"]
        back = {}
        for n in q.get("normalized", []) + q.get("redirects", []):
            back[n["to"]] = back.get(n["from"], n["from"])
        for p in q["pages"].values():
            for l in p.get("langlinks", []):
                out[back.get(p["title"], p["title"])] = l["*"]
                out[p["title"]] = l["*"]
    return out


def history_rows(title: str) -> tuple[list, str]:
    """Coaching history of a national team: the English article, else its German, French, Spanish or Italian one."""
    if title not in _history:
        text = fetch(title)
        rows, src = (tenure_rows(text) if text else []), title
        if text and not rows:
            for lang, t in langlinks(title).items():
                other = fetch(t, lang)
                rows = tenure_rows(other) if other else []
                if rows:
                    src = f"{lang}:{t}"
                    # Coaches by their English article, so names match the English sources.
                    en = english_titles(lang, [r[2] for r in rows])
                    rows = [(a, b, en.get(k, k), re.sub(r"\s*\([^)]*\)$", "", en[k]) if k in en else n, nat) for a, b, k, n, nat in rows]
                    break
        _history[title] = (rows, src)
    return _history[title]


def history_coach(sport: str, gender: str, code: str, names: list[str], year: int) -> tuple[str, str, str | None, str] | None:
    for n in names:
        title = f"{n} {'women' if gender == 'Women' else 'men'}'s {SPORT_TEAM[sport]}"
        if sport == "football":
            title = f"{n} {'women' + chr(39) + 's ' if gender == 'Women' else ''}national football team"
        hist, src = history_rows(title)
        rows = [r for r in hist if r[0] <= year <= r[1]]
        if len({r[2] for r in rows}) == 1:  # a handover that year is ambiguous
            r = rows[0]
            return r[2], r[3], r[4], src
    return None


def crawl(key_: str, cfg: dict, editions: list[dict], teams: dict, refresh: bool) -> dict[str, dict]:
    found = json.loads(FOUND.read_text(encoding="utf-8")) if FOUND.exists() else {}
    mine = found.setdefault(key_, {})
    links = edition_links(cfg)
    for e in editions:
        y = str(e["year"])
        if y in mine and mine[y] and not refresh:
            continue
        link = links.get(e["year"])
        if not link:
            continue
        code = e["champion"]
        names = TEAM_NAMES.get(code, []) + [teams.get(code, {}).get("name", code)]
        hit = None
        for title, text in candidates(link, cfg["gender"]):
            hit = coach_in(team_sections(text, names, code))
            cell = None if hit else coach_table(text, names, code)
            hit = hit or (coach_in([f"coach: {cell}"]) if cell else None)
            if hit:
                mine[y] = {"key": hit[0], "name": hit[1], "nation": hit[2], "team": code, "page": title}
                break
        if not hit and cfg["sport"] != "football":
            hit = history_coach(cfg["sport"], cfg["gender"], code, names, e["year"])
            if hit:
                mine[y] = {"key": hit[0], "name": hit[1], "nation": hit[2], "team": code, "page": hit[3], "from": "history"}
        if not hit:
            mine[y] = None
        FOUND.parent.mkdir(parents=True, exist_ok=True)
        FOUND.write_text(json.dumps(found, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return {y: v for y, v in mine.items() if v}


# ---------------------------------------------------------------- coaches from lists


def list_rows(text: str, needles: tuple) -> list[dict]:
    out = []
    for table in W.all_tables(text):
        labels = header_labels(table) if table else []
        if not table or not all(any(n in l for l in labels) for n in needles):
            continue
        ycol = next((i for i, l in enumerate(labels) if re.search(r"^(year|tournament|season|edition)", l)), 0)
        ccol = next(i for i, l in enumerate(labels) if re.search(r"coach|manager", l) and "captain" not in l)
        tcol = next((i for i, l in enumerate(labels) if re.search(r"club|team|champion", l) and i != ccol), None)
        if tcol is None:
            tcol = next((i for i, l in enumerate(labels) if re.search(r"^nation$|^country$", l) and i != ccol), None)
        ncol = next((i for i, l in enumerate(labels) if "nationality" in l), None)
        for r in table:
            if all(c["header"] for c in r) or len(r) <= max(ycol, ccol):
                continue
            ytext = W.plain(r[ycol]["text"])
            if len(re.findall(r"\b(?:18|19|20)\d\d\b", ytext)) > 1:  # summary tables ("1994, 2000, 2003")
                continue
            y = re.search(r"\b(18|19|20)\d\d\b", ytext)
            ppl = people_in(r[ccol]["text"])
            if not y or not ppl:
                continue
            out.append({"year": int(y.group()), "coaches": ppl,
                        "nation": nation(r[ncol]["text"]) if ncol is not None and ncol < len(r) else nation(r[ccol]["text"]),
                        "teamCell": r[tcol]["text"] if tcol is not None and tcol < len(r) else ""})
    return out


# ---------------------------------------------------------------- output


_canon: dict[str, str] = {}


def canonical(titles: list[str]) -> dict[str, str]:
    """English Wikipedia's target for each title (redirects resolved), so one coach has one key."""
    todo = sorted({t for t in titles if t and t not in _canon})
    for i in range(0, len(todo), 50):
        url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "query", "format": "json", "redirects": 1, "titles": "|".join(todo[i:i + 50])})
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                q = json.loads(resp.read().decode("utf-8"))["query"]
        except (urllib.error.URLError, TimeoutError, OSError):
            break
        step = {n["from"]: n["to"] for n in q.get("normalized", []) + q.get("redirects", [])}
        missing = {p["title"] for p in q["pages"].values() if "missing" in p}
        for t in todo[i:i + 50]:
            x = t
            for _ in range(3):
                x = step.get(x, x)
            _canon[t] = t if x in missing else x
    return {t: _canon.get(t, t) for t in titles}


def people_data(entries: list[dict], sources: list[str], total: int, note: str | None = None) -> dict:
    """entries: [{season, club, coaches:[(key, name)], nation}] -> the people.json shape."""
    canon = canonical([k for e in entries for k, _ in e["coaches"]])

    def display(k: str, n: str) -> str:
        """The English article's title for linked names ("Zé Roberto" -> "José Roberto Guimarães"), else as written."""
        c = canon.get(k, k)
        return re.sub(r"\s*\([^)]*\)$", "", c) if (k != n or c != k) else n
    entries = [{**e, "coaches": [(canon.get(k, k), display(k, n)) for k, n in e["coaches"]]} for e in entries]
    coaches: dict[str, dict] = {}
    for e in entries:
        for k, n in e["coaches"]:
            p = coaches.setdefault(key(k), {"name": n, "id": k, "nation": None, "titles": [], "lost": []})
            p["nation"] = p["nation"] or e["nation"]
            p["titles"].append({"season": e["season"], "club": e["club"]})
    coach_list = sorted(coaches.values(), key=lambda p: (-len(p["titles"]), p["name"]))
    nations = {}
    for c in [p["nation"] for p in coach_list if p["nation"]]:
        name_, flag = COUNTRIES.get(c) or (nation_info(c)["name"], nation_info(c)["flag"])
        nations[c] = {"name": name_, "flag": flag}
    known = len(entries)
    return {
        "meta": {"generated": date.today().isoformat(), "sources": sources, "kind": "league", "notes": [],
                 "coachesNote": note or (None if known == total else f"Coach found for {known} of {total} titles."),
                 "playersNote": None, "coverage": [known, total]},
        "coaches": coach_list, "players": [], "nations": dict(sorted(nations.items())),
    }


def write(path: Path, data: dict) -> None:
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    strip_gen = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}  # noqa: E731
    if old and strip_gen(old) == strip_gen(data):
        print(f"{path.relative_to(ROOT)} is up to date")
        return
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}: {len(data['coaches'])} coaches, {data['meta']['coverage'][0]} of {data['meta']['coverage'][1]} titles")


def check(name: str, data: dict, errors: list[str]) -> bool:
    if name not in EXPECT:
        return True
    who, n = EXPECT[name]
    got = next((len(p["titles"]) for p in data["coaches"] if key(who) in (key(p["name"]), key(p.get("id", "")))), 0)
    if got != n:
        errors.append(f"{name}: {who} has {got} titles, expected {n}")
        return False
    return True


def wiki_url(title: str) -> str:
    return f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"


def build_world_cup(refresh: bool, errors: list[str]) -> None:
    d = json.loads((ROOT / "football/world-cup/data/world-cup.json").read_text(encoding="utf-8"))
    title = "List of FIFA World Cup winning managers"
    rows = {r["year"]: r for r in list_rows(page("en", title, refresh), ("winning manager",))}
    entries = []
    for e in d["editions"]:
        r = rows.get(e["year"])
        if e.get("champion") and r:
            entries.append({"season": str(e["year"]), "club": e["champion"], "coaches": r["coaches"], "nation": r["nation"]})
    data = people_data(entries, [wiki_url(title)], sum(1 for e in d["editions"] if e.get("champion")))
    if check("world-cup", data, errors):
        write(ROOT / "football/world-cup/data/people.json", data)


def build_club_world(refresh: bool, errors: list[str]) -> None:
    d = json.loads((ROOT / "football/world-club-champions/data/world-club-champions.json").read_text(encoding="utf-8"))
    clubs = ClubIndex()
    titles = ["List of Intercontinental Cup winning managers", "List of FIFA Club World Cup winning managers"]
    rows = []
    for t in titles:
        rows += list_rows(page("en", t, refresh), ("manager",))
    entries, used = [], set()
    for r in rows:
        cid = clubs.resolve(r["teamCell"], None) if W.links(r["teamCell"]) else None
        label = key(W.plain(strip(r["teamCell"])))
        cands = [f for f in d["finals"] if f["year"] == r["year"] and id(f) not in used]
        pick = next((f for f in cands if f["champion"] == cid), None) or next(
            (f for f in cands if label and (key(d["clubs"][f["champion"]]["name"]) in label or label in key(d["clubs"][f["champion"]]["name"]))), None)
        if not pick and len(cands) == 1:
            pick = cands[0]
        if pick:
            used.add(id(pick))
            comp = {"IC": "Intercontinental Cup", "FCWC": "Club World Cup", "FIC": "FIFA Intercontinental Cup"}.get(pick["competition"], pick["competition"])
            entries.append({"season": f"{pick['season']} {comp}", "club": pick["champion"], "coaches": r["coaches"], "nation": r["nation"]})
    data = people_data(entries, [wiki_url(t) for t in titles], len(d["finals"]))
    ok = check("world-club-champions", data, errors)
    if data["meta"]["coverage"][0] < 0.9 * len(d["finals"]):
        errors.append(f"world club champions: coaches for {data['meta']['coverage'][0]} of {len(d['finals'])} finals")
        ok = False
    if ok:
        write(ROOT / "football/world-club-champions/data/people.json", data)


def build_nba(refresh: bool, errors: list[str]) -> None:
    d = json.loads((ROOT / "basketball/nba-rings/data/nba-rings.json").read_text(encoding="utf-8"))
    title = "List of NBA championship head coaches"
    text = page("en", title, refresh)
    table = next(t for t in W.all_tables(text) if any("coach" in l for l in header_labels(t)))
    labels = header_labels(table)
    ccol = next(i for i, l in enumerate(labels) if "coach" in l)
    tcol = next(i for i, l in enumerate(labels) if "team" in l)
    by_year = {s["year"]: s for s in d["seasons"]}
    entries = []
    for r in table:
        if all(c["header"] for c in r) or len(r) <= max(ccol, tcol):
            continue
        ppl = people_in(r[ccol]["text"])
        if not ppl:
            continue
        name = re.sub(r"[*^†‡]+", "", ppl[0][1]).strip()
        for y in re.findall(r"\b(19[4-9]\d|20\d\d)\b", W.plain(r[tcol]["text"])):
            s = by_year.get(int(y))
            if s:
                entries.append({"season": str(s["year"]), "club": s["champion"], "coaches": [(ppl[0][0], name)], "nation": "USA"})
    # The list has no nationality column; every NBA championship coach has been American.
    data = people_data(entries, [wiki_url(title)], len(d["seasons"]))
    if check("nba", data, errors):
        write(ROOT / "basketball/nba-rings/data/people.json", data)


def build_tournament(key_: str, refresh: bool, errors: list[str]) -> None:
    cfg = BT.COMPETITIONS[key_]
    folder = FOLDERS[cfg["sport"]] if not (cfg["sport"] == "football") else FOLDERS["football"]
    d = json.loads((ROOT / folder / "data" / f"{key_}.json").read_text(encoding="utf-8"))
    eds = [e for e in d["editions"] if e.get("champion")]
    entries, sources = [], []
    if key_ in LISTS:
        title, needles = LISTS[key_]
        rows = {r["year"]: r for r in list_rows(page("en", title, refresh), needles)}
        sources.append(wiki_url(title))
        for e in eds:
            r = rows.get(e["year"])
            if r:
                entries.append({"season": str(e["year"]), "club": e["champion"], "coaches": r["coaches"], "nation": r["nation"]})
    else:
        found = crawl(key_, cfg, eds, d["teams"], refresh)
        for e in eds:
            f = found.get(str(e["year"]))
            if f and f["team"] == e["champion"]:
                entries.append({"season": str(e["year"]), "club": e["champion"], "coaches": [(f["key"], f["name"])], "nation": f["nation"]})
                sources.append(wiki_url(f["page"]))
        sources = sorted(set(sources))[:3] + (["…"] if len(set(sources)) > 3 else [])
        sources = [s for s in sources if s != "…"]
    data = people_data(entries, sources, len(eds))
    ok = check(key_, data, errors)
    known, total = data["meta"]["coverage"]
    if known < 0.4 * total:
        errors.append(f"{key_}: coaches for only {known} of {total} titles")
        ok = False
    if ok:
        write(ROOT / folder / "data" / f"{key_}-people.json", data)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="re-download the lists and retry every edition")
    ap.add_argument("--only", help="one dataset key (world-cup, world-club-champions, nba or a tournament key)")
    args = ap.parse_args()
    errors: list[str] = []
    jobs = {"world-cup": build_world_cup, "world-club-champions": build_club_world, "nba": build_nba}
    for k, fn in jobs.items():
        if not args.only or args.only == k:
            fn(args.refresh, errors)
    for k in BT.COMPETITIONS:
        if not args.only or args.only == k:
            build_tournament(k, args.refresh, errors)
    for e in errors:
        log(f"error: {e}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
