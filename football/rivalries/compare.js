/* Great Rivalries: every rivalry side by side, from the totals and records in data/index.json. */
(async function () {
  "use strict";

  const { el } = Viz;
  const index = await d3.json("data/index.json", { cache: "no-cache" });
  const F = Football(index);
  const countryOf = new Map(index.groups.map((g) => [g.id, g.country]));
  const team = (r, s) => r.teams[s === "a" ? 0 : 1];
  const short = (r, s) => team(r, s).short ?? team(r, s).name;
  const pct = (x) => `${Math.round(x * 100)}%`;
  const fmtYear = (iso) => (iso ? iso.slice(0, 4) : "?");
  const years = (from, to) => (fmtYear(from) === fmtYear(to) ? fmtYear(from) : `${fmtYear(from)}–${fmtYear(to)}`);
  const MIN = 30; // fewer official matches than this and the shares say little
  const all = index.rivalries.filter((r) => r.record?.n);
  const leader = (r) => (r.record.a >= r.record.b ? "a" : "b");
  const tally = (r) => `${short(r, "a")} ${r.record.a} · ${r.record.d} draws · ${short(r, "b")} ${r.record.b}`;

  const METRICS = [
    { key: "played", head: "Matches", label: "Most played", note: "Official matches between them.",
      rows: all, value: (r) => r.record.n, text: (r) => String(r.record.n), sub: tally },
    { key: "even", head: "Gap", label: "Most even", note: `The smallest gap between the two sides' wins, as a share of the matches played (rivalries with at least ${MIN} matches).`,
      rows: all.filter((r) => r.record.n >= MIN), value: (r) => -Math.abs(r.record.a - r.record.b) / r.record.n,
      text: (r) => (r.record.a === r.record.b ? "Level" : `${Math.abs(r.record.a - r.record.b)} wins`), sub: tally },
    { key: "lopsided", head: "Leader", label: "Most one-sided", note: `The leader's share of the matches that had a winner (rivalries with at least ${MIN} matches).`,
      rows: all.filter((r) => r.record.n >= MIN), value: (r) => Math.max(r.record.a, r.record.b) / (r.record.a + r.record.b),
      text: (r) => pct(Math.max(r.record.a, r.record.b) / (r.record.a + r.record.b)), sub: (r) => `${short(r, leader(r))} leads · ${tally(r)}` },
    { key: "draws", head: "Draws", label: "Most draws", note: `Draws as a share of the matches played (rivalries with at least ${MIN} matches).`,
      rows: all.filter((r) => r.record.n >= MIN), value: (r) => r.record.d / r.record.n, text: (r) => pct(r.record.d / r.record.n), sub: tally },
    { key: "goals", head: "Per match", label: "Most goals", note: `Goals per match (rivalries with at least ${MIN} matches and a goal count).`,
      rows: all.filter((r) => r.record.n >= MIN && r.record.ga != null && r.record.gb != null), value: (r) => (r.record.ga + r.record.gb) / r.record.n,
      text: (r) => ((r.record.ga + r.record.gb) / r.record.n).toFixed(2), sub: (r) => `${short(r, "a")} ${r.record.ga} · ${short(r, "b")} ${r.record.gb} goals in ${r.record.n} matches` },
    { key: "now", head: "Wins", label: "Who rules now", note: "Wins in the last 20 official matches (rivalries where every match is listed).",
      rows: all.filter((r) => r.records), value: (r) => Math.max(r.records.last20.a, r.records.last20.b) * 100 - r.records.last20.d,
      text: (r) => `${Math.max(r.records.last20.a, r.records.last20.b)} of 20`,
      sub: (r) => { const l = r.records.last20; return `${short(r, l.a >= l.b ? "a" : "b")} · last 20: ${short(r, "a")} ${l.a}, ${l.d} draws, ${short(r, "b")} ${l.b}`; } },
    { key: "streak", head: "Wins", label: "Longest winning run", note: "The most consecutive official wins against the rival.",
      rows: all.filter((r) => r.records?.winRun), value: (r) => r.records.winRun.n, text: (r) => String(r.records.winRun.n),
      sub: (r) => `${short(r, r.records.winRun.side)}, ${years(r.records.winRun.from, r.records.winRun.to)}` },
    { key: "unbeaten", head: "Matches", label: "Longest unbeaten run", note: "The most consecutive official matches without losing to the rival.",
      rows: all.filter((r) => r.records?.unbeaten), value: (r) => r.records.unbeaten.n, text: (r) => String(r.records.unbeaten.n),
      sub: (r) => `${short(r, r.records.unbeaten.side)}, ${years(r.records.unbeaten.from, r.records.unbeaten.to)}` },
    { key: "bigwin", head: "Score", label: "Biggest win", note: "The widest margin in an official match between them.",
      rows: all.filter((r) => r.records?.bigWin), value: (r) => { const [w, l] = r.records.bigWin.score.split("–").map(Number); return (w - l) * 100 + w; },
      text: (r) => r.records.bigWin.score, sub: (r) => `${short(r, r.records.bigWin.side)}, ${fmtYear(r.records.bigWin.date)}${r.records.bigWin.comp ? ` · ${r.records.bigWin.comp}` : ""}` },
  ];

  function rivalryCell(r) {
    const a = el("a", "club", "");
    a.href = `#${r.id}`;
    a.addEventListener("click", () => scrollTo({ top: 0, behavior: Viz.reduceMotion ? "auto" : "smooth" }));
    a.append(F.flag(countryOf.get(r.group)), document.createTextNode(r.name));
    return a;
  }

  function render(key) {
    const m = METRICS.find((x) => x.key === key);
    document.getElementById("compare-note").textContent = m.note;
    const rows = [...m.rows].sort((a, b) => m.value(b) - m.value(a) || d3.ascending(a.name, b.name));
    F.richTable(document.getElementById("compare-table"), [
      { label: "#", cls: "rank", render: (r) => String(rows.indexOf(r) + 1) },
      { label: "Rivalry", render: (r) => F.withSub(rivalryCell(r), `${r.subtitle} · ${m.sub(r)}`) },
      { label: m.head, cls: "num strong", render: m.text },
    ], rows);
  }
  Viz.segmented("compare-tabs", METRICS, "played", render);
  render("played");
})();
