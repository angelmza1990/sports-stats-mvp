/* League balance: how evenly twenty national leagues have shared their titles. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote, ttRow } = Viz;
  const data = await d3.json(document.body.dataset.src);
  const F = Football(data);
  const { clubName } = F;
  const leagues = data.leagues;
  const NOW = new Date().getFullYear();
  const pct = (x) => `${Math.round(x * 100)}%`;
  const fmt1 = d3.format(".1f");

  /* ---------- Measures ---------- */

  function measures(titles) {
    const counts = d3.rollups(titles, (v) => v.length, (t) => t[1]).sort((a, b) => b[1] - a[1]);
    const n = titles.length;
    const hhi = d3.sum(counts, ([, c]) => (c / n) ** 2);
    return {
      n,
      counts,
      distinct: counts.length,
      eff: n ? 1 / hhi : 0,
      top1: n ? counts[0][1] / n : 0,
      top2: n ? (counts[0][1] + (counts[1]?.[1] ?? 0)) / n : 0,
    };
  }

  // Seasons in order, each with its champions (a shared season has two).
  const seasonsOf = (l) => d3.groups(l.titles, (t) => t[2]).map(([season, list]) => ({ season, year: list[0][0], champs: list.map((t) => t[1]) }));

  function streaksOf(l) {
    const out = [];
    const run = new Map();
    let prev = new Set();
    for (const s of seasonsOf(l)) {
      const next = new Map();
      for (const c of s.champs) {
        const r = prev.has(c) ? run.get(c) : { club: c, league: l, n: 0, from: s.season, fromYear: s.year };
        r.n += 1;
        r.to = s.season;
        next.set(c, r);
        if (!prev.has(c)) out.push(r);
      }
      prev = new Set(s.champs);
      run.clear();
      next.forEach((v, k) => run.set(k, v));
    }
    return out;
  }

  const streaks = leagues.flatMap(streaksOf);
  const longestOf = new Map(leagues.map((l) => [l, d3.greatest(streaks.filter((s) => s.league === l), (s) => s.n)]));

  function newcomerOf(l) {
    const seen = new Set();
    let last = null;
    for (const t of l.titles) {
      if (!seen.has(t[1])) last = t;
      seen.add(t[1]);
    }
    return last;
  }

  const all = new Map(leagues.map((l) => [l, measures(l.titles)]));
  const leagueLabel = (l) => {
    const span = el("span", "club");
    span.append(F.flag(l.country), document.createTextNode(l.label));
    return span;
  };

  /* ---------- Stat tiles ---------- */

  const mostEven = d3.greatest(leagues, (l) => all.get(l).eff);
  const mostTop2 = d3.greatest(leagues, (l) => all.get(l).top2);
  const longest = d3.greatest(streaks, (s) => s.n);
  F.statTiles("stats", [
    { label: "Titles compared", value: String(d3.sum(leagues, (l) => l.titles.length)), detail: `${leagues.length} leagues, ${Object.keys(data.clubs).length} different champions` },
    { label: "Most even league", value: fmt1(all.get(mostEven).eff), detail: `${mostEven.label}: effective champions` },
    { label: "Most shared by two", value: pct(all.get(mostTop2).top2), detail: `${mostTop2.label}: ${all.get(mostTop2).counts.slice(0, 2).map(([c]) => clubName(c)).join(" and ")}` },
    { label: "Longest reign", value: String(longest.n), detail: `${clubName(longest.club)} (${longest.league.label}), ${longest.from} to ${longest.to}`, club: longest.club },
  ]);

  /* ---------- Ranking ---------- */

  const METRICS = [
    { key: "eff", label: "Effective champions", head: "Effective", note: "Higher is more even.", value: (m) => +fmt1(m.eff), text: (m) => fmt1(m.eff) },
    { key: "top2", label: "Top two's share", head: "Top two", note: "The share of the titles won by the league's two most successful clubs. Higher is more concentrated.", value: (m) => Math.round(m.top2 * 100), text: (m) => pct(m.top2) },
    { key: "distinct", label: "Different champions", head: "Clubs", note: "How many clubs have won the league at least once.", value: (m) => m.distinct, text: (m) => String(m.distinct) },
  ];
  const PERIODS = [
    { key: "all", label: "All time", from: -Infinity },
    { key: "1990", label: "Since 1990", from: 1990 },
    { key: "2010", label: "Since 2010", from: 2010 },
  ];
  const state = { metric: "eff", period: "all" };

  function renderRanking() {
    const metric = METRICS.find((m) => m.key === state.metric);
    const period = PERIODS.find((p) => p.key === state.period);
    document.getElementById("metric-note").textContent = metric.note +
      (period.from > 0 ? ` Titles won in ${period.from} or later.` : "");
    const rows = leagues.map((l) => ({ l, m: measures(l.titles.filter((t) => t[0] >= period.from)) }))
      .filter((r) => r.m.n)
      .sort((a, b) => metric.value(b.m) - metric.value(a.m) || d3.ascending(a.l.label, b.l.label));
    F.rankList(document.getElementById("ranking-list"), rows.map(({ l, m }) => ({
      icon: F.flag(l.country),
      label: l.label,
      value: metric.value(m),
      second: m.n,
      color: "var(--series-1)",
      tip: (t) => {
        t.append(ttTitle(`${l.label} · ${l.competition}`),
          ttNote(`${m.n} titles · ${m.distinct} clubs · ${fmt1(m.eff)} effective · top two ${pct(m.top2)}`));
        m.counts.slice(0, 4).forEach(([c, k]) => t.append(ttRow("var(--series-1)", k, ` ${clubName(c)}`)));
      },
    })), ["League", metric.head, "Titles"]);
    // rankList prints the raw value: show percentages with their sign.
    if (metric.key === "top2") document.querySelectorAll("#ranking-list .rank-row .num.strong").forEach((n) => (n.textContent += "%"));
  }
  Viz.segmented("metric-tabs", METRICS, state.metric, (k) => { state.metric = k; renderRanking(); });
  Viz.segmented("period-tabs", PERIODS, state.period, (k) => { state.period = k; renderRanking(); });
  renderRanking();

  /* ---------- Decade heatmap ---------- */

  const RAMP = () => (Viz.isDark() ? ["#1f2c3d", "#9cc6ff"] : ["#e3edf9", "#0f3f7c"]);
  const MIN_TITLES = 4; // a decade with fewer titles in a league is left blank
  const decades = d3.range(Math.floor(d3.min(leagues, (l) => l.titles[0][0]) / 10) * 10, NOW + 1, 10);
  const cells = leagues.flatMap((l) => decades.map((d) => {
    const list = l.titles.filter((t) => t[0] >= d && t[0] < d + 10);
    return { l, d, list, m: measures(list) };
  }));

  function renderKey() {
    const [lo, hi] = RAMP();
    const key = document.getElementById("heat-key");
    const ramp = el("span", "ramp");
    ramp.style.background = `linear-gradient(90deg, ${lo}, ${hi})`;
    key.replaceChildren(el("span", null, "Shared"), ramp, el("span", null, "Two clubs won them all"));
  }

  function renderHeat(width) {
    const root = document.getElementById("heat-chart");
    const [lo, hi] = RAMP();
    const color = d3.scaleLinear().domain([0.2, 1]).range([lo, hi]).interpolate(d3.interpolateLab).clamp(true);
    const narrow = width < 640;
    const labelW = narrow ? 92 : 120;
    const top = 22;
    const cw = (width - labelW) / decades.length;
    const ch = narrow ? 22 : 26;
    const svg = d3.create("svg").attr("viewBox", `0 0 ${width} ${top + ch * leagues.length}`).attr("role", "img")
      .attr("aria-label", "Top two clubs' share of the titles in each league and decade");
    svg.append("g").attr("class", "axis").selectAll("text").data(decades).join("text")
      .attr("x", (d, i) => labelW + cw * i + cw / 2).attr("y", 12).attr("text-anchor", "middle")
      .text((d, i) => (narrow ? (i % 2 ? "" : `'${String(d).slice(2)}`) : `${d}s`));
    svg.append("g").selectAll("text").data(leagues).join("text").attr("class", "row-label")
      .attr("x", 0).attr("y", (l, i) => top + ch * i + ch / 2 + 4).text((l) => l.label);
    const g = svg.append("g").selectAll("g").data(cells.filter((c) => c.m.n >= MIN_TITLES)).join("g").attr("class", "heat-cell")
      .attr("transform", (c) => `translate(${labelW + cw * decades.indexOf(c.d)},${top + ch * leagues.indexOf(c.l)})`);
    g.append("rect").attr("x", 1).attr("y", 1).attr("width", cw - 2).attr("height", ch - 2).attr("rx", 3)
      .attr("fill", (c) => color(c.m.top2));
    if (cw >= 34) {
      g.append("text").attr("class", "heat-label").attr("x", cw / 2).attr("y", ch / 2 + 4).attr("text-anchor", "middle")
        .attr("fill", (c) => (d3.lab(color(c.m.top2)).l < 55 ? "#fff" : "#0b0b0b")).text((c) => Math.round(c.m.top2 * 100));
    }
    Viz.tooltipOn(g, (t, c) => {
      t.append(ttTitle(`${c.l.label}, ${c.d}s`), ttNote(`${c.m.n} titles · ${c.m.distinct} different champions · top two ${pct(c.m.top2)}`));
      c.m.counts.slice(0, 5).forEach(([club, k]) => t.append(ttRow(color(c.m.top2), k, ` ${clubName(club)}`)));
    });
    root.replaceChildren(svg.node());
  }
  renderKey();
  const rerenderHeat = Viz.responsive("heat-chart", renderHeat);

  /* ---------- Trend: effective champions over the last 20 titles ---------- */

  const WINDOW = 20;
  const SLOTS = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)"];
  const series = new Map(leagues.map((l) => {
    const perYear = d3.rollup(l.titles, (v) => v.length, (t) => t[0]);
    const seenInYear = new Map();
    const pts = [];
    l.titles.forEach((t, i) => {
      const k = seenInYear.get(t[0]) ?? 0;
      seenInYear.set(t[0], k + 1);
      if (i >= WINDOW - 1) {
        const m = measures(l.titles.slice(i - WINDOW + 1, i + 1));
        pts.push({ x: t[0] + (k + 1) / perYear.get(t[0]) - 0.5, season: t[2], eff: m.eff, m });
      }
    });
    return [l, pts];
  }));
  const picked = new Map(); // league -> slot index, kept while the league stays selected
  ["premier-league", "la-liga", "argentine-primera", "primeira-liga"].forEach((k, i) => picked.set(leagues.find((l) => l.key === k), i));

  const chips = document.getElementById("trend-chips");
  leagues.forEach((l) => {
    const b = el("button");
    b.type = "button";
    b.append(F.flag(l.country), document.createTextNode(l.label));
    b.addEventListener("click", () => {
      if (picked.has(l)) picked.delete(l);
      else {
        if (picked.size >= SLOTS.length) picked.delete(picked.keys().next().value);
        const used = new Set(picked.values());
        picked.set(l, SLOTS.findIndex((_, i) => !used.has(i)));
      }
      syncChips();
      rerenderTrend();
    });
    l._chip = b;
    chips.append(b);
  });
  function syncChips() {
    leagues.forEach((l) => {
      l._chip.setAttribute("aria-pressed", String(picked.has(l)));
      if (picked.has(l)) l._chip.style.setProperty("--c", SLOTS[picked.get(l)]);
    });
    Viz.legend("trend-legend", [...picked].sort((a, b) => a[1] - b[1]).map(([l, s]) => ({ label: l.label, color: SLOTS[s] })), "line");
  }
  syncChips();

  function renderTrend(width) {
    const root = document.getElementById("trend-chart");
    const chosen = [...picked].sort((a, b) => a[1] - b[1]);
    const height = width < 640 ? 260 : 340;
    const m = { t: 10, r: width < 640 ? 12 : 90, b: 26, l: 30 };
    const pts = chosen.flatMap(([l]) => series.get(l));
    if (!pts.length) {
      root.replaceChildren(el("p", "chart-note", "Pick a league above."));
      return;
    }
    const x = d3.scaleLinear().domain(d3.extent(pts, (p) => p.x)).range([m.l, width - m.r]);
    const y = d3.scaleLinear().domain([1, Math.max(8, d3.max(pts, (p) => p.eff))]).nice().range([height - m.b, m.t]);
    const svg = d3.create("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img")
      .attr("aria-label", `Effective number of champions over the last ${WINDOW} titles`);
    const yt = y.ticks(5);
    svg.append("g").selectAll("line").data(yt).join("line").attr("class", "gridline")
      .attr("x1", m.l).attr("x2", width - m.r).attr("y1", y).attr("y2", y);
    svg.append("g").attr("class", "axis").selectAll("text").data(yt).join("text")
      .attr("x", m.l - 6).attr("y", (d) => y(d) + 4).attr("text-anchor", "end").text((d) => d);
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${height - m.b})`)
      .call(d3.axisBottom(x).ticks(width < 640 ? 5 : 10).tickFormat(d3.format("d")).tickSize(0).tickPadding(8))
      .call((g) => g.select(".domain").attr("class", "baseline"));
    const line = d3.line().x((p) => x(p.x)).y((p) => y(p.eff));
    chosen.forEach(([l, s]) => {
      const p = series.get(l);
      svg.append("path").attr("class", "trend-line").attr("stroke", SLOTS[s]).attr("d", line(p));
      if (width >= 640) {
        const last = p[p.length - 1];
        svg.append("text").attr("class", "label-muted").attr("x", x(last.x) + 6).attr("y", y(last.eff) + 4).text(l.label);
      }
    });
    // Crosshair: every chosen league's value at the hovered year.
    const hair = svg.append("line").attr("class", "crosshair").attr("y1", m.t).attr("y2", height - m.b).style("display", "none");
    const dots = svg.append("g");
    svg.append("rect").attr("x", m.l).attr("y", m.t).attr("width", width - m.l - m.r).attr("height", height - m.t - m.b)
      .attr("fill", "transparent")
      .on("pointermove", (event) => {
        const xv = x.invert(d3.pointer(event)[0]);
        const at = chosen.map(([l, s]) => {
          const p = series.get(l);
          const i = d3.bisector((q) => q.x).right(p, xv) - 1;
          return { l, s, p: p[Math.max(0, i)], inRange: i >= 0 };
        }).filter((a) => a.inRange);
        hair.style("display", null).attr("x1", x(xv)).attr("x2", x(xv));
        dots.selectAll("circle").data(at).join("circle").attr("class", "trend-dot").attr("r", 4)
          .attr("cx", (a) => x(a.p.x)).attr("cy", (a) => y(a.p.eff)).attr("fill", (a) => SLOTS[a.s]);
        Viz.showTip(event, (t) => {
          t.append(ttTitle(String(Math.floor(xv + 0.5))));
          at.sort((a, b) => b.p.eff - a.p.eff).forEach((a) => {
            t.append(ttRow(SLOTS[a.s], fmt1(a.p.eff), ` ${a.l.label}, last ${WINDOW} titles to ${a.p.season}`));
          });
          if (at.length === 1) t.append(ttNote(at[0].p.m.counts.slice(0, 3).map(([c, k]) => `${clubName(c)} ${k}`).join(" · ")));
        });
      })
      .on("pointerleave", () => {
        hair.style("display", "none");
        dots.selectAll("circle").remove();
        Viz.hideTip();
      });
    root.replaceChildren(svg.node());
  }
  const rerenderTrend = Viz.responsive("trend-chart", renderTrend);

  /* ---------- Streaks ---------- */

  const topStreaks = streaks.filter((s) => s.n >= 4).sort((a, b) => b.n - a.n || a.fromYear - b.fromYear).slice(0, 25);
  F.richTable(document.getElementById("streaks-table"), [
    { label: "In a row", cls: "num strong", render: (s) => el("span", "streak-n", String(s.n)) },
    { label: "Club", render: (s) => F.clubLabel(s.club) },
    { label: "League", cls: "hide-sm", render: (s) => leagueLabel(s.league) },
    { label: "Seasons", render: (s) => (s.from === s.to ? s.from : `${s.from} to ${s.to}`) },
  ], topStreaks);

  /* ---------- Dominant clubs and newcomers ---------- */

  F.rankList(document.getElementById("dominant-list"), leagues.map((l) => ({ l, m: all.get(l) }))
    .sort((a, b) => b.m.top1 - a.m.top1)
    .map(({ l, m }) => ({
      icon: F.crest(m.counts[0][0]),
      label: `${clubName(m.counts[0][0])} · ${l.label}`,
      value: Math.round(m.top1 * 100),
      second: `${m.counts[0][1]} of ${m.n}`,
      color: "var(--series-1)",
    })), ["Club", "Share", "Titles"]);
  document.querySelectorAll("#dominant-list .rank-row .num.strong").forEach((n) => (n.textContent += "%"));

  const newcomers = leagues.map((l) => ({ l, t: newcomerOf(l) })).sort((a, b) => b.t[0] - a.t[0] || d3.ascending(a.l.label, b.l.label));
  F.richTable(document.getElementById("newcomers-table"), [
    { label: "League", render: (r) => leagueLabel(r.l) },
    { label: "First-time champion", render: (r) => F.withSub(F.clubLabel(r.t[1]), r.t[2]) },
    { label: "Years ago", cls: "num", render: (r) => (NOW - r.t[0] <= 0 ? "This year" : String(NOW - r.t[0])) },
  ], newcomers);

  /* ---------- Summary table ---------- */

  F.richTable(document.getElementById("summary-table"), [
    { label: "League", render: (l) => F.withSub(leagueLabel(l), `${l.titles[0][2]} to ${l.titles[l.titles.length - 1][2]}`) },
    { label: "Titles", cls: "num", render: (l) => String(all.get(l).n) },
    { label: "Clubs", cls: "num", render: (l) => String(all.get(l).distinct) },
    { label: "Effective", cls: "num strong", render: (l) => fmt1(all.get(l).eff) },
    { label: "Top club", cls: "hide-sm", render: (l) => F.withSub(F.clubLabel(all.get(l).counts[0][0]), `${all.get(l).counts[0][1]} titles, ${pct(all.get(l).top1)}`) },
    { label: "Top two", cls: "num", render: (l) => pct(all.get(l).top2) },
    { label: "Longest run", cls: "hide-sm", render: (l) => F.withSub(F.clubLabel(longestOf.get(l).club), `${longestOf.get(l).n} in a row from ${longestOf.get(l).from}`) },
  ], [...leagues].sort((a, b) => all.get(b).eff - all.get(a).eff));

  const links = document.getElementById("league-links");
  leagues.forEach((l, i) => {
    const a = el("a", null, l.label);
    a.href = `../${l.key}/`;
    links.append(a, document.createTextNode(i < leagues.length - 2 ? ", " : i === leagues.length - 2 ? " and " : ""));
  });

  /* ---------- Amateur and professional eras ---------- */

  (function professional() {
    const TREAT = {
      all: "Amateur titles count",
      "pro-only": "Only professional titles count",
      debated: "Debated",
      none: "No amateur national league",
    };
    const rows = leagues.map((l) => {
      const p = l.professional;
      const isAmateur = (t) => t[0] < p.since || l.amateurSeasons.includes(t[2]);
      const amateur = l.titles.filter(isAmateur);
      const pro = l.titles.filter((t) => !isAmateur(t));
      return { l, p, amateur, pro, top: measures(l.titles).counts[0], topPro: pro.length ? measures(pro).counts[0] : null };
    }).sort((a, b) => a.p.since - b.p.since || d3.ascending(a.l.label, b.l.label));
    const n = (k) => rows.filter((r) => r.p.treatment === k).length;
    document.getElementById("pro-lede").textContent =
      `When football turned professional in each league, and whether the titles from before still count. ${n("all")} of the ${rows.length} leagues count their amateur titles like the rest, ${n("pro-only")} count only the professional ones, ${n("debated")} are debated, and ${n("none")} had no amateur national league.`;
    const leader = (c) => (c ? F.withSub(document.createTextNode(clubName(c[0])), `${c[1]} titles`) : "–");
    function render(filter) {
      const list = rows.filter((r) => filter === "every" || r.p.treatment === filter);
      F.richTable(document.getElementById("pro-table"), [
        { label: "League", render: (r) => F.withSub(leagueLabel(r.l), r.l.competition) },
        { label: "Professional since", short: "Pro", cls: "num strong", render: (r) => String(r.p.since) },
        { label: "Amateur titles", short: "Am.", cls: "num", render: (r) => (r.amateur.length ? F.withSub(document.createTextNode(String(r.amateur.length)), `${r.amateur[0][0]}–${r.amateur[r.amateur.length - 1][0]}`) : "–") },
        { label: "How they count", render: (r) => F.withSub(el("strong", null, TREAT[r.p.treatment]), `${r.p.milestone}. ${r.p.note}`) },
        { label: "Most titles, all eras", cls: "hide-sm", render: (r) => leader(r.top) },
        { label: "Professional era only", cls: "hide-sm", render: (r) => (r.amateur.length ? leader(r.topPro) : "same") },
      ], list);
    }
    Viz.segmented("pro-filter", [{ key: "every", label: "All leagues" }, ...Object.entries(TREAT).map(([key, label]) => ({ key, label }))], "every", render);
    render("every");
  })();

  Viz.onThemeChange(() => {
    renderKey();
    rerenderHeat();
  });
})();
