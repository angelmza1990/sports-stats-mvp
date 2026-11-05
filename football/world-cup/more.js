/* FIFA World Cup: the defending champions, the penalty shoot-outs and how the scoring record grew. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote, ttRow } = Viz;
  const raw = await d3.json(document.body.dataset.src);
  const F = Football({
    ...raw, nationMode: true, countries: raw.teams,
    clubs: Object.fromEntries(Object.entries(raw.teams).map(([code, t]) => [code, { name: t.name, country: code, crest: null }])),
  });
  const name = (code) => raw.teams[code]?.name ?? code;
  const label = (code) => F.clubLabel(code);
  // FIFA counts West Germany's record for Germany.
  const unified = (code) => ({ FRG: "GER" })[code] ?? code;
  const fmtDay = d3.utcFormat("%-d %b %Y");
  const day = (s) => fmtDay(d3.utcParse("%Y-%m-%d")(s));
  const editions = raw.editions;
  const [YEAR, STAGE, DATE, HOME, AWAY, HG, AG, , PENS] = [0, 1, 2, 3, 4, 5, 6, 7, 8];

  /* ---------- Defending champions ---------- */

  const RANK = { "Group stage": 1, "Final round": 2, "Round of 32": 2, "Round of 16": 3, "Second group stage": 4, "Quarter-finals": 4, "Semi-finals": 5, "Third place": 5, Final: 6 };
  const RESULT = { 1: "Group stage", 2: "Round of 32", 3: "Round of 16", 4: "Quarter-finals" };
  function reached(year, code) {
    const e = editions.find((x) => x.year === year);
    const team = unified(code);
    if (unified(e.champion) === team) return { text: "Champion again", level: 9 };
    if (unified(e.runnerUp) === team) return { text: "Runner-up", level: 8 };
    if (unified(e.third) === team) return { text: "Third place", level: 7 };
    if (unified(e.fourth) === team) return { text: "Fourth place", level: 6 };
    const played = raw.matches.filter((m) => m[YEAR] === year && (unified(m[HOME]) === team || unified(m[AWAY]) === team));
    if (!played.length) return { text: "Did not take part", level: 0 };
    const best = d3.max(played, (m) => RANK[m[STAGE]] ?? 1);
    const stage = played.find((m) => (RANK[m[STAGE]] ?? 1) === best)[STAGE];
    // The 1974–1982 second group stages were the last eight (or twelve) teams.
    return { text: best === 4 && stage === "Second group stage" ? "Second group stage" : RESULT[best] ?? stage, level: best };
  }
  const defending = editions.slice(1).map((e, i) => ({ year: e.year, team: editions[i].champion, won: editions[i].year, ...reached(e.year, editions[i].champion) }));
  const out = defending.filter((d) => d.level === 1);
  document.getElementById("defending-lede").textContent =
    `How far each champion went at the next World Cup. ${defending.filter((d) => d.level === 9).length} retained the title (${defending.filter((d) => d.level === 9).map((d) => `${name(d.team)} in ${d.year}`).join(", ")}); ` +
    `${out.length} went out in the first round, ${out.filter((d) => d.year >= 2002).length} of them since 2002: ${out.map((d) => `${name(d.team)} ${d.year}`).join(", ")}.`;
  F.richTable(document.getElementById("defending-table"), [
    { label: "World Cup", render: (d) => String(d.year) },
    { label: "Defending champion", render: (d) => F.withSub(label(d.team), `champion in ${d.won}`) },
    { label: "Result", render: (d) => d.text },
  ], defending.slice().reverse());

  /* ---------- Penalty shoot-outs ---------- */

  const shootouts = raw.matches.filter((m) => m[PENS]).map((m) => {
    const homeWon = m[PENS][0] > m[PENS][1];
    return { year: m[YEAR], date: m[DATE], stage: m[STAGE], winner: homeWon ? m[HOME] : m[AWAY], loser: homeWon ? m[AWAY] : m[HOME],
      score: `${m[HG]}–${m[AG]}`, pens: homeWon ? `${m[PENS][0]}–${m[PENS][1]}` : `${m[PENS][1]}–${m[PENS][0]}` };
  });
  const record = new Map();
  shootouts.forEach((s) => {
    for (const [code, won] of [[unified(s.winner), 1], [unified(s.loser), 0]]) {
      const r = record.get(code) ?? { team: code, won: 0, lost: 0 };
      r[won ? "won" : "lost"] += 1;
      record.set(code, r);
    }
  });
  const teamsList = [...record.values()].sort((a, b) => b.won + b.lost - (a.won + a.lost) || b.won - a.won);
  const finals = shootouts.filter((s) => s.stage === "Final");
  document.getElementById("so-lede").textContent =
    `${shootouts.length} World Cup matches have been decided on penalties since the first, in 1982; ${finals.length} of them finals (${finals.map((s) => `${s.year}, ${name(s.winner)}`).join("; ")}).`;
  F.richTable(document.getElementById("so-teams"), [
    { label: "Team", render: (r) => label(r.team) },
    { label: "Played", cls: "num", render: (r) => String(r.won + r.lost) },
    { label: "Won", cls: "num strong", render: (r) => String(r.won) },
    { label: "Lost", cls: "num", render: (r) => String(r.lost) },
  ], teamsList);
  F.richTable(document.getElementById("so-list"), [
    { label: "Winner", render: (s) => F.withSub(label(s.winner), `${s.score}, ${s.pens} on penalties vs ${name(s.loser)}`) },
    { label: "Stage", render: (s) => F.withSub(document.createTextNode(String(s.year)), s.stage) },
  ], shootouts.slice().reverse());

  /* ---------- The scoring record ---------- */

  const steps = raw.recordTimeline;
  function renderRecord(width) {
    const narrow = width < 640;
    const height = narrow ? 220 : 260;
    const m = { t: 14, r: narrow ? 12 : 120, b: 26, l: 32 };
    const parse = d3.utcParse("%Y-%m-%d");
    const pts = steps.map((s) => ({ ...s, t: parse(s.date) }));
    const end = parse(`${raw.meta.through}-12-31`);
    const x = d3.scaleUtc().domain([parse("1930-01-01"), end]).range([m.l, width - m.r]);
    const y = d3.scaleLinear().domain([0, d3.max(pts, (p) => p.goals)]).nice().range([height - m.b, m.t]);
    const svg = d3.create("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", "The record for most World Cup goals over time");
    const yt = y.ticks(5);
    svg.append("g").selectAll("line").data(yt).join("line").attr("class", (d) => (d === 0 ? "baseline" : "gridline"))
      .attr("x1", m.l).attr("x2", width - m.r).attr("y1", y).attr("y2", y);
    svg.append("g").attr("class", "axis").selectAll("text").data(yt).join("text").attr("x", m.l - 6).attr("y", (d) => y(d) + 4).attr("text-anchor", "end").text((d) => d);
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${height - m.b})`)
      .call(d3.axisBottom(x).ticks(narrow ? 5 : 10).tickSize(0).tickPadding(8)).call((g) => g.select(".domain").remove());
    const line = d3.line().curve(d3.curveStepAfter).x((p) => x(p.t)).y((p) => y(p.goals));
    svg.append("path").attr("class", "trend-line").attr("stroke", "var(--series-1)").attr("d", line([...pts, { ...pts[pts.length - 1], t: end }]));
    // One dot per new (not equalled) record, labelled with the holders who took it past the old mark.
    const records = pts.filter((p, i) => i === 0 || p.goals > pts[i - 1].goals);
    const dots = svg.append("g").selectAll("circle").data(records).join("circle").attr("class", "trend-dot").attr("r", 4.5)
      .attr("cx", (p) => x(p.t)).attr("cy", (p) => y(p.goals)).attr("fill", "var(--series-1)");
    Viz.tooltipOn(dots, (t, p) => {
      const same = pts.filter((q) => q.goals === p.goals);
      t.append(ttTitle(`${p.goals} goal${p.goals === 1 ? "" : "s"}`), ttRow("var(--series-1)", p.player, ` (${name(p.team)}), ${day(p.date)}`));
      if (same.length > 1) t.append(ttNote(`Equalled by ${same.slice(1).map((q) => `${q.player} (${q.tournament})`).join(", ")}`));
    });
    if (!narrow) {
      const holders = d3.groups(records, (p) => p.player).map(([player, list]) => list[list.length - 1]).filter((p) => p.goals >= 10);
      svg.append("g").selectAll("text").data(holders).join("text").attr("class", "label-muted")
        .attr("x", (p) => x(p.t) + 8).attr("y", (p) => y(p.goals) - 6).text((p) => `${p.player} ${p.goals}`);
    }
    document.getElementById("record-chart").replaceChildren(svg.node());
  }
  Viz.responsive("record-chart", renderRecord);
  F.richTable(document.getElementById("record-table"), [
    { label: "Goals", cls: "num strong", render: (s) => String(s.goals) },
    { label: "Player", render: (s) => {
      const span = el("span", "club");
      span.append(F.flag(s.team), document.createTextNode(s.player));
      return F.withSub(span, name(s.team));
    } },
    { label: "Date", render: (s) => F.withSub(document.createTextNode(day(s.date)), `${s.tournament} World Cup`) },
  ], steps.slice().reverse());
})();
