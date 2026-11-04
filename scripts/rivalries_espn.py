"""Rivalries with no published head-to-head history: their meetings in AFA tournaments as ESPN records them, read from
one club's season schedules. ESPN's Argentine coverage starts in the late 2000s and leaves out the city leagues and the
third division (Torneo Federal A), so these pages carry a partial record, labeled as such.

Only the pair's own matches are cached (data/raw/espn/<id>.json, with the seasons already read); a refresh reads the
last two seasons again, and any season never read."""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

from rivalries_americas import knockout
from rivalries_common import RAW, W

SCHEDULE = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams/{team}/schedule?season={season}"
FIRST_SEASON = 2003
CLUBS = RAW.parent / "football" / "clubs.json"
ARGENTINA = timezone(timedelta(hours=-3))
FINISHED = {"STATUS_FULL_TIME", "STATUS_FINAL_AET", "STATUS_FINAL_PEN", "STATUS_FINAL"}


def espn_id(club: str) -> str:
    return next(c["espn"] for c in json.loads(CLUBS.read_text(encoding="utf-8"))["clubs"] if c["id"] == club)


def schedule(team: str, season: int) -> list[dict]:
    req = urllib.request.Request(SCHEDULE.format(team=team, season=season), headers={"User-Agent": W.USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    time.sleep(0.3)
    return body.get("events", [])


def classify(e: dict, comp: dict) -> tuple[str, str]:
    """(competition, stage) from ESPN's league slug: the Copa de la Liga is part of the Primera División."""
    slug = e.get("league", {}).get("slug", "")
    note = " ".join(n.get("headline", "") for n in comp.get("notes", []))
    if "friendly" in slug:
        return "Friendly", "friendly"
    if slug == "arg.copa":
        return "Copa Argentina", "cup"
    if slug == "arg.2":
        return "Segunda División", "league"
    if slug in ("arg.1", "arg.copa_lpf"):
        return "Primera División", "playoff" if knockout(note) else "league"
    if slug.startswith("conmebol"):
        return e["league"]["name"].replace("CONMEBOL ", "Copa "), "intl"
    return e.get("league", {}).get("name", slug), "cup"


def match(e: dict, ids: dict[str, str]) -> dict | None:
    comp = e["competitions"][0]
    if comp["status"]["type"]["name"] not in FINISHED:
        return None
    side = {x["homeAway"]: x for x in comp["competitors"]}
    home, away = ids.get(side["home"]["team"]["id"]), ids.get(side["away"]["team"]["id"])
    if not home or not away:
        return None
    name, stage = classify(e, comp)
    # ESPN gives kick-off in UTC: an evening match in Argentina falls on the next day there.
    when = datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(ARGENTINA).date().isoformat()
    m = {"date": when, "comp": name, "stage": stage, "home": home, "away": away,
         "hs": int(side["home"]["score"]["value"]), "as": int(side["away"]["score"]["value"])}
    rnd = knockout(" ".join(n.get("headline", "") for n in comp.get("notes", [])))
    if rnd:
        m["round"] = rnd
    pens = [side[k].get("shootoutScore") for k in ("home", "away")]
    if all(p is not None for p in pens):
        m["pens"] = [int(p) for p in pens]
    if comp["status"]["type"]["name"] == "STATUS_FINAL_AET":
        m["aet"] = True
    venue = comp.get("venue", {}).get("fullName")
    if venue:
        m["venue"] = venue
    return m


def espn_derby(rid: str, a: str, b: str, label: str):
    """A builder for the meetings of clubs `a` and `b` (clubs.json ids) that ESPN records, in `a`'s schedules."""
    def builder(refresh: bool) -> dict:
        cache = RAW / "espn" / f"{rid}.json"
        saved = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {"seasons": [], "matches": {}}
        ids = {espn_id(a): a, espn_id(b): b}
        this_year = date.today().year
        todo = [s for s in range(FIRST_SEASON, this_year + 1) if s not in saved["seasons"] or refresh and s >= this_year - 1]
        try:
            for s in todo:
                for e in schedule(espn_id(a), s):
                    m = match(e, ids)
                    if m:
                        saved["matches"][e["id"]] = m
                if s < this_year - 1 and s not in saved["seasons"]:
                    saved["seasons"].append(s)
        except OSError as err:
            if not cache.exists():
                raise
            print(f"warning: could not read ESPN's schedules for {rid} ({err}); using the saved copy", file=sys.stderr)
        else:
            cache.parent.mkdir(parents=True, exist_ok=True)
            saved["seasons"].sort()
            cache.write_text(json.dumps(saved, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        ms = sorted(saved["matches"].values(), key=lambda m: m["date"])
        # ESPN spells some grounds two ways ("Bautista Garganti", "Bautista Gargantini"): keep the longer.
        venues = {m["venue"] for m in ms if "venue" in m}
        for m in ms:
            if "venue" in m:
                m["venue"] = max((v for v in venues if v.startswith(m["venue"])), key=len)
        official = [dict(m) for m in ms if m["stage"] != "friendly"]
        friendlies = [dict(m) for m in ms if m["stage"] == "friendly"]
        first = official[0]["date"][:4]
        return {"matches": official, "friendlies": friendlies, "coverage": f"AFA matches since {first} recorded by ESPN",
                "source": {"label": f"ESPN, {label} schedules", "url": f"https://www.espn.com/soccer/team/fixtures/_/id/{espn_id(a)}"},
                "notes": [f"No published head-to-head history: this page counts only the AFA matches ESPN records, from {first} on. "
                          "It leaves out the city league, earlier seasons and the third division (Torneo Federal A), "
                          "so it is a partial record and doesn't say who leads the rivalry overall."]}
    return builder
