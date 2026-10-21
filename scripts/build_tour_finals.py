"""Build the ATP Finals and WTA Finals dataset used by tennis/finals: every edition's champion, runner-up and
host city, every match, and each player's result at each edition.

Sources:
  * Jeff Sackmann's ATP and WTA match files (every Finals match; the WTA files start with the 1975 edition).
  * Wikipedia's ATP Finals and WTA Finals pages: the list of finals (every champion, checked against the
    match files) and the venues table.

Usage:
    python3 scripts/build_tour_finals.py            # cached files
    python3 scripts/build_tour_finals.py --refresh  # re-download the Wikipedia pages
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wikitables as W  # noqa: E402
from build_grand_slams import load_overrides, nationality  # noqa: E402
from build_tennis_ages import finals_champions, nation  # noqa: E402
from olympic_events import nation_info  # noqa: E402
from tennis_data import ascii_key, download, is_walkover, read_matches, start_date  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "raw" / "wikipedia"
OUTPUT = ROOT / "tennis" / "finals" / "data" / "finals.json"

TOURS = {
    "atp": {
        "name": "ATP Finals", "page": "ATP Finals", "first": 1970,
        # The Finals under each of their names in the match files (the season-ending Masters until 1989).
        "names": {"Masters", "Masters Dec", "Tour Finals", "Masters Cup"},
    },
    "wta": {
        "name": "WTA Finals", "page": "WTA Finals", "first": 1975,
        "names": {"Virginia Slims Championships", "Virginia Slims Championships 1", "Virginia Slims Championships 2",
                  "Avon Championships", "WTA Tour Championships", "WTA Championships", "WTA Finals", "Singapore",
                  "Shenzhen Finals", "Guadalajara Finals", "Fort Worth Finals", "Cancun Finals", "Riyadh Finals"},
    },
}
# Known records the build must reproduce.
EXPECT = {
    "atp": {"titles": {"Novak Djokovic": 7, "Roger Federer": 6, "Ivan Lendl": 5, "Pete Sampras": 5},
            "record": {"Roger Federer": (59, 17)}, "appearances": {"Roger Federer": 17}},
    "wta": {"titles": {"Martina Navratilova": 8, "Steffi Graf": 5, "Serena Williams": 5, "Chris Evert": 4}},
}
ROUND_ORDER = {"W": 0, "F": 1, "SF": 2, "QF": 3, "R16": 4, "RR": 5}


def page(title: str, refresh: bool) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return W.fetch_raw(title, CACHE / f"{slug}.wiki", refresh, pause=1.5)


def edition_key(row: dict, tour: str) -> str:
    """The edition a match belongs to, as Wikipedia labels it: ATP Masters played in January count for the
    previous season; the WTA held two championships in 1986 (March and November)."""
    d = start_date(row)
    if tour == "atp":
        return str(d.year - 1 if d.month <= 2 else d.year)
    if d.year == 1986:
        return "1986 (March)" if d.month <= 6 else "1986 (November)"
    return str(d.year)


def venues(text: str) -> list[dict]:
    """Host city per year from the 'Venues' table."""
    start = re.search(r"^=+\s*Venues\s*=+", text, re.M)
    table = W.parse_table(W.find_table(text[start.start():], r"Venues"))
    # A header row written as "!Surface||Stadium||Capacity" comes through as one cell; split it.
    head = [h.strip().lower() for c in table[0] for h in re.sub(r'\|\|\s*[a-z]+="[^"]*"\s*\|', "||", W.plain(c["text"])).split("||")]
    out = []
    for row in table[1:]:
        if all(c["header"] for c in row) and not re.search(r"\d{4}", row[0]["text"]):
            continue
        cells = {h: row[i]["text"] for i, h in enumerate(head) if i < len(row)}
        years_txt = W.plain(cells.get("years", ""))
        ys = [int(y) for y in re.findall(r"\d{4}|(?<=[–-])\d{2}\b", years_txt.replace("–", "-")) if y]
        m = re.match(r"\s*(\d{4})(?:\s*[–-]\s*(\d{2,4}))?", years_txt)
        if not m:
            continue
        a = int(m.group(1))
        b = m.group(2)
        b = a if not b else int(b) if len(b) == 4 else int(str(a)[:2] + b)
        del ys
        city = W.plain(cells.get("city", "")).split(",")[0].strip()
        country = nation(cells.get("country") or cells.get("city", ""))
        out.append({"from": a, "to": b, "city": city, "nation": country, "venue": W.plain(cells.get("venue") or cells.get("stadium", "")).strip(),
                    "surface": W.plain(cells.get("surface", "")).strip()})
    return out


def build(refresh: bool) -> tuple[dict, list[str]]:
    data = {"meta": {"generated": date.today().isoformat(), "sources": []}, "tours": {}, "nations": {}}
    errors = []
    for tour, cfg in TOURS.items():
        text = page(cfg["page"], refresh)
        data["meta"]["sources"].append(f"https://en.wikipedia.org/wiki/{cfg['page'].replace(' ', '_')}")
        wiki_finals = finals_champions(text)
        hosts = venues(text)
        overrides = load_overrides(tour)
        paths = download(cfg["first"], date.today().year, False, tour)
        # The ATP names are unique to the Finals (one 1998 row gives a draw of 64); WTA names like "Singapore" aren't.
        rows = read_matches(paths, lambda r: r["tourney_name"] in cfg["names"] and (tour == "atp" or int(r["draw_size"] or 0) <= 16))

        matches = []
        for r in rows:
            when = start_date(r)
            matches.append({
                "edition": edition_key(r, tour), "round": r["round"], "score": r["score"], "walkover": is_walkover(r["score"]),
                "winner": r["winner_name"], "loser": r["loser_name"],
                "winnerNation": nationality(r["winner_name"], r["winner_ioc"], when, overrides),
                "loserNation": nationality(r["loser_name"], r["loser_ioc"], when, overrides),
            })

        # Wikipedia's list of finals, keyed like the match files' editions.
        wiki = {}
        for f in wiki_finals:
            key = str(f["year"])
            if f["year"] == 1986 and tour == "wta":
                key = "1986 (March)" if "March" in f["page"] else "1986 (November)"
            wiki[key] = f
        by_edition = defaultdict(list)
        for m in matches:
            by_edition[m["edition"]].append(m)

        editions = []
        for key in sorted(set(wiki) | set(by_edition), key=lambda k: (int(k[:4]), k)):
            ms = by_edition.get(key, [])
            w = wiki.get(key)
            final = next((m for m in ms if m["round"] == "F"), None)
            champ = final["winner"] if final else (w["name"] if w else None)
            if not final and champ:  # Round robin only (1970, 1971): use the match files' spelling of the champion.
                champ = next((m[s] for m in ms for s in ("winner", "loser") if ascii_key(m[s]) == ascii_key(champ)), champ)
            same = lambda a, b: ascii_key(a).startswith(ascii_key(b)) or ascii_key(b).startswith(ascii_key(a))  # noqa: E731
            if w and champ and not same(champ, w["name"]):
                errors.append(f"{tour} {key}: champion {champ} in the match files, {w['name']} on Wikipedia")
            if not w:
                errors.append(f"{tour} {key}: not in Wikipedia's list of finals")
            year = int(key[:4])
            host = next((h for h in hosts if h["from"] <= year <= h["to"]), None)
            # Each player's best result at this edition.
            res: dict[str, str] = {}
            nat: dict[str, str] = {}
            for m in ms:
                for side, other in (("winner", "loser"), ("loser", "winner")):
                    nat[m[side]] = m[f"{side}Nation"]
                rnd = m["round"] if m["round"] in ROUND_ORDER else "RR"
                for p in (m["winner"], m["loser"]):
                    res.setdefault(p, "RR")
                if rnd != "RR":
                    if ROUND_ORDER[rnd] < ROUND_ORDER[res[m["loser"]]]:
                        res[m["loser"]] = rnd
            if final:
                res[final["winner"]] = "W"
            elif champ in res:
                res[champ] = "W"
            players = []
            for p, r_ in res.items():
                won = sum(1 for m in ms if m["winner"] == p and not m["walkover"])
                lost = sum(1 for m in ms if m["loser"] == p and not m["walkover"])
                players.append({"name": p, "nation": nat.get(p), "result": r_, "won": won, "lost": lost})
            players.sort(key=lambda p: (ROUND_ORDER[p["result"]], -p["won"]))
            runner = final["loser"] if final else None
            editions.append({
                "edition": key, "year": year,
                "champion": champ or "", "championNation": nat.get(champ) or (w or {}).get("nation"),
                "runnerUp": runner or (None if ms else (w or {}).get("runnerUp")),
                "runnerUpNation": nat.get(runner) if runner else (None if ms else (w or {}).get("runnerUpNation")),
                "score": final["score"] if final else ("Round robin" if ms else ((w or {}).get("score") or "").replace(",", "") or None),
                "city": host["city"] if host else None, "hostNation": host["nation"] if host else None,
                "venue": host["venue"] if host else None, "surface": host["surface"] if host else None,
                "matchData": bool(ms), "players": players,
            })
        data["tours"][tour] = {"name": cfg["name"], "editions": editions, "hosts": hosts,
                               "matches": [{k: m[k] for k in ("edition", "round", "winner", "loser", "score", "walkover")} for m in matches]}
        for e in editions:
            for c in [e["championNation"], e["runnerUpNation"], e["hostNation"], *[p["nation"] for p in e["players"]]]:
                if c:
                    data["nations"].setdefault(c, nation_info(c))

        # Checks.
        exp = EXPECT[tour]
        titles = Counter(e["champion"] for e in editions)
        for name, n in exp["titles"].items():
            if titles[name] != n:
                errors.append(f"{tour}: {name} {titles[name]} titles, expected {n}")
        for name, (w_, l_) in exp.get("record", {}).items():
            got = (sum(p["won"] for e in editions for p in e["players"] if p["name"] == name),
                   sum(p["lost"] for e in editions for p in e["players"] if p["name"] == name))
            if got != (w_, l_):
                errors.append(f"{tour}: {name} {got[0]}-{got[1]} at the Finals, expected {w_}-{l_}")
        for name, n in exp.get("appearances", {}).items():
            got = sum(1 for e in editions for p in e["players"] if p["name"] == name)
            if got != n:
                errors.append(f"{tour}: {name} {got} appearances, expected {n}")
        for e in editions:
            if e["matchData"] and sum(1 for p in e["players"] if p["result"] == "W") != 1:
                errors.append(f"{tour} {e['edition']}: {sum(1 for p in e['players'] if p['result'] == 'W')} champions")
            if not e["city"]:
                errors.append(f"{tour} {e['edition']}: no host city")
        missing = [e["edition"] for e in editions if not e["matchData"]]
        allowed = {"atp": set(), "wta": {"1972", "1973", "1974"}}[tour]
        if set(missing) - allowed:
            errors.append(f"{tour}: editions without match data {sorted(set(missing) - allowed)}")
    unknown = sorted(c for c, n in data["nations"].items() if n["name"] == c)
    if unknown:
        errors.append(f"unknown nations {unknown}")
    data["nations"] = dict(sorted(data["nations"].items()))
    return data, errors


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="re-download the Wikipedia pages")
    args = ap.parse_args()
    data, errors = build(args.refresh)
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    old = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else None
    strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}  # noqa: E731
    if old and strip(old) == strip(data):
        print(f"{OUTPUT.relative_to(ROOT)} is up to date")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    t = data["tours"]
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(t['atp']['editions'])} ATP and {len(t['wta']['editions'])} WTA editions, "
          f"{len(t['atp']['matches'])} + {len(t['wta']['matches'])} matches")


if __name__ == "__main__":
    main()
