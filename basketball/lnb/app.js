/* Liga Nacional de Básquet: every final since 1985, titles by club, city, coach and player, top scorers and records. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote, ttRow } = Viz;
  const raw = await d3.json(document.body.dataset.src);
  const { clubs, finals } = raw;
  const countries = {
    ARG: { name: "Argentina", flag: "ar" }, USA: { name: "United States", flag: "us" }, URU: { name: "Uruguay", flag: "uy" },
    BRA: { name: "Brazil", flag: "br" }, PUR: { name: "Puerto Rico", flag: "pr" }, VEN: { name: "Venezuela", flag: "ve" },
    DOM: { name: "Dominican Republic", flag: "do" }, PAR: { name: "Paraguay", flag: "py" }, CHI: { name: "Chile", flag: "cl" },
    CUB: { name: "Cuba", flag: "cu" }, PAN: { name: "Panama", flag: "pa" }, COL: { name: "Colombia", flag: "co" },
    MEX: { name: "Mexico", flag: "mx" }, BAH: { name: "Bahamas", flag: "bs" }, CAN: { name: "Canada", flag: "ca" },
  };
  // Clubs have no logo source here: Football's crest() draws a lettered badge for each.
  const entities = Object.fromEntries(Object.entries(clubs).map(([id, c]) => [id, { name: c.name, country: "ARG", crest: null }]));
  const F = Football({ clubs: entities, countries });
  const name = (id) => clubs[id]?.name ?? id;
  const latest = finals[finals.length - 1];
  const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
  const series = (f) => `${f.series[0]}–${f.series[1]}`;
  const person = (who, club) => F.withSub(document.createTextNode(who ?? "–"), club && who ? name(club) : "");

  /* ---------- Stat tiles ---------- */

  const titles = d3.rollup(finals, (v) => v.length, (f) => f.champion);
  const [top, topN] = d3.greatest(titles, (d) => d[1]);
  const topClubs = [...titles].filter(([, n]) => n === topN).map(([id]) => name(id));
  const players = raw.players;
  F.statTiles("stats", [
    { label: "Finals", value: String(finals.length), detail: `${finals[0].season} to ${latest.season}, ${titles.size} different champions` },
    { label: "Most titles", value: String(topN), detail: `${topClubs.join(", ")} (${finals.filter((f) => f.champion === top).map((f) => f.season).join(", ")})` },
    { label: "Most titles, player", value: String(players[0].titles), detail: `${players[0].name}, with ${new Set(finals.filter((f) => players[0].seasons.includes(f.season)).map((f) => f.champion)).size} clubs` },
    { label: "Latest champion", value: name(latest.champion), detail: `${latest.season}, ${series(latest)} against ${name(latest.runnerUp)}` },
  ]);

  /* ---------- Bar chart race ---------- */

  F.race(F.titleFrames(finals, (f) => f.season, "1985"), {
    colorOf: () => "var(--series-1)",
    icons: false,
    emptyTicker: "Press play to start with the first final, 1985.",
    ticker: (f) => [el("strong", null, `${f.season} · ${name(f.champion)}`), document.createTextNode(` · ${series(f)} against ${name(f.runnerUp)}`)],
    frameMs: 560,
  });

  /* ---------- Every final ---------- */

  F.richTable(document.getElementById("finals-table"), [
    { label: "Season", render: (f) => f.season },
    { label: "Champion", render: (f) => F.withSub(F.clubLabel(f.champion), f.championCity ?? clubs[f.champion]?.city ?? "") },
    { label: "Series", cls: "num strong", render: (f) => series(f) },
    { label: "Runner-up", render: (f) => F.clubLabel(f.runnerUp) },
    { label: "Coach", cls: "hide-sm", render: (f) => f.coach },
    { label: "Season MVP", cls: "hide-sm", render: (f) => person(f.mvp, f.mvpClub) },
    { label: "Finals MVP", cls: "hide-sm", render: (f) => person(f.finalsMvp, f.finalsMvpClub) },
  ], finals.slice().reverse());

  /* ---------- Titles by club, city, coach and player ---------- */

  const seasonsTip = (title, list) => (t) => {
    t.append(ttTitle(`${title}: ${plural(list.length, "title")}`));
    t.append(ttNote(list.join(" · ")));
  };
  const finalsOf = (id) => finals.filter((f) => f.champion === id || f.runnerUp === id);
  const BREAKDOWN = {
    clubs: {
      label: "Clubs", headers: ["Club", "Titles", "Finals"],
      rows: () => [...titles].sort((a, b) => b[1] - a[1] || finalsOf(b[0]).length - finalsOf(a[0]).length).map(([id, n]) => ({
        icon: F.crest(id), label: name(id), value: n, second: finalsOf(id).length, color: "var(--series-1)",
        tip: (t) => {
          t.append(ttTitle(`${name(id)} · ${clubs[id].city}`));
          t.append(ttRow("var(--series-1)", plural(n, "title"), ` in ${plural(finalsOf(id).length, "final")}`));
          t.append(ttNote(finals.filter((f) => f.champion === id).map((f) => f.season).join(" · ")));
        },
      })),
    },
    cities: {
      label: "Cities", headers: ["City", "Titles", "Clubs"],
      rows: () => d3.groups(finals, (f) => f.championCity ?? clubs[f.champion].city).sort((a, b) => b[1].length - a[1].length).map(([city, list]) => ({
        icon: el("span"), label: city, value: list.length, second: new Set(list.map((f) => f.champion)).size, color: "var(--series-2)",
        tip: seasonsTip(city, list.map((f) => `${f.season} ${name(f.champion)}`)),
      })),
    },
    coaches: {
      label: "Coaches", headers: ["Coach", "Titles", ""],
      rows: () => raw.coaches.map((c) => ({
        icon: F.flag(c.country), label: c.name, value: c.titles, second: "", color: "var(--series-3)", tip: seasonsTip(c.name, c.seasons),
      })),
    },
    players: {
      label: "Players", headers: ["Player", "Titles", "Clubs"],
      rows: () => players.map((p) => {
        const won = finals.filter((f) => p.seasons.includes(f.season));
        return {
          icon: F.flag(p.country), label: p.name, value: p.titles, second: new Set(won.map((f) => f.champion)).size, color: "var(--series-4)",
          tip: seasonsTip(p.name, won.length === p.seasons.length ? won.map((f) => `${f.season} ${name(f.champion)}`) : p.seasons),
        };
      }),
    },
  };
  const renderBreakdown = (k) => F.rankList(document.getElementById("breakdown-list"), BREAKDOWN[k].rows(), BREAKDOWN[k].headers);
  Viz.segmented("breakdown-tabs", Object.entries(BREAKDOWN).map(([key, b]) => ({ key, label: b.label })), "clubs", renderBreakdown);
  renderBreakdown("clubs");

  /* ---------- How the finals were decided ---------- */

  const results = d3.groups(finals, series).sort((a, b) => {
    const [x, y] = [a[1][0].series, b[1][0].series];
    return x[0] - y[0] || x[1] - y[1];
  });
  F.rankList(document.getElementById("series-list"), results.map(([s, list]) => {
    const [w, l] = list[0].series;
    const label = l === 0 ? `${s} sweep` : w - l === 1 ? `${s}, the deciding game` : s;
    return {
      icon: el("span"), label, value: list.length, second: `best of ${2 * w - 1}`, color: "var(--series-2)",
      tip: seasonsTip(`${s} finals`, list.map((f) => `${f.season} ${name(f.champion)}`)),
    };
  }), ["Result", "Finals", "Format"]);
  F.repeatedFinals(document.getElementById("repeated"), finals.map((f) => ({ ...f, year: f.year })), (f) => f.season, 8);

  /* ---------- Scorers and all-time leaders ---------- */

  const SCORERS = {
    season: {
      label: "Season top scorers",
      render: (root) => F.richTable(root, [
        { label: "Season", render: (s) => s.season },
        { label: "Player", render: (s) => F.withSub(document.createTextNode(s.player), countries[s.country]?.name ?? "") },
        { label: "Club", cls: "hide-sm", render: (s) => (s.club ? F.clubLabel(s.club) : s.clubName) },
        { label: "Games", cls: "num hide-sm", render: (s) => String(s.games ?? "–") },
        { label: "Points", cls: "num strong", render: (s) => d3.format(",")(s.points) },
        { label: "Per game", cls: "num", render: (s) => d3.format(".1f")(s.avg) },
      ], raw.topScorers.slice().reverse()),
    },
    points: { label: "Career points", cat: "Points", noun: "points", second: "Games" },
    games: { label: "Games played", cat: "Games played", noun: "games", second: "Seasons" },
  };
  function renderScorers(k) {
    const root = document.getElementById("scorer-list");
    root.replaceChildren();
    const s = SCORERS[k];
    if (s.render) {
      const box = el("div", "data-table tall");
      root.append(box);
      s.render(box);
      return;
    }
    F.rankList(root, raw.career[s.cat].map((p) => ({
      icon: F.flag(p.country), label: p.name, value: p.value, second: k === "points" ? p.games : p.seasons, color: "var(--series-1)",
      tip: (t) => {
        t.append(ttTitle(p.name), ttRow("var(--series-1)", d3.format(",")(p.value), ` ${s.noun}`));
        t.append(ttNote(`${plural(p.games, "game")} in ${plural(p.seasons, "season")}${k === "points" ? ` · ${d3.format(".1f")(p.value / p.games)} per game` : ""}`));
      },
    })), ["Player", s.label, s.second]);
  }
  Viz.segmented("scorer-tabs", Object.entries(SCORERS).map(([key, s]) => ({ key, label: s.label })), "season", renderScorers);
  renderScorers("season");

  /* ---------- All-time records ---------- */

  F.richTable(document.getElementById("records-table"), [
    { label: "Statistic", render: ([cat]) => cat },
    { label: "Player", render: ([, list]) => F.withSub(document.createTextNode(list[0].name), countries[list[0].country]?.name ?? "") },
    { label: "Record", cls: "num strong", render: ([cat, list]) => (cat === "Points per game" ? d3.format(".1f")(list[0].value) : d3.format(",")(list[0].value)) },
    { label: "Games", cls: "num hide-sm", render: ([, list]) => String(list[0].games) },
    { label: "Seasons", cls: "num hide-sm", render: ([, list]) => String(list[0].seasons) },
  ], Object.entries(raw.career));

  /* ---------- Seasons in the league ---------- */

  const byStay = Object.entries(clubs).sort((a, b) => b[1].seasons - a[1].seasons || a[1].name.localeCompare(b[1].name));
  const now = byStay.filter(([, c]) => c.current).length;
  document.getElementById("clubs-lede").textContent =
    `${Object.keys(clubs).length} clubs have played the Liga Nacional; these are the 25 with the most seasons. A darker bar marks the ${now} clubs in this season's league.`;
  F.rankList(document.getElementById("clubs-list"), byStay.slice(0, 25).map(([id, c]) => ({
    icon: F.crest(id), label: c.name, value: c.seasons, second: titles.get(id) ?? "", color: c.current ? "var(--series-1)" : "var(--series-1-soft, var(--axis))",
    tip: (t) => {
      t.append(ttTitle(`${c.name} · ${c.city}`), ttNote(`${plural(c.seasons, "season")} in the league${c.current ? ", including this one" : ""}`));
      if (titles.get(id)) t.append(ttNote(plural(titles.get(id), "title")));
    },
  })), ["Club", "Seasons", "Titles"]);

  /* ---------- Footer ---------- */

  const src = document.getElementById("source");
  src.textContent = raw.source.label;
  src.href = raw.source.url;
  document.getElementById("data-through").textContent = `Through the ${latest.season} final.`;
  document.getElementById("no-final").textContent = raw.noFinal.map((s) => `The ${s.season} season ${/pandemia|covid/i.test(s.note) ? "was cut short by the COVID-19 pandemic and " : ""}had no champion.`).join(" ");
})();
