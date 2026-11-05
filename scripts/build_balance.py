"""Build football/league-balance/data/balance.json: every national champion of the 20 league pages, side by side.

Reads the datasets written by build_leagues.py and build_football.py (no downloads), keeps each title's year,
season and champion, and the names, crests and countries of the champions. The page computes the measures
(effective number of champions, the top two's share, streaks) from these lists.

Usage:
    python3 scripts/build_balance.py
"""

from __future__ import annotations

import json
from datetime import date

from build_football import COUNTRIES, ROOT

# Page folder -> (short label, country code). Order: Europe, then South America, then North America.
LEAGUES = {
    "premier-league": ("England", "ENG"),
    "la-liga": ("Spain", "ESP"),
    "serie-a": ("Italy", "ITA"),
    "bundesliga": ("Germany", "GER"),
    "ligue-1": ("France", "FRA"),
    "primeira-liga": ("Portugal", "POR"),
    "eredivisie": ("Netherlands", "NED"),
    "scottish-premiership": ("Scotland", "SCO"),
    "super-lig": ("Turkey", "TUR"),
    "argentine-primera": ("Argentina", "ARG"),
    "brasileirao": ("Brazil", "BRA"),
    "uruguayan-primera": ("Uruguay", "URU"),
    "paraguayan-primera": ("Paraguay", "PAR"),
    "chilean-primera": ("Chile", "CHI"),
    "colombian-primera": ("Colombia", "COL"),
    "ecuadorian-serie-a": ("Ecuador", "ECU"),
    "peruvian-primera": ("Peru", "PER"),
    "bolivian-primera": ("Bolivia", "BOL"),
    "liga-mx": ("Mexico", "MEX"),
    "mls": ("United States", "USA"),
}
OUT = ROOT / "football" / "league-balance" / "data" / "balance.json"


def main() -> None:
    leagues, clubs, countries = [], {}, {}
    for key, (label, country) in LEAGUES.items():
        data = json.loads((ROOT / "football" / key / "data" / f"{key}.json").read_text())
        titles = [[t["year"], t["champion"], t["season"]] for t in data["titles"]]
        assert all(t[0] and t[1] for t in titles), key
        for _, cid, _ in titles:
            c = data["clubs"][cid]
            clubs[f"{key}/{cid}"] = {"name": c["name"], "crest": c.get("crest")}
        name, flag = COUNTRIES[country]
        countries[country] = {"name": name, "flag": flag}
        leagues.append({
            "key": key, "label": label, "country": country, "competition": data["meta"]["competition"],
            "through": data["meta"].get("through"), "eras": data["meta"].get("eras") or [],
            "titles": [[y, f"{key}/{cid}", s] for y, cid, s in titles],
        })
    out = {"meta": {"generated": date.today().isoformat()}, "countries": countries, "clubs": clubs, "leagues": leagues}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"{OUT.relative_to(ROOT)}: {len(leagues)} leagues, {sum(len(l['titles']) for l in leagues)} titles, {len(clubs)} champions")


if __name__ == "__main__":
    main()
