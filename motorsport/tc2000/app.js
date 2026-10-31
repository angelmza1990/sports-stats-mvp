/* TC2000: Argentina's touring-car champions since 1979, race wins, poles and the current season. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote, ttRow } = Viz;
  const raw = await d3.json(document.body.dataset.src);
  const { drivers, champions, meta } = raw;

  // Makes in a fixed order, so each keeps its color whatever is on screen.
  const MAKES = {
    Renault: { country: "FRA" }, Ford: { country: "USA" }, Toyota: { country: "JPN" }, Chevrolet: { country: "USA" },
    Honda: { country: "JPN" }, Volkswagen: { country: "GER" }, Peugeot: { country: "FRA" }, Dodge: { country: "USA" },
  };
  const makeColor = (m) => (MAKES[m] ? `var(--mk-${m.toLowerCase()})` : "var(--mk-other)");
  const countries = {
    ARG: { name: "Argentina", flag: "ar" }, FRA: { name: "France", flag: "fr" }, USA: { name: "United States", flag: "us" },
    JPN: { name: "Japan", flag: "jp" }, GER: { name: "Germany", flag: "de" },
  };

  // One lookup for drivers, makes and teams (prefixed ids) so the race can switch between them.
  const entities = {};
  Object.entries(drivers).forEach(([id, d]) => (entities[`d:${id}`] = { name: d.name, country: "ARG", crest: null }));
  Object.entries(MAKES).forEach(([m, x]) => (entities[`m:${m}`] = { name: m, country: x.country, crest: null }));
  champions.forEach((c) => (entities[`t:${c.outfit}`] = { name: c.outfit, country: "ARG", crest: null }));
  const F = Football({ clubs: entities, countries });
  const name = (id) => drivers[id]?.name ?? id;
  const surname = (id) => {
    const n = name(id);
    const m = n.match(/(del Río|Ponce de León|Di Palma|Bessone II|Fernandino II)$/);
    return m ? m[1] : n.split(" ").slice(-1)[0];
  };
  const makeLabel = (m) => {
    const span = el("span", "club");
    const dot = el("span", "make-dot");
    dot.style.setProperty("--c", makeColor(m));
    span.append(dot, document.createTextNode(m));
    return span;
  };
  const latest = champions[champions.length - 1];
  const winsOf = Object.fromEntries(raw.wins.map((w) => [w.driver, w]));
  const fmtDate = (d) => (d ? new Date(d.date + "T00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) + `, ${d.place}` : "–");

  /* ---------- Stat tiles ---------- */

  const titles = d3.rollup(champions, (v) => v.length, (c) => c.driver);
  const [topDriver, topN] = d3.greatest(titles, (d) => d[1]);
  const totalWins = d3.sum(raw.wins, (w) => w.wins);
  const makeTitles = d3.rollup(champions, (v) => v.length, (c) => c.brand);
  const [topMake, topMakeN] = d3.greatest(makeTitles, (d) => d[1]);
  F.statTiles("stats", [
    { label: "Championships", value: String(champions.length), detail: `${champions[0].season} to ${latest.season}, ${titles.size} different champions` },
    { label: "Most titles", value: String(topN), detail: `${name(topDriver)} (${champions.filter((c) => c.driver === topDriver).map((c) => c.season).join(", ")})` },
    { label: "Most race wins", value: String(raw.wins[0].wins), detail: `${name(raw.wins[0].driver)} · ${totalWins} races won by ${raw.wins.length} drivers since 1980` },
    { label: "Latest champion", value: surname(latest.driver), detail: `${latest.season}, ${latest.car} · ${topMake} leads the makes with ${topMakeN}` },
  ]);

  /* ---------- Bar chart race ---------- */

  const RACES = {
    drivers: {
      label: "Drivers",
      champion: (c) => `d:${c.driver}`,
      ticker: (c) => [el("strong", null, `${c.season} · ${name(c.driver)}`), document.createTextNode(` · ${c.car} · ${c.team}`)],
      color: () => "var(--series-1)",
    },
    makes: {
      label: "Makes",
      champion: (c) => `m:${c.brand}`,
      ticker: (c) => [el("strong", null, `${c.season} · ${c.brand}`), document.createTextNode(` · ${c.car} · ${name(c.driver)}`)],
      color: (id) => makeColor(id.slice(2)),
    },
    teams: {
      label: "Teams",
      champion: (c) => `t:${c.outfit}`,
      ticker: (c) => [el("strong", null, `${c.season} · ${c.outfit}`), document.createTextNode(` · ${c.team === c.outfit ? "" : c.team + " · "}${name(c.driver)}`)],
      color: () => "var(--series-2)",
    },
  };
  let current = "drivers";
  const framesFor = (k) => {
    const events = champions.map((c) => ({ ...c, champion: RACES[k].champion(c) }));
    return F.titleFrames(events, (e) => String(e.season), String(events[0].season));
  };
  const race = F.race(framesFor("drivers"), {
    colorOf: (id) => RACES[current].color(id),
    icons: false,
    emptyTicker: "Press play to start with the first season, 1979.",
    ticker: (e) => RACES[current].ticker(e),
    frameMs: 560,
  });
  Viz.segmented("race-metric", Object.entries(RACES).map(([key, r]) => ({ key, label: r.label })), "drivers", (k) => {
    current = k;
    d3.selectAll("#race-chart g.row").remove(); // repaint bars in the new colors
    race.setFrames(framesFor(k));
  });

  /* ---------- The eras of each make ---------- */

  (function eras() {
    const strip = document.getElementById("era-strip");
    const axis = document.getElementById("era-axis");
    const n = champions.length;
    strip.style.setProperty("--n", n);
    axis.style.setProperty("--n", n);
    const present = [...new Set(champions.map((c) => c.brand))].sort((a, b) => Object.keys(MAKES).indexOf(a) - Object.keys(MAKES).indexOf(b));
    Viz.legend("era-legend", present.map((m) => ({ label: `${m} (${makeTitles.get(m)})`, color: makeColor(m) })));
    champions.forEach((c, i) => {
      const cell = el("div", `era-cell${c.era === "Súper TC2000" ? " super" : ""}`);
      cell.style.setProperty("--c", makeColor(c.brand));
      cell.setAttribute("role", "listitem");
      cell.tabIndex = 0;
      cell.setAttribute("aria-label", `${c.season}: ${c.brand}, ${c.car}, ${name(c.driver)}`);
      Viz.tooltipOnNode(cell, (t) => {
        t.append(ttTitle(`${c.season} · ${c.brand}`), ttRow(makeColor(c.brand), name(c.driver), c.car));
        t.append(ttNote(`${c.team}${c.wins != null ? ` · ${c.wins} wins` : ""}${c.era === "Súper TC2000" ? " · Súper TC2000" : ""}`));
      });
      strip.append(cell);
      // Decades, plus the first and last seasons when they are not next to a decade.
      const shown = c.season % 10 === 0 ? c.season > champions[0].season + 2 : i === 0 || (i === n - 1 && c.season % 10 > 2);
      const label = el("span", i === n - 1 ? "last" : null, shown ? String(c.season) : "");
      label.style.gridRow = "1";
      axis.append(label);
    });
    const from = champions.findIndex((c) => c.era === "Súper TC2000");
    const to = champions.findLastIndex((c) => c.era === "Súper TC2000");
    if (from >= 0) {
      const sup = el("span", "super-label", "Súper TC2000");
      sup.style.gridRow = "2";
      sup.style.gridColumn = `${from + 1} / ${to + 2}`;
      axis.append(sup);
    }
    Viz.table("era-table", ["Season", "Make", "Car", "Champion"], champions.map((c) => [String(c.season), c.brand, c.car, name(c.driver)]));
  })();

  /* ---------- Every champion ---------- */

  F.richTable(document.getElementById("champions-table"), [
    { label: "Season", render: (c) => String(c.season) },
    { label: "Driver", render: (c) => F.withSub(document.createTextNode(name(c.driver)), [drivers[c.driver]?.province, c.era === "Súper TC2000" ? "Súper TC2000" : null].filter(Boolean).join(" · ")) },
    { label: "Car", cls: "hide-sm", render: (c) => F.withSub(makeLabel(c.brand), c.car) },
    { label: "Team", cls: "hide-sm", render: (c) => F.withSub(document.createTextNode(c.team), c.outfit !== c.team ? c.outfit : "") },
    { label: "Wins", cls: "num strong", render: (c) => (c.wins == null ? "–" : String(c.wins)) },
  ], champions.slice().reverse());

  /* ---------- Titles by driver, make, team and province ---------- */

  function groupBy(keyOf) {
    return d3.groups(champions, keyOf).sort((a, b) => b[1].length - a[1].length || d3.min(a[1], (c) => c.season) - d3.min(b[1], (c) => c.season));
  }
  const seasonsTip = (title, list, color, who) => (t) => {
    t.append(ttTitle(`${title}: ${list.length} ${list.length === 1 ? "title" : "titles"}`));
    t.append(ttNote(list.map((c) => `${c.season} ${who(c)}`).join(" · ")));
  };
  const BREAKDOWN = {
    drivers: {
      label: "Drivers", headers: ["Driver", "Titles", "Race wins"],
      rows: () => groupBy((c) => c.driver).map(([id, list]) => ({
        icon: el("span"), label: name(id), value: list.length, second: winsOf[id]?.wins ?? "–", color: "var(--series-1)",
        tip: seasonsTip(name(id), list, "var(--series-1)", (c) => `${c.car} (${c.team})`),
      })),
    },
    makes: {
      label: "Makes", headers: ["Make", "Titles", "Drivers"],
      rows: () => groupBy((c) => c.brand).map(([m, list]) => ({
        icon: F.flag(MAKES[m]?.country), label: m, value: list.length, second: new Set(list.map((c) => c.driver)).size, color: makeColor(m),
        tip: seasonsTip(m, list, makeColor(m), (c) => `${surname(c.driver)} (${c.car})`),
      })),
    },
    teams: {
      label: "Teams", headers: ["Team", "Titles", "Drivers"],
      rows: () => groupBy((c) => c.outfit).map(([t, list]) => ({
        icon: el("span"), label: t, value: list.length, second: new Set(list.map((c) => c.driver)).size, color: "var(--series-2)",
        tip: seasonsTip(t, list, "var(--series-2)", (c) => `${surname(c.driver)} (${c.team})`),
      })),
    },
    provinces: {
      label: "Provinces", headers: ["Province", "Titles", "Drivers"],
      rows: () => groupBy((c) => drivers[c.driver]?.province ?? "–").map(([p, list]) => ({
        icon: el("span"), label: p, value: list.length, second: new Set(list.map((c) => c.driver)).size, color: "var(--series-3)",
        tip: seasonsTip(p, list, "var(--series-3)", (c) => surname(c.driver)),
      })),
    },
  };
  const renderBreakdown = (k) => F.rankList(document.getElementById("breakdown-list"), BREAKDOWN[k].rows(), BREAKDOWN[k].headers);
  Viz.segmented("breakdown-tabs", Object.entries(BREAKDOWN).map(([key, b]) => ({ key, label: b.label })), "drivers", renderBreakdown);
  renderBreakdown("drivers");

  /* ---------- Most race wins and poles ---------- */

  const RANKS = {
    wins: { label: "Race wins", list: raw.wins, field: "wins", noun: "wins", color: "var(--series-1)" },
    poles: { label: "Poles", list: raw.poles, field: "poles", noun: "poles", color: "var(--series-4)" },
  };
  function renderRank(k) {
    const r = RANKS[k];
    F.rankList(document.getElementById("wins-list"), r.list.slice(0, 30).map((w) => ({
      icon: el("span"), label: name(w.driver), value: w[r.field], second: titles.get(w.driver) || "", color: r.color,
      tip: (t) => {
        t.append(ttTitle(name(w.driver)), ttRow(r.color, w[r.field], r.noun));
        t.append(ttNote(`First: ${fmtDate(w.first)} · Last: ${fmtDate(w.last)}`));
      },
    })), ["Driver", r.label, "Titles"]);
  }
  Viz.segmented("wins-tabs", Object.entries(RANKS).map(([key, r]) => ({ key, label: r.label })), "wins", renderRank);
  renderRank("wins");

  /* ---------- The current season ---------- */

  const cs = raw.currentSeason;
  const rounds = d3.sum(cs.wins, (w) => w.n);
  document.getElementById("season-title").textContent = `The ${cs.year} season so far`;
  document.getElementById("season-lede").textContent = cs.year > meta.through
    ? `${rounds} rounds run, ${cs.wins.length} different winners. Hover a row for where each driver won or took pole.`
    : `${rounds} rounds, ${cs.wins.length} different winners.`;
  const seasonRows = (list, noun) => list.map((e) => ({
    icon: F.flag(MAKES[e.brand]?.country), label: name(e.driver), value: e.n, second: e.brand, color: makeColor(e.brand),
    tip: (t) => { t.append(ttTitle(name(e.driver)), ttRow(makeColor(e.brand), e.n, `${noun} · ${e.brand}`)); t.append(ttNote(e.places.join(" · "))); },
  }));
  F.rankList(document.getElementById("season-wins"), seasonRows(cs.wins, "wins"), ["Driver", "Wins", "Make"]);
  F.rankList(document.getElementById("season-poles"), seasonRows(cs.poles, "poles"), ["Driver", "Poles", "Make"]);

  /* ---------- Teams' championship ---------- */

  F.richTable(document.getElementById("teams-table"), [
    { label: "Season", render: (t) => String(t.season) },
    { label: "Team", render: (t) => F.withSub(document.createTextNode(t.team), t.outfit !== t.team ? t.outfit : "") },
    { label: "Car", render: (t) => t.car },
    { label: "Drivers' champion", cls: "hide-sm", render: (t) => { const c = champions.find((x) => x.season === t.season); return c ? `${name(c.driver)} (${c.team})` : "–"; } },
  ], raw.teamChampions.slice().reverse());

  /* ---------- Footer ---------- */

  const links = (id, items) => {
    const root = document.getElementById(id);
    items.forEach(([label, url], i) => {
      const a = el("a", null, label);
      a.href = url;
      root.append(a);
      if (i < items.length - 1) root.append(document.createTextNode(i === items.length - 2 ? " and " : ", "));
    });
  };
  links("sources", [["Turismo Competición 2000", meta.sources[0]], ["Súper TC2000", meta.sources[1]]]);
  links("site-sources", [["historic statistics", meta.sources[2]], [`${meta.current} statistics`, meta.sources[3]]]);
  document.getElementById("data-through").textContent = `Champions through ${meta.through}; race wins and poles include the current season (data from ${meta.generated}).`;
})();
