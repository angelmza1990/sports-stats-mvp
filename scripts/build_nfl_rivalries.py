"""Build the NFL rivalries dataset used by american-football/nfl-rivalries.

Reads the "Season-by-season results" table of each rivalry's English Wikipedia article: a row per season with the
game played at each side's stadium (cells span rows when a season has two games at one place) and a row per playoff
game. Every game is rebuilt with its winner and score, historical names are mapped to the current franchise
(data/nfl/franchises.json), and the running head to head is checked against the article's "Overall series" column and
its summary rows.

Usage:
    python3 scripts/build_nfl_rivalries.py            # use the cached pages if present
    python3 scripts/build_nfl_rivalries.py --refresh  # re-download the pages
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import wikitables as W
from build_nba_rivalries import Teams, fold
from rivalries_us import season_rows, write

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "raw" / "wikipedia" / "nfl-rivalries"
FRANCHISES = ROOT / "data" / "nfl" / "franchises.json"
OUTPUT = ROOT / "american-football" / "nfl-rivalries" / "data" / "nfl-rivalries.json"

# (id, article, team a, team b, light/dark colors): each pair passes the CVD and normal-vision separation checks, in both
# modes and against the tie gray.
RIVALRIES = [
    ("bears-packers", "Bears–Packers rivalry", "CHI", "GB", ("#3845bf", "#067e3f", "#4252cd", "#05ab58")),
    ("cowboys-eagles", "Cowboys–Eagles rivalry", "DAL", "PHI", ("#245fd4", "#05ab58", "#245fd4", "#05ab58")),
    ("cowboys-giants", "Cowboys–Giants rivalry", "DAL", "NYG", ("#0a96d6", "#3845bf", "#0a96d6", "#4252cd")),
    ("commanders-cowboys", "Commanders–Cowboys rivalry", "WAS", "DAL", ("#9e024a", "#245fd4", "#e85082", "#245fd4")),
    ("eagles-giants", "Eagles–Giants rivalry", "PHI", "NYG", ("#05ab58", "#245fd4", "#05ab58", "#245fd4")),
    ("packers-vikings", "Packers–Vikings rivalry", "GB", "MIN", ("#067e3f", "#824fcf", "#098b47", "#824fcf")),
    ("bears-lions", "Bears–Lions rivalry", "CHI", "DET", ("#d9471b", "#0a96d6", "#d9471b", "#0a96d6")),
    ("ravens-steelers", "Ravens–Steelers rivalry", "BAL", "PIT", ("#824fcf", "#ce9707", "#824fcf", "#b68611")),
    ("browns-steelers", "Browns–Steelers rivalry", "CLE", "PIT", ("#d9471b", "#824fcf", "#d9471b", "#824fcf")),
    ("chiefs-raiders", "Chiefs–Raiders rivalry", "KC", "LV", ("#d33a3c", "#824fcf", "#e54c4a", "#824fcf")),
    ("broncos-raiders", "Broncos–Raiders rivalry", "DEN", "LV", ("#d9471b", "#824fcf", "#d9471b", "#824fcf")),
    ("broncos-chiefs", "Broncos–Chiefs rivalry", "DEN", "KC", ("#245fd4", "#d33a3c", "#245fd4", "#e54c4a")),
    ("jets-patriots", "Jets–Patriots rivalry", "NYJ", "NE", ("#05ab58", "#245fd4", "#05ab58", "#245fd4")),
    ("49ers-rams", "49ers–Rams rivalry", "SF", "LAR", ("#d33a3c", "#245fd4", "#e54c4a", "#245fd4")),
    ("falcons-saints", "Falcons–Saints rivalry", "ATL", "NO", ("#d33a3c", "#ce9707", "#b71824", "#b68611")),
    ("bills-dolphins", "Bills–Dolphins rivalry", "BUF", "MIA", ("#245fd4", "#d9471b", "#245fd4", "#d9471b")),
    ("lions-packers", "Lions–Packers rivalry", "DET", "GB", ("#0a96d6", "#067e3f", "#0a96d6", "#098b47")),
]

TEAM_STYLE = re.compile(r"NFL(?:Alt)?(?:Primary|Secondary)Style\s*\|\s*([^}|]+)")
ROUNDS = [("super bowl", "Super Bowl"), ("nfc championship", "NFC Championship"), ("afc championship", "AFC Championship"),
          ("nfl championship", "NFL Championship"), ("afl championship", "AFL Championship"), ("divisional", "Divisional round"),
          ("wild card", "Wild Card round"), ("division championship", "Division playoff"), ("division playoff", "Division playoff"),
          ("conference championship", "Conference championship"), ("playoff", "Playoffs")]


def raw_rows(section: str) -> list[list[tuple[str, str, int]]]:
    """Each row's cells as (attributes, content, rowspan), a cell spanning columns repeated; "!" header cells count
    like "|" ones."""
    out = []
    for raw in section.split("\n|-"):
        lines: list[str] = []
        for line in raw.split("\n"):
            if lines and lines[-1].count("{{") > lines[-1].count("}}"):
                lines[-1] += line
            else:
                lines.append(line)
        cells: list[str] = []
        for line in lines:
            if line.startswith(("|", "!")) and not line.startswith(("|}", "|-", "|+")):
                cells.extend(W.split_outside(line[1:], "||" if line.startswith("|") else "!!"))
            elif cells and line.strip() and not line.startswith("{{Game log"):
                cells[-1] += "\n" + line
        row = []
        for c in cells:
            pieces = W.split_outside(c, "|")
            if len(pieces) > 1 and re.search(r"(style|rowspan|colspan|align)\s*=", pieces[0]):
                attrs, text = pieces[0], "|".join(pieces[1:])
            else:
                attrs, text = "", c
            span = re.search(r'rowspan\s*=\s*"?(\d+)', attrs)
            cols = re.search(r'colspan\s*=\s*"?(\d+)', attrs)
            for _ in range(int(cols.group(1)) if cols else 1):  # "canceled (Players' strike)" across the venue columns
                row.append((attrs, text.strip(), int(span.group(1)) if span else 1))
        if row:
            out.append(row)
    return out


def grid(rows: list[list[tuple[str, str, int]]], width: int) -> list[list[tuple[str, str, bool]]]:
    """Rows with the spanned cells filled in, each as (attributes, content, carried from the row above)."""
    pending: dict[int, list] = {}
    out = []
    for row in rows:
        full, cells, col = [], iter(row), 0
        while col < width:
            if col in pending:
                attrs, text, left = pending[col]
                full.append((attrs, text, True))
                pending[col][2] -= 1
                if pending[col][2] == 0:
                    del pending[col]
            else:
                cell = next(cells, None)
                if cell is None:
                    break
                attrs, text, span = cell
                full.append((attrs, text, False))
                if span > 1:
                    pending[col] = [attrs, text, span - 1]
            col += 1
        out.append(full)
    return out


def header(line: str, teams: Teams) -> list[str]:
    keys = []
    for raw in W.split_outside(line.strip("{} \t"), "|"):
        label = fold(W.plain(raw)).strip()
        if label == "season":
            keys.append("season")
        elif label == "season series":
            keys.append("series")
        elif label.startswith("at neutral") or label in ("neutral site", "at neutral sites"):
            keys.append("neutral")
        elif label.startswith("at "):
            targets = [teams.find(t) for t, _ in W.links(raw)] or [teams.find(raw[3:])]
            fid = next((t for t in targets if t), None)
            if fid is None:
                raise ValueError(f"unknown venue column {raw!r}")
            keys.append("home-a" if fid == teams.a else "home-b")
        elif label == "overall series":
            keys.append("overall")
        elif label == "notes":
            keys.append("notes")
    return keys


def result(attrs: str, text: str, teams: Teams) -> tuple[str | None, int, int, bool] | None:
    """(winner or None for a tie, winner's points, loser's points, overtime) from a game cell."""
    plain = W.plain(re.sub(r"<br\s*/?>", " ", text))
    m = re.search(r"(\d+)\s*[–-]\s*(\d+)", plain)
    if not m or re.search(r"no game|cancel|postpon|forfeit", plain, re.I):
        return None
    hi, lo = int(m.group(1)), int(m.group(2))
    ot = bool(re.search(r"\bOT\b|overtime", plain))
    if fold(plain).startswith("tie") and hi == lo:
        return None, hi, lo, ot
    styled = TEAM_STYLE.search(attrs)
    winner = teams.find(styled.group(1)) if styled else None
    winner = winner or teams.find(plain[: m.start()])
    if winner is None:
        raise ValueError(f"no winner in {text!r}")
    return winner, hi, lo, ot


def overall(text: str, teams: Teams) -> tuple[int, int, int] | None:
    """(wins of a, wins of b, ties) from "Packers <br /> 109–97–6"."""
    plain = W.plain(re.sub(r"<br\s*/?>", " ", text))
    m = re.search(r"(\d+)\s*[–-]\s*(\d+)(?:\s*[–-]\s*(\d+))?", plain)
    if not m:
        return None
    w, l, t = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if w == l:
        return w, l, t
    leader = teams.find(plain[: m.start()])
    if leader is None:
        return None
    return (w, l, t) if leader == teams.a else (l, w, t)


def round_name(*texts: str) -> str:
    """The round named first: in the season cell, else in the notes ("NFC Championship. Packers go on to win Super
    Bowl XLV" is the NFC Championship)."""
    for text in texts:
        t = fold(W.plain(text))
        hits = [(t.find(key), name) for key, name in ROUNDS if key in t and key != "playoff"]
        if hits:
            return min(hits)[1]
    return "Playoffs"


def parse(text: str, teams: Teams) -> tuple[list[dict], dict, list[str]]:
    m = re.search(r"==\s*Season[–-]+by[–-]+season results\s*==", text, re.I)
    if not m:
        raise ValueError("no season-by-season results")
    body = text[m.end():]
    end = re.search(r"\n==[^=]", body)
    body = re.sub(r"<!--[\s\S]*?-->", "", body[: end.start()] if end else body)
    body = re.sub(r"<ref[^>/]*/>|<ref[^>]*>[\s\S]*?</ref>", "", body)
    games, published, checks = [], {}, []
    year = None
    tally = [0, 0, 0]
    expect = None
    for section in re.split(r"(?=\{\{Game log section start)", body)[1:]:
        head, _, rest = section.partition("\n")
        keys = header(head, teams)
        rows = grid(raw_rows(rest), len(keys))
        summary = "summary" in fold(head)
        for row in rows:
            get = {k: row[i] for i, k in enumerate(keys) if i < len(row)}
            if "season" not in get:
                continue
            first = get["season"][1]
            label = fold(W.plain(first))
            if not get["season"][2]:
                tally = compare(expect, tally, checks)
                expect = None
            if summary:
                rec = overall(get["series"][1], teams) if "series" in get else None
                if rec and label:
                    published[label] = rec
                continue
            playoff = bool(re.search(r"playoff|super bowl|championship|wild card|divisional", label)) and not re.match(r"^\{\{nfly", first.strip())
            y = re.search(r"(?<!\d)(\d{4})(?!\d)", first)
            if y and not playoff:
                year = int(y.group(1))
            elif y and playoff:
                # "2025 Playoffs" belong to the 2025 season; a Super Bowl named by its numeral to the season before.
                year = int(y.group(1)) if int(y.group(1)) <= (year or 0) + 1 else year
            if year is None:
                continue
            for col in ("home-a", "home-b", "neutral"):
                if col not in get or get[col][2]:
                    continue  # spanned from the row above: already counted
                attrs, cell, _ = get[col]
                res = result(attrs, cell, teams)
                if res is None:
                    continue
                winner, hi, lo, ot = res
                home = teams.a if col in ("home-a", "neutral") else teams.b
                away = teams.b if home == teams.a else teams.a
                hs, as_ = (hi, lo) if winner in (home, None) else (lo, hi)
                g = {"season": year, "home": home, "away": away, "hs": hs, "as": as_, "playoff": playoff}
                if col == "neutral":
                    g["neutral"] = True
                if ot:
                    g["end"] = "OT"
                if playoff:
                    g["round"] = round_name(first, get.get("notes", ("", "", False))[1])
                games.append(g)
                i = 2 if winner is None else 0 if winner == teams.a else 1
                tally[i] += 1
            if "overall" in get and not get["overall"][2]:
                expect = (year, overall(get["overall"][1], teams))
    compare(expect, tally, checks)
    return games, published, checks


def compare(expect, tally: list[int], checks: list[str]) -> list[int]:
    """Check the running total once a season's rows are all read: the article's "Overall series" after it."""
    if not expect or not expect[1] or list(expect[1]) == tally:
        return tally
    checks.append(f"{expect[0]}: the games add up to {tally[0]}–{tally[1]}–{tally[2]}, the article's running total is "
                  f"{expect[1][0]}–{expect[1][1]}–{expect[1][2]}")
    return list(expect[1])


def build(cfg: tuple, franchises: dict, refresh: bool) -> dict:
    rid, title, a, b, colors = cfg
    slug = re.sub(r"[^a-z0-9]+", "-", fold(title.replace("–", "-"))).strip("-")
    text = W.fetch_raw(title, CACHE / f"{slug}.wiki", refresh, pause=2)
    target = re.match(r"\s*#redirect\s*\[\[([^\]|#]+)", text, re.I)
    if target:
        text = W.fetch_raw(target.group(1).strip(), CACHE / f"{slug}-r.wiki", refresh, pause=2)
    teams = Teams(franchises, a, b)
    games, published, checks = parse(text, teams)
    if len(games) < 30:
        raise SystemExit(f"{rid}: only {len(games)} games")
    if len(checks) > 3:
        raise SystemExit(f"{rid}: the games drift from the article's running total: {checks[:5]}")
    seasons = season_rows(games, a, b, lambda m: m["season"], regular=lambda m: not m["playoff"], split=False)
    series = []
    for g in games:
        if g["playoff"]:
            won = None if g["hs"] == g["as"] else g["home"] if g["hs"] > g["as"] else g["away"]
            series.append({"season": str(g["season"]), "year": g["season"], "round": g["round"], "a": int(won == a), "b": int(won == b),
                           "winner": won, "score": [g["hs"], g["as"]] if g["home"] == a else [g["as"], g["hs"]],
                           **({"neutral": True} if g.get("neutral") else {"home": g["home"]}), **({"ot": True} if g.get("end") else {})})
    notes = [f"Where the article's running total differs from its games: {c}." for c in checks]
    reg = [sum(s["a"] for s in seasons), sum(s["b"] for s in seasons), sum(s.get("t", 0) for s in seasons)]
    pub = next((v for k, v in published.items() if k.startswith("regular season")), None)
    if pub and list(pub) != reg:
        print(f"note: {rid}: regular season {reg}, the article's summary says {list(pub)}", file=sys.stderr)
        notes.append(f"The article's summary counts {pub[0]}–{pub[1]}{f'–{pub[2]}' if pub[2] else ''} in the regular season; "
                     f"its season rows add up to {reg[0]}–{reg[1]}{f'–{reg[2]}' if reg[2] else ''}.")
    name = title.replace(" rivalry", "")
    return {"id": rid, "name": name, "teams": [a, b], "colors": {"light": list(colors[:2]), "dark": list(colors[2:])},
            "seasons": seasons, "series": series, "games": games, "notes": notes,
            "source": {"label": f"English Wikipedia, {title}", "url": "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    franchises = {f["id"]: f for f in json.loads(FRANCHISES.read_text(encoding="utf-8"))["franchises"]}
    built = []
    for cfg in RIVALRIES:
        r = build(cfg, franchises, args.refresh)
        reg = [sum(s["a"] for s in r["seasons"]), sum(s["b"] for s in r["seasons"]), sum(s.get("t", 0) for s in r["seasons"])]
        print(f"{r['name']}: regular season {reg} in {len(r['seasons'])} seasons, {len(r['series'])} playoff games", file=sys.stderr)
        built.append(r)
    write(OUTPUT, built, franchises, "nfl")


if __name__ == "__main__":
    main()
