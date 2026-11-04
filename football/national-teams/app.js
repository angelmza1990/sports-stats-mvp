/* National teams: every men's international since 1872. Head to head between any two teams, Elo ratings and the all-time table. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote, ttRow } = Viz;
  const [db, elo] = await Promise.all([d3.json("data/matches.json"), d3.json("data/elo.json")]);
  const teams = db.teams;
  // Football() keys flags by id: team i is "t<i>".
  const key = (i) => `t${i}`;
  const countries = Object.fromEntries(teams.map((t, i) => [key(i), { name: t.name, flag: t.flag }]));
  const F = Football({ nationMode: true, clubs: Object.fromEntries(teams.map((t, i) => [key(i), { name: t.name, country: key(i) }])), countries });
  const name = (i) => teams[i].name;
  const byName = new Map(teams.map((t, i) => [t.name, i]));
  const label = (i) => F.clubLabel(key(i));
  const day0 = d3.utcParse("%Y-%m-%d")(db.meta.day0);
  const dateOf = (d) => d3.utcDay.offset(day0, d);
  const fmtDay = d3.utcFormat("%-d %b %Y");
  const pct = (x, digits = 0) => `${(x * 100).toFixed(digits)}%`;
  const T = db.tournaments;
  const FRIENDLY = T.indexOf("Friendly");
  const MAJOR = new Set(["Copa América", "UEFA Euro", "African Cup of Nations", "AFC Asian Cup", "Gold Cup", "CONCACAF Championship", "Confederations Cup", "Oceania Nations Cup"]);
  const GROUPS = ["FIFA World Cup", "Continental championships", "World Cup qualifiers", "Continental qualifiers", "Nations Leagues", "Other tournaments", "Friendlies"];
  const groupOf = (t) => {
    const n = T[t];
    if (n === "FIFA World Cup") return GROUPS[0];
    if (MAJOR.has(n)) return GROUPS[1];
    if (n === "FIFA World Cup qualification") return GROUPS[2];
    if (n.includes("qualification")) return GROUPS[3];
    if (n.includes("Nations League")) return GROUPS[4];
    return t === FRIENDLY ? GROUPS[6] : GROUPS[5];
  };
  const M = db.matches.map(([d, h, a, hs, as, t, neutral, so]) => ({ d, h, a, hs, as, t, neutral: Boolean(neutral), so }));

  /* ---------- Stat tiles ---------- */

  const played = new Array(teams.length).fill(0);
  M.forEach((m) => { played[m.h] += 1; played[m.a] += 1; });
  const most = d3.maxIndex(played);
  const peak = elo.peaks[0];
  F.statTiles("stats", [
    { label: "Matches", value: d3.format(",")(M.length), detail: `${dateOf(M[0].d).getUTCFullYear()} to ${fmtDay(dateOf(M[M.length - 1].d))}` },
    { label: "National teams", value: String(teams.length), detail: `${d3.sum(played, (n) => n >= 500)} with 500 matches or more` },
    { label: "Most matches", value: d3.format(",")(played[most]), detail: name(most), club: key(most) },
    { label: "Highest Elo ever", value: String(peak.rating), detail: `${name(peak.team)}, ${peak.date.slice(0, 4)}`, club: key(peak.team) },
  ]);
  document.getElementById("data-through").textContent = `Matches through ${fmtDay(dateOf(M[M.length - 1].d))}.`;

  /* ---------- Head to head ---------- */

  const CLASSICS = [
    ["Argentina", "Brazil"], ["Argentina", "Uruguay"], ["Brazil", "Uruguay"], ["England", "Scotland"], ["England", "Germany"],
    ["Germany", "Netherlands"], ["Argentina", "England"], ["Spain", "Portugal"], ["Germany", "Italy"], ["France", "Italy"],
    ["Mexico", "United States"], ["Chile", "Peru"], ["Argentina", "Chile"], ["Brazil", "Paraguay"], ["Belgium", "Netherlands"],
    ["Austria", "Hungary"], ["South Korea", "Japan"], ["Algeria", "Egypt"],
  ].filter(([a, b]) => byName.has(a) && byName.has(b)).map(([a, b]) => [byName.get(a), byName.get(b)]);
  const state = { a: CLASSICS[0][0], b: CLASSICS[0][1], kind: "all" };

  const options = [...teams.keys()].sort((x, y) => d3.ascending(name(x), name(y)));
  for (const id of ["team-a", "team-b"]) {
    const sel = document.getElementById(id);
    options.forEach((i) => {
      const o = el("option", null, name(i));
      o.value = String(i);
      sel.append(o);
    });
    sel.addEventListener("change", () => {
      state[id === "team-a" ? "a" : "b"] = +sel.value;
      renderH2H();
    });
  }
  document.getElementById("swap").addEventListener("click", () => {
    [state.a, state.b] = [state.b, state.a];
    renderH2H();
  });
  const classicRoot = document.getElementById("classics");
  const classicButtons = CLASSICS.map(([a, b]) => {
    const btn = el("button");
    btn.type = "button";
    btn.append(F.flag(key(a)), F.flag(key(b)), document.createTextNode(`${name(a)}–${name(b)}`));
    btn.addEventListener("click", () => {
      Object.assign(state, { a, b });
      renderH2H();
    });
    classicRoot.append(btn);
    return { btn, a, b };
  });
  Viz.segmented("kind-tabs", [{ key: "all", label: "All matches" }, { key: "competitive", label: "Without friendlies" }], "all", (k) => {
    state.kind = k;
    renderH2H();
  });

  const COLOR = { a: "var(--series-1)", b: "var(--series-2)", d: "var(--draw)" };
  function split(root, parts) {
    root.replaceChildren();
    const total = d3.sum(parts, (p) => p.n);
    parts.forEach((p) => {
      if (!p.n) return;
      const seg = el("div");
      seg.style.setProperty("--c", p.color);
      seg.style.flex = String(p.n / total);
      root.append(seg);
    });
  }
  // From team A's side: "a" win, "b" win or "d" draw (shoot-outs count as draws).
  const result = (m, A) => (m.hs === m.as ? "d" : (m.hs > m.as) === (m.h === A) ? "a" : "b");
  const goalsOf = (m, A) => (m.h === A ? [m.hs, m.as] : [m.as, m.hs]);
  const tally = (list, A) => {
    const r = { n: list.length, a: 0, d: 0, b: 0, ga: 0, gb: 0 };
    list.forEach((m) => {
      r[result(m, A)] += 1;
      const [x, y] = goalsOf(m, A);
      r.ga += x;
      r.gb += y;
    });
    return r;
  };

  function renderH2H() {
    const { a: A, b: B } = state;
    document.getElementById("team-a").value = String(A);
    document.getElementById("team-b").value = String(B);
    classicButtons.forEach((c) => c.btn.setAttribute("aria-pressed", String((c.a === A && c.b === B) || (c.a === B && c.b === A))));
    classicButtons.forEach((c) => c.btn.style.setProperty("--c", "var(--sport)"));
    const list = M.filter((m) => ((m.h === A && m.a === B) || (m.h === B && m.a === A)) && (state.kind === "all" || m.t !== FRIENDLY));
    const t = tally(list, A);

    const head = document.getElementById("rv-versus");
    const side = (i, wins, right) => {
      const sd = el("div", `rv-side${right ? " right" : ""}`);
      const txt = el("div");
      txt.append(el("div", "rv-name", name(i)), el("div", "rv-wins", String(wins)), el("div", "rv-label", wins === 1 ? "win" : "wins"));
      sd.append(F.flag(key(i)), txt);
      return sd;
    };
    const mid = el("div", "rv-mid");
    mid.append(el("div", "rv-draws", String(t.d)), el("div", "rv-label", t.d === 1 ? "draw" : "draws"));
    head.replaceChildren(side(A, t.a), mid, side(B, t.b, true));
    split(document.getElementById("rv-split"), [{ n: t.a, color: COLOR.a }, { n: t.d, color: COLOR.d }, { n: t.b, color: COLOR.b }]);
    const goals = document.getElementById("rv-goals");
    if (!list.length) {
      goals.replaceChildren(el("span", null, A === B ? "Pick two different teams." : "They have never met."));
      document.getElementById("h2h-body").hidden = true;
      return;
    }
    document.getElementById("h2h-body").hidden = false;
    goals.replaceChildren(el("span", null, `${t.ga} goals by ${name(A)}`),
      el("span", null, `${t.n} matches since ${dateOf(list[0].d).getUTCFullYear()}`), el("span", null, `${t.gb} goals by ${name(B)}`));

    // Lead chart: A's wins minus B's wins after every match.
    Viz.legend("lead-legend", [{ label: `${name(A)} ahead`, color: COLOR.a }, { label: `${name(B)} ahead`, color: COLOR.b }]);
    let lead = 0;
    const pts = list.map((m, i) => {
      const r = result(m, A);
      lead += r === "a" ? 1 : r === "b" ? -1 : 0;
      return { i, m, lead, when: dateOf(m.d) };
    });
    const maxA = d3.greatest(pts, (p) => p.lead), maxB = d3.least(pts, (p) => p.lead);
    document.getElementById("lead-note").textContent = [
      maxA.lead > 0 ? `${name(A)}'s biggest lead: ${maxA.lead}, in ${maxA.when.getUTCFullYear()}.` : "",
      maxB.lead < 0 ? `${name(B)}'s biggest lead: ${-maxB.lead}, in ${maxB.when.getUTCFullYear()}.` : "",
    ].filter(Boolean).join(" ");
    leadPts = pts;
    rerenderLead();

    // By competition
    const rows = GROUPS.map((g) => ({ g, ...tally(list.filter((m) => groupOf(m.t) === g), A) })).filter((r) => r.n);
    const compRoot = document.getElementById("comp-table");
    F.richTable(compRoot, [
      { label: "Competition", render: (r) => r.g },
      { label: "P", cls: "num", render: (r) => String(r.n) },
      { label: teams[A].name, short: "W", cls: "num", render: (r) => String(r.a) },
      { label: "D", cls: "num", render: (r) => String(r.d) },
      { label: teams[B].name, short: "L", cls: "num", render: (r) => String(r.b) },
      { label: "", cls: "hide-sm", render: (r) => { const bar = el("div", "wdl-bar"); split(bar, [{ n: r.a, color: COLOR.a }, { n: r.d, color: COLOR.d }, { n: r.b, color: COLOR.b }]); return bar; } },
    ], rows.length > 1 ? [...rows, { g: "All", ...t }] : rows);

    // Records
    const biggest = (side) => d3.greatest(list.filter((m) => result(m, A) === side), (m) => { const [x, y] = goalsOf(m, A); return Math.abs(x - y) * 100 + Math.max(x, y); });
    const run = (test) => {
      let best = null, cur = null;
      list.forEach((m) => {
        if (test(result(m, A))) {
          cur = cur ? { ...cur, n: cur.n + 1, to: m } : { n: 1, from: m, to: m };
          if (!best || cur.n > best.n) best = cur;
        } else cur = null;
      });
      return best;
    };
    const scoreOf = (m) => { const [x, y] = goalsOf(m, A); return `${x}–${y}`; };
    const yearOf = (m) => dateOf(m.d).getUTCFullYear();
    const span = (r) => (yearOf(r.from) === yearOf(r.to) ? String(yearOf(r.from)) : `${yearOf(r.from)}–${yearOf(r.to)}`);
    const recRows = [];
    for (const [s, i] of [["a", A], ["b", B]]) {
      const big = biggest(s);
      if (big) recRows.push({ what: `Biggest win, ${name(i)}`, value: s === "a" ? scoreOf(big) : scoreOf(big).split("–").reverse().join("–"), sub: `${fmtDay(dateOf(big.d))} · ${T[big.t]}` });
    }
    for (const [s, i] of [["a", A], ["b", B]]) {
      const w = run((r) => r === s);
      if (w && w.n > 1) recRows.push({ what: `Most wins in a row, ${name(i)}`, value: String(w.n), sub: span(w) });
      const u = run((r) => r !== (s === "a" ? "b" : "a"));
      if (u && u.n > 1) recRows.push({ what: `Longest unbeaten run, ${name(i)}`, value: String(u.n), sub: span(u) });
    }
    const last10 = tally(list.slice(-10), A);
    recRows.push({ what: `Last ${last10.n}`, value: `${last10.a}–${last10.d}–${last10.b}`, sub: `${name(A)} wins, draws, ${name(B)} wins` });
    F.richTable(document.getElementById("records-table"), [
      { label: "", render: (r) => F.withSub(document.createTextNode(r.what), r.sub) },
      { label: "", cls: "num strong", render: (r) => r.value },
    ], recRows);

    // Every match
    document.getElementById("matches-title").textContent = `Every match (${list.length})`;
    F.richTable(document.getElementById("matches-table"), [
      { label: "Date", render: (m) => F.withSub(document.createTextNode(fmtDay(dateOf(m.d))), T[m.t]) },
      { label: "Home", cls: "hide-sm", render: (m) => (m.neutral ? el("span", "muted", "Neutral") : label(m.h)) },
      { label: "Result", render: (m) => {
        const r = result(m, A);
        const s = el("span", `result result-${r}`);
        s.append(F.flag(key(m.h)), document.createTextNode(` ${m.hs}–${m.as} `), F.flag(key(m.a)));
        return F.withSub(s, m.so ? `${name(m.so === 1 ? m.h : m.a)} won on penalties` : `${name(m.h)} vs ${name(m.a)}`);
      } },
    ], list.slice().reverse());
  }

  let leadPts = [];
  function renderLead(width) {
    const root = document.getElementById("lead-chart");
    if (!leadPts.length) return root.replaceChildren();
    const height = width < 640 ? 200 : 240;
    const m = { t: 10, r: 10, b: 26, l: 34 };
    const x = d3.scaleUtc().domain(d3.extent(leadPts, (p) => p.when)).range([m.l, width - m.r]);
    const ext = Math.max(2, d3.max(leadPts, (p) => Math.abs(p.lead)));
    const y = d3.scaleLinear().domain([-ext, ext]).nice().range([height - m.b, m.t]);
    const svg = d3.create("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", "Wins ahead in the head to head over time");
    const yt = y.ticks(5);
    svg.append("g").selectAll("line").data(yt).join("line").attr("class", (d) => (d === 0 ? "baseline" : "gridline"))
      .attr("x1", m.l).attr("x2", width - m.r).attr("y1", y).attr("y2", y);
    svg.append("g").attr("class", "axis").selectAll("text").data(yt).join("text")
      .attr("x", m.l - 6).attr("y", (d) => y(d) + 4).attr("text-anchor", "end").text((d) => Math.abs(d));
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${height - m.b})`)
      .call(d3.axisBottom(x).ticks(width < 640 ? 5 : 10).tickSize(0).tickPadding(8)).call((g) => g.select(".domain").remove());
    // Two areas clipped at zero: the leader's color fills the gap to the line.
    const area = d3.area().curve(d3.curveStepAfter).x((p) => x(p.when)).y0(y(0));
    svg.append("path").attr("fill", COLOR.a).attr("fill-opacity", 0.85).attr("d", area.y1((p) => y(Math.max(0, p.lead)))(leadPts));
    svg.append("path").attr("fill", COLOR.b).attr("fill-opacity", 0.85).attr("d", area.y1((p) => y(Math.min(0, p.lead)))(leadPts));
    const bis = d3.bisector((p) => p.when).right;
    svg.append("rect").attr("x", m.l).attr("y", m.t).attr("width", width - m.l - m.r).attr("height", height - m.t - m.b).attr("fill", "transparent")
      .on("pointermove", (event) => {
        const p = leadPts[Math.max(0, bis(leadPts, x.invert(d3.pointer(event)[0])) - 1)];
        Viz.showTip(event, (t) => {
          t.append(ttTitle(`${fmtDay(p.when)} · ${T[p.m.t]}`), ttNote(`${name(p.m.h)} ${p.m.hs}–${p.m.as} ${name(p.m.a)}`));
          const lead = p.lead;
          t.append(lead === 0 ? ttNote("Level") : ttRow(lead > 0 ? COLOR.a : COLOR.b, Math.abs(lead), ` ${name(lead > 0 ? state.a : state.b)} ahead`));
        });
      })
      .on("pointerleave", Viz.hideTip);
    root.replaceChildren(svg.node());
  }
  const rerenderLead = Viz.responsive("lead-chart", renderLead);
  renderH2H();

  /* ---------- Elo ---------- */

  const SLOTS = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)"];
  const chartTeams = Object.keys(elo.series).map(Number).sort((x, y) => d3.ascending(name(x), name(y)));
  const picked = new Map();
  ["Brazil", "Argentina", "Germany", "Spain"].map((n) => byName.get(n)).filter((i) => elo.series[i]).forEach((i, s) => picked.set(i, s));
  const chips = new Map();
  chartTeams.forEach((i) => {
    const b = el("button");
    b.type = "button";
    b.append(F.flag(key(i)), document.createTextNode(name(i)));
    b.addEventListener("click", () => {
      if (picked.has(i)) picked.delete(i);
      else {
        if (picked.size >= SLOTS.length) picked.delete(picked.keys().next().value);
        const used = new Set(picked.values());
        picked.set(i, SLOTS.findIndex((_, s) => !used.has(s)));
      }
      syncChips();
      rerenderElo();
    });
    chips.set(i, b);
    document.getElementById("elo-chips").append(b);
  });
  function syncChips() {
    chips.forEach((b, i) => {
      b.setAttribute("aria-pressed", String(picked.has(i)));
      if (picked.has(i)) b.style.setProperty("--c", SLOTS[picked.get(i)]);
    });
    Viz.legend("elo-legend", [...picked].sort((x, y) => x[1] - y[1]).map(([i, s]) => ({ label: name(i), color: SLOTS[s] })), "line");
  }
  syncChips();
  document.getElementById("elo-note").textContent =
    `The rating at the end of each year the team played; teams with at least ${elo.meta.chartMin} matches. A gap is a year without matches.`;

  function renderElo(width) {
    const root = document.getElementById("elo-chart");
    const chosen = [...picked].sort((x, y) => x[1] - y[1]);
    if (!chosen.length) return root.replaceChildren(el("p", "chart-note", "Pick a team above."));
    const narrow = width < 640;
    const height = narrow ? 280 : 380;
    const m = { t: 10, r: narrow ? 12 : 100, b: 26, l: 44 };
    // A null breaks the line where a team skipped a year.
    const lines = chosen.map(([i, s]) => ({ i, s, pts: elo.series[i].flatMap(([yr, r], k, all) => (k && yr - all[k - 1][0] > 1 ? [null] : []).concat([{ yr, r }])) }));
    const all = lines.flatMap((l) => l.pts.filter(Boolean));
    const x = d3.scaleLinear().domain([1872, d3.max(all, (p) => p.yr)]).range([m.l, width - m.r]);
    const y = d3.scaleLinear().domain([Math.min(1400, d3.min(all, (p) => p.r)), d3.max(all, (p) => p.r)]).nice().range([height - m.b, m.t]);
    const svg = d3.create("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", "Elo rating at the end of each year");
    const yt = y.ticks(6);
    svg.append("g").selectAll("line").data(yt).join("line").attr("class", "gridline").attr("x1", m.l).attr("x2", width - m.r).attr("y1", y).attr("y2", y);
    svg.append("g").attr("class", "axis").selectAll("text").data(yt).join("text").attr("x", m.l - 6).attr("y", (d) => y(d) + 4).attr("text-anchor", "end").text((d) => d);
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${height - m.b})`)
      .call(d3.axisBottom(x).ticks(narrow ? 5 : 12).tickFormat(d3.format("d")).tickSize(0).tickPadding(8)).call((g) => g.select(".domain").remove());
    const line = d3.line().defined((p) => p).x((p) => x(p.yr)).y((p) => y(p.r));
    lines.forEach((l) => {
      svg.append("path").attr("class", "trend-line").attr("stroke", SLOTS[l.s]).attr("d", line(l.pts));
      const last = l.pts[l.pts.length - 1];
      if (!narrow && x.domain()[1] - last.yr <= 1) svg.append("text").attr("class", "label-muted").attr("x", x(last.yr) + 6).attr("y", y(last.r) + 4).text(name(l.i));
    });
    const hair = svg.append("line").attr("class", "crosshair").attr("y1", m.t).attr("y2", height - m.b).style("display", "none");
    const dots = svg.append("g");
    svg.append("rect").attr("x", m.l).attr("y", m.t).attr("width", width - m.l - m.r).attr("height", height - m.t - m.b).attr("fill", "transparent")
      .on("pointermove", (event) => {
        const yr = Math.round(x.invert(d3.pointer(event)[0]));
        const hits = lines.map((l) => ({ ...l, p: l.pts.find((p) => p && p.yr === yr) })).filter((h) => h.p);
        hair.style("display", null).attr("x1", x(yr)).attr("x2", x(yr));
        dots.selectAll("circle").data(hits).join("circle").attr("class", "trend-dot").attr("r", 4).attr("cx", (h) => x(h.p.yr)).attr("cy", (h) => y(h.p.r)).attr("fill", (h) => SLOTS[h.s]);
        Viz.showTip(event, (t) => {
          t.append(ttTitle(String(yr)));
          hits.sort((p, q) => q.p.r - p.p.r).forEach((h) => t.append(ttRow(SLOTS[h.s], h.p.r, ` ${name(h.i)}`)));
          if (!hits.length) t.append(ttNote("None of these teams played that year."));
        });
      })
      .on("pointerleave", () => { hair.style("display", "none"); dots.selectAll("circle").remove(); Viz.hideTip(); });
    root.replaceChildren(svg.node());
  }
  const rerenderElo = Viz.responsive("elo-chart", renderElo);

  const bestBy = d3.groups(elo.best, (b) => b.team).map(([i, list]) => ({ i, years: list.map((b) => b.year) })).sort((p, q) => q.years.length - p.years.length);
  const ranges = (ys) => ys.reduce((out, y) => {
    const last = out[out.length - 1];
    if (last && y === last[1] + 1) last[1] = y;
    else out.push([y, y]);
    return out;
  }, []).map(([p, q]) => (p === q ? String(p) : `${p}–${q}`)).join(", ");
  F.rankList(document.getElementById("best-list"), bestBy.slice(0, 15).map((b) => ({
    icon: F.flag(key(b.i)), label: name(b.i), value: b.years.length, second: `last ${b.years[b.years.length - 1]}`, color: "var(--series-1)",
    tip: (t) => t.append(ttTitle(name(b.i)), ttNote(`World's best at the end of ${b.years.length} years: ${ranges(b.years)}`)),
  })), ["Team", "Years", ""]);

  F.rankList(document.getElementById("current-list"), elo.current.slice(0, 20).map((c) => ({
    icon: F.flag(key(c.team)), label: name(c.team), value: c.rating - 1500, second: `${c.change >= 0 ? "+" : "−"}${Math.abs(c.change)}`, color: "var(--series-1)",
  })), ["Team", "Rating", "Change"]);
  // The bars start at 1500 so the differences show; print the real rating.
  document.querySelectorAll("#current-list .rank-row .num.strong").forEach((n, i) => (n.textContent = String(elo.current[i].rating)));

  F.richTable(document.getElementById("peaks-table"), [
    { label: "#", cls: "rank", render: (p) => String(elo.peaks.indexOf(p) + 1) },
    { label: "Team", render: (p) => F.withSub(label(p.team), fmtDay(d3.utcParse("%Y-%m-%d")(p.date))) },
    { label: "Peak", cls: "num strong", render: (p) => String(p.rating) },
  ], elo.peaks.slice(0, 12));

  F.richTable(document.getElementById("upsets-table"), [
    { label: "Chance", cls: "num strong", render: (u) => pct(u.p, 1) },
    { label: "Winner", render: (u) => F.withSub(label(u.winner), `${u.score} vs ${name(u.loser)} · ${u.rw} vs ${u.rl}`) },
    { label: "Date", cls: "hide-sm", render: (u) => F.withSub(document.createTextNode(fmtDay(d3.utcParse("%Y-%m-%d")(u.date))), u.tournament) },
  ], elo.upsets.slice(0, 12));

  /* ---------- All-time table ---------- */

  const SORTS = [
    { key: "pld", label: "Matches", value: (r) => r.n },
    { key: "w", label: "Wins", value: (r) => r.w },
    { key: "pct", label: "Win %", value: (r) => r.w / r.n },
    { key: "gd", label: "Goal difference", value: (r) => r.gf - r.ga },
  ];
  const tableState = { sort: "w", kind: "all" };
  function renderTable() {
    const rows = teams.map((_, i) => ({ i, n: 0, w: 0, d: 0, l: 0, gf: 0, ga: 0 }));
    M.forEach((m) => {
      if (tableState.kind === "competitive" && m.t === FRIENDLY) return;
      for (const [me, gf, ga] of [[m.h, m.hs, m.as], [m.a, m.as, m.hs]]) {
        const r = rows[me];
        r.n += 1; r.gf += gf; r.ga += ga;
        r[gf > ga ? "w" : gf < ga ? "l" : "d"] += 1;
      }
    });
    const s = SORTS.find((x) => x.key === tableState.sort);
    const list = rows.filter((r) => r.n >= 100).sort((p, q) => s.value(q) - s.value(p) || q.n - p.n);
    document.getElementById("alltime-lede").textContent =
      `${list.length} national teams with at least 100 ${tableState.kind === "competitive" ? "competitive matches (friendlies left out)" : "matches"}.`;
    F.richTable(document.getElementById("alltime-table"), [
      { label: "#", cls: "rank", render: (r) => String(list.indexOf(r) + 1) },
      { label: "Team", render: (r) => label(r.i) },
      { label: "P", cls: "num", render: (r) => d3.format(",")(r.n) },
      { label: "W", cls: "num strong", render: (r) => d3.format(",")(r.w) },
      { label: "D", cls: "num hide-sm", render: (r) => String(r.d) },
      { label: "L", cls: "num hide-sm", render: (r) => String(r.l) },
      { label: "Goals", cls: "num hide-sm", render: (r) => `${d3.format(",")(r.gf)}–${d3.format(",")(r.ga)}` },
      { label: "Win %", cls: "num", render: (r) => pct(r.w / r.n, 1) },
    ], list);
  }
  Viz.segmented("alltime-sort", SORTS, tableState.sort, (k) => { tableState.sort = k; renderTable(); });
  Viz.segmented("alltime-kind", [{ key: "all", label: "All matches" }, { key: "competitive", label: "Without friendlies" }], "all", (k) => { tableState.kind = k; renderTable(); });
  renderTable();
})();
