/* Formula 1: World Champions since 1950 and all-time race wins. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote } = Viz;
  const raw = await d3.json(document.body.dataset.src);
  const { drivers, constructors, champions } = raw;
  const cchamps = raw.constructorChampions;

  // One lookup for drivers, constructors and nations (prefixed ids) so the race can switch between them.
  const entities = {};
  Object.entries(drivers).forEach(([id, d]) => (entities[`d:${id}`] = { name: d.name, country: d.nation, crest: null }));
  Object.entries(constructors).forEach(([id, c]) => (entities[`c:${id}`] = { name: c.name, country: c.nation, crest: null }));
  Object.entries(raw.countries).forEach(([code, c]) => (entities[`n:${code}`] = { name: c.name, country: code, crest: null }));
  const F = Football({ clubs: entities, countries: raw.countries });
  const driverName = (id) => drivers[id]?.name ?? id;
  const constructorName = (id) => constructors[id]?.name ?? id;
  const countryName = F.countryName;

  const withFlag = (code, text) => {
    const span = el("span", "club");
    span.append(F.flag(code), document.createTextNode(text));
    return span;
  };
  const driverLabel = (id) => withFlag(drivers[id]?.nation, driverName(id));
  const constructorLabel = (id) => withFlag(constructors[id]?.nation, constructorName(id));

  /* ---------- Stat tiles ---------- */

  const dTitles = d3.rollup(champions, (v) => v.length, (c) => c.driver);
  const maxD = d3.max(dTitles.values());
  const leaders = [...dTitles].filter(([, n]) => n === maxD).map(([id]) => driverName(id));
  const cTitles = d3.rollup(cchamps, (v) => v.length, (c) => c.constructor);
  const [topC, topCN] = d3.greatest(cTitles, (d) => d[1]);
  const nations = d3.rollup(champions, (v) => v.length, (c) => drivers[c.driver].nation);
  const [topNation, topNationN] = d3.greatest(nations, (d) => d[1]);
  const latest = champions[champions.length - 1];
  F.statTiles("stats", [
    { label: "Championships", value: String(champions.length), detail: `${champions[0].season} to ${latest.season}, ${dTitles.size} different champions` },
    { label: "Most drivers' titles", value: String(maxD), detail: leaders.join(" and ") },
    { label: "Most constructors' titles", value: String(topCN), detail: constructorName(topC) },
    { label: "Latest champion", value: driverName(latest.driver).split(" ").slice(-1)[0], detail: `${latest.season}, ${latest.constructors.map(constructorName).join(" / ")} · ${countryName(topNation)} leads nations with ${topNationN}` },
  ]);

  /* ---------- Bar chart race ---------- */

  const RACES = {
    drivers: {
      label: "Drivers",
      events: () => champions.map((c) => ({ ...c, champion: `d:${c.driver}` })),
      ticker: (c) => [F.flag(drivers[c.driver].nation), el("strong", null, ` ${c.season} · ${driverName(c.driver)}`),
        document.createTextNode(` · ${c.constructors.map(constructorName).join(" / ")} · ${c.wins} wins`)],
      color: "var(--series-1)",
    },
    constructors: {
      label: "Constructors",
      events: () => cchamps.map((c) => ({ ...c, champion: `c:${c.constructor}` })),
      ticker: (c) => [F.flag(constructors[c.constructor].nation), el("strong", null, ` ${c.season} · ${constructorName(c.constructor)}`),
        document.createTextNode(` · ${c.engine} engine · ${c.drivers.join(", ")}`)],
      color: "var(--series-2)",
    },
    nations: {
      label: "Nationalities",
      events: () => champions.map((c) => ({ ...c, champion: `n:${drivers[c.driver].nation}` })),
      ticker: (c) => [F.flag(drivers[c.driver].nation), el("strong", null, ` ${c.season} · ${countryName(drivers[c.driver].nation)}`),
        document.createTextNode(` · ${driverName(c.driver)}`)],
      color: "var(--series-3)",
    },
  };
  let current = "drivers";
  const framesFor = (k) => {
    const events = RACES[k].events();
    return F.titleFrames(events, (e) => String(e.season), String(events[0].season));
  };
  const race = F.race(framesFor("drivers"), {
    colorOf: () => RACES[current].color,
    icons: false,
    emptyTicker: "Press play to start with the first World Championship, 1950.",
    ticker: (e) => RACES[current].ticker(e),
    frameMs: 520,
  });
  Viz.segmented("race-metric", Object.entries(RACES).map(([key, r]) => ({ key, label: r.label })), "drivers", (k) => {
    current = k;
    d3.selectAll("#race-chart g.row").remove(); // repaint bars in the new color
    race.setFrames(framesFor(k));
  });

  /* ---------- Every champion ---------- */

  (function championsTable() {
    const root = document.getElementById("champions-table");
    const views = {
      drivers: () => F.richTable(root, [
        { label: "Season", render: (c) => String(c.season) },
        { label: "Driver", render: (c) => F.withSub(driverLabel(c.driver), c.constructors.map(constructorName).join(" / ")) },
        { label: "Constructor", cls: "hide-sm", render: (c) => { const w = el("div", "stack-clubs"); c.constructors.forEach((id) => w.append(constructorLabel(id))); return w; } },
        { label: "Engine", cls: "hide-sm", render: (c) => c.engine || "–" },
        { label: "Age", cls: "num hide-sm", render: (c) => String(c.age ?? "–") },
        { label: "Wins", cls: "num strong", render: (c) => String(c.wins ?? "–") },
        { label: "Poles", cls: "num", render: (c) => String(c.poles ?? "–") },
        { label: "Points", short: "Pts", cls: "num hide-sm", render: (c) => String(c.points ?? "–") },
      ], champions.slice().reverse()),
      constructors: () => F.richTable(root, [
        { label: "Season", render: (c) => String(c.season) },
        { label: "Constructor", render: (c) => F.withSub(constructorLabel(c.constructor), c.drivers.join(", ")) },
        { label: "Engine", render: (c) => c.engine || "–" },
        { label: "Drivers", cls: "years", render: (c) => c.drivers.join(", ") },
        { label: "Wins", cls: "num strong", render: (c) => String(c.wins ?? "–") },
      ], cchamps.slice().reverse()),
    };
    Viz.segmented("champions-tabs", [{ key: "drivers", label: "Drivers' champions" }, { key: "constructors", label: "Constructors' champions" }], "drivers", (k) => views[k]());
    views.drivers();
  })();

  /* ---------- By nationality and constructor ---------- */

  const byNation = d3.groups(champions, (c) => drivers[c.driver].nation).sort((a, b) => b[1].length - a[1].length);
  F.rankList(document.getElementById("by-nation"), byNation.map(([code, list]) => {
    const who = d3.rollups(list, (v) => v.map((c) => c.season), (c) => c.driver).sort((a, b) => b[1].length - a[1].length);
    return {
      icon: F.flag(code), label: countryName(code), value: list.length, second: who.length, color: "var(--series-3)",
      tip: (t) => {
        t.append(ttTitle(`${countryName(code)}: ${list.length} titles`));
        who.forEach(([d, ys]) => t.append(Viz.ttRow("var(--series-3)", ys.length, `${driverName(d)} (${ys.join(", ")})`)));
      },
    };
  }), ["Nation", "Titles", "Drivers"]);

  function constructorBreakdown(kind) {
    const pairs = kind === "drivers"
      ? champions.flatMap((c) => c.constructors.map((id) => ({ id, season: c.season, who: driverName(c.driver) })))
      : cchamps.map((c) => ({ id: c.constructor, season: c.season, who: c.drivers.join(" & ") }));
    const groups = d3.groups(pairs, (p) => p.id).sort((a, b) => b[1].length - a[1].length);
    F.rankList(document.getElementById("by-constructor"), groups.map(([id, list]) => ({
      icon: F.flag(constructors[id]?.nation), label: constructorName(id), value: list.length,
      second: kind === "drivers" ? new Set(list.map((p) => p.who)).size : null, color: "var(--series-2)",
      tip: (t) => {
        t.append(ttTitle(`${constructorName(id)}: ${list.length} ${kind === "drivers" ? "drivers' titles" : "constructors' titles"}`));
        t.append(ttNote(list.map((p) => `${p.season} ${p.who}`).join(" · ")));
      },
    })), ["Constructor", "Titles", kind === "drivers" ? "Drivers" : ""]);
  }
  Viz.segmented("constructor-tabs", [{ key: "drivers", label: "Drivers' titles" }, { key: "constructors", label: "Constructors' titles" }], "drivers", constructorBreakdown);
  constructorBreakdown("drivers");

  /* ---------- Most Grand Prix wins ---------- */

  const WINS = {
    drivers: () => raw.driverWins.slice(0, 25).map((w) => ({
      icon: F.flag(drivers[w.driver].nation), label: driverName(w.driver), value: w.wins, color: "var(--series-1)",
      tip: (t) => { t.append(ttTitle(driverName(w.driver)), Viz.ttRow("var(--series-1)", w.wins, "wins")); t.append(ttNote(`First: ${w.first} · Last: ${w.last}`)); },
    })),
    constructors: () => raw.constructorWins.slice(0, 25).map((w) => ({
      icon: F.flag(constructors[w.constructor].nation), label: constructorName(w.constructor), value: w.wins, color: "var(--series-2)",
      tip: (t) => { t.append(ttTitle(constructorName(w.constructor)), Viz.ttRow("var(--series-2)", w.wins, "wins")); t.append(ttNote(`Active ${w.active} · first: ${w.first} · last: ${w.last}`)); },
    })),
    nations: () => raw.countryWins.map((w) => ({
      icon: F.flag(w.nation), label: countryName(w.nation), value: w.wins, second: w.drivers, color: "var(--series-3)",
      tip: (t) => { t.append(ttTitle(countryName(w.nation)), Viz.ttRow("var(--series-3)", w.wins, `wins by ${w.drivers} drivers`)); },
    })),
  };
  const HEADERS = { drivers: ["Driver", "Wins", ""], constructors: ["Constructor", "Wins", ""], nations: ["Nation", "Wins", "Drivers"] };
  const renderWins = (k) => F.rankList(document.getElementById("wins-list"), WINS[k](), HEADERS[k]);
  Viz.segmented("wins-tabs", [{ key: "drivers", label: "Drivers" }, { key: "constructors", label: "Constructors" }, { key: "nations", label: "Nationalities" }], "drivers", renderWins);
  renderWins("drivers");

  /* ---------- Footer ---------- */

  const src = document.getElementById("sources");
  const LABELS = ["Drivers' Champions", "Constructors' Champions", "Grand Prix winners", "Grand Prix winners by constructor"];
  raw.meta.sources.forEach((url, i) => {
    const a = el("a", null, LABELS[i] ?? url);
    a.href = url;
    src.append(a);
    if (i < raw.meta.sources.length - 1) src.append(document.createTextNode(", "));
  });
  document.getElementById("data-through").textContent = `Champions through ${raw.meta.through}; race wins include the current season.`;
})();
