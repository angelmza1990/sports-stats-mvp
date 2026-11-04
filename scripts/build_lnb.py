"""Build the Liga Nacional de Básquet dataset used by basketball/lnb.

Reads Spanish Wikipedia's "Liga Nacional de Básquet" article: every final since 1985 (champion, series, runner-up,
coach and MVPs), the clubs that have played the league with their seasons in it, the titles by club, coach and player,
each season's top scorer and the all-time leaders. Titles by club are worked out from the finals and checked against
the article's own table.

Usage:
    python3 scripts/build_lnb.py            # use the cached page if present
    python3 scripts/build_lnb.py --refresh  # re-download the page
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

import wikitables as W

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "raw" / "wikipedia" / "lnb" / "es-liga-nacional-de-basquet.wiki"
OUTPUT = ROOT / "basketball" / "lnb" / "data" / "lnb.json"
PAGE = "Liga Nacional de Básquet"

# Article titles that name the same club in different tables (case, redirects), folded to one key.
SAME_CLUB = {
    "gimnasia y esgrima pedernera unidos": "club gimnasia y esgrima y pedernera unidos",
    "club sportivo independiente de general pico": "club sportivo independiente (general pico)",
    "gimnasia y esgrima (comodoro rivadavia)": "club gimnasia y esgrima (comodoro rivadavia)",
    "club atletico boca juniors (basquetbol)": "club atletico boca juniors (baloncesto)",
    "club obras sanitarias de la nacion": "club atletico obras sanitarias de la nacion",
    "olimpo de bahia blanca": "club olimpo (baloncesto)",
    "club union progresista": "union progresista (va)",
    "club atletico river plate": "club atletico river plate (baloncesto)",
    "club gimnasia y esgrima pedernera unidos": "club gimnasia y esgrima y pedernera unidos",
    "penarol (mar del plata)": "club atletico penarol (mar del plata)",
}
# Titles per club in the article's table, through 2025-26, frozen: later seasons may add to these, never change them.
TITLES_THROUGH = 2026
FLAGS = {"argentina": "ARG", "arg": "ARG", "estados unidos": "USA", "usa": "USA", "uruguay": "URU", "brasil": "BRA",
         "puerto rico": "PUR", "venezuela": "VEN", "republica dominicana": "DOM", "paraguay": "PAR", "chile": "CHI",
         "cuba": "CUB", "panama": "PAN", "colombia": "COL", "mexico": "MEX", "bahamas": "BAH", "canada": "CAN"}


def links(text: str) -> list[tuple[str, str]]:
    """Wiki links without the flag images ("Archivo:...")."""
    return [(t, d) for t, d in W.links(text) if not t.lower().startswith(("archivo:", "file:", "imagen:"))]


CATEGORIES = {"partidos jugados": "Games played", "puntos totales": "Points", "promedio de puntos": "Points per game",
              "dobles": "Two-pointers", "triples": "Three-pointers", "libres": "Free throws", "rebotes": "Rebounds",
              "asistencias": "Assists", "robos": "Steals", "tapas": "Blocks"}


def fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower().strip()


def club_key(target: str) -> str:
    k = re.sub(r"\s+", " ", fold(target.replace("_", " ")))
    return SAME_CLUB.get(k, k)


def season_end(text: str) -> tuple[str, int]:
    """("1990-91", 1991) from "1990-91", "1990-1991" or "1985"."""
    m = re.match(r"\s*(\d{4})(?:\s*[-–/]\s*(\d{2,4}))?", W.plain(text))
    start = int(m.group(1))
    if not m.group(2):
        return str(start), start
    end = int(m.group(2)) if len(m.group(2)) == 4 else start // 100 * 100 + int(m.group(2))
    return f"{start}–{end % 100:02d}", end


def flag(text: str) -> str | None:
    m = re.search(r"\{\{\s*bandera\s*\|(?:[^|}]*=[^|}]*\|)*\s*([^|}]+)", text, re.I)
    return FLAGS.get(fold(m.group(1))) if m else None


def person_and_club(text: str) -> tuple[str | None, str | None]:
    """("Sebastián Uranga", club key) from "[[Sebastián Uranga]] <br />([[Club Ferro ...|Ferro Carril Oeste]])"."""
    ls = links(text)
    if not ls:
        name = W.plain(text).strip(" '")
        return (None if not name or "designó" in name or name.startswith("No ") else name), None
    person = ls[0][1]
    club = club_key(ls[1][0]) if len(ls) > 1 else None
    return person, club


def participants(text: str) -> dict[str, dict]:
    grid = W.parse_table(W.find_table(text, r"=== Historial de participantes ===", 1))
    clubs = {}
    for r in grid[1:]:
        if len(r) < 5:
            continue
        ls = links(r[1]["text"])
        target, display = ls[0] if ls else (W.plain(r[1]["text"]).strip(" '"),) * 2
        city = [x for x in links(r[2]["text"]) if not x[0].lower().startswith("archivo:")]
        clubs[club_key(target)] = {
            "name": W.plain(display).strip(" '"), "city": city[-1][1] if city else W.plain(r[2]["text"]).strip(),
            "seasons": W.number(r[3]["text"]), "current": "liga nacional de basquet" in fold(r[4]["text"]) or W.plain(r[4]["text"]).strip() == "LNB",
        }
    return clubs


def finals(text: str, clubs: dict) -> tuple[list[dict], list[dict]]:
    grid = W.parse_table(W.find_table(text, r"== Historial de campeones =="))
    out, skipped = [], []
    for r in grid[1:]:
        label, end = season_end(r[0]["text"])
        if len(r) < 7 or r[1]["text"] == r[2]["text"]:  # a season with no final spans the row
            skipped.append({"season": label, "year": end, "note": W.plain(r[1]["text"]).strip()})
            continue
        champ, runner = links(r[1]["text"]), links(r[3]["text"])
        series = re.search(r"(\d+)\s*-\s*(\d+)", r[2]["text"])
        coach = " and ".join(d for t, d in links(r[4]["text"])) or W.plain(r[4]["text"]).strip()
        mvp, mvp_club = person_and_club(r[5]["text"])
        fmvp, fmvp_club = person_and_club(r[6]["text"])
        f = {"season": label, "year": end, "champion": club_key(champ[0][0]), "runnerUp": club_key(runner[0][0]),
             "series": [int(series.group(1)), int(series.group(2))], "coach": coach,
             "mvp": mvp, "mvpClub": mvp_club, "finalsMvp": fmvp, "finalsMvpClub": fmvp_club,
             "championCity": champ[-1][1] if len(champ) > 1 else None}
        for k in ("champion", "runnerUp"):
            if f[k] not in clubs:
                raise SystemExit(f"{label}: {f[k]} is not in the list of participants")
        out.append(f)
    return out, skipped


def titles_table(text: str, heading: str, people: bool) -> list[dict]:
    grid = W.parse_table(W.find_table(text, heading))
    rows = []
    for r in grid[1:]:
        if len(r) < 3:
            continue
        ls = links(r[0]["text"])
        seasons = [season_end(d)[0] for t, d in links(r[2]["text"])]
        row = {"titles": W.number(r[1]["text"]), "seasons": seasons}
        if people:
            row.update({"name": ls[0][1] if ls else W.plain(r[0]["text"]).strip(), "country": flag(r[0]["text"])})
        else:
            row["club"] = club_key(ls[0][0])
        rows.append(row)
    return rows


def top_scorers(text: str, clubs: dict) -> list[dict]:
    grid = W.parse_table(W.find_table(text, r"=== Máximos anotadores ==="))
    out = []
    for r in grid[1:]:
        if len(r) < 6:
            continue
        label, end = season_end(r[0]["text"])
        player = links(r[1]["text"])
        team = links(r[2]["text"])
        out.append({"season": label, "year": end, "player": player[0][1] if player else W.plain(r[1]["text"]).strip(),
                    "country": flag(r[1]["text"]), "club": club_key(team[0][0]) if team else None,
                    "clubName": W.plain(team[0][1]) if team else W.plain(r[2]["text"]).strip(),
                    "games": W.number(r[3]["text"]), "points": W.number(r[4]["text"]),
                    "avg": float(W.plain(r[5]["text"]).replace(",", ".").strip() or 0)})
    return out


def career(text: str) -> dict[str, list[dict]]:
    """The all-time leaders: the top ten in games and points, and the leader of each other category."""
    grid = W.parse_table(W.find_table(text, r"==== En toda la historia ===="))
    out: dict[str, list[dict]] = {}
    cat = None
    for r in grid[1:]:
        texts = [c["text"] for c in r]
        if "bandera" not in texts[0]:
            label = W.plain(texts[0]).strip(" '")
            cat, texts = CATEGORIES.get(fold(label), label), texts[1:]
        if not texts or cat is None:
            continue
        ls = links(texts[0])
        nums = [W.number(W.plain(t).replace(" ", "").replace(" ", "")) for t in texts[1:]]
        value = W.plain(texts[1]).replace(" ", "").replace(" ", "").replace(",", ".")
        out.setdefault(cat, []).append({"name": ls[0][1] if ls else W.plain(texts[0]).strip(), "country": flag(texts[0]),
                                        "value": float(value) if "." in value else int(value), "games": nums[-2], "seasons": nums[-1]})
    return out


def coach_wins(text: str) -> list[dict]:
    grid = W.parse_table(W.find_table(text, r"==== Más partidos ganados ===="))
    return [{"name": links(r[0]["text"])[0][1], "wins": W.number(r[1]["text"])} for r in grid[1:] if len(r) >= 2 and links(r[0]["text"])]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    text = W.fetch_raw(PAGE, CACHE, args.refresh, pause=1.5, lang="es")
    clubs = participants(text)
    fs, skipped = finals(text, clubs)
    team_titles = titles_table(text, r"=== Campeonatos por equipos ===", people=False)
    coaches = titles_table(text, r"=== Campeonatos por entrenadores ===", people=True)
    players = titles_table(text, r"=== Campeonatos por jugadores ===", people=True)
    scorers = top_scorers(text, clubs)
    leaders = career(text)

    # The finals must agree with the article's titles table (a later season may only add titles).
    got = Counter(f["champion"] for f in fs)
    for row in team_titles:
        if got[row["club"]] != row["titles"]:
            later = sum(1 for f in fs if f["champion"] == row["club"] and f["year"] > TITLES_THROUGH)
            if got[row["club"]] - later != row["titles"]:
                raise SystemExit(f"{clubs.get(row['club'], {}).get('name', row['club'])}: {got[row['club']]} titles in the finals, "
                                 f"{row['titles']} in the titles table")
    if set(got) - {r["club"] for r in team_titles}:
        raise SystemExit(f"champions missing from the titles table: {set(got) - {r['club'] for r in team_titles}}")
    if len(fs) < 40 or fs[0]["season"] != "1985":
        raise SystemExit(f"only {len(fs)} finals parsed")

    used = {f[k] for f in fs for k in ("champion", "runnerUp", "mvpClub", "finalsMvpClub") if f.get(k)} | {s["club"] for s in scorers if s["club"]}
    unknown = sorted(u for u in used if u not in clubs)
    if unknown:
        raise SystemExit(f"clubs outside the participants list: {unknown}")
    # Readable ids for the page: the article title as a slug ("asociacion-deportiva-atenas").
    ids = {k: re.sub(r"[^a-z0-9]+", "-", k).strip("-") for k in clubs}
    for f in fs:
        for k in ("champion", "runnerUp", "mvpClub", "finalsMvpClub"):
            if f.get(k):
                f[k] = ids[f[k]]
    for x in scorers:
        x["club"] = ids.get(x["club"])
    clubs = {ids[k]: v for k, v in clubs.items()}
    out = {
        "updated": date.today().isoformat(),
        "source": {"label": "Spanish Wikipedia, Liga Nacional de Básquet", "url": "https://es.wikipedia.org/wiki/Liga_Nacional_de_B%C3%A1squet"},
        "clubs": clubs, "finals": fs, "noFinal": skipped, "coaches": coaches, "players": players,
        "topScorers": scorers, "career": leaders, "coachWins": coach_wins(text),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    top = ", ".join(f"{clubs[ids[c]]['name']} {n}" for c, n in got.most_common(3))
    print(f"LNB: {len(fs)} finals ({fs[0]['season']}–{fs[-1]['season']}), {len(got)} champions ({top}), {len(clubs)} clubs, "
          f"{len(scorers)} top scorers, {len(coaches)} coaches, {len(players)} players, career categories {list(leaders)}", file=sys.stderr)


if __name__ == "__main__":
    main()
