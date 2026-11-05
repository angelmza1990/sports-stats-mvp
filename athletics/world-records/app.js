/* Athletics world records: how each record came down (or went up), mark by mark. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote, ttRow } = Viz;
  const raw = await d3.json(document.body.dataset.src);
  const F = Football({ clubs: {}, countries: raw.countries });
  const parse = d3.utcParse("%Y-%m-%d");
  const fmtDay = d3.utcFormat("%-d %b %Y");
  const today = new Date();
  const years = (a, b) => (b - a) / (365.25 * 864e5);
  const athlete = (m) => {
    const span = el("span", "club");
    span.append(F.flag(m.nation), document.createTextNode(m.athlete));
    return span;
  };
  const nationName = (c) => raw.countries[c]?.name ?? c ?? "";
  // A time in seconds as the sport writes it: 9.58, 3:42.66, 1:59:30.
  const clock = (s) => {
    if (s < 60) return s.toFixed(2).replace(/\.?0+$/, "") || "0";
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    const ss = sec.toFixed(sec % 1 ? 2 : 0).replace(/\.?0+$/, "").padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
  };
  const shown = (e, v) => (e.kind === "time" ? clock(v) : `${v.toFixed(2)} m`);
  const stood = (y) => (y < 1 ? `${Math.max(1, Math.round(y * 12))} months` : `${y.toFixed(y < 10 ? 1 : 0)} years`);

  const events = raw.events.map((e) => ({ ...e, marks: e.marks.map((m) => ({ ...m, t: parse(m.date) })) }));
  events.forEach((e) => e.marks.forEach((m, i) => (m.until = e.marks[i + 1]?.t ?? today)));
  const LABELS = [...new Set(events.map((e) => e.label))];
  const state = { label: "100 m", sex: "men" };
  const current = () => events.find((e) => e.label === state.label && e.sex === state.sex) ?? events.find((e) => e.label === state.label);

  /* ---------- Page tiles ---------- */

  const all = events.flatMap((e) => e.marks.map((m) => ({ ...m, e })));
  const oldest = events.map((e) => e.marks[e.marks.length - 1]).sort((a, b) => a.t - b.t)[0];
  const oldestEvent = events.find((e) => e.marks.includes(oldest));
  F.statTiles("stats", [
    { label: "World records", value: String(all.length), detail: `in ${events.length} events, since ${d3.min(all, (m) => m.t).getUTCFullYear()}` },
    { label: "Oldest record today", value: String(oldest.t.getUTCFullYear()), detail: `${oldestEvent.label} ${oldestEvent.sex}, ${oldest.athlete}` },
    { label: "Newest record", value: String(d3.max(all, (m) => m.t).getUTCFullYear()), detail: (() => { const m = all.reduce((p, q) => (q.t > p.t ? q : p)); return `${m.e.label} ${m.e.sex}, ${m.athlete}`; })() },
  ]);

  /* ---------- One event ---------- */

  function render() {
    const e = current();
    state.sex = e.sex;
    const marks = e.marks;
    const first = marks[0], last = marks[marks.length - 1];
    const longest = marks.reduce((p, q) => (years(q.t, q.until) > years(p.t, p.until) ? q : p));
    const counts = d3.rollups(marks, (v) => v.length, (m) => m.athlete).sort((a, b) => b[1] - a[1]);
    const root = document.getElementById("event-stats");
    root.replaceChildren();
    F.statTiles("event-stats", [
      { label: "The record", value: last.text, detail: `${last.athlete}, ${fmtDay(last.t)}` },
      { label: "Records", value: String(marks.length), detail: `since ${first.text} in ${first.t.getUTCFullYear()}` },
      { label: "Longest standing", value: stood(years(longest.t, longest.until)), detail: `${longest.text}, ${longest.athlete} (${longest.t.getUTCFullYear()})${longest === last ? ", still standing" : ""}` },
      { label: "Most records", value: String(counts[0][1]), detail: counts[0][0] },
    ]);
    const note = document.getElementById("event-note");
    note.replaceChildren(document.createTextNode(`${e.note} `));
    const a = el("a", null, "Source");
    a.href = e.source;
    note.append(a, document.createTextNode("."));
    rerender();
    F.richTable(document.getElementById("records-table"), [
      { label: "Mark", cls: "num strong", render: (m) => m.text },
      { label: "Athlete", render: (m) => F.withSub(athlete(m), nationName(m.nation)) },
      { label: "Date", render: (m) => F.withSub(document.createTextNode(fmtDay(m.t)), m === last ? `standing for ${stood(years(m.t, today))}` : `stood ${stood(years(m.t, m.until))}`) },
    ], marks.slice().reverse());
  }

  function chart(width) {
    const e = current();
    const marks = e.marks;
    const narrow = width < 640;
    const height = narrow ? 260 : 340;
    const m = { t: 14, r: narrow ? 12 : 24, b: 26, l: e.kind === "time" && marks[0].value >= 60 ? 64 : 48 };
    const x = d3.scaleUtc().domain([d3.utcYear.floor(marks[0].t), today]).range([m.l, width - m.r]);
    const y = d3.scaleLinear().domain(d3.extent(marks, (d) => d.value)).nice().range([height - m.b, m.t]);
    const svg = d3.create("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", `${e.label} ${e.sex} world record over time`);
    const yt = y.ticks(5);
    svg.append("g").selectAll("line").data(yt).join("line").attr("class", "gridline").attr("x1", m.l).attr("x2", width - m.r).attr("y1", y).attr("y2", y);
    svg.append("g").attr("class", "axis").selectAll("text").data(yt).join("text").attr("x", m.l - 6).attr("y", (d) => y(d) + 4).attr("text-anchor", "end").text((d) => shown(e, d));
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${height - m.b})`)
      .call(d3.axisBottom(x).ticks(narrow ? 5 : 10).tickSize(0).tickPadding(8)).call((g) => g.select(".domain").remove());
    const line = d3.line().curve(d3.curveStepAfter).x((d) => x(d.t)).y((d) => y(d.value));
    svg.append("path").attr("class", "trend-line").attr("stroke", "var(--series-1)").attr("d", line([...marks, { ...marks[marks.length - 1], t: today }]));
    const dots = svg.append("g").selectAll("circle").data(marks).join("circle").attr("class", "trend-dot").attr("r", 4)
      .attr("cx", (d) => x(d.t)).attr("cy", (d) => y(d.value)).attr("fill", "var(--series-1)");
    Viz.tooltipOn(dots, (t, d) => {
      t.append(ttTitle(d.text), ttRow("var(--series-1)", d.athlete, ` · ${nationName(d.nation)}`), ttNote(`${fmtDay(d.t)} · stood ${stood(years(d.t, d.until))}`));
    });
    // Name the holders of the records that stood longest.
    if (!narrow) {
      const top = marks.slice().sort((p, q) => years(q.t, q.until) - years(p.t, p.until)).slice(0, 4);
      svg.append("g").selectAll("text").data(top).join("text").attr("class", "label-muted")
        .attr("x", (d) => Math.min(x(d.t) + 6, width - m.r - 120)).attr("y", (d) => y(d.value) + (e.kind === "time" ? -8 : 16)).text((d) => `${d.athlete.split(" ").slice(-1)[0]} ${d.text}`);
    }
    document.getElementById("progression-chart").replaceChildren(svg.node());
  }
  const rerender = Viz.responsive("progression-chart", chart);

  Viz.segmented("event-tabs", LABELS.map((l) => ({ key: l, label: l })), state.label, (k) => {
    state.label = k;
    const sexes = events.filter((e) => e.label === k).map((e) => e.sex);
    sexTabs(sexes.includes(state.sex) ? state.sex : sexes[0], sexes);
    render();
  });
  function sexTabs(sex, sexes) {
    state.sex = sex;
    document.getElementById("sex-tabs").replaceChildren();
    Viz.segmented("sex-tabs", sexes.map((s) => ({ key: s, label: s === "men" ? "Men" : "Women" })), sex, (k) => { state.sex = k; render(); });
  }
  sexTabs("men", ["men", "women"]);
  render();

  /* ---------- The records today ---------- */

  const standing = events.map((e) => ({ e, m: e.marks[e.marks.length - 1] })).sort((a, b) => a.m.t - b.m.t);
  F.richTable(document.getElementById("today-table"), [
    { label: "Event", render: (r) => F.withSub(document.createTextNode(r.e.label), r.e.sex === "men" ? "Men" : "Women") },
    { label: "Record", render: (r) => F.withSub(athlete(r.m), `${r.m.text} · ${fmtDay(r.m.t)}`) },
    { label: "Standing", cls: "num strong", render: (r) => stood(years(r.m.t, today)) },
  ], standing);
  const setters = d3.rollups(all, (v) => v, (m) => m.athlete).sort((a, b) => b[1].length - a[1].length).slice(0, 15);
  F.rankList(document.getElementById("setters-list"), setters.map(([who, list]) => ({
    icon: F.flag(list[0].nation), label: who, value: list.length, second: [...new Set(list.map((m) => m.e.label))].join(", "), color: "var(--series-1)",
    tip: (t) => t.append(ttTitle(who), ttNote(list.map((m) => `${m.text} (${m.t.getUTCFullYear()})`).join(" · "))),
  })), ["Athlete", "Records", "Events"]);
})();
