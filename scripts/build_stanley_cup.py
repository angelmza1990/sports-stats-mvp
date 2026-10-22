"""Build the Stanley Cup dataset used by ice-hockey/stanley-cup: every Stanley Cup Final since 1915 (the
Final era: NHA/NHL against the western leagues until 1926, NHL only since 1927), the Conn Smythe
Trophy winners and both head coaches of every Final.

Sources (Wikipedia, CC BY-SA 4.0): "List of Stanley Cup champions" (both Final tables, plus its
appearances tables to check the totals) and "Conn Smythe Trophy". Team names map to today's franchise
through data/nhl/franchises.json.

Usage:
    python3 scripts/build_stanley_cup.py            # cached pages
    python3 scripts/build_stanley_cup.py --refresh  # re-download them
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wikitables as W  # noqa: E402
from build_football_people import header_labels, people_in  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "raw" / "wikipedia" / "nhl"
FRANCHISES = ROOT / "data" / "nhl" / "franchises.json"
OUT_DIR = ROOT / "ice-hockey" / "stanley-cup" / "data"
PAGES = {"cups": "List of Stanley Cup champions", "mvp": "Conn Smythe Trophy"}
CANADIAN = re.compile(r"\b(Montreal|Toronto|Ottawa|Vancouver|Victoria|Calgary|Edmonton|Winnipeg|Quebec|Hamilton)\b")


def page(title: str, refresh: bool) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return W.fetch_raw(title, CACHE / f"{slug}.wiki", refresh, pause=1.5)


def load_franchises() -> tuple[list[dict], dict[str, str]]:
    franchises = json.loads(FRANCHISES.read_text(encoding="utf-8"))["franchises"]
    return franchises, {a: f["id"] for f in franchises for a in f["aliases"]}


def team_name(cell: str, year: int | None = None) -> str:
    link = W.links(cell)
    name = W.plain(link[0][1] or link[0][0]) if link else W.plain(cell)
    name = re.sub(r"\s*\(.*$|[‡^†*#§]+", "", name).strip()
    if name == "Ottawa Senators" and year and year < 1935:
        return "Ottawa Senators (original)"
    return name


def tables_with(text: str, *needles: str) -> list[list[list[dict]]]:
    out = []
    for t in W.all_tables(text):
        labels = [l.lower() for l in header_labels(t)] if t else []
        if all(any(n == l or n in l for l in labels) for n in needles):
            out.append(t)
    return out


def parse_finals(text: str, alias: dict[str, str]) -> list[dict]:
    seasons = {}
    for table in tables_with(text, "year", "winning team", "coach", "games", "losing team"):
        labels = [l.lower() for l in header_labels(table)]
        coach_cols = [i for i, l in enumerate(labels) if l == "coach"]
        for r in table:
            if all(c["header"] for c in r) or len(r) < 6:
                continue
            y = re.search(r"scfy\s*\|\s*(\d{4})", r[0]["text"]) or re.search(r"\b(19|20)\d\d\b", W.plain(r[0]["text"]))
            games = re.search(r"(\d)\s*[–-]\s*(\d)", W.plain(r[3]["text"]))
            if not y or not games or re.search(r"(?i)lockout|not awarded", r[1]["text"]):
                continue  # 1919 (flu) and 2005 (lockout): no Cup awarded
            year = int(y.group(1) if len(y.group(1)) == 4 else y.group(0))
            champ, runner = team_name(r[1]["text"], year), team_name(r[4]["text"], year)
            for n in (champ, runner):
                if n not in alias:
                    raise KeyError(f"unknown team {n!r} ({year}): add it to {FRANCHISES.relative_to(ROOT)}")
            league = re.search(r"\[\[(?:[^\]|]*\|)?(NHA|NHL|PCHA|WCHL|WHL)\]\]", r[1]["text"])
            w, l = sorted(map(int, games.groups()), reverse=True)
            seasons[year] = {
                "year": year, "champion": alias[champ], "championName": champ, "runnerUp": alias[runner], "runnerUpName": runner,
                "result": f"{w}–{l}", "country": "CAN" if CANADIAN.search(champ) else "USA",
                "runnerUpCountry": "CAN" if CANADIAN.search(runner) else "USA",
                "league": league.group(1) if league else "NHL",
                "coach": people_in(r[coach_cols[0]]["text"])[:1] if coach_cols else [],
                "runnerUpCoach": people_in(r[coach_cols[1]]["text"])[:1] if len(coach_cols) > 1 and coach_cols[1] < len(r) else [],
            }
    return [seasons[y] for y in sorted(seasons)]


def parse_mvps(text: str, alias: dict[str, str]) -> dict[int, dict]:
    out = {}
    for table in tables_with(text, "year", "winner", "team", "position"):
        for r in table:
            if all(c["header"] for c in r) or len(r) < 3:
                continue
            y = re.search(r"\b(19|20)\d\d\b", W.plain(r[0]["text"]))
            ppl = people_in(r[1]["text"])
            if y and ppl:
                out[int(y.group())] = {"name": ppl[0][1], "team": alias.get(team_name(r[2]["text"], int(y.group())))}
    return out


def appearance_totals(text: str, alias: dict[str, str]) -> Counter:
    """Wins per franchise from the 'Stanley Cup Final era' appearances tables (active and defunct teams)."""
    start = text.index("Stanley Cup Final era")
    totals = Counter()
    for table in tables_with(text[start:], "apps", "team", "wins", "losses"):
        labels = [l.lower() for l in header_labels(table)]
        tc, wc = labels.index("team"), labels.index("wins")
        for r in table:
            if all(c["header"] for c in r) or len(r) <= max(tc, wc):
                continue
            name = team_name(r[tc]["text"])
            n = re.search(r"nts\s*\|\s*(\d+)", r[wc]["text"]) or re.search(r"(\d+)", W.plain(r[wc]["text"]))
            if n and name in alias:
                totals[alias[name] if name != "Ottawa Senators" or "original" not in r[tc]["text"] else "OTS"] += int(n.group(1))
    return totals


def build(refresh: bool) -> tuple[dict, dict, list[str]]:
    franchises, alias = load_franchises()
    text = page(PAGES["cups"], refresh)
    seasons = parse_finals(text, alias)
    mvps = parse_mvps(page(PAGES["mvp"], refresh), alias)
    for s in seasons:
        m = mvps.get(s["year"])
        s["mvp"] = m["name"] if m else None
        s["mvpOnLoser"] = bool(m) and m["team"] == s["runnerUp"]

    coaches: dict[str, dict] = {}
    for s in seasons:
        for ppl, team, bucket in ((s.pop("coach"), s["champion"], "titles"), (s.pop("runnerUpCoach"), s["runnerUp"], "lost")):
            for k, n in ppl:
                n = re.sub(r"-playing$|\s*\(\d+\)$", "", n).strip()
                c = coaches.setdefault(re.sub(r"[^a-z]", "", k.lower()), {"name": n, "nation": None, "titles": [], "lost": []})
                c[bucket].append({"season": str(s["year"]), "club": team})
    people = {
        "meta": {"generated": date.today().isoformat(), "sources": [f"https://en.wikipedia.org/wiki/{PAGES['cups'].replace(' ', '_')}"],
                 "kind": "cup", "notes": [], "coachesNote": "Early teams were often run by a manager or a playing coach; the list names whoever Wikipedia credits.",
                 "playersNote": None},
        "coaches": sorted(coaches.values(), key=lambda c: (-len(c["titles"]), -len(c["lost"]), c["name"])),
        "players": [], "nations": {},
    }
    data = {
        "meta": {"generated": date.today().isoformat(), "through": seasons[-1]["year"],
                 "sources": [f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}" for t in PAGES.values()]},
        "franchises": [{k: v for k, v in f.items() if k != "aliases"} for f in franchises],
        "seasons": seasons,
    }

    errors = []
    wins = Counter(s["champion"] for s in seasons)
    expected = appearance_totals(text, alias)
    diff = {k: (wins.get(k, 0), expected.get(k, 0)) for k in set(wins) | set(expected) if wins.get(k, 0) != expected.get(k, 0)}
    if diff:
        errors.append(f"Cups per franchise differ from the appearances tables (got, expected): {diff}")
    if wins["MTL"] != 24:
        errors.append(f"Montreal Canadiens: {wins['MTL']} Cups, expected 24")
    years = [s["year"] for s in seasons]
    if sorted(set(range(1915, years[-1] + 1)) - set(years)) != [1919, 2005]:
        errors.append(f"missing Finals: {sorted(set(range(1915, years[-1] + 1)) - set(years))} (expected only 1919 and 2005)")
    no_mvp = [s["year"] for s in seasons if s["year"] >= 1965 and not s["mvp"]]
    if no_mvp:
        errors.append(f"no Conn Smythe winner for {no_mvp}")
    roy = sum(1 for s in seasons if s["mvp"] == "Patrick Roy")
    if roy != 3:
        errors.append(f"Patrick Roy has {roy} Conn Smythes, expected 3")
    bowman = next((c for c in people["coaches"] if c["name"] == "Scotty Bowman"), None)
    if not bowman or len(bowman["titles"]) != 9:
        errors.append(f"Scotty Bowman: {bowman and len(bowman['titles'])} Cups as coach, expected 9")
    return data, people, errors


def write(path: Path, data: dict) -> None:
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}  # noqa: E731
    if old and strip(old) == strip(data):
        print(f"{path.relative_to(ROOT)} is up to date")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="re-download the Wikipedia pages")
    args = ap.parse_args()
    data, people, errors = build(args.refresh)
    if errors:
        sys.exit("validation failed:\n  " + "\n  ".join(errors))
    write(OUT_DIR / "stanley-cup.json", data)
    write(OUT_DIR / "people.json", people)


if __name__ == "__main__":
    main()
