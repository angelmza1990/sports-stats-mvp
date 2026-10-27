"""English rivalries between the big six (English Wikipedia, engsoccerdata, LFChistory.net)."""

from __future__ import annotations

import html
import re
import sys
import time
import urllib.request

from rivalries_common import (ES_ROUNDS, ROOT, W, bold, en_team, find, football_season, footballboxes, goals_text, label_index,  # noqa: F401
                              page, parse_date, score_of, shootout)


LIVERPOOL, UNITED = "liverpool", "manchester-united"
EN_ROUNDS = [(r"semi-final", "Semi-finals"), (r"quarter-final", "Quarter-finals"), (r"\bfinal\b", "Final"),
             (r"round of 16", "Round of 16"), (r"(\d)(?:st|nd|rd|th) round", None), (r"test match", "Test match")]


def nwd_team(text: str) -> str | None:
    return en_team(text, ("liverpool",), ("manchester united", "newton heath"), LIVERPOOL, UNITED)


def nwd_comp(text: str) -> tuple[str, str, str, str]:
    """ "FA Cup 2nd round replay" -> ("FA Cup", "cup", "Second round", "replay")."""
    t = W.plain(text)
    lo = t.lower()
    leg = "replay" if "replay" in lo else ""
    if "charity shield" in lo or "community shield" in lo:
        return "FA Charity / Community Shield", "super", "Final", ""
    if lo.startswith("fa cup"):
        comp, stage = "FA Cup", "cup"
    elif "league cup" in lo:
        comp, stage = "League Cup", "cup"
    elif "europa league" in lo:
        comp, stage = "UEFA Europa League", "intl"
    elif "test match" in lo:
        comp, stage = "Football League test match", "league"
        return comp, stage, "", ""
    elif "premier league" in lo:
        return "Premier League", "league", "", ""
    elif "first division" in lo:
        return "First Division", "league", "", ""
    elif "second division" in lo:
        return "Second Division", "league", "", ""
    else:
        return t, "friendly", "", ""
    rnd = ""
    for pat, name in EN_ROUNDS:
        mm = re.search(pat, lo)
        if mm:
            rnd = name or f"{['', 'First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth'][int(mm.group(1))]} round"
            break
    return comp, stage, rnd, leg


def build_nwd(refresh: bool) -> dict:
    text = page("Liverpool F.C.–Manchester United F.C. rivalry", refresh)
    start, end = text.index("===All-time results==="), text.index("===Women's football results===")
    official, friendlies = [], []
    sections = re.split(r"\n(====[^=\n]+====)\s*\n", text[start:end])
    for heading, body in zip(sections[1::2], sections[2::2]):
        home_team = LIVERPOOL if "Liverpool in the league" in heading else UNITED if "Manchester United in the league" in heading else None
        friendly = "friendly" in heading.lower()
        for grid in W.all_tables("\n" + body):
            labels = [W.plain(c["text"]).lower() for c in grid[0]] if grid else []
            sub = [W.plain(c["text"]).lower() for c in grid[1]] if len(grid) > 1 else []
            if "date" not in labels:
                continue
            two_team = "team 1" in sub
            for r in grid[2 if two_team else 1:]:
                d = parse_date(r[0]["text"])
                if not d:
                    continue
                if two_team:
                    home, away, sc = nwd_team(r[2]["text"]), nwd_team(r[4]["text"]), score_of(r[3]["text"])
                    comp_cell = r[5]["text"]
                else:
                    home = home_team
                    away = UNITED if home_team == LIVERPOOL else LIVERPOOL
                    sc, comp_cell = score_of(r[2]["text"]), r[3]["text"]
                if not sc or not home or not away:
                    continue
                comp, stage, rnd, leg = nwd_comp(comp_cell)
                if re.search(r"war league|wartime|war cup", comp, re.I):
                    continue  # wartime matches are not official
                if friendly:
                    comp, stage, rnd, leg = (W.plain(comp_cell) or "Friendly"), "friendly", "", ""
                m = {"date": d, "comp": comp, "stage": stage, "round": rnd, "leg": leg, "home": home, "away": away,
                     "hs": sc[0], "as": sc[1], "venue": W.plain(r[1]["text"])}
                raw = " ".join(c["text"] for c in r)
                if re.search(r"a\.e\.t|aet|extra time", raw, re.I):
                    m["aet"] = True
                (friendlies if friendly else official).append(m)
    for m in official + friendlies:
        m["season"] = football_season(m["date"])
        grounds = {"Anfield", "Old Trafford", "Bank Street", "Clayton", "North Road"} | ({"Maine Road"} if m["date"] < "1950" else set())
        if m["venue"] not in grounds:
            m["neutral"] = True
    return {
        "id": "liverpool-united", "name": "North-West derby", "subtitle": "Liverpool vs Manchester United", "country": "ENG",
        "teams": [{"id": LIVERPOOL, "name": "Liverpool", "short": "Liverpool"}, {"id": UNITED, "name": "Manchester United", "short": "United"}],
        "matches": official, "friendlies": friendlies,
        "scorers": lfc_leaders(refresh, "Top scorers", "goals"),
        "appearances": lfc_leaders(refresh, "Top appearances", "apps"),
        "leadersByTeam": True,
        "source": {"label": "English Wikipedia, Liverpool F.C.–Manchester United F.C. rivalry",
                   "url": "https://en.wikipedia.org/wiki/Liverpool_F.C.%E2%80%93Manchester_United_F.C._rivalry"},
        "notes": [
            "Manchester United played as Newton Heath until 1902. Wartime matches are not counted.",
            "The sources publish only each club's top five scorers and appearance makers (LFChistory.net).",
            "Wikipedia lists only the friendlies played since 2014.",
        ],
    }


LFC_URL = "https://www.lfchistory.net/Opposition/Team/Profile/22"


def lfc_leaders(refresh: bool, title: str, key: str) -> list[dict]:
    """Each club's top five from LFChistory's head-to-head page ("Ryan Giggs 48 apps · 5 goals")."""
    cache = ROOT / "data" / "raw" / "lfchistory" / "opposition-22.html"
    if refresh or not cache.exists():
        try:
            req = urllib.request.Request(LFC_URL, headers={"User-Agent": W.USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", "replace")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(body, encoding="utf-8")
        except OSError as err:
            if not cache.exists():
                raise
            print(f"warning: LFChistory unavailable ({err}); using the saved copy", file=sys.stderr)
    t = cache.read_text(encoding="utf-8")
    t = html.unescape(re.sub(r"<[^>]+>", "\n", re.sub(r"<script.*?</script>", "", t, flags=re.S)))
    lines = [x.strip() for x in t.split("\n") if x.strip()]
    i = lines.index(title)
    out, team = [], None
    for j in range(i + 1, len(lines)):
        ln = lines[j]
        if ln in ("MANCHESTER UNITED", "LIVERPOOL"):
            if team and ln == "MANCHESTER UNITED" and any(o["team"] == UNITED for o in out):
                break
            team = UNITED if ln == "MANCHESTER UNITED" else LIVERPOOL
            continue
        mm = re.match(r"(\d+) apps · (\d+) goals?", ln)
        if mm and team:
            out.append({"name": lines[j - 1], "team": team, "apps": int(mm.group(1)), "goals": int(mm.group(2))})
        if ln in ("Top scorers", "Notes") and j > i + 1:
            break
    return sorted(out, key=lambda o: -o[key])
