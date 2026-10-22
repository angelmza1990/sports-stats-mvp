"""Build the Super Bowl dataset used by american-football/super-bowl: every Super Bowl, the NFL championships
before it, the Super Bowl MVPs and both head coaches of every game.

Sources (Wikipedia, CC BY-SA 4.0): "List of Super Bowl champions", "List of NFL champions (1920–1969)",
"Super Bowl Most Valuable Player" and "List of Super Bowl head coaches". Team names map to today's
franchise through data/nfl/franchises.json.

Usage:
    python3 scripts/build_super_bowl.py            # cached pages
    python3 scripts/build_super_bowl.py --refresh  # re-download them
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
CACHE = ROOT / "data" / "raw" / "wikipedia" / "nfl"
FRANCHISES = ROOT / "data" / "nfl" / "franchises.json"
OUT_DIR = ROOT / "american-football" / "super-bowl" / "data"
PAGES = {
    "games": "List of Super Bowl champions",
    "nfl": "List of NFL champions (1920–1969)",
    "mvp": "Super Bowl Most Valuable Player",
    "coaches": "List of Super Bowl head coaches",
}

# Super Bowls won through Super Bowl LX (February 2026), frozen. New games may add to these but never change them.
HISTORY_THROUGH = 2026
HISTORY = {"NE": 6, "PIT": 6, "SF": 5, "DAL": 5, "KC": 4, "GB": 4, "NYG": 4, "DEN": 3, "LV": 3, "WAS": 3, "PHI": 2,
           "SEA": 2, "BAL": 2, "IND": 2, "LAR": 2, "TB": 2, "MIA": 2, "CHI": 1, "NYJ": 1, "NO": 1}
# League championships (NFL titles 1920–1969 plus Super Bowls from the 1970 season), as the NFL counts them.
LEAGUE_TITLES = {"GB": 13, "CHI": 9, "NYG": 8}


def page(title: str, refresh: bool) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return W.fetch_raw(title, CACHE / f"{slug}.wiki", refresh, pause=1.5)


def roman(n: str) -> int:
    if n.isdigit():  # Super Bowl 50 was numbered in Arabic numerals
        return int(n)
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    for a, b in zip(n, n[1:] + " "):
        v = vals[a]
        total += -v if b in vals and vals[b] > v else v
    return total


def load_franchises() -> tuple[list[dict], dict[str, str]]:
    franchises = json.loads(FRANCHISES.read_text(encoding="utf-8"))["franchises"]
    alias = {a: f["id"] for f in franchises for a in f["aliases"]}
    return franchises, alias


def team_name(cell: str) -> str:
    link = W.links(cell)
    name = W.plain(link[0][1] or link[0][0]) if link else W.plain(cell)
    name = re.sub(r"\s*\(\d+\)|[‡^†*#§]+", "", name).strip()
    return re.sub(r"^\d{4} ", "", re.sub(r" season$", "", name))


def place(cell: str) -> str:
    """A venue or city cell: {{Sort|key|Pontiac, Michigan}} -> its text, without the "(2)" counters."""
    m = re.search(r"\{\{\s*sort\s*\|[^|]*\|(.*)", cell, re.I | re.S)
    text = m.group(1) if m else cell
    text = re.split(r"\{\{\s*#tag|<ref|\{\{\s*refn|\{\{\s*efn", text, flags=re.I)[0]  # drop footnotes
    text = W.plain(text).replace("}}", "").strip()
    return re.sub(r"\s*\(\d+\)\s*$", "", text).strip()


def find_table(text: str, *needles: str) -> list[list[dict]]:
    for t in W.all_tables(text):
        labels = [l.lower() for l in header_labels(t)] if t else []
        if all(any(n in l for l in labels) for n in needles):
            return t
    raise LookupError(f"no table with {needles}")


def parse_games(text: str, alias: dict[str, str]) -> list[dict]:
    table = find_table(text, "winning team", "losing team", "venue")
    games = []
    for r in table:
        if all(c["header"] for c in r) or len(r) < 8:
            continue
        num = re.search(r"\b([IVXLC]+|50)\b", W.plain(r[0]["text"]))
        year = re.search(r"\{\{\s*dts\s*\|\s*(\d{4})", r[1]["text"], re.I) or re.search(r"\b(19|20)\d\d\b", W.plain(r[1]["text"]))
        pts = [re.search(r"\d+", W.plain(r[i]["text"])) for i in (3, 5)]
        if not num or not year or not all(pts):
            continue
        y = int(year.group(1) if year.re.groups == 1 and len(year.group(1)) == 4 else year.group(0))
        champ, runner = team_name(r[2]["text"]), team_name(r[4]["text"])
        nfc = "d0e7ff" in (r[2]["attrs"] if isinstance(r[2]["attrs"], str) else str(r[2]["attrs"])).lower()
        for n in (champ, runner):
            if n not in alias:
                raise KeyError(f"unknown team {n!r} (Super Bowl {num.group(1)}): add it to {FRANCHISES.relative_to(ROOT)}")
        games.append({
            "number": num.group(1), "n": roman(num.group(1)), "year": y, "season": y - 1,
            "champion": alias[champ], "championName": champ, "runnerUp": alias[runner], "runnerUpName": runner,
            "conference": "NFC" if nfc else "AFC", "winPts": int(pts[0].group()), "losePts": int(pts[1].group()),
            "venue": place(r[6]["text"]), "city": place(r[7]["text"]),
        })
    return sorted(games, key=lambda g: g["n"])


def parse_mvps(text: str) -> dict[int, list[dict]]:
    table = find_table(text, "super bowl", "winner", "team", "position")
    out: dict[int, list[dict]] = {}
    for r in table:
        if all(c["header"] for c in r) or len(r) < 4:
            continue
        num = re.search(r"\b([IVXLC]+|50)\b", W.plain(r[1]["text"]))
        ppl = people_in(r[2]["text"])
        if num and ppl:
            out.setdefault(roman(num.group(1)), []).append({"name": ppl[0][1], "team": team_name(r[3]["text"])})
    return out


def parse_nfl_titles(text: str, alias: dict[str, str], defunct: set[str]) -> list[dict]:
    rows = []
    for needles in (("season", "champion", "runner-up"), ("season", "winning team", "losing team")):
        table = find_table(text, *needles)
        labels = [l.lower() for l in header_labels(table)]
        ccol = next(i for i, l in enumerate(labels) if l in ("champion", "winning team"))
        rcol = next(i for i, l in enumerate(labels) if l in ("runner-up", "losing team"))
        for r in table:
            if all(c["header"] for c in r) or len(r) <= max(ccol, rcol):
                continue
            y = re.search(r"\b(19[2-6]\d)\b", W.plain(r[0]["text"]))
            if not y:
                continue
            champ, runner = team_name(r[ccol]["text"]), team_name(r[rcol]["text"])
            if champ not in alias:
                raise KeyError(f"unknown team {champ!r} ({y.group(1)}): add it to {FRANCHISES.relative_to(ROOT)}")
            rows.append({"season": int(y.group(1)), "champion": alias[champ], "championName": champ,
                         "runnerUp": alias.get(runner), "runnerUpName": runner, "via": "NFL Championship"})
    return sorted({r["season"]: r for r in rows}.values(), key=lambda r: r["season"])


def parse_coaches(text: str) -> dict[int, tuple[list, list]]:
    table = find_table(text, "super bowl", "winning coach", "losing coach")
    labels = [l.lower() for l in header_labels(table)]
    sb = labels.index("super bowl")
    wc = next(i for i, l in enumerate(labels) if "winning coach" in l)
    lc = next(i for i, l in enumerate(labels) if "losing coach" in l)
    out = {}
    for r in table:
        if all(c["header"] for c in r) or len(r) <= max(sb, wc, lc):
            continue
        num = re.search(r"\b([IVXLC]+|50)\b", W.plain(r[sb]["text"]))
        if num:
            out[roman(num.group(1))] = (people_in(r[wc]["text"]), people_in(r[lc]["text"]))
    return out


def build(refresh: bool) -> tuple[dict, dict, list[str]]:
    franchises, alias = load_franchises()
    defunct = {f["id"] for f in franchises if f.get("defunct")}
    games = parse_games(page(PAGES["games"], refresh), alias)
    mvps = parse_mvps(page(PAGES["mvp"], refresh))
    for g in games:
        m = mvps.get(g["n"], [])
        g["mvp"] = [x["name"] for x in m]
        g["mvpOnLoser"] = bool(m) and all(alias.get(x["team"]) == g["runnerUp"] for x in m)
    nfl = parse_nfl_titles(page(PAGES["nfl"], refresh), alias, defunct)
    league = nfl + [{"season": g["season"], "champion": g["champion"], "championName": g["championName"], "runnerUp": g["runnerUp"],
                     "runnerUpName": g["runnerUpName"], "via": f"Super Bowl {g['number']}"} for g in games if g["season"] >= 1970]
    coaches_by_game = parse_coaches(page(PAGES["coaches"], refresh))

    data = {
        "meta": {
            "generated": date.today().isoformat(),
            "sources": [f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}" for t in PAGES.values()],
            "through": games[-1]["year"],
        },
        "franchises": [{k: v for k, v in f.items() if k != "aliases"} for f in franchises],
        "games": games,
        "leagueTitles": league,
    }

    # Coaches (the people dataset shared with the football pages): titles and Super Bowls lost.
    coaches: dict[str, dict] = {}
    for g in games:
        won, lost = coaches_by_game.get(g["n"], ([], []))
        label = f"{g['year']} · Super Bowl {g['number']}"
        for ppl, team, bucket in ((won, g["champion"], "titles"), (lost, g["runnerUp"], "lost")):
            for k, n in ppl[:1]:
                n = re.sub(r"\s*\(\d+\)$", "", n)
                c = coaches.setdefault(re.sub(r"[^a-z]", "", k.lower()), {"name": n, "nation": "USA", "titles": [], "lost": []})
                c[bucket].append({"season": label, "club": team})
    people = {
        "meta": {"generated": date.today().isoformat(), "sources": [f"https://en.wikipedia.org/wiki/{PAGES['coaches'].replace(' ', '_')}"],
                 "kind": "cup", "notes": [], "coachesNote": None, "playersNote": None},
        "coaches": sorted(coaches.values(), key=lambda c: (-len(c["titles"]), -len(c["lost"]), c["name"])),
        "players": [],
        "nations": {"USA": {"name": "United States", "flag": "us"}},
    }

    errors = []
    sb = Counter(g["champion"] for g in games if g["year"] <= HISTORY_THROUGH)
    if sb != Counter(HISTORY):
        errors.append(f"Super Bowl wins through {HISTORY_THROUGH} differ: "
                      f"{ {k: (sb.get(k, 0), HISTORY.get(k, 0)) for k in set(sb) | set(HISTORY) if sb.get(k, 0) != HISTORY.get(k, 0)} }")
    if [g["n"] for g in games] != list(range(1, len(games) + 1)):
        errors.append("Super Bowls are not numbered 1..n")
    missing_mvp = [g["number"] for g in games if not g["mvp"]]
    if missing_mvp:
        errors.append(f"no MVP for Super Bowl {missing_mvp}")
    brady = sum(1 for g in games if "Tom Brady" in g["mvp"])
    if brady != 5:
        errors.append(f"Tom Brady has {brady} Super Bowl MVPs, expected 5")
    lt = Counter(r["champion"] for r in league)
    for team, n in LEAGUE_TITLES.items():
        if lt[team] < n:
            errors.append(f"{team}: {lt[team]} league titles, expected {n}")
    seasons = [r["season"] for r in league]
    if seasons != list(range(1920, seasons[-1] + 1)):
        errors.append(f"league titles are not one per season: missing {sorted(set(range(1920, seasons[-1] + 1)) - set(seasons))}")
    bb = next((c for c in people["coaches"] if c["name"] == "Bill Belichick"), None)
    if not bb or (len(bb["titles"]), len(bb["lost"])) != (6, 3):
        errors.append(f"Bill Belichick: {bb and (len(bb['titles']), len(bb['lost']))}, expected 6 wins and 3 losses")
    if sum(1 for g in games if g["n"] in coaches_by_game) != len(games):
        errors.append("a Super Bowl without its coaches")
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
    write(OUT_DIR / "super-bowl.json", data)
    write(OUT_DIR / "people.json", people)


if __name__ == "__main__":
    main()
