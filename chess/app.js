/* Chess: world champions, number ones, head-to-head records, rapid and blitz, records and nations. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote } = Viz;
  const data = await d3.json(document.body.dataset.src);
  const feds = data.federations;
  const F = Football({
    nationMode: true,
    clubs: Object.fromEntries(Object.entries(feds).map(([c, f]) => [c, { name: f.name, country: c, crest: null }])),
    countries: feds,
  });
  const fedName = (c) => feds[c]?.name ?? c ?? "";
  const who = (name, fed) => {
    const span = el("span", "club");
    if (fed) span.append(F.flag(fed));
    span.append(document.createTextNode(name));
    return span;
  };
  const surname = (n) => n.split(" ").slice(-1)[0];
  const thisYear = new Date().getFullYear();
  const PALETTE = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)", "#8b5cf6", "#e11d74", "#0ea5a4", "#a16207"];
  const titleEvents = data.worldChampionships.filter((e) => ["official", "classical"].includes(e.era) && e.kind !== "aborted");

  /* ---------- Stat tiles ---------- */

  (function stats() {
    const champs = new Set(data.reigns.map((r) => r.name));
    const current = data.reigns[data.reigns.length - 1];
    const months = d3.rollups(data.numberOnes["classical-open"], (v) => v.length, (m) => m.player).sort((a, b) => b[1] - a[1])[0];
    const fast = d3.rollups(["rapid-open", "blitz-open"].flatMap((k) => data.fast[k].flatMap((r) => r.champions)), (v) => v.length, (c) => c.name)
      .sort((a, b) => b[1] - a[1])[0];
    F.statTiles("stats", [
      { label: "World champions", value: String(champs.size), detail: "classical title since 1886" },
      { label: "Current champion", value: surname(current.name), detail: `${current.name}, since ${current.from}`, club: current.fed },
      { label: "Most months at No. 1", value: String(months[1]), detail: months[0] },
      { label: "Rapid and blitz world titles", value: String(fast[1]), detail: fast[0] },
    ]);
  })();

  /* ---------- Reigns of the world champions ---------- */

  (function reignChart() {
    Viz.legend("reign-legend", [{ label: "Classical world title", color: "var(--sport)" }, { label: "FIDE title (1993–2006)", color: "var(--ink-muted)" }]);
    const rows = [];
    const add = (r, line) => {
      let row = rows.find((x) => x.name === r.name && x.line === line);
      if (!row) rows.push((row = { name: r.name, fed: r.fed, line, spans: [] }));
      row.spans.push(r);
    };
    data.reigns.forEach((r) => add(r, "classical"));
    data.fideReigns.forEach((r) => add(r, "fide"));
    Viz.responsive("reign-chart", (width) => {
      const box = d3.select("#reign-chart");
      box.selectAll("*").remove();
      const narrow = width < 600;
      const rowH = 24;
      const margin = { top: 24, right: 16, bottom: 8, left: narrow ? 104 : 190 };
      const height = margin.top + rows.length * rowH + margin.bottom;
      const x = d3.scaleLinear().domain([1886, thisYear + 1]).range([margin.left, width - margin.right]);
      const svg = box.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img")
        .attr("aria-label", "Reigns of the world chess champions: " + data.reigns.map((r) => `${r.name} ${r.from}–${r.to}`).join(", "));
      const ticks = x.ticks(narrow ? 5 : 10);
      svg.append("g").selectAll("line").data(ticks).join("line").attr("class", "gridline")
        .attr("x1", (d) => x(d)).attr("x2", (d) => x(d)).attr("y1", margin.top - 6).attr("y2", height - margin.bottom);
      svg.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", (d) => x(d)).attr("y", margin.top - 10)
        .attr("text-anchor", "middle").text((d) => d);
      const g = svg.selectAll("g.row").data(rows).join("g").attr("class", "row mark-group").attr("transform", (d, i) => `translate(0,${margin.top + i * rowH})`);
      g.append("text").attr("class", "reign-label").attr("x", margin.left - 8).attr("y", rowH / 2).attr("dy", "0.35em").attr("text-anchor", "end")
        .text((d) => (narrow ? surname(d.name) : d.name));
      g.each(function (d) {
        d3.select(this).selectAll("rect").data(d.spans).join("rect").attr("class", "mark")
          .attr("x", (s) => x(s.from)).attr("y", 5).attr("height", rowH - 10).attr("rx", 3)
          .attr("width", (s) => Math.max(3, x(s.to) - x(s.from)))
          .attr("fill", d.line === "fide" ? "var(--ink-muted)" : "var(--sport)");
      });
      Viz.tooltipOn(g, (t, d) => {
        t.append(ttTitle(`${d.name} · ${fedName(d.fed)}`));
        d.spans.forEach((s) => t.append(ttNote(`${d.line === "fide" ? "FIDE champion" : "World champion"} ${s.from}–${s.current ? "today" : s.to} · ${s.events} ${s.events === 1 ? "event" : "events"} won`)));
      });
    });
  })();

  /* ---------- Every World Championship ---------- */

  (function matches() {
    const ERA = { unofficial: "Before 1886", official: "Undisputed", classical: "Classical (split)", fide: "FIDE (split)" };
    const TABS = [
      { key: "all", label: "All", test: () => true },
      { key: "official", label: "Undisputed", test: (e) => e.era === "official" },
      { key: "split", label: "Split title, 1993–2006", test: (e) => e.era === "classical" || e.era === "fide" },
      { key: "unofficial", label: "Before 1886", test: (e) => e.era === "unofficial" },
    ];
    function render(key) {
      const list = data.worldChampionships.filter(TABS.find((t) => t.key === key).test).slice().sort((a, b) => b.year - a.year || (a.era > b.era ? 1 : -1));
      F.richTable(document.getElementById("matches-table"), [
        { label: "Year", render: (e) => F.withSub(el("strong", null, e.label), e.kind === "match" ? "" : e.kind) },
        { label: "Winner", render: (e) => F.withSub(who(e.winner, e.winnerFed), e.kind === "aborted" ? "match abandoned" : e.drawn ? "drawn: champion retained" : "") },
        { label: "Score", cls: "h2h-score", render: (e) => e.score },
        { label: "Runner-up", render: (e) => who(e.runnerUp, e.runnerUpFed) },
        { label: "Where", cls: "hide-sm", render: (e) => e.location },
        { label: "Format", cls: "years", render: (e) => e.format },
        { label: "Title", cls: "hide-sm", render: (e) => el("span", `era-tag ${e.era === "fide" ? "fide" : e.era === "official" ? "professional" : ""}`, ERA[e.era]) },
      ], list);
    }
    Viz.segmented("matches-era", TABS, "all", render);
    render("all");
  })();

  /* ---------- Rivalries for the title ---------- */

  (function titlePairs() {
    const points = (score) => (score.split("·")[0].match(/\d+(?:½)?|½/g) || []).map((s) => (s === "½" ? 0.5 : parseFloat(s) + (s.endsWith("½") ? 0.5 : 0)));
    const half = (n) => `${Math.floor(n) || (n % 1 ? "" : "0")}${n % 1 ? "½" : ""}`;
    const groups = d3.groups(data.worldChampionships.filter((e) => e.kind === "match" || e.kind === "aborted"), (e) => [e.winner, e.runnerUp].sort().join("|"))
      .filter(([, v]) => v.length >= 2).sort((a, b) => b[1].length - a[1].length || d3.max(b[1], (e) => e.year) - d3.max(a[1], (e) => e.year));
    const root = document.getElementById("title-pairs");
    groups.forEach(([key, list]) => {
      const [a, b] = key.split("|");
      // Flags as at the pair's first meeting (Karpov and Kasparov were Soviet players then).
      const fedOf = {};
      list.slice().sort((x, y) => y.year - x.year).forEach((e) => { fedOf[e.winner] = e.winnerFed; fedOf[e.runnerUp] = e.runnerUpFed; });
      const won = (p) => list.filter((e) => e.kind === "match" && e.winner === p && !e.drawn).length;
      const pts = { [a]: 0, [b]: 0 };
      list.forEach((e) => { const [w, r] = points(e.score); if (w != null && r != null) { pts[e.winner] += w; pts[e.runnerUp] += r; } });
      const row = el("div", "pair-row");
      const count = el("div", "count", String(list.length));
      count.append(el("small", null, "matches"));
      const players = el("div", "players");
      players.append(who(a, fedOf[a]), el("span", "vs", "vs"), who(b, fedOf[b]));
      const drawn = list.filter((e) => e.drawn).length;
      const aborted = list.filter((e) => e.kind === "aborted").length;
      const h2h = el("div", "h2h", `${surname(a)} ${won(a)}–${won(b)} ${surname(b)}` + (drawn ? ` · ${drawn} drawn` : "") + (aborted ? ` · ${aborted} abandoned` : ""));
      const meta = el("div", "meta", `${list.map((e) => `${e.label}: ${surname(e.winner)} ${e.score.split("·")[0].trim()}`).join(" · ")} · games score ${surname(a)} ${half(pts[a])}–${half(pts[b])}`);
      row.append(count, players, h2h, meta);
      root.append(row);
    });
  })();

  /* ---------- World number one ---------- */

  (function numberOnes() {
    let mode = "classical";
    let section = "open";
    function render() {
      const list = data.numberOnes[`${mode}-${section}`] || [];
      const counts = d3.rollups(list, (v) => v, (m) => m.player).sort((a, b) => b[1].length - a[1].length);
      const color = new Map(counts.map(([p], i) => [p, PALETTE[i] ?? "var(--axis)"]));
      Viz.legend("no1-legend", counts.slice(0, 8).map(([p]) => ({ label: p, color: color.get(p) })));
      Viz.responsive("no1-ribbon", (width) => {
        const box = d3.select("#no1-ribbon");
        box.selectAll("*").remove();
        if (!list.length) return;
        const t = (m) => m.year + (m.month - 1) / 12;
        const x = d3.scaleLinear().domain([d3.min(list, t), d3.max(list, t) + 1 / 12]).range([8, width - 8]);
        const h = 54;
        const svg = box.append("svg").attr("viewBox", `0 0 ${width} ${h + 22}`).attr("role", "img").attr("aria-label", `World number one by month, ${mode} ${section}`);
        svg.selectAll("rect").data(list).join("rect").attr("x", (m) => x(t(m))).attr("y", 4).attr("height", h)
          .attr("width", Math.max(1, x(1 / 12) - x(0) + 0.5)).attr("fill", (m) => color.get(m.player));
        const ticks = x.ticks(width < 600 ? 4 : 10).filter(Number.isInteger);
        svg.selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", (d) => x(d)).attr("y", h + 18).attr("text-anchor", "middle").text((d) => d);
        const hit = svg.append("rect").attr("width", width).attr("height", h + 8).attr("fill", "transparent");
        hit.on("mousemove", (ev) => {
          const [mx] = d3.pointer(ev);
          const v = x.invert(mx);
          const m = list.find((q) => t(q) <= v && v < t(q) + 1 / 12) ?? list[list.length - 1];
          Viz.showTip(ev, (tt) => { tt.append(ttTitle(m.player)); tt.append(ttNote(`${d3.timeFormat("%B %Y")(new Date(m.year, m.month - 1))} · ${fedName(m.fed)}`)); });
        }).on("mouseleave", Viz.hideTip);
      });
      F.rankList(document.getElementById("no1-list"), counts.map(([p, v]) => ({
        icon: F.flag(d3.greatest(v, (m) => m.year * 12 + m.month).fed), label: p, value: v.length, color: color.get(p),
        second: `${(v.length / 12).toFixed(1)} yrs`,
        tip: (tt) => { tt.append(ttTitle(p)); tt.append(ttNote(`${v.length} months at No. 1, first in ${v[0].year}, last in ${v[v.length - 1].year}`)); },
      })), ["Player", "Months", "Years"]);
    }
    Viz.segmented("no1-mode", [{ key: "classical", label: "Classical" }, { key: "rapid", label: "Rapid" }, { key: "blitz", label: "Blitz" }], mode, (k) => { mode = k; render(); });
    Viz.segmented("no1-section", [{ key: "open", label: "Open" }, { key: "women", label: "Women" }], section, (k) => { section = k; render(); });
    render();
  })();

  /* ---------- Head to head ---------- */

  (function headToHead() {
    const players = Object.fromEntries(data.h2h.players.map((p) => [p.key, p]));
    let mode = "classical";
    let focus = "carlsen";
    const select = document.getElementById("h2h-player");
    data.h2h.players.slice().sort((a, b) => d3.ascending(surname(a.name), surname(b.name))).forEach((p) => {
      const o = el("option", null, p.name);
      o.value = p.key;
      select.append(o);
    });
    select.value = focus;
    select.addEventListener("change", () => { focus = select.value; table(); });

    const bar = (w, d, l) => {
      const b = el("div", "score-bar");
      [["var(--series-3)", w], ["var(--axis)", d], ["var(--series-2)", l]].forEach(([c, n]) => {
        if (!n) return;
        const s = el("span");
        s.style.setProperty("--c", c);
        s.style.flex = String(n);
        b.append(s);
      });
      return b;
    };
    function table() {
      const rows = data.h2h.pairs.filter((p) => p.mode === mode && (p.a === focus || p.b === focus)).map((p) => {
        const mine = p.a === focus;
        const w = mine ? p.aWins ?? 0 : p.bWins ?? 0;
        const l = mine ? p.bWins ?? 0 : p.aWins ?? 0;
        return { opp: mine ? p.b : p.a, w, l, d: p.draws ?? 0, games: p.games, first: p.first, last: p.last };
      }).sort((a, b) => b.games - a.games);
      F.richTable(document.getElementById("h2h-table"), [
        { label: "Opponent", render: (r) => who(players[r.opp].name, players[r.opp].fed) },
        { label: "Games", cls: "num", render: (r) => String(r.games) },
        { label: "Won", short: "W", cls: "num strong", render: (r) => String(r.w) },
        { label: "Drawn", short: "D", cls: "num", render: (r) => String(r.d) },
        { label: "Lost", short: "L", cls: "num", render: (r) => String(r.l) },
        { label: "Score", cls: "num", render: (r) => `${(((r.w + r.d / 2) / r.games) * 100).toFixed(0)}%` },
        { label: "", cls: "hide-sm", render: (r) => bar(r.w, r.d, r.l) },
        { label: "Years", cls: "years", render: (r) => (r.first === r.last ? String(r.first) : `${r.first}–${r.last}`) },
      ], rows);
    }
    function rivalries() {
      const root = document.getElementById("h2h-rivalries");
      root.replaceChildren();
      data.h2h.pairs.filter((p) => p.mode === mode).sort((a, b) => b.games - a.games).slice(0, 12).forEach((p) => {
        const A = players[p.a];
        const B = players[p.b];
        const row = el("div", "pair-row");
        const count = el("div", "count", String(p.games));
        count.append(el("small", null, "games"));
        const ps = el("div", "players");
        ps.append(who(A.name, A.fed), el("span", "vs", "vs"), who(B.name, B.fed));
        const aw = p.aWins ?? 0;
        const bw = p.bWins ?? 0;
        const h = el("div", "h2h", aw === bw ? `Level, ${aw}–${bw}` : `${surname(aw > bw ? A.name : B.name)} ${Math.max(aw, bw)}–${Math.min(aw, bw)}`);
        const meta = el("div", "meta", `${p.draws ?? 0} draws · ${p.first}–${p.last}`);
        row.append(count, ps, h, meta);
        root.append(row);
      });
    }
    Viz.segmented("h2h-mode", [{ key: "classical", label: "Classical" }, { key: "rapid", label: "Rapid" }, { key: "blitz", label: "Blitz and bullet" }], mode, (k) => {
      mode = k;
      table();
      rivalries();
    });
    table();
    rivalries();
  })();

  /* ---------- Rapid and blitz ---------- */

  (function fast() {
    const TABS = [
      { key: "rapid-open", label: "Rapid · Open" }, { key: "rapid-women", label: "Rapid · Women" },
      { key: "blitz-open", label: "Blitz · Open" }, { key: "blitz-women", label: "Blitz · Women" },
    ];
    const names = (list) => {
      const wrap = el("div", "stack-clubs");
      (list || []).forEach((c) => wrap.append(who(c.name, c.fed)));
      return list && list.length ? wrap : el("span", "muted", "–");
    };
    function render(key) {
      const rows = data.fast[key];
      const tally = d3.rollups(rows.flatMap((r) => r.champions.map((c) => ({ ...c, year: r.year }))), (v) => v, (c) => c.name).sort((a, b) => b[1].length - a[1].length);
      F.rankList(document.getElementById("fast-leaders"), tally.slice(0, 10).map(([n, v]) => ({
        icon: F.flag(v[v.length - 1].fed), label: n, value: v.length, color: "var(--sport)",
        second: v.map((c) => c.year).join(", "),
      })), ["Player", "Titles", "Years"]);
      F.richTable(document.getElementById("fast-table"), [
        { label: "Year", render: (r) => String(r.year) },
        { label: "Champion", render: (r) => (r.fromRecords ? F.withSub(names(r.champions), "") : names(r.champions)) },
        { label: "Runner-up", cls: "hide-sm", render: (r) => names(r.runnerUp) },
      ], rows.slice().reverse());
    }
    Viz.segmented("fast-tabs", TABS, "rapid-open", render);
    render("rapid-open");
  })();

  /* ---------- Women's World Championship ---------- */

  (function women() {
    const tally = d3.rollups(data.women, (v) => v, (e) => e.winner).sort((a, b) => b[1].length - a[1].length);
    F.rankList(document.getElementById("women-leaders"), tally.slice(0, 10).map(([n, v]) => ({
      icon: F.flag(v[v.length - 1].winnerFed), label: n, value: v.length, color: "var(--sport)",
      second: `${v[0].year}–${v[v.length - 1].year}`,
    })), ["Champion", "Titles", "Span"]);
    F.richTable(document.getElementById("women-table"), [
      { label: "Year", render: (e) => String(e.year) },
      { label: "Champion", render: (e) => who(e.winner, e.winnerFed) },
      { label: "Runner-up", cls: "hide-sm", render: (e) => (e.runnerUp ? who(e.runnerUp, e.runnerUpFed) : "–") },
      { label: "W–L–D", cls: "num h2h-score", render: (e) => (e.w != null ? `${e.w}–${e.l}–${e.d}` : "–") },
    ], data.women.slice().reverse());
  })();

  /* ---------- Records ---------- */

  (function records() {
    const longest = data.reigns.map((r) => ({ ...r, years: r.to - r.from })).sort((a, b) => b.years - a.years)[0];
    const wins = d3.rollups(titleEvents, (v) => v.length, (e) => e.winner).sort((a, b) => b[1] - a[1]);
    const topWins = wins.filter((w) => w[1] === wins[0][1]).map((w) => w[0]);
    const peak = data.peaks.recordProgression.slice().sort((a, b) => b.rating - a.rating)[0];
    const no1 = d3.rollups(data.numberOnes["classical-open"], (v) => v.length, (m) => m.player).sort((a, b) => b[1] - a[1])[0];
    const count = (key) => d3.rollups(data.fast[key].flatMap((r) => r.champions), (v) => v.length, (c) => c.name).sort((a, b) => b[1] - a[1])[0];
    const rapid = count("rapid-open");
    const blitz = count("blitz-open");
    const womenTop = d3.rollups(data.women, (v) => v.length, (e) => e.winner).sort((a, b) => b[1] - a[1])[0];
    const young = data.prodigies.youngestGM[0];
    const olymp = Object.entries(data.olympiad.medalsOpen).sort((a, b) => b[1][0] - a[1][0])[0];
    const fedOfPlayer = (n) => data.worldChampionships.find((e) => e.winner === n)?.winnerFed ?? data.h2h.players.find((p) => p.name === n)?.fed;
    const cards = [
      ["Longest reign", `${longest.years} years`, `${longest.name}, ${longest.from}–${longest.to}`, longest.fed],
      ["Most World Championship wins", String(wins[0][1]), topWins.join(" and "), topWins.length === 1 ? fedOfPlayer(topWins[0]) : null],
      ["Highest rating ever", String(peak.rating), `${peak.name}, ${peak.achieved}`, fedOfPlayer(peak.name)],
      ["Most months at No. 1", String(no1[1]), no1[0], fedOfPlayer(no1[0])],
      ["Most rapid world titles", String(rapid[1]), rapid[0], fedOfPlayer(rapid[0])],
      ["Most blitz world titles", String(blitz[1]), blitz[0], fedOfPlayer(blitz[0])],
      ["Most women's world titles", String(womenTop[1]), womenTop[0], data.women.find((e) => e.winner === womenTop[0])?.winnerFed],
      ["Youngest grandmaster", young.age.replace(/, \d+ days?/, ""), `${young.name}, ${young.year}`, young.fed],
      ["Most Olympiad golds", String(olymp[1][0]), fedName(olymp[0]), olymp[0]],
    ];
    const root = document.getElementById("record-cards");
    cards.forEach(([label, value, detail, fed]) => {
      const c = el("div", "record-card");
      const d = el("div", "detail");
      if (fed) d.append(F.flag(fed));
      d.append(document.createTextNode(detail));
      c.append(el("div", "label", label), el("div", "value", value), d);
      root.append(c);
    });

    F.richTable(document.getElementById("rating-record"), [
      { label: "Achieved", render: (r) => r.achieved },
      { label: "Player", render: (r) => r.name },
      { label: "Rating", cls: "num strong", render: (r) => String(r.rating) },
    ], data.peaks.recordProgression.slice().reverse());

    const decades = Object.keys(data.peaks.decades);
    const peaks = (d) => F.richTable(document.getElementById("peak-list"), [
      { label: "#", cls: "num rank", render: (r) => String(data.peaks.decades[d].indexOf(r) + 1) },
      { label: "Player", render: (r) => who(r.name, r.fed) },
      { label: "Peak", cls: "num strong", render: (r) => String(r.rating) },
      { label: "When", cls: "num", render: (r) => r.achieved },
    ], data.peaks.decades[d].slice(0, 10));
    Viz.segmented("peak-decade", decades.map((d) => ({ key: d, label: d })), decades[decades.length - 1], peaks);
    peaks(decades[decades.length - 1]);

    F.richTable(document.getElementById("youngest-table"), [
      { label: "#", cls: "num rank", render: (r) => String(data.prodigies.youngestGM.indexOf(r) + 1) },
      { label: "Player", render: (r) => who(r.name, r.fed) },
      { label: "Age", render: (r) => r.age },
      { label: "Year", cls: "num", render: (r) => r.year },
    ], data.prodigies.youngestGM);
    F.richTable(document.getElementById("gm-record-table"), [
      { label: "Year", render: (r) => r.year },
      { label: "Player", render: (r) => who(r.name, r.fed) },
      { label: "Age", render: (r) => r.age },
    ], data.prodigies.gmRecord.slice().reverse());
  })();

  /* ---------- Nations ---------- */

  (function nations() {
    const tally = (items) => d3.rollups(items.filter((i) => i.fed), (v) => v, (i) => i.fed)
      .map(([fed, v]) => ({ fed, value: v.length, people: [...new Set(v.map((i) => i.name))] })).sort((a, b) => b.value - a.value);
    const medals = (table) => Object.entries(table).map(([fed, m]) => ({ fed, value: m[0], second: m[0] + m[1] + m[2], people: [] }))
      .filter((r) => r.value).sort((a, b) => b.value - a.value || b.second - a.second);
    const MEASURES = [
      ["champions", "World champions (classical)", () => tally(data.reigns.filter((r, i, all) => all.findIndex((x) => x.name === r.name) === i).map((r) => ({ fed: r.fed, name: r.name }))), "Champions"],
      ["titles", "World Championship titles", () => tally(titleEvents.map((e) => ({ fed: e.winnerFed, name: e.winner }))), "Titles"],
      ["women", "Women's world titles", () => tally(data.women.map((e) => ({ fed: e.winnerFed, name: e.winner }))), "Titles"],
      ["rapid", "Rapid world titles (open and women)", () => tally(["rapid-open", "rapid-women"].flatMap((k) => data.fast[k].flatMap((r) => r.champions))), "Titles"],
      ["blitz", "Blitz world titles (open and women)", () => tally(["blitz-open", "blitz-women"].flatMap((k) => data.fast[k].flatMap((r) => r.champions))), "Titles"],
      ["no1", "Months at No. 1 (classical, open)", () => tally(data.numberOnes["classical-open"].map((m) => ({ fed: m.fed, name: m.player }))), "Months"],
      ["no1w", "Months at No. 1 (classical, women)", () => tally(data.numberOnes["classical-women"].map((m) => ({ fed: m.fed, name: m.player }))), "Months"],
      ["olympiad", "Chess Olympiad golds (open)", () => medals(data.olympiad.medalsOpen), "Golds"],
      ["olympiadw", "Chess Olympiad golds (women)", () => medals(data.olympiad.medalsWomen), "Golds"],
      ["peaks", "Top 20 peak ratings of the 2020s", () => tally((data.peaks.decades["2020s"] || []).map((r) => ({ fed: r.fed, name: r.name }))), "Players"],
    ];
    const select = document.getElementById("nations-measure");
    MEASURES.forEach(([key, label]) => {
      const o = el("option", null, label);
      o.value = key;
      select.append(o);
    });
    function render() {
      const [, label, get, unit] = MEASURES.find((m) => m[0] === select.value);
      const rows = get();
      F.rankList(document.getElementById("nations-list"), rows.slice(0, 20).map((r) => ({
        icon: F.flag(r.fed), label: fedName(r.fed), value: r.value, color: "var(--sport)",
        second: r.second ?? (r.people.length > 1 ? `${r.people.length} players` : r.people[0] ?? ""),
        tip: (t) => { t.append(ttTitle(`${fedName(r.fed)} · ${label}`)); if (r.people.length) t.append(ttNote(r.people.join(", "))); },
      })), ["Federation", unit, ""]);
    }
    select.addEventListener("change", render);
    render();
  })();

  /* ---------- Candidates and World Cup ---------- */

  [["candidates-table", data.candidates], ["worldcup-table", data.worldCup]].forEach(([id, list]) => {
    F.richTable(document.getElementById(id), [
      { label: "Year", render: (e) => String(e.year) },
      { label: "Winner", render: (e) => who(e.winner, e.winnerFed) },
      { label: "Runner-up", cls: "hide-sm", render: (e) => (e.runnerUp ? who(e.runnerUp, e.runnerUpFed) : "–") },
    ], list.slice().reverse());
  });

  const src = document.getElementById("sources");
  data.meta.sources.forEach((url, i) => {
    const a = el("a", null, decodeURIComponent(url.split("/wiki/")[1]).replace(/_/g, " "));
    a.href = url;
    src.append(a);
    if (i < data.meta.sources.length - 1) src.append(document.createTextNode(", "));
  });
  document.getElementById("data-through").textContent = `Covers every World Championship through ${data.meta.through}.`;
})();
