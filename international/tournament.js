/* International team tournaments (rugby, basketball, volleyball, field hockey): one page, several competitions. */
(async function () {
  "use strict";

  const { el, table, responsive, tooltipOn, ttTitle, ttNote, columnPath } = Viz;
  const options = JSON.parse(document.body.dataset.datasets); // [{key, label, src}]
  const all = await Promise.all(options.map((o) => d3.json(o.src)));
  const byKey = Object.fromEntries(options.map((o, i) => [o.key, all[i]]));

  // One lookup with every team from every competition on the page.
  const teams = Object.assign({}, ...all.map((d) => d.teams));
  const F = Football({ nationMode: true, clubs: Object.fromEntries(Object.entries(teams).map(([c, t]) => [c, { name: t.name, country: c, crest: null }])), countries: teams });
  const name = (c) => teams[c]?.name ?? c;
  const continent = (c) => teams[c]?.continent ?? "Other";
  const CONT_COLOR = { Europe: "var(--series-1)", Americas: "var(--series-2)", Oceania: "var(--series-3)", Asia: "var(--series-4)" };
  const contColor = (c) => CONT_COLOR[c] ?? "var(--ink-muted)";
  const teamLabel = (c) => F.clubLabel(c);
  const finish = (e, c) => (e.champion === c ? 1 : e.runnerUp === c ? 2 : e.third === c ? 3 : e.fourth === c ? 4 : 0);
  const PLACE = { 1: "Champion", 2: "Runner-up", 3: "Third", 4: "Fourth" };
  const scoreText = (e) => (e.roundRobin ? "round robin" : e.score ? `${e.score}${e.note === "penalties" ? " pens" : e.note === "extra time" ? " a.e.t." : ""}` : "–");

  let data;
  let race;
  let raceKind = "titles";

  /* ---------- Bar chart race ---------- */

  const RACES = {
    titles: { label: "Titles", teams: (e) => [e.champion] },
    finals: { label: "Finals", teams: (e) => [e.champion, e.runnerUp] },
    podium: { label: "Podiums", teams: (e) => [e.champion, e.runnerUp, e.third].filter(Boolean) },
  };
  function frames() {
    const tally = new Map();
    const reached = new Map();
    const out = [{ label: String(data.editions[0].year), event: null, ranked: [] }];
    data.editions.forEach((e, i) => {
      new Set(RACES[raceKind].teams(e)).forEach((t) => {
        tally.set(t, (tally.get(t) || 0) + 1);
        reached.set(t, i);
      });
      const ranked = [...tally].map(([id, n]) => ({ id, n, since: reached.get(id) })).sort((a, b) => b.n - a.n || a.since - b.since).slice(0, 10);
      out.push({ label: String(e.year), event: e, ranked });
    });
    return out;
  }

  /* ---------- Render one competition ---------- */

  function show(id, visible) {
    document.getElementById(id).hidden = !visible;
  }

  function render(key) {
    data = byKey[key];
    document.dispatchEvent(new CustomEvent("competitionchange", { detail: key }));
    const eds = data.editions;
    const isOlympics = /olympic/i.test(data.meta.label);
    const winWord = isOlympics ? "gold medals" : "titles";

    // Stat tiles
    document.getElementById("stats").replaceChildren();
    const titles = d3.rollup(eds, (v) => v.length, (e) => e.champion);
    const [leader, leaderN] = d3.greatest(titles, (d) => d[1]);
    const last = eds[eds.length - 1];
    F.statTiles("stats", [
      { label: isOlympics ? "Olympic tournaments" : "Editions", value: String(eds.length), detail: `${eds[0].year} to ${last.year}` },
      { label: isOlympics ? "Gold medallists" : "Champions", value: String(titles.size), detail: `different ${isOlympics ? "teams" : "nations"}` },
      { label: `Most ${winWord}`, value: String(leaderN), detail: name(leader), club: leader },
      { label: `Latest ${isOlympics ? "gold" : "champion"}`, value: name(last.champion), detail: `${last.year} · ${scoreText(last)} vs ${name(last.runnerUp)}`, club: last.champion },
    ]);
    document.querySelectorAll("[data-gender]").forEach((n) => (n.textContent = `${data.meta.label} · ${data.meta.gender}`));

    // Race
    if (race) race.setFrames(frames());
    else {
      race = F.race(frames(), {
        colorOf: (id) => contColor(continent(id)),
        frameMs: 900,
        emptyTicker: "Press play to start with the first edition.",
        ticker: (e) => [F.flag(e.champion), el("strong", null, ` ${e.year} · ${name(e.champion)}`),
          document.createTextNode(` def. ${name(e.runnerUp)} ${scoreText(e)} · hosts: ${e.hosts.map(name).join(", ") || e.hostText}`)],
      });
    }

    // Champions and podium
    const ids = new Set(eds.flatMap((e) => [e.champion, e.runnerUp, e.third, e.fourth]).filter(Boolean));
    const byTeam = [...ids].map((id) => ({ id, places: [1, 2, 3, 4].map((p) => eds.filter((e) => finish(e, id) === p)) }))
      .sort((a, b) => d3.descending(a.places[0].length, b.places[0].length) || d3.descending(a.places[1].length, b.places[1].length) || d3.descending(a.places[2].length, b.places[2].length));
    const years = (list) => list.map((e) => e.year).join(", ") || "–";
    const championsViews = {
      team: () => F.richTable(document.getElementById("champions-table"), [
        { label: "Team", render: (r) => F.withSub(teamLabel(r.id), `Won: ${years(r.places[0])} · Runner-up: ${years(r.places[1])}`) },
        { label: isOlympics ? "Gold" : "Titles", cls: "num strong", render: (r) => String(r.places[0].length) },
        { label: isOlympics ? "Silver" : "Runner-up", short: "2nd", cls: "num", render: (r) => String(r.places[1].length) },
        { label: isOlympics ? "Bronze" : "Third", short: "3rd", cls: "num", render: (r) => String(r.places[2].length) },
        { label: "Fourth", short: "4th", cls: "num", render: (r) => String(r.places[3].length) },
        { label: "Years won", cls: "years", render: (r) => years(r.places[0]) },
      ], byTeam),
      edition: () => F.richTable(document.getElementById("champions-table"), [
        { label: "Year", render: (e) => String(e.year) },
        { label: isOlympics ? "Gold" : "Champion", render: (e) => teamLabel(e.champion) },
        { label: "Final", cls: "score", render: (e) => scoreText(e) },
        { label: isOlympics ? "Silver" : "Runner-up", render: (e) => teamLabel(e.runnerUp) },
        { label: isOlympics ? "Bronze" : "Third", cls: "hide-sm", render: (e) => (e.third ? teamLabel(e.third) : "–") },
        { label: "Fourth", cls: "hide-sm", render: (e) => (e.fourth ? teamLabel(e.fourth) : "–") },
      ], eds.slice().reverse()),
    };
    document.getElementById("champions-tabs").replaceChildren();
    Viz.segmented("champions-tabs", [{ key: "team", label: "By team" }, { key: "edition", label: "Every edition" }], "team", (k) => championsViews[k]());
    championsViews.team();

    // Continents
    const conts = d3.groups(eds, (e) => continent(e.champion));
    const contGroups = [...new Set(eds.flatMap((e) => [continent(e.champion), continent(e.runnerUp)]))].map((c) => {
      const icon = el("i", "confed-key");
      icon.style.setProperty("--c", contColor(c));
      const won = eds.filter((e) => continent(e.champion) === c);
      return { label: c, icon, won, lost: eds.filter((e) => continent(e.runnerUp) === c), winners: d3.groups(won, (e) => e.champion).sort((a, b) => b[1].length - a[1].length) };
    }).sort((a, b) => b.won.length - a.won.length || b.lost.length - a.lost.length);
    F.groupRows(document.getElementById("continents-list"), contGroups, "Continent");
    void conts;

    // Hosts
    const hostWins = eds.filter((e) => e.hosts.includes(e.champion));
    document.getElementById("hosts-note").textContent = hostWins.length
      ? `${hostWins.length} ${hostWins.length === 1 ? "host has" : "hosts have"} won at home: ${hostWins.map((e) => `${name(e.champion)} ${e.year}`).join(", ")}.`
      : "No host has won at home yet.";
    const times = d3.rollups(eds.flatMap((e) => e.hosts.map((h) => ({ h, y: e.year }))), (v) => v.map((d) => d.y), (d) => d.h)
      .sort((a, b) => b[1].length - a[1].length || a[1][0] - b[1][0]);
    const chips = document.getElementById("hosts-summary");
    chips.replaceChildren();
    times.forEach(([code, ys]) => {
      const chip = el("span", "host-chip");
      chip.append(F.flag(code), el("strong", null, name(code)), document.createTextNode(` ${ys.join(", ")}`));
      chips.append(chip);
    });
    F.richTable(document.getElementById("hosts-table"), [
      { label: "Year", render: (e) => String(e.year) },
      { label: "Host", render: (e) => { const w = el("span", "tags"); e.hosts.forEach((h) => w.append(F.flag(h))); w.append(document.createTextNode(e.hosts.map(name).join(", ") || e.hostText)); return w; } },
      { label: "Teams", cls: "num", render: (e) => String(e.teams ?? "–") },
      { label: "Host result", render: (e) => e.hosts.map((h) => (e.hosts.length > 1 ? `${name(h)}: ` : "") + (PLACE[finish(e, h)] ?? "Outside the top four")).join(" · ") || "–" },
      { label: isOlympics ? "Gold" : "Champion", cls: "hide-sm", render: (e) => teamLabel(e.champion) },
    ], eds.slice().reverse().map((e) => ({ ...e, _rowClass: e.hosts.includes(e.champion) ? "split-row" : null })));

    // Repeated finals
    F.repeatedFinals(document.getElementById("pairs-list"), eds.filter((e) => e.champion !== e.runnerUp && !e.roundRobin),
      (e) => `${e.year} ${name(e.champion)} (${scoreText(e)})`);

    // Growth
    const metrics = [
      { key: "teams", label: "Teams", value: (e) => e.teams },
      { key: "matches", label: "Matches", value: (e) => e.matches },
      { key: "attendance", label: "Attendance", value: (e) => e.attendance },
    ].filter((m) => eds.some((e) => m.value(e)));
    show("growth", metrics.length > 0);
    if (metrics.length) {
      let metric = metrics[0];
      const draw = (width) => {
        const container = d3.select("#growth-chart");
        container.selectAll("*").remove();
        const list = eds.filter((e) => metric.value(e));
        const height = 240;
        const margin = { top: 24, right: 8, bottom: 28, left: 44 };
        const x = d3.scaleBand().domain(list.map((e) => e.year)).range([margin.left, width - margin.right]).padding(0.25);
        const y = d3.scaleLinear().domain([0, d3.max(list, metric.value)]).nice().range([height - margin.bottom, margin.top]);
        const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", `${metric.label} per edition`);
        const axis = svg.append("g").attr("class", "axis");
        y.ticks(4).forEach((v) => {
          axis.append("line").attr("class", v === 0 ? "baseline" : "gridline").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", y(v)).attr("y2", y(v));
          axis.append("text").attr("x", margin.left - 8).attr("y", y(v)).attr("dy", "0.35em").attr("text-anchor", "end").text(d3.format("~s")(v));
        });
        const every = Math.ceil(list.length / (width < 560 ? 6 : 14));
        list.forEach((e, i) => {
          if (i % every === 0 || i === list.length - 1) axis.append("text").attr("x", x(e.year) + x.bandwidth() / 2).attr("y", height - 8).attr("text-anchor", "middle").text(e.year);
        });
        const colW = Math.min(24, x.bandwidth());
        const g = svg.selectAll("g.col").data(list).join("g").attr("class", "col mark-group").attr("transform", (e) => `translate(${x(e.year) + (x.bandwidth() - colW) / 2},0)`);
        g.append("rect").attr("x", -4).attr("y", margin.top).attr("width", colW + 8).attr("height", height - margin.top - margin.bottom).attr("fill", "transparent");
        g.append("path").attr("class", "mark").attr("fill", "var(--series-1)").attr("d", (e) => columnPath(0, y(metric.value(e)), colW, y(0) - y(metric.value(e))));
        tooltipOn(g, (t, e) => {
          t.append(ttTitle(`${e.year} · ${e.hosts.map(name).join(", ") || e.hostText}`));
          metrics.forEach((m) => m.value(e) && t.append(Viz.ttRow("var(--series-1)", d3.format(",")(m.value(e)), m.label.toLowerCase())));
        });
      };
      const container = document.getElementById("growth-chart");
      container.replaceChildren();
      document.getElementById("growth-tabs").replaceChildren();
      let width = container.clientWidth || 800;
      draw(width);
      Viz.segmented("growth-tabs", metrics, metric.key, (k) => { metric = metrics.find((m) => m.key === k); draw(container.clientWidth || width); });
    }

    // All-time table
    show("alltime", Boolean(data.alltime));
    if (data.alltime) {
      const rows = data.alltime.slice().sort((a, b) => (b.pts ?? b.w) - (a.pts ?? a.w) || b.w - a.w);
      const has = (k) => rows.some((r) => r[k] != null);
      const unit = data.meta.unit;
      document.getElementById("alltime-note").textContent = `${rows.length} teams, ranked by ${has("pts") ? "points" : "wins"}.`;
      F.richTable(document.getElementById("alltime-table"), [
        { label: "#", cls: "num rank", render: (r) => String(rows.indexOf(r) + 1) },
        { label: "Team", render: (r) => teamLabel(r.team) },
        ...(has("apps") ? [{ label: "Editions", short: "Ed.", cls: "num", render: (r) => String(r.apps ?? "–") }] : []),
        { label: "Played", short: "P", cls: "num", render: (r) => String(r.pld) },
        { label: "W", cls: "num strong", render: (r) => String(r.w) },
        ...(has("d") ? [{ label: "D", cls: "num", render: (r) => String(r.d ?? 0) }] : []),
        { label: "L", cls: "num", render: (r) => String(r.l) },
        ...(has("pf") ? [{ label: `${unit[0].toUpperCase()}${unit.slice(1)} for`, short: "F", cls: "num hide-sm", render: (r) => d3.format(",")(r.pf ?? 0) },
          { label: "Against", short: "A", cls: "num hide-sm", render: (r) => d3.format(",")(r.pa ?? 0) }] : []),
        { label: "Win %", cls: "num", render: (r) => `${((100 * r.w) / r.pld).toFixed(1)}%` },
        ...(has("pts") ? [{ label: "Points", short: "Pts", cls: "num strong", render: (r) => String(r.pts) }] : []),
      ], rows);
    }

    // Participations
    show("participation", Boolean(data.participation));
    if (data.participation) {
      const rows = data.participation.slice().sort((a, b) => b.apps - a.apps || d3.ascending(name(a.team), name(b.team))).slice(0, 25);
      const best = (team) => {
        const places = eds.map((e) => finish(e, team)).filter(Boolean);
        return places.length ? `${PLACE[Math.min(...places)]} (${eds.filter((e) => finish(e, team) === Math.min(...places)).map((e) => e.year).join(", ")})` : "Outside the top four";
      };
      F.rankList(document.getElementById("participation-list"), rows.map((r) => ({
        icon: F.flag(r.team), label: name(r.team), value: r.apps, color: contColor(continent(r.team)),
        tip: (t) => {
          t.append(ttTitle(`${name(r.team)}: ${r.apps} appearances`));
          t.append(ttNote(`Best: ${best(r.team)}`));
          t.append(ttNote(Object.entries(r.results).map(([y, res]) => `${y} ${res}`).join(" · ")));
        },
      })), ["Team", "Appearances", ""]);
    }

    // Player records
    show("players", data.players.length > 0);
    if (data.players.length) {
      const root = document.getElementById("players-table");
      const views = Object.fromEntries(data.players.map((p, i) => [String(i), () => F.richTable(root, [
        { label: "#", cls: "num rank", render: (r) => String(p.rows.indexOf(r) + 1) },
        { label: "Player", render: (r) => { const s = el("span", "club"); s.append(F.flag(r.team), document.createTextNode(r.name)); return r.years ? F.withSub(s, r.years) : s; } },
        { label: p.label.replace(/^Most /, "").replace(/^./, (c) => c.toUpperCase()), cls: "num strong", render: (r) => String(r.value) },
        ...(p.rows.some((r) => r.apps) ? [{ label: "Matches", short: "M", cls: "num", render: (r) => String(r.apps ?? "–") }] : []),
        ...(p.rows.some((r) => r.gold != null) ? [{ label: "Gold", cls: "num", render: (r) => String(r.gold ?? "–") }] : []),
        ...(p.rows.some((r) => r.years) ? [{ label: "Years", cls: "years", render: (r) => r.years ?? "–" }] : []),
      ], p.rows)]));
      document.getElementById("players-tabs").replaceChildren();
      Viz.segmented("players-tabs", data.players.map((p, i) => ({ key: String(i), label: p.label })), "0", (k) => views[k]());
      views["0"]();
    }

    // Footer
    const src = document.getElementById("sources");
    src.replaceChildren();
    data.meta.sources.forEach((url, i) => {
      const a = el("a", null, decodeURIComponent(url.split("/wiki/")[1]).replace(/_/g, " "));
      a.href = url;
      src.append(a);
      if (i < data.meta.sources.length - 1) src.append(document.createTextNode(", "));
    });
    document.getElementById("data-through").textContent = `Covers every edition through ${data.meta.through}.`;
  }

  Viz.segmented("race-metric", Object.entries(RACES).map(([key, r]) => ({ key, label: r.label })), "titles", (k) => {
    raceKind = k;
    race.setFrames(frames());
  });
  // ?c=<key> opens a specific competition, and the URL follows the selector so views can be shared.
  const requested = new URLSearchParams(location.search).get("c");
  const initial = byKey[requested] ? requested : options[0].key;
  Viz.segmented("competition", options.map((o) => ({ key: o.key, label: o.label })), initial, (k) => {
    history.replaceState(null, "", `?c=${k}`);
    render(k);
  });
  render(initial);
})();
