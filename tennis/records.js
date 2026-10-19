/* ATP and WTA Records: Open Era career leaders. The page sets data-src. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote } = Viz;
  const raw = await d3.json(document.body.dataset.src);
  const players = raw.players;
  const SURFACES = ["Hard", "Clay", "Grass", "Carpet"];
  const SURFACE_COLOR = { Hard: "var(--series-1)", Clay: "var(--series-2)", Grass: "var(--series-3)", Carpet: "var(--series-4)" };
  const slug = (s) => s.normalize("NFKD").replace(/[^\w]+/g, "-").toLowerCase();
  const nationOf = { ...raw.titlistNations, ...Object.fromEntries(players.map((p) => [p.name, p.nation])) };

  const entities = {};
  Object.keys(nationOf).forEach((n) => (entities[slug(n)] = { name: n, country: nationOf[n], crest: null }));
  const F = Football({ clubs: entities, countries: raw.countries });
  const WTA = raw.meta.tour === "wta";
  const pct = (w, l) => (w + l ? (100 * w) / (w + l) : 0);
  const fmtPct = (v) => `${v.toFixed(1)}%`;
  const who = (p) => {
    const span = el("span", "club");
    span.append(F.flag(p.nation), document.createTextNode(p.name));
    return span;
  };

  /* ---------- Stat tiles ---------- */

  const top = (key) => players.slice().sort((a, b) => key(b) - key(a))[0];
  const tTitles = top((p) => p.titles);
  const tWeeks = top((p) => p.weeks);
  const tWins = top((p) => p.won);
  const tPct = top((p) => (p.won + p.lost >= 300 ? pct(p.won, p.lost) : 0));
  F.statTiles("stats", [
    { label: "Most titles", value: String(tTitles.titles), detail: tTitles.name },
    { label: "Most weeks at No. 1", value: String(tWeeks.weeks), detail: tWeeks.name },
    { label: "Most matches won", value: d3.format(",")(tWins.won), detail: `${tWins.name}, ${tWins.won}–${tWins.lost}` },
    { label: "Best win percentage", value: fmtPct(pct(tPct.won, tPct.lost)), detail: `${tPct.name} (min. 300 matches)` },
  ]);

  /* ---------- Race: career titles by year ---------- */

  const years = Object.keys(raw.titlesByYear).map(Number).sort((a, b) => a - b);
  const tally = new Map();
  const frames = [{ label: String(years[0]), event: null, ranked: [] }];
  years.forEach((y) => {
    const won = raw.titlesByYear[y];
    Object.entries(won).forEach(([name, n]) => tally.set(name, (tally.get(name) || 0) + n));
    const best = Object.entries(won).sort((a, b) => b[1] - a[1])[0];
    const ranked = [...tally].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([name, n]) => ({ id: slug(name), n }));
    frames.push({ label: String(y), event: { year: y, name: best[0], n: best[1] }, ranked });
  });
  F.race(frames, {
    colorOf: () => "var(--series-1)",
    icons: false,
    frameMs: 700,
    emptyTicker: "Press play to start in 1968, the first year of the Open Era.",
    ticker: (e) => [F.flag(nationOf[e.name]), el("strong", null, ` ${e.year}`), document.createTextNode(` · most titles that year: ${e.name} (${e.n})`)],
  });

  /* ---------- All-time leaders ---------- */

  const METRICS = [
    { key: "titles", label: "Titles", surfaced: true, value: (p, s) => (s ? p.surface[s].titles : p.titles) },
    { key: "weeks", label: "Weeks at No. 1", surfaced: false, value: (p) => p.weeks },
    { key: "won", label: "Matches won", surfaced: true, value: (p, s) => (s ? p.surface[s].won : p.won) },
    { key: "played", label: "Matches played", surfaced: true, value: (p, s) => (s ? p.surface[s].won + p.surface[s].lost : p.won + p.lost) },
    {
      key: "pct", label: "Win %", surfaced: true, pct: true,
      value: (p, s) => {
        const w = s ? p.surface[s].won : p.won;
        const l = s ? p.surface[s].lost : p.lost;
        return w + l >= (s ? 100 : 300) ? pct(w, l) : 0;
      },
    },
  ];
  let metric = METRICS[0];
  let surface = "";
  function renderLeaders() {
    const s = metric.surfaced ? surface : "";
    const list = players.filter((p) => metric.value(p, s) > 0).sort((a, b) => metric.value(b, s) - metric.value(a, s)).slice(0, 20);
    F.rankList(document.getElementById("leaders-list"), list.map((p) => {
      const v = metric.value(p, s);
      const w = s ? p.surface[s].won : p.won;
      const l = s ? p.surface[s].lost : p.lost;
      return {
        icon: F.flag(p.nation), label: p.name, value: metric.pct ? Number(v.toFixed(1)) : v,
        second: metric.key === "weeks" ? null : `${w}–${l}`, color: s ? SURFACE_COLOR[s] : "var(--ink-2)",
        tip: (t) => {
          t.append(ttTitle(p.name));
          t.append(ttNote(`${p.titles} titles · ${p.won}–${p.lost} (${fmtPct(pct(p.won, p.lost))}) · ${p.weeks} weeks at No. 1`));
          SURFACES.forEach((x) => {
            const r = p.surface[x];
            if (r.won + r.lost) t.append(Viz.ttRow(SURFACE_COLOR[x], r.titles, `${x}: titles · ${r.won}–${r.lost}`));
          });
        },
      };
    }), [metric.label, metric.pct ? "%" : "Total", metric.key === "weeks" ? "" : "W–L"]);
    document.getElementById("leaders-surface").style.opacity = metric.surfaced ? 1 : 0.4;
  }
  Viz.segmented("leaders-metric", METRICS, metric.key, (k) => { metric = METRICS.find((m) => m.key === k); renderLeaders(); });
  Viz.segmented("leaders-surface", [{ key: "", label: "All" }, ...SURFACES.map((x) => ({ key: x, label: x }))], "", (k) => { surface = k; renderLeaders(); });
  renderLeaders();

  /* ---------- Kings of each surface ---------- */

  const grid = document.getElementById("surface-grid");
  SURFACES.forEach((s) => {
    const card = el("div", "card");
    const h = el("h3", "sub", s);
    card.append(h);
    const list = el("div");
    card.append(list);
    grid.append(card);
    const leaders = players.filter((p) => p.surface[s].titles).sort((a, b) => b.surface[s].titles - a.surface[s].titles || b.surface[s].won - a.surface[s].won).slice(0, 8);
    F.rankList(list, leaders.map((p) => ({
      icon: F.flag(p.nation), label: p.name, value: p.surface[s].titles, color: SURFACE_COLOR[s],
      second: `${fmtPct(pct(p.surface[s].won, p.surface[s].lost))}`,
      tip: (t) => { t.append(ttTitle(`${p.name} on ${s.toLowerCase()}`)); t.append(ttNote(`${p.surface[s].titles} titles · ${p.surface[s].won}–${p.surface[s].lost}`)); },
    })), ["Player", "Titles", "Win %"]);
  });

  /* ---------- Career records table ---------- */

  const tableRows = players.filter((p) => p.titles >= 10 || p.weeks).sort((a, b) => b.titles - a.titles || b.won - a.won);
  F.richTable(document.getElementById("players-table"), [
    { label: "#", cls: "num rank", render: (p) => String(tableRows.indexOf(p) + 1) },
    { label: "Player", render: (p) => F.withSub(who(p), SURFACES.map((s) => `${s} ${p.surface[s].won}–${p.surface[s].lost}`).join(" · ")) },
    { label: "Titles", cls: "num strong", render: (p) => String(p.titles) },
    { label: "Slams", cls: "num hide-sm", render: (p) => String(p.levels.G) },
    { label: WTA ? "WTA 1000" : "Masters", cls: "num hide-sm", render: (p) => String(p.levels.M) },
    { label: "Weeks No. 1", short: "No. 1", cls: "num", render: (p) => String(p.weeks || "–") },
    { label: "Won", cls: "num hide-sm", render: (p) => String(p.won) },
    { label: "Played", cls: "num", render: (p) => String(p.won + p.lost) },
    { label: "Win %", cls: "num", render: (p) => fmtPct(pct(p.won, p.lost)) },
    ...SURFACES.map((s) => ({ label: s, cls: "num hide-sm", render: (p) => String(p.surface[s].titles) })),
  ], tableRows);

  /* ---------- Nations ---------- */

  const NATION_METRICS = [
    { key: "titles", label: "Titles", second: "players", secondLabel: "Players" },
    { key: "players", label: "Title-winning players", second: "titles", secondLabel: "Titles" },
    { key: "won", label: "Match wins", second: null },
    { key: "weeks", label: "Weeks at No. 1", second: "no1", secondLabel: "No. 1s" },
  ];
  function renderNations(key) {
    const m = NATION_METRICS.find((x) => x.key === key);
    const rows = raw.nations.filter((n) => n[key] > 0).sort((a, b) => b[key] - a[key]).slice(0, 25);
    F.rankList(document.getElementById("nations-list"), rows.map((n) => {
      const stars = players.filter((p) => p.nation === n.nation).sort((a, b) => b.titles - a.titles).slice(0, 5);
      return {
        icon: F.flag(n.nation), label: F.countryName(n.nation), value: n[key], second: m.second ? n[m.second] : null, color: "var(--series-1)",
        tip: (t) => {
          t.append(ttTitle(F.countryName(n.nation)));
          t.append(ttNote(`${n.titles} titles by ${n.players} players · ${d3.format(",")(n.won)} match wins · ${n.no1} No. 1s (${n.weeks} weeks)`));
          stars.forEach((p) => t.append(Viz.ttRow("var(--series-1)", p.titles, p.name)));
        },
      };
    }), ["Nation", m.label, m.secondLabel ?? ""]);
  }
  Viz.segmented("nations-tabs", NATION_METRICS, "titles", renderNations);
  renderNations("titles");

  /* ---------- Year-end No. 1 ---------- */

  const byName = Object.fromEntries(players.map((p) => [p.name, p]));
  F.richTable(document.getElementById("year-end-table"), [
    { label: "Year", render: (y) => String(y.year) },
    { label: "Player", render: (y) => who({ name: y.player, nation: byName[y.player]?.nation ?? nationOf[y.player] }) },
    { label: "Times", cls: "num", render: (y) => String(raw.yearEnd.filter((z) => z.player === y.player && z.year <= y.year).length) },
  ], raw.yearEnd.slice().reverse());

  document.getElementById("data-through").textContent = `${raw.meta.through}.`;
})();
