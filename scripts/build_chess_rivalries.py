"""Build the chess rivalries dataset used by chess/rivalries.

Every game between the two players in PGN Mentor's game files (the same files and the same classical/rapid/blitz
split as the chess page's head to head), with its date, event and colors, and the World Championship matches they
played for the title (from chess/data/chess.json, built first by build_chess.py).

Usage:
    python3 scripts/build_chess_rivalries.py            # use the saved game files
    python3 scripts/build_chess_rivalries.py --refresh  # re-download them
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date

from build_chess import H2H_PLAYERS, OUTPUT as CHESS, game_mode, load_pgn
from build_football import ROOT

OUTPUT = ROOT / "chess" / "rivalries" / "data" / "chess-rivalries.json"

# (first player, second player, a line on the rivalry). The first is the one who became champion first, or the elder.
RIVALRIES = [
    ("steinitz", "chigorin", "Two World Championship matches, 1889 and 1892, and the 19th century's great clash of styles."),
    ("lasker", "tarrasch", "The 1908 title match, after years of rivalry for the German chess world."),
    ("capablanca", "alekhine", "The 1927 Buenos Aires match, and a rematch that never came."),
    ("botvinnik", "smyslov", "Three title matches in five years, 1954 to 1958."),
    ("botvinnik", "tal", "Tal's 1960 storm and Botvinnik's 1961 return match."),
    ("petrosian", "spassky", "Two title matches, 1966 and 1969."),
    ("spassky", "fischer", "Reykjavík 1972, the match of the Cold War."),
    ("karpov", "korchnoi", "Baguio 1978, Merano 1981 and the 1974 Candidates final."),
    ("karpov", "kasparov", "Five World Championship matches and 144 title games, 1984 to 1990."),
    ("kasparov", "anand", "The 1995 PCA title match atop the World Trade Center."),
    ("kasparov", "kramnik", "London 2000, where the pupil took the title from the teacher."),
    ("kramnik", "topalov", "Elista 2006, the reunification match."),
    ("anand", "kramnik", "Bonn 2008, Anand's undisputed title."),
    ("anand", "topalov", "Sofia 2010."),
    ("anand", "carlsen", "Chennai 2013 and Sochi 2014: the title passed to Carlsen."),
    ("carlsen", "caruana", "London 2018: twelve classical draws and a rapid tiebreak."),
    ("carlsen", "nakamura", "The great online and blitz rivalry of the 2010s and 2020s."),
    ("carlsen", "nepomniachtchi", "Dubai 2021, and childhood rivals."),
    ("ding", "nepomniachtchi", "Astana 2023, after Carlsen gave up the title."),
    ("ding", "gukesh", "Singapore 2024: Gukesh, the youngest undisputed champion."),
]


def games_between(a: str, b: str, refresh: bool) -> list[dict]:
    pats = {k: re.compile(r"^(?:" + pat + r")", re.I) for k, _, _, _, pat in H2H_PLAYERS}
    files = {k: f for k, _, _, f, _ in H2H_PLAYERS}
    who = lambda n: None if "/" in n else next((k for k in (a, b) if pats[k].search(n.strip())), None)  # noqa: E731
    seen, out = set(), []
    for key in (a, b):
        for block in re.split(r"\n(?=\[Event )", load_pgn(files[key], refresh)):
            tags = dict(re.findall(r'\[(\w+) "([^"]*)"\]', block[:2000]))
            white, black = who(tags.get("White", "")), who(tags.get("Black", ""))
            if {white, black} != {a, b} or tags.get("Result") not in ("1-0", "0-1", "1/2-1/2"):
                continue
            mode = game_mode(tags.get("Event", ""), tags.get("Round", ""), tags.get("Site", ""))
            if not mode:
                continue
            moves = re.sub(r"\{[^}]*\}|\[[^\]]*\]|\s+", " ", block.split("]\n", 1)[-1])[:120]
            uid = (tags.get("Date", "")[:10], white, tags.get("Round", ""), moves)
            if uid in seen:
                continue
            seen.add(uid)
            d = tags.get("Date", "").replace("??", "01")
            year = int(d[:4]) if d[:4].isdigit() else None
            if not year:
                continue
            score = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}[tags["Result"]]
            out.append({"date": d[:10] if re.match(r"\d{4}\.\d\d\.\d\d", d) else f"{year}.01.01", "year": year,
                        "event": re.sub(r"\s+", " ", tags.get("Event", "")).strip(), "white": white, "mode": mode,
                        # The first player's score: 1 a win, 0.5 a draw, 0 a loss.
                        "s": score if white == a else 1 - score})
    out.sort(key=lambda g: (g["date"], g["event"]))
    for g in out:
        g["date"] = g["date"].replace(".", "-")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    players = {k: {"name": n, "fed": f} for k, n, f, _, _ in H2H_PLAYERS}
    chess = json.loads(CHESS.read_text(encoding="utf-8"))
    built = []
    for a, b, blurb in RIVALRIES:
        games = games_between(a, b, args.refresh)
        names = {players[a]["name"], players[b]["name"]}
        # Title matches, the 1984–85 one abandoned without a result included.
        title = [{k: m.get(k) for k in ("year", "label", "kind", "winner", "runnerUp", "score", "location", "drawn", "format")}
                 for m in chess["worldChampionships"] if m.get("kind") in ("match", "aborted") and {m.get("winner"), m.get("runnerUp")} == names]
        if len(games) < 10:
            raise SystemExit(f"{a}–{b}: only {len(games)} games")
        built.append({"id": f"{a}-{b}", "players": [a, b], "blurb": blurb, "games": games, "titleMatches": title})
        by = {m: [sum(g["s"] == 1 for g in games if g["mode"] == m), sum(g["s"] == 0.5 for g in games if g["mode"] == m),
                  sum(g["s"] == 0 for g in games if g["mode"] == m)] for m in ("classical", "rapid", "blitz")}
        print(f"{players[a]['name']}–{players[b]['name']}: {len(games)} games {games[0]['year']}–{games[-1]['year']}, {by}, "
              f"{len(title)} title matches", file=sys.stderr)
    used = {p for r in built for p in r["players"]}
    out = {"updated": date.today().isoformat(), "rivalries": built, "players": {k: players[k] for k in sorted(used)},
           "federations": chess["federations"],
           "source": {"label": "PGN Mentor's game files", "url": "https://www.pgnmentor.com/files.html"}}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(built)} rivalries, {sum(len(r['games']) for r in built)} games", file=sys.stderr)


if __name__ == "__main__":
    main()
