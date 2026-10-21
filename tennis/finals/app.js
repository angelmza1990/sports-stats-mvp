/* ATP and WTA Finals: results grid, champions, leaders, records, matchups, nations and host cities. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote } = Viz;
  const data = await d3.json(document.body.dataset.src);
  const F = Football({
    nationMode: true,
    clubs: Object.fromEntries(Object.entries(data.nations).map(([c, n]) => [c, { name: n.name, country: c, crest: null }])),
    countries: data.nations,
  });
  const nationName = (c) => data.nations[c]?.name ?? c ?? "";
  const who = (name, nation) => {
    const span = el("span", "club");
    if (nation) span.append(F.flag(nation));
    span.append(document.createTextNode(name ?? "—"));
    return span;
  };
  const surname = (n) => n.split(" ").slice(-1)[0];
  const RESULT = {
    W: { label: "Champion", color: "var(--gold)" },
    F: { label: "Final", color: "var(--silver)" },
    SF: { label: "Semifinal", color: "var(--bronze)" },
    QF: { label: "Quarterfinal", color: "color-mix(in srgb, var(--sport) 55%, var(--surface))" },
    R16: { label: "Round of 16", color: "color-mix(in srgb, var(--sport) 35%, var(--surface))" },
    RR: { label: "Round robin", color: "color-mix(in srgb, var(--sport) 35%, var(--surface))" },
  };
  const ROUND = { F: "Final", SF: "Semifinal", QF: "Quarterfinal", R16: "Round of 16", RR: "Round robin", BR: "Third place" };
  const pct = (w, l) => (w + l ? Math.round((1000 * w) / (w + l)) / 10 : 0);

  const charts = {};
  function chart(id, draw) {
    if (charts[id]) {
      charts[id].draw = draw;
      charts[id].redraw();
    } else {
      charts[id] = { draw };
      charts[id].redraw = Viz.responsive(id, (width) => charts[id].draw(width));
    }
  }

  document.getElementById("sources").replaceChildren(
    ...data.meta.sources.flatMap((u, i) => {
      const a = el("a", null, decodeURIComponent(u.split("/wiki/")[1]).replace(/_/g, " "));
      a.href = u;
      return i ? [document.createTextNode(", "), a] : [a];
    }),
  );

  let tour = "atp";
  let T;
  let P; // per-player totals
  function derive() {
    T = data.tours[tour];
    const byName = new Map();
    T.editions.forEach((e, i) => {
      e.index = i;
      e.players.forEach((p) => {
        let s = byName.get(p.name);
        if (!s) byName.set(p.name, (s = { name: p.name, nation: p.nation, nations: new Set(), editions: [], titles: 0, finals: 0, won: 0, lost: 0 }));
        s.nations.add(p.nation);
        s.nation = p.nation;
        s.editions.push({ e, ...p });
        s.won += p.won;
        s.lost += p.lost;
      });
    });
    // Titles and finals come from the list of finals, which also covers editions without match data.
    T.editions.forEach((e) => {
      [[e.champion, e.championNation, "titles"], [e.runnerUp, e.runnerUpNation, null]].forEach(([name, nation, key]) => {
        if (!name) return;
        let s = byName.get(name);
        if (!s) byName.set(name, (s = { name, nation, nations: new Set([nation]), editions: [], titles: 0, finals: 0, won: 0, lost: 0 }));
        s.finals += 1;
        if (key) s.titles += 1;
      });
    });
    byName.forEach((s) => {
      s.apps = s.editions.length;
      // Longest run of consecutive editions played.
      const idx = s.editions.map((x) => x.e.index).sort((a, b) => a - b);
      let best = idx.length ? 1 : 0;
      let run = 1;
      let from = idx[0];
      let bestFrom = idx[0];
      for (let i = 1; i < idx.length; i++) {
        if (idx[i] === idx[i - 1] + 1) run += 1;
        else {
          run = 1;
          from = idx[i];
        }
        if (run > best) {
          best = run;
          bestFrom = from;
        }
      }
      s.streak = { n: best, from: T.editions[bestFrom]?.edition, to: T.editions[(bestFrom ?? 0) + best - 1]?.edition };
    });
    P = [...byName.values()];
  }

  /* ---------- Stat tiles ---------- */

  function stats() {
    const top = (key) => d3.greatest(P, (p) => p[key]);
    const titles = top("titles");
    const apps = top("apps");
    const wins = top("won");
    document.getElementById("stats").replaceChildren();
    F.statTiles("stats", [
      { label: "Editions", value: String(T.editions.length), detail: `${T.editions[0].edition}–${T.editions[T.editions.length - 1].edition}` },
      { label: "Most titles", value: String(titles.titles), detail: titles.name, club: titles.nation },
      { label: "Most appearances", value: String(apps.apps), detail: apps.name, club: apps.nation },
      { label: "Most match wins", value: String(wins.won), detail: `${wins.name}, ${wins.won}–${wins.lost}`, club: wins.nation },
    ]);
  }

  /* ---------- Results grid ---------- */

  function grid() {
    const eds = T.editions.filter((e) => e.matchData);
    const rows = P.filter((p) => p.apps >= 3).sort((a, b) => b.apps - a.apps || b.titles - a.titles || b.won - a.won).slice(0, 30);
    const used = tour === "atp" ? ["W", "F", "SF", "RR"] : ["W", "F", "SF", "QF", "RR"];
    Viz.legend("grid-legend", used.map((k) => ({ label: k === "RR" ? (tour === "atp" ? "Round robin or earlier" : "Earlier round") : RESULT[k].label, color: RESULT[k].color })));
    chart("grid-chart", (width) => {
      const box = d3.select("#grid-chart");
      box.selectAll("*").remove();
      const narrow = width < 600;
      const left = narrow ? 92 : 170;
      const right = narrow ? 34 : 92;
      const cell = Math.max(9, Math.floor((width - left - right) / eds.length));
      const rowH = narrow ? 18 : 20;
      const top = 24;
      const w = left + eds.length * cell + right;
      const h = top + rows.length * rowH + 4;
      // Wider than the card on phones: the card scrolls sideways instead of shrinking the grid.
      const svg = box.append("svg").attr("viewBox", `0 0 ${w} ${h}`).attr("width", w).attr("height", h)
        .style("max-width", "none").style("width", `${w}px`).style("height", `${h}px`);
      const x = (i) => left + i * cell;
      const decade = eds.map((e, i) => [e, i]).filter(([e]) => e.year % (narrow ? 10 : 5) === 0 && !e.edition.includes("November"));
      svg.append("g").selectAll("text").data(decade).join("text").attr("class", "tick-label").attr("x", ([, i]) => x(i) + cell / 2).attr("y", 14)
        .attr("text-anchor", "middle").text(([e]) => e.year);
      const g = svg.append("g").selectAll("g").data(rows).join("g").attr("transform", (d, i) => `translate(0 ${top + i * rowH})`);
      g.append("text").attr("class", "grid-name").attr("x", left - 8).attr("y", rowH / 2 + 4).attr("text-anchor", "end").text((p) => (narrow ? surname(p.name) : p.name));
      g.append("rect").attr("x", left).attr("y", rowH / 2 - 0.5).attr("width", eds.length * cell).attr("height", 1).attr("fill", "var(--border)");
      const cells = g.selectAll("rect.cell").data((p) => p.editions.map((x_) => ({ ...x_, p, i: eds.indexOf(x_.e) })).filter((c) => c.i >= 0)).join("rect")
        .attr("class", "cell").attr("x", (c) => x(c.i) + 1).attr("y", 2).attr("width", cell - 2).attr("height", rowH - 4).attr("rx", 2)
        .attr("fill", (c) => RESULT[c.result].color);
      Viz.tooltipOn(cells, (c) => {
        const t = el("div");
        t.append(ttTitle(`${c.p.name} · ${c.e.edition}`), el("div", null, `${RESULT[c.result].label} · ${c.won}–${c.lost}`));
        return t;
      });
      g.append("text").attr("class", "grid-count").attr("x", left + eds.length * cell + 8).attr("y", rowH / 2 + 4).text((p) => (narrow || !p.titles ? String(p.apps) : `${p.apps} · ${p.titles} title${p.titles === 1 ? "" : "s"}`));
    });
  }

  /* ---------- Champions ---------- */

  function champions() {
    const rows = T.editions.slice().reverse();
    F.richTable(document.getElementById("champions-table"), [
      { label: "Year", render: (e) => e.edition },
      { label: "Champion", render: (e) => who(e.champion, e.championNation) },
      { label: "Runner-up", render: (e) => (e.runnerUp ? who(e.runnerUp, e.runnerUpNation) : "—") },
      { label: "Final", cls: "hide-sm", render: (e) => e.score ?? "" },
      { label: "Host", cls: "hide-sm", render: (e) => who(e.city, e.hostNation) },
    ], rows);
  }

  /* ---------- Leaders ---------- */

  let leaderTab = "titles";
  const LEADERS = {
    titles: { label: "Titles", value: (p) => p.titles, second: (p) => `${p.finals} finals`, filter: (p) => p.titles > 0 },
    finals: { label: "Finals", value: (p) => p.finals, second: (p) => `${p.titles} won`, filter: (p) => p.finals > 0 },
    apps: { label: "Appearances", value: (p) => p.apps, second: (p) => `${p.won}–${p.lost}`, filter: (p) => p.apps > 0 },
    won: { label: "Match wins", value: (p) => p.won, second: (p) => `${p.won}–${p.lost}`, filter: (p) => p.won > 0 },
    pct: { label: "Win %", value: (p) => pct(p.won, p.lost), second: (p) => `${p.won}–${p.lost}`, filter: (p) => p.won + p.lost >= 15 },
  };
  function leaders() {
    const L = LEADERS[leaderTab];
    const rows = P.filter(L.filter).sort((a, b) => L.value(b) - L.value(a) || b.titles - a.titles || b.won - a.won).slice(0, 20).map((p) => ({
      icon: F.flag(p.nation),
      label: p.name,
      value: L.value(p),
      second: L.second(p),
      tip: () => {
        const t = el("div");
        t.append(ttTitle(p.name), el("div", null, `${p.titles} titles · ${p.finals} finals · ${p.apps} appearances · ${p.won}–${p.lost}`));
        if (p.editions.length) t.append(ttNote(p.editions.map((x) => `${x.e.edition} ${x.result === "W" ? "🏆" : x.result}`).join(", ")));
        return t;
      },
    }));
    F.rankList(document.getElementById("leaders-list"), rows, ["Player", L.label, ""]);
  }
  Viz.segmented("leaders-tabs", Object.entries(LEADERS).map(([key, l]) => ({ key, label: l.label })), leaderTab, (k) => {
    leaderTab = k;
    leaders();
  });

  /* ---------- Records ---------- */

  function records() {
    const g = (fn, filter = () => true) => d3.greatest(P.filter(filter), fn);
    const titles = g((p) => p.titles);
    const finals = g((p) => p.finals);
    const apps = g((p) => p.apps);
    const streak = g((p) => p.streak.n);
    const wins = g((p) => p.won);
    const best = g((p) => pct(p.won, p.lost), (p) => p.won + p.lost >= 15);
    // Consecutive titles.
    let run = { n: 0 };
    T.editions.forEach((e, i) => {
      let n = 1;
      while (i - n >= 0 && T.editions[i - n].champion === e.champion) n += 1;
      if (n > run.n) run = { n, name: e.champion, nation: e.championNation, to: e.edition, from: T.editions[i - n + 1].edition };
    });
    const unbeaten = T.editions.filter((e) => e.matchData && e.players.some((p) => p.result === "W" && p.lost === 0));
    const cards = [
      ["Most titles", titles.titles, titles.name, titles.nation],
      ["Most finals", finals.finals, finals.name, finals.nation],
      ["Most consecutive titles", run.n, `${run.name}, ${run.from}–${run.to}`, run.nation],
      ["Most appearances", apps.apps, apps.name, apps.nation],
      ["Most consecutive appearances", streak.streak.n, `${streak.name}, ${streak.streak.from}–${streak.streak.to}`, streak.nation],
      ["Most match wins", wins.won, `${wins.name}, ${wins.won}–${wins.lost}`, wins.nation],
      ["Best win percentage", `${best ? pct(best.won, best.lost) : 0}%`, best ? `${best.name}, ${best.won}–${best.lost} (15+ matches)` : "", best?.nation],
      ["Unbeaten champions", unbeaten.length, "titles won without losing a match", null],
    ];
    const root = document.getElementById("record-cards");
    root.replaceChildren();
    cards.forEach(([label, value, detail, nation]) => {
      const c = el("div", "record-card");
      c.append(el("div", "label", label), el("div", "value", String(value)));
      const d = el("div", "detail");
      if (nation) d.append(F.flag(nation));
      d.append(document.createTextNode(detail));
      c.append(d);
      root.append(c);
    });
    F.richTable(document.getElementById("unbeaten-table"), [
      { label: "Year", render: (e) => e.edition },
      { label: "Champion", render: (e) => who(e.champion, e.championNation) },
      { label: "Record", cls: "num", render: (e) => { const p = e.players.find((x) => x.result === "W"); return `${p.won}–${p.lost}`; } },
    ], unbeaten.slice().reverse());
    const debut = T.editions.filter((e) => {
      const p = P.find((x) => x.name === e.champion);
      return p && (p.editions.length ? p.editions[0].e === e : true) && !T.editions.slice(0, e.index).some((x) => x.runnerUp === e.champion || x.champion === e.champion);
    });
    F.richTable(document.getElementById("debut-table"), [
      { label: "Year", render: (e) => e.edition },
      { label: "Champion", render: (e) => who(e.champion, e.championNation) },
      { label: "Runner-up", cls: "hide-sm", render: (e) => (e.runnerUp ? who(e.runnerUp, e.runnerUpNation) : "—") },
    ], debut.slice().reverse());
  }

  /* ---------- Matchups ---------- */

  let h2hPlayer = "";
  function matchups() {
    const pairs = d3.groups(T.matches.filter((m) => !m.walkover), (m) => [m.winner, m.loser].sort().join("|"))
      .map(([key, ms]) => ({ key, ms, a: key.split("|")[0], b: key.split("|")[1] }))
      .filter((p) => !h2hPlayer || p.a === h2hPlayer || p.b === h2hPlayer)
      .sort((x, y) => y.ms.length - x.ms.length || d3.max(y.ms, (m) => m.edition).localeCompare(d3.max(x.ms, (m) => m.edition)));
    const shown = pairs.filter((p) => p.ms.length >= (h2hPlayer ? 1 : 3)).slice(0, h2hPlayer ? 40 : 25);
    const nationOf = new Map(P.map((p) => [p.name, p.nation]));
    const root = document.getElementById("h2h-list");
    root.replaceChildren();
    shown.forEach((pr) => {
      let [a, b] = [pr.a, pr.b];
      if (h2hPlayer && b === h2hPlayer) [a, b] = [b, a];
      const wa = pr.ms.filter((m) => m.winner === a).length;
      const row = el("div", "pair-row");
      const count = el("div", "count", String(pr.ms.length));
      count.append(el("small", null, pr.ms.length === 1 ? "match" : "matches"));
      const players = el("div", "players");
      players.append(who(a, nationOf.get(a)), el("span", "vs", "vs"), who(b, nationOf.get(b)));
      const h2h = el("div", "h2h", `${surname(a)} ${wa}–${pr.ms.length - wa} ${surname(b)}`);
      const meta = el("div", "meta", pr.ms.slice().sort((x, y) => x.edition.localeCompare(y.edition))
        .map((m) => `${m.edition} ${m.round === "RR" ? "RR" : ROUND[m.round] ?? m.round}: ${surname(m.winner)} ${m.score}`).join(" · "));
      row.append(count, players, h2h, meta);
      root.append(row);
    });
    if (!shown.length) root.append(el("p", "card-note", "No matches."));
  }
  function playerSelect() {
    const sel = document.getElementById("h2h-player");
    sel.replaceChildren();
    const all = el("option", null, "All players");
    all.value = "";
    sel.append(all);
    P.filter((p) => p.won + p.lost >= 6).sort((a, b) => surname(a.name).localeCompare(surname(b.name))).forEach((p) => {
      const o = el("option", null, p.name);
      o.value = p.name;
      sel.append(o);
    });
    h2hPlayer = "";
    sel.value = "";
  }
  document.getElementById("h2h-player").addEventListener("change", (e) => {
    h2hPlayer = e.target.value;
    matchups();
  });

  /* ---------- Nations ---------- */

  let nationTab = "titles";
  function nationList() {
    const by = new Map();
    const get = (c) => {
      if (!by.has(c)) by.set(c, { code: c, titles: 0, finals: 0, players: new Set(), apps: 0, won: 0, lost: 0 });
      return by.get(c);
    };
    T.editions.forEach((e) => {
      if (e.championNation) {
        get(e.championNation).titles += 1;
        get(e.championNation).finals += 1;
      }
      if (e.runnerUpNation) get(e.runnerUpNation).finals += 1;
      e.players.forEach((p) => {
        if (!p.nation) return;
        const n = get(p.nation);
        n.players.add(p.name);
        n.apps += 1;
        n.won += p.won;
        n.lost += p.lost;
      });
    });
    const M = {
      titles: [(n) => n.titles, (n) => `${n.finals} finals`],
      finals: [(n) => n.finals, (n) => `${n.titles} won`],
      players: [(n) => n.players.size, (n) => `${n.apps} appearances`],
      won: [(n) => n.won, (n) => `${n.won}–${n.lost}`],
    }[nationTab];
    const rows = [...by.values()].filter((n) => M[0](n) > 0).sort((a, b) => M[0](b) - M[0](a) || b.titles - a.titles || b.won - a.won).map((n) => ({
      icon: F.flag(n.code),
      label: nationName(n.code),
      value: M[0](n),
      second: M[1](n),
      tip: () => {
        const t = el("div");
        t.append(ttTitle(nationName(n.code)), el("div", null, `${n.titles} titles · ${n.finals} finals · ${n.won}–${n.lost}`));
        const champs = d3.rollups(T.editions.filter((e) => e.championNation === n.code), (v) => v.length, (e) => e.champion).sort((a, b) => b[1] - a[1]);
        champs.forEach(([name, k]) => t.append(Viz.ttRow("var(--gold)", k, name)));
        if (!champs.length) t.append(ttNote([...n.players].slice(0, 8).join(", ") + (n.players.size > 8 ? "…" : "")));
        return t;
      },
    }));
    F.rankList(document.getElementById("nation-list"), rows, ["Nation", { titles: "Titles", finals: "Finals", players: "Players", won: "Wins" }[nationTab], ""]);
  }
  Viz.segmented("nation-tabs", [{ key: "titles", label: "Titles" }, { key: "finals", label: "Finals" }, { key: "players", label: "Players" }, { key: "won", label: "Match wins" }], nationTab, (k) => {
    nationTab = k;
    nationList();
  });

  /* ---------- Host cities ---------- */

  function hosts() {
    const last = T.editions[T.editions.length - 1].year;
    const spans = T.hosts.filter((h) => h.from <= last).map((h) => ({ ...h, to: Math.min(h.to, last) }));
    const cities = d3.rollups(spans, (v) => ({ years: d3.sum(v, (h) => h.to - h.from + 1), nation: v[0].nation, spans: v }), (h) => h.city)
      .sort((a, b) => b[1].years - a[1].years);
    const color = new Map(cities.map(([c], i) => [c, ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)", "#8b5cf6", "#e11d74", "#0ea5a4", "#a16207"][i] ?? "var(--axis)"]));
    chart("host-chart", (width) => {
      const box = d3.select("#host-chart");
      box.selectAll("*").remove();
      const narrow = width < 600;
      const h = 70;
      const x = d3.scaleLinear().domain([spans[0].from, last + 1]).range([4, width - 4]);
      const svg = box.append("svg").attr("viewBox", `0 0 ${width} ${h}`).attr("width", width).attr("height", h);
      const r = svg.append("g").selectAll("rect").data(spans).join("rect").attr("x", (s) => x(s.from) + 0.5).attr("width", (s) => Math.max(1, x(s.to + 1) - x(s.from) - 1))
        .attr("y", 4).attr("height", 36).attr("rx", 3).attr("fill", (s) => color.get(s.city));
      svg.append("g").selectAll("text").data(spans.filter((s) => x(s.to + 1) - x(s.from) > (narrow ? 50 : 64))).join("text").attr("class", "host-label")
        .attr("x", (s) => (x(s.from) + x(s.to + 1)) / 2).attr("y", 27).attr("text-anchor", "middle").text((s) => s.city);
      Viz.tooltipOn(r, (s) => {
        const t = el("div");
        t.append(ttTitle(`${s.city}, ${nationName(s.nation)}`), el("div", null, s.from === s.to ? String(s.from) : `${s.from}–${s.to}`));
        if (s.venue) t.append(ttNote(`${s.venue}${s.surface ? ` · ${s.surface}` : ""}`));
        return t;
      });
      svg.append("g").selectAll("text.t").data(x.ticks(narrow ? 5 : 10).filter(Number.isInteger)).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 8)
        .attr("text-anchor", "middle").text((d) => d);
    });
    F.richTable(document.getElementById("host-table"), [
      { label: "City", render: ([c, v]) => who(c, v.nation) },
      { label: "Editions", cls: "num strong", render: ([, v]) => String(v.years) },
      { label: "Years", cls: "years", render: ([, v]) => v.spans.map((s) => (s.from === s.to ? s.from : `${s.from}–${s.to}`)).join(", ") },
    ], cities);
  }

  const renderAll = () => {
    derive();
    playerSelect();
    [stats, grid, champions, leaders, records, matchups, nationList, hosts].forEach((f) => f());
  };
  Viz.segmented("tour", [{ key: "atp", label: "ATP Finals" }, { key: "wta", label: "WTA Finals" }], tour, (k) => {
    tour = k;
    renderAll();
  });
  renderAll();
})();
