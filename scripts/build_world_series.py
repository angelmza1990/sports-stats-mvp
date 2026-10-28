"""Build the World Series dataset used by baseball/world-series: every World Series since 1903, the
league of both teams, the World Series MVP (awarded since 1955) and both managers of every Series.

Sources (Wikipedia, CC BY-SA 4.0): "List of World Series champions" (the results table, plus its
appearances table to check the totals) and "World Series Most Valuable Player Award". Team names map to
today's franchise through data/mlb/franchises.json.

Usage:
    python3 scripts/build_world_series.py            # cached pages
    python3 scripts/build_world_series.py --refresh  # re-download them
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
CACHE = ROOT / "data" / "raw" / "wikipedia" / "mlb"
FRANCHISES = ROOT / "data" / "mlb" / "franchises.json"
OUT_DIR = ROOT / "baseball" / "world-series" / "data"
PAGES = {"series": "List of World Series champions", "mvp": "World Series Most Valuable Player Award"}
# The results table shades each team by league: red for the American League, blue for the National League.
LEAGUE_BG = {"#fcc": "AL", "#d0e7ff": "NL"}
PITCHER = re.compile(r"(?i)pitcher")


def page(title: str, refresh: bool) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return W.fetch_raw(title, CACHE / f"{slug}.wiki", refresh, pause=1.5)


def load_franchises() -> tuple[list[dict], dict[str, str]]:
    franchises = json.loads(FRANCHISES.read_text(encoding="utf-8"))["franchises"]
    return franchises, {a: f["id"] for f in franchises for a in f["aliases"]}


def team_name(cell: str) -> str:
    link = W.links(cell)
    name = W.plain(link[0][1] or link[0][0]) if link else W.plain(cell)
    return re.sub(r"\s*\(.*$|[‡^†*#§]+", "", name).strip()


def league_of(cell: dict) -> str | None:
    m = re.search(r"background:\s*(#[0-9a-f]+)", cell["attrs"], re.I)
    return LEAGUE_BG.get(m.group(1).lower()) if m else None


def year_of(text: str) -> int | None:
    m = re.search(r"wsy\s*\|\s*(\d{4})", text) or re.search(r"\b(?:19|20)\d\d\b", W.plain(text))
    return int(m.group(1) if m.groups() else m.group()) if m else None


def parse_series(text: str, alias: dict[str, str]) -> list[dict]:
    table = next(t for t in W.all_tables(text) if header_labels(t)[:2] == ["year", "winning team"])
    out = {}
    for r in table:
        if all(c["header"] for c in r) or len(r) < 6 or "not played" in r[1]["text"]:
            continue
        year = year_of(r[0]["text"])
        games = re.findall(r"\d+", W.plain(re.sub(r"\{\{ref label[^{}]*\}\}", "", r[3]["text"])))
        if not year or len(games) < 2:
            continue
        champ, runner = team_name(r[1]["text"]), team_name(r[4]["text"])
        for n in (champ, runner):
            if n not in alias:
                raise KeyError(f"unknown team {n!r} ({year}): add it to {FRANCHISES.relative_to(ROOT)}")
        w, l = int(games[0]), int(games[1])
        out[year] = {
            "year": year, "champion": alias[champ], "championName": champ, "runnerUp": alias[runner], "runnerUpName": runner,
            "result": f"{w}–{l}", "ties": int(games[2]) if len(games) > 2 else 0, "bestOf": 2 * w - 1,
            "league": league_of(r[1]), "runnerUpLeague": league_of(r[4]),
            "coach": people_in(r[2]["text"])[:1], "runnerUpCoach": people_in(r[5]["text"])[:1],
        }
    return [out[y] for y in sorted(out)]


def parse_mvps(text: str, alias: dict[str, str]) -> dict[int, list[dict]]:
    table = next(t for t in W.all_tables(text) if header_labels(t)[:3] == ["year", "player", "team"])
    out: dict[int, list[dict]] = {}
    for r in table:
        if all(c["header"] for c in r) or len(r) < 4:
            continue
        year, ppl = year_of(r[0]["text"]), people_in(re.sub(r"\{\{sup\|.*?\}\}\}?", "", r[1]["text"]))
        if year and ppl:
            out.setdefault(year, []).append({
                "name": ppl[0][1], "team": alias.get(team_name(r[2]["text"])),
                "pitcher": bool(PITCHER.search(W.plain(r[3]["text"]))),
            })
    return out


def appearance_totals(text: str, alias: dict[str, str]) -> tuple[Counter, Counter]:
    """Wins and losses per franchise from the appearances table."""
    table = next(t for t in W.all_tables(text) if header_labels(t)[:3] == ["team", "wins", "losses"])
    wins, losses = Counter(), Counter()
    for r in table:
        if all(c["header"] for c in r) or len(r) < 3:
            continue
        names = [re.sub(r"\s*\(.*$", "", W.plain(target)) for target, _ in W.links(r[0]["text"])]
        fid = next((alias[n] for n in reversed(names) if n in alias), None)
        if fid:
            wins[fid] += W.number(r[1]["text"]) or 0
            losses[fid] += W.number(r[2]["text"]) or 0
    return wins, losses


def build(refresh: bool) -> tuple[dict, dict, list[str]]:
    franchises, alias = load_franchises()
    text = page(PAGES["series"], refresh)
    seasons = parse_series(text, alias)
    mvps = parse_mvps(page(PAGES["mvp"], refresh), alias)
    for s in seasons:
        m = mvps.get(s["year"], [])
        s["mvps"] = [x["name"] for x in m]
        s["mvpPitcher"] = [x["pitcher"] for x in m]
        s["mvpOnLoser"] = bool(m) and all(x["team"] == s["runnerUp"] for x in m)
        # Toronto is the only Canadian franchise to reach the World Series.
        s["country"] = "CAN" if s["champion"] == "TOR" else "USA"

    coaches: dict[str, dict] = {}
    for s in seasons:
        for ppl, team, bucket in ((s.pop("coach"), s["champion"], "titles"), (s.pop("runnerUpCoach"), s["runnerUp"], "lost")):
            for k, n in ppl:
                c = coaches.setdefault(re.sub(r"[^a-z]", "", k.lower()), {"name": n, "nation": None, "titles": [], "lost": []})
                c[bucket].append({"season": str(s["year"]), "club": team})
    people = {
        "meta": {"generated": date.today().isoformat(), "sources": [f"https://en.wikipedia.org/wiki/{PAGES['series'].replace(' ', '_')}"],
                 "kind": "cup", "notes": [], "coachesNote": "In baseball the head coach is the manager. Early clubs were often run by a player-manager.",
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
    losses = Counter(s["runnerUp"] for s in seasons)
    exp_w, exp_l = appearance_totals(text, alias)
    for got, exp, what in ((wins, exp_w, "titles"), (losses, exp_l, "lost Series")):
        diff = {k: (got.get(k, 0), exp.get(k, 0)) for k in set(got) | set(exp) if got.get(k, 0) != exp.get(k, 0)}
        if diff:
            errors.append(f"{what} per franchise differ from the appearances table (got, expected): {diff}")
    if wins["NYY"] != 27:
        errors.append(f"New York Yankees: {wins['NYY']} titles, expected 27")
    years = [s["year"] for s in seasons]
    if sorted(set(range(1903, years[-1] + 1)) - set(years)) != [1904, 1994]:
        errors.append(f"missing Series: {sorted(set(range(1903, years[-1] + 1)) - set(years))} (expected only 1904 and 1994)")
    if [s for s in seasons if s["league"] is None or s["runnerUpLeague"] is None or s["league"] == s["runnerUpLeague"]]:
        errors.append("a Series without one American League and one National League team")
    no_mvp = [s["year"] for s in seasons if s["year"] >= 1955 and not s["mvps"]]
    if no_mvp:
        errors.append(f"no World Series MVP for {no_mvp}")
    if next(s for s in seasons if s["year"] == 1960)["mvpOnLoser"] is not True:
        errors.append("1960: Bobby Richardson, of the losing Yankees, should be the MVP")
    mcgraw = next((c for c in people["coaches"] if c["name"] == "John McGraw"), None)
    if not mcgraw or (len(mcgraw["titles"]), len(mcgraw["lost"])) != (3, 6):
        errors.append(f"John McGraw: {mcgraw and (len(mcgraw['titles']), len(mcgraw['lost']))} as manager, expected 3 won and 6 lost")
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
    write(OUT_DIR / "world-series.json", data)
    write(OUT_DIR / "people.json", people)


if __name__ == "__main__":
    main()
