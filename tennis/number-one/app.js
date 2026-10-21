/* Tennis world No. 1: timeline, weeks over time, longest runs, every No. 1 and nations. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote } = Viz;
  const data = await d3.json(document.body.dataset.src);
  const NEUTRAL = "NEU";
  const nations = { ...data.nations, [NEUTRAL]: { name: "Neutral (no flag)", flag: null } };
  const F = Football({
    nationMode: true,
    clubs: Object.fromEntries(Object.entries(nations).map(([c, n]) => [c, { name: n.name, country: c, crest: null }])),
    countries: nations,
  });
  const PALETTE = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)", "#8b5cf6", "#e11d74", "#0ea5a4", "#a16207", "#64748b", "#16a34a"];
  // Nations get their own, deeper palette so the nation band doesn't read as the player band.
  const NATION_PALETTE = ["#1e40af", "#b91c1c", "#047857", "#b45309", "#6d28d9", "#be185d", "#0e7490", "#4d7c0f", "#7c2d12", "#334155"];
  const OTHER = "var(--axis)";
  const FROZEN = "var(--wash)";
  const parse = (s) => new Date(`${s}T00:00:00Z`);
  const dateText = (s) => parse(s).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  const nationName = (c) => nations[c]?.name ?? c;
  const who = (name, nation) => {
    const span = el("span", "club");
    span.append(F.flag(nation), document.createTextNode(name));
    return span;
  };
  const yearsText = (w) => `${(w / 52.18).toFixed(1)} years`;

  // One resize observer per chart; switching tour swaps the drawing function and redraws.
  const charts = {};
  function chart(id, draw) {
    if (charts[id]) {
      charts[id].draw = draw;
      charts[id].redraw();
    } else {
      charts[id] = { draw };
      charts[id].redraw = Viz.responsive(id, (width) => charts[id].draw(width));
    }
  }

  document.getElementById("sources").replaceChildren(
    ...data.meta.sources.flatMap((u, i) => {
      const a = el("a", null, decodeURIComponent(u.split("/wiki/")[1]).replace(/_/g, " "));
      a.href = u;
      return i ? [document.createTextNode(", "), a] : [a];
    }),
  );

  let tour = "atp";
  let S; // the tour's derived data
  function derive() {
    const spells = data.tours[tour].spells.map((s) => ({ ...s, nation: s.frozen ? null : s.nation ?? NEUTRAL, s: parse(s.start), e: new Date(parse(s.end).getTime() + 86400000) }));
    const held = spells.filter((s) => !s.frozen);
    const players = d3.rollups(held, (v) => ({
      name: v[0].name,
      nation: v[v.length - 1].nation,
      nations: [...new Set(v.map((s) => s.nation))],
      weeks: d3.sum(v, (s) => s.weeks),
      spells: v.length,
      longest: d3.greatest(v, (s) => s.weeks),
      first: v[0].start,
      last: v[v.length - 1].end,
      current: v.some((s) => s.current),
    }), (s) => s.name).map(([, p]) => p).sort((a, b) => b.weeks - a.weeks);
    const byNation = d3.rollups(held, (v) => ({
      code: v[0].nation,
      weeks: d3.sum(v, (s) => s.weeks),
      players: [...new Set(v.map((s) => s.name))],
      first: v[0].start,
    }), (s) => s.nation).map(([, n]) => n).sort((a, b) => b.weeks - a.weeks || a.first.localeCompare(b.first));
    const color = new Map(players.slice(0, PALETTE.length).map((p, i) => [p.name, PALETTE[i]]));
    const nationColor = new Map(byNation.slice(0, NATION_PALETTE.length).map((n, i) => [n.code, NATION_PALETTE[i]]));
    S = { spells, held, players, byNation, color, nationColor, start: spells[0].s, end: spells[spells.length - 1].e };
  }

  /* ---------- Stat tiles ---------- */

  function stats() {
    const top = S.players[0];
    const run = d3.greatest(S.held, (s) => s.weeks);
    const flagged = S.byNation.filter((n) => n.code !== NEUTRAL);
    document.getElementById("stats").replaceChildren();
    F.statTiles("stats", [
      { label: "Players at No. 1", value: String(S.players.length), detail: `since ${dateText(data.tours[tour].spells[0].start)}` },
      { label: "Nations", value: String(flagged.length), detail: S.byNation.length > flagged.length ? "plus players under no flag" : "with a No. 1" },
      { label: "Most weeks", value: String(top.weeks), detail: top.name, club: top.nation },
      { label: "Longest run", value: String(run.weeks), detail: `${run.name}, ${run.start.slice(0, 4)}–${run.end.slice(0, 4)}`, club: run.nation },
    ]);
  }

  /* ---------- Timeline ribbon ---------- */

  function spellTip(s) {
    const t = el("div");
    if (s.frozen) {
      t.append(ttTitle("Rankings frozen"), el("div", null, `${dateText(s.start)} – ${dateText(s.end)}`), ttNote("COVID-19 pandemic: no weeks counted"));
      return t;
    }
    t.append(ttTitle(s.name));
    t.append(el("div", null, `${dateText(s.start)} – ${s.current ? "today" : dateText(s.end)}`));
    t.append(el("div", null, `${s.weeks} week${s.weeks === 1 ? "" : "s"} in a row · ${nationName(s.nation)}`));
    return t;
  }

  function ribbon() {
    chart("ribbon", (width) => {
      const box = d3.select("#ribbon");
      box.selectAll("*").remove();
      const narrow = width < 600;
      const margin = { top: 4, right: 4, bottom: 22, left: narrow ? 54 : 70 };
      const band = narrow ? 44 : 56;
      const gap = 8;
      const height = margin.top + band * 2 + gap + margin.bottom;
      const x = d3.scaleUtc().domain([S.start, S.end]).range([margin.left, width - margin.right]);
      const svg = box.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("width", width).attr("height", height);
      [["Player", 0], ["Nation", band + gap]].forEach(([label, y]) => {
        svg.append("text").attr("class", "band-label").attr("x", margin.left - 8).attr("y", margin.top + y + band / 2 + 4).attr("text-anchor", "end").text(label);
      });
      const draw = (y, fill) => {
        const r = svg.append("g").selectAll("rect").data(S.spells).join("rect")
          .attr("x", (s) => x(s.s)).attr("width", (s) => Math.max(0.6, x(s.e) - x(s.s)))
          .attr("y", margin.top + y).attr("height", band).attr("fill", fill);
        Viz.tooltipOn(r, spellTip);
      };
      draw(0, (s) => (s.frozen ? FROZEN : S.color.get(s.name) ?? OTHER));
      draw(band + gap, (s) => (s.frozen ? FROZEN : S.nationColor.get(s.nation) ?? OTHER));
      const ticks = x.ticks(narrow ? 5 : 10);
      svg.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", (d) => x(d)).attr("y", height - 6)
        .attr("text-anchor", "middle").text((d) => d.getUTCFullYear());
    });
    Viz.legend("ribbon-legend", [...[...S.color].map(([name, color]) => ({ label: name, color })), { label: "Others", color: OTHER }, { label: "Rankings frozen", color: FROZEN }]);
    Viz.legend("nation-legend", [...[...S.nationColor].map(([code, color]) => ({ label: nationName(code), color })), ...(S.byNation.length > S.nationColor.size ? [{ label: "Other nations", color: OTHER }] : [])]);
  }

  /* ---------- Players and nations that have reached No. 1 ---------- */

  function countChart() {
    const seenP = new Set();
    const seenN = new Set();
    const steps = [];
    S.held.forEach((s) => {
      const newP = !seenP.has(s.name);
      const newN = s.nation !== NEUTRAL && !seenN.has(s.nation);
      seenP.add(s.name);
      if (s.nation !== NEUTRAL) seenN.add(s.nation);
      if (newP || newN) steps.push({ d: s.s, players: seenP.size, nations: seenN.size, who: newP ? s.name : null, nation: newN ? s.nation : null });
    });
    steps.push({ d: S.end, players: seenP.size, nations: seenN.size });
    const lines = [{ key: "players", label: "Players", color: "var(--sport)" }, { key: "nations", label: "Nations", color: "var(--series-2)" }];
    Viz.legend("count-legend", lines, "line");
    chart("count-chart", (width) => {
      const box = d3.select("#count-chart");
      box.selectAll("*").remove();
      const narrow = width < 600;
      const height = narrow ? 220 : 260;
      const margin = { top: 12, right: 34, bottom: 24, left: 30 };
      const x = d3.scaleUtc().domain([S.start, S.end]).range([margin.left, width - margin.right]);
      const y = d3.scaleLinear().domain([0, seenP.size + 1]).nice().range([height - margin.bottom, margin.top]);
      const svg = box.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("width", width).attr("height", height);
      const yt = y.ticks(5);
      svg.append("g").selectAll("line").data(yt).join("line").attr("class", "gridline").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", y).attr("y2", y);
      svg.append("g").selectAll("text").data(yt).join("text").attr("class", "tick-label").attr("x", margin.left - 6).attr("y", (d) => y(d) + 4).attr("text-anchor", "end").text((d) => d);
      svg.append("g").selectAll("text").data(x.ticks(narrow ? 5 : 10)).join("text").attr("class", "tick-label").attr("x", x).attr("y", height - 6).attr("text-anchor", "middle").text((d) => d.getUTCFullYear());
      lines.forEach((l) => {
        svg.append("path").datum(steps).attr("fill", "none").attr("stroke", l.color).attr("stroke-width", 2.5)
          .attr("d", d3.line().curve(d3.curveStepAfter).x((p) => x(p.d)).y((p) => y(p[l.key])));
        svg.append("text").attr("class", "line-end").attr("x", width - margin.right + 6).attr("y", y(steps[steps.length - 1][l.key]) + 4).attr("fill", l.color).text(steps[steps.length - 1][l.key]);
      });
      const dots = svg.append("g").selectAll("circle").data(steps.filter((p) => p.who)).join("circle")
        .attr("cx", (p) => x(p.d)).attr("cy", (p) => y(p.players)).attr("r", 4).attr("fill", "var(--sport)").attr("stroke", "var(--surface)").attr("stroke-width", 1.5);
      Viz.tooltipOn(dots, (p) => {
        const t = el("div");
        t.append(ttTitle(`No. ${p.players}: ${p.who}`), el("div", null, dateText(p.d.toISOString().slice(0, 10))));
        if (p.nation) t.append(ttNote(`First No. 1 for ${nationName(p.nation)}`));
        return t;
      });
    });
  }

  /* ---------- Weeks at No. 1 over time ---------- */

  let raceBy = "players";
  function race() {
    const groups = raceBy === "players"
      ? S.players.slice(0, 8).map((p) => ({ key: p.name, label: p.name.split(" ").slice(-1)[0], full: p.name, color: S.color.get(p.name), of: (s) => s.name === p.name }))
      : S.byNation.slice(0, 8).map((n) => ({ key: n.code, label: nationName(n.code), full: nationName(n.code), color: S.nationColor.get(n.code), of: (s) => s.nation === n.code }));
    // Cumulative weeks as a series of points at the start and end of every spell.
    const series = groups.map((g) => {
      let total = 0;
      const pts = [{ d: S.start, v: 0 }];
      S.held.filter(g.of).forEach((s) => {
        pts.push({ d: s.s, v: total });
        total += s.weeks;
        pts.push({ d: s.e, v: total, s });
      });
      pts.push({ d: S.end, v: total });
      return { ...g, pts, total };
    });
    chart("race-chart", (width) => {
      const box = d3.select("#race-chart");
      box.selectAll("*").remove();
      const narrow = width < 600;
      const height = narrow ? 300 : 380;
      const margin = { top: 12, right: narrow ? 70 : 110, bottom: 24, left: 36 };
      const x = d3.scaleUtc().domain([S.start, S.end]).range([margin.left, width - margin.right]);
      const y = d3.scaleLinear().domain([0, d3.max(series, (s) => s.total)]).nice().range([height - margin.bottom, margin.top]);
      const svg = box.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("width", width).attr("height", height);
      const yt = y.ticks(6);
      svg.append("g").selectAll("line").data(yt).join("line").attr("class", "gridline").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", y).attr("y2", y);
      svg.append("g").selectAll("text").data(yt).join("text").attr("class", "tick-label").attr("x", margin.left - 6).attr("y", (d) => y(d) + 4).attr("text-anchor", "end").text((d) => d);
      svg.append("g").selectAll("text").data(x.ticks(narrow ? 5 : 10)).join("text").attr("class", "tick-label").attr("x", x).attr("y", height - 6).attr("text-anchor", "middle").text((d) => d.getUTCFullYear());
      const line = d3.line().x((p) => x(p.d)).y((p) => y(p.v));
      series.forEach((s) => {
        const path = svg.append("path").datum(s.pts).attr("class", "race-line").attr("fill", "none").attr("stroke", s.color).attr("stroke-width", 2.5).attr("d", line);
        Viz.tooltipOn(path, () => {
          const t = el("div");
          t.append(ttTitle(s.full), el("div", null, `${s.total} weeks at No. 1`));
          return t;
        });
      });
      // End labels, nudged apart so they don't overlap.
      const labels = series.map((s) => ({ s, y: y(s.total) })).sort((a, b) => a.y - b.y);
      for (let i = 1; i < labels.length; i++) labels[i].y = Math.max(labels[i].y, labels[i - 1].y + 13);
      svg.append("g").selectAll("text").data(labels).join("text").attr("class", "line-end").attr("x", width - margin.right + 6).attr("y", (l) => l.y + 4)
        .attr("fill", (l) => l.s.color).text((l) => `${l.s.label} ${l.s.total}`);
    });
  }
  Viz.segmented("race-by", [{ key: "players", label: "Players" }, { key: "nations", label: "Nations" }], raceBy, (k) => {
    raceBy = k;
    race();
  });

  /* ---------- Longest runs ---------- */

  let streakMode = "all";
  function streaks() {
    const runs = streakMode === "all" ? S.held.slice() : S.players.map((p) => p.longest);
    const rows = runs.sort((a, b) => b.weeks - a.weeks || a.start.localeCompare(b.start)).slice(0, 20).map((s) => ({
      icon: F.flag(s.nation),
      label: s.name,
      value: s.weeks,
      second: `${s.start.slice(0, 4)}–${s.current ? "now" : s.end.slice(0, 4)}`,
      color: S.color.get(s.name) ?? "var(--ink-muted)",
      tip: () => spellTip(s),
    }));
    F.rankList(document.getElementById("streak-list"), rows, ["Player", "Weeks", "Years"]);
  }
  Viz.segmented("streak-mode", [{ key: "all", label: "Every run" }, { key: "best", label: "Each player's best" }], streakMode, (k) => {
    streakMode = k;
    streaks();
  });

  /* ---------- Every No. 1 ---------- */

  function players() {
    const rows = S.players;
    F.richTable(document.getElementById("player-table"), [
      { label: "#", cls: "num rank", render: (p) => String(rows.indexOf(p) + 1) },
      { label: "Player", render: (p) => {
        const span = el("span", "club");
        p.nations.forEach((n) => span.append(F.flag(n)));
        span.append(document.createTextNode(p.name + (p.current ? " (current)" : "")));
        return span;
      } },
      { label: "Weeks", short: "Wks", cls: "num strong", render: (p) => String(p.weeks) },
      { label: "Years", cls: "num hide-sm", render: (p) => yearsText(p.weeks).replace(" years", "") },
      { label: "Spells", cls: "num", render: (p) => String(p.spells) },
      { label: "Longest run", short: "Best", cls: "num", render: (p) => String(p.longest.weeks) },
      { label: "First week", cls: "years hide-sm", render: (p) => dateText(p.first) },
      { label: "Last week", cls: "years hide-sm", render: (p) => (p.current ? "current" : dateText(p.last)) },
    ], rows);
  }

  /* ---------- Nations ---------- */

  let nationMeasure = "weeks";
  function nationList() {
    const rows = S.byNation.slice().sort((a, b) => (nationMeasure === "weeks" ? b.weeks - a.weeks : b.players.length - a.players.length || b.weeks - a.weeks))
      .map((n) => ({
        icon: F.flag(n.code),
        label: nationName(n.code),
        value: nationMeasure === "weeks" ? n.weeks : n.players.length,
        second: nationMeasure === "weeks" ? `${n.players.length} player${n.players.length === 1 ? "" : "s"}` : `${n.weeks} wk`,
        color: S.nationColor.get(n.code) ?? "var(--ink-muted)",
        tip: () => {
          const t = el("div");
          t.append(ttTitle(nationName(n.code)), el("div", null, `${n.weeks} weeks at No. 1 (${yearsText(n.weeks)})`));
          n.players.forEach((name) => {
            const w = d3.sum(S.held.filter((s) => s.name === name && s.nation === n.code), (s) => s.weeks);
            t.append(Viz.ttRow(S.color.get(name) ?? "var(--ink-muted)", w, name));
          });
          return t;
        },
      }));
    F.rankList(document.getElementById("nation-list"), rows, ["Nation", nationMeasure === "weeks" ? "Weeks" : "Players", nationMeasure === "weeks" ? "Players" : "Weeks"]);
  }
  Viz.segmented("nation-measure", [{ key: "weeks", label: "Weeks at No. 1" }, { key: "players", label: "Players" }], nationMeasure, (k) => {
    nationMeasure = k;
    nationList();
  });

  const renderAll = () => {
    derive();
    [stats, ribbon, countChart, race, streaks, players, nationList].forEach((f) => f());
  };
  Viz.segmented("tour", [{ key: "atp", label: "Men (ATP)" }, { key: "wta", label: "Women (WTA)" }], tour, (k) => {
    tour = k;
    renderAll();
  });
  renderAll();
})();
