"""Minimal Wikipedia wikitext helpers: fetch raw pages and parse wikitables."""

from __future__ import annotations

import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "sports-stats-mvp/1.0 (https://github.com/angelmza1990/sports-stats-mvp)"
RAW_URL = "https://en.wikipedia.org/w/index.php?title={title}&action=raw"


def fetch_raw(title: str, cache: Path, refresh: bool, pause: float = 3.0) -> str:
    """Raw wikitext of a page, cached on disk. Pauses between downloads to respect rate limits."""
    if refresh or not cache.exists():
        print(f"downloading Wikipedia: {title}", file=sys.stderr)
        url = RAW_URL.format(title=urllib.parse.quote(title.replace(" ", "_")))
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    text = resp.read().decode("utf-8")
                break
            except urllib.error.HTTPError as err:
                if err.code != 429 or attempt == 3:
                    raise
                time.sleep(15 * (attempt + 1))
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text, encoding="utf-8")
        time.sleep(pause)
    return cache.read_text(encoding="utf-8")


def split_outside(text: str, sep: str) -> list[str]:
    """Split on sep, ignoring separators inside [[...]] and {{...}}."""
    parts, depth, buf, i = [], 0, [], 0
    while i < len(text):
        two = text[i:i + 2]
        if two in ("[[", "{{"):
            depth += 1
            buf.append(two)
            i += 2
            continue
        if two in ("]]", "}}"):
            depth = max(0, depth - 1)
            buf.append(two)
            i += 2
            continue
        if depth == 0 and text.startswith(sep, i):
            parts.append("".join(buf))
            buf = []
            i += len(sep)
            continue
        buf.append(text[i])
        i += 1
    parts.append("".join(buf))
    return parts


def find_table(wikitext: str, anchor: str, nth: int = 0) -> str:
    """Text of the nth top-level wikitable after the first match of the anchor regex."""
    m = re.search(anchor, wikitext)
    if not m:
        raise LookupError(f"anchor not found: {anchor}")
    pos = m.end()
    for _ in range(nth + 1):
        start = wikitext.find("\n{|", pos)
        if start < 0:
            raise LookupError(f"no table after {anchor}")
        depth, i = 0, start + 1
        while i < len(wikitext):
            line_end = wikitext.find("\n", i)
            line_end = len(wikitext) if line_end < 0 else line_end
            line = wikitext[i:line_end].lstrip()
            if line.startswith("{|"):
                depth += 1
            elif line.startswith("|}"):
                depth -= 1
                if depth == 0:
                    table = wikitext[start + 1:line_end]
                    pos = line_end
                    break
            i = line_end + 1
    return table


ATTR_RE = re.compile(r"^\s*(?:(?:style|rowspan|colspan|align|scope|bgcolor|class|width|data-sort-value|valign|nowrap)\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s|]+)\s*)+$", re.I)


def _cell(raw: str) -> tuple[dict, str]:
    pieces = split_outside(raw, "|")
    attrs = ""
    if len(pieces) > 1 and ATTR_RE.match(pieces[0]):
        attrs, content = pieces[0], "|".join(pieces[1:])
    else:
        content = raw
    def num(name: str) -> int:
        m = re.search(name + r'\s*=\s*"?(\d+)', attrs, re.I)
        return int(m.group(1)) if m else 1
    return {"rowspan": num("rowspan"), "colspan": num("colspan"), "attrs": attrs}, content.strip()


def parse_table(table: str) -> list[list[dict]]:
    """Rows of cells ({text, attrs, header}) with rowspans and colspans expanded."""
    body = table.split("\n", 1)[1] if "\n" in table else ""
    # Drop nested tables entirely.
    rows_raw = re.split(r"\n\|-[^\n]*", "\n" + body)
    grid: list[list[dict]] = []
    pending: dict[int, tuple[int, dict]] = {}
    for raw in rows_raw:
        cells = []
        for line in raw.split("\n"):
            s = line.strip()
            if not s or s.startswith("|+") or s.startswith("|}") or s.startswith("{|"):
                continue
            if s[0] in "!|":
                sep = "!!" if s[0] == "!" else "||"
                for part in split_outside(s[1:], sep):
                    if s[0] == "!":
                        part = part
                    cells.append((s[0] == "!", part))
            elif cells:
                head, prev = cells[-1]
                cells[-1] = (head, prev + "\n" + line)
        if not cells:
            continue
        row, col = [], 0
        queue = list(cells)
        while queue or col in pending:
            if col in pending:
                left, cell = pending[col]
                row.append(cell)
                if left > 1:
                    pending[col] = (left - 1, cell)
                else:
                    del pending[col]
                col += 1
                continue
            header, raw_cell = queue.pop(0)
            meta, text = _cell(raw_cell)
            cell = {"text": text, "attrs": meta["attrs"], "header": header}
            for _ in range(meta["colspan"]):
                row.append(cell)
                if meta["rowspan"] > 1:
                    pending[col] = (meta["rowspan"] - 1, cell)
                col += 1
        grid.append(row)
    return grid


def strip_refs(text: str) -> str:
    text = re.sub(r"<ref[^>]*/>", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    return re.sub(r"\{\{(?:efn|refn|sfn|notetag|#tag:ref)[^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*\}\}", "", text, flags=re.I)


def links(text: str) -> list[tuple[str, str]]:
    """All [[target|text]] links as (target, text)."""
    out = []
    for m in re.finditer(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]", strip_refs(text)):
        target = m.group(1).strip()
        if target.lower().startswith(("file:", "image:", "category:")):
            continue
        out.append((target, (m.group(2) or target).strip()))
    return out


def plain(text: str) -> str:
    """Readable text: links -> their label, templates and markup removed."""
    text = strip_refs(text)
    text = re.sub(r"\{\{(?:nowrap|nobr|small|center)\|([^{}]*)\}\}", r"\1", text, flags=re.I)
    text = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("'''", "").replace("''", "").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def number(text: str) -> int | None:
    m = re.search(r"-?\d[\d,]*", plain(text))
    return int(m.group(0).replace(",", "")) if m else None


COUNTRY_NAMES = {
    "argentina": "ARG", "brazil": "BRA", "uruguay": "URU", "paraguay": "PAR", "chile": "CHI", "colombia": "COL",
    "ecuador": "ECU", "peru": "PER", "bolivia": "BOL", "venezuela": "VEN", "mexico": "MEX", "spain": "ESP",
    "italy": "ITA", "england": "ENG", "germany": "GER", "west germany": "FRG", "netherlands": "NED", "portugal": "POR",
    "france": "FRA", "scotland": "SCO", "romania": "ROU", "yugoslavia": "YUG", "serbia": "SRB", "belgium": "BEL",
    "greece": "GRE", "sweden": "SWE", "wales": "WAL", "ireland": "IRL", "republic of ireland": "IRL",
    "northern ireland": "NIR", "croatia": "CRO", "poland": "POL", "denmark": "DEN", "norway": "NOR",
    "switzerland": "SUI", "austria": "AUT", "czech republic": "CZE", "czechoslovakia": "TCH", "ukraine": "UKR",
    "russia": "RUS", "soviet union": "URS", "turkey": "TUR", "hungary": "HUN", "bulgaria": "BUL", "ghana": "GHA",
    "cameroon": "CMR", "ivory coast": "CIV", "egypt": "EGY", "senegal": "SEN", "nigeria": "NGA", "united states": "USA",
    "slovenia": "SVN", "slovakia": "SVK", "bosnia and herzegovina": "BIH", "georgia": "GEO", "finland": "FIN",
    "iceland": "ISL", "israel": "ISR", "algeria": "ALG", "morocco": "MAR", "gabon": "GAB", "guinea": "GUI",
    "mali": "MLI", "togo": "TOG", "costa rica": "CRC", "honduras": "HON", "panama": "PAN", "jamaica": "JAM",
    "japan": "JPN", "south korea": "KOR", "australia": "AUS", "canada": "CAN", "kosovo": "KOS", "albania": "ALB",
    "montenegro": "MNE", "north macedonia": "MKD", "armenia": "ARM", "belarus": "BLR", "kazakhstan": "KAZ",
    "cyprus": "CYP", "luxembourg": "LUX", "malta": "MLT", "latvia": "LVA", "lithuania": "LTU", "estonia": "EST",
    "moldova": "MDA", "azerbaijan": "AZE", "east germany": "GDR", "czechia": "CZE", "dr congo": "COD",
    "paraguay national": "PAR",
}


def flag_code(text: str) -> str | None:
    """Country code from the first flag-like template in a cell ({{ARG}}, {{flagicon|Brazil}}, {{fba|ESP|1945}}...)."""
    for m in re.finditer(r"\{\{\s*([^{}|]+?)\s*(?:\|([^{}|]*))?(?:\|[^{}]*)?\}\}", text):
        name, arg = m.group(1).strip(), (m.group(2) or "").strip()
        lname = name.lower()
        if lname in ("flagicon", "fbaicon", "fba", "flagcountry", "flag", "fb", "flagathlete", "flagu", "fbicon"):
            if re.fullmatch(r"[A-Z]{3}", arg):
                return arg
            code = COUNTRY_NAMES.get(arg.lower())
            if code:
                return code
        elif re.fullmatch(r"[A-Z]{3}", name):
            return name
    return None
