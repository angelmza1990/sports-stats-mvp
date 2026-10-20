/* Shared building blocks for the football pages: crests, flags, tables, bar race. */
window.Football = function (data) {
  "use strict";

  const { el, barPath } = Viz;
  const clubs = data.clubs;
  const countries = data.countries;
  // Nations mode (national teams): flags stand in for crests.
  const nations = Boolean(data.nationMode);

  const clubName = (id) => clubs[id]?.name ?? id;
  const countryName = (code) => countries[code]?.name ?? code;
  const fit = (text, narrow, max = 15) => (narrow && text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text);
  const NOTE = { penalties: "pens", "extra time": "a.e.t.", playoff: "playoff", replay: "replay" };
  const scoreText = (f) => (f.legs || []).map((l) => l.score + (l.note ? ` ${NOTE[l.note] ?? l.note}` : "")).join(", ");

  /* ---------- Crests and flags ---------- */

  const CREST = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/soccer";
  const crestUrl = (id, dark = Viz.isDark()) => `${CREST}/${dark ? "500-dark" : "500"}/${id}.png&h=80&w=80`;
  const initials = (name) => name.replace(/\(.*?\)/g, "").replace(/[^A-Za-zÀ-ÿ ]/g, "").split(" ").filter(Boolean).slice(0, 3).map((w) => w[0]).join("").toUpperCase();

  function crest(id, cls = "crest") {
    if (nations) return flag(id);
    const club = clubs[id];
    const badge = () => {
      const b = el("span", `crest-badge ${cls}`, initials(club?.name ?? id));
      b.setAttribute("aria-hidden", "true");
      return b;
    };
    if (!club?.crest) return badge();
    const img = el("img", cls);
    img.alt = "";
    img.loading = "lazy";
    img.dataset.crest = club.crest;
    img.src = crestUrl(club.crest);
    img.addEventListener("error", () => {
      // Fall back to the light crest, then to a lettered badge.
      if (img.src !== crestUrl(club.crest, false)) img.src = crestUrl(club.crest, false);
      else img.replaceWith(badge());
    });
    return img;
  }

  function svgCrest(g, id, size) {
    const club = clubs[id];
    g.selectAll("*").remove();
    if (nations) {
      const fg = g.append("g").attr("transform", `translate(${-size / 2},${-size * 0.375})`);
      fg.append("rect").attr("width", size).attr("height", size * 0.75).attr("rx", 2).attr("fill", "var(--wash)").attr("stroke", "var(--border)");
      const iso = countries[id]?.flag;
      if (iso) fg.append("image").attr("href", Viz.flagUrl(iso)).attr("width", size).attr("height", size * 0.75).attr("preserveAspectRatio", "xMidYMid slice");
      else fg.append("text").attr("class", "badge-text").attr("x", size / 2).attr("y", size * 0.375).attr("dy", "0.35em").attr("text-anchor", "middle").text(id);
      return;
    }
    const badge = () => {
      g.selectAll("*").remove();
      g.append("circle").attr("r", size / 2 - 1).attr("class", "badge-circle");
      g.append("text").attr("class", "badge-text").attr("text-anchor", "middle").attr("dy", "0.35em").text(initials(club?.name ?? id));
    };
    if (!club?.crest) return badge();
    g.append("image").attr("data-crest", club.crest).attr("href", crestUrl(club.crest))
      .attr("x", -size / 2).attr("y", -size / 2).attr("width", size).attr("height", size)
      .on("error", function () {
        const light = crestUrl(club.crest, false);
        if (this.getAttribute("href") !== light) this.setAttribute("href", light);
        else badge();
      });
  }

  Viz.onThemeChange(() => {
    document.querySelectorAll("img[data-crest]").forEach((img) => (img.src = crestUrl(img.dataset.crest)));
    document.querySelectorAll("image[data-crest]").forEach((img) => img.setAttribute("href", crestUrl(img.dataset.crest)));
  });

  function flag(code) {
    const iso = countries[code]?.flag;
    const fallback = () => {
      const s = el("span", "flag-code", code ?? "");
      s.title = countryName(code);
      return s;
    };
    if (!iso) return fallback();
    const img = el("img", "flag");
    img.src = Viz.flagUrl(iso);
    img.alt = countryName(code);
    img.title = countryName(code);
    img.loading = "lazy";
    img.addEventListener("error", () => img.replaceWith(fallback()), { once: true });
    return img;
  }

  function svgFlag(g, code) {
    const iso = countries[code]?.flag;
    g.append("rect").attr("width", 20).attr("height", 15).attr("rx", 2).attr("fill", "var(--wash)").attr("stroke", "var(--border)");
    if (iso) g.append("image").attr("href", Viz.flagUrl(iso)).attr("width", 20).attr("height", 15).attr("preserveAspectRatio", "xMidYMid slice");
  }

  function clubLabel(id, withFlag = false) {
    const span = el("span", "club");
    if (withFlag && !nations) span.append(flag(clubs[id]?.country));
    span.append(crest(id), document.createTextNode(clubName(id)));
    return span;
  }

  /* ---------- Tables ---------- */

  /** columns: [{label, short?, cls?, render(row) -> Node|string}] */
  function richTable(root, columns, rows) {
    const t = el("table");
    const head = el("tr");
    columns.forEach((c) => {
      const th = el("th", c.cls);
      th.append(el("span", c.short ? "long" : null, c.label));
      if (c.short) th.append(el("span", "short", c.short));
      head.append(th);
    });
    t.append(head);
    rows.forEach((r) => {
      const tr = el("tr", r._rowClass);
      columns.forEach((c) => {
        const td = el("td", c.cls);
        const v = c.render(r);
        td.append(typeof v === "string" ? document.createTextNode(v) : v);
        tr.append(td);
      });
      t.append(tr);
    });
    root.replaceChildren(t);
  }

  function withSub(node, sub) {
    const wrap = el("div");
    wrap.append(node, el("div", "sub", sub));
    return wrap;
  }

  function statTiles(rootId, tiles) {
    const root = document.getElementById(rootId);
    tiles.forEach((t) => {
      const box = el("div", "stat");
      const value = el("div", "value");
      if (t.club) value.append(crest(t.club, "crest crest-lg"));
      value.append(document.createTextNode(t.value));
      box.append(el("span", "label", t.label), value, el("span", "detail", t.detail));
      root.append(box);
    });
  }

  /* ---------- Repeated finals ---------- */

  /** finals: [{champion, runnerUp, year, ...}]; label(f) -> short text for each meeting. */
  function repeatedFinals(root, finals, label, limit = 12) {
    root.replaceChildren();
    const pairs = d3.groups(finals, (f) => [f.champion, f.runnerUp].sort().join("|"))
      .filter(([, list]) => list.length >= 2)
      .sort((a, b) => b[1].length - a[1].length || b[1][b[1].length - 1].year - a[1][a[1].length - 1].year)
      .slice(0, limit);
    if (!pairs.length) root.append(el("p", "footnote", "No final has been repeated."));
    pairs.forEach(([key, list]) => {
      const [a, b] = key.split("|");
      const wa = list.filter((f) => f.champion === a).length;
      const wb = list.length - wa;
      const [first, second] = wa >= wb ? [a, b] : [b, a];
      const row = el("div", "pair-row");
      const count = el("div", "count", String(list.length));
      count.append(el("small", null, "finals"));
      const players = el("div", "players");
      players.append(clubLabel(first), el("span", "vs", "vs"), clubLabel(second));
      const h2h = el("div", "h2h", wa === wb ? `Tied ${wa}–${wb}` : `${clubName(first)} ${Math.max(wa, wb)}–${Math.min(wa, wb)}`);
      row.append(count, players, h2h, el("div", "meta", list.map(label).join(" · ")));
      root.append(row);
    });
  }

  /* ---------- Titles / runners-up rows by group (country, confederation) ---------- */

  /** groups: [{key, label, icon?: Node, won: [], lost: [], winners: [[id, list]]}] */
  function groupRows(root, groups, firstLabel) {
    const maxN = d3.max(groups, (r) => Math.max(r.won.length, r.lost.length)) || 1;
    root.replaceChildren();
    const head = el("div", "country-head");
    head.append(el("span"), el("span", null, firstLabel), el("span", null, "Titles"), el("span", "num", "Titles"),
      el("span", null, "Runners-up"), el("span", "num", "R-up"), el("span", "num", "Clubs"));
    root.append(head);
    groups.forEach((r) => {
      const row = el("div", "country-row");
      const bar = (n, cls) => {
        const wrap = el("div", "bar-wrap");
        const b = el("div", `bar ${cls}`);
        b.style.width = `${(n / maxN) * 100}%`;
        wrap.append(b);
        return wrap;
      };
      row.append(r.icon ?? el("span"), el("span", "name", r.label), bar(r.won.length, "won"), el("span", "num strong", String(r.won.length)),
        bar(r.lost.length, "lost"), el("span", "num", String(r.lost.length)), el("span", "num", String(r.winners.length)));
      Viz.tooltipOnNode(row, (t) => {
        t.append(Viz.ttTitle(`${r.label}: ${r.won.length} titles, ${r.lost.length} runners-up`));
        r.winners.forEach(([id, list]) => t.append(Viz.ttRow("var(--ink-2)", list.length, clubName(id))));
        if (!r.winners.length) t.append(Viz.ttNote("No titles yet"));
      });
      root.append(row);
    });
  }

  /* ---------- Bar chart race ---------- */

  /**
   * frames: [{label, event, ranked: [{id, n}]}]
   * opts: {chartId, colorOf(id), ticker(event) -> Node[] | string, emptyTicker, frameMs, top}
   * Returns {setFrames(frames)} so a page can swap datasets (e.g. with/without an era).
   */
  function race(frames, opts) {
    const TOP = opts.top ?? 10;
    const state = { frames, idx: Viz.reduceMotion ? frames.length - 1 : 0, playing: false, timer: null };
    const dateEl = document.getElementById("race-date");
    const tickerEl = document.getElementById("race-ticker");
    const playBtn = document.getElementById("race-play");
    const scrub = document.getElementById("race-scrub");
    const speedSel = document.getElementById("race-speed");

    const rowH = 38;
    const barH = 24;
    const crestSize = 28;
    const margin = { top: 24, right: 64, bottom: 8, left: 200 };
    const height = margin.top + rowH * TOP + margin.bottom;
    const svg = d3.select(`#${opts.chartId ?? "race-chart"}`).append("svg").attr("role", "img");
    const grid = svg.append("g");
    const bars = svg.append("g");
    let width = 0;
    let narrow = false;
    const x = d3.scaleLinear();
    const frameDuration = () => (opts.frameMs ?? 600) / +speedSel.value;
    const yPos = (i) => margin.top + i * rowH + (rowH - barH) / 2;

    function update(duration) {
      const frame = state.frames[state.idx];
      const maxN = d3.max(frame.ranked, (d) => d.n) ?? 0;
      x.domain([0, Math.max(4, maxN * 1.05)]).range([0, width - margin.left - margin.right]);
      const t = svg.transition().duration(duration).ease(d3.easeLinear);
      svg.attr("aria-label", `Most titles after ${frame.label}: ` + frame.ranked.map((d) => `${clubName(d.id)} ${d.n}`).join(", "));

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

      const rows = bars.selectAll("g.row").data(frame.ranked, (d) => d.id).join(
        (enter) => {
          const g = enter.append("g").attr("class", "row").attr("opacity", 0).attr("transform", `translate(${margin.left},${yPos(TOP)})`);
          g.append("path").attr("class", "mark").attr("fill", (d) => opts.colorOf(d.id)).property("_w", 0);
          g.append("text").attr("class", "label-name").attr("x", nations ? -10 : -34).attr("y", barH / 2).attr("dy", "0.35em").attr("text-anchor", "end");
          if (!nations) g.append("g").attr("transform", `translate(-28,${(barH - 15) / 2})`).each(function (d) { svgFlag(d3.select(this), clubs[d.id]?.country); });
          if (opts.icons !== false) {
            g.append("g").attr("class", "crest-slot").each(function (d) { svgCrest(d3.select(this), d.id, crestSize); })
              .attr("transform", `translate(${crestSize / 2 + 4},${barH / 2})`);
          }
          g.append("text").attr("class", "label-value").attr("y", barH / 2).attr("dy", "0.35em").property("_v", 0);
          return g;
        },
        (u) => u,
        (exit) => exit.transition(t).attr("opacity", 0).attr("transform", `translate(${margin.left},${yPos(TOP)})`).remove()
      );

      rows.select("text.label-name").text((d) => fit(clubName(d.id), narrow));
      rows.transition(t).attr("opacity", 1).attr("transform", (d, i) => `translate(${margin.left},${yPos(i)})`);
      rows.select("path").transition(t).attrTween("d", function (d) {
        const i = d3.interpolate(this._w, x(d.n));
        return (k) => barPath(0, 0, (this._w = i(k)), barH);
      });
      rows.select("g.crest-slot").transition(t).attr("transform", (d) => `translate(${x(d.n) + crestSize / 2 + 4},${barH / 2})`);
      const valueGap = opts.icons === false ? 8 : crestSize + 10;
      rows.select("text.label-value").transition(t).attr("x", (d) => x(d.n) + valueGap)
        .tween("text", function (d) {
          const i = d3.interpolateRound(this._v, d.n);
          return (k) => (this.textContent = this._v = i(k));
        });

      dateEl.textContent = frame.label;
      scrub.value = state.idx;
      tickerEl.replaceChildren();
      if (!frame.event) tickerEl.textContent = opts.emptyTicker;
      else tickerEl.append(...[].concat(opts.ticker(frame.event)));
    }

    function step() {
      if (state.idx >= state.frames.length - 1) return pause();
      state.idx++;
      update(frameDuration());
      state.timer = setTimeout(step, frameDuration());
    }
    function play() {
      if (state.idx >= state.frames.length - 1) {
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
      const done = state.idx >= state.frames.length - 1;
      playBtn.textContent = done ? "↺" : "▶";
      playBtn.setAttribute("aria-label", done ? "Replay" : "Play");
    }
    playBtn.addEventListener("click", () => (state.playing ? pause() : play()));
    scrub.addEventListener("input", () => {
      pause();
      state.idx = +scrub.value;
      update(0);
    });

    scrub.max = frames.length - 1;
    Viz.responsive(opts.chartId ?? "race-chart", (w) => {
      width = w;
      narrow = w < 560;
      margin.left = narrow ? 150 : 200;
      svg.attr("viewBox", `0 0 ${w} ${height}`);
      update(0);
    });
    pause();
    if (!Viz.reduceMotion) {
      const io = new IntersectionObserver((entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          io.disconnect();
          if (state.idx === 0) play();
        }
      }, { threshold: 0.6 });
      io.observe(document.getElementById(opts.chartId ?? "race-chart"));
    }

    return {
      setFrames(next) {
        pause();
        const atEnd = state.idx >= state.frames.length - 1;
        state.frames = next;
        scrub.max = next.length - 1;
        state.idx = atEnd ? next.length - 1 : Math.min(state.idx, next.length - 1);
        update(400);
        pause();
      },
    };
  }

  /** Cumulative ranking frames from a chronological list of events with a `champion` field. */
  function titleFrames(events, labelOf, initialLabel, top = 10) {
    const tally = new Map();
    const reached = new Map();
    const frames = [{ label: initialLabel, event: null, ranked: [] }];
    events.forEach((e, i) => {
      tally.set(e.champion, (tally.get(e.champion) ?? 0) + 1);
      reached.set(e.champion, i);
      const ranked = [...tally.entries()]
        .map(([id, n]) => ({ id, n, since: reached.get(id) }))
        .sort((a, b) => b.n - a.n || a.since - b.since)
        .slice(0, top);
      frames.push({ label: labelOf(e), event: e, ranked });
    });
    return frames;
  }

  /**
   * Ranked rows with an icon, a bar and up to two numbers.
   * rows: [{icon: Node, label, value, second?, tip?(t)}]; headers: [first, value, second]
   */
  function rankList(root, rows, headers) {
    root.replaceChildren();
    const maxN = d3.max(rows, (r) => r.value) || 1;
    const head = el("div", "rank-head");
    head.append(el("span"), el("span", null, headers[0]), el("span"), el("span", "num", headers[1]), el("span", "num", headers[2] ?? ""));
    root.append(head);
    rows.forEach((r) => {
      const row = el("div", "rank-row");
      const cell = el("div", "bar-cell");
      const bar = el("div", "bar");
      bar.style.width = `${(r.value / maxN) * 100}%`;
      if (r.color) bar.style.setProperty("--c", r.color);
      cell.append(bar);
      row.append(r.icon ?? el("span"), el("span", "name", r.label), cell, el("span", "num strong", String(r.value)),
        el("span", "num", r.second != null ? String(r.second) : ""));
      if (r.tip) Viz.tooltipOnNode(row, r.tip);
      root.append(row);
    });
  }

  return {
    rankList,
    clubs, countries, clubName, countryName, fit, scoreText, crest, svgCrest, flag, svgFlag, clubLabel,
    richTable, withSub, statTiles, repeatedFinals, groupRows, race, titleFrames,
  };
};
