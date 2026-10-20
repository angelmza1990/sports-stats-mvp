"""Build the NBA championships dataset used by basketball/nba-rings.

Reads Wikipedia's "List of NBA champions" table (via the MediaWiki API),
maps every historical team name to its current franchise and writes a
compact JSON file for the front end.

Usage:
    python3 scripts/build_nba_rings.py            # use the cached page if present
    python3 scripts/build_nba_rings.py --refresh  # re-download the page
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "nba_champions_wikitext.json"
FRANCHISES = ROOT / "data" / "nba" / "franchises.json"
OUTPUT = ROOT / "basketball" / "nba-rings" / "data" / "nba-rings.json"

PAGE = "List_of_NBA_champions"
API = f"https://en.wikipedia.org/w/api.php?action=parse&page={PAGE}&prop=wikitext&format=json&formatversion=2"
USER_AGENT = "sports-stats-mvp/1.0 (https://github.com/angelmza1990/sports-stats-mvp)"

FIRST_SEASON = 1947
COLUMNS = ["year", "west", "west_coach", "result", "east", "east_coach", "mvp", "ref"]

# Players listed under an earlier name, merged for the Finals MVP leaderboard.
PLAYER_ALIASES = {"Lew Alcindor": "Kareem Abdul-Jabbar"}

# Championships through 2026, frozen. New seasons may add to these but never change them.
HISTORY_THROUGH = 2026
HISTORY = {
    "BOS": 18, "LAL": 17, "GSW": 7, "CHI": 6, "SAS": 5, "DET": 3, "MIA": 3, "PHI": 3, "NYK": 3,
    "MIL": 2, "HOU": 2, "OKC": 2, "ATL": 1, "SAC": 1, "WAS": 1, "POR": 1, "DAL": 1, "TOR": 1,
    "CLE": 1, "DEN": 1, "BLB": 1,
}


def fetch(refresh: bool) -> str:
    if refresh or not RAW.exists():
        print("downloading Wikipedia page...", file=sys.stderr)
        RAW.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(API, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
            RAW.write_bytes(body)
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            if not RAW.exists():
                raise
            # The saved snapshot (data/raw/, kept in the repo) stands in when the page can't be fetched.
            print(f"warning: could not download the page ({err}); using the saved copy", file=sys.stderr)
    return json.loads(RAW.read_text(encoding="utf-8"))["parse"]["wikitext"]


def split_outside_links(text: str, sep: str) -> list[str]:
    """Split on `sep`, ignoring separators inside [[...]] and {{...}}."""
    parts, depth, buf, i = [], 0, [], 0
    while i < len(text):
        two = text[i : i + 2]
        if two in ("[[", "{{"):
            depth += 1
        elif two in ("]]", "}}"):
            depth = max(0, depth - 1)
        if depth == 0 and text.startswith(sep, i):
            parts.append("".join(buf))
            buf = []
            i += len(sep)
            continue
        buf.append(text[i])
        i += 1
    parts.append("".join(buf))
    return parts


def parse_cell(raw: str) -> tuple[dict, str]:
    """Split a wikitable cell into (attributes, content)."""
    pieces = split_outside_links(raw, "|")
    if len(pieces) > 1 and re.search(r"(style|rowspan|colspan|align|bgcolor)\s*=", pieces[0]):
        attrs, content = pieces[0], "|".join(pieces[1:])
    else:
        attrs, content = "", raw
    rowspan = re.search(r'rowspan\s*=\s*"?(\d+)', attrs)
    upper = attrs.upper()
    return {
        "rowspan": int(rowspan.group(1)) if rowspan else 1,
        "winner": "FFFF99" in upper,
        "on_loser": "FFBBBB" in upper,  # Finals MVP from the losing team
    }, content.strip()


def parse_table(wikitext: str) -> list[dict]:
    start = wikitext.find("\n!Year")
    if start < 0:
        raise ValueError("champions table not found")
    end = wikitext.find("\n|}", start)
    body = wikitext[start:end]
    raw_rows = body.split("\n|-")[1:]

    pending: dict[int, tuple[int, tuple[dict, str]]] = {}  # column -> (rows left, cell)
    rows = []
    for raw in raw_rows:
        cells_raw = []
        for line in raw.strip("\n").split("\n"):
            if line.startswith("|"):
                cells_raw.extend(split_outside_links(line[1:], "||"))
            elif cells_raw:
                cells_raw[-1] += "\n" + line
        queue = [parse_cell(c) for c in cells_raw]
        row = {}
        for col in range(len(COLUMNS)):
            if col in pending:
                left, cell = pending[col]
                row[col] = cell
                if left > 1:
                    pending[col] = (left - 1, cell)
                else:
                    del pending[col]
            elif queue:
                cell = queue.pop(0)
                row[col] = cell
                if cell[0]["rowspan"] > 1:
                    pending[col] = (cell[0]["rowspan"] - 1, cell)
        rows.append({COLUMNS[c]: row.get(c, ({}, "")) for c in range(len(COLUMNS))})
    return rows


def link_text(content: str) -> str:
    """Display text of the first [[link]] in a cell."""
    m = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", content)
    if not m:
        return re.sub(r"[{}'\[\]]", "", content).strip()
    return (m.group(2) or m.group(1)).strip()


def season_year(content: str) -> int:
    m = re.search(r"(19|20)\d{2}", content)
    if not m:
        raise ValueError(f"no year in {content!r}")
    return int(m.group(0))


def load_franchises() -> tuple[list[dict], dict[str, str]]:
    franchises = json.loads(FRANCHISES.read_text(encoding="utf-8"))["franchises"]
    alias = {}
    for f in franchises:
        for name in f["aliases"]:
            alias[name] = f["id"]
    return franchises, alias


def franchise_for(name: str, year: int, alias: dict[str, str]) -> str:
    if name == "Baltimore Bullets":
        name = "Baltimore Bullets (1947)" if year < 1955 else "Baltimore Bullets (1963)"
    if name not in alias:
        raise KeyError(f"unknown team name {name!r} ({year}): add it to data/nba/franchises.json")
    return alias[name]


def build(wikitext: str) -> dict:
    franchises, alias = load_franchises()
    seasons = []
    for row in parse_table(wikitext):
        year = season_year(row["year"][1])
        west, east = row["west"], row["east"]
        if west[0].get("winner") == east[0].get("winner"):
            raise ValueError(f"{year}: could not tell which team won")
        champ, runner = (west, east) if west[0]["winner"] else (east, west)
        champ_name, runner_name = link_text(champ[1]), link_text(runner[1])
        result = re.search(r"(\d)\s*[–-]\s*(\d)", row["result"][1])
        wins = sorted(map(int, result.groups()), reverse=True) if result else None
        mvp = link_text(row["mvp"][1]) if "[[" in row["mvp"][1] else None
        seasons.append({
            "year": year,
            "champion": franchise_for(champ_name, year, alias),
            "championName": champ_name,
            "runnerUp": franchise_for(runner_name, year, alias),
            "runnerUpName": runner_name,
            "conference": "West" if west[0]["winner"] else "East",
            "result": f"{wins[0]}–{wins[1]}" if wins else None,
            "mvp": PLAYER_ALIASES.get(mvp, mvp),
            "mvpListedAs": mvp if mvp in PLAYER_ALIASES else None,
            "mvpOnLoser": bool(row["mvp"][0].get("on_loser")),
        })

    seasons.sort(key=lambda s: s["year"])
    return {
        "meta": {
            "generated": date.today().isoformat(),
            "source": f"Wikipedia, {PAGE.replace('_', ' ')} (CC BY-SA 4.0)",
            "sourceUrl": f"https://en.wikipedia.org/wiki/{PAGE}",
            "notes": [
                "Titles are credited to the current franchise (e.g. Minneapolis Lakers count for the Lakers, Seattle SuperSonics for the Thunder).",
                "Conference is the side of the Finals bracket the champion came from that season; before 1971 these were the Eastern and Western Divisions.",
            ],
        },
        "franchises": [{k: v for k, v in f.items() if k != "aliases"} for f in franchises],
        "seasons": seasons,
    }


def validate(data: dict) -> list[str]:
    errors = []
    years = [s["year"] for s in data["seasons"]]
    expected_years = list(range(FIRST_SEASON, years[-1] + 1))
    if years != expected_years:
        errors.append(f"seasons are not consecutive from {FIRST_SEASON}: {sorted(set(expected_years) - set(years))} missing")
    if years[-1] < HISTORY_THROUGH:
        errors.append(f"latest season {years[-1]} is older than {HISTORY_THROUGH}")
    history = Counter(s["champion"] for s in data["seasons"] if s["year"] <= HISTORY_THROUGH)
    if history != Counter(HISTORY):
        diff = {k: (history.get(k, 0), HISTORY.get(k, 0)) for k in set(history) | set(HISTORY) if history.get(k, 0) != HISTORY.get(k, 0)}
        errors.append(f"titles through {HISTORY_THROUGH} differ (got, expected): {diff}")
    for s in data["seasons"]:
        if s["year"] >= 1969 and not s["mvp"]:
            errors.append(f"{s['year']}: missing Finals MVP")
        if s["result"] is None or not s["result"].startswith("4"):
            errors.append(f"{s['year']}: unexpected result {s['result']}")
    return errors


def unchanged(data: dict) -> bool:
    """True if the output already holds the same data (ignoring the build date)."""
    if not OUTPUT.exists():
        return False
    old = json.loads(OUTPUT.read_text(encoding="utf-8"))
    strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}
    return strip(old) == strip(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download the Wikipedia page")
    args = parser.parse_args()

    data = build(fetch(args.refresh))
    errors = validate(data)
    if errors:
        sys.exit("validation failed:\n  " + "\n  ".join(errors))

    if unchanged(data):
        print(f"{OUTPUT.relative_to(ROOT)} is up to date")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(data['seasons'])} seasons, latest {data['seasons'][-1]['year']}")


if __name__ == "__main__":
    main()
