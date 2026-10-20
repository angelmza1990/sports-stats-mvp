"""Keep a local copy of every flag the site shows, so pages don't depend on a flag CDN.

Scans every dataset for flag codes ("flag": "ar", "gb-eng"...) and downloads
the SVGs that assets/flags/ doesn't have yet from flagcdn.com (Flagpedia,
public domain). Run it after the data builds.

Usage:
    python3 scripts/fetch_flags.py
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLAGS = ROOT / "assets" / "flags"
SOURCE = "https://flagcdn.com/{code}.svg"
USER_AGENT = "sports-stats-mvp/1.0 (https://github.com/angelmza1990/sports-stats-mvp)"


def codes_in(value) -> set[str]:
    out = set()
    if isinstance(value, dict):
        for k, v in value.items():
            if k == "flag" and isinstance(v, str) and re.fullmatch(r"[a-z]{2}(-[a-z]{3})?", v):
                out.add(v)
            else:
                out |= codes_in(v)
    elif isinstance(value, list):
        for v in value:
            out |= codes_in(v)
    return out


def main() -> None:
    codes = set()
    for path in ROOT.glob("*/*/data/*.json"):
        codes |= codes_in(json.loads(path.read_text(encoding="utf-8")))
    FLAGS.mkdir(parents=True, exist_ok=True)
    missing = sorted(c for c in codes if not (FLAGS / f"{c}.svg").exists())

    def fetch(code: str) -> str | None:
        req = urllib.request.Request(SOURCE.format(code=code), headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                (FLAGS / f"{code}.svg").write_bytes(resp.read())
        except (urllib.error.URLError, TimeoutError) as err:
            return f"{code} ({err})"
        return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        failed = [f for f in pool.map(fetch, missing) if f]
    print(f"{len(codes)} flags in use, {len(missing) - len(failed)} downloaded")
    if failed:
        # Pages fall back to a lettered badge, so a missing flag is not fatal.
        print(f"could not download: {', '.join(failed)}", file=sys.stderr)


if __name__ == "__main__":
    main()
