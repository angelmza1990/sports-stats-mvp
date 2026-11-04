/* EuroLeague: Elo ratings of every club since 2000–01 (chart, peaks, today's ranking, best team of each season, upsets)
   and home-court advantage season by season. Ratings are computed by scripts/build_euroleague.py. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote, ttRow } = Viz;
  const raw = await d3.json(document.body.dataset.src);
  const { elo, home } = raw;
  const entities = {};
  raw.alltime.forEach((r) => (entities[r.code] = { name: r.name, country: r.club ? raw.clubs[r.club]?.country : null, crest: r.crest }));
  const F = Football({ clubs: entities, countries: raw.countries });
  const name = (code) => entities[code]?.name ?? code;
  const day0 = d3.utcParse("%Y-%m-%d")(elo.day0);
  const dayDate = (d) => d3.utcDay.offset(day0, d);
  const fmtDay = (iso) => d3.utcFormat("%-d %b %Y")(d3.utcParse("%Y-%m-%d")(iso));
  const pct = (x, digits = 0) => `${(x * 100).toFixed(digits)}%`;
  const fmt0 = d3.format(".0f");

  /* ---------- Rating chart ---------- */

  const SLOTS = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)"];
  const codes = Object.keys(elo.series).sort((a, b) => d3.ascending(name(a), name(b)));
  const picked = new Map();
  ["MAD", "CSK", "OLY", "ULK"].filter((c) => elo.series[c]).forEach((c, i) => picked.set(c, i));
  const chips = new Map();
  const chipRoot = document.getElementById("elo-chips");
  codes.forEach((code) => {
    const b = el("button");
    b.type = "button";
    b.append(F.crest(code), document.createTextNode(name(code)));
    b.addEventListener("click", () => {
      if (picked.has(code)) picked.delete(code);
      else {
        if (picked.size >= SLOTS.length) picked.delete(picked.keys().next().value);
        const used = new Set(picked.values());
        picked.set(code, SLOTS.findIndex((_, i) => !used.has(i)));
      }
      syncChips();
      rerender();
    });
    chips.set(code, b);
    chipRoot.append(b);
  });
  function syncChips() {
    chips.forEach((b, code) => {
      b.setAttribute("aria-pressed", String(picked.has(code)));
      if (picked.has(code)) b.style.setProperty("--c", SLOTS[picked.get(code)]);
    });
    Viz.legend("elo-legend", [...picked].sort((a, b) => a[1] - b[1]).map(([c, s]) => ({ label: name(c), color: SLOTS[s] })), "line");
  }
  syncChips();
  document.getElementById("elo-note").textContent =
    `Clubs with at least ${elo.minGames} EuroLeague games. A gap in a line is a season the club did not play the EuroLeague. ` +
    `Settings: K ${elo.k} with a margin-of-victory multiplier, ${elo.hfa} points for home court (none at the Final Four), ` +
    `${pct(elo.carry)} of a rating kept between seasons, new clubs start at ${elo.start}.`;

  // Points as {date, r}; a null breaks the line where a club missed a season (more than 200 days without a game).
  const pointsOf = (code) => elo.series[code].flatMap(([d, r], i, all) =>
    (i && d - all[i - 1][0] > 200 ? [null] : []).concat([{ d, date: dayDate(d), r }]));

  function render(width) {
    const root = document.getElementById("elo-chart");
    const chosen = [...picked].sort((a, b) => a[1] - b[1]);
    if (!chosen.length) {
      root.replaceChildren(el("p", "chart-note", "Pick a club above."));
      return;
    }
    const narrow = width < 640;
    const height = narrow ? 280 : 380;
    const m = { t: 10, r: narrow ? 12 : 110, b: 26, l: 40 };
    const lines = chosen.map(([code, s]) => ({ code, s, pts: pointsOf(code) }));
    const all = lines.flatMap((l) => l.pts.filter(Boolean));
    const x = d3.scaleUtc().domain([dayDate(d3.min(Object.values(elo.series), (s) => s[0][0])), d3.max(all, (p) => p.date)]).range([m.l, width - m.r]);
    const y = d3.scaleLinear().domain([Math.min(1350, d3.min(all, (p) => p.r)), Math.max(1800, d3.max(all, (p) => p.r))]).nice().range([height - m.b, m.t]);
    const svg = d3.create("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", "Elo rating after every EuroLeague game");
    const yt = y.ticks(6);
    svg.append("g").selectAll("line").data(yt).join("line").attr("class", (d) => (d === elo.mean ? "baseline" : "gridline"))
      .attr("x1", m.l).attr("x2", width - m.r).attr("y1", y).attr("y2", y);
    svg.append("g").attr("class", "axis").selectAll("text").data(yt).join("text")
      .attr("x", m.l - 6).attr("y", (d) => y(d) + 4).attr("text-anchor", "end").text((d) => d);
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${height - m.b})`)
      .call(d3.axisBottom(x).ticks(narrow ? 5 : 12).tickSize(0).tickPadding(8))
      .call((g) => g.select(".domain").remove());
    const line = d3.line().defined((p) => p).x((p) => x(p.date)).y((p) => y(p.r));
    lines.forEach((l) => {
      svg.append("path").attr("class", "trend-line").attr("stroke", SLOTS[l.s]).attr("d", line(l.pts));
      const last = l.pts[l.pts.length - 1];
      // Only lines that reach the latest games get an end label; the others would land among them.
      if (!narrow && x.domain()[1] - last.date < 200 * 864e5) {
        svg.append("text").attr("class", "label-muted").attr("x", x(last.date) + 6).attr("y", y(last.r) + 4).text(name(l.code));
      }
    });
    const hair = svg.append("line").attr("class", "crosshair").attr("y1", m.t).attr("y2", height - m.b).style("display", "none");
    const dots = svg.append("g");
    const bis = d3.bisector((p) => p.date).right;
    svg.append("rect").attr("x", m.l).attr("y", m.t).attr("width", width - m.l - m.r).attr("height", height - m.t - m.b).attr("fill", "transparent")
      .on("pointermove", (event) => {
        const at = x.invert(d3.pointer(event)[0]);
        const hits = lines.map((l) => {
          const pts = l.pts.filter(Boolean);
          const i = bis(pts, at) - 1;
          const p = pts[i];
          // Only while the club was playing: within 200 days of its last game.
          return p && (at - p.date) / 864e5 < 200 ? { ...l, p } : null;
        }).filter(Boolean);
        hair.style("display", null).attr("x1", x(at)).attr("x2", x(at));
        dots.selectAll("circle").data(hits).join("circle").attr("class", "trend-dot").attr("r", 4)
          .attr("cx", (h) => x(h.p.date)).attr("cy", (h) => y(h.p.r)).attr("fill", (h) => SLOTS[h.s]);
        Viz.showTip(event, (t) => {
          t.append(ttTitle(d3.utcFormat("%B %Y")(at)));
          hits.sort((a, b) => b.p.r - a.p.r).forEach((h) => t.append(ttRow(SLOTS[h.s], h.p.r, ` ${name(h.code)}`)));
          if (!hits.length) t.append(ttNote("None of these clubs was playing."));
        });
      })
      .on("pointerleave", () => {
        hair.style("display", "none");
        dots.selectAll("circle").remove();
        Viz.hideTip();
      });
    root.replaceChildren(svg.node());
  }
  const rerender = Viz.responsive("elo-chart", render);

  /* ---------- Peaks, today's ranking, best of each season, upsets ---------- */

  F.richTable(document.getElementById("peaks-table"), [
    { label: "#", cls: "rank", render: (p) => String(elo.peaks.indexOf(p) + 1) },
    { label: "Club", render: (p) => F.withSub(F.clubLabel(p.code), fmtDay(p.date)) },
    { label: "Season", cls: "hide-sm", render: (p) => p.season },
    { label: "Peak", cls: "num strong", render: (p) => fmt0(p.rating) },
  ], elo.peaks.slice(0, 10));

  F.rankList(document.getElementById("current-list"), elo.current.slice(0, 18).map((c) => ({
    icon: F.crest(c.code),
    label: name(c.code),
    value: Math.round(c.rating - 1300),
    second: `${c.change >= 0 ? "+" : "−"}${fmt0(Math.abs(c.change))}`,
    color: "var(--series-1)",
    tip: (t) => t.append(ttTitle(name(c.code)), ttNote(`Rating ${fmt0(c.rating)}, ${c.change >= 0 ? "up" : "down"} ${fmt0(Math.abs(c.change))} this season`)),
  })), ["Club", "Rating", "Season"]);
  // The bars start at 1300 so the differences show; print the real rating.
  document.querySelectorAll("#current-list .rank-row .num.strong").forEach((n, i) => (n.textContent = fmt0(elo.current[i].rating)));

  const best = [...elo.seasonBest].reverse();
  F.richTable(document.getElementById("best-table"), [
    { label: "Season", render: (b) => b.season },
    { label: "Best rated before the playoffs", render: (b) => F.withSub(F.clubLabel(b.code),
      `${fmt0(b.rating)} · ${!b.champion ? "season cancelled" : b.champion === b.code ? "won the title" : `${name(b.champion)} won it`}`) },
    { label: "Champion", cls: "hide-sm", render: (b) => (b.champion ? (b.champion === b.code ? el("span", "muted", "Same") : F.clubLabel(b.champion))
      : el("span", "muted", "Cancelled")) },
  ], best);
  const decided = elo.seasonBest.filter((b) => b.champion);
  const same = decided.filter((b) => b.champion === b.code).length;
  document.getElementById("best-note").textContent =
    `The best-rated team going into the playoffs won the title ${same} times in ${decided.length} seasons: a Final Four rewards the best team less often than a long series would.`;

  F.richTable(document.getElementById("upsets-table"), [
    { label: "Chance", cls: "num strong", render: (u) => pct(u.p, 1) },
    { label: "Winner", render: (u) => F.withSub(F.clubLabel(u.winner), `${u.score} vs ${name(u.loser)}${u.home === u.winner ? ", at home" : u.phase === "Final Four" ? "" : ", away"}`) },
    { label: "Date", cls: "hide-sm", render: (u) => F.withSub(document.createTextNode(fmtDay(u.date)), u.phase) },
  ], elo.upsets.slice(0, 12));

  /* ---------- Home advantage ---------- */

  const seasons = home.seasons.map((s) => ({ ...s, rate: s.homeWins / s.games }));
  const avg = home.total.homeWins / home.total.games;
  const current = seasons[seasons.length - 1]; // in progress
  const done = seasons.filter((s) => s !== current).sort((a, b) => a.rate - b.rate);
  const covid = seasons.find((s) => s.season === "2020–21"); // played almost entirely behind closed doors
  const colorOf = (s) => (s === covid ? "var(--series-2)" : "var(--series-1)");
  document.getElementById("home-lede").textContent =
    `The share of games the home team won, season by season: ${pct(avg, 1)} of ${d3.format(",")(home.total.games)} games since 2000–01, by ${home.total.margin.toFixed(1)} points on average. Final Four games, played at a neutral venue, are left out.`;
  const nth = (n) => (n === 1 ? "the lowest" : `the ${["", "", "second", "third", "fourth", "fifth"][n] ?? `${n}th`}-lowest`);
  document.getElementById("home-note").textContent =
    `${covid.season}, played almost entirely without fans because of the COVID-19 pandemic, had ${nth(done.indexOf(covid) + 1)} home win share, ${pct(covid.rate, 1)}` +
    (done[0] === covid ? "." : `; the lowest was ${done[0].season}, ${pct(done[0].rate, 1)}.`) +
    ` The highest was ${done[done.length - 1].season}, ${pct(done[done.length - 1].rate, 1)}. ${current.season} is in progress (${current.games} games so far).`;
  Viz.legend("home-legend", [{ label: "Home win share", color: "var(--series-1)" }, { label: "2020–21, without fans", color: "var(--series-2)" },
    { label: `Average, ${pct(avg, 1)}`, color: "var(--ink-2)" }]);

  function renderHome(width) {
    const root = document.getElementById("home-chart");
    const narrow = width < 640;
    const height = narrow ? 220 : 280;
    const m = { t: 10, r: 8, b: 26, l: 40 };
    const x = d3.scaleBand().domain(seasons.map((s) => s.season)).range([m.l, width - m.r]).padding(0.2);
    const y = d3.scaleLinear().domain([0.5, 0.7]).range([height - m.b, m.t]);
    const svg = d3.create("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", "Home win share by season");
    const yt = [0.5, 0.55, 0.6, 0.65, 0.7];
    svg.append("g").selectAll("line").data(yt).join("line").attr("class", (d) => (d === 0.5 ? "baseline" : "gridline"))
      .attr("x1", m.l).attr("x2", width - m.r).attr("y1", y).attr("y2", y);
    svg.append("g").attr("class", "axis").selectAll("text").data(yt).join("text")
      .attr("x", m.l - 6).attr("y", (d) => y(d) + 4).attr("text-anchor", "end").text((d) => pct(d));
    svg.append("g").attr("class", "axis").selectAll("text").data(seasons).join("text")
      .attr("x", (s) => x(s.season) + x.bandwidth() / 2).attr("y", height - 8).attr("text-anchor", "middle")
      .text((s, i) => (i % (narrow ? 5 : 3) === 0 ? `'${s.season.slice(2, 4)}` : ""));
    const bars = svg.append("g").selectAll("path").data(seasons).join("path")
      .attr("fill", colorOf).attr("fill-opacity", (s) => (s === current ? 0.45 : 1))
      .attr("d", (s) => Viz.columnPath(x(s.season), y(Math.max(0.5, s.rate)), x.bandwidth(), y(0.5) - y(Math.max(0.5, s.rate)), 3));
    svg.append("line").attr("stroke", "var(--ink-2)").attr("stroke-width", 2).attr("stroke-dasharray", "5 4")
      .attr("x1", m.l).attr("x2", width - m.r).attr("y1", y(avg)).attr("y2", y(avg));
    Viz.tooltipOn(bars, (t, s) => t.append(ttTitle(s.season),
      ttRow(colorOf(s), pct(s.rate, 1), " home wins"),
      ttNote(`${s.homeWins} of ${s.games} games · home side +${s.margin.toFixed(1)} points a game${s === current ? " · season in progress" : ""}`)));
    root.replaceChildren(svg.node());
  }
  Viz.responsive("home-chart", renderHome);

  F.richTable(document.getElementById("home-phases"), [
    { label: "Stage", render: (p) => p.phase },
    { label: "Games", cls: "num", render: (p) => d3.format(",")(p.games) },
    { label: "Home wins", cls: "num strong", render: (p) => pct(p.homeWins / p.games, 1) },
    { label: "Home margin", cls: "num", render: (p) => `+${p.margin.toFixed(1)}` },
  ], [...home.phases, { phase: "All stages", ...home.total }]);
})();
