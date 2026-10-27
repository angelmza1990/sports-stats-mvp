"""Le Classique: Paris Saint-Germain vs Marseille (English Wikipedia, "Le Classique")."""

from __future__ import annotations

import re

from rivalries_common import W, Pair, box_goals, en_round, footballboxes, page, score_of

PSG, OM = "paris-saint-germain", "marseille"
SECTIONS = [("Ligue 1", "Ligue 1", "league"), ("Coupe de France", "Coupe de France", "cup"),
            ("Coupe de la Ligue", "Coupe de la Ligue", "cup"), ("Trophée des Champions", "Trophée des Champions", "super")]


def leaders(text: str, heading: str, key: str, pair: Pair) -> list[dict]:
    out = []
    for r in W.parse_table(W.find_table(text, heading))[1:]:
        if len(r) < 6:
            continue
        name, team, val = W.person(r[1]["text"]), pair.team(r[3]["text"]), W.number(r[-1]["text"])
        if name and team and val:
            out.append({"name": name, "team": team, key: val})
    return sorted(out, key=lambda o: -o[key])


def build_classique(refresh: bool) -> dict:
    text = page("Le Classique", refresh)
    pair = Pair(PSG, ("paris saint-germain", "psg", "paris"), OM, ("marseille", "om"))
    start = text.index("==Matches==")
    end = text.index("==Records==", start) if "==Records==" in text[start:] else len(text)
    body = text[start:end]
    matches = []
    for heading, comp, stage in SECTIONS:
        m = re.search(r"^===\s*" + re.escape(heading) + r"\s*===\s*$", body, re.M)
        nxt = re.search(r"^===[^=]", body[m.end():], re.M)
        part = body[m.end():m.end() + nxt.start()] if nxt else body[m.end():]
        for box in footballboxes(part):
            home, away = pair.team(box["team1"]), pair.team(box["team2"])
            if not box["date"] or not box["score"] or not home or not away or home == away:
                continue
            rnd = "" if stage == "league" else en_round(box.get("round", "")) or ("Final" if stage == "super" else "")
            mm = {"date": box["date"], "comp": comp, "stage": stage, "round": rnd, "home": home, "away": away,
                  "hs": box["score"][0], "as": box["score"][1], "venue": W.plain(box.get("stadium", "")),
                  "goalsHome": box_goals(box.get("goals1", "")), "goalsAway": box_goals(box.get("goals2", ""))}
            ps = score_of(box.get("penaltyscore", ""))
            if ps:
                mm["pens"] = list(ps)
            if re.search(r"a\.e\.t|aet|extra time", box["raw"].split("|score")[1][:80] if "|score" in box["raw"] else "", re.I):
                mm["aet"] = True
            grounds = ("parc des princes", "velodrome", "colombes", "yves-du-manoir")
            v = mm["venue"].lower()
            mm["neutral"] = bool(v) and not any(g in v for g in grounds)
            matches.append(mm)
    for m in matches:
        y, mo = int(m["date"][:4]), int(m["date"][5:7])
        start_y = y if mo >= 7 else y - 1
        m["season"] = f"{start_y}–{str(start_y + 1)[2:]}"
    return {
        "matches": matches,
        "scorers": leaders(text, r"===Top goalscorers===", "goals", pair),
        "appearances": leaders(text, r"===Most appearances===", "apps", pair),
        "source": {"label": "English Wikipedia, Le Classique", "url": "https://en.wikipedia.org/wiki/Le_Classique"},
        "notes": ["Friendlies are not listed match by match in the source, so this rivalry has no friendlies tab."],
    }
