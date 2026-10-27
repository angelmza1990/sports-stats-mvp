"""Der Klassiker: Bayern Munich vs Borussia Dortmund (English Wikipedia, "Der Klassiker")."""

from __future__ import annotations

import re

from rivalries_common import W, Pair, en_round, page, parse_date, score_of, shootout

BAYERN, DORTMUND = "bayern-munich", "borussia-dortmund"
SECTIONS = [("Bundesliga", "Bundesliga", "league"), ("DFB-Pokal", "DFB-Pokal", "cup"), ("DFB-Ligapokal", "DFB-Ligapokal", "cup"),
            ("DFB/DFL/Franz Beckenbauer Supercup", "German Super Cup", "super"), ("UEFA Champions League", "UEFA Champions League", "intl")]


def build_klassiker(refresh: bool) -> dict:
    text = page("Der Klassiker", refresh)
    pair = Pair(BAYERN, ("bayern", "bayerm"), DORTMUND, ("dortmund", "borussia"))
    matches = []
    for heading, comp, stage in SECTIONS:
        m = re.search(r"^===\s*" + re.escape(heading) + r"\s*===\s*$", text, re.M)
        if not m:
            raise SystemExit(f"Der Klassiker: no {heading} section")
        grid = W.parse_table(W.find_table(text[m.start():], re.escape(heading)))
        for r in grid[1:]:
            cells = [c for c in r if W.plain(c["text"]) or "'''" in c["text"]]
            if len(r) < 5:
                continue
            season_cell, date_cell, home_cell, away_cell, res_cell = r[0], r[1], r[-3], r[-2], r[-1]
            d, sc = parse_date(date_cell["text"]), score_of(res_cell["text"])
            home, away = pair.team(home_cell["text"]), pair.team(away_cell["text"])
            if not d or not sc or not home or not away or home == away:
                continue  # fixtures not yet played
            anchor = re.search(r"#([^|\]]+)", season_cell["text"])
            rnd = "" if stage == "league" else (en_round(anchor.group(1)) if anchor else ("Final" if stage == "super" else ""))
            mm = {"date": d, "comp": comp, "stage": stage, "season": W.plain(season_cell["text"]), "round": rnd,
                  "home": home, "away": away, "hs": sc[0], "as": sc[1]}
            pens = shootout(res_cell["text"])
            if pens:
                mm["pens"] = list(pens)
            if re.search(r"a\.e\.t|aet|extra time", res_cell["text"], re.I):
                mm["aet"] = True
            if (stage == "cup" and rnd == "Final") or (stage == "intl" and rnd == "Final"):
                mm["neutral"] = True  # the DFB-Pokal final in Berlin, the 2013 Champions League final at Wembley
            matches.append(mm)
    return {
        "matches": matches,
        "source": {"label": "English Wikipedia, Der Klassiker", "url": "https://en.wikipedia.org/wiki/Der_Klassiker"},
        "notes": ["The list starts with the Bundesliga's first season (1965–66); earlier regional league meetings are not included.",
                  "Friendlies are not listed match by match in the source, so this rivalry has no friendlies tab."],
    }
