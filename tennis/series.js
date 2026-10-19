/* Tennis tournament series (Grand Slams, Masters 1000, WTA 1000): every chart on the page, built with D3 v7.
   The page sets data-src (the dataset) and data-series (labels). Bars are split by tournament
   (data.colorBy = "event") or by surface ("surface"). */
(async function () {
  "use strict";

  const { el, table, responsive, tooltipOn, tooltipOnNode, ttTitle, ttNote, barPath } = Viz;
  const data = await d3.json(document.body.dataset.src);
  const CFG = JSON.parse(document.body.dataset.series || "{}");
  const TITLE = CFG.title ?? data.meta.name; // "Grand Slam", "Masters 1000"...

  const EVENTS = data.events.map((e) => e.key);
  const SHORT = { "Australian Open": "AO", "Roland Garros": "RG", Wimbledon: "W", "US Open": "USO" };
  const short = (event) => SHORT[event] ?? event;
  const SURFACE_COLOR = { Hard: "var(--series-1)", Clay: "var(--series-2)", Grass: "var(--series-3)", Carpet: "var(--series-4)" };
  const BY_EVENT = data.colorBy === "event";
  const KEYS = data.colors; // the series each bar is split into
  const COLOR = Object.fromEntries(KEYS.map((k, i) => [k, BY_EVENT ? `var(--series-${i + 1})` : SURFACE_COLOR[k]]));
  const keyOf = (e) => (BY_EVENT ? e.event : e.surface);
  const keyClass = (k) => k.replace(/\W+/g, "");
  const TABS = data.tabs;
  const tabBy = Object.fromEntries(TABS.map((t) => [t.key, t]));
  const countries = data.countries;
  const editions = data.editions.map((e) => ({ ...e, date: d3.utcParse("%Y-%m-%d")(e.date) }));
  const inScope = (scope) => {
    if (scope === "All") return editions;
    const set = new Set(tabBy[scope].events ?? [scope]);
    return editions.filter((e) => set.has(e.event));
  };
  /** Colors shown for a scope: one tournament's own color, or every series. */
  const keysFor = (scope) => (BY_EVENT && scope !== "All" ? KEYS.filter((k) => (tabBy[scope].events ?? [scope]).includes(k)) : KEYS);
  const scopeColor = (scope) => (BY_EVENT && COLOR[scope]) || "var(--ink-2)";
  const editionName = (e) => `${short(e.event)} ${e.label}`;
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

  Viz.legend("race-legend", KEYS.map((k) => ({ label: k, color: COLOR[k] })));
  Viz.legend("leaders-legend", KEYS.map((k) => ({ label: k, color: COLOR[k] })));

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

  /** Tabs for every scope ("All" + each tournament); a dropdown when there are too many for pills. */
  function slamTabs(containerId, onChange, initial = "All") {
    if (TABS.length <= 6) {
      Viz.segmented(containerId, TABS, initial, onChange);
      return;
    }
    const root = document.getElementById(containerId);
    root.className = "scope-select";
    const select = el("select");
    select.setAttribute("aria-label", "Tournament");
    TABS.forEach((t) => {
      const o = el("option", null, t.label);
      o.value = t.key;
      o.selected = t.key === initial;
      select.append(o);
    });
    select.addEventListener("change", () => onChange(select.value));
    root.append(select);
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
      { label: CFG.played ?? "Finals played", value: String(editions.length), detail: `Since ${editions[0].event} ${editions[0].label}` },
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
    const tally = new Map(); // player -> {series key: n}
    const reached = new Map();
    const frames = [{ edition: null, ranked: [] }];
    editions.forEach((e, i) => {
      const c = tally.get(e.champion) ?? Object.fromEntries(KEYS.map((k) => [k, 0]));
      c[keyOf(e)]++;
      tally.set(e.champion, c);
      reached.set(e.champion, i);
      const ranked = [...tally.entries()]
        .map(([name, counts]) => ({ name, counts: { ...counts }, total: d3.sum(KEYS, (k) => counts[k]), since: reached.get(name) }))
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
      const nonzero = KEYS.filter((k) => counts[k] > 0.001);
      let x0 = 0;
      KEYS.forEach((k) => {
        const path = row.select(`path.seg-${keyClass(k)}`);
        const w = x(counts[k] || 0);
        const i = nonzero.indexOf(k);
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

      svg.attr("aria-label", `Most ${TITLE} titles after ${frame.edition ? editionName(frame.edition) : editions[0].year}: ` +
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
          KEYS.forEach((k) => g.append("path").attr("class", `mark seg-${keyClass(k)}`).attr("fill", COLOR[k]));
          g.append("text").attr("class", "label-name").attr("x", -34).attr("y", barH / 2).attr("dy", "0.35em").attr("text-anchor", "end");
          g.append("g").attr("class", "flag-slot").attr("transform", `translate(-28,${(barH - 15) / 2})`)
            .each(function (d) { svgFlag(d3.select(this), playerIoc(d.name)); });
          g.append("text").attr("class", "label-value").attr("y", barH / 2).attr("dy", "0.35em");
          g.property("_c", Object.fromEntries(KEYS.map((k) => [k, 0])));
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
            label.attr("x", end + 8).text(Math.round(d3.sum(KEYS, (k) => this._c[k])));
          };
        });

      const e = frame.edition;
      dateEl.textContent = e ? e.label.replace(/ \(.*\)/, "") : String(editions[0].year);
      scrub.value = state.idx;
      tickerEl.replaceChildren();
      if (!e) {
        const first = editions[0];
        tickerEl.textContent = `Press play to start at ${first.event} ${first.label}${CFG.firstNote ? `, ${CFG.firstNote}` : ""}.`;
      } else {
        tickerEl.append(flag(e.championIoc), el("strong", null, `${e.event} ${e.label} · ${e.champion}`),
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
      const keys = keysFor(scope);
      const rows = top.map((g) => ({
        name: g.name,
        ioc: playerIoc(g.name),
        parts: keys.map((k) => ({ color: COLOR[k], value: g.eds.filter((e) => keyOf(e) === k).length })),
        label: String(g.eds.length),
        tip: (t) => {
          t.append(ttTitle(g.name));
          d3.groups(g.eds, (e) => e.event).sort((a, b) => b[1].length - a[1].length).forEach(([event, won]) => {
            t.append(Viz.ttRow(COLOR[event] ?? "var(--ink-muted)", won.length, `${event}: ${won.map((e) => e.label).join(", ")}`));
          });
        },
      }));
      document.getElementById("leaders-legend").hidden = BY_EVENT && scope !== "All";
      hstack("leaders-chart", rows, `Most ${scope === "All" ? TITLE : tabBy[scope].label} titles`);
      const split = BY_EVENT && scope !== "All" ? [] : KEYS;
      table("leaders-table", ["Player", "Nation", "Titles", ...split.map(short), "Won"],
        groups.sort((a, b) => b.eds.length - a.eds.length).map((g) => [
          g.name, countryName(playerIoc(g.name)), String(g.eds.length),
          ...split.map((k) => String(g.eds.filter((e) => keyOf(e) === k).length)),
          g.eds.map((e) => (scope === "All" || tabBy[scope].events ? editionName(e) : e.label)).join(", "),
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
        const years = g.eds.map((e) => `${scope === "All" || tabBy[scope].events ? editionName(e) : e.label} (${surname(e.champion)})`).join(", ");
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
      box.style.setProperty("--c", BY_EVENT && COLOR[key] ? COLOR[key] : "var(--ink-muted)");
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
        keysFor(scope).forEach((key) => {
          const k = n.eds.filter((e) => keyOf(e) === key).length;
          if (!k) return;
          const seg = el("span");
          seg.style.setProperty("--c", COLOR[key]);
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
      const winColor = scopeColor(scope);
      Viz.legend("matches-legend", [{ label: "Won", color: winColor }, { label: "Lost", color: "var(--loss)" }]);
      const value = sort === "won" ? (r) => r.won : (r) => r.won + r.lost;
      const list = data.matchRecords[scope].slice().sort((a, b) => value(b) - value(a) || b.won - a.won).slice(0, 10);
      hstack("matches-chart", list.map((r) => ({
        name: r.player,
        ioc: r.ioc,
        parts: [{ color: winColor, value: r.won }, { color: "var(--loss)", value: r.lost }],
        label: `${r.won}–${r.lost}`,
        tip: (t) => {
          t.append(ttTitle(`${r.player} · ${tabBy[scope].label}`));
          t.append(Viz.ttRow(winColor, r.won, "won"), Viz.ttRow("var(--loss)", r.lost, "lost"));
          t.append(ttNote(`${r.won + r.lost} matches · ${((r.won / (r.won + r.lost)) * 100).toFixed(1)}% won`));
        },
      })), `${sort === "won" ? "Most matches won" : "Most matches played"}: ${tabBy[scope].label}`);
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
        const meta = el("div", "meta", eds.map((e) => `${scope === "All" || tabBy[scope].events ? editionName(e) : e.label} ${surname(e.champion)}`).join(" · "));
        row.append(count, players, h2h, meta);
        root.append(row);
      });
    }
    slamTabs("finals-tabs", render);
    render("All");
  })();

  /* ---------- Footer ---------- */

  const wiki = data.meta.fromWikipedia;
  const tour = data.meta.tour.toUpperCase();
  const list = (xs) => (xs.length > 1 ? `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}` : xs[0]);
  document.getElementById("wiki-note").textContent = (wiki.length
    ? `${list(wiki)} rebuilt from the Wikipedia draw pages (CC BY-SA 4.0), which the ${tour} dataset doesn't cover yet. `
    : "") + `Covers every final through ${data.meta.through}.`;
})();
