/* The Big Three: every chart on the page, built with D3 v7. */
(async function () {
  "use strict";

  const data = await d3.json("data/big-three.json");

  const PLAYERS = data.players;
  const IDS = PLAYERS.map((p) => p.id);
  const byId = Object.fromEntries(PLAYERS.map((p) => [p.id, p]));
  const color = (id) => `var(--p-${id})`;
  const reduceMotion = Viz.reduceMotion;
  const DAY = 864e5;

  const parseDate = d3.utcParse("%Y-%m-%d");
  PLAYERS.forEach((p) => {
    p.bornDate = parseDate(p.born);
    p.endDate = p.retired ? parseDate(p.retired) : new Date();
  });
  const ageAt = (pid, date) => (date - byId[pid].bornDate) / (365.25 * DAY);

  const titles = data.titles.map((t) => ({ ...t, date: parseDate(t.date) }));
  const matches = data.h2h.map((m) => ({ ...m, date: parseDate(m.date) }));

  const METRICS = [
    { key: "G", label: "Grand Slams", test: (t) => t.level === "G", min: 5 },
    { key: "M", label: "Masters 1000", test: (t) => t.level === "M", min: 5 },
    { key: "F", label: "ATP Finals", test: (t) => t.level === "F", min: 3 },
    { key: "all", label: "All titles", test: () => true, min: 20 },
  ];
  const metricBy = Object.fromEntries(METRICS.map((m) => [m.key, m]));

  const ROUNDS = {
    F: "Final", SF: "Semifinal", QF: "Quarterfinal", R16: "Round of 16", R32: "Round of 32",
    R64: "Round of 64", R128: "Round of 128", RR: "Round robin", BR: "Bronze medal match",
  };
  const LEVELS = { G: "Grand Slam", M: "Masters 1000", F: "ATP Finals", O: "Olympics", A: "ATP Tour", D: "Davis Cup" };

  const { el, table, responsive, showTip, hideTip, tooltipOn, barPath, ttTitle, ttNote } = Viz;

  const swatch = (pid, cls) => Viz.swatch(color(pid), cls);
  const ttRow = (pid, value, label) => Viz.ttRow(color(pid), value, label ?? byId[pid].name);
  const legend = (containerId, kind) =>
    Viz.legend(containerId, PLAYERS.map((p) => ({ label: p.name, color: color(p.id) })), kind);
  const segmented = (containerId, initial, onChange) => Viz.segmented(containerId, METRICS, initial, onChange);

  const count = (list, pid) => list.filter((t) => t.player === pid).length;
  const years = (list) => list.map((t) => t.date.getUTCFullYear()).join(", ");

  /* ---------- Player cards ---------- */

  (function playerCards() {
    const root = document.getElementById("player-cards");
    const stats = [
      { label: "Grand Slams", value: (pid) => count(titles.filter(metricBy.G.test), pid) },
      { label: "Masters 1000", value: (pid) => count(titles.filter(metricBy.M.test), pid) },
      { label: "ATP Finals", value: (pid) => count(titles.filter(metricBy.F.test), pid) },
      { label: "Titles", value: (pid) => count(titles, pid) },
    ];
    stats.forEach((s) => (s.max = d3.max(IDS, s.value)));
    PLAYERS.forEach((p) => {
      const card = el("article", "player-card");
      card.style.setProperty("--c", color(p.id));
      const status = p.retired ? `Retired ${p.retired.slice(0, 4)}` : "Active";
      card.append(el("h3", null, p.name), el("p", "meta", `${p.country} · Born ${p.born.slice(0, 4)} · ${status}`));
      const dl = el("dl");
      stats.forEach((s) => {
        const v = s.value(p.id);
        const box = el("div");
        box.append(el("dt", null, s.label), el("dd", v === s.max && v > 0 ? "lead" : "", String(v)));
        dl.append(box);
      });
      card.append(dl);
      root.append(card);
    });
  })();

  /* ---------- Bar chart race ---------- */

  (function race() {
    const first = d3.utcMonth.floor(d3.min(titles, (t) => t.date));
    const last = d3.utcMonth.floor(d3.max(titles, (t) => t.date));
    const months = d3.utcMonth.range(d3.utcMonth.offset(first, -1), d3.utcMonth.offset(last, 1));

    // frames[metric][i] = { counts: {pid: n}, latest: title | null }
    const frames = {};
    METRICS.forEach((m) => {
      const list = titles.filter(m.test);
      const counts = Object.fromEntries(IDS.map((id) => [id, 0]));
      let j = 0;
      let latest = null;
      frames[m.key] = months.map((month) => {
        const end = d3.utcMonth.offset(month, 1);
        while (j < list.length && list[j].date < end) {
          counts[list[j].player]++;
          latest = list[j];
          j++;
        }
        return { counts: { ...counts }, latest };
      });
    });

    const state = { metric: "G", idx: reduceMotion ? months.length - 1 : 0, playing: false, timer: null };
    const fmtDate = d3.utcFormat("%b %Y");
    const dateEl = document.getElementById("race-date");
    const tickerEl = document.getElementById("race-ticker");
    const playBtn = document.getElementById("race-play");
    const scrub = document.getElementById("race-scrub");
    const speedSel = document.getElementById("race-speed");
    scrub.max = months.length - 1;

    const rowH = 56;
    const barH = 24;
    const margin = { top: 24, right: 48, bottom: 8, left: 96 };
    const height = margin.top + rowH * IDS.length + margin.bottom;

    const svg = d3.select("#race-chart").append("svg").attr("role", "img");
    const grid = svg.append("g");
    const bars = svg.append("g");
    let width = 0;
    let x = d3.scaleLinear();

    function frameDuration() {
      return 150 / +speedSel.value;
    }

    function update(duration) {
      const frame = frames[state.metric][state.idx];
      const metric = metricBy[state.metric];
      const ranked = IDS.slice().sort((a, b) => frame.counts[b] - frame.counts[a] || IDS.indexOf(a) - IDS.indexOf(b));
      const maxVal = d3.max(IDS, (id) => frame.counts[id]);
      x.domain([0, Math.max(metric.min, maxVal * 1.08)]).range([0, width - margin.left - margin.right]);

      const t = svg.transition().duration(duration).ease(d3.easeLinear);

      svg.attr("aria-label", `${metric.label} won by ${fmtDate(months[state.idx])}: ` +
        ranked.map((id) => `${byId[id].short} ${frame.counts[id]}`).join(", "));

      const ticks = x.ticks(width < 500 ? 4 : 6).filter(Number.isInteger);
      grid
        .selectAll("g.tick")
        .data(ticks, (d) => d)
        .join(
          (enter) => {
            const g = enter.append("g").attr("class", "tick").attr("opacity", 0)
              .attr("transform", (d) => `translate(${margin.left + x(d)},0)`);
            g.append("line").attr("class", (d) => (d === 0 ? "baseline" : "gridline"))
              .attr("y1", margin.top - 6).attr("y2", height - margin.bottom);
            g.append("text").attr("class", "tick-label").attr("y", margin.top - 12).attr("text-anchor", "middle").text((d) => d);
            return g;
          },
          (update) => update,
          (exit) => exit.transition(t).attr("opacity", 0).remove()
        )
        .transition(t)
        .attr("opacity", 1)
        .attr("transform", (d) => `translate(${margin.left + x(d)},0)`);

      const rows = bars
        .selectAll("g.row")
        .data(ranked, (d) => d)
        .join((enter) => {
          const g = enter.append("g").attr("class", "row")
            .attr("transform", (d, i) => `translate(${margin.left},${margin.top + i * rowH + (rowH - barH) / 2})`);
          g.append("path").attr("class", "mark").attr("fill", (d) => color(d)).property("_w", 0);
          g.append("text").attr("class", "label-name").attr("x", -12).attr("y", barH / 2).attr("dy", "0.35em")
            .attr("text-anchor", "end").text((d) => byId[d].short);
          g.append("text").attr("class", "label-value").attr("y", barH / 2).attr("dy", "0.35em").property("_v", 0);
          return g;
        });

      rows.transition(t).attr("transform", (d, i) => `translate(${margin.left},${margin.top + i * rowH + (rowH - barH) / 2})`);

      rows.select("path").transition(t).attrTween("d", function (d) {
        const i = d3.interpolate(this._w, x(frame.counts[d]));
        return (k) => barPath(0, 0, (this._w = i(k)), barH);
      });

      rows.select("text.label-value").transition(t)
        .attrTween("x", function (d) {
          const from = +this.getAttribute("x") || 0;
          const i = d3.interpolate(from, x(frame.counts[d]) + 8);
          return (k) => i(k);
        })
        .tween("text", function (d) {
          const i = d3.interpolateRound(this._v, frame.counts[d]);
          return (k) => (this.textContent = this._v = i(k));
        });

      dateEl.textContent = fmtDate(months[state.idx]);
      scrub.value = state.idx;
      renderTicker(frame.latest);
    }

    function renderTicker(t) {
      tickerEl.replaceChildren();
      if (!t) {
        tickerEl.textContent = "No titles yet.";
        return;
      }
      tickerEl.append(swatch(t.player), el("strong", null, `${t.tourney} ${t.date.getUTCFullYear()}`),
        document.createTextNode(` · ${byId[t.player].name} def. ${t.opponent}, ${t.score}`));
    }

    function step() {
      if (state.idx >= months.length - 1) return pause();
      state.idx++;
      update(frameDuration());
      state.timer = setTimeout(step, frameDuration());
    }

    function play() {
      if (state.idx >= months.length - 1) {
        state.idx = 0;
        update(0);
      }
      state.playing = true;
      playBtn.textContent = "❚❚";
      playBtn.setAttribute("aria-label", "Pause");
      state.timer = setTimeout(step, frameDuration());
    }

    function pause() {
      state.playing = false;
      clearTimeout(state.timer);
      playBtn.textContent = state.idx >= months.length - 1 ? "↺" : "▶";
      playBtn.setAttribute("aria-label", state.idx >= months.length - 1 ? "Replay" : "Play");
    }

    playBtn.addEventListener("click", () => (state.playing ? pause() : play()));
    scrub.addEventListener("input", () => {
      pause();
      state.idx = +scrub.value;
      update(0);
    });

    function renderTable() {
      const rows = [];
      for (let i = 0; i < months.length; i++) {
        const isYearEnd = months[i].getUTCMonth() === 11 || i === months.length - 1;
        if (!isYearEnd) continue;
        const c = frames[state.metric][i].counts;
        rows.push([String(months[i].getUTCFullYear()), ...IDS.map((id) => String(c[id]))]);
      }
      table("race-table", ["End of", ...PLAYERS.map((p) => p.short)], rows.reverse());
    }

    segmented("race-metric", state.metric, (key) => {
      state.metric = key;
      update(state.playing ? frameDuration() : 400);
      renderTable();
    });

    responsive("race-chart", (w) => {
      width = w;
      svg.attr("viewBox", `0 0 ${w} ${height}`);
      update(0);
    });
    renderTable();
    pause();

    // Start the race the first time it scrolls into view.
    if (!reduceMotion) {
      const io = new IntersectionObserver((entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          io.disconnect();
          if (state.idx === 0) play();
        }
      }, { threshold: 0.6 });
      io.observe(document.getElementById("race-chart"));
    }
  })();

  /* ---------- Titles by age ---------- */

  (function byAge() {
    let metric = "G";
    legend("age-legend", "line");

    function series(key) {
      const list = titles.filter(metricBy[key].test);
      return PLAYERS.map((p) => {
        const own = list.filter((t) => t.player === p.id);
        const pts = [{ age: 17, n: 0 }];
        own.forEach((t, i) => pts.push({ age: ageAt(p.id, t.date), n: i + 1, t }));
        const endAge = ageAt(p.id, p.endDate);
        pts.push({ age: endAge, n: own.length });
        return { id: p.id, pts, total: own.length, endAge };
      });
    }

    function valueAt(s, age) {
      let n = 0;
      for (const p of s.pts) if (p.age <= age) n = p.n;
      return n;
    }

    const render = (width) => {
      const container = d3.select("#age-chart");
      container.selectAll("*").remove();
      const all = series(metric);
      const narrow = width < 520;
      const margin = { top: 12, right: narrow ? 92 : 110, bottom: 36, left: 36 };
      const height = narrow ? 300 : 380;
      const x = d3.scaleLinear().domain([17, 42]).range([margin.left, width - margin.right]);
      const y = d3.scaleLinear().domain([0, d3.max(all, (s) => s.total)]).nice(5).range([height - margin.bottom, margin.top]);

      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img")
        .attr("aria-label", `${metricBy[metric].label} by age: ` + all.map((s) => `${byId[s.id].short} ${s.total}`).join(", "));

      const gy = svg.append("g").attr("class", "axis");
      y.ticks(5).forEach((v) => {
        gy.append("line").attr("class", v === 0 ? "baseline" : "gridline").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", y(v)).attr("y2", y(v));
        gy.append("text").attr("x", margin.left - 8).attr("y", y(v)).attr("dy", "0.35em").attr("text-anchor", "end").text(v);
      });
      const gx = svg.append("g").attr("class", "axis");
      x.ticks(narrow ? 5 : 10).forEach((v) => {
        gx.append("text").attr("x", x(v)).attr("y", height - margin.bottom + 18).attr("text-anchor", "middle").text(v);
      });
      gx.append("text").attr("x", width - margin.right).attr("y", height - 4).attr("text-anchor", "end").text("Age");

      const line = d3.line().curve(d3.curveStepAfter).x((p) => x(p.age)).y((p) => y(p.n));
      svg.append("g").selectAll("path").data(all).join("path")
        .attr("d", (s) => line(s.pts)).attr("fill", "none").attr("stroke", (s) => color(s.id))
        .attr("stroke-width", 2).attr("stroke-linejoin", "round").attr("stroke-linecap", "round");

      // End markers + leader-lined labels in a right-hand column.
      const ends = all.map((s) => ({ ...s, ex: x(s.endAge), ey: y(s.total), ly: y(s.total) }));
      const sorted = ends.slice().sort((a, b) => a.ly - b.ly);
      for (let i = 1; i < sorted.length; i++) sorted[i].ly = Math.max(sorted[i].ly, sorted[i - 1].ly + 18);
      const labelX = width - margin.right + 14;
      const gEnd = svg.append("g");
      gEnd.selectAll("polyline").data(ends).join("polyline")
        .attr("points", (s) => `${s.ex},${s.ey} ${labelX - 4},${s.ly}`)
        .attr("fill", "none").attr("stroke", "var(--axis)").attr("stroke-width", 1);
      gEnd.selectAll("circle").data(ends).join("circle")
        .attr("cx", (s) => s.ex).attr("cy", (s) => s.ey).attr("r", 4.5)
        .attr("fill", (s) => color(s.id)).attr("stroke", "var(--surface)").attr("stroke-width", 2);
      gEnd.selectAll("text").data(ends).join("text").attr("class", "label-name")
        .attr("x", labelX).attr("y", (s) => s.ly).attr("dy", "0.35em")
        .text((s) => `${byId[s.id].short} ${s.total}`);

      // Crosshair
      const cross = svg.append("line").attr("class", "baseline").attr("y1", margin.top).attr("y2", height - margin.bottom).attr("opacity", 0);
      svg.append("rect").attr("x", margin.left).attr("y", margin.top).attr("width", width - margin.left - margin.right)
        .attr("height", height - margin.top - margin.bottom).attr("fill", "transparent")
        .on("pointermove", (event) => {
          const [mx] = d3.pointer(event);
          const age = Math.round(x.invert(mx) * 10) / 10;
          cross.attr("x1", x(age)).attr("x2", x(age)).attr("opacity", 1);
          showTip(event, (t) => {
            t.append(ttTitle(`By age ${age.toFixed(1)}`));
            all.slice().sort((a, b) => valueAt(b, age) - valueAt(a, age))
              .forEach((s) => t.append(ttRow(s.id, valueAt(s, age), byId[s.id].short + (age > s.endAge ? " (retired)" : ""))));
          });
        })
        .on("pointerleave", () => {
          cross.attr("opacity", 0);
          hideTip();
        });

      // Table
      const rows = [];
      all.forEach((s) => s.pts.filter((p) => p.t).forEach((p) =>
        rows.push([byId[s.id].short, String(p.n), p.age.toFixed(1), `${p.t.tourney} ${p.t.date.getUTCFullYear()}`])));
      table("age-table", ["Player", "Title #", "Age", "Tournament"], rows);
    };

    const rerender = responsive("age-chart", render);
    segmented("age-metric", metric, (key) => {
      metric = key;
      rerender();
    });
  })();

  /* ---------- Grand Slams by tournament (small multiples) ---------- */

  (function slams() {
    legend("slams-legend");
    const SLAMS = ["Australian Open", "Roland Garros", "Wimbledon", "US Open"];
    const slamTitles = titles.filter(metricBy.G.test);
    const cell = (slam, pid) => slamTitles.filter((t) => t.tourney === slam && t.player === pid);
    const maxN = d3.max(SLAMS, (s) => d3.max(IDS, (id) => cell(s, id).length));

    const root = document.getElementById("slams-chart");
    const panels = SLAMS.map((slam) => {
      const panel = el("div");
      panel.append(el("h3", null, slam));
      const chart = el("div", "chart");
      chart.id = `slam-${slam.replace(/\s+/g, "-").toLowerCase()}`;
      panel.append(chart);
      root.append(panel);
      return { slam, id: chart.id };
    });

    panels.forEach(({ slam, id }) => {
      responsive(id, (width) => {
        const container = d3.select(`#${id}`);
        container.selectAll("*").remove();
        const rowH = 28;
        const barH = 16;
        const margin = { left: 64, right: 26 };
        const height = rowH * IDS.length;
        const x = d3.scaleLinear().domain([0, maxN]).range([0, width - margin.left - margin.right]);
        const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img")
          .attr("aria-label", `${slam}: ` + IDS.map((pid) => `${byId[pid].short} ${cell(slam, pid).length}`).join(", "));
        svg.append("line").attr("class", "baseline").attr("x1", margin.left).attr("x2", margin.left).attr("y1", 0).attr("y2", height);
        const g = svg.selectAll("g.row").data(IDS).join("g").attr("class", "row mark-group")
          .attr("transform", (d, i) => `translate(${margin.left},${i * rowH})`);
        g.append("rect").attr("x", -margin.left).attr("width", width).attr("height", rowH).attr("fill", "transparent");
        g.append("path").attr("class", "mark").attr("fill", (d) => color(d))
          .attr("d", (d) => barPath(0, (rowH - barH) / 2, x(cell(slam, d).length), barH));
        g.append("text").attr("class", "label-muted").attr("x", -8).attr("y", rowH / 2).attr("dy", "0.35em")
          .attr("text-anchor", "end").text((d) => byId[d].short);
        g.append("text").attr("class", "label-value").attr("x", (d) => x(cell(slam, d).length) + 6)
          .attr("y", rowH / 2).attr("dy", "0.35em").text((d) => cell(slam, d).length);
        tooltipOn(g, (t, d) => {
          const list = cell(slam, d);
          t.append(ttTitle(slam), ttRow(d, list.length, `${byId[d].name}`));
          if (list.length) t.append(ttNote(years(list)));
        });
      });
    });

    table("slams-table", ["Player", ...SLAMS, "Total"], PLAYERS.map((p) =>
      [p.name, ...SLAMS.map((s) => String(cell(s, p.id).length)), String(count(slamTitles, p.id))]));
  })();

  /* ---------- Grouped horizontal bars (Masters, surfaces) ---------- */

  function groupedBars({ chartId, tableId, categories, cell, catLabel, title }) {
    const maxN = d3.max(categories, (c) => d3.max(IDS, (id) => cell(c, id).length));
    responsive(chartId, (width) => {
      const container = d3.select(`#${chartId}`);
      container.selectAll("*").remove();
      const narrow = width < 520;
      const barH = narrow ? 8 : 10;
      const gap = 2;
      const groupGap = 18;
      const groupH = IDS.length * (barH + gap) - gap;
      const margin = { top: 24, right: 30, bottom: 4, left: narrow ? 96 : 120 };
      const height = margin.top + categories.length * (groupH + groupGap) - groupGap + margin.bottom;
      const x = d3.scaleLinear().domain([0, maxN]).nice().range([margin.left, width - margin.right]);

      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", title);
      const axis = svg.append("g").attr("class", "axis");
      x.ticks(narrow ? 4 : 6).filter(Number.isInteger).forEach((v) => {
        axis.append("line").attr("class", v === 0 ? "baseline" : "gridline").attr("x1", x(v)).attr("x2", x(v)).attr("y1", margin.top - 6).attr("y2", height - margin.bottom);
        axis.append("text").attr("x", x(v)).attr("y", margin.top - 12).attr("text-anchor", "middle").text(v);
      });

      const groups = svg.selectAll("g.group").data(categories).join("g").attr("class", "group")
        .attr("transform", (d, i) => `translate(0,${margin.top + i * (groupH + groupGap)})`);
      groups.append("text").attr("class", "label-name").attr("x", margin.left - 10).attr("y", groupH / 2).attr("dy", "0.35em")
        .attr("text-anchor", "end").text(catLabel);

      const rows = groups.selectAll("g.row").data((c) => IDS.map((pid) => ({ c, pid, list: cell(c, pid) }))).join("g")
        .attr("class", "row mark-group").attr("transform", (d, i) => `translate(0,${i * (barH + gap)})`);
      rows.append("rect").attr("x", 0).attr("y", -gap / 2).attr("width", width).attr("height", barH + gap).attr("fill", "transparent");
      rows.append("path").attr("class", "mark").attr("fill", (d) => color(d.pid))
        .attr("d", (d) => barPath(x(0), 0, x(d.list.length) - x(0), barH, Math.min(4, barH / 2)));
      rows.append("text").attr("class", "label-muted").attr("x", (d) => x(d.list.length) + 6).attr("y", barH / 2)
        .attr("dy", "0.35em").text((d) => d.list.length);
      tooltipOn(rows, (t, d) => {
        t.append(ttTitle(catLabel(d.c)), ttRow(d.pid, d.list.length, byId[d.pid].name));
        if (d.list.length) t.append(ttNote(years(d.list)));
      });
    });

    table(tableId, ["", ...PLAYERS.map((p) => p.short)], categories.map((c) => [catLabel(c), ...IDS.map((id) => String(cell(c, id).length))]));
  }

  (function masters() {
    legend("masters-legend");
    const list = titles.filter(metricBy.M.test);
    const events = d3.groupSort(list, (g) => -g.length, (t) => t.tourney);
    groupedBars({
      chartId: "masters-chart",
      tableId: "masters-table",
      categories: events,
      cell: (event, pid) => list.filter((t) => t.tourney === event && t.player === pid),
      catLabel: (event) => event.replace(/ Masters$/, ""),
      title: "Masters 1000 titles by tournament",
    });
  })();

  (function surfaces() {
    legend("surface-legend");
    const order = ["Hard", "Clay", "Grass", "Carpet"];
    const present = order.filter((s) => titles.some((t) => t.surface === s));
    groupedBars({
      chartId: "surface-chart",
      tableId: "surface-table",
      categories: present,
      cell: (surface, pid) => titles.filter((t) => t.surface === surface && t.player === pid),
      catLabel: (s) => s,
      title: "Titles by surface",
    });
  })();

  /* ---------- Head to head ---------- */

  (function headToHead() {
    const PAIRS = [["djokovic", "nadal"], ["djokovic", "federer"], ["nadal", "federer"]];
    const root = document.getElementById("h2h-cards");

    PAIRS.forEach(([a, b], k) => {
      const list = matches.filter((m) => (m.winner === a && m.loser === b) || (m.winner === b && m.loser === a));
      const wins = (pid, filter = () => true) => list.filter((m) => m.winner === pid && filter(m)).length;
      const wa = wins(a);
      const wb = wins(b);

      const card = el("article", "h2h-card");
      const top = el("div", "h2h-top");
      const nameA = el("div", "name");
      nameA.append(swatch(a), document.createTextNode(byId[a].name));
      const nameB = el("div", "name right");
      nameB.append(document.createTextNode(byId[b].name), swatch(b));
      const score = el("div", "h2h-score");
      score.append(document.createTextNode(String(wa)), el("span", null, "–"), document.createTextNode(String(wb)));
      score.setAttribute("aria-label", `${byId[a].short} ${wa}, ${byId[b].short} ${wb}`);
      top.append(nameA, score, nameB);

      const split = el("div", "split");
      [[a, wa], [b, wb]].forEach(([pid, n]) => {
        const seg = el("div");
        seg.style.setProperty("--c", color(pid));
        seg.style.flex = String(n);
        split.append(seg);
      });

      // Breakdown table
      const groups = [
        { label: "Surface", rows: ["Hard", "Clay", "Grass", "Carpet"].map((s) => [s, (m) => m.surface === s]) },
        {
          label: "Event",
          rows: [
            ["Grand Slams", (m) => m.level === "G"],
            ["Masters 1000", (m) => m.level === "M"],
            ["ATP Finals", (m) => m.level === "F"],
            ["Other", (m) => !["G", "M", "F"].includes(m.level)],
          ],
        },
        {
          label: "Big stage",
          rows: [
            ["All finals", (m) => m.round === "F"],
            ["Grand Slam finals", (m) => m.round === "F" && m.level === "G"],
          ],
        },
      ];
      const tbl = el("table", "breakdown");
      const head = el("tr");
      head.append(el("th"), el("td", null, byId[a].short.slice(0, 3).toUpperCase()), el("td", null, byId[b].short.slice(0, 3).toUpperCase()));
      tbl.append(head);
      groups.forEach((g) => {
        const gr = el("tr", "group");
        gr.append(el("th", null, g.label));
        gr.firstChild.colSpan = 3;
        tbl.append(gr);
        g.rows.forEach(([label, f]) => {
          const x = wins(a, f);
          const y = wins(b, f);
          if (x + y === 0) return;
          const tr = el("tr");
          tr.append(el("th", null, label), el("td", x > y ? "win" : "", String(x)), el("td", y > x ? "win" : "", String(y)));
          tbl.append(tr);
        });
      });

      const timeline = el("div", "h2h-timeline");
      timeline.append(el("p", "caption",
        `${list.length} matches, ${list[0].date.getUTCFullYear()}–${list[list.length - 1].date.getUTCFullYear()} · ▲ ${byId[a].short} wins · ▼ ${byId[b].short} wins`));
      const chart = el("div", "chart");
      chart.id = `h2h-chart-${k}`;
      timeline.append(chart);

      const body = el("div", "h2h-body");
      body.append(tbl, timeline);
      card.append(top, split, body);
      root.append(card);

      responsive(chart.id, (width) => {
        const container = d3.select(chart);
        container.selectAll("*").remove();
        const y0 = d3.min(list, (m) => m.date.getUTCFullYear());
        const y1 = d3.max(list, (m) => m.date.getUTCFullYear());
        const yearsRange = d3.range(y0, y1 + 1);
        const byYear = d3.group(list, (m) => m.date.getUTCFullYear(), (m) => m.winner);
        const maxStack = d3.max(yearsRange, (yr) => d3.max([a, b], (pid) => byYear.get(yr)?.get(pid)?.length ?? 0));
        const step = 13;
        const half = 10 + maxStack * step;
        const margin = { top: 4, bottom: 24, left: 8, right: 8 };
        const height = margin.top + half * 2 + margin.bottom;
        const mid = margin.top + half;
        const x = d3.scaleBand().domain(yearsRange).range([margin.left, width - margin.right]).padding(0.1);
        const r = Math.max(3, Math.min(5, x.bandwidth() / 2 - 1));

        const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img")
          .attr("aria-label", `Match timeline: ${byId[a].short} ${wa} wins above the line, ${byId[b].short} ${wb} wins below`);
        svg.append("line").attr("class", "baseline").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", mid).attr("y2", mid);
        const tickEvery = width < 420 ? 5 : 2;
        svg.append("g").attr("class", "axis").selectAll("text")
          .data(yearsRange.filter((yr) => yr % tickEvery === 0)).join("text")
          .attr("x", (yr) => x(yr) + x.bandwidth() / 2).attr("y", height - 4).attr("text-anchor", "middle").text((yr) => yr);

        const dots = [];
        byYear.forEach((winners, yr) => winners.forEach((ms, pid) => ms.forEach((m, i) => {
          const dir = pid === a ? -1 : 1;
          dots.push({ m, cx: x(yr) + x.bandwidth() / 2, cy: mid + dir * (10 + i * step) });
        })));

        const g = svg.append("g").selectAll("g").data(dots).join("g").attr("class", "mark-group");
        g.append("circle").attr("class", "hit").attr("cx", (d) => d.cx).attr("cy", (d) => d.cy).attr("r", 10).attr("fill", "transparent");
        g.append("circle").attr("class", "mark").attr("cx", (d) => d.cx).attr("cy", (d) => d.cy).attr("r", r)
          .attr("fill", (d) => color(d.m.winner)).attr("stroke", "var(--surface)").attr("stroke-width", 2);
        tooltipOn(g, (t, d) => {
          const m = d.m;
          t.append(ttTitle(`${m.tourney} ${m.date.getUTCFullYear()}`));
          t.append(ttRow(m.winner, "W", `${byId[m.winner].name} def. ${byId[m.loser].short}`));
          t.append(ttNote(`${ROUNDS[m.round] ?? m.round} · ${m.surface} · ${LEVELS[m.level] ?? m.level}`));
          t.append(ttNote(m.score));
        });
      });
    });
  })();

  /* ---------- Footer ---------- */

  const fmtLong = d3.utcFormat("%B %Y");
  document.getElementById("data-through").textContent =
    `Match records through ${fmtLong(parseDate(data.meta.dataThrough))}; titles through ${fmtLong(d3.max(titles, (t) => t.date))}.`;
})();
