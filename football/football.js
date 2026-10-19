/* Copa Libertadores and Champions League pages. */
(async function () {
  "use strict";

  const { el, table, responsive, tooltipOn, ttTitle, ttNote, barPath } = Viz;
  const data = await d3.json(document.body.dataset.src);
  const F = Football(data);
  const { clubs, clubName, countryName, scoreText } = F;
  const finals = data.finals;

  // West German clubs count for Germany in country totals (as on UEFA's own tables).
  const nation = (code) => ({ FRG: "GER" })[code] ?? code;

  /* ---------- Country colors (top three title-winning nations, the rest gray) ---------- */

  const nationTitles = d3.rollups(finals, (v) => ({ n: v.length, first: v[0].year }), (f) => nation(f.championCountry))
    .sort((a, b) => b[1].n - a[1].n || a[1].first - b[1].first);
  const COLOR_SLOTS = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];
  const nationColor = new Map(nationTitles.slice(0, 3).map(([code], i) => [code, COLOR_SLOTS[i]]));
  const colorOf = (code) => nationColor.get(nation(code)) ?? "var(--ink-muted)";

  /* ---------- Stat tiles ---------- */

  const titles = d3.rollup(finals, (v) => v.length, (f) => f.champion);
  const [leader, leaderN] = d3.greatest(titles, (d) => d[1]);
  const topNations = nationTitles.filter(([, v]) => v.n === nationTitles[0][1].n).map(([code]) => countryName(code));
  F.statTiles("stats", [
    { label: "Finals played", value: String(finals.length), detail: `${finals[0].season} to ${finals[finals.length - 1].season}` },
    { label: "Different champions", value: String(titles.size), detail: `${d3.sum(titles.values(), (v) => v === 1)} won it once` },
    { label: "Most titles", value: String(leaderN), detail: clubName(leader), club: leader },
    {
      label: "Champion countries",
      value: String(new Set(finals.map((f) => nation(f.championCountry))).size),
      detail: topNations.length > 1 ? `${topNations.join(" and ")} tied on ${nationTitles[0][1].n}` : `${topNations[0]} leads with ${nationTitles[0][1].n}`,
    },
  ]);

  /* ---------- Bar chart race ---------- */

  Viz.legend("race-legend", [
    ...nationTitles.slice(0, 3).map(([code]) => ({ label: countryName(code), color: nationColor.get(code) })),
    { label: "Other countries", color: "var(--ink-muted)" },
  ]);
  F.race(F.titleFrames(finals, (f) => f.season, String(finals[0].year)), {
    colorOf: (id) => colorOf(clubs[id]?.country),
    emptyTicker: `Press play to start with the first final, ${finals[0].season}.`,
    ticker: (f) => [F.crest(f.champion), el("strong", null, `${f.season} · ${clubName(f.champion)}`),
      document.createTextNode(` def. ${clubName(f.runnerUp)}, ${scoreText(f)}`)],
  });

  /* ---------- Champions and runners-up ---------- */

  (function championsTable() {
    const root = document.getElementById("champions-table");
    const seasons = (list) => list.map((f) => f.season).join(", ") || "–";
    const byClub = () => {
      const ids = new Set(finals.flatMap((f) => [f.champion, f.runnerUp]));
      const rows = [...ids].map((id) => ({ id, won: finals.filter((f) => f.champion === id), lost: finals.filter((f) => f.runnerUp === id) }))
        .sort((a, b) => b.won.length - a.won.length || b.lost.length - a.lost.length || d3.ascending(clubName(a.id), clubName(b.id)));
      F.richTable(root, [
        { label: "Club", render: (r) => F.withSub(F.clubLabel(r.id, true), `Won: ${seasons(r.won)} · Lost: ${seasons(r.lost)}`) },
        { label: "Titles", cls: "num strong", render: (r) => String(r.won.length) },
        { label: "Runners-up", short: "R-up", cls: "num", render: (r) => String(r.lost.length) },
        { label: "Finals", cls: "num", render: (r) => String(r.won.length + r.lost.length) },
        { label: "Seasons won", cls: "years", render: (r) => seasons(r.won) },
        { label: "Seasons runner-up", cls: "years", render: (r) => seasons(r.lost) },
      ], rows);
    };
    const everyFinal = () => F.richTable(root, [
      { label: "Season", render: (f) => f.season },
      { label: "Champion", render: (f) => F.clubLabel(f.champion, true) },
      { label: "Score", cls: "score", render: (f) => scoreText(f) },
      { label: "Runner-up", render: (f) => F.clubLabel(f.runnerUp, true) },
    ], finals.slice().reverse());
    Viz.segmented("champions-tabs", [{ key: "club", label: "By club" }, { key: "final", label: "Every final" }], "club",
      (k) => (k === "club" ? byClub() : everyFinal()));
    byClub();
  })();

  /* ---------- Most repeated finals ---------- */

  F.repeatedFinals(document.getElementById("pairs-list"), finals, (f) => `${f.season} ${clubName(f.champion)} (${scoreText(f)})`);

  /* ---------- Countries ---------- */

  (function countriesSection() {
    const codes = new Set(finals.flatMap((f) => [nation(f.championCountry), nation(f.runnerUpCountry)]));
    const groups = [...codes].map((code) => {
      const won = finals.filter((f) => nation(f.championCountry) === code);
      return {
        label: countryName(code), icon: F.flag(code), won,
        lost: finals.filter((f) => nation(f.runnerUpCountry) === code),
        winners: d3.groups(won, (f) => f.champion).sort((a, b) => b[1].length - a[1].length),
      };
    }).sort((a, b) => b.won.length - a.won.length || b.lost.length - a.lost.length);
    document.getElementById("country-note").textContent =
      `${groups.filter((r) => r.won.length).length} countries have produced a champion and ${groups.length} have reached a final.` +
      (finals.some((f) => f.championCountry === "FRG" || f.runnerUpCountry === "FRG") ? " West Germany is counted with Germany." : "");
    F.groupRows(document.getElementById("countries-list"), groups, "Country");
  })();

  /* ---------- All-time points table ---------- */

  (function pointsTable() {
    const rows = data.alltime.slice().sort((a, b) => b.pts - a.pts || (b.gf - b.ga) - (a.gf - a.ga)).slice(0, 30);
    document.getElementById("points-note").textContent = `${data.meta.pointsRule}. Top ${rows.length} clubs.`;
    const sign = (n) => (n > 0 ? `+${n}` : String(n));
    F.richTable(document.getElementById("points-table"), [
      { label: "#", cls: "num rank", render: (r) => String(rows.indexOf(r) + 1) },
      { label: "Club", render: (r) => F.clubLabel(r.club, true) },
      { label: "Seasons", short: "Ssn", cls: "num", render: (r) => String(r.part) },
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

  /* ---------- All-time club records ---------- */

  (function clubRecords() {
    const METRICS = [
      { key: "w", label: "Most wins", unit: "wins" },
      { key: "gf", label: "Most goals", unit: "goals" },
      { key: "part", label: "Most participations", unit: "seasons" },
      { key: "pts", label: "Most points", unit: "points" },
    ];
    let metric = "w";
    const top = () => data.alltime.slice().sort((a, b) => b[metric] - a[metric]).slice(0, 15);
    const container = d3.select("#records-chart");

    function draw(width) {
      const m = METRICS.find((d) => d.key === metric);
      const list = top();
      container.selectAll("*").remove();
      const narrow = width < 560;
      const rowH = 34;
      const barH = 18;
      const margin = { top: 4, right: 64, bottom: 4, left: narrow ? 150 : 210 };
      const height = margin.top + list.length * rowH + margin.bottom;
      const x = d3.scaleLinear().domain([0, d3.max(list, (r) => r[metric])]).range([0, width - margin.left - margin.right]);
      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", `${m.label}, all time`);
      svg.append("line").attr("class", "baseline").attr("x1", margin.left).attr("x2", margin.left).attr("y1", 0).attr("y2", height);
      const g = svg.selectAll("g.row").data(list).join("g").attr("class", "row mark-group")
        .attr("transform", (d, i) => `translate(${margin.left},${margin.top + i * rowH})`);
      g.append("rect").attr("x", -margin.left).attr("width", width).attr("height", rowH).attr("fill", "transparent");
      g.append("text").attr("class", "label-name").attr("x", -56).attr("y", rowH / 2).attr("dy", "0.35em").attr("text-anchor", "end")
        .text((d) => F.fit(clubName(d.club), narrow));
      g.append("g").attr("transform", `translate(-50,${(rowH - 15) / 2})`).each(function (d) { F.svgFlag(d3.select(this), d.country); });
      g.append("g").attr("transform", `translate(-14,${rowH / 2})`).each(function (d) { F.svgCrest(d3.select(this), d.club, 22); });
      g.append("path").attr("class", "mark").attr("fill", "var(--ink-2)").attr("d", (d) => barPath(0, (rowH - barH) / 2, x(d[metric]), barH));
      g.append("text").attr("class", "label-value").attr("x", (d) => x(d[metric]) + 8).attr("y", rowH / 2).attr("dy", "0.35em").text((d) => d[metric]);
      tooltipOn(g, (t, d) => {
        t.append(ttTitle(clubName(d.club)));
        t.append(Viz.ttRow("var(--ink-2)", d[metric], m.unit));
        t.append(ttNote(`${d.part} seasons · ${d.pld} played · ${d.w}W ${d.d}D ${d.l}L · goals ${d.gf}–${d.ga} · ${d.pts} pts`));
      });
    }

    function renderTable() {
      table("records-table", ["Club", "Country", "Seasons", "Played", "W", "D", "L", "GF", "GA", "Pts"],
        top().map((r) => [clubName(r.club), countryName(r.country), String(r.part), String(r.pld), String(r.w), String(r.d), String(r.l), String(r.gf), String(r.ga), String(r.pts)]));
    }

    const rerender = responsive("records-chart", draw);
    renderTable();
    Viz.segmented("records-tabs", METRICS, metric, (k) => {
      metric = k;
      rerender();
      renderTable();
    });
  })();

  /* ---------- Players ---------- */

  (function players() {
    const root = document.getElementById("players-table");
    const playerCell = (p) => {
      const span = el("span", "club");
      span.append(F.flag(p.nation), document.createTextNode(p.player));
      return F.withSub(span, p.clubs.join(", "));
    };
    function ranked(list, key) {
      const sorted = list.slice().sort((a, b) => b[key] - a[key]);
      let rank = 0;
      return sorted.map((p, i) => ({ ...p, rank: i > 0 && sorted[i - 1][key] === p[key] ? rank : (rank = i + 1) }));
    }
    const views = {
      scorers: () => F.richTable(root, [
        { label: "#", cls: "num rank", render: (p) => String(p.rank) },
        { label: "Player", render: playerCell },
        { label: "Goals", cls: "num strong", render: (p) => String(p.goals) },
        { label: "Apps", cls: "num", render: (p) => (p.apps != null ? String(p.apps) : "–") },
        { label: "Goals per game", short: "Ratio", cls: "num", render: (p) => (p.apps ? (p.goals / p.apps).toFixed(2) : "–") },
        { label: "Clubs", cls: "years", render: (p) => p.clubs.join(", ") },
      ], ranked(data.scorers, "goals").slice(0, 25)),
      appearances: () => F.richTable(root, [
        { label: "#", cls: "num rank", render: (p) => String(p.rank) },
        { label: "Player", render: playerCell },
        { label: "Appearances", short: "Apps", cls: "num strong", render: (p) => String(p.apps) },
        { label: "Years", cls: "num", render: (p) => p.years ?? "–" },
        { label: "Clubs", cls: "years", render: (p) => p.clubs.join(", ") },
      ], ranked(data.appearances, "apps").slice(0, 25)),
    };
    Viz.segmented("players-tabs", [{ key: "scorers", label: "Top scorers" }, { key: "appearances", label: "Most appearances" }], "scorers",
      (k) => views[k]());
    views.scorers();
  })();

  document.getElementById("data-through").textContent = `Covers every final through ${data.meta.through}.`;
})();
