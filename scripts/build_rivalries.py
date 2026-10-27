"""Build the datasets used by football/rivalries: every match of the great rivalries between the biggest clubs of
Argentina, Brazil, England, Spain, Italy, France and Germany.

Each country has its own source module (scripts/rivalries_<country>.py). The sources are Wikipedia (CC BY-SA 4.0)
in English, Spanish, Portuguese and Italian, RSSSF's head-to-head lists, engsoccerdata's English results and
LFChistory.net. Where no source lists every match, the rivalry keeps the head-to-head totals by competition that
Wikipedia publishes, and its latest matches.

Each rivalry is written to football/rivalries/data/<id>.json (official matches, friendlies, knockout ties, finals
and player leaders), and football/rivalries/data/index.json lists them all, grouped by country.

Usage:
    python3 scripts/build_rivalries.py                   # every rivalry, cached pages
    python3 scripts/build_rivalries.py river-boca        # some rivalries
    python3 scripts/build_rivalries.py --refresh         # re-download every page
"""

from __future__ import annotations

import argparse
import json
import sys

import rivalries_argentina as AR
import rivalries_england as EN
import rivalries_italy as IT
import rivalries_spain as ES
from rivalries_common import OUT_DIR, build_ties, finish, record, summary

# Each rivalry's two club colors for light and dark mode. Every pair was tuned and checked with the dataviz palette
# validator against the draw gray (#b8bcc1 light, #56595e dark): lightness band, CVD separation and normal-vision floor.
COLORS = {
    "river-boca": ("#d33a3c", "#245fd4", "#e54c4a", "#245fd4"),
    "river-independiente": ("#de4544", "#9e024a", "#b71824", "#e85082"),
    "river-racing": ("#d33a3c", "#0a96d6", "#e54c4a", "#0a96d6"),
    "river-san-lorenzo": ("#d33a3c", "#3845bf", "#e54c4a", "#4252cd"),
    "boca-independiente": ("#245fd4", "#d33a3c", "#245fd4", "#e54c4a"),
    "boca-racing": ("#215cd0", "#079de0", "#1e59cd", "#1499da"),
    "boca-san-lorenzo": ("#427ff7", "#3641bc", "#1e59cd", "#6a82fe"),
    "independiente-racing": ("#d33a3c", "#0a96d6", "#e54c4a", "#0a96d6"),
    "independiente-san-lorenzo": ("#d33a3c", "#3845bf", "#e54c4a", "#4252cd"),
    "racing-san-lorenzo": ("#0a96d6", "#3845bf", "#0a96d6", "#4252cd"),
    "madrid-barcelona": ("#824fcf", "#b21557", "#824fcf", "#e85082"),
    "inter-milan": ("#245fd4", "#d33a3c", "#245fd4", "#e54c4a"),
    "juventus-inter": ("#ce9707", "#245fd4", "#b68611", "#245fd4"),
    "juventus-milan": ("#ce9707", "#d33a3c", "#b68611", "#b71824"),
    "liverpool-united": ("#9e024a", "#de4544", "#e85082", "#b71824"),
    "arsenal-tottenham": ("#d9471b", "#3845bf", "#d9471b", "#4252cd"),
    "city-united": ("#0a96d6", "#d33a3c", "#0a96d6", "#e54c4a"),
    "arsenal-chelsea": ("#d9471b", "#245fd4", "#d9471b", "#245fd4"),
    "arsenal-liverpool": ("#d9471b", "#a3004c", "#b23308", "#e85082"),
    "arsenal-city": ("#d9471b", "#0a96d6", "#d9471b", "#0a96d6"),
    "arsenal-united": ("#e04e24", "#a20519", "#af2f02", "#ed5350"),
    "chelsea-liverpool": ("#245fd4", "#b21557", "#245fd4", "#e85082"),
    "chelsea-city": ("#215cd0", "#079de0", "#1e59cd", "#1499da"),
    "chelsea-united": ("#245fd4", "#d33a3c", "#245fd4", "#e54c4a"),
    "chelsea-tottenham": ("#427ff7", "#3641bc", "#1e59cd", "#6a82fe"),
    "liverpool-city": ("#b21557", "#0a96d6", "#e85082", "#0a96d6"),
    "liverpool-tottenham": ("#b21557", "#3845bf", "#e85082", "#4252cd"),
    "city-tottenham": ("#0a96d6", "#3845bf", "#0a96d6", "#4252cd"),
    "united-tottenham": ("#d33a3c", "#3845bf", "#e54c4a", "#4252cd"),
    "psg-marseille": ("#3845bf", "#0a96d6", "#4252cd", "#0a96d6"),
    "bayern-dortmund": ("#d33a3c", "#ce9707", "#b71824", "#b68611"),
    "palmeiras-corinthians": ("#067e3f", "#824fcf", "#098b47", "#824fcf"),
    "palmeiras-sao-paulo": ("#067e3f", "#fd736d", "#029d50", "#b71824"),
    "corinthians-sao-paulo": ("#824fcf", "#d33a3c", "#824fcf", "#e54c4a"),
    "santos-sao-paulo": ("#ce9707", "#d33a3c", "#b68611", "#b71824"),
    "corinthians-santos": ("#824fcf", "#ce9707", "#824fcf", "#b68611"),
    "palmeiras-santos": ("#067e3f", "#ce9707", "#05ab58", "#996f09"),
    "flamengo-fluminense": ("#fd736d", "#067e3f", "#b71824", "#029d50"),
    "flamengo-vasco": ("#d33a3c", "#824fcf", "#e54c4a", "#824fcf"),
    "botafogo-fluminense": ("#ce9707", "#067e3f", "#996f09", "#05ab58"),
    "botafogo-flamengo": ("#ce9707", "#d33a3c", "#b68611", "#b71824"),
    "fluminense-vasco": ("#067e3f", "#824fcf", "#098b47", "#824fcf"),
    "botafogo-vasco": ("#ce9707", "#824fcf", "#b68611", "#824fcf"),
    "internacional-gremio": ("#d33a3c", "#0a96d6", "#e54c4a", "#0a96d6"),
    "cruzeiro-atletico": ("#245fd4", "#ce9707", "#245fd4", "#b68611"),
}

GROUPS = [
    {"id": "arg", "country": "ARG", "name": "Argentina", "label": "The big five"},
    {"id": "esp", "country": "ESP", "name": "Spain", "label": ""},
    {"id": "ita", "country": "ITA", "name": "Italy", "label": "The big three"},
    {"id": "eng", "country": "ENG", "name": "England", "label": "The big six"},
]


def R(id, name, subtitle, group, a, b, build, min_matches, **extra):  # noqa: A002, N802
    return {"id": id, "name": name, "subtitle": subtitle, "group": group, "teams": [a, b], "build": build, "min": min_matches, **extra}


RIVER = {"id": "river-plate", "name": "River Plate", "short": "River"}
BOCA = {"id": "boca-juniors", "name": "Boca Juniors", "short": "Boca"}
MADRID = {"id": "real-madrid", "name": "Real Madrid", "short": "Madrid"}
BARCA = {"id": "barcelona", "name": "Barcelona", "short": "Barça"}
INTER = {"id": "inter-milan", "name": "Inter", "short": "Inter"}
MILAN = {"id": "milan", "name": "Milan", "short": "Milan"}
INDEPENDIENTE = {"id": "independiente", "name": "Independiente", "short": "Independiente"}
RACING = {"id": "racing", "name": "Racing Club", "short": "Racing"}
SAN_LORENZO = {"id": "san-lorenzo", "name": "San Lorenzo", "short": "San Lorenzo"}
LIVERPOOL = {"id": "liverpool", "name": "Liverpool", "short": "Liverpool"}
UNITED = {"id": "manchester-united", "name": "Manchester United", "short": "United"}

# The last number is the official matches through October 2026. A rebuild that finds fewer means a source
# changed shape: fail and keep the previous data rather than publish a shorter history.
RIVALRIES = [
    R("river-boca", "Superclásico", "River Plate vs Boca Juniors", "arg", RIVER, BOCA, AR.build_superclasico, 266,
      link_ties=AR.link_super_ties),
    R("river-independiente", "River vs Independiente", "River Plate vs Independiente", "arg", RIVER, INDEPENDIENTE,
      AR.big_five("river-independiente", "river-plate", "independiente"), 220, leaders=False),
    R("river-racing", "River vs Racing", "River Plate vs Racing Club", "arg", RIVER, RACING,
      AR.big_five("river-racing", "river-plate", "racing"), 230, leaders=False),
    R("river-san-lorenzo", "River vs San Lorenzo", "River Plate vs San Lorenzo", "arg", RIVER, SAN_LORENZO,
      AR.big_five("river-san-lorenzo", "river-plate", "san-lorenzo"), 220, leaders=False),
    R("boca-independiente", "Boca vs Independiente", "Boca Juniors vs Independiente", "arg", BOCA, INDEPENDIENTE,
      AR.big_five("boca-independiente", "boca-juniors", "independiente"), 205, leaders=False),
    R("boca-racing", "Boca vs Racing", "Boca Juniors vs Racing Club", "arg", BOCA, RACING,
      AR.big_five("boca-racing", "boca-juniors", "racing"), 220, leaders=False),
    R("boca-san-lorenzo", "Boca vs San Lorenzo", "Boca Juniors vs San Lorenzo", "arg", BOCA, SAN_LORENZO,
      AR.big_five("boca-san-lorenzo", "boca-juniors", "san-lorenzo"), 210, leaders=False),
    R("independiente-racing", "Clásico de Avellaneda", "Independiente vs Racing Club", "arg", INDEPENDIENTE, RACING,
      AR.big_five("independiente-racing", "independiente", "racing"), 235, leaders=False),
    R("independiente-san-lorenzo", "Independiente vs San Lorenzo", "Independiente vs San Lorenzo", "arg", INDEPENDIENTE, SAN_LORENZO,
      AR.big_five("independiente-san-lorenzo", "independiente", "san-lorenzo"), 200, leaders=False),
    R("racing-san-lorenzo", "Racing vs San Lorenzo", "Racing Club vs San Lorenzo", "arg", RACING, SAN_LORENZO,
      AR.big_five("racing-san-lorenzo", "racing", "san-lorenzo"), 210, leaders=False),
    R("madrid-barcelona", "El Clásico", "Real Madrid vs Barcelona", "esp", MADRID, BARCA, ES.build_clasico, 265),
    R("inter-milan", "Derby della Madonnina", "Inter vs Milan", "ita", INTER, MILAN, IT.build_derby, 246),
    R("liverpool-united", "North-West derby", "Liverpool vs Manchester United", "eng", LIVERPOOL, UNITED,
      EN.build_nwd, 218),
]


def validate(data: dict, cfg: dict) -> None:
    if data["mode"] == "summary":
        n = data["summary"]["total"]["n"]
        if n < cfg["min"]:
            raise SystemExit(f"{data['name']}: totals add up to {n} matches (expected at least {cfg['min']})")
        return
    n = len(data["matches"])
    if n < cfg["min"]:
        raise SystemExit(f"{data['name']}: only {n} official matches parsed (expected at least {cfg['min']})")
    ids = {t["id"] for t in data["teams"]}
    for m in data["matches"] + data["friendlies"]:
        if not m.get("date") or {m["home"], m["away"]} != ids:
            raise SystemExit(f"{data['name']}: bad match {m}")
    if cfg.get("leaders", True) and (not data.get("scorers") or not data.get("appearances")):
        raise SystemExit(f"{data['name']}: no scorer or appearance leaders parsed")


def build(cfg: dict, refresh: bool) -> dict:
    data = cfg["build"](refresh)
    data.update({k: cfg[k] for k in ("id", "name", "subtitle", "teams", "group")})
    data["country"] = next(g["country"] for g in GROUPS if g["id"] == cfg["group"])
    c = COLORS[cfg["id"]]
    data["colors"] = {"light": list(c[:2]), "dark": list(c[2:])}
    data.setdefault("mode", "full")
    for key in ("matches", "friendlies", "ties", "scorers", "appearances"):
        data.setdefault(key, [])
    source_ties = data.pop("_ties", None)
    data.pop("pair", None)
    published = data.pop("published", None)
    finish(data)
    if data["mode"] == "full":
        if source_ties is not None:
            data["ties"] = AR.link_ties(data, source_ties)
        elif cfg.get("link_ties"):
            cfg["link_ties"](data)
        else:
            data["ties"] = build_ties(data, cfg.get("ties"))
        if published:
            # The totals the source itself publishes: a gap is reported (and kept within a few matches by MIN).
            got = record(data)
            diff = {k: got[k] - published[k] for k in ("n", "a", "d", "b", "ga", "gb") if published.get(k) is not None and got[k] != published[k]}
            if diff:
                print(f"note: {data['name']} differs from the published totals by {diff}", file=sys.stderr)
                data["notes"].append(f"The source's own totals table counts {published['n']} official matches "
                                     f"({published['a']}–{published['d']}–{published['b']}); the match list adds up to {got['n']} "
                                     f"({got['a']}–{got['d']}–{got['b']}).")
    validate(data, cfg)
    return data


def index_entry(data: dict) -> dict:
    full = data["mode"] == "full"
    return {"id": data["id"], "name": data["name"], "subtitle": data["subtitle"], "group": data["group"],
            "teams": data["teams"], "colors": data["colors"], "mode": data["mode"],
            "record": record(data) if full else data["summary"]["total"],
            "first": data["matches"][0]["date"][:4] if full else data["summary"].get("since"),
            "dataThrough": data.get("dataThrough")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    unknown = set(args.ids) - {r["id"] for r in RIVALRIES}
    if unknown:
        raise SystemExit(f"unknown rivalries: {', '.join(sorted(unknown))}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    built = [build(cfg, args.refresh) for cfg in RIVALRIES if not args.ids or cfg["id"] in args.ids]
    # Written only once every rivalry has passed, so a failed rebuild leaves every file as it was.
    for data in built:
        (OUT_DIR / f"{data['id']}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        summary(data)
    files = [json.loads(p.read_text(encoding="utf-8")) for p in (OUT_DIR / f"{c['id']}.json" for c in RIVALRIES) if p.exists()]
    index = {
        "groups": [g for g in GROUPS if any(d["group"] == g["id"] for d in files)],
        "rivalries": [index_entry(d) for d in files],
        "clubs": {k: v for d in files for k, v in d["clubs"].items()},
        "countries": {k: v for d in files for k, v in d["countries"].items()},
    }
    (OUT_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"index: {len(index['rivalries'])} rivalries", file=sys.stderr)


if __name__ == "__main__":
    main()
