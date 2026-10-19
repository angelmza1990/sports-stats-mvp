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
RAW_URL = "https://{lang}.wikipedia.org/w/index.php?title={title}&action=raw"


def fetch_raw(title: str, cache: Path, refresh: bool, pause: float = 3.0, lang: str = "en") -> str:
    """Raw wikitext of a page, cached on disk. Pauses between downloads to respect rate limits."""
    if refresh or not cache.exists():
        print(f"downloading Wikipedia ({lang}): {title}", file=sys.stderr)
        url = RAW_URL.format(lang=lang, title=urllib.parse.quote(title.replace(" ", "_")))
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
    table = None
    for _ in range(nth + 1):
        table = None
        start = wikitext.find("\n{|", pos)
        if start < 0:
            raise LookupError(f"no table after {anchor}")
        depth, i = 0, start + 1
        while i < len(wikitext):
            line_end = wikitext.find("\n", i)
            line_end = len(wikitext) if line_end < 0 else line_end
            line = wikitext[i:line_end].lstrip()
            if depth == 1 and re.match(r"^=+[^=].*=+\s*$", line):
                # A section heading can't sit inside a table: the source forgot its closing "|}".
                table = wikitext[start + 1:i]
                pos = i
                break
            if line.startswith("{|"):
                depth += 1
            elif line.startswith("|}"):
                depth -= 1
                if depth == 0:
                    table = wikitext[start + 1:line_end]
                    pos = line_end
                    break
            i = line_end + 1
        if table is None:
            raise LookupError(f"unterminated table after {anchor}")
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
    rows_raw = re.split(r"\n[ \t]*\|-[^\n]*", "\n" + body)
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


def header_labels(row: list[dict]) -> list[str]:
    """Header labels, reading abbreviation/tooltip templates ({{Abbr|Pts|Points}} -> "Pts")."""
    out = []
    for c in row:
        m = re.search(r"\{\{\s*(?:abreviatura|abreviaci[oó]n|abbr|tooltip)\s*\|([^|}]+)", c["text"], re.I)
        out.append((m.group(1) if m else plain(c["text"])).strip())
    return out


def links(text: str) -> list[tuple[str, str]]:
    """All [[target|text]] links as (target, text)."""
    out = []
    for m in re.finditer(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]", strip_refs(text)):
        target = m.group(1).strip()
        if target.lower().startswith(("file:", "image:", "category:")):
            continue
        out.append((target, (m.group(2) or target).strip()))
    return out


def person(text: str) -> str | None:
    """A person's name from a cell: {{sortname|First|Last}} or the first link."""
    m = re.search(r"\{\{\s*sortname\s*\|([^|}]*)\|([^|}]*)(?:\|([^|}]*))?[^}]*\}\}", text, re.I)
    if m:
        first, last, target = (m.group(1) or "").strip(), (m.group(2) or "").strip(), (m.group(3) or "").strip()
        return f"{first} {last}".strip() if not target or "=" in target else re.sub(r"\s*\([^)]*\)$", "", target)
    found = links(text)
    if found:
        target, label = found[0]
        return label if "(" in target or label == target else label
    return plain(text) or None


def plain(text: str) -> str:
    """Readable text: links -> their label, templates and markup removed."""
    text = strip_refs(text)
    text = re.sub(r"\{\{\s*sortname\s*\|([^|}]*)\|([^|}]*)[^}]*\}\}", r"\1 \2", text, flags=re.I)
    text = re.sub(r"\{\{\s*sort\s*\|[^|{}]*\|(.*?)\}\}", r"\1", text, flags=re.I)
    text = re.sub(r"\{\{(?:nowrap|nobr|small|center|maybe|nowrap begin|bold|big|F1|F1GP)\|([^{}]*)\}\}", r"\1", text, flags=re.I)
    text = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("'''", "").replace("''", "").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def number(text: str) -> int | None:
    # Accepts "1,234" and the Spanish-style "1.234" thousands separators.
    m = re.search(r"-?\d{1,3}(?:[.,]\d{3})+(?!\d)|-?\d+", plain(text).replace("−", "-"))
    return int(re.sub(r"[.,]", "", m.group(0))) if m else None


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
    "paraguay national": "PAR", "kingdom of yugoslavia": "YUG", "dutch east indies": "DEI", "zaire": "ZAI",
    "cuba": "CUB", "haiti": "HAI", "el salvador": "SLV", "north korea": "PRK", "kuwait": "KUW", "iraq": "IRQ",
    "indonesia": "IDN", "south africa": "RSA", "kingdom of italy": "ITA", "nazi germany": "GER", "fr yugoslavia": "FRY",
    "serbia and montenegro": "SCG", "trinidad and tobago": "TRI", "angola": "ANG", "new zealand": "NZL", "qatar": "QAT",
    "saudi arabia": "KSA", "iran": "IRN", "china": "CHN", "tunisia": "TUN", "united arab emirates": "UAE",
}


def flag_codes(text: str) -> list[str]:
    """Every country code from flag-like templates in a cell, in order (e.g. co-hosts)."""
    out = []
    for m in re.finditer(r"\{\{[^{}]*\}\}", text):
        code = flag_code(m.group(0))
        if code and code not in out:
            out.append(code)
    return out


def all_tables(wikitext: str) -> list[list[list[dict]]]:
    """Every top-level table on a page, parsed."""
    out, pos = [], 0
    while True:
        start = wikitext.find("\n{|", pos)
        if start < 0:
            return out
        try:
            table = find_table(wikitext[start:], r"^", 0)
        except LookupError:
            return out
        out.append(parse_table(table))
        pos = start + len(table)


def table_with_headers(wikitext: str, *needles: str) -> list[list[dict]]:
    """The first table whose header rows contain every needle (case-insensitive)."""
    for grid in all_tables(wikitext):
        head = " ".join(plain(c["text"]).lower() for row in grid[:2] for c in row)
        if all(n.lower() in head for n in needles):
            return grid
    raise LookupError(f"no table with headers {needles}")


def flag_code(text: str) -> str | None:
    """Country code from the first flag-like template in a cell ({{ARG}}, {{flagicon|Brazil}}, {{fba|ESP|1945}}...)."""
    for m in re.finditer(r"\{\{\s*([^{}|]+?)\s*(?:\|([^{}|]*))?(?:\|[^{}]*)?\}\}", text):
        name, arg = m.group(1).strip(), (m.group(2) or "").strip()
        lname = name.lower()
        # flag templates, plus the sport-specific ones ({{ru-big|…}}, {{bk-big|…}}, {{vb|…}}, {{fh-big|…}}, {{hb-big|…}}).
        if lname.startswith(("flag", "fb", "ru-", "bk", "vb", "fh", "ru", "hb")) and lname not in ("flagathlete",):
            if re.fullmatch(r"[A-Z]{3}", arg):
                return arg
            code = COUNTRY_NAMES.get(arg.lower())
            if code:
                return code
        elif re.fullmatch(r"[A-Z]{3}", name):
            return name
    return None
