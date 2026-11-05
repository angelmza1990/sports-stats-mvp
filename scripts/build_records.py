"""Build athletics/world-records: how the world records of the classic events came down (or went up), mark by mark.

Reads each event's world record progression from Wikipedia (CC BY-SA 4.0). A page splits the progression into
tables (hand timing, then electronic timing; the years before and after the IAAF); each event names the tables it
uses and, where timing changed, the date each takes over. Within a table only marks that beat or equal the record
of the time are kept, so later rows that a page lists out of order or unratified don't break the line.

Usage:
    python3 scripts/build_records.py            # cached pages
    python3 scripts/build_records.py --refresh  # re-download them
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime

import wikitables as W
from build_champions import country, nation, page
from build_football import ROOT

OUT = ROOT / "athletics" / "world-records" / "data" / "records.json"

# key, label, sex, page, [(table, from, until)], "time" (lower is better) or "mark" (higher), the record today, a note.
EVENTS = [
    ("100m-men", "100 m", "men", "Men's 100 metres world record progression", [(2, None, "1977-01-01"), (3, "1977-01-01", None)], "time", 9.58,
     "Hand-timed records until 1976, electronic since 1977, when the first electronic record (9.95) stood slower than the last hand-timed 9.9."),
    ("100m-women", "100 m", "women", "Women's 100 metres world record progression", [(1, None, "1977-01-01"), (2, "1977-01-01", None)], "time", 10.49,
     "Hand-timed records until 1976, electronic since 1977."),
    ("mile-men", "Mile", "men", "Mile run world record progression", [(4, None, None)], "time", 222.66, "Records ratified by the IAAF and World Athletics since 1913."),
    ("marathon-men", "Marathon", "men", "Marathon world record progression", [(0, None, None)], "time", 7170, "World bests until 2003; World Athletics ratifies marathon world records since 2004."),
    ("marathon-women", "Marathon", "women", "Marathon world record progression", [(1, None, None)], "time", 7796, "World bests until 2003; World Athletics ratifies marathon world records since 2004."),
    ("long-jump-men", "Long jump", "men", "Men's long jump world record progression", [(1, None, None), (2, None, None)], "mark", 8.95, "Records ratified by the IAAF and World Athletics since 1901."),
    ("long-jump-women", "Long jump", "women", "Women's long jump world record progression", [(1, None, None)], "mark", 7.52, "Records ratified by the IAAF and World Athletics since 1922."),
    ("high-jump-men", "High jump", "men", "Men's high jump world record progression", [(2, None, None)], "mark", 2.45, "Records ratified by the IAAF and World Athletics since 1912."),
    ("high-jump-women", "High jump", "women", "Women's high jump world record progression", [(1, None, None)], "mark", 2.10, "Records ratified by the IAAF and World Athletics since 1922."),
    ("pole-vault-men", "Pole vault", "men", "Men's pole vault world record progression", [(1, None, None)], "mark", 6.31,
     "Marks since 1849, before and after the IAAF; indoor marks count as world records since 2000."),
]


def mark_of(text: str, kind: str) -> float | None:
    text = re.sub(r"\{\{\s*AthAbbr[^}]*\}\}|<ref.*?(?:</ref>|/>)|'''|\{\{\s*pad[^}]*\}\}", "", text, flags=re.S)
    m = re.search(r"T&Fcalc\s*\|\s*([\d.]+)", text)
    if m:
        return float(m.group(1))
    if re.search(r"T&Fcalc2", text):
        return None  # feet and inches
    m = re.search(r"(?:(\d+):)?(?:(\d+):)?(\d+(?:\.\d+)?)", W.plain(text))
    if not m:
        return None
    parts = [float(p) for p in m.groups() if p is not None]
    value = 0.0
    for p in parts:
        value = value * 60 + p
    return value if kind == "time" or "." in m.group(0) else None


def date_of(text: str) -> str | None:
    m = re.search(r"dts\s*\|\s*(\d{4})-(\d{2})-(\d{2})", text) or re.search(r"dts\s*\|(?:[^|}]*=[^|}]*\|)*\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    plain = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", W.plain(re.sub(r"<ref.*?(?:</ref>|/>)", "", text, flags=re.S))).strip()
    for fmt in ("%d %B %Y", "%B %d, %Y", "%d %b %Y", "%b %d, %Y", "%B %d %Y"):
        try:
            return datetime.strptime(re.search(r"[\w ,]+\d{4}", plain).group(0).strip(), fmt).date().isoformat()
        except (ValueError, AttributeError):
            continue
    m = re.search(r"\b(1[89]\d\d|20\d\d)\b", plain)
    return f"{m.group(1)}-07-01" if m and re.fullmatch(r"\s*\d{4}\s*", plain) else None


def athlete_of(text: str) -> str | None:
    m = re.search(r"\{\{\s*(?:flagathlete|flai)\s*\|\s*(\[\[[^\]]+\]\]|[^|}]+)", text)
    if m:
        text = m.group(1)
    name = W.person(re.sub(r"<ref.*?(?:</ref>|/>)", "", text, flags=re.S))
    return re.sub(r"\s*\([^)]*\)$", "", name).strip() if name else None


def build(refresh: bool) -> tuple[dict, list[str]]:
    events, nations, errors = [], set(), []
    for key, label, sex, title, segments, kind, today, note in EVENTS:
        grids = W.all_tables(page(title, refresh))
        better = (lambda a, b: a <= b) if kind == "time" else (lambda a, b: a >= b)
        marks = []
        for index, start, until in segments:
            grid = grids[index]
            labels = [W.plain(c["text"]).lower() for c in grid[0]]
            col = lambda *needles: next((i for i, l in enumerate(labels) for n in needles if l.startswith(n)), None)
            mark_i, who_i, nat_i, date_i = col("time", "mark"), col("athlete", "name"), col("nationality", "nation"), col("date")
            best = None
            for row in grid[1:]:
                if len(row) <= max(mark_i, who_i, date_i) or row[mark_i] is row[who_i]:
                    continue
                value, day, who = mark_of(row[mark_i]["text"], kind), date_of(row[date_i]["text"]), athlete_of(row[who_i]["text"])
                if value is None or not day or not who:
                    continue
                if (start and day < start) or (until and day >= until):
                    continue
                if best is not None and not better(value, best):
                    continue
                best = value
                code = nation(row[nat_i]["text"]) if nat_i is not None else None
                shown = re.sub(r"\s+", " ", W.plain(re.sub(r"\{\{\s*AthAbbr[^}]*\}\}|<ref.*?(?:</ref>|/>)", "", row[mark_i]["text"], flags=re.S))).strip(" '")
                marks.append({"date": day, "value": round(value, 3), "athlete": who, "nation": code or nation(row[who_i]["text"]),
                              "text": shown if kind == "time" else (f"{value:.2f}" if abs(value * 100 - round(value * 100)) < 1e-6 else f"{value:.3f}") + " m"})
        marks.sort(key=lambda m: m["date"])
        if not marks or abs(marks[-1]["value"] - today) > 0.005:
            errors.append(f"{key}: the record today is {marks[-1]['value'] if marks else None}, expected {today}")
        missing = sorted({m["athlete"] for m in marks if not m["nation"]})
        if missing:
            print(f"{key}: no nation for {missing}", file=sys.stderr)
        nations |= {m["nation"] for m in marks if m["nation"]}
        events.append({"key": key, "label": label, "sex": sex, "kind": kind, "note": note,
                       "source": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}", "marks": marks})
    data = {"meta": {"generated": date.today().isoformat()},
            "countries": {c: {"name": country(c)[0], "flag": country(c)[1]} for c in sorted(nations)}, "events": events}
    return data, errors


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true")
    data, errors = build(ap.parse_args().refresh)
    if errors:
        print("validation failed:\n  " + "\n  ".join(errors), file=sys.stderr)
        sys.exit(1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(data['events'])} events, {sum(len(e['marks']) for e in data['events'])} records")


if __name__ == "__main__":
    main()
