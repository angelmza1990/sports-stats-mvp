/* EuroLeague: every final since 1958, titles by club and country, the all-time table of the EuroLeague era, the most decorated
   coaches and players, and five great rivalries game by game since 2000–01 (with their totals in every competition where published). */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote, ttRow } = Viz;
  const raw = await d3.json(document.body.dataset.src);
  const { finals, clubs, countries } = raw;
  // Crests come from the EuroLeague (clubs that never played it since 2000 get a lettered badge); all-time rows are keyed by API code.
  const entities = Object.fromEntries(Object.entries(clubs).map(([id, c]) => [id, { name: c.name, country: c.country, crest: c.crest }]));
  raw.alltime.forEach((r) => (entities[`code:${r.code}`] = { name: r.name, country: r.club ? clubs[r.club]?.country : null, crest: r.crest }));
  const F = Football({ clubs: entities, countries });
  const name = (id) => clubs[id]?.name ?? id;
  const latest = finals[finals.length - 1];
  const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
  const fmtDay = (iso) => d3.utcFormat("%-d %B %Y")(d3.utcParse("%Y-%m-%d")(iso));
  const score = (f) => f.games.map((g) => `${g[0]}–${g[1]}`).join(", ");
  const withFlag = (text, code) => {
    const span = el("span", "club");
    if (code) span.append(F.flag(code));
    span.append(document.createTextNode(text));
    return span;
  };

  /* ---------- Stat tiles ---------- */

  const titles = d3.rollup(finals, (v) => v.length, (f) => f.champion);
  const lost = d3.rollup(finals, (v) => v.length, (f) => f.runnerUp);
  const [top, topN] = d3.greatest(titles, (d) => d[1]);
  const coach = raw.coaches[0], player = raw.players[0];
  F.statTiles("stats", [
    { label: "Finals", value: String(finals.length), detail: `${finals[0].season} to ${latest.season}, ${titles.size} different champions` },
    { label: "Most titles", value: String(topN), detail: name(top), club: top },
    { label: "Most titles, coach", value: String(coach.titles), detail: coach.name },
    { label: "Most titles, player", value: String(player.titles), detail: player.name },
  ]);

  /* ---------- Bar chart race ---------- */

  F.race(F.titleFrames(finals, (f) => f.season, finals[0].season), {
    colorOf: () => "var(--series-1)",
    emptyTicker: `Press play to start with the first final, ${finals[0].season}.`,
    ticker: (f) => [F.crest(f.champion), el("strong", null, `${f.season} · ${name(f.champion)}`),
      document.createTextNode(` · ${score(f)} against ${name(f.runnerUp)}`)],
    frameMs: 420,
  });

  /* ---------- Titles by club and country ---------- */

  const seasonsOf = (id) => finals.filter((f) => f.champion === id).map((f) => f.season);
  F.rankList(document.getElementById("clubs-list"), [...titles].sort((a, b) => b[1] - a[1] || (lost.get(a[0]) ?? 0) - (lost.get(b[0]) ?? 0))
    .map(([id, n]) => ({
      icon: F.crest(id), label: name(id), value: n, second: lost.get(id) ?? 0, color: "var(--series-1)",
      tip: (t) => {
        t.append(ttTitle(`${name(id)}: ${plural(n, "title")}`));
        t.append(ttNote(seasonsOf(id).join(" · ")));
        if (lost.get(id)) t.append(ttNote(`Lost ${plural(lost.get(id), "final")}: ${finals.filter((f) => f.runnerUp === id).map((f) => f.season).join(", ")}`));
      },
    })), ["Club", "Titles", "Lost finals"]);

  const byNation = d3.groups(finals, (f) => clubs[f.champion].country).sort((a, b) => b[1].length - a[1].length);
  F.rankList(document.getElementById("nations-list"), byNation.map(([code, list]) => ({
    icon: F.flag(code), label: countries[code]?.name ?? code, value: list.length, second: new Set(list.map((f) => f.champion)).size, color: "var(--series-2)",
    tip: (t) => {
      t.append(ttTitle(`${countries[code]?.name ?? code}: ${plural(list.length, "title")}`));
      d3.groups(list, (f) => f.champion).forEach(([id, v]) => t.append(ttRow("var(--series-2)", v.length, ` ${name(id)}`)));
    },
  })), ["Country", "Titles", "Clubs"]);

  /* ---------- Every final ---------- */

  const person = (p) => (p ? withFlag(p.name, p.nation) : document.createTextNode("–"));
  F.richTable(document.getElementById("finals-table"), [
    { label: "Season", render: (f) => f.season },
    { label: "Champion", render: (f) => F.clubLabel(f.champion) },
    { label: "Score", cls: "num strong", render: (f) => score(f) },
    { label: "Runner-up", render: (f) => F.clubLabel(f.runnerUp) },
    { label: "Host", cls: "hide-sm", render: (f) => f.host },
    { label: "Finals MVP", cls: "hide-sm", render: (f) => person(f.mvp) },
    { label: "Champion coach", cls: "hide-sm", render: (f) => person(f.coach) },
  ], finals.slice().reverse());

  /* ---------- All-time table ---------- */

  const at = raw.alltime;
  document.getElementById("alltime-lede").textContent =
    `Every club's games since the first Euroleague Basketball season, ${raw.alltimeFrom}, ranked by wins: ${at.length} clubs, through ${fmtDay(raw.gamesThrough)}.`;
  F.richTable(document.getElementById("alltime-table"), [
    { label: "#", cls: "num rank", render: (r) => String(at.indexOf(r) + 1) },
    { label: "Club", render: (r) => F.clubLabel(`code:${r.code}`) },
    { label: "Seasons", short: "S", cls: "num hide-sm", render: (r) => String(r.seasons) },
    { label: "Played", short: "P", cls: "num", render: (r) => String(r.pld) },
    { label: "W", cls: "num strong", render: (r) => String(r.w) },
    { label: "L", cls: "num", render: (r) => String(r.l) },
    { label: "Won", cls: "num", render: (r) => d3.format(".0%")(r.w / r.pld) },
    { label: "Points", cls: "num hide-sm", render: (r) => `${d3.format(",")(r.pf)}–${d3.format(",")(r.pa)}` },
    { label: "Titles", cls: "num", render: (r) => String(r.titles || "–") },
  ], at);

  /* ---------- Coaches and players ---------- */

  const people = (id, list) => F.rankList(document.getElementById(id), list.map((p) => ({
    icon: F.flag(p.nation), label: p.name, value: p.titles, second: p.finalsLost, color: id === "coaches-list" ? "var(--series-3)" : "var(--series-4)",
    tip: (t) => {
      t.append(ttTitle(`${p.name}: ${plural(p.titles, "title")}`));
      if (p.won.length) t.append(ttNote(`Won in ${p.won.join(", ")}`));
      if (p.finalsLost) t.append(ttNote(`Lost ${plural(p.finalsLost, "final")}`));
    },
  })), [id === "coaches-list" ? "Coach" : "Player", "Titles", "Lost finals"]);
  people("coaches-list", raw.coaches.filter((c) => c.titles >= 2));
  people("players-list", raw.players);

  /* ---------- Great rivalries ---------- */

  const COLOR = { a: "var(--team-a)", b: "var(--team-b)", d: "var(--draw)" };
  const parse = d3.utcParse("%Y-%m-%d");
  const fmtDate = d3.utcFormat("%-d %b %Y");
  let current = raw.rivalries[0];

  function split(root, parts) {
    root.replaceChildren();
    const total = d3.sum(parts, (p) => p.n);
    parts.forEach((p) => {
      if (!p.n) return;
      const seg = el("div");
      seg.style.setProperty("--c", p.color);
      seg.style.flex = String(p.n / total);
      root.append(seg);
    });
  }
  function applyColors() {
    const c = Viz.isDark() ? current.colors.dark : current.colors.light;
    document.body.style.setProperty("--team-a", c[0]);
    document.body.style.setProperty("--team-b", c[1]);
  }
  Viz.onThemeChange(() => applyColors());

  function wdlTable(rootId, rows, A, B, total) {
    const root = document.getElementById(rootId);
    root.replaceChildren();
    const table = el("table");
    const hrow = el("tr");
    const th = (text, cls) => {
      const c = el("th", cls);
      c.append(text);
      return c;
    };
    const teamHead = (team, c) => {
      const sp = el("span", "who");
      const i = el("i", "team-dot");
      i.style.setProperty("--c", c);
      sp.append(i, document.createTextNode(team.name));
      return sp;
    };
    const hasD = rows.some((x) => x.d) || total?.d;
    hrow.append(th(""), th("P", "num"), th(teamHead(A, COLOR.a), "num"), ...(hasD ? [th("D", "num")] : []), th(teamHead(B, COLOR.b), "num"), th("", "hide-sm"));
    table.append(hrow);
    const row = (label, x, cls) => {
      const tr = el("tr", cls);
      const bar = el("div", "wdl-bar");
      split(bar, [{ n: x.a, color: COLOR.a }, { n: x.d, color: COLOR.d }, { n: x.b, color: COLOR.b }]);
      const barCell = el("td", "hide-sm");
      barCell.append(bar);
      tr.append(el("td", null, label), el("td", "num", String(x.n)), el("td", `num${x.a > x.b ? " win" : ""}`, String(x.a)),
        ...(hasD ? [el("td", "num", String(x.d))] : []), el("td", `num${x.b > x.a ? " win" : ""}`, String(x.b)), barCell);
      table.append(tr);
    };
    rows.forEach((x) => row(x.comp, x, /euro/i.test(x.comp) ? "highlight" : ""));
    if (total) row("All", total, "total");
    root.append(table);
  }

  const PHASE_ORDER = ["Regular season", "Top 16", "Play-in", "Playoffs", "Final Four"];
  function rivalry(r) {
    current = r;
    applyColors();
    const [A, B] = r.teams;
    const games = r.games.map((g) => {
      const homeWon = g.hs > g.as;
      return { ...g, when: parse(g.date), winner: (g.home === "a") === homeWon ? "a" : "b" };
    });
    const rec = (list) => ({ n: list.length, a: list.filter((g) => g.winner === "a").length, d: 0, b: list.filter((g) => g.winner === "b").length });
    const t = rec(games);
    const head = document.getElementById("rv-versus");
    head.replaceChildren();
    const side = (team, wins, right) => {
      const sd = el("div", `rv-side${right ? " right" : ""}`);
      const txt = el("div");
      txt.append(el("div", "rv-name", team.name), el("div", "rv-wins", String(wins)), el("div", "rv-label", wins === 1 ? "win" : "wins"));
      sd.append(F.crest(team.id, "crest"), txt);
      return sd;
    };
    const mid = el("div", "rv-mid");
    mid.append(el("div", "rv-draws", String(t.n)), el("div", "rv-label", "EuroLeague games"));
    head.append(side(A, t.a), mid, side(B, t.b, true));
    head.setAttribute("aria-label", `${A.name} ${t.a} wins, ${B.name} ${t.b} wins in ${t.n} EuroLeague games`);
    split(document.getElementById("rv-split"), [{ n: t.a, color: COLOR.a }, { n: t.b, color: COLOR.b }]);
    const pts = (side) => d3.sum(games, (g) => (g.home === side ? g.hs : g.as));
    document.getElementById("rv-detail").replaceChildren(
      el("span", null, `${d3.format(",")(pts("a"))} points by ${A.name}`), el("span", null, `since ${games[0].season}`),
      el("span", null, `${d3.format(",")(pts("b"))} points by ${B.name}`));

    const phases = d3.groups(games, (g) => g.phase).sort((x, y) => PHASE_ORDER.indexOf(x[0]) - PHASE_ORDER.indexOf(y[0]))
      .map(([phase, list]) => ({ comp: phase, ...rec(list) }));
    wdlTable("phase-table", phases, A, B, t);
    const nameOf = (s) => (s === "a" ? A.name : B.name);
    document.getElementById("finals-note").textContent = r.finals.length
      ? `European finals between them (since 1958): ${r.finals.map((f) => `${f.season} ${nameOf(f.winner)}`).join(", ")}.`
      : "They have never met in a European final.";

    document.getElementById("allcomp-card").hidden = !r.total;
    if (r.total) {
      wdlTable("comp-table", r.comps, A, B, r.total);
      document.getElementById("rivalry-note").textContent = `Every competition, domestic and European, as ${r.source.label} counts them.`;
    }

    lead(games, A, B);
    const euro = games.slice().reverse();
    document.getElementById("euro-title").textContent = `Their ${plural(euro.length, "EuroLeague game")}, most recent first`;
    F.richTable(document.getElementById("euro-table"), [
      { label: "Date", render: (g) => fmtDate(g.when) },
      { label: "Stage", cls: "hide-sm", render: (g) => g.phase },
      { label: "Home", render: (g) => nameOf(g.home) },
      { label: "Score", cls: "num strong", render: (g) => `${g.hs}–${g.as}` },
      { label: "Away", render: (g) => nameOf(g.home === "a" ? "b" : "a") },
      { label: "Winner", render: (g) => nameOf(g.winner) },
    ], euro);
  }

  function lead(games, A, B) {
    let diff = 0;
    const pts = games.map((g) => ({ g, diff: (diff += g.winner === "a" ? 1 : -1) }));
    const maxA = d3.greatest(pts, (p) => p.diff), maxB = d3.least(pts, (p) => p.diff);
    const now = pts[pts.length - 1].diff;
    const leadText = (v) => (v > 0 ? `${A.name} +${v}` : v < 0 ? `${B.name} +${-v}` : "level");
    document.getElementById("lead-note").textContent =
      `${A.name} led by as many as ${Math.max(0, maxA.diff)}${maxA.diff > 0 ? ` (${maxA.g.date.slice(0, 4)})` : ""}; ` +
      `${B.name} by as many as ${Math.max(0, -maxB.diff)}${maxB.diff < 0 ? ` (${maxB.g.date.slice(0, 4)})` : ""}. Today: ${leadText(now)}. EuroLeague games only.`;
    Viz.legend("lead-legend", [{ label: `${A.name} ahead`, color: COLOR.a }, { label: `${B.name} ahead`, color: COLOR.b }]);
    const old = document.getElementById("lead-chart");
    const node = el("div", old.className);
    node.id = old.id;
    old.replaceWith(node);
    Viz.responsive(node, (width) => {
      const container = d3.select(node);
      container.selectAll("*").remove();
      const narrow = width < 560;
      const margin = { top: 20, right: 14, bottom: 26, left: narrow ? 34 : 40 };
      const height = narrow ? 240 : 300;
      const x = d3.scaleUtc().domain(d3.extent(pts, (p) => p.g.when)).range([margin.left, width - margin.right]);
      const ext = Math.max(4, d3.max(pts, (p) => Math.abs(p.diff)));
      const y = d3.scaleLinear().domain([-ext, ext]).nice().range([height - margin.bottom, margin.top]);
      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img")
        .attr("aria-label", `Head-to-head lead after each of ${pts.length} games. Today: ${leadText(now)}.`);
      const axis = svg.append("g").attr("class", "axis");
      y.ticks(narrow ? 5 : 7).forEach((v) => {
        axis.append("line").attr("class", v === 0 ? "baseline" : "gridline").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", y(v)).attr("y2", y(v));
        axis.append("text").attr("x", margin.left - 6).attr("y", y(v)).attr("dy", "0.32em").attr("text-anchor", "end").text(v ? `+${Math.abs(v)}` : "0");
      });
      x.ticks(narrow ? 5 : 10).forEach((t) => axis.append("text").attr("x", x(t)).attr("y", height - 6).attr("text-anchor", "middle").text(t.getUTCFullYear()));
      axis.append("text").attr("class", "label-muted").attr("x", margin.left + 6).attr("y", margin.top - 6).text(`↑ ${A.name} ahead`);
      axis.append("text").attr("class", "label-muted").attr("x", margin.left + 6).attr("y", height - margin.bottom - 6).text(`↓ ${B.name} ahead`);
      const step = [{ g: { when: pts[0].g.when }, diff: 0 }, ...pts];
      const area = (f) => d3.area().curve(d3.curveStepAfter).x((p) => x(p.g.when)).y0(y(0)).y1((p) => y(f(p.diff)));
      svg.append("path").attr("d", area((v) => Math.max(0, v))(step)).attr("fill", COLOR.a).attr("fill-opacity", 0.28);
      svg.append("path").attr("d", area((v) => Math.min(0, v))(step)).attr("fill", COLOR.b).attr("fill-opacity", 0.28);
      svg.append("path").attr("d", d3.line().curve(d3.curveStepAfter).x((p) => x(p.g.when)).y((p) => y(p.diff))(step))
        .attr("fill", "none").attr("stroke", "var(--ink-2)").attr("stroke-width", 2);
      const cross = svg.append("g").attr("pointer-events", "none").style("display", "none");
      cross.append("line").attr("class", "gridline").attr("y1", margin.top).attr("y2", height - margin.bottom);
      const cdot = cross.append("circle").attr("r", 5).attr("stroke", "var(--surface)").attr("stroke-width", 2);
      const bisect = d3.bisector((p) => p.g.when).center;
      const name2 = (sd) => (sd === "a" ? A.name : B.name);
      svg.append("rect").attr("x", margin.left).attr("y", margin.top).attr("width", width - margin.left - margin.right)
        .attr("height", height - margin.top - margin.bottom).attr("fill", "transparent")
        .on("pointermove pointerenter", (event) => {
          const p = pts[bisect(pts, x.invert(d3.pointer(event)[0]))];
          cross.style("display", null).attr("transform", `translate(${x(p.g.when)},0)`);
          cdot.attr("cy", y(p.diff)).attr("fill", p.g.winner === "a" ? COLOR.a : COLOR.b);
          Viz.showTip(event, (t) => {
            t.append(ttTitle(`${fmtDate(p.g.when)} · ${p.g.season} ${p.g.phase}`));
            t.append(ttRow(p.g.winner === "a" ? COLOR.a : COLOR.b, `${p.g.hs}–${p.g.as}`, ` ${name2(p.g.home)} at home`));
            t.append(ttNote(`After it: ${leadText(p.diff)}`));
          });
        })
        .on("pointerleave", () => {
          cross.style("display", "none");
          Viz.hideTip();
        });
    });
  }

  Viz.segmented("rivalry-tabs", raw.rivalries.map((r) => ({ key: r.id, label: `${r.teams[0].name} vs ${r.teams[1].name}` })), raw.rivalries[0].id,
    (k) => rivalry(raw.rivalries.find((r) => r.id === k)));
  rivalry(raw.rivalries[0]);

  /* ---------- Footer ---------- */

  const srcs = document.getElementById("rivalry-sources");
  raw.rivalries.filter((r) => r.source).forEach((r, i) => {
    const a = el("a", null, r.source.label.replace(/^English Wikipedia, /, ""));
    a.href = r.source.url;
    srcs.append(...(i ? [document.createTextNode(", "), a] : [a]));
  });
  document.getElementById("data-through").textContent = `Through the ${latest.season} final; games through ${fmtDay(raw.gamesThrough)}.`;
})();
