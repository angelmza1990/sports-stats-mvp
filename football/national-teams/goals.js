/* National teams: the scorers of the competitive internationals, goals by minute, hat-tricks and the penalty shoot-outs. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote, ttRow } = Viz;
  const data = await d3.json("data/goals.json");
  const teams = data.teams;
  const key = (i) => `t${i}`;
  const countries = Object.fromEntries(teams.map((t, i) => [key(i), { name: t.name, flag: t.flag }]));
  const F = Football({ nationMode: true, clubs: Object.fromEntries(teams.map((t, i) => [key(i), { name: t.name, country: key(i) }])), countries });
  const name = (i) => teams[i].name;
  const label = (i) => F.clubLabel(key(i));
  const player = (p) => {
    const span = el("span", "club");
    span.append(F.flag(key(p.team)), document.createTextNode(p.name));
    return span;
  };
  const fmtDay = d3.utcFormat("%-d %b %Y");
  const day = (s) => fmtDay(d3.utcParse("%Y-%m-%d")(s));
  const pct = (x, digits = 0) => `${(x * 100).toFixed(digits)}%`;
  const fmt = d3.format(",");
  const cov = data.coverage;

  /* ---------- Goals ---------- */

  document.getElementById("goals-lede").textContent =
    `${fmt(cov.goals)} goals with their scorer and minute, from ${fmt(cov.matches)} of the ${fmt(cov.competitive)} competitive matches: the World Cup, the continental championships, their qualifiers, the Nations Leagues and other tournaments. ` +
    `${pct(cov.pens / cov.goals, 1)} were penalties and ${pct(cov.own / cov.goals, 1)} own goals. Friendlies have no scorers in the database and are left out.`;

  const SCOPES = [
    { key: "all", label: "All competitive" },
    { key: "wc", label: "World Cup" },
    { key: "cont", label: "Continental championships" },
    { key: "qual", label: "Qualifiers" },
  ];
  let scope = "all";

  function renderScorers() {
    const list = data.scorers[scope].slice(0, 25);
    F.richTable(document.getElementById("scorers-table"), [
      { label: "#", cls: "rank", render: (p) => String(data.scorers[scope].findIndex((q) => q.goals === p.goals) + 1) },
      { label: "Player", render: (p) => F.withSub(player(p), `${name(p.team)} · ${p.years}`) },
      { label: "Goals", cls: "num strong", render: (p) => String(p.goals) },
      ...(scope === "all" ? [
        { label: "Pens", cls: "num hide-sm", render: (p) => String(p.pens) },
        { label: "Hat-tricks", cls: "num hide-sm", render: (p) => String(p.hat) },
      ] : []),
    ], list);
  }

  // Five-minute buckets of normal time, then extra time. Stoppage time is mostly recorded as the 45th or 90th minute.
  const BUCKETS = d3.range(18).map((k) => ({ from: k * 5 + 1, to: k * 5 + 5, label: `${k * 5 + 1}–${k * 5 + 5}` })).concat([{ from: 91, to: 120, label: "ET" }]);
  function renderMinutes(width) {
    const counts = data.minutes[scope];
    const bars = BUCKETS.map((b) => ({ ...b, n: d3.sum(counts.slice(b.from, b.to + 1)) }));
    const total = d3.sum(bars, (b) => b.n);
    const narrow = width < 640;
    const height = narrow ? 200 : 240;
    const m = { t: 10, r: 8, b: 26, l: 40 };
    const x = d3.scaleBand().domain(bars.map((b) => b.label)).range([m.l, width - m.r]).padding(0.2);
    const y = d3.scaleLinear().domain([0, d3.max(bars, (b) => b.n / total)]).nice().range([height - m.b, m.t]);
    const svg = d3.create("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", "Goals by minute");
    const yt = y.ticks(4);
    svg.append("g").selectAll("line").data(yt).join("line").attr("class", (d) => (d === 0 ? "baseline" : "gridline"))
      .attr("x1", m.l).attr("x2", width - m.r).attr("y1", y).attr("y2", y);
    svg.append("g").attr("class", "axis").selectAll("text").data(yt).join("text")
      .attr("x", m.l - 6).attr("y", (d) => y(d) + 4).attr("text-anchor", "end").text((d) => pct(d));
    svg.append("g").attr("class", "axis").selectAll("text").data(bars.filter((b, k) => k % (narrow ? 3 : 1) === 0 || b.label === "ET")).join("text")
      .attr("x", (b) => x(b.label) + x.bandwidth() / 2).attr("y", height - 8).attr("text-anchor", "middle").text((b) => (b.label === "ET" ? "ET" : b.to));
    const marks = svg.append("g").selectAll("path").data(bars).join("path").attr("fill", "var(--series-1)")
      .attr("d", (b) => Viz.columnPath(x(b.label), y(b.n / total), x.bandwidth(), y(0) - y(b.n / total), Math.min(3, x.bandwidth() / 2)));
    Viz.tooltipOn(marks, (t, b) => {
      t.append(ttTitle(b.label === "ET" ? "Extra time" : `Minutes ${b.label}`), ttRow("var(--series-1)", fmt(b.n), ` goals (${pct(b.n / total, 1)})`));
      if (b.to === 45 || b.to === 90) t.append(ttNote("Includes most stoppage-time goals."));
    });
    document.getElementById("minutes-root").replaceChildren(svg.node());
    const second = d3.sum(counts.slice(46, 91)), first = d3.sum(counts.slice(1, 46));
    document.getElementById("minutes-note").textContent =
      `${pct(second / (first + second))} of the goals in normal time come after half-time. The 41–45 and 86–90 bars include most stoppage-time goals, which the database records as the 45th or 90th minute.`;
  }
  const rerenderMinutes = Viz.responsive("minutes-root", renderMinutes);
  Viz.segmented("goals-scope", SCOPES, scope, (k) => { scope = k; renderScorers(); rerenderMinutes(); });
  renderScorers();

  // A team's own top scorers.
  const pick = document.getElementById("team-scorers-pick");
  const withList = Object.keys(data.byTeam).map(Number).sort((p, q) => d3.ascending(name(p), name(q)));
  withList.forEach((i) => {
    const o = el("option", null, name(i));
    o.value = String(i);
    pick.append(o);
  });
  pick.value = String(teams.findIndex((t) => t.name === "Argentina"));
  function renderTeamScorers() {
    const list = data.byTeam[pick.value];
    F.rankList(document.getElementById("team-scorers"), list.map((p) => ({
      icon: F.flag(key(p.team)), label: p.name, value: p.goals, second: p.years, color: "var(--series-1)",
      tip: (t) => t.append(ttTitle(p.name), ttNote(`${p.goals} competitive goals for ${name(p.team)}, ${p.pens} from the penalty spot · ${p.years}`)),
    })), ["Player", "Goals", "Years"]);
  }
  pick.addEventListener("change", renderTeamScorers);
  renderTeamScorers();

  F.richTable(document.getElementById("hat-table"), [
    { label: "Goals", cls: "num strong", render: (h) => String(h.goals) },
    { label: "Player", render: (h) => F.withSub(player(h), `${h.score} vs ${name(h.opponent)}`) },
    { label: "Date", cls: "hide-sm", render: (h) => F.withSub(document.createTextNode(day(h.date)), h.tournament) },
  ], data.hatTricks.slice(0, 12));

  /* ---------- Penalty shoot-outs ---------- */

  const so = data.shootouts;
  document.getElementById("so-lede").textContent =
    `${fmt(so.teams.reduce((n, r) => n + r.all[0], 0))} shoot-outs between national teams since the first in 1967. ` +
    `Where the order is known (${so.firstKnown} shoot-outs), the team that kicked first won ${pct(so.firstWon / so.firstKnown)}.`;
  const soState = { scope: "all", sort: "most" };
  function renderShootouts() {
    const n = (r) => r[soState.scope][0] + r[soState.scope][1];
    const share = (r) => r[soState.scope][0] / n(r);
    const list = so.teams.filter((r) => n(r) >= (soState.sort === "most" ? 1 : so.min))
      .sort((p, q) => (soState.sort === "most" ? n(q) - n(p) || share(q) - share(p)
        : soState.sort === "best" ? share(q) - share(p) || n(q) - n(p) : share(p) - share(q) || n(q) - n(p))).slice(0, 20);
    F.richTable(document.getElementById("so-table"), [
      { label: "#", cls: "rank", render: (r) => String(list.indexOf(r) + 1) },
      { label: "Team", render: (r) => label(r.team) },
      { label: "Played", cls: "num", render: (r) => String(n(r)) },
      { label: "Won", cls: "num strong", render: (r) => String(r[soState.scope][0]) },
      { label: "Lost", cls: "num", render: (r) => String(r[soState.scope][1]) },
      { label: "Won %", cls: "num", render: (r) => pct(share(r)) },
    ], list);
    document.getElementById("so-note").textContent = soState.sort === "most" ? "" : `Teams with at least ${so.min} shoot-outs${soState.scope === "major" ? " at these tournaments" : ""}.`;
  }
  Viz.segmented("so-sort", [{ key: "most", label: "Most" }, { key: "best", label: "Best record" }, { key: "worst", label: "Worst record" }], "most",
    (k) => { soState.sort = k; renderShootouts(); });
  Viz.segmented("so-scope", [{ key: "all", label: "All" }, { key: "major", label: "World Cup and continental" }], "all",
    (k) => { soState.scope = k; renderShootouts(); });
  renderShootouts();

  F.richTable(document.getElementById("so-major"), [
    { label: "Winner", render: (s) => F.withSub(label(s.winner), `${s.score} vs ${name(s.loser)}, won on penalties`) },
    { label: "Date", render: (s) => F.withSub(document.createTextNode(day(s.date)), s.tournament) },
  ], so.major);
})();
