"""Build the Olympic Games dataset used by olympics/ (Summer and Winter Games).

Reads from Wikipedia: the medal table of every Games ({{Medals table}} template
on each "YYYY Summer/Winter Olympics medal table" page), the all-time medal
table by nation, the list of host cities and the lists of athletes with the
most medals and the most gold medals. Nation names and flags come from the
comparison of IOC, FIFA and ISO country codes.

Usage:
    python3 scripts/build_olympics.py            # use saved pages
    python3 scripts/build_olympics.py --refresh  # re-download them
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date

import wikitables as W
from build_football import RAW_DIR, ROOT, slug

OUTPUT = ROOT / "olympics" / "data" / "olympics.json"
CACHE = RAW_DIR / "olympics"
CODES_PAGE = "Comparison of alphabetic country codes"
ISO_PAGE = "ISO 3166-1"
ALLTIME_PAGE = "All-time Olympic Games medal table"
HOSTS_PAGE = "List of Olympic Games host cities"
ATHLETES_PAGE = "List of multiple Olympic medalists"
GOLD_PAGE = "List of multiple Olympic gold medalists"
SEASONS = ("Summer", "Winter")
MEDALS = ("gold", "silver", "bronze")

# Delegations that no longer exist or never had a country code of their own: (name, flagcdn code or None).
EXTRA = {
    "URS": ("Soviet Union", None), "EUN": ("Unified Team", None), "TCH": ("Czechoslovakia", None), "YUG": ("Yugoslavia", None),
    "SCG": ("Serbia and Montenegro", None), "GDR": ("East Germany", None), "FRG": ("West Germany", "de"),
    "EUA": ("United Team of Germany", None), "ANZ": ("Australasia", None), "BOH": ("Bohemia", None), "RU1": ("Russian Empire", None),
    "ROC": ("ROC (Russian Olympic Committee)", None), "RAU": ("United Arab Republic", None), "OAR": ("Olympic Athletes from Russia", None), "AIN": ("Individual Neutral Athletes", None),
    "IOA": ("Independent Olympic Athletes", None), "IOP": ("Independent Olympic Participants", None), "EOR": ("Refugee Olympic Team", None),
    "ZZX": ("Mixed team", None), "BWI": ("British West Indies", None), "AHO": ("Netherlands Antilles", "cw"), "RHO": ("Rhodesia", None),
    "SAA": ("Saar", None), "UAR": ("United Arab Republic", None), "TPE": ("Chinese Taipei", "tw"), "HKG": ("Hong Kong", "hk"),
    "PUR": ("Puerto Rico", "pr"), "KOS": ("Kosovo", "xk"), "GBR": ("Great Britain", "gb"), "ISV": ("Virgin Islands", "vi"),
    "BER": ("Bermuda", "bm"), "MIX": ("Mixed team", None),
}

# The code comparison uses formal names for a few countries; the site uses the common ones.
COMMON_NAMES = {"CHN": "China", "KOR": "South Korea", "PRK": "North Korea", "RUS": "Russia", "IRI": "Iran", "TAN": "Tanzania",
                "VIE": "Vietnam", "SYR": "Syria", "MDA": "Moldova", "LAO": "Laos", "BRU": "Brunei", "FSM": "Micronesia", "VEN": "Venezuela",
                "BOL": "Bolivia", "CZE": "Czech Republic"}

# The current Games: the medal count of a few leading nations, as a check on the parser.
EXPECTED = {("Summer", 2024): {"USA": (40, 44, 42), "CHN": (40, 27, 24), "JPN": (20, 12, 13), "AUS": (18, 19, 16)},
            ("Summer", 2020): {"USA": (39, 41, 33), "CHN": (38, 32, 19)},
            ("Winter", 2022): {"NOR": (16, 8, 13), "GER": (12, 10, 5)}}
EXPECTED_ATHLETES = {"Michael Phelps": (23, 3, 2), "Larisa Latynina": (9, 5, 4), "Marit Bjørgen": (8, 4, 3), "Paavo Nurmi": (9, 3, 0)}


def page(title: str, refresh: bool) -> str:
    text = W.fetch_raw(title, CACHE / f"{slug(title)}.wiki", refresh, pause=1.5)
    m = re.match(r"\s*#REDIRECT\s*\[\[([^\]|#]+)", text, re.I)
    return page(m.group(1), refresh) if m else text


def nation_directory(refresh: bool) -> dict[str, dict]:
    """IOC code -> {name, flag}: names from the code comparison, flags via ISO alpha-3 -> alpha-2."""
    iso = {}
    for grid in W.all_tables(page(ISO_PAGE, refresh)):
        labels = W.header_labels(grid[0])
        if "Alpha-2 code" in labels and "Alpha-3 code" in labels:
            a2, a3 = labels.index("Alpha-2 code"), labels.index("Alpha-3 code")
            for row in grid[1:]:
                mono = lambda t: (re.search(r"mono\|([A-Z]{2,3})", t) or re.search(r"\b([A-Z]{2,3})\b", W.plain(t)) or [None, ""])[1]
                two, three = mono(row[a2]["text"]), mono(row[a3]["text"])
                if re.fullmatch(r"[A-Z]{2}", two) and re.fullmatch(r"[A-Z]{3}", three):
                    iso[three] = two.lower()
    out = {}
    for grid in W.all_tables(page(CODES_PAGE, refresh)):
        labels = W.header_labels(grid[0])
        if labels[:5] != ["Flag", "Country", "IOC", "FIFA", "ISO"]:
            continue
        for row in grid[1:]:
            if len(row) < 5:
                continue
            ioc = W.plain(re.split(r"<hr", row[2]["text"])[0])
            if not re.fullmatch(r"[A-Z]{3}", ioc) or ioc in out:
                continue
            three = W.plain(re.split(r"<hr", row[4]["text"])[0])
            out[ioc] = {"name": W.plain(row[1]["text"]), "flag": iso.get(three)}
    for code, (name, flag) in EXTRA.items():
        out[code] = {"name": name, "flag": flag}
    for code, name in COMMON_NAMES.items():
        if code in out:
            out[code]["name"] = name
    return out


def medal_template(text: str, directory: dict) -> tuple[dict[str, tuple[int, int, int]], str | None]:
    """The {{Medals table}} counts and the host's code (given as a code, or as a linked country name)."""
    start = text.find("{{Medals table")
    body = text[start:text.find("\n}}", start)]
    counts = {}
    for code in dict.fromkeys(re.findall(r"gold_([A-Z0-9]{3})\s*=", body)):
        get = lambda medal: int((re.search(rf"\b{medal}_{code}\s*=\s*(\d+)", body) or [0, 0])[1])
        counts[code] = (get("gold"), get("silver"), get("bronze"))
    host = re.search(r"host_([A-Z0-9]{3})\s*=\s*yes", body) or re.search(r"\|\s*host\s*=\s*([A-Z]{3})\b", body)
    if host:
        return counts, host.group(1)
    named = re.search(r"\|\s*host\s*=\s*([^\n|]*\[\[[^\n]*?\]\])", body)
    if named:
        name = W.plain(named.group(1)).lower()
        code = next((c for c, n in directory.items() if n["name"].lower() == name), None)
        return counts, code
    return counts, None


def parse_hosts(refresh: bool) -> list[dict]:
    grid = W.all_tables(page(HOSTS_PAGE, refresh))[0]
    out = []
    for row in grid[1:]:
        if len(row) < 7:
            continue
        year = W.number(row[1]["text"])
        season = "Summer" if "Summer Olympics" in row[2]["text"] else "Winter" if "Winter Olympics" in row[3]["text"] else None
        if not year or not season:
            continue
        cancelled = "cancel" in (row[2]["text"] + row[3]["text"]).lower() or "not held" in (row[2]["text"] + row[3]["text"]).lower()
        city = ", ".join(W.plain(p) for p in re.split(r"<br\s*/?>", W.strip_refs(row[4]["text"])) if W.plain(p))
        country = re.search(r"name=([^|}]+)", row[5]["text"]) or re.search(r"\{\{\s*flag\s*\|([^|}]+)", row[5]["text"])
        out.append({"season": season, "year": year, "city": city, "country": (country.group(1) if country else W.plain(row[5]["text"])).strip(),
                    "region": W.plain(row[6]["text"]), "cancelled": cancelled})
    return out


def parse_alltime(refresh: bool) -> dict[str, dict]:
    """Per nation: Games attended and medals, Summer and Winter, from the all-time table."""
    out = {}
    for grid in W.all_tables(page(ALLTIME_PAGE, refresh)):
        if not grid or W.plain(grid[0][0]["text"]) != "Team":
            continue
        for row in grid[2:]:
            code = re.search(r"flag ?IOC\|([A-Z0-9]{3})", row[0]["text"]) if row else None
            nums = [W.number(c["text"]) for c in row[1:16]]
            if not code or len(nums) < 10 or any(n is None for n in nums[:10]):
                continue
            rec = {}
            for i, season in enumerate(SEASONS):
                games, g, s, b, _ = nums[i * 5:i * 5 + 5]
                rec[season] = {"games": games, "gold": g, "silver": s, "bronze": b}
            out.setdefault(code.group(1), rec)
    return out


def parse_athletes(refresh: bool) -> list[dict]:
    """Athletes with the most medals and the most golds (two lists, merged)."""
    athletes = {}
    for title in (ATHLETES_PAGE, GOLD_PAGE):
        for grid in W.all_tables(page(title, refresh)):
            labels = [l.strip() for l in W.header_labels(grid[0])]
            if labels[:4] != ["No.", "Athlete", "Nation", "Sport"] or "Gold" not in labels:
                continue
            col = {l: labels.index(l) for l in labels}
            for row in grid[1:]:
                if len(row) < len(labels):
                    continue
                name = W.person(row[col["Athlete"]]["text"])
                medals = [W.number(row[col[m.capitalize()]]["text"]) for m in MEDALS]
                if not name or any(m is None for m in medals):
                    continue
                name = re.sub(r"'''|\s*\(.*?\)$", "", name).strip()
                key = (name, W.plain(row[col["Years"]]["text"]))
                if key in athletes:
                    continue
                sports = [x for _, x in W.links(row[col["Sport"]]["text"])] or [W.plain(row[col["Sport"]]["text"])]
                sports = [re.sub(r"\s+at the (Summer|Winter) Olympics$", "", s) for s in sports]
                gender_col = col.get("Gender", col.get("Sex"))
                athletes[key] = {
                    "name": name, "nations": W.flag_codes(row[col["Nation"]]["text"]) or re.findall(r"flag ?IOC\|([A-Z0-9]{3})", row[col["Nation"]]["text"]),
                    "sport": " / ".join(dict.fromkeys(sports)), "years": key[1].replace("-", "–"),
                    "season": W.plain(row[col["Games"]]["text"]), "gender": W.plain(row[gender_col]["text"]) if gender_col is not None else "",
                    **dict(zip(MEDALS, medals)),
                }
    return sorted(athletes.values(), key=lambda a: (-(a["gold"] + a["silver"] + a["bronze"]), -a["gold"]))


def build(refresh: bool) -> dict:
    directory = nation_directory(refresh)
    hosts = parse_hosts(refresh)
    host_of = {(h["season"], h["year"]): h for h in hosts}
    games = []
    for season, first in (("Summer", 1896), ("Winter", 1924)):
        for h in sorted((h for h in hosts if h["season"] == season and not h["cancelled"] and h["year"] <= date.today().year), key=lambda h: h["year"]):
            title = f"{h['year']} {season} Olympics medal table"
            try:
                counts, host = medal_template(page(title, refresh), directory)
            except Exception as err:  # Games that were cancelled (1916, 1940, 1944), or just held, have no page
                if h["year"] not in (1916, 1940, 1944):
                    print(f"skipping {title}: {err}", file=sys.stderr)
                continue
            if not counts:
                continue
            games.append({
                "season": season, "year": h["year"], "city": h["city"], "country": h["country"], "region": h["region"], "host": host,
                "medals": {c: list(m) for c, m in sorted(counts.items(), key=lambda kv: (-kv[1][0], -kv[1][1], -kv[1][2]))},
            })
    games.sort(key=lambda g: (g["year"], g["season"] == "Summer"))
    alltime = parse_alltime(refresh)
    athletes = parse_athletes(refresh)
    upcoming = [h for h in hosts if h["year"] > max(g["year"] for g in games)]
    codes = {c for g in games for c in g["medals"]} | set(alltime) | {c for a in athletes for c in a["nations"]} | {g["host"] for g in games if g["host"]}
    return {
        "meta": {
            "generated": date.today().isoformat(),
            "through": f"{games[-1]['year']} {games[-1]['season']} Olympics",
            "sources": [f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}" for t in (ALLTIME_PAGE, HOSTS_PAGE, ATHLETES_PAGE, GOLD_PAGE)],
        },
        "nations": {c: directory.get(c, {"name": c, "flag": None}) for c in sorted(codes)},
        "games": games,
        "upcoming": [{k: h[k] for k in ("season", "year", "city", "country")} for h in sorted(upcoming, key=lambda h: h["year"])],
        "alltime": alltime,
        "athletes": athletes,
    }


def validate(data: dict) -> list[str]:
    errors = []
    by = {(g["season"], g["year"]): g for g in data["games"]}
    for key, expected in EXPECTED.items():
        got = by.get(key, {}).get("medals", {})
        for code, medals in expected.items():
            if tuple(got.get(code, ())) != medals:
                errors.append(f"{key[1]} {key[0]} {code}: {got.get(code)}, expected {medals}")
    counts = Counter(g["season"] for g in data["games"])
    if counts["Summer"] < 30 or counts["Winter"] < 24:
        errors.append(f"only {counts['Summer']} Summer and {counts['Winter']} Winter Games")
    for g in data["games"]:
        if not g["host"]:
            errors.append(f"{g['year']} {g['season']}: no host")
    names = {a["name"]: a for a in data["athletes"]}
    for name, medals in EXPECTED_ATHLETES.items():
        a = names.get(name)
        if not a or (a["gold"], a["silver"], a["bronze"]) != medals:
            errors.append(f"{name}: {a and (a['gold'], a['silver'], a['bronze'])}, expected {medals}")
    unknown = sorted(c for c, n in data["nations"].items() if n["name"] == c)
    if unknown:
        errors.append(f"nations without a name (add them to EXTRA): {unknown}")
    # The all-time table and the per-Games tables should agree for the leading nations.
    summed = defaultdict(lambda: defaultdict(Counter))
    for g in data["games"]:
        for c, m in g["medals"].items():
            for medal, n in zip(MEDALS, m):
                summed[c][g["season"]][medal] += n
    off = []
    for c, rec in data["alltime"].items():
        for season in SEASONS:
            mine = tuple(summed[c][season][m] for m in MEDALS)
            theirs = tuple(rec[season][m] for m in MEDALS)
            if mine != theirs:
                off.append(f"{c} {season} {mine} vs {theirs}")
    data["meta"]["tableDifferences"] = len(off)
    if off:
        print(f"warning: {len(off)} nation/season totals differ between the per-Games and all-time tables: {off[:12]}", file=sys.stderr)
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="re-download the Wikipedia pages")
    args = parser.parse_args()
    data = build(args.refresh)
    errors = validate(data)
    if errors:
        sys.exit("validation failed:\n  " + "\n  ".join(errors))
    if OUTPUT.exists():
        old = json.loads(OUTPUT.read_text(encoding="utf-8"))
        strip = lambda d: {**d, "meta": {k: v for k, v in d["meta"].items() if k != "generated"}}
        if strip(old) == strip(data):
            print(f"{OUTPUT.relative_to(ROOT)} is up to date")
            return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(data['games'])} Games, {len(data['athletes'])} athletes")


if __name__ == "__main__":
    main()
