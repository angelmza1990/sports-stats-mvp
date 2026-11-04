"""Shared by the NFL and NHL rivalry builds: per-season records from a list of games, the totals, and the JSON the
shared rivalries front end (assets/league-rivalries.js) reads. The NBA build writes the same shape."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

# What each league calls things on the page.
LEAGUES = {
    "nba": {"logo": "nba", "final": "NBA Finals", "finalRe": "NBA Finals|BAA Finals", "playoffUnit": "series", "ties": False},
    "nfl": {"logo": "nfl", "final": "Super Bowl", "finalRe": "Super Bowl", "playoffUnit": "game", "ties": True},
    "nhl": {"logo": "nhl", "final": "Stanley Cup Final", "finalRe": "Stanley Cup Final", "playoffUnit": "series", "ties": True},
}


def season_label(start: int, split: bool) -> str:
    return f"{start}–{(start + 1) % 100:02d}" if split else str(start)


def season_rows(games: list[dict], a: str, b: str, season_of, regular, split: bool = True) -> list[dict]:
    """One row per season with regular-season meetings: wins of a and b, ties, and the same split by venue."""
    rows = defaultdict(lambda: {"a": 0, "b": 0, "t": 0, "home-a": [0, 0, 0], "home-b": [0, 0, 0], "neutral": [0, 0, 0]})
    for m in games:
        if not regular(m):
            continue
        r = rows[season_of(m)]
        i = 2 if m["hs"] == m["as"] else 0 if (m["home"] == a) == (m["hs"] > m["as"]) else 1
        r[("a", "b", "t")[i]] += 1
        r["neutral" if m.get("neutral") else "home-a" if m["home"] == a else "home-b"][i] += 1
    out = []
    for y in sorted(rows):
        r = rows[y]
        row = {"season": season_label(y, split), "year": y, "a": r["a"], "b": r["b"]}
        if r["t"]:
            row["t"] = r["t"]
        for k in ("home-a", "home-b", "neutral"):
            if any(r[k]):
                row[k] = r[k] if r[k][2] else r[k][:2]
        out.append(row)
    return out


def record(r: dict) -> dict:
    reg = [sum(s["a"] for s in r["seasons"]), sum(s["b"] for s in r["seasons"]), sum(s.get("t", 0) for s in r["seasons"])]
    po = [sum(s["a"] for s in r["series"]), sum(s["b"] for s in r["series"]), sum(s.get("ties", 0) for s in r["series"])]
    a, b = r["teams"]
    won = [sum(1 for s in r["series"] if s["winner"] == a and not s.get("roundRobin")),
           sum(1 for s in r["series"] if s["winner"] == b and not s.get("roundRobin"))]
    return {"regular": reg, "playoffs": po, "series": won}


def write(output: Path, built: list[dict], franchises: dict, league: str) -> None:
    for r in built:
        r["record"] = record(r)
    used = {t for r in built for t in r["teams"]}
    out = {"updated": date.today().isoformat(), "league": {"key": league, **LEAGUES[league]}, "rivalries": built,
           "franchises": {fid: {k: franchises[fid].get(k) for k in ("name", "short", "logo")} for fid in sorted(used)}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {output.relative_to(output.parents[3])}: {len(built)} rivalries", file=sys.stderr)

