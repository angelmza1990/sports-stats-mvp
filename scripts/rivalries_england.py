"""English rivalries between the big six (English Wikipedia, engsoccerdata, LFChistory.net)."""

from __future__ import annotations

import csv
import html
import io
import re
import sys
import time
import urllib.request

from rivalries_common import (ES_ROUNDS, RAW, ROOT, TODAY, W, Pair, bold, box_goals, en_round, en_team, find, fold,  # noqa: F401
                              football_season, footballboxes, goals_text, label_index, page, parse_date, score_of, shootout)


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
                   "url": "https://en.wikipedia.org/wiki/Liverpool_F.C.%E2%80%93Manchester_United_F.C._rivalry",
                   "extra": [{"what": "top scorers and appearances", "label": "LFChistory.net", "url": LFC_URL}]},
        "friendliesNote": "Wikipedia lists only the friendlies played since 2014.",
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


# ---------------------------------------------------------------- The rest of the big six

# engsoccerdata (github.com/jalapic/engsoccerdata) has every English league match through 2024–25 and the FA Cup,
# League Cup and European Cup through 2018–19; each club's season article on English Wikipedia covers the years
# since, and the Charity / Community Shields come from Wikipedia's list of them.

ARSENAL, CHELSEA, CITY, SPURS = "arsenal", "chelsea", "manchester-city", "tottenham-hotspur"
BIG_SIX = {
    ARSENAL: ("Arsenal", "Arsenal F.C.", ("arsenal",)),
    CHELSEA: ("Chelsea", "Chelsea F.C.", ("chelsea",)),
    LIVERPOOL: ("Liverpool", "Liverpool F.C.", ("liverpool",)),
    CITY: ("Manchester City", "Manchester City F.C.", ("manchester city", "man city", "ardwick")),
    UNITED: ("Manchester United", "Manchester United F.C.", ("manchester united", "man united", "man utd", "newton heath")),
    SPURS: ("Tottenham Hotspur", "Tottenham Hotspur F.C.", ("tottenham", "spurs")),
}
ESD = "https://raw.githubusercontent.com/jalapic/engsoccerdata/master/data-raw/{}.csv"
ESD_LEAGUE_LAST, ESD_CUPS_LAST, ESD_EUROPE_LAST = 2024, 2018, 2017  # last season (its starting year) in each file
SEASON_PAGES_FROM = 2018
CURRENT_SEASON = int(TODAY[:4]) if int(TODAY[5:7]) >= 7 else int(TODAY[:4]) - 1
FA_ROUNDS = {"1": "First round", "2": "Second round", "3": "Third round", "4": "Fourth round", "5": "Fifth round",
             "6": "Quarter-finals", "s": "Semi-finals", "f": "Final"}
EURO = "European Cup / Champions League"


def esd_rows(name: str, refresh: bool) -> list[dict]:
    """One engsoccerdata file, kept on disk as just the matches between two of the big six."""
    cache = RAW / "engsoccerdata" / f"big-six-{name}.csv"
    clubs = {v[0] for v in BIG_SIX.values()}
    if refresh or not cache.exists():
        try:
            req = urllib.request.Request(ESD.format(name), headers={"User-Agent": W.USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as resp:
                rows = list(csv.DictReader(io.StringIO(resp.read().decode("utf-8", "replace"))))
            keep = [r for r in rows if r.get("home") in clubs and r.get("visitor") in clubs]
            cache.parent.mkdir(parents=True, exist_ok=True)
            with cache.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(keep)
        except OSError as err:
            if not cache.exists():
                raise
            print(f"warning: engsoccerdata {name} unavailable ({err}); using the saved copy", file=sys.stderr)
    return list(csv.DictReader(cache.open(encoding="utf-8")))


def club_of(name: str) -> str | None:
    return next((cid for cid, v in BIG_SIX.items() if v[0] == name), None)


def season_label(start: int) -> str:
    return f"{start}–{str(start + 1)[2:]}"


ESD_SEASONS: set[int] = set()  # league seasons engsoccerdata has (2022–23 is missing from it)


def esd_matches(refresh: bool) -> list[dict]:
    out = []
    for r in esd_rows("england", refresh):
        ESD_SEASONS.add(int(r["Season"]))
        s = int(r["Season"])
        if s > ESD_LEAGUE_LAST:
            continue
        tier = int(r["tier"])
        comp = "Premier League" if tier == 1 and s >= 1992 else "First Division" if tier == 1 else "Second Division"
        out.append({"date": r["Date"], "comp": comp, "stage": "league", "season": season_label(s), "home": club_of(r["home"]),
                    "away": club_of(r["visitor"]), "hs": int(r["hgoal"]), "as": int(r["vgoal"])})
    for r in esd_rows("facup", refresh):
        s = int(r["Season"])
        if s > ESD_CUPS_LAST or r.get("nonmatch") not in ("NA", "", None):
            continue
        m = {"date": r["Date"], "comp": "FA Cup", "stage": "cup", "season": season_label(s), "round": FA_ROUNDS.get(r["round"], r["round"]),
             "leg": "replay" if r["tie"].startswith("replay") else "", "home": club_of(r["home"]), "away": club_of(r["visitor"]),
             "hs": int(r["hgoal"]), "as": int(r["vgoal"]), "venue": r["Venue"] if r["Venue"] != "NA" else "",
             "neutral": r.get("neutral") == "yes"}
        if r.get("aet") == "yes":
            m["aet"] = True
        if r.get("hp") not in ("NA", "") and r.get("vp") not in ("NA", ""):
            m["pens"] = [int(r["hp"]), int(r["vp"])]
        out.append(m)
    for r in esd_rows("leaguecup", refresh):
        s = int(r["Season"])
        if s > ESD_CUPS_LAST:
            continue
        rnd = r["round"].lower()
        rnd = "Semi-finals" if rnd.startswith("semi") else "Final" if rnd == "final" else FA_ROUNDS.get(rnd, rnd)
        leg = "replay" if r["tie"].startswith("replay") else {"1": "first leg", "2": "second leg"}.get(r["leg"], "") if rnd == "Semi-finals" else ""
        m = {"date": r["Date"], "comp": "League Cup", "stage": "cup", "season": season_label(s), "round": rnd, "leg": leg,
             "home": club_of(r["home"]), "away": club_of(r["visitor"]), "hs": int(r["hgoal"]), "as": int(r["vgoal"]),
             "neutral": rnd == "Final"}
        out.append(m)
    for r in esd_rows("champs", refresh):
        s = int(r["Season"])
        if s > ESD_EUROPE_LAST:
            continue
        rnd = {"QF": "Quarter-finals", "SF": "Semi-finals", "final": "Final", "R16": "Round of 16"}.get(r["round"], "Group stage" if r["round"].lower().startswith("group") else r["round"])
        hs, as_ = (int(r["tothgoal"]), int(r["totvgoal"])) if r["tothgoal"] not in ("NA", "") else (int(r["hgoal"]), int(r["vgoal"]))
        m = {"date": r["Date"], "comp": EURO, "stage": "intl", "season": season_label(s), "round": rnd,
             "leg": {"1": "first leg", "2": "second leg"}.get(r["leg"], ""), "home": club_of(r["home"]), "away": club_of(r["visitor"]),
             "hs": hs, "as": as_, "neutral": rnd == "Final"}
        if r["aet"] not in ("NA", ""):
            m["aet"] = True
        p = re.match(r"\s*(\d+)-(\d+)", r.get("pens", ""))
        if p:
            m["pens"] = [int(p.group(1)), int(p.group(2))]
        out.append(m)
    return out


def league_cup_fix(matches: list[dict], refresh: bool) -> None:
    """engsoccerdata's League Cup scores stop at 90 minutes. Since 1997, when replays ended, a level single match went to
    extra time: take the result from the edition's article (a note under the results row, or the final's own article)."""
    pair_of = lambda t: next((cid for cid, v in BIG_SIX.items() if any(n in fold(W.plain(t)) for n in v[2])), None)  # noqa: E731
    for m in matches:
        start = int(m["season"][:4])
        if m["comp"] != "League Cup" or m["hs"] != m["as"] or m.get("leg") or start < 1997:
            continue
        cup = "EFL Cup" if start >= 2016 else "Football League Cup"
        note = None
        if m["round"] == "Final":
            try:
                text = page(f"{start + 1} {cup} final", refresh)
                note = re.search(r"\|\s*details\s*=\s*([^\n]*)", text)
                note = W.plain(note.group(1).replace("<br>", " ")) if note else None
            except Exception as err:  # noqa: BLE001
                print(f"note: no article for the {start + 1} {cup} final ({err})", file=sys.stderr)
        else:
            text = page(f"{season_label(start)} {cup}", refresh)
            names = [BIG_SIX[m["home"]][0], BIG_SIX[m["away"]][0]]
            hit = re.search(r"[^\n]*" + re.escape(names[0]) + r"[^\n]*" + re.escape(names[1]) + r"[^\n]*\n\|-\s*\n!colspan=\"?\d\"?\|([^\n]+)", text)
            note = W.plain(hit.group(1)) if hit else None
        if not note:
            print(f"note: League Cup {m['date']} {m['home']}–{m['away']}: no extra-time note found", file=sys.stderr)
            continue
        win = pair_of(note)
        sc = re.search(r"(\d+)\s*[–-]\s*(\d+)\s*(?:after extra time|a\.e\.t)", note, re.I)
        pens = re.search(r"(\d+)\s*[–-]\s*(\d+)\s*on penalties", note, re.I)
        m["aet"] = True
        if sc and win:
            hi, lo = sorted((int(sc.group(1)), int(sc.group(2))), reverse=True)
            m["hs"], m["as"] = (hi, lo) if win == m["home"] else (lo, hi)
        if pens and win:
            hi, lo = sorted((int(pens.group(1)), int(pens.group(2))), reverse=True)
            m["pens"] = [hi, lo] if win == m["home"] else [lo, hi]


SEASON_COMPS = [(r"pre-season|friendl|tour|summer series", None, "friendly"), (r"community shield|charity shield", "FA Charity / Community Shield", "super"),
                (r"premier league", "Premier League", "league"), (r"fa cup", "FA Cup", "cup"),
                (r"efl cup|league cup|carabao", "League Cup", "cup"), (r"champions league", EURO, "intl"),
                (r"europa league", "UEFA Europa League", "intl"), (r"conference league", "UEFA Conference League", "intl"),
                (r"uefa super cup", "UEFA Super Cup", "super"), (r"club world cup", "FIFA Club World Cup", "intl")]


def season_page_matches(refresh: bool) -> list[dict]:
    """Every football box between two of the big six on each club's season articles since 2018–19."""
    pair_of = lambda t: next((cid for cid, v in BIG_SIX.items() if any(n in fold(W.plain(t)) for n in v[2])), None)  # noqa: E731
    out, seen = [], set()
    for start in range(SEASON_PAGES_FROM, CURRENT_SEASON + 1):
        for cid, (_, article, _) in BIG_SIX.items():
            title = f"{season_label(start)} {article} season"
            try:
                text = page(title, refresh)
            except Exception as err:  # noqa: BLE001 - a season article not written yet
                print(f"note: {title}: {err}", file=sys.stderr)
                continue
            heads = [(m.start(), W.plain(m.group(1))) for m in re.finditer(r"^=+\s*(.+?)\s*=+\s*$", text, re.M)]
            for box_m, box in zip(re.finditer(r"\{\{\s*(?:football ?box(?: collapsible)?|footballbox(?:_collapsible)?)\b", text, re.I), footballboxes(text)):
                home, away = pair_of(box["team1"]), pair_of(box["team2"])
                if not home or not away or home == away or not box["date"] or not box["score"]:
                    continue
                key = (box["date"], home, away)
                if key in seen:
                    continue
                # The nearest heading above the box that names a competition ("Premier League" above "Matches").
                comp, stage = next(((c, s) for pos, h in reversed(heads) if pos < box_m.start()
                                    for pat, c, s in SEASON_COMPS if re.search(pat, h, re.I)), (None, None))
                if stage is None:
                    comp, stage = next(((c, s) for pat, c, s in SEASON_COMPS if re.search(pat, box.get("round", ""), re.I)), (None, None))
                if stage is None:
                    continue
                league_era = stage == "league" and start <= ESD_LEAGUE_LAST and start in ESD_SEASONS
                if league_era or (stage in ("cup", "super") and comp != "FA Charity / Community Shield" and start <= ESD_CUPS_LAST) \
                        or (comp == EURO and start <= ESD_EUROPE_LAST) or comp == "FA Charity / Community Shield":
                    continue  # covered by engsoccerdata or the Shield list
                seen.add(key)
                rnd = "" if stage in ("league", "friendly") else en_round(box.get("round", "")) or ("Final" if stage == "super" else "")
                raw_round = W.plain(box.get("round", "")).lower()
                m = {"date": box["date"], "comp": comp or (W.plain(box.get("round", "")) or "Friendly"), "stage": stage,
                     "season": season_label(start), "round": rnd,
                     "leg": "first leg" if "first leg" in raw_round else "second leg" if "second leg" in raw_round else "",
                     "home": home, "away": away, "hs": box["score"][0], "as": box["score"][1],
                     "venue": W.plain(box.get("stadium", "")), "goalsHome": box_goals(box.get("goals1", "")),
                     "goalsAway": box_goals(box.get("goals2", ""))}
                if stage == "friendly":
                    m["comp"] = "Friendly"
                ps = score_of(box.get("penaltyscore", ""))
                if ps:
                    m["pens"] = list(ps)
                if re.search(r"a\.e\.t|aet|extra time", box.get("score", "") if isinstance(box.get("score"), str) else box["raw"][:400], re.I) \
                        or re.search(r"\|\s*aet\s*=\s*(?:yes|y)\b", box["raw"], re.I):
                    m["aet"] = True
                m["neutral"] = rnd == "Final" or (rnd == "Semi-finals" and comp == "FA Cup")
                out.append(m)
    return out


def shield_matches(refresh: bool) -> list[dict]:
    """Charity / Community Shields between two of the big six: the list gives the year, its own article the date."""
    text = page("List of FA Community Shield matches", refresh)
    grid = next(g for g in W.all_tables(text[text.index("==Results=="):]) if any(W.plain(c["text"]) == "Year" for c in g[0]))
    pair_of = lambda t: next((cid for cid, v in BIG_SIX.items() if any(n in fold(W.plain(t)) for n in v[2])), None)  # noqa: E731
    out = []
    for r in grid[1:]:
        if len(r) < 6:
            continue
        year, win, lose = W.plain(r[1]["text"]), pair_of(r[2]["text"]), pair_of(r[4]["text"])
        sc = score_of(r[3]["text"])
        if not win or not lose or win == lose or not sc or not year.isdigit():
            continue
        shared = "shared" in r[0]["attrs"].lower() or "#" in r[0]["attrs"] and "p" not in W.plain(r[0]["text"]) and sc[0] == sc[1]
        replay = "replay" in W.plain(r[3]["text"]).lower()
        d = None
        try:
            art = page(f"{year} FA {'Charity' if int(year) < 2002 else 'Community'} Shield", refresh)
            mm = re.search(r"\|\s*date\s*=\s*([^\n]*)", art)
            if mm:
                d = parse_date(re.sub(r"\{\{\s*(?:start date|dts)\s*\|(?:df=y\|)?\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})[^}]*\}\}",
                                      lambda x: f"{x.group(3)}/{x.group(2)}/{x.group(1)}", mm.group(1), flags=re.I))
        except Exception as err:  # noqa: BLE001
            print(f"note: no article for the {year} Shield ({err})", file=sys.stderr)
        m = {"date": d or f"{year}-08-10", "comp": "FA Charity / Community Shield", "stage": "super", "season": year, "round": "Final",
             "home": win, "away": lose, "hs": sc[0], "as": sc[1], "venue": W.plain(r[5]["text"]), "neutral": True}
        if not d:
            m["approxDate"] = True
        if replay:
            m["leg"] = "replay"
        pens = shootout(r[3]["text"])
        if pens:
            m["pens"] = list(pens)
            m["advanced"] = win
        elif sc[0] == sc[1] and not replay:
            m["shared"] = True
        out.append(m)
    return out


EXTRA_EUROPE = [("1970–71 European Cup Winners' Cup", "European Cup Winners' Cup"),
                ("2015–16 UEFA Europa League knockout phase", "UEFA Europa League")]


def extra_europe(refresh: bool) -> list[dict]:
    """The two meetings in other UEFA competitions before 2018–19 (Cup Winners' Cup 1971, Europa League 2016)."""
    pair_of = lambda t: next((cid for cid, v in BIG_SIX.items() if any(n in fold(W.plain(t)) for n in v[2])), None)  # noqa: E731
    out = []
    for title, comp in EXTRA_EUROPE:
        text = page(title, refresh)
        for box in footballboxes(text):
            home, away = pair_of(box["team1"]), pair_of(box["team2"])
            if home and away and home != away and box["date"] and box["score"]:
                rnd = en_round(box.get("round", "")) or ("Semi-finals" if "Winners' Cup" in comp else "Round of 16")
                out.append({"date": box["date"], "comp": comp, "stage": "intl", "season": football_season(box["date"]), "round": rnd,
                            "home": home, "away": away, "hs": box["score"][0], "as": box["score"][1],
                            "venue": W.plain(box.get("stadium", ""))})
    for m in out:  # both legs of each tie
        legs = sorted((x for x in out if {x["home"], x["away"]} == {m["home"], m["away"]} and x["comp"] == m["comp"]), key=lambda x: x["date"])
        if len(legs) == 2:
            m["leg"] = "first leg" if m is legs[0] else "second leg"
    return out


def en_leaders(text: str, heading: str, key: str, pair: Pair) -> list[dict]:
    """A leaders table with Player and Club columns and a Goals or Apps column."""
    m = re.search(r"^=+\s*" + heading + r"\s*=+\s*$", text, re.M)
    if not m:
        return []
    out = []
    for grid in W.all_tables(text[m.end():m.end() + 20000])[:1]:
        labels = label_index(grid[0])
        i_name = next((i for lab, i in labels.items() if lab.startswith(("player", "name"))), None)
        i_club = next((i for lab, i in labels.items() if lab.startswith(("club", "team"))), None)
        i_val = next((i for lab, i in labels.items() if lab.startswith(("goals", "apps", "appearances", "total"))), None)
        if None in (i_name, i_val):
            continue
        for r in grid[1:]:
            if len(r) <= max(i_name, i_val):
                continue
            name, val = W.person(r[i_name]["text"]), W.number(r[i_val]["text"])
            raw = r[i_club]["text"] if i_club is not None else ""
            short = {"united": UNITED, "city": CITY}.get(fold(W.plain(raw)).strip())
            teams = {t for t in (pair.a, pair.b) if any(n in fold(W.plain(raw)) for n in BIG_SIX[t][2]) or t == short}
            team = "both" if len(teams) == 2 else next(iter(teams), None)
            if name and val and team:
                out.append({"name": name, "team": team, key: val})
    return sorted(out, key=lambda o: -o[key])


def en_published(text: str, pair: Pair) -> dict | None:
    """The head-to-head totals table (Competition, Played, wins, draws, wins, goals): its Total row."""
    for grid in W.all_tables(text):
        head = [W.plain(c["text"]).lower() for c in grid[0]]
        if not head or not head[0].startswith("competition") or len(head) < 5:
            continue
        total = next((r for r in grid if re.match(r"^total", W.plain(r[0]["text"]), re.I)), None)
        if not total:
            continue
        nums = [int(x) for c in total[1:] for x in re.findall(r"\d+", W.plain(c["text"]))]
        if len(nums) < 4:
            continue
        first = next((t for t in (pair.team(grid[0][2]["text"]), ) if t), None)
        if first is None:
            short = {"city": CITY, "united": UNITED, "spurs": SPURS}.get(fold(W.plain(grid[0][2]["text"])).split(" ")[0])
            first = short or pair.a
        n, wa, d, wb = nums[:4]
        ga, gb = (nums[4], nums[5]) if len(nums) >= 6 else (None, None)
        if first == pair.b:
            wa, wb, ga, gb = wb, wa, gb, ga
        return {"n": n, "a": wa, "d": d, "b": wb, "ga": ga, "gb": gb}
    return None


ENG_PAGES = {"arsenal-tottenham": "North London derby", "city-united": "Manchester derby",
             "arsenal-united": "Arsenal F.C.–Manchester United F.C. rivalry", "chelsea-liverpool": "Chelsea F.C.–Liverpool F.C. rivalry",
             "arsenal-chelsea": "Arsenal F.C.–Chelsea F.C. rivalry", "liverpool-city": "Liverpool F.C.–Manchester City F.C. rivalry",
             "chelsea-tottenham": "Chelsea F.C.–Tottenham Hotspur F.C. rivalry"}
_ALL: dict[str, list[dict]] = {}


def big_six_matches(refresh: bool) -> list[dict]:
    if "all" not in _ALL:
        ms = esd_matches(refresh)
        league_cup_fix(ms, refresh)
        ms += season_page_matches(refresh) + shield_matches(refresh) + extra_europe(refresh)
        _ALL["all"] = ms
    return _ALL["all"]


def big_six(key: str, a: str, b: str):
    def builder(refresh: bool) -> dict:
        pair = Pair(a, BIG_SIX[a][2], b, BIG_SIX[b][2])
        ms = [dict(m) for m in big_six_matches(refresh) if {m["home"], m["away"]} == {a, b}]
        official = [m for m in ms if m["stage"] != "friendly"]
        friendlies = [m for m in ms if m["stage"] == "friendly"]
        for m in official:
            if m.pop("shared", False):
                m["decided"] = "Shield shared"
        data = {"matches": official, "friendlies": friendlies,
                "source": {"label": "engsoccerdata (league and cup results); English Wikipedia (club season articles since 2018–19, "
                                    "the Charity / Community Shield list)", "url": "https://github.com/jalapic/engsoccerdata"},
                "notes": ["League matches through 2024–25 and FA Cup, League Cup and European Cup matches through 2018–19 come from "
                          "engsoccerdata; later matches, with their scorers, from each club's season article on English Wikipedia.",
                          "Wartime matches are not counted. Friendlies are listed only since 2018–19."],
                "friendliesNote": "They are listed only since 2018–19, from the clubs' season articles."}
        title = ENG_PAGES.get(key)
        if title:
            text = page(title, refresh)
            pub = en_published(text, pair)
            if pub:
                data["published"] = pub
            data["scorers"] = en_leaders(text, r"=+\s*(?:Top goalscorers|Top scorers|Fixture top scorers)[^=\n]*=+", "goals", pair)
            data["appearances"] = en_leaders(text, r"=+\s*(?:Most appearances|Top appearance makers)[^=\n]*=+", "apps", pair)
            data["source"]["label"] += f"; top scorers and appearances from English Wikipedia, {title}"
        return data

    return builder
