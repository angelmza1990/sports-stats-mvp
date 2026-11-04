/* Chess Rivalries: every game between two of the greats, classical, rapid and blitz, with the head to head worked out here. */
(async function () {
  "use strict";

  const { el, responsive, ttTitle, ttNote, ttRow } = Viz;
  const all = await d3.json(document.body.dataset.src);
  const { players, federations } = all;
  const byId = new Map(all.rivalries.map((r) => [r.id, r]));
  const COLOR = { a: "var(--team-a)", b: "var(--team-b)", d: "var(--draw)" };
  // One validated pair for every rivalry: the first player blue, the second gold.
  const PAIR = { light: ["#245fd4", "#ce9707"], dark: ["#245fd4", "#b68611"] };
  const MODES = [["all", "All games"], ["classical", "Classical"], ["rapid", "Rapid"], ["blitz", "Blitz"]];
  const parse = d3.utcParse("%Y-%m-%d");
  const fmtDate = d3.utcFormat("%-d %b %Y");

  let data, A, B, mode = "all";

  /* ---------- Helpers ---------- */

  const name = (k) => players[k]?.name ?? k;
  const surname = (k) => (k === "ding" ? "Ding" : k === "hou" ? "Hou" : k === "gukesh" ? "Gukesh" : name(k).split(" ").slice(-1)[0]);
  const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
  const pts = (x) => d3.format(".1~f")(x).replace(".5", "½").replace(/^0½/, "½");
  // Only the year is known for games without a full date in the files.
  const dateText = (g) => (g.date.endsWith("-01-01") ? String(g.year) : fmtDate(g.when));
  const result = (g) => (g.s === 1 ? A : g.s === 0 ? B : null);
  const tally = (list) => ({ a: list.filter((g) => g.s === 1).length, d: list.filter((g) => g.s === 0.5).length, b: list.filter((g) => g.s === 0).length, n: list.length });
  const games = () => (mode === "all" ? data.games : data.games.filter((g) => g.mode === mode));

  function flag(k) {
    const iso = federations[players[k]?.fed]?.flag;
    if (!iso) return el("span", "flag-code", players[k]?.fed ?? "");
    const img = el("img", "flag");
    img.src = Viz.flagUrl(iso);
    img.alt = federations[players[k].fed].name;
    img.title = federations[players[k].fed].name;
    img.loading = "lazy";
    return img;
  }

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

  function freshChart(id) {
    const old = document.getElementById(id);
    const node = el("div", old.className);
    node.id = id;
    old.replaceWith(node);
    return node;
  }

  function table(rootId, columns, rows) {
    const t = el("table");
    const head = el("tr");
    columns.forEach((c) => head.append(el("th", c.cls, c.label)));
    t.append(head);
    rows.forEach((r) => {
      const tr = el("tr", r._cls);
      columns.forEach((c) => {
        const td = el("td", c.cls);
        const v = c.render(r);
        td.append(typeof v === "string" ? document.createTextNode(v) : v);
        tr.append(td);
      });
      t.append(tr);
    });
    document.getElementById(rootId).replaceChildren(t);
  }

  /* ---------- Picker ---------- */

  function picker(currentId) {
    const root = document.getElementById("picker");
    root.replaceChildren();
    const grid = el("div", "picker-grid");
    grid.setAttribute("role", "tablist");
    grid.setAttribute("aria-label", "Rivalry");
    all.rivalries.forEach((r) => {
      const b = el("button");
      b.type = "button";
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", String(r.id === currentId));
      const crests = el("span", "crests");
      r.players.forEach((p) => crests.append(flag(p)));
      const [p, q] = r.players;
      const title = r.titleMatches.length ? ` · ${plural(r.titleMatches.length, "title match", "title matches")}` : "";
      b.append(crests, el("strong", null, `${surname(p)}–${surname(q)}`), el("small", null, `${plural(r.games.length, "game")} since ${r.games[0].year}${title}`));
      b.addEventListener("click", () => select(r.id));
      grid.append(b);
    });
    root.append(grid);
  }

  function applyColors() {
    const c = Viz.isDark() ? PAIR.dark : PAIR.light;
    document.body.style.setProperty("--team-a", c[0]);
    document.body.style.setProperty("--team-b", c[1]);
  }
  Viz.onThemeChange(() => data && (applyColors(), render()));

  function select(id) {
    data = byId.get(id);
    data.games.forEach((g) => (g.when = parse(g.date)));
    [A, B] = data.players;
    applyColors();
    picker(id);
    try {
      history.replaceState(null, "", `#${id}`);
    } catch (e) {}
    // A rivalry without games in the chosen time control falls back to all games.
    if (mode !== "all" && !data.games.some((g) => g.mode === mode)) mode = "all";
    modeTabs();
    render();
  }

  function modeTabs() {
    const counts = d3.rollup(data.games, (v) => v.length, (g) => g.mode);
    const options = MODES.filter(([k]) => k === "all" || counts.get(k)).map(([key, label]) => ({ key, label: key === "all" ? label : `${label} (${counts.get(key)})` }));
    Viz.segmented("mode-tabs", options, mode, (k) => {
      mode = k;
      render();
    });
  }

  /* ---------- Summary ---------- */

  function versus() {
    const r = tally(games());
    const head = document.getElementById("rv-versus");
    head.replaceChildren();
    const side = (k, wins, right) => {
      const s = el("div", `rv-side${right ? " right" : ""}`);
      const txt = el("div");
      txt.append(el("div", "rv-name", name(k)), el("div", "rv-wins", String(wins)), el("div", "rv-label", wins === 1 ? "win" : "wins"));
      const f = flag(k);
      f.classList.add("rv-flag");
      s.append(f, txt);
      return s;
    };
    const mid = el("div", "rv-mid");
    mid.append(el("div", "rv-draws", String(r.d)), el("div", "rv-label", r.d === 1 ? "draw" : "draws"));
    head.append(side(A, r.a), mid, side(B, r.b, true));
    head.setAttribute("aria-label", `${name(A)} ${r.a} wins, ${r.d} draws, ${name(B)} ${r.b} wins`);
    split(document.getElementById("rv-split"), [{ n: r.a, color: COLOR.a }, { n: r.d, color: COLOR.d }, { n: r.b, color: COLOR.b }]);
    const detail = document.getElementById("rv-detail");
    detail.replaceChildren();
    MODES.slice(1).forEach(([k, label]) => {
      const t = tally(data.games.filter((g) => g.mode === k));
      if (!t.n) return;
      const s = el("span");
      s.append(el("strong", null, `${t.a}–${t.d}–${t.b}`), document.createTextNode(` ${label.toLowerCase()}`));
      detail.append(s);
    });
    document.getElementById("blurb").textContent = data.blurb;
  }

  function stats() {
    const root = document.getElementById("stats");
    root.replaceChildren();
    const list = games();
    const r = tally(list);
    const last = list[list.length - 1];
    const tile = (label, value, detail) => {
      const box = el("div", "stat");
      box.append(el("span", "label", label), el("div", "value", value), el("span", "detail", detail));
      root.append(box);
    };
    tile("Games", String(r.n), `${list[0].year}–${last.year}${mode === "all" ? "" : `, ${mode}`}`);
    tile("Score", `${pts(r.a + r.d / 2)}–${pts(r.b + r.d / 2)}`, `${surname(A)}–${surname(B)}, a point a win and half a draw`);
    tile("Draws", `${d3.format(".0%")(r.n ? r.d / r.n : 0)}`, `${plural(r.d, "game")} drawn`);
    const res = last.s === 1 ? `${surname(A)} won` : last.s === 0 ? `${surname(B)} won` : "Draw";
    tile("Latest game", res, `${last.event} · ${dateText(last)}`);
  }

  /* ---------- The lead, game by game ---------- */

  function timeline() {
    const list = games();
    let diff = 0, ra = 0, rb = 0, rd = 0;
    const points = list.map((g, i) => {
      if (g.s === 1) (diff++, ra++);
      else if (g.s === 0) (diff--, rb++);
      else rd++;
      return { g, i, diff, ra, rb, rd };
    });
    const maxA = d3.greatest(points, (p) => p.diff);
    const maxB = d3.least(points, (p) => p.diff);
    const now = points[points.length - 1].diff;
    const lead = (v) => (v > 0 ? `${surname(A)} +${v}` : v < 0 ? `${surname(B)} +${-v}` : "level");
    document.getElementById("timeline-note").textContent =
      `${surname(A)} led by as many as ${Math.max(0, maxA.diff)}${maxA.diff > 0 ? ` (${maxA.g.year})` : ""}; ` +
      `${surname(B)} by as many as ${Math.max(0, -maxB.diff)}${maxB.diff < 0 ? ` (${maxB.g.year})` : ""}. Today: ${lead(now)}.`;
    Viz.legend("timeline-legend", [
      { label: `${surname(A)} ahead`, color: COLOR.a },
      { label: `${surname(B)} ahead`, color: COLOR.b },
    ]);
    const node = freshChart("timeline-chart");
    responsive(node, (width) => {
      const container = d3.select(node);
      container.selectAll("*").remove();
      const narrow = width < 560;
      const margin = { top: 20, right: 14, bottom: 26, left: narrow ? 34 : 40 };
      const height = narrow ? 240 : 320;
      // Games are spaced evenly, so a year of many games takes more room than a quiet one.
      const x = d3.scaleLinear().domain([0, Math.max(1, points.length)]).range([margin.left, width - margin.right]);
      const ext = Math.max(3, d3.max(points, (p) => Math.abs(p.diff)));
      const y = d3.scaleLinear().domain([-ext, ext]).nice().range([height - margin.bottom, margin.top]);
      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img")
        .attr("aria-label", `Lead after each of ${points.length} games. Today: ${lead(now)}.`);
      const axis = svg.append("g").attr("class", "axis");
      y.ticks(narrow ? 5 : 7).filter(Number.isInteger).forEach((v) => {
        axis.append("line").attr("class", v === 0 ? "baseline" : "gridline").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", y(v)).attr("y2", y(v));
        axis.append("text").attr("x", margin.left - 6).attr("y", y(v)).attr("dy", "0.32em").attr("text-anchor", "end").text(v > 0 ? `+${v}` : v < 0 ? `+${-v}` : "0");
      });
      // The year at evenly spaced games.
      const marks = Math.min(narrow ? 4 : 8, points.length);
      let lastYear = null;
      d3.range(marks).map((k) => Math.round((k * (points.length - 1)) / Math.max(1, marks - 1))).forEach((i) => {
        const yr = points[i].g.year;
        if (yr === lastYear) return;
        lastYear = yr;
        axis.append("text").attr("x", x(i + 0.5)).attr("y", height - 6).attr("text-anchor", "middle").text(yr);
      });
      axis.append("text").attr("class", "label-muted").attr("x", margin.left + 6).attr("y", margin.top - 6).text(`↑ ${surname(A)} ahead`);
      axis.append("text").attr("class", "label-muted").attr("x", margin.left + 6).attr("y", height - margin.bottom - 6).text(`↓ ${surname(B)} ahead`);
      const step = [{ i: -1, diff: 0 }, ...points];
      const area = (f) => d3.area().curve(d3.curveStepAfter).x((p) => x(p.i + 1)).y0(y(0)).y1((p) => y(f(p.diff)));
      svg.append("path").attr("d", area((v) => Math.max(0, v))(step)).attr("fill", COLOR.a).attr("fill-opacity", 0.28);
      svg.append("path").attr("d", area((v) => Math.min(0, v))(step)).attr("fill", COLOR.b).attr("fill-opacity", 0.28);
      svg.append("path").attr("d", d3.line().curve(d3.curveStepAfter).x((p) => x(p.i + 1)).y((p) => y(p.diff))(step))
        .attr("fill", "none").attr("stroke", "var(--ink-2)").attr("stroke-width", 2);
      const mark = (p, c, label) => {
        const cx = x(p.i + 1), anchor = cx > width * 0.7 ? "end" : "start";
        svg.append("circle").attr("cx", cx).attr("cy", y(p.diff)).attr("r", 4.5).attr("fill", c).attr("stroke", "var(--surface)").attr("stroke-width", 2);
        if (label) svg.append("text").attr("class", "label-value").attr("x", cx + (anchor === "end" ? -8 : 8)).attr("y", y(p.diff) + (p.diff >= 0 ? -8 : 16)).attr("text-anchor", anchor).text(label);
      };
      if (maxA.diff > 0) mark(maxA, COLOR.a, `+${maxA.diff}`);
      if (maxB.diff < 0) mark(maxB, COLOR.b, `+${-maxB.diff}`);
      const cross = svg.append("g").attr("pointer-events", "none").style("display", "none");
      cross.append("line").attr("class", "gridline").attr("y1", margin.top).attr("y2", height - margin.bottom).attr("stroke", "var(--ink-muted)");
      const cdot = cross.append("circle").attr("r", 5).attr("stroke", "var(--surface)").attr("stroke-width", 2);
      const show = (event, p) => {
        cross.style("display", null).attr("transform", `translate(${x(p.i + 1)},0)`);
        cdot.attr("cy", y(p.diff)).attr("fill", p.g.s === 1 ? COLOR.a : p.g.s === 0 ? COLOR.b : COLOR.d);
        Viz.showTip(event, (t) => {
          t.append(ttTitle(`${dateText(p.g)} · game ${p.i + 1}`));
          const w = result(p.g);
          t.append(ttRow(w === A ? COLOR.a : w === B ? COLOR.b : COLOR.d, w ? `${surname(w)} won` : "Draw", ` · ${surname(p.g.white)} had white`));
          t.append(ttNote(`${p.g.event} · ${p.g.mode}`));
          t.append(ttNote(`After it: ${surname(A)} ${p.ra} · draws ${p.rd} · ${surname(B)} ${p.rb} (${lead(p.diff)})`));
        });
      };
      const overlay = svg.append("rect").attr("class", "hit").attr("x", margin.left).attr("y", margin.top)
        .attr("width", width - margin.left - margin.right).attr("height", height - margin.top - margin.bottom).attr("fill", "transparent")
        .attr("tabindex", 0).attr("aria-label", "Explore the games; use the left and right arrow keys");
      let idx = points.length - 1;
      overlay.on("pointermove pointerenter", (event) => {
        const [px] = d3.pointer(event);
        idx = Math.max(0, Math.min(points.length - 1, Math.floor(x.invert(px))));
        show(event, points[idx]);
      }).on("pointerleave blur", () => {
        cross.style("display", "none");
        Viz.hideTip();
      }).on("focus", (event) => show(event, points[idx])).on("keydown", (event) => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        idx = Math.max(0, Math.min(points.length - 1, idx + (event.key === "ArrowRight" ? 1 : -1)));
        show(event, points[idx]);
      });
    });
  }

  /* ---------- Year by year ---------- */

  function years() {
    const list = games();
    const byYear = d3.rollup(list, (v) => ({ ...tally(v), events: d3.rollups(v, (w) => w.length, (g) => g.event).sort((p, q) => q[1] - p[1]) }), (g) => g.year);
    Viz.legend("years-legend", [
      { label: `${surname(A)} wins`, color: COLOR.a },
      { label: "Draws", color: COLOR.d },
      { label: `${surname(B)} wins`, color: COLOR.b },
    ]);
    const node = freshChart("years-chart");
    responsive(node, (width) => {
      const container = d3.select(node);
      container.selectAll("*").remove();
      const narrow = width < 560;
      const margin = { top: 12, right: 10, bottom: 24, left: 30 };
      const height = narrow ? 220 : 280;
      const span = d3.range(list[0].year, list[list.length - 1].year + 1);
      const x = d3.scaleBand().domain(span).range([margin.left, width - margin.right]).paddingInner(span.length > 40 ? 0.12 : 0.22);
      const y = d3.scaleLinear().domain([0, d3.max(byYear.values(), (v) => v.n) || 1]).nice().range([height - margin.bottom, margin.top]);
      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img")
        .attr("aria-label", `Games between ${name(A)} and ${name(B)} each year, ${span[0]} to ${span[span.length - 1]}.`);
      const axis = svg.append("g").attr("class", "axis");
      y.ticks(4).filter(Number.isInteger).forEach((v) => {
        axis.append("line").attr("class", v === 0 ? "baseline" : "gridline").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", y(v)).attr("y2", y(v));
        axis.append("text").attr("x", margin.left - 6).attr("y", y(v)).attr("dy", "0.32em").attr("text-anchor", "end").text(v);
      });
      const every = Math.max(1, Math.ceil(span.length / (narrow ? 5 : 10)));
      span.filter((yr, i) => i % every === 0).forEach((yr) => axis.append("text").attr("x", x(yr) + x.bandwidth() / 2).attr("y", height - 6).attr("text-anchor", "middle").text(yr));
      const bw = x.bandwidth();
      byYear.forEach((v, yr) => {
        // Stacked from the baseline: first player's wins, draws, second player's wins, with a 2px surface gap.
        let base = y(0);
        [[v.a, COLOR.a], [v.d, COLOR.d], [v.b, COLOR.b]].forEach(([n, c], k, arr) => {
          if (!n) return;
          const h = y(0) - y(n);
          const top = k === arr.length - 1 || !arr.slice(k + 1).some(([m]) => m);
          const r = top ? Math.min(4, bw / 2, h) : 0;
          const y0 = base - h;
          svg.append("path").attr("fill", c).attr("d",
            `M${x(yr)},${base}V${y0 + r}Q${x(yr)},${y0} ${x(yr) + r},${y0}H${x(yr) + bw - r}Q${x(yr) + bw},${y0} ${x(yr) + bw},${y0 + r}V${base}Z`);
          base = y0 - (h > 2 ? 2 : 0);
        });
        const hit = svg.append("rect").attr("class", "hit").attr("x", x(yr) - (x.step() - bw) / 2).attr("y", margin.top)
          .attr("width", x.step()).attr("height", height - margin.top - margin.bottom).attr("fill", "transparent");
        hit.on("pointerenter pointermove", (event) => Viz.showTip(event, (t) => {
          t.append(ttTitle(`${yr} · ${plural(v.n, "game")}`));
          t.append(ttRow(COLOR.a, String(v.a), ` ${surname(A)} wins`), ttRow(COLOR.d, String(v.d), " draws"), ttRow(COLOR.b, String(v.b), ` ${surname(B)} wins`));
          t.append(ttNote(v.events.slice(0, 4).map(([e, n]) => `${e} (${n})`).join(" · ") + (v.events.length > 4 ? ` · ${v.events.length - 4} more` : "")));
        })).on("pointerleave", () => Viz.hideTip());
      });
    });
    table("games-table", [
      { label: "Date", render: (g) => dateText(g) },
      { label: "Event", render: (g) => g.event },
      { label: "White", render: (g) => surname(g.white) },
      { label: "Result", render: (g) => (g.s === 0.5 ? "½–½" : `${surname(result(g))} won`) },
      { label: "Time control", cls: "hide-sm", render: (g) => g.mode },
    ], [...list].reverse());
  }

  /* ---------- With each color, where they met, title matches ---------- */

  function colors() {
    const list = games();
    const rows = [A, B].map((k) => {
      const white = list.filter((g) => g.white === k);
      const black = list.filter((g) => g.white !== k);
      const score = (v) => (k === A ? tally(v) : { a: tally(v).b, d: tally(v).d, b: tally(v).a, n: v.length });
      return { k, w: score(white), bl: score(black) };
    });
    const cell = (t) => (t.n ? `${t.a}–${t.d}–${t.b}` : "–");
    const pct = (t) => (t.n ? d3.format(".0%")((t.a + t.d / 2) / t.n) : "–");
    table("colors-table", [
      { label: "Player", render: (r) => surname(r.k) },
      { label: "With white", cls: "num", render: (r) => cell(r.w) },
      { label: "Score", cls: "num strong", render: (r) => pct(r.w) },
      { label: "With black", cls: "num", render: (r) => cell(r.bl) },
      { label: "Score", cls: "num strong", render: (r) => pct(r.bl) },
    ], rows);
    document.getElementById("colors-lede").textContent = "Wins, draws and losses of each player with the white and with the black pieces, and the share of the points they took.";
  }

  function events() {
    const list = games();
    const root = document.getElementById("events-list");
    root.replaceChildren();
    const ev = d3.rollups(list, (v) => ({ ...tally(v), first: v[0].year, last: v[v.length - 1].year }), (g) => g.event).sort((p, q) => q[1].n - p[1].n).slice(0, 10);
    const max = ev[0]?.[1].n || 1;
    const headRow = el("div", "rank-head");
    headRow.append(el("span"), el("span", null, "Event"), el("span"), el("span", "num", "Games"), el("span", "num", `${surname(A)}–${surname(B)}`));
    root.append(headRow);
    ev.forEach(([e, t]) => {
      const row = el("div", "rank-row");
      const cell = el("div", "bar-cell");
      const bar = el("div", "bar");
      bar.style.width = `${(t.n / max) * 100}%`;
      cell.append(bar);
      row.append(el("span"), el("span", "name", e), cell, el("span", "num strong", String(t.n)), el("span", "num", `${t.a}–${t.d}–${t.b}`));
      Viz.tooltipOnNode(row, (tip) => {
        tip.append(ttTitle(e), ttNote(`${t.first === t.last ? t.first : `${t.first}–${t.last}`} · ${plural(t.n, "game")}`));
        tip.append(ttRow(COLOR.a, String(t.a), ` ${surname(A)} wins`), ttRow(COLOR.d, String(t.d), " draws"), ttRow(COLOR.b, String(t.b), ` ${surname(B)} wins`));
      });
      root.append(row);
    });
  }

  function titleMatches() {
    const ms = data.titleMatches;
    const section = document.getElementById("title");
    section.hidden = !ms.length;
    if (!ms.length) return;
    const decided = ms.filter((m) => m.kind !== "aborted");
    const wa = decided.filter((m) => m.winner === name(A)).length;
    const off = ms.length - decided.length;
    document.getElementById("title-lede").textContent = (ms.length === 1
      ? `They played one match for the title: ${ms[0].winner} won it.`
      : `They played ${ms.length} matches for the title: ${surname(A)} won ${wa}, ${surname(B)} ${decided.length - wa}`) +
      (off ? `; the ${ms.find((m) => m.kind === "aborted").label} match was stopped without a result.` : ms.length === 1 ? "" : ".");
    table("title-table", [
      { label: "Year", render: (m) => m.label },
      { label: "Champion", cls: "strong", render: (m) => (m.kind === "aborted" ? `Stopped, ${m.winner} kept the title` : m.winner) },
      { label: "Score", cls: "num", render: (m) => m.score ?? "–" },
      { label: "Runner-up", render: (m) => m.runnerUp },
      { label: "Where", cls: "hide-sm", render: (m) => m.location ?? "" },
    ], [...ms].reverse());
  }

  function footer() {
    const src = document.getElementById("source");
    src.textContent = all.source.label;
    src.href = all.source.url;
    const last = data.games[data.games.length - 1];
    document.getElementById("data-through").textContent = `Games through ${dateText(last)}.`;
    document.getElementById("mode-note").textContent = mode === "all" ? "Classical, rapid and blitz together." : `${MODES.find(([k]) => k === mode)[1]} games only.`;
  }

  function render() {
    versus();
    stats();
    timeline();
    years();
    colors();
    events();
    titleMatches();
    footer();
  }

  const wanted = location.hash.slice(1);
  select(byId.has(wanted) ? wanted : byId.has("karpov-kasparov") ? "karpov-kasparov" : all.rivalries[0].id);
})();
