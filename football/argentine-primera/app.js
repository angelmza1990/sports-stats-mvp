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
        (off ? ` In ${off} rows the source's wins, draws and losses don't add up to matches played; figures are shown as published.` : "");
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

  document.getElementById("data-through").textContent = `Covers every title through ${data.meta.through}.`;
})();
