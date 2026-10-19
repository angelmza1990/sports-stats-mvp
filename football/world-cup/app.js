/* FIFA World Cup: every tournament since 1930. */
(async function () {
  "use strict";

  const { el, table, responsive, tooltipOn, ttTitle, ttNote, barPath, columnPath } = Viz;
  const raw = await d3.json(document.body.dataset.src);
  // National teams play the role of clubs; flags stand in for crests.
  const data = {
    ...raw,
    nationMode: true,
    clubs: Object.fromEntries(Object.entries(raw.teams).map(([code, t]) => [code, { name: t.name, country: code, crest: null }])),
    countries: raw.teams,
  };
  const F = Football(data);
  const name = (code) => raw.teams[code]?.name ?? code;
  const confedOf = (code) => raw.teams[code]?.confederation ?? "UEFA";
  const editions = raw.editions;
  const NOTE = { penalties: "pens", "extra time": "a.e.t." };
  const finalScore = (e) => `${e.finalScore}${e.finalNote ? ` ${NOTE[e.finalNote]}` : ""}${e.shootout ? ` (${e.shootout})` : ""}`;
  // FIFA lists West Germany's record under Germany.
  const unified = (code) => ({ FRG: "GER" })[code] ?? code;

  const teamLabel = (code) => F.clubLabel(code);
  const hostsLabel = (codes) => {
    const wrap = el("span", "tags");
    codes.forEach((c) => wrap.append(F.flag(c)));
    wrap.append(document.createTextNode(codes.map(name).join(", ")));
    return wrap;
  };

  /* ---------- Stat tiles ---------- */

  const titles = d3.rollup(editions, (v) => v.length, (e) => unified(e.champion));
  const [leader, leaderN] = d3.greatest(titles, (d) => d[1]);
  F.statTiles("stats", [
    { label: "Tournaments", value: String(editions.length), detail: `${editions[0].year} to ${editions[editions.length - 1].year}` },
    { label: "Champions", value: String(titles.size), detail: `national teams; ${name(leader)} leads with ${leaderN}`, club: leader },
    { label: "Goals scored", value: d3.format(",")(d3.sum(editions, (e) => e.goals)), detail: `in ${d3.format(",")(d3.sum(editions, (e) => e.matches))} matches` },
    { label: "Latest champion", value: name(editions[editions.length - 1].champion), detail: `${editions[editions.length - 1].year}, ${finalScore(editions[editions.length - 1])} vs ${name(editions[editions.length - 1].runnerUp)}`, club: editions[editions.length - 1].champion },
  ]);

  /* ---------- Bar chart race: titles / finals / top four ---------- */

  const MEASURES = {
    titles: { label: "Titles", teams: (e) => [e.champion] },
    finals: { label: "Finals reached", teams: (e) => [e.champion, e.runnerUp] },
    podium: { label: "Top-four finishes", teams: (e) => [e.champion, e.runnerUp, e.third, e.fourth].filter(Boolean) },
  };
  function frames(key) {
    const tally = new Map();
    const reached = new Map();
    const out = [{ label: "1930", event: null, ranked: [] }];
    editions.forEach((e, i) => {
      MEASURES[key].teams(e).forEach((t) => {
        const id = unified(t);
        tally.set(id, (tally.get(id) ?? 0) + 1);
        reached.set(id, i);
      });
      const ranked = [...tally.entries()].map(([id, n]) => ({ id, n, since: reached.get(id) }))
        .sort((a, b) => b.n - a.n || a.since - b.since).slice(0, 10);
      out.push({ label: String(e.year), event: e, ranked });
    });
    return out;
  }
  const CONF_COLOR = { UEFA: "var(--series-1)", CONMEBOL: "var(--series-2)" };
  const race = F.race(frames("titles"), {
    colorOf: (id) => CONF_COLOR[confedOf(id)] ?? "var(--ink-muted)",
    emptyTicker: "Press play to start with the first World Cup, Uruguay 1930.",
    ticker: (e) => [F.flag(e.champion), el("strong", null, ` ${e.year} · ${name(e.champion)}`),
      document.createTextNode(` def. ${name(e.runnerUp)} ${finalScore(e)} · hosts: ${e.hosts.map(name).join(", ")}`)],
    frameMs: 900,
  });
  Viz.segmented("race-metric", Object.entries(MEASURES).map(([key, m]) => ({ key, label: m.label })), "titles",
    (k) => race.setFrames(frames(k)));

  /* ---------- Champions, runners-up and the podium ---------- */

  (function championsTable() {
    const root = document.getElementById("champions-table");
    const yearsOf = (list) => list.map((e) => e.year).join(", ") || "–";
    const byTeam = () => {
      const ids = new Set(editions.flatMap((e) => [e.champion, e.runnerUp, e.third, e.fourth].filter(Boolean)));
      const rows = [...ids].map((id) => ({
        id,
        won: editions.filter((e) => e.champion === id),
        lost: editions.filter((e) => e.runnerUp === id),
        third: editions.filter((e) => e.third === id),
        fourth: editions.filter((e) => e.fourth === id),
      })).sort((a, b) => b.won.length - a.won.length || b.lost.length - a.lost.length || b.third.length - a.third.length || b.fourth.length - a.fourth.length);
      F.richTable(root, [
        { label: "Team", render: (r) => F.withSub(teamLabel(r.id), `Won: ${yearsOf(r.won)} · Runner-up: ${yearsOf(r.lost)}`) },
        { label: "Titles", cls: "num strong", render: (r) => String(r.won.length) },
        { label: "Runners-up", short: "2nd", cls: "num", render: (r) => String(r.lost.length) },
        { label: "Third", short: "3rd", cls: "num", render: (r) => String(r.third.length) },
        { label: "Fourth", short: "4th", cls: "num", render: (r) => String(r.fourth.length) },
        { label: "Years won", cls: "years", render: (r) => yearsOf(r.won) },
        { label: "Years runner-up", cls: "years", render: (r) => yearsOf(r.lost) },
      ], rows);
    };
    const everyFinal = () => F.richTable(root, [
      { label: "Year", render: (e) => String(e.year) },
      { label: "Champion", render: (e) => teamLabel(e.champion) },
      { label: "Score", cls: "score", render: (e) => finalScore(e) },
      { label: "Runner-up", render: (e) => teamLabel(e.runnerUp) },
      { label: "Third", cls: "hide-sm", render: (e) => (e.third ? teamLabel(e.third) : "–") },
      { label: "Final venue", cls: "years", render: (e) => [e.finalVenue, e.finalCity].filter(Boolean).join(", ") || "–" },
    ], editions.slice().reverse());
    Viz.segmented("champions-tabs", [{ key: "team", label: "By team" }, { key: "final", label: "Every final" }], "team",
      (k) => (k === "team" ? byTeam() : everyFinal()));
    byTeam();
  })();

  /* ---------- By continent ---------- */

  (function confederations() {
    const CONFEDS = ["UEFA", "CONMEBOL", "CONCACAF", "AFC", "CAF", "OFC"];
    const NAMES = { UEFA: "Europe (UEFA)", CONMEBOL: "South America (CONMEBOL)", CONCACAF: "North & Central America (CONCACAF)", AFC: "Asia (AFC)", CAF: "Africa (CAF)", OFC: "Oceania (OFC)" };
    const groups = CONFEDS.map((c) => {
      const won = editions.filter((e) => confedOf(e.champion) === c).map((e) => ({ ...e, champion: unified(e.champion) }));
      const icon = el("i", "confed-key");
      icon.style.setProperty("--c", CONF_COLOR[c] ?? "var(--ink-muted)");
      return {
        label: NAMES[c], icon, won,
        lost: editions.filter((e) => confedOf(e.runnerUp) === c),
        winners: d3.groups(won, (e) => e.champion).sort((a, b) => b[1].length - a[1].length),
      };
    }).filter((g) => g.won.length || g.lost.length);
    F.groupRows(document.getElementById("confederations-list"), groups, "Confederation");
    const versus = document.getElementById("versus");
    const side = (c, right) => {
      const box = el("div", `side${right ? " right" : ""}`);
      const label = el("div", "name");
      const key = el("i");
      key.style.setProperty("--c", CONF_COLOR[c]);
      if (right) label.append(document.createTextNode(NAMES[c]), key);
      else label.append(key, document.createTextNode(NAMES[c]));
      box.append(label, el("div", "big", String(editions.filter((e) => confedOf(e.champion) === c).length)));
      return box;
    };
    versus.append(side("UEFA"), el("div", "mid", `${editions.length} World Cups`), side("CONMEBOL", true));
  })();

  /* ---------- Hosts ---------- */

  (function hosts() {
    const finish = (e, code) => (e.champion === code ? "Champion" : e.runnerUp === code ? "Runner-up" : e.third === code ? "Third" : e.fourth === code ? "Fourth" : "Did not reach the semi-finals");
    const hostWins = editions.filter((e) => e.hosts.includes(e.champion));
    document.getElementById("hosts-note").textContent =
      `${hostWins.length} hosts have won their own World Cup: ${hostWins.map((e) => `${name(e.champion)} ${e.year}`).join(", ")}.`;
    const times = d3.rollups(editions.flatMap((e) => e.hosts.map((h) => ({ host: unified(h), year: e.year }))), (v) => v.map((d) => d.year), (d) => d.host)
      .sort((a, b) => b[1].length - a[1].length || a[1][0] - b[1][0]);
    const summary = document.getElementById("hosts-summary");
    times.forEach(([code, years]) => {
      const chip = el("span", "host-chip");
      chip.append(F.flag(code), el("strong", null, name(code)), document.createTextNode(` ${years.join(", ")}`));
      summary.append(chip);
    });
    F.richTable(document.getElementById("hosts-table"), [
      { label: "Year", render: (e) => String(e.year) },
      { label: "Host", render: (e) => hostsLabel(e.hosts) },
      { label: "Teams", cls: "num", render: (e) => String(e.teams) },
      { label: "Host result", render: (e) => e.hosts.map((h) => (e.hosts.length > 1 ? `${name(h)}: ` : "") + finish(e, h)).join(" · ") },
      { label: "Champion", cls: "hide-sm", render: (e) => teamLabel(e.champion) },
    ], editions.slice().reverse().map((e) => ({ ...e, _rowClass: e.hosts.includes(e.champion) ? "split-row" : null })));
  })();

  /* ---------- Repeated finals ---------- */

  F.repeatedFinals(document.getElementById("pairs-list"),
    editions.map((e) => ({ ...e, champion: unified(e.champion), runnerUp: unified(e.runnerUp) })),
    (e) => `${e.year} ${name(e.champion)} (${finalScore(e)})`);

  /* ---------- How the tournament grew ---------- */

  (function growth() {
    const METRICS = [
      { key: "goals", label: "Goals", value: (e) => e.goals, fmt: d3.format(",") },
      { key: "matches", label: "Matches", value: (e) => e.matches, fmt: d3.format(",") },
      { key: "teams", label: "Teams", value: (e) => e.teams, fmt: d3.format(",") },
      { key: "gpm", label: "Goals per match", value: (e) => e.goals / e.matches, fmt: d3.format(".2f") },
      { key: "attendance", label: "Attendance", value: (e) => e.attendance, fmt: d3.format(".3s") },
    ];
    let metric = METRICS[0];
    const container = d3.select("#growth-chart");
    function draw(width) {
      container.selectAll("*").remove();
      const narrow = width < 560;
      const height = 280;
      const margin = { top: 24, right: 8, bottom: 28, left: 44 };
      const x = d3.scaleBand().domain(editions.map((e) => e.year)).range([margin.left, width - margin.right]).padding(0.25);
      const y = d3.scaleLinear().domain([0, d3.max(editions, metric.value)]).nice().range([height - margin.bottom, margin.top]);
      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", `${metric.label} per World Cup`);
      const axis = svg.append("g").attr("class", "axis");
      y.ticks(5).forEach((v) => {
        axis.append("line").attr("class", v === 0 ? "baseline" : "gridline").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", y(v)).attr("y2", y(v));
        axis.append("text").attr("x", margin.left - 8).attr("y", y(v)).attr("dy", "0.35em").attr("text-anchor", "end").text(d3.format(metric.key === "gpm" ? ".1f" : "~s")(v));
      });
      editions.forEach((e, i) => {
        if (narrow && i % 3 !== 0 && i !== editions.length - 1) return;
        axis.append("text").attr("x", x(e.year) + x.bandwidth() / 2).attr("y", height - 8).attr("text-anchor", "middle").text(narrow ? `'${String(e.year).slice(2)}` : e.year);
      });
      const colW = Math.min(24, x.bandwidth());
      const g = svg.selectAll("g.col").data(editions).join("g").attr("class", "col mark-group")
        .attr("transform", (e) => `translate(${x(e.year) + (x.bandwidth() - colW) / 2},0)`);
      g.append("rect").attr("x", -4).attr("y", margin.top).attr("width", colW + 8).attr("height", height - margin.top - margin.bottom).attr("fill", "transparent");
      g.append("path").attr("class", "mark").attr("fill", "var(--series-1)")
        .attr("d", (e) => columnPath(0, y(metric.value(e)), colW, y(0) - y(metric.value(e))));
      const maxE = d3.greatest(editions, metric.value);
      g.filter((e) => e === maxE || e === editions[editions.length - 1]).append("text").attr("class", "label-value")
        .attr("x", colW / 2).attr("y", (e) => y(metric.value(e)) - 6).attr("text-anchor", "middle").text((e) => metric.fmt(metric.value(e)));
      tooltipOn(g, (t, e) => {
        t.append(ttTitle(`${e.year} · ${e.hosts.map(name).join(", ")}`));
        t.append(Viz.ttRow("var(--series-1)", metric.fmt(metric.value(e)), metric.label.toLowerCase()));
        t.append(ttNote(`${e.teams} teams · ${e.matches} matches · ${e.goals} goals (${(e.goals / e.matches).toFixed(2)} per match)`));
        if (e.attendance) t.append(ttNote(`Attendance ${d3.format(",")(e.attendance)} (avg ${d3.format(",")(e.avgAttendance)})`));
      });
    }
    const rerender = responsive("growth-chart", draw);
    Viz.segmented("growth-tabs", METRICS, metric.key, (k) => {
      metric = METRICS.find((m) => m.key === k);
      rerender();
    });
    table("growth-table", ["Year", "Hosts", "Teams", "Matches", "Goals", "Goals/match", "Attendance", "Avg attendance"],
      editions.map((e) => [String(e.year), e.hosts.map(name).join(", "), String(e.teams), String(e.matches), String(e.goals),
        (e.goals / e.matches).toFixed(2), e.attendance ? d3.format(",")(e.attendance) : "–", e.avgAttendance ? d3.format(",")(e.avgAttendance) : "–"]).reverse());
  })();

  /* ---------- All-time points table ---------- */

  (function points() {
    const rows = raw.alltime.slice().sort((a, b) => b.pts - a.pts || (b.gf - b.ga) - (a.gf - a.ga));
    document.getElementById("points-note").textContent = `${raw.meta.pointsRule}. ${rows.length} national teams.`;
    const sign = (n) => (n > 0 ? `+${n}` : String(n));
    F.richTable(document.getElementById("points-table"), [
      { label: "#", cls: "num rank", render: (r) => String(rows.indexOf(r) + 1) },
      { label: "Team", render: (r) => teamLabel(r.team) },
      { label: "Tournaments", short: "WCs", cls: "num", render: (r) => String(r.part) },
      { label: "Played", short: "P", cls: "num", render: (r) => String(r.pld) },
      { label: "W", cls: "num", render: (r) => String(r.w) },
      { label: "D", cls: "num", render: (r) => String(r.d) },
      { label: "L", cls: "num", render: (r) => String(r.l) },
      { label: "GF", cls: "num hide-sm", render: (r) => String(r.gf) },
      { label: "GA", cls: "num hide-sm", render: (r) => String(r.ga) },
      { label: "GD", cls: "num", render: (r) => sign(r.gf - r.ga) },
      { label: "Points", short: "Pts", cls: "num strong", render: (r) => String(r.pts) },
    ], rows);
  })();

  /* ---------- Team appearances ---------- */

  (function appearances() {
    const list = raw.appearances.slice().sort((a, b) => b.apps - a.apps || a.debut - b.debut);
    const top = list.slice(0, 20);
    responsive("appearances-chart", (width) => {
      const container = d3.select("#appearances-chart");
      container.selectAll("*").remove();
      const narrow = width < 560;
      const rowH = 30;
      const barH = 16;
      const margin = { top: 4, right: 48, bottom: 4, left: narrow ? 130 : 180 };
      const height = margin.top + top.length * rowH + margin.bottom;
      const x = d3.scaleLinear().domain([0, d3.max(top, (r) => r.apps)]).range([0, width - margin.left - margin.right]);
      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", "Most World Cup appearances by national team");
      svg.append("line").attr("class", "baseline").attr("x1", margin.left).attr("x2", margin.left).attr("y1", 0).attr("y2", height);
      const g = svg.selectAll("g.row").data(top).join("g").attr("class", "row mark-group")
        .attr("transform", (d, i) => `translate(${margin.left},${margin.top + i * rowH})`);
      g.append("rect").attr("x", -margin.left).attr("width", width).attr("height", rowH).attr("fill", "transparent");
      g.append("text").attr("class", "label-name").attr("x", -34).attr("y", rowH / 2).attr("dy", "0.35em").attr("text-anchor", "end").text((d) => F.fit(name(d.team), narrow));
      g.append("g").attr("transform", `translate(-16,${rowH / 2})`).each(function (d) { F.svgCrest(d3.select(this), d.team, 20); });
      g.append("path").attr("class", "mark").attr("fill", "var(--ink-2)").attr("d", (d) => barPath(0, (rowH - barH) / 2, x(d.apps), barH));
      g.append("text").attr("class", "label-value").attr("x", (d) => x(d.apps) + 8).attr("y", rowH / 2).attr("dy", "0.35em").text((d) => d.apps);
      tooltipOn(g, (t, d) => {
        t.append(ttTitle(name(d.team)), Viz.ttRow("var(--ink-2)", d.apps, "World Cups"));
        t.append(ttNote(`Debut ${d.debut}${d.best ? ` · best: ${d.best}` : ""}`));
      });
    });
    table("appearances-table", ["Team", "World Cups", "Debut", "Best result"], list.map((r) => [name(r.team), String(r.apps), String(r.debut ?? "–"), r.best ?? "–"]));
  })();

  /* ---------- Players ---------- */

  (function players() {
    const root = document.getElementById("players-table");
    const playerCell = (p) => {
      const span = el("span", "club");
      span.append(F.flag(p.team), document.createTextNode(p.player));
      return F.withSub(span, `${name(p.team)} · ${p.tournaments}`);
    };
    const ranked = (list, key) => {
      const sorted = list.slice().sort((a, b) => b[key] - a[key]);
      let rank = 0;
      return sorted.map((p, i) => ({ ...p, rank: i > 0 && sorted[i - 1][key] === p[key] ? rank : (rank = i + 1) }));
    };
    // Drop footnote markers and separate years the source runs together ("19901994").
    const clean = (s) => s.replace(/(\d{4})T\b/g, "$1").replace(/(\d{4})(?=[\d[(])/g, "$1, ").replace(/\s+/g, " ");
    const views = {
      scorers: () => F.richTable(root, [
        { label: "#", cls: "num rank", render: (p) => String(p.rank) },
        { label: "Player", render: playerCell },
        { label: "Goals", cls: "num strong", render: (p) => String(p.goals) },
        { label: "Matches", short: "Apps", cls: "num", render: (p) => String(p.matches) },
        { label: "Goals per match", short: "Ratio", cls: "num", render: (p) => (p.matches ? (p.goals / p.matches).toFixed(2) : "–") },
        { label: "Tournaments", cls: "years", render: (p) => clean(p.tournaments) },
      ], ranked(raw.scorers, "goals").slice(0, 30).map((p) => ({ ...p, tournaments: clean(p.tournaments) }))),
      matches: () => F.richTable(root, [
        { label: "#", cls: "num rank", render: (p) => String(p.rank) },
        { label: "Player", render: playerCell },
        { label: "Matches", cls: "num strong", render: (p) => String(p.matches) },
        { label: "Tournaments", cls: "years", render: (p) => p.tournaments },
      ], ranked(raw.playerMatches, "matches").slice(0, 30)),
      tournaments: () => F.richTable(root, [
        { label: "#", cls: "num rank", render: (p) => String(p.rank) },
        { label: "Player", render: playerCell },
        { label: "Tournaments played", short: "Played", cls: "num strong", render: (p) => String(p.played) },
        { label: "In squad", short: "Squad", cls: "num", render: (p) => String(p.squads) },
        { label: "Years", cls: "years", render: (p) => p.tournaments },
      ], ranked(raw.playerTournaments, "played").slice(0, 30)),
    };
    Viz.segmented("players-tabs", [
      { key: "scorers", label: "Top scorers" },
      { key: "matches", label: "Most matches" },
      { key: "tournaments", label: "Most tournaments" },
    ], "scorers", (k) => views[k]());
    views.scorers();
  })();

  /* ---------- Awards by tournament ---------- */

  F.richTable(document.getElementById("awards-table"), [
    { label: "Year", render: (e) => String(e.year) },
    {
      label: "Top scorer", render: (e) => {
        const wrap = el("div", "stack-clubs");
        (e.topScorers || []).forEach((s) => {
          const span = el("span", "club");
          span.append(F.flag(s.team), document.createTextNode(s.player));
          wrap.append(span);
        });
        return wrap;
      },
    },
    { label: "Goals", cls: "num strong", render: (e) => String(e.topScorerGoals ?? "–") },
    { label: "Best player", cls: "hide-sm", render: (e) => e.bestPlayer ?? "–" },
    { label: "Winning coach", cls: "years", render: (e) => e.coach ?? "–" },
  ], editions.slice().reverse());

  /* ---------- Footer ---------- */

  const src = document.getElementById("sources");
  const LABELS = ["World Cup article", "list of finals", "records and statistics", "top goalscorers", "team appearances", "player appearances"];
  raw.meta.sources.forEach((url, i) => {
    const a = el("a", null, LABELS[i] ?? url);
    a.href = url;
    src.append(a);
    if (i < raw.meta.sources.length - 1) src.append(document.createTextNode(", "));
  });
  document.getElementById("data-through").textContent = `Covers every World Cup through ${raw.meta.through}.`;
})();
