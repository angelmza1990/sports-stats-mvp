/* Argentine Primera División: league champions since 1891. */
(async function () {
  "use strict";

  const { el, tooltipOn, ttTitle, ttNote } = Viz;
  const data = await d3.json(document.body.dataset.src);
  const F = Football(data);
  const { clubName } = F;
  const titles = data.titles;
  const ASSOC = data.meta.associations; // {FAF: "...", AAmF: "...", LAF: "..."}

  const ERAS = [
    { key: "all", label: "All eras", test: () => true },
    { key: "professional", label: "Professional era", test: (t) => t.era === "professional" },
    { key: "amateur", label: "Amateur era", test: (t) => t.era === "amateur" },
  ];
  const eraBy = Object.fromEntries(ERAS.map((e) => [e.key, e]));
  const PRO_START = d3.min(titles.filter((t) => t.era === "professional"), (t) => t.year);

  /* ---------- Stat tiles ---------- */

  const counts = d3.rollup(titles, (v) => v.length, (t) => t.champion);
  const [leader, leaderN] = d3.greatest(counts, (d) => d[1]);
  const proCounts = d3.rollup(titles.filter(eraBy.professional.test), (v) => v.length, (t) => t.champion);
  const [proLeader, proN] = d3.greatest(proCounts, (d) => d[1]);
  const splitYears = [...new Set(titles.filter((t) => t.split).map((t) => t.year))].sort((a, b) => a - b);
  F.statTiles("stats", [
    { label: "League titles awarded", value: String(titles.length), detail: `${titles[0].year} to ${titles[titles.length - 1].season}` },
    { label: "Most titles", value: String(leaderN), detail: clubName(leader), club: leader },
    { label: "Most professional titles", value: String(proN), detail: `${clubName(proLeader)}, since ${PRO_START}`, club: proLeader },
    { label: "Years with two champions", value: String(splitYears.length), detail: "rival associations, 1912–1934" },
  ]);

  /* ---------- Bar chart race with an era switch ---------- */

  const framesFor = (key) => {
    const list = titles.filter(eraBy[key].test);
    return F.titleFrames(list, (t) => t.season.replace(/\s*\(.*\)$/, ""), String(list[0].year));
  };
  const tickerFor = (t) => [F.crest(t.champion), el("strong", null, `${t.season} · ${clubName(t.champion)}`),
    document.createTextNode(t.runnerUp ? `, ahead of ${clubName(t.runnerUp)}` : "")];
  const race = F.race(framesFor("all"), {
    colorOf: () => "var(--series-1)",
    emptyTicker: "Press play to start with the first championship, 1891.",
    ticker: tickerFor,
    frameMs: 380,
  });
  Viz.segmented("race-era", ERAS.slice(0, 2), "all", (k) => race.setFrames(framesFor(k)));

  /* ---------- Sections scoped by the era filter ---------- */

  const seasonsText = (list) => list.map((t) => t.season).join(", ") || "–";

  function render(key) {
    const list = titles.filter(eraBy[key].test);
    const ids = new Set(list.flatMap((t) => [t.champion, t.runnerUp]).filter(Boolean));
    const rows = [...ids].map((id) => ({
      id,
      won: list.filter((t) => t.champion === id),
      lost: list.filter((t) => t.runnerUp === id),
    })).filter((r) => r.won.length || r.lost.length)
      .sort((a, b) => b.won.length - a.won.length || b.lost.length - a.lost.length || d3.ascending(clubName(a.id), clubName(b.id)));
    F.richTable(document.getElementById("clubs-table"), [
      { label: "Club", render: (r) => F.withSub(F.clubLabel(r.id), `Won: ${seasonsText(r.won)}`) },
      { label: "Titles", cls: "num strong", render: (r) => String(r.won.length) },
      ...(key === "all" ? [
        { label: "Amateur", short: "Am.", cls: "num", render: (r) => String(r.won.filter((t) => t.era === "amateur").length) },
        { label: "Professional", short: "Pro", cls: "num", render: (r) => String(r.won.filter((t) => t.era === "professional").length) },
      ] : []),
      { label: "Runners-up", short: "R-up", cls: "num", render: (r) => String(r.lost.length) },
      { label: "Seasons won", cls: "years", render: (r) => seasonsText(r.won) },
    ], rows.filter((r) => r.won.length));

    const tagged = list.slice().reverse().map((t) => ({ ...t, _rowClass: t.split ? "split-row" : null }));
    F.richTable(document.getElementById("seasons-table"), [
      { label: "Season", render: (t) => t.season },
      { label: "Champion", render: (t) => F.clubLabel(t.champion) },
      { label: "Runner-up", cls: "hide-sm", render: (t) => (t.runnerUp ? F.clubLabel(t.runnerUp) : "–") },
      { label: "Era", render: (t) => assocTag(t) },
    ], tagged);
  }

  function assocTag(t) {
    const span = el("span", `era-tag ${t.era}`, t.era === "professional" ? "Pro" : "Amateur");
    if (!t.association) return span;
    const wrap = el("span", "tags");
    const a = el("span", `assoc-tag assoc-${t.association}`, t.association);
    a.title = ASSOC[t.association];
    wrap.append(span, a);
    return wrap;
  }

  Viz.segmented("era-filter", ERAS, "all", render);
  render("all");

  /* ---------- All-time tables (total, professional, amateur) ---------- */

  (function allTime() {
    const TABS = [
      { key: "total", label: "All eras" },
      { key: "professional", label: "Professional era" },
      { key: "amateur", label: "Amateur era" },
    ];
    const periods = data.meta.alltimePeriods;
    const sign = (n) => (n > 0 ? `+${n}` : String(n));
    function render(key) {
      const rows = (data.alltime[key] || []).slice().sort((a, b) => b.pts - a.pts || (b.gf - b.ga) - (a.gf - a.ga));
      const note = { total: "Amateur and professional eras combined", professional: "Professional era", amateur: "Amateur era" }[key];
      const off = rows.filter((r) => r.pld !== r.w + r.d + r.l).length;
      document.getElementById("alltime-note").textContent = `${note}, ${periods[key] ?? ""}: ${rows.length} clubs.` +
        (off ? ` In ${off} rows the source's wins, draws and losses don't add up to matches played; figures are shown as published.` : "") + ` ${F.EFFECTIVENESS_NOTE}`;
      F.richTable(document.getElementById("alltime-table"), [
        { label: "#", cls: "num rank", render: (r) => String(rows.indexOf(r) + 1) },
        { label: "Club", render: (r) => F.clubLabel(r.club) },
        { label: "Played", short: "P", cls: "num", render: (r) => String(r.pld) },
        { label: "W", cls: "num", render: (r) => String(r.w) },
        { label: "D", cls: "num", render: (r) => String(r.d) },
        { label: "L", cls: "num", render: (r) => String(r.l) },
        { label: "GF", cls: "num hide-sm", render: (r) => String(r.gf) },
        { label: "GA", cls: "num hide-sm", render: (r) => String(r.ga) },
        { label: "GD", cls: "num hide-sm", render: (r) => sign(r.gf - r.ga) },
        ...(key === "total" ? [{ label: "Titles", cls: "num", render: (r) => String(counts.get(r.club) ?? 0) }] : []),
        { label: "Points", short: "Pts", cls: "num strong", render: (r) => String(r.pts) },
        F.effColumn,
      ], rows);
    }
    Viz.segmented("alltime-tabs", TABS, "total", render);
    render("total");
  })();

  /* ---------- Top scorers ---------- */

  (function scorers() {
    const list = data.scorers;
    const byClub = d3.rollups(list.flatMap((sc) => sc.clubs.map((c) => ({ ...sc, club: c }))), (v) => v, (d) => d.club)
      .sort((a, b) => b[1].length - a[1].length).slice(0, 12);
    F.rankList(document.getElementById("scorer-clubs"), byClub.map(([club, v]) => ({
      icon: F.crest(club), label: clubName(club), value: v.length, second: new Set(v.map((d) => d.player)).size,
      tip: (t) => {
        t.append(ttTitle(`${clubName(club)}: ${v.length} top scorers`));
        t.append(ttNote(v.map((d) => `${d.season} ${d.player} (${d.goals})`).join(" · ")));
      },
    })), ["Club", "Times", "Players"]);

    const byPlayer = d3.rollups(list, (v) => v, (d) => d.player).sort((a, b) => b[1].length - a[1].length || d3.max(b[1], (d) => d.goals) - d3.max(a[1], (d) => d.goals)).slice(0, 12);
    F.rankList(document.getElementById("scorer-players"), byPlayer.map(([player, v]) => ({
      icon: F.flag(v[0].nation), label: player, value: v.length, second: d3.max(v, (d) => d.goals),
      tip: (t) => {
        t.append(ttTitle(player));
        v.forEach((d) => t.append(Viz.ttRow("var(--ink-2)", d.goals, `${d.season} · ${d.clubs.map(clubName).join(" / ")}`)));
      },
    })), ["Player", "Titles", "Best"]);

    const playerCell = (name, nation, sub) => {
      const span = el("span", "club");
      span.append(F.flag(nation), document.createTextNode(name));
      return sub ? F.withSub(span, sub) : span;
    };
    const clubsCell = (ids) => {
      const wrap = el("div", "stack-clubs");
      ids.forEach((c) => wrap.append(F.clubLabel(c)));
      return wrap;
    };
    const views = {
      season: () => F.richTable(document.getElementById("scorers-table"), [
        { label: "Tournament", render: (d) => d.season },
        { label: "Top scorer", render: (d) => playerCell(d.player, d.nation, d.clubs.map(clubName).join(" / ")) },
        { label: "Club", cls: "hide-sm", render: (d) => clubsCell(d.clubs) },
        { label: "Goals", cls: "num strong", render: (d) => String(d.goals) },
        { label: "Matches", short: "M", cls: "num hide-sm", render: (d) => (d.matches ? String(d.matches) : "–") },
      ], list.slice().reverse()),
      alltime: () => F.richTable(document.getElementById("scorers-table"), [
        { label: "#", cls: "num rank", render: (d) => String(data.alltimeScorers.indexOf(d) + 1) },
        { label: "Player", render: (d) => playerCell(d.player, d.nation) },
        { label: "Career", cls: "years", render: (d) => d.career },
        { label: "Goals", cls: "num strong", render: (d) => String(d.goals) },
        { label: "Matches", short: "M", cls: "num", render: (d) => String(d.matches ?? "–") },
        { label: "Per match", short: "Ratio", cls: "num", render: (d) => (d.matches ? (d.goals / d.matches).toFixed(2) : "–") },
      ], data.alltimeScorers),
    };
    Viz.segmented("scorers-tabs", [{ key: "season", label: "Every tournament" }, { key: "alltime", label: "All-time scorers" }], "season", (k) => views[k]());
    views.season();
  })();

  /* ---------- Amateur era: timeline of splits + year-by-year table ---------- */

  (function amateurEra() {
    const amateurYears = d3.range(titles[0].year, 1935);
    const periods = d3.groups(titles.filter((t) => t.association), (t) => t.association).map(([assoc, list]) => ({
      assoc, from: d3.min(list, (t) => t.year), to: d3.max(list, (t) => t.year),
    }));
    const COLORS = { FAF: "var(--series-2)", AAmF: "var(--series-3)", LAF: "var(--series-1)" };
    Viz.legend("split-legend", [
      { label: "One association", color: "var(--axis)" },
      ...periods.map((p) => ({ label: `${ASSOC[p.assoc]} (${p.assoc})`, color: COLORS[p.assoc] })),
    ]);

    const periodBox = document.getElementById("split-periods");
    const text = {
      FAF: "The Federación Argentina de Football split from the official association. Porteño (1912, 1914) and Estudiantes de La Plata (1913) won its titles.",
      AAmF: "The Asociación Amateurs de Football ran a rival league for eight seasons, won by Racing, River Plate, Independiente and San Lorenzo, until the 1927 reunification.",
      LAF: "Clubs left to found the professional Liga Argentina de Football in 1931, while the amateur association kept its own championship until the 1934 merger that created today's AFA.",
    };
    periods.forEach((p) => {
      const box = el("div", "split-period");
      box.style.setProperty("--c", COLORS[p.assoc]);
      box.append(el("strong", null, `${p.from}–${p.to} · ${p.assoc}`), el("p", null, text[p.assoc] ?? ASSOC[p.assoc]));
      periodBox.append(box);
    });

    Viz.responsive("split-timeline", (width) => {
      const container = d3.select("#split-timeline");
      container.selectAll("*").remove();
      const narrow = width < 560;
      const margin = { top: 8, right: 8, bottom: 24, left: 8 };
      const height = 64;
      const x = d3.scaleBand().domain(amateurYears).range([margin.left, width - margin.right]).paddingInner(0.12);
      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img")
        .attr("aria-label", `Amateur era 1891 to 1934; two champions in ${splitYears.join(", ")}`);
      const cells = svg.selectAll("g.year").data(amateurYears).join("g").attr("class", "year mark-group")
        .attr("transform", (y) => `translate(${x(y)},${margin.top})`);
      cells.append("rect").attr("class", "mark").attr("width", x.bandwidth()).attr("height", height - margin.top - margin.bottom).attr("rx", 2)
        .attr("fill", (y) => {
          const t = titles.find((d) => d.year === y && d.association);
          return t ? COLORS[t.association] : "var(--axis)";
        })
        .attr("opacity", (y) => (titles.some((t) => t.year === y) ? 1 : 0.35));
      svg.append("g").attr("class", "axis").selectAll("text").data(amateurYears.filter((y) => y % (narrow ? 10 : 5) === 0)).join("text")
        .attr("x", (y) => x(y) + x.bandwidth() / 2).attr("y", height - 6).attr("text-anchor", "middle").text((y) => y);
      tooltipOn(cells, (t, y) => {
        const list = titles.filter((d) => d.year === y);
        t.append(ttTitle(String(y)));
        if (!list.length) t.append(ttNote("No championship held"));
        list.forEach((d) => t.append(Viz.ttRow(d.association ? COLORS[d.association] : "var(--axis)", d.association ?? "Official", clubName(d.champion))));
      });
    });

    const rows = amateurYears.map((y) => {
      const list = titles.filter((t) => t.year === y && (t.era === "amateur" || t.association === "LAF"));
      return {
        year: y,
        official: list.filter((t) => !t.association),
        rival: list.find((t) => t.association),
        _rowClass: list.some((t) => t.association) ? "split-row" : null,
      };
    });
    F.richTable(document.getElementById("amateur-table"), [
      { label: "Year", render: (r) => String(r.year) },
      {
        label: "Official association", render: (r) => {
          if (!r.official.length) return el("span", "muted", "No championship");
          const wrap = el("div", "stack-clubs");
          r.official.forEach((t) => wrap.append(F.clubLabel(t.champion)));
          return wrap;
        },
      },
      {
        label: "Rival association", render: (r) => {
          if (!r.rival) return el("span", "muted", "–");
          const wrap = el("span", "tags");
          const a = el("span", `assoc-tag assoc-${r.rival.association}`, r.rival.association);
          a.title = ASSOC[r.rival.association];
          wrap.append(a, F.clubLabel(r.rival.champion));
          return wrap;
        },
      },
    ], rows.reverse());
  })();

  /* ---------- Every title: leagues, national cups and international ---------- */

  (async function allTitles() {
    const intl = await d3.json("data/international.json");
    const compName = Object.fromEntries(intl.competitions.map((c) => [c.key, c.label]));
    Object.entries(intl.clubs).forEach(([id, c]) => (data.clubs[id] ??= { ...c, country: "ARG" }));
    const KINDS = { league: "League", cup: "National cup", intl: "International" };
    const all = [
      ...titles.map((t) => ({ club: t.champion, era: t.era, kind: "league", year: t.year, label: `League ${t.season}` })),
      ...data.cups.flatMap((c) => c.editions.map((e) => ({ club: e.champion, era: e.era, kind: "cup", year: e.year, label: `${c.name} ${e.season}` }))),
      ...intl.titles.map((t) => ({ club: t.club, era: t.era, kind: "intl", year: t.year, label: `${compName[t.comp]} ${t.season}` })),
    ].sort((a, b) => a.year - b.year || ["league", "cup", "intl"].indexOf(a.kind) - ["league", "cup", "intl"].indexOf(b.kind));
    const state = { era: "all", kind: "all" };
    const scoped = () => all.filter((t) => (state.era === "all" || t.era === state.era) && (state.kind === "all" || t.kind === state.kind));
    const count = (list, kind, era) => list.filter((t) => (!kind || t.kind === kind) && (!era || t.era === era)).length;
    const total = document.getElementById("titles-total");
    total.textContent = `${all.length} titles: ${count(all, "league")} leagues, ${count(all, "cup")} national cups and ${count(all, "intl")} international titles.`;

    // The race: every title in order, one frame per title.
    const framesFor = () => F.titleFrames(scoped().map((t) => ({ ...t, champion: t.club })), (t) => String(t.year), String(scoped()[0]?.year - 1 || ""));
    const race = F.race(framesFor(), {
      prefix: "titles-race",
      colorOf: (id) => `var(--series-${{ league: 1, cup: 3, intl: 2 }[state.kind] ?? 1})`,
      emptyTicker: "Press play to start with the first title.",
      ticker: (t) => [el("strong", null, `${t.year} · ${clubName(t.club)}`), document.createTextNode(` · ${t.label}`)],
      frameMs: 300,
    });

    // The line chart: titles by the end of each year, for up to four clubs.
    const SLOTS = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)"];
    const picked = new Map(["river-plate", "boca-juniors", "independiente", "racing"].map((c, i) => [c, i]));
    const chipClubs = d3.groups(all, (t) => t.club).sort((a, b) => b[1].length - a[1].length).slice(0, 16).map(([c]) => c);
    const chips = new Map();
    chipClubs.forEach((c) => {
      const b = el("button");
      b.type = "button";
      b.append(F.crest(c), document.createTextNode(clubName(c)));
      b.addEventListener("click", () => {
        if (picked.has(c)) picked.delete(c);
        else {
          if (picked.size >= SLOTS.length) picked.delete(picked.keys().next().value);
          const used = new Set(picked.values());
          picked.set(c, SLOTS.findIndex((_, s) => !used.has(s)));
        }
        syncChips();
        rerenderLine();
      });
      chips.set(c, b);
      document.getElementById("titles-chips").append(b);
    });
    function syncChips() {
      chips.forEach((b, c) => {
        b.setAttribute("aria-pressed", String(picked.has(c)));
        if (picked.has(c)) b.style.setProperty("--c", SLOTS[picked.get(c)]);
      });
      Viz.legend("titles-legend", [...picked].sort((x, y) => x[1] - y[1]).map(([c, s]) => ({ label: clubName(c), color: SLOTS[s] })), "line");
    }
    syncChips();

    function renderLine(width) {
      const root = document.getElementById("titles-line");
      const chosen = [...picked].sort((x, y) => x[1] - y[1]);
      if (!chosen.length) return root.replaceChildren(el("p", "chart-note", "Pick a club above."));
      const list = scoped();
      const narrow = width < 640;
      const height = narrow ? 260 : 360;
      const m = { t: 10, r: narrow ? 12 : 110, b: 26, l: 36 };
      const first = state.era === "professional" ? 1931 : 1891;
      const last = d3.max(all, (t) => t.year);
      const yearsAll = d3.range(first, last + 1);
      const lines = chosen.map(([c, s]) => {
        let n = 0;
        const byYear = d3.rollup(list.filter((t) => t.club === c), (v) => v.length, (t) => t.year);
        return { c, s, pts: yearsAll.map((yr) => ({ yr, n: (n += byYear.get(yr) ?? 0) })) };
      });
      const x = d3.scaleLinear().domain([first, last]).range([m.l, width - m.r]);
      const y = d3.scaleLinear().domain([0, Math.max(1, d3.max(lines, (l) => l.pts[l.pts.length - 1].n))]).nice().range([height - m.b, m.t]);
      const svg = d3.create("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", "Titles won by the end of each year");
      const yt = y.ticks(6);
      svg.append("g").selectAll("line").data(yt).join("line").attr("class", (d) => (d === 0 ? "baseline" : "gridline")).attr("x1", m.l).attr("x2", width - m.r).attr("y1", y).attr("y2", y);
      svg.append("g").attr("class", "axis").selectAll("text").data(yt).join("text").attr("x", m.l - 6).attr("y", (d) => y(d) + 4).attr("text-anchor", "end").text((d) => d);
      svg.append("g").attr("class", "axis").attr("transform", `translate(0,${height - m.b})`)
        .call(d3.axisBottom(x).ticks(narrow ? 5 : 12).tickFormat(d3.format("d")).tickSize(0).tickPadding(8)).call((g) => g.select(".domain").remove());
      const line = d3.line().curve(d3.curveStepAfter).x((p) => x(p.yr)).y((p) => y(p.n));
      lines.forEach((l) => svg.append("path").attr("class", "trend-line").attr("stroke", SLOTS[l.s]).attr("d", line(l.pts)));
      if (!narrow) {
        // End labels, nudged apart so close totals don't overlap.
        const ends = lines.map((l) => ({ l, n: l.pts[l.pts.length - 1].n, y: y(l.pts[l.pts.length - 1].n) + 4 })).sort((a, b) => a.y - b.y);
        ends.forEach((e, i) => { if (i && e.y - ends[i - 1].y < 14) e.y = ends[i - 1].y + 14; });
        svg.append("g").selectAll("text").data(ends).join("text").attr("class", "label-muted")
          .attr("x", width - m.r + 6).attr("y", (e) => e.y).text((e) => `${clubName(e.l.c)} ${e.n}`);
      }
      const hair = svg.append("line").attr("class", "crosshair").attr("y1", m.t).attr("y2", height - m.b).style("display", "none");
      const dots = svg.append("g");
      svg.append("rect").attr("x", m.l).attr("y", m.t).attr("width", width - m.l - m.r).attr("height", height - m.t - m.b).attr("fill", "transparent")
        .on("pointermove", (event) => {
          const yr = Math.max(first, Math.min(last, Math.round(x.invert(d3.pointer(event)[0]))));
          const hits = lines.map((l) => ({ ...l, p: l.pts[yr - first] }));
          hair.style("display", null).attr("x1", x(yr)).attr("x2", x(yr));
          dots.selectAll("circle").data(hits).join("circle").attr("class", "trend-dot").attr("r", 4).attr("cx", (h) => x(h.p.yr)).attr("cy", (h) => y(h.p.n)).attr("fill", (h) => SLOTS[h.s]);
          Viz.showTip(event, (t) => {
            t.append(ttTitle(`By the end of ${yr}`));
            hits.slice().sort((p, q) => q.p.n - p.p.n).forEach((h) => t.append(Viz.ttRow(SLOTS[h.s], h.p.n, ` ${clubName(h.c)}`)));
            const won = list.filter((t2) => t2.year === yr && picked.has(t2.club));
            if (won.length) t.append(ttNote(won.map((t2) => `${clubName(t2.club)}: ${t2.label}`).join(" · ")));
          });
        })
        .on("pointerleave", () => { hair.style("display", "none"); dots.selectAll("circle").remove(); Viz.hideTip(); });
      root.replaceChildren(svg.node());
    }
    const rerenderLine = Viz.responsive("titles-line", renderLine);

    // The table: every club with a title, broken down by kind and era.
    function renderTable() {
      const list = scoped();
      const rows = d3.groups(list, (t) => t.club).map(([club, mine]) => ({ club, mine, every: all.filter((t) => t.club === club) }))
        .sort((a, b) => b.mine.length - a.mine.length || count(b.mine, "league") - count(a.mine, "league") || d3.ascending(clubName(a.club), clubName(b.club)));
      let rank = 0;
      rows.forEach((r, i) => (r.rank = i && rows[i - 1].mine.length === r.mine.length ? rank : (rank = i + 1)));
      const both = state.era === "all";
      const num = (n) => (n ? String(n) : "–");
      F.richTable(document.getElementById("titles-table"), [
        { label: "#", cls: "num rank", render: (r) => String(r.rank) },
        { label: "Club", render: (r) => F.clubLabel(r.club) },
        ...Object.entries(KINDS).filter(([k]) => state.kind === "all" || state.kind === k).map(([k, label]) => ({
          label: label === "League" ? "Leagues" : `${label}s`, short: { league: "Lg", cup: "Cup", intl: "Intl" }[k], cls: "num", render: (r) => num(count(r.mine, k)),
        })),
        ...(both ? [
          { label: "Amateur", short: "Am.", cls: "num hide-sm", render: (r) => num(count(r.mine, null, "amateur")) },
          { label: "Professional", short: "Pro", cls: "num hide-sm", render: (r) => num(count(r.mine, null, "professional")) },
        ] : []),
        { label: "Total", cls: "num strong", render: (r) => String(r.mine.length) },
      ], rows);
    }

    const rerender = () => {
      d3.selectAll("#titles-race-chart g.row").remove();
      race.setFrames(framesFor());
      rerenderLine();
      renderTable();
    };
    Viz.segmented("titles-era", [
      { key: "all", label: "All eras" }, { key: "professional", label: "Professional" }, { key: "amateur", label: "Amateur" },
    ], "all", (k) => { state.era = k; rerender(); });
    Viz.segmented("titles-kind", [
      { key: "all", label: "All titles" }, { key: "league", label: "Leagues" }, { key: "cup", label: "National cups" }, { key: "intl", label: "International" },
    ], "all", (k) => { state.kind = k; rerender(); });
    renderTable();
  })();

  /* ---------- National cups ---------- */

  (function cups() {
    const ERA_LABEL = { amateur: "Amateur", professional: "Professional", both: "Amateur and professional" };
    const list = data.cups;
    const counts = d3.rollup(list, (v) => v.length, (c) => c.era);
    const both = counts.get("both") ?? 0;
    document.getElementById("cups-count").textContent =
      `${list.length} cups: ${counts.get("amateur") ?? 0} amateur, ${counts.get("professional") ?? 0} professional` +
      (both ? ` and ${both === 1 ? "one" : both} played in both eras.` : ".");
    const editionsOf = (cup) => new Set(cup.editions.map((e) => e.season)).size;
    const winsIn = (cup, era) => cup.editions.filter((e) => era === "all" || e.era === era);

    function board(root, editions, limit) {
      const byClub = d3.rollups(editions, (v) => v, (e) => e.champion)
        .sort((a, b) => b[1].length - a[1].length || d3.min(a[1], (e) => e.year) - d3.min(b[1], (e) => e.year));
      F.rankList(root, byClub.slice(0, limit).map(([club, won]) => ({
        icon: F.crest(club), label: clubName(club), value: won.length,
        second: editions.filter((e) => e.runnerUp === club).length || null,
        tip: (t) => {
          t.append(ttTitle(`${clubName(club)}: ${won.length} ${won.length === 1 ? "title" : "titles"}`));
          t.append(ttNote(won.map((e) => `${e.cupName ? `${e.cupName} ` : ""}${e.season}`).join(" · ")));
        },
      })), ["Club", "Titles", "Finals lost"]);
    }

    function card(cup, era) {
      const box = el("article", "card cup-card");
      box.append(el("h3", null, cup.name));
      const meta = el("div", "cup-meta");
      const played = editionsOf(cup);
      const n = played + cup.unfinished.length;
      meta.append(el("span", `era-tag ${cup.era === "professional" ? "professional" : cup.era === "both" ? "both" : ""}`, ERA_LABEL[cup.era]),
        el("span", null, `${cup.years} · ${n} ${n === 1 ? "edition" : "editions"}` +
          (cup.unfinished.length ? ` (${cup.unfinished.join(", ")} not finished)` : "")));
      box.append(meta, el("p", "cup-desc", cup.description));
      const wins = winsIn(cup, era);
      if (!wins.length) {
        box.append(el("p", "muted", "No champion was crowned."));
        return box;
      }
      const leaders = el("div");
      box.append(leaders);
      board(leaders, wins, 5);
      const details = el("details");
      details.append(el("summary", null, played === 1 ? "The final" : `Every edition (${played})`));
      const tableBox = el("div", "data-table");
      details.append(tableBox);
      F.richTable(tableBox, [
        { label: "Season", render: (e) => e.season },
        { label: "Champion", render: (e) => (e.shared ? F.withSub(F.clubLabel(e.champion), "shared title") : F.clubLabel(e.champion)) },
        { label: "Runner-up", render: (e) => (e.runnerUp ? F.clubLabel(e.runnerUp) : "–") },
      ], wins.slice().reverse());
      box.append(details);
      return box;
    }

    function render(era) {
      const shown = list.filter((c) => era === "all" || c.era === era || c.era === "both");
      const all = shown.flatMap((c) => winsIn(c, era).map((e) => ({ ...e, cupName: c.name })));
      document.getElementById("cups-leaders-title").textContent =
        `Most cup titles${era === "all" ? "" : `, ${era} era`} (${all.length} titles in ${shown.length} cups)`;
      board(document.getElementById("cups-leaders"), all, 12);
      document.getElementById("cups-list").replaceChildren(...shown.map((c) => card(c, era)));
    }
    Viz.segmented("cups-era", [
      { key: "all", label: "All cups" }, { key: "amateur", label: "Amateur era" }, { key: "professional", label: "Professional era" },
    ], "all", render);
    render("all");
  })();

  /* ---------- Relegation and seasons in the top flight ---------- */

  (function relegation() {
    const rel = data.relegation;
    const down = rel.moves.filter((m) => m.down > 0).sort((a, b) => b.down - a.down || d3.ascending(clubName(a.club), clubName(b.club)));
    F.rankList(document.getElementById("relegation-list"), down.slice(0, 20).map((m) => ({
      icon: F.crest(m.club), label: clubName(m.club), value: m.down, second: `${m.up} up`, color: "var(--series-1)",
      tip: (t) => t.append(ttTitle(clubName(m.club)), ttNote(`${m.down} relegation${m.down === 1 ? "" : "s"} and ${m.up} promotion${m.up === 1 ? "" : "s"} (or readmissions) since 1931`)),
    })), ["Club", "Down", ""]);
    const seasons = new Map(rel.seasons.map((s) => [s.club, s]));
    // Clubs of today never relegated in the professional era, with most of a century in the top flight.
    const never = rel.moves.filter((m) => m.down === 0 && (seasons.get(m.club)?.seasons ?? 0) >= 50).map((m) => clubName(m.club));
    const big = ["river-plate", "independiente", "racing", "san-lorenzo"].filter((c) => rel.moves.some((m) => m.club === c && m.down > 0));
    document.getElementById("relegation-note").textContent =
      `${rel.moves.filter((m) => m.down > 0).length} clubs relegated at least once, through ${rel.through}. ` +
      `${never.join(", ")} ${never.length === 1 ? "is the only one" : "are the only ones"} of the big clubs never relegated; ${big.map(clubName).join(", ")} all went down at least once.`;
    const run = (s) => (s.since === "-" || !s.run ? s.seasons : s.run);
    const VIEWS = {
      total: (s) => s.seasons,
      run,
    };
    function render(view) {
      const list = rel.seasons.slice().sort((a, b) => VIEWS[view](b) - VIEWS[view](a)).slice(0, 30);
      F.rankList(document.getElementById("topflight-list"), list.map((s) => ({
        icon: F.crest(s.club), label: clubName(s.club), value: VIEWS[view](s),
        second: view === "total" ? `since ${s.first.slice(0, 4)}` : s.since === "-" ? (s.seasons > 1 ? "never left" : "first season") : `since ${s.since.slice(0, 4)}`, color: "var(--series-1)",
        tip: (t) => t.append(ttTitle(clubName(s.club)), ttNote(`${s.seasons} seasons in the Primera División, first in ${s.first}; ${s.since === "-" ? (s.seasons > 1 ? "never relegated" : "its first season") : `back since ${s.since}, ${s.run} seasons in a row`}`)),
      })), ["Club", "Seasons", ""]);
    }
    Viz.segmented("seasons-tabs", [{ key: "total", label: "All seasons" }, { key: "run", label: "Current run" }], "total", render);
    render("total");
  })();

  document.getElementById("data-through").textContent = `Covers every title through ${data.meta.through}.`;
})();
