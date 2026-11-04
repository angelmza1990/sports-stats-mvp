"""Build the NBA rivalries dataset used by basketball/nba-rivalries.

Reads the "Season-by-season results" table of each rivalry's English Wikipedia article: one row per regular season
(the season series, split by venue) and one per playoff series, with the running head-to-head after each. Every
historical team name is mapped to its current franchise (data/nba/franchises.json), and the rows are checked against
the totals each article publishes at the end of its table.

Usage:
    python3 scripts/build_nba_rivalries.py            # use the cached pages if present
    python3 scripts/build_nba_rivalries.py --refresh  # re-download the pages
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import wikitables as W

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "raw" / "wikipedia" / "nba-rivalries"
FRANCHISES = ROOT / "data" / "nba" / "franchises.json"
OUTPUT = ROOT / "basketball" / "nba-rivalries" / "data" / "nba-rivalries.json"

# Validated light/dark pairs shared with the football rivalries (see build_rivalries.COLORS); the first color is the
# first team's. Black-and-silver San Antonio takes purple, as black-and-white clubs do there.
RIVALRIES = [
    ("celtics-lakers", "Celtics–Lakers rivalry", "BOS", "LAL", ("#067e3f", "#ce9707", "#05ab58", "#996f09")),
    ("76ers-celtics", "76ers–Celtics rivalry", "PHI", "BOS", ("#fd736d", "#067e3f", "#b71824", "#029d50")),
    ("celtics-knicks", "Celtics–Knicks rivalry", "BOS", "NYK", ("#067e3f", "#fd736d", "#029d50", "#b71824")),
    ("celtics-pistons", "Celtics–Pistons rivalry", "BOS", "DET", ("#067e3f", "#fd736d", "#029d50", "#b71824")),
    ("celtics-heat", "Celtics–Heat rivalry", "BOS", "MIA", ("#067e3f", "#fd736d", "#029d50", "#b71824")),
    ("bulls-pistons", "Bulls–Pistons rivalry", "CHI", "DET", ("#d33a3c", "#245fd4", "#e54c4a", "#245fd4")),
    ("bulls-knicks", "Bulls–Knicks rivalry", "CHI", "NYK", ("#d33a3c", "#245fd4", "#e54c4a", "#245fd4")),
    ("bulls-cavaliers", "Bulls–Cavaliers rivalry", "CHI", "CLE", ("#de4544", "#9e024a", "#b71824", "#e85082")),
    ("heat-knicks", "Heat–Knicks rivalry", "MIA", "NYK", ("#d33a3c", "#245fd4", "#e54c4a", "#245fd4")),
    ("knicks-pacers", "Knicks–Pacers rivalry", "NYK", "IND", ("#245fd4", "#ce9707", "#245fd4", "#b68611")),
    ("lakers-pistons", "Lakers–Pistons rivalry", "LAL", "DET", ("#ce9707", "#245fd4", "#b68611", "#245fd4")),
    ("lakers-spurs", "Lakers–Spurs rivalry", "LAL", "SAS", ("#ce9707", "#824fcf", "#b68611", "#824fcf")),
    ("kings-lakers", "Kings–Lakers rivalry", "SAC", "LAL", ("#824fcf", "#ce9707", "#824fcf", "#b68611")),
    ("cavaliers-warriors", "Cavaliers–Warriors rivalry", "CLE", "GSW", ("#d33a3c", "#ce9707", "#b71824", "#b68611")),
    ("mavericks-spurs", "Mavericks–Spurs rivalry", "DAL", "SAS", ("#0a96d6", "#3845bf", "#0a96d6", "#4252cd")),
    ("rockets-spurs", "Rockets–Spurs rivalry", "HOU", "SAS", ("#d33a3c", "#824fcf", "#e54c4a", "#824fcf")),
]

SUMMARY_ROWS = {"regular season games": "regular", "postseason games": "playoffs", "postseason series": "series",
                "regular and postseason": "overall"}
TEAM_CELL = re.compile(r"(?:NBA|Basketball) color cell2?\s*\|\s*([^}|]+)")


def fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower().strip()


class Teams:
    """The two franchises of a rivalry, recognised by any of their historical names or nicknames."""

    def __init__(self, franchises: dict, a: str, b: str):
        self.a, self.b = a, b
        self.names = {}
        for fid in (a, b):
            f = franchises[fid]
            for name in [f["name"], *f["aliases"]]:
                self.names[fold(name)] = fid
                self.names[fold(name.split()[-1])] = fid  # "Royals", "Nationals", "Lakers"
            self.names[fold(f["short"])] = fid
        self.names["sixers"] = self.names.get("76ers", a if a == "PHI" else b)

    def find(self, text: str) -> str | None:
        t = fold(W.plain(text))
        if t in self.names:
            return self.names[t]
        hits = {fid for name, fid in self.names.items() if re.search(rf"\b{re.escape(name)}\b", t)}
        return hits.pop() if len(hits) == 1 else None


def cells(row: str) -> list[tuple[str, str]]:
    """(attributes, content) of each cell of a table row; a cell's continuation lines join it."""
    out: list[str] = []
    lines: list[str] = []
    for line in row.split("\n"):
        # A template broken over two lines ("{{NBA color cell2" / "|Los Angeles Lakers}}") is one line.
        if lines and lines[-1].count("{{") > lines[-1].count("}}"):
            lines[-1] += line
        else:
            lines.append(line)
    for line in lines:
        if line.startswith("|") and not line.startswith(("|}", "|-")):
            out.extend(W.split_outside(line[1:], "||"))
        elif out and line.strip() and not line.startswith(("{{Game log", "!")):
            out[-1] += "\n" + line
    parsed = []
    for c in out:
        pieces = W.split_outside(c, "|")
        if len(pieces) > 1 and re.search(r"(style|align|colspan|bgcolor)\s*=", pieces[0]):
            parsed.append((pieces[0], "|".join(pieces[1:]).strip()))
        else:
            parsed.append(("", c.strip()))
    return parsed


def result(cell: tuple[str, str], teams: Teams) -> tuple[int, int] | None:
    """(wins of team a, wins of team b) from a cell like "Lakers, 2–1" (the winner's record first) or "Tie, 1–1"."""
    attrs, text = cell
    m = re.search(r"(\d+)\s*[–-]\s*(\d+)", W.plain(text))
    if not m:
        return None
    w, l = int(m.group(1)), int(m.group(2))
    if w == l:
        return w, l
    styled = TEAM_CELL.search(attrs)
    winner = teams.find(styled.group(1)) if styled and styled.group(1).strip() else None
    winner = winner or teams.find(re.sub(r",?\s*\{\{nowrap.*|\d.*", "", text))
    if winner is None:
        raise ValueError(f"no winner in {cell}")
    return (w, l) if winner == teams.a else (l, w)


def header(line: str, teams: Teams) -> list[str]:
    """Column keys of a "Game log section start" header: season, winner, record, at:<team>/neutral, overall, notes."""
    labels = [W.plain(x).strip().lower() for x in W.split_outside(line.strip("{} \t"), "|")]
    keys = []
    for raw, label in zip(W.split_outside(line.strip("{} \t"), "|"), labels):
        if label == "season":
            keys.append("season")
        elif label == "season series":
            keys += ["winner", "record"]
        elif label.startswith("at neutral"):
            keys.append("neutral")
        elif label.startswith("at "):
            target = re.search(r"\[\[([^|\]]+)", raw)
            fid = teams.find(target.group(1)) if target else None
            if fid is None:
                raise ValueError(f"unknown venue column {raw!r}")
            keys.append("home-a" if fid == teams.a else "home-b")
        elif label == "overall series":
            keys.append("overall")
        elif label == "notes":
            keys.append("notes")
    return keys


def parse(text: str, teams: Teams) -> dict:
    m = re.search(r"==\s*Season[–-]+by[–-]+season results\s*==", text, re.I)
    if not m:
        raise ValueError("no season-by-season results")
    body = text[m.end():]
    end = re.search(r"\n==[^=]", body)
    body = body[: end.start()] if end else body
    body = re.sub(r"<!--[\s\S]*?-->", "", body)
    seasons, series, published = [], [], {}
    last_overall = None
    for section in re.split(r"(?=\{\{Game log section start)", body)[1:]:
        head, _, rest = section.partition("\n")
        keys = header(head, teams)
        for raw in rest.split("\n|-")[0:]:
            row = cells(raw)
            if len(row) < 3:
                continue
            get = {k: row[i] for i, k in enumerate(keys) if i < len(row)}
            first = re.sub(r"<!--.*?-->", "", get["season"][1]).strip()
            label = fold(W.plain(first))
            if label in SUMMARY_ROWS:
                rec = result(get["record"], teams)
                split = {k: result(get[k], teams) for k in ("home-a", "home-b", "neutral") if k in get and result(get[k], teams)}
                published[SUMMARY_ROWS[label]] = {"a": rec[0], "b": rec[1], **{k: list(v) for k, v in split.items()}}
                continue
            rec = result(get["record"], teams)
            if rec is None or rec == (0, 0):
                continue  # a season with no meetings yet
            split = {k: list(result(get[k], teams)) for k in ("home-a", "home-b", "neutral") if k in get and result(get[k], teams)}
            if "overall" in get and result(get["overall"], teams):
                last_overall = result(get["overall"], teams)
            year = re.search(r"\{\{(?:nbay|NBA Year)\|(\d{4})", first, re.I)
            if year:
                y = int(year.group(1))
                seasons.append({"season": f"{y}–{(y + 1) % 100:02d}", "year": y, "a": rec[0], "b": rec[1], **split})
                continue
            link = re.search(r"\[\[(\d{4})[ _](?:NBA|BAA)[ _](Finals|playoffs)[^|\]]*(?:\|([^\]]+))?\]\]", first, re.I)
            if not link:
                raise ValueError(f"unknown row {first!r}")
            y = int(link.group(1))
            rnd = re.sub(r"^\d{4}\s*", "", W.plain(link.group(3) or f"{y} NBA Finals")).strip()
            rnd = re.sub(r"\s+", " ", rnd).replace("Round Robin", "Round-Robin")
            item = {"season": f"{y - 1}–{y % 100:02d}", "year": y - 1, "round": rnd, "a": rec[0], "b": rec[1],
                    "winner": teams.a if rec[0] > rec[1] else teams.b, **split}
            if "round-robin" in rnd.lower():
                item["roundRobin"] = True  # games of a three-team round-robin, not a series
            series.append(item)
    return {"seasons": seasons, "series": series, "published": published, "lastOverall": last_overall}


def build(cfg: tuple, franchises: dict, refresh: bool) -> dict:
    rid, title, a, b, colors = cfg
    slug = re.sub(r"[^a-z0-9]+", "-", fold(title.replace("–", "-"))).strip("-")
    text = W.fetch_raw(title, CACHE / f"{slug}.wiki", refresh, pause=1.5)
    target = re.match(r"\s*#redirect\s*\[\[([^\]|#]+)", text, re.I)
    if target:
        text = W.fetch_raw(target.group(1).strip(), CACHE / f"{slug}-r.wiki", refresh, pause=1.5)
    teams = Teams(franchises, a, b)
    data = parse(text, teams)
    seasons, series = data["seasons"], data["series"]
    reg = [sum(s["a"] for s in seasons), sum(s["b"] for s in seasons)]
    po = [sum(s["a"] for s in series), sum(s["b"] for s in series)]
    won = [sum(1 for s in series if s["winner"] == a and not s.get("roundRobin")),
           sum(1 for s in series if s["winner"] == b and not s.get("roundRobin"))]
    notes = []
    pub = data["published"]
    for key, got in (("regular", reg), ("playoffs", po), ("series", won)):
        p = pub.get(key)
        if p and [p["a"], p["b"]] != got:
            what = {"regular": "regular-season games", "playoffs": "playoff games", "series": "playoff series"}[key]
            print(f"note: {rid}: {what} add up to {got[0]}–{got[1]}, the article's summary says {p['a']}–{p['b']}", file=sys.stderr)
            # A newer season in the rows than in the summary is expected; anything else is reported on the page.
            notes.append(f"The article's summary counts {p['a']}–{p['b']} {what}; its season rows add up to {got[0]}–{got[1]}.")
            if abs(p["a"] + p["b"] - sum(got)) > max(6, 0.04 * sum(got)):
                raise SystemExit(f"{rid}: {what} {got} are too far from the published {p}")
    if not seasons or not reg[0] + reg[1]:
        raise SystemExit(f"{rid}: no seasons parsed")
    name = title.replace(" rivalry", "")
    return {"id": rid, "name": name, "teams": [a, b],
            "colors": {"light": list(colors[:2]), "dark": list(colors[2:])},
            "seasons": seasons, "series": series,
            "record": {"regular": reg, "playoffs": po, "series": won},
            "published": pub, "notes": notes,
            "source": {"label": f"English Wikipedia, {title}", "url": "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    franchises = {f["id"]: f for f in json.loads(FRANCHISES.read_text(encoding="utf-8"))["franchises"]}
    built = []
    for cfg in RIVALRIES:
        r = build(cfg, franchises, args.refresh)
        reg, po, sw = r["record"]["regular"], r["record"]["playoffs"], r["record"]["series"]
        print(f"{r['name']}: regular season {reg[0]}–{reg[1]} in {len(r['seasons'])} seasons, playoffs {po[0]}–{po[1]}, "
              f"series {sw[0]}–{sw[1]}", file=sys.stderr)
        built.append(r)
    used = {t for r in built for t in r["teams"]}
    out = {"updated": date.today().isoformat(), "rivalries": built,
           "franchises": {fid: {k: franchises[fid][k] for k in ("name", "short", "logo")} for fid in sorted(used)}}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(built)} rivalries", file=sys.stderr)


if __name__ == "__main__":
    main()
