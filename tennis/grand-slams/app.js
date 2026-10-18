/* Grand Slams: every chart on the page, built with D3 v7. */
(async function () {
  "use strict";

  const { el, table, responsive, tooltipOn, tooltipOnNode, ttTitle, ttNote, barPath } = Viz;
  const data = await d3.json("data/grand-slams.json");

  const SLAMS = data.slams;
  const SLAM_META = {
    "Australian Open": { short: "AO", color: "var(--slam-ao)" },
    "Roland Garros": { short: "RG", color: "var(--slam-rg)" },
    Wimbledon: { short: "W", color: "var(--slam-w)" },
    "US Open": { short: "USO", color: "var(--slam-uso)" },
  };
  const TABS = [{ key: "All", label: "All Slams" }, ...SLAMS.map((s) => ({ key: s, label: s }))];
  const countries = data.countries;
  const editions = data.editions.map((e) => ({ ...e, date: d3.utcParse("%Y-%m-%d")(e.date) }));
  const inScope = (scope) => (scope === "All" ? editions : editions.filter((e) => e.slam === scope));
  const editionName = (e) => `${SLAM_META[e.slam].short} ${e.label}`;
  const surname = (name) => name.split(" ").slice(1).join(" ") || name;

  // Each player's nationality: the one they won (or reached) most finals under.
  const playerIoc = (() => {
    const tally = d3.rollup(
      editions.flatMap((e) => [[e.champion, e.championIoc], [e.runnerUp, e.runnerUpIoc]]),
      (v) => d3.greatest(d3.rollups(v, (x) => x.length, (x) => x[1]), (d) => d[1])[0],
      (d) => d[0]
    );
    return (name) => tally.get(name);
  })();

  Viz.legend("race-legend", SLAMS.map((s) => ({ label: s, color: SLAM_META[s].color })));
  Viz.legend("leaders-legend", SLAMS.map((s) => ({ label: s, color: SLAM_META[s].color })));

  /* ---------- Flags ---------- */

  const countryName = (ioc) => countries[ioc]?.name ?? ioc;

  function flag(ioc) {
    const iso = countries[ioc]?.flag;
    const fallback = () => {
      const s = el("span", "flag-code", ioc);
      s.title = countryName(ioc);
      return s;
    };
    if (!iso) return fallback();
    const img = el("img", "flag");
    img.src = `https://flagcdn.com/${iso}.svg`;
    img.alt = countryName(ioc);
    img.title = countryName(ioc);
    img.loading = "lazy";
    img.addEventListener("error", () => img.replaceWith(fallback()), { once: true });
    return img;
  }

  function svgFlag(g, ioc) {
    const iso = countries[ioc]?.flag;
    g.selectAll("*").remove();
    g.append("rect").attr("width", 20).attr("height", 15).attr("rx", 2).attr("fill", "var(--wash)").attr("stroke", "var(--border)");
    if (iso) {
      g.append("image").attr("href", `https://flagcdn.com/${iso}.svg`).attr("width", 20).attr("height", 15).attr("preserveAspectRatio", "xMidYMid slice");
    } else {
      g.append("text").attr("x", 10).attr("y", 7.5).attr("dy", "0.35em").attr("text-anchor", "middle").attr("class", "badge-text").attr("font-size", 7).text(ioc);
    }
  }

  function who(name, ioc) {
    const span = el("span", "who");
    span.append(flag(ioc), document.createTextNode(name));
    return span;
  }

  /** Tabs for "All Slams" + each major. */
  function slamTabs(containerId, onChange, initial = "All") {
    Viz.segmented(containerId, TABS, initial, onChange);
  }

  /* ---------- Stacked horizontal bars (leaders, match records) ---------- */

  /** rows: [{name, ioc, parts: [{color, value}], label, tip(t)}] */
  function hstack(containerId, rows, title) {
    const container = d3.select(`#${containerId}`);
    responsive(containerId, (width) => {
      container.selectAll("*").remove();
      const narrow = width < 560;
      const rowH = 32;
      const barH = 18;
      const margin = { top: 4, right: 64, bottom: 4, left: narrow ? 128 : 190 };
      const height = margin.top + rows.length * rowH + margin.bottom;
      const maxV = d3.max(rows, (r) => d3.sum(r.parts, (p) => p.value)) || 1;
      const x = d3.scaleLinear().domain([0, maxV]).range([0, width - margin.left - margin.right]);
      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", title);
      svg.append("line").attr("class", "baseline").attr("x1", margin.left).attr("x2", margin.left).attr("y1", 0).attr("y2", height);

      const g = svg.selectAll("g.row").data(rows).join("g").attr("class", "row mark-group")
        .attr("transform", (d, i) => `translate(${margin.left},${margin.top + i * rowH})`);
      g.append("rect").attr("x", -margin.left).attr("width", width).attr("height", rowH).attr("fill", "transparent");
      g.append("text").attr("class", "label-name").attr("x", -34).attr("y", rowH / 2).attr("dy", "0.35em").attr("text-anchor", "end")
        .text((d) => (narrow ? surname(d.name) : d.name));
      g.append("g").attr("transform", `translate(-28,${(rowH - 15) / 2})`).each(function (d) {
        svgFlag(d3.select(this), d.ioc);
      });
      g.each(function (d) {
        const sel = d3.select(this);
        const nonzero = d.parts.filter((p) => p.value > 0);
        let x0 = 0;
        nonzero.forEach((p, i) => {
          const w = x(p.value);
          const last = i === nonzero.length - 1;
          sel.append("path").attr("class", "mark").attr("fill", p.color)
            .attr("d", barPath(x0, (rowH - barH) / 2, Math.max(1, w - (last ? 0 : 2)), barH, last ? 4 : 0));
          x0 += w;
        });
        sel.append("text").attr("class", "label-value").attr("x", x0 + 8).attr("y", rowH / 2).attr("dy", "0.35em").text(d.label);
      });
      tooltipOn(g, (t, d) => d.tip(t));
    });
  }

  /* ---------- Stat tiles ---------- */

  (function stats() {
    const champions = new Set(editions.map((e) => e.champion));
    const nations = new Set(editions.map((e) => e.championIoc));
    const titles = d3.rollup(editions, (v) => v.length, (e) => e.champion);
    const [leader, n] = d3.greatest(titles, (d) => d[1]);
    const tiles = [
      { label: "Majors played", value: String(editions.length), detail: `Since Roland Garros 1968` },
      { label: "Different champions", value: String(champions.size), detail: `${d3.sum(titles.values(), (v) => v === 1)} won exactly one` },
      { label: "Champion nations", value: String(nations.size), detail: `${countryName(d3.greatest(d3.rollup(editions, (v) => v.length, (e) => e.championIoc), (d) => d[1])[0])} leads` },
      { label: "Most titles", value: String(n), detail: leader, ioc: playerIoc(leader) },
    ];
    const root = document.getElementById("stats");
    tiles.forEach((t) => {
      const box = el("div", "stat");
      const detail = el("span", "detail");
      if (t.ioc) detail.append(flag(t.ioc), document.createTextNode(" "));
      detail.append(document.createTextNode(t.detail));
      box.append(el("span", "label", t.label), el("div", "value", t.value), detail);
      root.append(box);
    });
  })();

  /* ---------- Bar chart race ---------- */

  (function race() {
    const TOP = 10;
    const tally = new Map(); // player -> {slam: n}
    const reached = new Map();
    const frames = [{ edition: null, ranked: [] }];
    editions.forEach((e, i) => {
      const c = tally.get(e.champion) ?? Object.fromEntries(SLAMS.map((s) => [s, 0]));
      c[e.slam]++;
      tally.set(e.champion, c);
      reached.set(e.champion, i);
      const ranked = [...tally.entries()]
        .map(([name, counts]) => ({ name, counts: { ...counts }, total: d3.sum(SLAMS, (s) => counts[s]), since: reached.get(name) }))
        .sort((a, b) => b.total - a.total || a.since - b.since)
        .slice(0, TOP);
      frames.push({ edition: e, ranked });
    });

    const state = { idx: Viz.reduceMotion ? frames.length - 1 : 0, playing: false, timer: null };
    const dateEl = document.getElementById("race-date");
    const tickerEl = document.getElementById("race-ticker");
    const playBtn = document.getElementById("race-play");
    const scrub = document.getElementById("race-scrub");
    const speedSel = document.getElementById("race-speed");
    scrub.max = frames.length - 1;

    const rowH = 36;
    const barH = 22;
    const margin = { top: 24, right: 48, bottom: 8, left: 190 };
    const height = margin.top + rowH * TOP + margin.bottom;
    const svg = d3.select("#race-chart").append("svg").attr("role", "img");
    const grid = svg.append("g");
    const bars = svg.append("g");
    let width = 0;
    let narrow = false;
    const x = d3.scaleLinear();
    const frameDuration = () => 320 / +speedSel.value;
    const yPos = (i) => margin.top + i * rowH + (rowH - barH) / 2;

    function drawSegments(row, counts) {
      const nonzero = SLAMS.filter((s) => counts[s] > 0.001);
      let x0 = 0;
      SLAMS.forEach((s) => {
        const path = row.select(`path.seg-${SLAM_META[s].short}`);
        const w = x(counts[s] || 0);
        const i = nonzero.indexOf(s);
        if (i < 0) {
          path.attr("d", null);
          return;
        }
        const last = i === nonzero.length - 1;
        path.attr("d", barPath(x0, 0, Math.max(0.5, w - (last ? 0 : 2)), barH, last ? 4 : 0));
        x0 += w;
      });
      return x0;
    }

    function update(duration) {
      const frame = frames[state.idx];
      const maxN = d3.max(frame.ranked, (d) => d.total) ?? 0;
      x.domain([0, Math.max(5, maxN * 1.05)]).range([0, width - margin.left - margin.right]);
      const t = svg.transition().duration(duration).ease(d3.easeLinear);

      svg.attr("aria-label", `Most Grand Slam titles after ${frame.edition ? editionName(frame.edition) : "1968"}: ` +
        frame.ranked.map((d) => `${d.name} ${d.total}`).join(", "));

      const ticks = x.ticks(narrow ? 4 : 6).filter(Number.isInteger);
      grid.selectAll("g.tick").data(ticks, (d) => d).join(
        (enter) => {
          const g = enter.append("g").attr("class", "tick").attr("opacity", 0).attr("transform", (d) => `translate(${margin.left + x(d)},0)`);
          g.append("line").attr("class", (d) => (d === 0 ? "baseline" : "gridline")).attr("y1", margin.top - 6).attr("y2", height - margin.bottom);
          g.append("text").attr("class", "tick-label").attr("y", margin.top - 12).attr("text-anchor", "middle").text((d) => d);
          return g;
        },
        (u) => u,
        (exit) => exit.transition(t).attr("opacity", 0).remove()
      ).transition(t).attr("opacity", 1).attr("transform", (d) => `translate(${margin.left + x(d)},0)`);

      const rows = bars.selectAll("g.row").data(frame.ranked, (d) => d.name).join(
        (enter) => {
          const g = enter.append("g").attr("class", "row").attr("opacity", 0).attr("transform", `translate(${margin.left},${yPos(TOP)})`);
          SLAMS.forEach((s) => g.append("path").attr("class", `mark seg-${SLAM_META[s].short}`).attr("fill", SLAM_META[s].color));
          g.append("text").attr("class", "label-name").attr("x", -34).attr("y", barH / 2).attr("dy", "0.35em").attr("text-anchor", "end");
          g.append("g").attr("class", "flag-slot").attr("transform", `translate(-28,${(barH - 15) / 2})`)
            .each(function (d) { svgFlag(d3.select(this), playerIoc(d.name)); });
          g.append("text").attr("class", "label-value").attr("y", barH / 2).attr("dy", "0.35em");
          g.property("_c", Object.fromEntries(SLAMS.map((s) => [s, 0])));
          return g;
        },
        (u) => u,
        (exit) => exit.transition(t).attr("opacity", 0).attr("transform", `translate(${margin.left},${yPos(TOP)})`).remove()
      );

      rows.select("text.label-name").text((d) => (narrow ? surname(d.name) : d.name));
      rows.transition(t).attr("opacity", 1).attr("transform", (d, i) => `translate(${margin.left},${yPos(i)})`)
        .tween("bars", function (d) {
          const row = d3.select(this);
          const interp = d3.interpolateObject(this._c, d.counts);
          const label = row.select("text.label-value");
          return (k) => {
            this._c = interp(k);
            const end = drawSegments(row, this._c);
            label.attr("x", end + 8).text(Math.round(d3.sum(SLAMS, (s) => this._c[s])));
          };
        });

      const e = frame.edition;
      dateEl.textContent = e ? e.label.replace(/ \(.*\)/, "") : "1968";
      scrub.value = state.idx;
      tickerEl.replaceChildren();
      if (!e) {
        tickerEl.textContent = "Press play to start at Roland Garros 1968, the first Open Era major.";
      } else {
        tickerEl.append(flag(e.championIoc), el("strong", null, `${e.slam} ${e.label} · ${e.champion}`),
          document.createTextNode(` def. ${e.runnerUp}, ${e.score}`));
      }
    }

    function step() {
      if (state.idx >= frames.length - 1) return pause();
      state.idx++;
      update(frameDuration());
      state.timer = setTimeout(step, frameDuration());
    }

    function play() {
      if (state.idx >= frames.length - 1) {
        state.idx = 0;
        update(0);
      }
      state.playing = true;
      playBtn.textContent = "❚❚";
      playBtn.setAttribute("aria-label", "Pause");
      state.timer = setTimeout(step, 250);
    }

    function pause() {
      state.playing = false;
      clearTimeout(state.timer);
      const done = state.idx >= frames.length - 1;
      playBtn.textContent = done ? "↺" : "▶";
      playBtn.setAttribute("aria-label", done ? "Replay" : "Play");
    }

    playBtn.addEventListener("click", () => (state.playing ? pause() : play()));
    scrub.addEventListener("input", () => {
      pause();
      state.idx = +scrub.value;
      update(0);
    });

    responsive("race-chart", (w) => {
      width = w;
      narrow = w < 560;
      margin.left = narrow ? 120 : 190;
      svg.attr("viewBox", `0 0 ${w} ${height}`);
      update(0);
    });
    pause();

    if (!Viz.reduceMotion) {
      const io = new IntersectionObserver((entries) => {
        if (entries.some((en) => en.isIntersecting)) {
          io.disconnect();
          if (state.idx === 0) play();
        }
      }, { threshold: 0.6 });
      io.observe(document.getElementById("race-chart"));
    }
  })();

  /* ---------- Most titles ---------- */

  /** Top entries by count, extended to include everyone tied with the last one. */
  function topWithTies(entries, n, value) {
    const sorted = entries.slice().sort((a, b) => value(b) - value(a));
    if (sorted.length <= n) return sorted;
    const cutoff = value(sorted[n - 1]);
    return sorted.filter((e, i) => i < n || value(e) === cutoff).slice(0, n + 4);
  }

  (function leaders() {
    function render(scope) {
      const list = inScope(scope);
      const groups = d3.groups(list, (e) => e.champion).map(([name, eds]) => ({ name, eds }));
      const top = topWithTies(groups, 10, (g) => g.eds.length)
        .sort((a, b) => b.eds.length - a.eds.length || a.eds[0].date - b.eds[0].date);
      const rows = top.map((g) => ({
        name: g.name,
        ioc: playerIoc(g.name),
        parts: (scope === "All" ? SLAMS : [scope]).map((s) => ({ color: SLAM_META[s].color, value: g.eds.filter((e) => e.slam === s).length })),
        label: String(g.eds.length),
        tip: (t) => {
          t.append(ttTitle(g.name));
          (scope === "All" ? SLAMS : [scope]).forEach((s) => {
            const won = g.eds.filter((e) => e.slam === s);
            if (won.length) t.append(Viz.ttRow(SLAM_META[s].color, won.length, `${s}: ${won.map((e) => e.label).join(", ")}`));
          });
        },
      }));
      document.getElementById("leaders-legend").hidden = scope !== "All";
      hstack("leaders-chart", rows, `Most ${scope === "All" ? "Grand Slam" : scope} titles in the Open Era`);
      table("leaders-table", ["Player", "Nation", "Titles", ...(scope === "All" ? SLAMS.map((s) => SLAM_META[s].short) : ["Years"])],
        groups.sort((a, b) => b.eds.length - a.eds.length).map((g) => [
          g.name, countryName(playerIoc(g.name)), String(g.eds.length),
          ...(scope === "All" ? SLAMS.map((s) => String(g.eds.filter((e) => e.slam === s).length)) : [g.eds.map((e) => e.label).join(", ")]),
        ]));
    }
    slamTabs("leaders-tabs", render);
    render("All");
  })();

  /* ---------- Runners-up ---------- */

  (function runnersUp() {
    const root = document.getElementById("runners-table");
    function render(scope) {
      const list = inScope(scope);
      const lost = d3.groups(list, (e) => e.runnerUp).map(([name, eds]) => ({
        name, eds, won: list.filter((e) => e.champion === name).length,
      }));
      const top = topWithTies(lost, 12, (g) => g.eds.length)
        .sort((a, b) => b.eds.length - a.eds.length || b.won - a.won);
      const t = el("table");
      const head = el("tr");
      [["Player"], ["Finals lost", "num", "Lost"], ["Finals played", "num", "Played"], ["Titles", "num"], ["Lost finals", "years"]].forEach(([h, cls, short]) => {
        const th = el("th", cls);
        th.append(el("span", short ? "long" : null, h));
        if (short) th.append(el("span", "short", short));
        head.append(th);
      });
      t.append(head);
      top.forEach((g) => {
        const tr = el("tr");
        const years = g.eds.map((e) => `${scope === "All" ? editionName(e) : e.label} (${surname(e.champion)})`).join(", ");
        const name = el("td");
        name.append(who(g.name, playerIoc(g.name)), el("div", "sub", years));
        tr.append(
          name,
          el("td", "num strong", String(g.eds.length)),
          el("td", "num", String(g.eds.length + g.won)),
          el("td", "num", String(g.won)),
          el("td", "years", years)
        );
        t.append(tr);
      });
      root.replaceChildren(t);
    }
    slamTabs("runners-tabs", render);
    render("All");
  })();

  /* ---------- Nations ---------- */

  (function nations() {
    const counts = document.getElementById("nation-counts");
    TABS.forEach(({ key, label }) => {
      const list = inScope(key);
      const box = el("div", "nation-count");
      box.style.setProperty("--c", key === "All" ? "var(--ink-muted)" : SLAM_META[key].color);
      box.append(el("div", "label", label), el("div", "value", String(new Set(list.map((e) => e.championIoc)).size)),
        el("div", "detail", `nations · ${new Set(list.map((e) => e.champion)).size} champions`));
      counts.append(box);
    });

    const root = document.getElementById("nations-list");
    function render(scope) {
      const list = inScope(scope);
      const byNation = d3.groups(list, (e) => e.championIoc)
        .map(([ioc, eds]) => ({ ioc, eds, players: d3.groups(eds, (e) => e.champion).sort((a, b) => b[1].length - a[1].length) }))
        .sort((a, b) => b.eds.length - a.eds.length || b.players.length - a.players.length);
      const maxN = byNation[0]?.eds.length ?? 1;

      root.replaceChildren();
      const head = el("div", "nation-head");
      head.append(el("span"), el("span", null, "Nation"), el("span"), el("span", "num", "Titles"), el("span", "num", "Champions"));
      root.append(head);
      byNation.forEach((n) => {
        const row = el("div", "nation-row");
        const stack = el("div", "stack");
        stack.style.width = `${(n.eds.length / maxN) * 100}%`;
        (scope === "All" ? SLAMS : [scope]).forEach((s) => {
          const k = n.eds.filter((e) => e.slam === s).length;
          if (!k) return;
          const seg = el("span");
          seg.style.setProperty("--c", SLAM_META[s].color);
          seg.style.flex = String(k);
          stack.append(seg);
        });
        const barWrap = el("div");
        barWrap.append(stack);
        row.append(flag(n.ioc), el("span", "name", countryName(n.ioc)), barWrap,
          el("span", "num strong", String(n.eds.length)), el("span", "num", String(n.players.length)));
        row.setAttribute("aria-label", `${countryName(n.ioc)}: ${n.eds.length} titles by ${n.players.length} champions`);
        tooltipOnNode(row, (t) => {
          t.append(ttTitle(`${countryName(n.ioc)} · ${n.eds.length} ${n.eds.length === 1 ? "title" : "titles"}`));
          n.players.forEach(([name, eds]) => t.append(Viz.ttRow("var(--ink-muted)", eds.length, name)));
        });
        root.append(row);
      });
    }
    slamTabs("nations-tabs", render);
    render("All");
  })();

  /* ---------- Match records ---------- */

  (function matchRecords() {
    let scope = "All";
    let sort = "won";
    Viz.segmented("matches-sort", [{ key: "won", label: "Most wins" }, { key: "played", label: "Most matches" }], sort, (k) => {
      sort = k;
      render();
    });
    function render() {
      const winColor = scope === "All" ? "var(--ink-2)" : SLAM_META[scope].color;
      Viz.legend("matches-legend", [{ label: "Won", color: winColor }, { label: "Lost", color: "var(--loss)" }]);
      const value = sort === "won" ? (r) => r.won : (r) => r.won + r.lost;
      const list = data.matchRecords[scope].slice().sort((a, b) => value(b) - value(a) || b.won - a.won).slice(0, 10);
      hstack("matches-chart", list.map((r) => ({
        name: r.player,
        ioc: r.ioc,
        parts: [{ color: winColor, value: r.won }, { color: "var(--loss)", value: r.lost }],
        label: `${r.won}–${r.lost}`,
        tip: (t) => {
          t.append(ttTitle(`${r.player} · ${scope === "All" ? "all majors" : scope}`));
          t.append(Viz.ttRow(winColor, r.won, "won"), Viz.ttRow("var(--loss)", r.lost, "lost"));
          t.append(ttNote(`${r.won + r.lost} matches · ${((r.won / (r.won + r.lost)) * 100).toFixed(1)}% won`));
        },
      })), `${sort === "won" ? "Most matches won" : "Most matches played"} at ${scope === "All" ? "Grand Slams" : scope}`);
      table("matches-table", ["Player", "Nation", "Won", "Lost", "Played", "Win %"], list.map((r) => [
        r.player, countryName(r.ioc), String(r.won), String(r.lost), String(r.won + r.lost), `${((r.won / (r.won + r.lost)) * 100).toFixed(1)}%`,
      ]));
    }
    slamTabs("matches-tabs", (k) => {
      scope = k;
      render();
    });
    render();
  })();

  /* ---------- Most repeated finals ---------- */

  (function repeatedFinals() {
    const root = document.getElementById("finals-list");
    function render(scope) {
      const list = inScope(scope);
      const pairs = d3.groups(list, (e) => [e.champion, e.runnerUp].sort().join(" | "))
        .filter(([, eds]) => eds.length >= 2)
        .sort((a, b) => b[1].length - a[1].length || d3.max(b[1], (e) => e.date) - d3.max(a[1], (e) => e.date))
        .slice(0, 10);
      root.replaceChildren();
      if (!pairs.length) {
        root.append(el("p", "footnote", "No final has been repeated."));
        return;
      }
      pairs.forEach(([key, eds]) => {
        const [a, b] = key.split(" | ");
        const wa = eds.filter((e) => e.champion === a).length;
        const wb = eds.length - wa;
        const [first, second] = wa >= wb ? [a, b] : [b, a];
        const row = el("div", "pair-row");
        const count = el("div", "count", String(eds.length));
        count.append(el("small", null, "finals"));
        const players = el("div", "players");
        const pa = el("span");
        pa.append(flag(playerIoc(first)), document.createTextNode(first));
        const pb = el("span");
        pb.append(flag(playerIoc(second)), document.createTextNode(second));
        players.append(pa, el("span", "vs", "vs"), pb);
        const h2h = el("div", "h2h", wa === wb ? `Tied ${wa}–${wb}` : `${surname(first)} ${Math.max(wa, wb)}–${Math.min(wa, wb)}`);
        const meta = el("div", "meta", eds.map((e) => `${scope === "All" ? editionName(e) : e.label} ${surname(e.champion)}`).join(" · "));
        row.append(count, players, h2h, meta);
        root.append(row);
      });
    }
    slamTabs("finals-tabs", render);
    render("All");
  })();

  /* ---------- Footer ---------- */

  const wiki = data.meta.fromWikipedia;
  document.getElementById("wiki-note").textContent = wiki.length
    ? `${wiki.join(" and ")} rebuilt from the Wikipedia draw pages (CC BY-SA 4.0), which the ATP dataset doesn't cover yet. Covers every major through ${data.meta.through}.`
    : `Covers every major through ${data.meta.through}.`;
})();
