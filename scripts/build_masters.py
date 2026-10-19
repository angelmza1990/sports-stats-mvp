"""Build the ATP Masters 1000 and WTA 1000 datasets used by tennis/masters-1000 and tennis/wta-1000.

The list of finals comes from Wikipedia's yearly results tables (ATP Masters
1000 and its earlier names since 1990; WTA Tier I, Premier Mandatory and
Premier 5, and WTA 1000 since 1990). Each final is matched to its tournament
in Jeff Sackmann's ATP/WTA match files to count every match; events the files
don't cover yet are rebuilt from their Wikipedia draw pages.

Usage:
    python3 scripts/build_masters.py              # both tours, cached files
    python3 scripts/build_masters.py --tour wta   # WTA 1000 only
    python3 scripts/build_masters.py --refresh    # re-download everything
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import wikitables as W
from build_grand_slams import COUNTRIES, load_overrides, nationality
from tennis_data import (
    RAW_DIR, ROOT, ascii_key, ascii_name, download, draw_from_wikipedia, final_date, is_walkover, read_matches,
)

CACHE = RAW_DIR / "wikipedia" / "tennis"
FIRST_YEAR = 1990
TOP_N = 25
SURFACES = ["Hard", "Clay", "Carpet", "Grass"]

# Canonical event -> (pattern matching Wikipedia labels, still on the calendar, approx. final (month, day), surface).
# Calendar order. Patterns are tried in order against the lowercased label.
EVENTS = {
    "atp": [
        ("Indian Wells", r"indian wells", True, (3, 16), "Hard"),
        ("Miami", r"miami|key biscayne", True, (3, 30), "Hard"),
        ("Monte Carlo", r"monte.?carlo", True, (4, 13), "Clay"),
        ("Madrid", r"madrid", True, (5, 4), "Clay"),
        ("Rome", r"rome|italian", True, (5, 18), "Clay"),
        ("Hamburg", r"hamburg", False, (5, 11), "Clay"),
        ("Canada", r"canad|montr[eé]al|toronto", True, (8, 7), "Hard"),
        ("Cincinnati", r"cincinnati", True, (8, 18), "Hard"),
        ("Shanghai", r"shanghai", True, (10, 12), "Hard"),
        ("Stockholm", r"stockholm", False, (10, 25), "Carpet"),
        ("Essen", r"essen", False, (10, 29), "Carpet"),
        ("Stuttgart", r"stuttgart", False, (10, 28), "Hard"),
        ("Paris", r"paris", True, (11, 2), "Hard"),
    ],
    "wta": [
        ("Doha", r"doha|qatar", True, (2, 15), "Hard"),
        ("Dubai", r"dubai", True, (2, 22), "Hard"),
        ("Tokyo", r"tokyo|pan pacific", False, (2, 2), "Carpet"),
        ("Boca Raton", r"boca raton", False, (3, 4), "Hard"),
        ("Indian Wells", r"indian wells", True, (3, 16), "Hard"),
        ("Miami", r"miami|key biscayne", True, (3, 30), "Hard"),
        ("Charleston", r"charleston|hilton head", False, (4, 13), "Clay"),
        ("Madrid", r"madrid", True, (5, 4), "Clay"),
        ("Berlin", r"berlin|german open", False, (5, 11), "Clay"),
        ("Rome", r"rome|italian", True, (5, 18), "Clay"),
        ("San Diego", r"san diego", False, (8, 3), "Hard"),
        ("Canada", r"canad|montr[eé]al|toronto", True, (8, 7), "Hard"),
        ("Cincinnati", r"cincinnati", True, (8, 18), "Hard"),
        ("Guadalajara", r"guadalajara", False, (9, 24), "Hard"),
        ("Beijing", r"beijing|china open", True, (10, 5), "Hard"),
        ("Wuhan", r"wuhan", True, (10, 12), "Hard"),
        ("Moscow", r"moscow|kremlin", False, (10, 19), "Carpet"),
        ("Zurich", r"z[uü]rich", False, (10, 19), "Carpet"),
        ("Chicago", r"chicago", False, (2, 11), "Carpet"),
        ("Philadelphia", r"philadelphia", False, (11, 9), "Carpet"),
    ],
}

TOURS = {
    "atp": {
        "main": "ATP Masters 1000 tournaments",
        "name": "ATP Masters 1000",
        "output": ROOT / "tennis" / "masters-1000" / "data" / "masters-1000.json",
        # Retired players' totals are exact; active ones are minimums.
        "titles": {"Rafael Nadal": 36, "Roger Federer": 28, "Andre Agassi": 17, "Andy Murray": 14, "Pete Sampras": 11},
        "active": {"Novak Djokovic": 40},
        "per_year": {y: 9 for y in range(1990, 2020)} | {2020: 3, 2021: 8, 2022: 8, 2023: 9, 2024: 9, 2025: 9},
    },
    "wta": {
        "main": "WTA 1000 tournaments",
        "name": "WTA 1000",
        "output": ROOT / "tennis" / "wta-1000" / "data" / "wta-1000.json",
        "titles": {"Serena Williams": 23, "Martina Hingis": 17, "Steffi Graf": 15, "Maria Sharapova": 14,
                   "Lindsay Davenport": 11, "Justine Henin": 10, "Conchita Martinez": 9, "Simona Halep": 9, "Petra Kvitova": 9},
        "active": {"Iga Swiatek": 12, "Aryna Sabalenka": 11, "Victoria Azarenka": 10},
        "per_year": {2020: 3, 2021: 7, 2022: 8, 2023: 9, 2024: 10, 2025: 10},
    },
}


def page(title: str, refresh: bool) -> str:
    """Raw wikitext, following one redirect."""
    text = W.fetch_raw(title, CACHE / f"{re.sub(r'[^a-z0-9]+', '-', ascii_name(title).lower())}.wiki", refresh, pause=1.0)
    m = re.match(r"\s*#REDIRECT\s*\[\[([^\]|#]+)", text, re.I)
    return page(m.group(1), refresh) if m else text


def event_of(label: str, tour: str) -> str | None:
    low = label.lower()
    return next((name for name, pattern, *_ in EVENTS[tour] if re.search(pattern, low)), None)


def tokens(name: str) -> set[str]:
    plain = ascii_name(name).lower()
    return {t for t in re.split(r"[^a-z]+", plain) if len(t) > 1}


def wiki_score(text: str) -> str:
    """'7–6(8–6), 6–4' -> '7-6(6) 6-4' (match-file notation keeps the set loser's tiebreak points)."""
    text = W.plain(text).replace("–", "-").replace("−", "-")
    text = re.sub(r"\((\d+)-(\d+)\)", lambda m: f"({min(int(m.group(1)), int(m.group(2)))})", text)
    return re.sub(r"\s*,\s*", " ", text).strip()


def yearly_finals(tour: str, refresh: bool) -> list[dict]:
    """Every singles final listed on the yearly results pages."""
    cfg = TOURS[tour]
    main = page(cfg["main"], refresh)
    titles = dict(re.findall(r"===\s*(\d{4})\s*===\s*\n\{\{Main\|([^}|]+)", main))
    finals = []
    for year in range(FIRST_YEAR, date.today().year + 1):
        title = titles.get(str(year)) or f"{year} {cfg['main']}"
        try:
            text = page(title, refresh)
        except Exception as err:  # the current year's page may not exist yet
            if year == date.today().year:
                print(f"{tour}: no results page for {year} yet ({err})", file=sys.stderr)
                continue
            raise
        seen = set()
        for row in W.parse_table(W.find_table(text, r"==\s*Results", 0))[1:]:
            if len(row) < 4:
                continue  # cancelled (2020-22)
            head = row[0]["text"]
            draw = re.search(r"\[\[([^\]|]*singles[^\]|]*)", head, re.I)
            label = W.plain(re.split(r"<br|\{\{small", head)[0])
            key = draw.group(1) if draw else label
            if key in seen:
                continue
            seen.add(key)
            champion = W.person(row[1]["text"])
            if not champion or not W.plain(row[1]["text"]):
                continue  # not played yet
            event = event_of(label, tour)
            finals.append({
                "year": year, "label": label, "event": event, "draw": draw.group(1) if draw else None,
                "champion": re.sub(r"[*§]+$", "", champion).strip(), "championIoc": W.flag_code(row[1]["text"]),
                "runnerUp": re.sub(r"[*§]+$", "", W.person(row[2]["text"]) or "").strip(), "runnerUpIoc": W.flag_code(row[2]["text"]),
                "score": wiki_score(row[3]["text"]),
            })
    return finals


def build(tour: str, refresh: bool) -> dict:
    cfg = TOURS[tour]
    events = {name: {"current": cur, "final": fin, "surface": surf} for name, _, cur, fin, surf in EVENTS[tour]}
    finals = yearly_finals(tour, refresh)
    unknown = sorted({f["label"] for f in finals if not f["event"]})
    if unknown:
        sys.exit(f"{tour}: events missing from EVENTS: {unknown}")

    paths = download(FIRST_YEAR, date.today().year, refresh, tour)
    rows = read_matches(paths, lambda r: r["tourney_level"] not in ("D", "CC", "E", "J") and "qual" not in r["tourney_name"].lower())
    by_year = defaultdict(list)
    for r in rows:
        by_year[int(r["tourney_date"][:4])].append(r)
    known = {ascii_key(r[f"{s}_name"]): r[f"{s}_name"] for r in rows for s in ("winner", "loser")}
    iocs = {r[f"{s}_name"]: r[f"{s}_ioc"] for r in rows for s in ("winner", "loser")}
    overrides = load_overrides(tour)

    editions, matches, added, final_only = [], [], [], []
    for f in finals:
        cands = [r for r in by_year[f["year"]] if r["round"] == "F"
                 and tokens(r["winner_name"]) & tokens(f["champion"]) and tokens(r["loser_name"]) & tokens(f["runnerUp"])]
        if len(cands) > 1:
            cands = [r for r in cands if event_of(r["tourney_name"], tour) == f["event"]]
        if cands:
            final = cands[0]
            tid = final["tourney_id"]
            event_rows = [r for r in by_year[f["year"]] if r["tourney_id"] == tid]
            when = final_date(final)
            source = "match data"
        else:
            month, day = events[f["event"]]["final"]
            base = {"tourney_name": f["event"], "tourney_level": "M", "tourney_date": f"{f['year']}{month:02d}{day:02d}",
                    "surface": events[f["event"]]["surface"], "tourney_id": f"wiki-{f['year']}-{f['event']}"}
            try:
                event_rows = draw_from_wikipedia(f["draw"], base, refresh, known, iocs) if f["draw"] else []
            except (LookupError, ValueError) as err:
                print(f"{tour}: {f['year']} {f['event']}: {err}", file=sys.stderr)
                event_rows = []
            when = date(f["year"], month, day)
            final = next((r for r in event_rows if r["round"] == "F"), None)
            if final:
                source = "wikipedia"
                added.append(f"{f['event']} {f['year']}")
            else:
                # Keep the final from the results table, without its matches.
                name = lambda n: known.get(ascii_key(n), ascii_name(n))
                final = {"winner_name": name(f["champion"]), "loser_name": name(f["runnerUp"]), "score": f["score"],
                         "winner_ioc": f["championIoc"] or iocs.get(name(f["champion"]), ""),
                         "loser_ioc": f["runnerUpIoc"] or iocs.get(name(f["runnerUp"]), ""), "surface": base["surface"]}
                source = "results table"
                final_only.append(f"{f['event']} {f['year']}")
        surface = final["surface"] if final.get("surface") in SURFACES else events[f["event"]]["surface"]
        ioc = lambda side: nationality(final[f"{side}_name"], final[f"{side}_ioc"] or f[f"{'champion' if side == 'winner' else 'runnerUp'}Ioc"] or "", when, overrides)
        editions.append({
            "event": f["event"], "year": f["year"], "label": str(f["year"]), "date": when.isoformat(),
            "champion": final["winner_name"], "championIoc": ioc("winner"),
            "runnerUp": final["loser_name"], "runnerUpIoc": ioc("loser"),
            "score": final["score"], "surface": surface, "source": source,
        })
        for r in event_rows:
            matches.append((f["event"], when, r))
    editions.sort(key=lambda e: e["date"])

    # Match records per player (walkovers excluded), per event, for former events together, and overall.
    current = [name for name, e in events.items() if e["current"]]
    former = [name for name, e in events.items() if not e["current"] and any(x["event"] == name for x in editions)]
    record: dict[str, Counter] = defaultdict(Counter)
    player_iocs: dict[str, Counter] = defaultdict(Counter)
    for event, when, r in matches:
        if is_walkover(r["score"]):
            continue
        for side, result in (("winner", "won"), ("loser", "lost")):
            name = r[f"{side}_name"]
            for scope in ("All", event, "Former" if event in former else None):
                if scope:
                    record[name][(scope, result)] += 1
            player_iocs[name][nationality(name, r[f"{side}_ioc"], when, overrides)] += 1

    def top(scope: str) -> list[dict]:
        entries = [
            {"player": name, "ioc": player_iocs[name].most_common(1)[0][0], "won": c[(scope, "won")], "lost": c[(scope, "lost")]}
            for name, c in record.items() if c[(scope, "won")] + c[(scope, "lost")] > 0
        ]
        by_won = sorted(entries, key=lambda e: (-e["won"], e["lost"]))[:TOP_N]
        by_played = sorted(entries, key=lambda e: (-(e["won"] + e["lost"]), -e["won"]))[:TOP_N]
        return sorted({e["player"]: e for e in by_won + by_played}.values(), key=lambda e: -e["won"])

    tabs = [{"key": "All", "label": f"All {cfg['name']}"}] + [{"key": e, "label": e} for e in current]
    if former:
        tabs.append({"key": "Former", "label": "Former events", "events": former})
    match_records = {t["key"]: top(t["key"]) for t in tabs}
    used = {e["championIoc"] for e in editions} | {e["runnerUpIoc"] for e in editions}
    used |= {e["ioc"] for lst in match_records.values() for e in lst}
    used_surfaces = [s for s in SURFACES if any(e["surface"] == s for e in editions)]
    last = editions[-1]
    return {
        "meta": {
            "generated": date.today().isoformat(),
            "through": f"{last['event']} {last['label']}",
            "tour": tour,
            "name": cfg["name"],
            "sources": [
                f"Jeff Sackmann / Tennis Abstract {tour.upper()} match data (CC BY-NC-SA 4.0)",
                f"https://en.wikipedia.org/wiki/{cfg['main'].replace(' ', '_')} (CC BY-SA 4.0)",
            ],
            "fromWikipedia": added,
            "finalsOnly": final_only,
        },
        "events": [{"key": name, "current": events[name]["current"]} for name in [*current, *former]],
        "tabs": tabs,
        "colorBy": "surface",
        "colors": used_surfaces,
        "countries": {code: {"name": COUNTRIES[code][0], "flag": COUNTRIES[code][1]} for code in sorted(used) if code in COUNTRIES},
        "editions": editions,
        "matchRecords": match_records,
    }


def validate(tour: str, data: dict) -> list[str]:
    cfg = TOURS[tour]
    errors = []
    titles = Counter(e["champion"] for e in data["editions"])
    for name, n in cfg["titles"].items():
        if titles[name] != n:
            errors.append(f"{name}: {titles[name]} titles, expected {n}")
    for name, n in cfg["active"].items():
        if titles[name] < n:
            errors.append(f"{name}: {titles[name]} titles, expected at least {n}")
    per_year = Counter(e["year"] for e in data["editions"])
    for year, n in cfg["per_year"].items():
        if per_year[year] != n:
            errors.append(f"{year}: {per_year[year]} finals, expected {n}")
    unknown = {e[k] for e in data["editions"] for k in ("championIoc", "runnerUpIoc")} - set(data["countries"])
    if unknown:
        errors.append(f"countries missing from COUNTRIES: {sorted(unknown)}")
    for e in data["editions"]:
        if not e["champion"] or e["champion"] == e["runnerUp"]:
            errors.append(f"bad final: {e}")
    if data["meta"]["finalsOnly"]:
        print(f"{tour}: finals without match data: {data['meta']['finalsOnly']}", file=sys.stderr)
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download raw files")
    parser.add_argument("--tour", choices=list(TOURS), action="append", help="default: both")
    args = parser.parse_args()

    failed = False
    for tour in args.tour or list(TOURS):
        out = TOURS[tour]["output"]
        data = build(tour, args.refresh)
        errors = validate(tour, data)
        if errors:
            print(f"{tour}: validation failed:\n  " + "\n  ".join(errors), file=sys.stderr)
            failed = True
            continue
        if out.exists():
            old = json.loads(out.read_text(encoding="utf-8"))
            strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}
            if strip(old) == strip(data):
                print(f"{out.relative_to(ROOT)} is up to date")
                continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}: {len(data['editions'])} finals, through {data['meta']['through']}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
