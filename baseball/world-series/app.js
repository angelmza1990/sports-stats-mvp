/* World Series: every chart on the page, built with D3 v7. */
(async function () {
  "use strict";

  const { el, table, responsive, tooltipOn, tooltipOnNode, ttTitle, ttNote, barPath, columnPath } = Viz;
  const data = await d3.json(document.body.dataset.src);

  const franchises = data.franchises;
  const byId = Object.fromEntries(franchises.map((f) => [f.id, f]));
  const seasons = data.seasons;
  const latest = seasons[seasons.length - 1];

  const LEAGUE = {
    AL: { label: "American League", short: "AL", color: "var(--al)" },
    NL: { label: "National League", short: "NL", color: "var(--nl)" },
  };
  const leagueColor = (fid) => LEAGUE[byId[fid].conference].color;
  const mvpText = (s) => s.mvps.join(", ");

  /* ---------- Logos ---------- */

  const LOGO_BASE = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/mlb";
  const logoUrl = (code, dark = Viz.isDark()) => `${LOGO_BASE}/${dark ? "500-dark" : "500"}/${code}.png&h=96&w=96`;

  function logo(fid, className = "logo") {
    const f = byId[fid];
    const badge = () => {
      const b = el("span", `badge ${className === "logo" ? "" : className}`, f.id);
      b.setAttribute("aria-hidden", "true");
      return b;
    };
    const img = el("img", className);
    img.alt = "";
    img.loading = "lazy";
    img.decoding = "async";
    img.dataset.logo = f.logo;
    img.src = logoUrl(f.logo);
    img.addEventListener("error", () => {
      if (img.src.includes("500-dark")) img.src = logoUrl(f.logo, false);
      else img.replaceWith(badge());
    });
    return img;
  }

  function svgLogo(g, fid, size) {
    const f = byId[fid];
    g.selectAll("*").remove();
    g.append("image").attr("data-logo", f.logo).attr("href", logoUrl(f.logo))
      .attr("x", -size / 2).attr("y", -size / 2).attr("width", size).attr("height", size)
      .on("error", function () {
        if (this.getAttribute("href").includes("500-dark")) this.setAttribute("href", logoUrl(f.logo, false));
        else {
          g.selectAll("*").remove();
          g.append("circle").attr("class", "badge-circle").attr("r", size / 2 - 1);
          g.append("text").attr("class", "badge-text").attr("text-anchor", "middle").attr("dy", "0.35em").text(f.id);
        }
      });
  }

  Viz.onThemeChange(() => {
    document.querySelectorAll("img[data-logo]").forEach((img) => (img.src = logoUrl(img.dataset.logo)));
    document.querySelectorAll("image[data-logo]").forEach((img) => img.setAttribute("href", logoUrl(img.dataset.logo)));
  });

  // "Brooklyn Robins" -> "Robins", "Los Angeles Dodgers" -> "Dodgers".
  const CITY = /^(New York|Los Angeles|San Francisco|San Diego|St\. Louis|Kansas City|Tampa Bay|Boston|Brooklyn|Chicago|Philadelphia|Oakland|Washington|Milwaukee|Atlanta|Pittsburgh|Cincinnati|Detroit|Cleveland|Baltimore|Minnesota|Toronto|Florida|Miami|Anaheim|Houston|Arizona|Colorado|Texas|Seattle) /;
  function shortName(name, fid) {
    const f = byId[fid];
    if (f && name.endsWith(f.short)) return f.short;
    return name.replace(CITY, "") || name;
  }

  function seriesTooltip(t, s) {
    t.append(ttTitle(`${s.year} World Series`));
    t.append(Viz.ttRow(LEAGUE[s.league].color, s.result + (s.ties ? `, ${s.ties} tie` : ""), `${s.championName} (${s.league}) def. ${s.runnerUpName} (${s.runnerUpLeague})`));
    if (s.bestOf !== 7) t.append(ttNote(`Best of ${s.bestOf}`));
    if (s.mvps.length) t.append(ttNote(`MVP: ${mvpText(s)}${s.mvpOnLoser ? ", from the losing team" : ""}`));
  }

  const counts = d3.rollup(seasons, (v) => v.length, (s) => s.champion);
  const titleCount = (fid) => counts.get(fid) ?? 0;

  /* ---------- Droughts (used by the stat tiles and their own section) ---------- */

  const gaps = [];
  franchises.forEach((f) => {
    const won = seasons.filter((s) => s.champion === f.id).map((s) => s.year);
    won.forEach((y, i) => {
      const next = won[i + 1];
      gaps.push({ fid: f.id, from: y, to: next ?? null, years: (next ?? latest.year + 1) - y - (next ? 0 : 1), open: next == null });
    });
  });
  gaps.sort((a, b) => b.years - a.years || a.from - b.from);

  /* ---------- Stat tiles ---------- */

  (function stats() {
    const root = document.getElementById("stats");
    const [leader, n] = d3.greatest(counts, (d) => d[1]);
    let best = { fid: null, len: 0 };
    let run = { fid: null, len: 0 };
    seasons.forEach((s, i) => {
      const prev = seasons[i - 1];
      const consecutive = prev && (prev.year === s.year - 1 || (prev.year === 1993 && s.year === 1995) || (prev.year === 1903 && s.year === 1905));
      run = s.champion === run.fid && consecutive ? { ...run, len: run.len + 1 } : { fid: s.champion, len: 1, from: s.year };
      if (run.len > best.len) best = { ...run, to: s.year };
    });
    const wait = gaps[0];
    const tiles = [
      { label: "Most titles", value: String(n), logo: leader, detail: byId[leader].name },
      { label: "Longest streak", value: String(best.len), logo: best.fid, detail: `${byId[best.fid].short}, ${best.from}–${best.to}` },
      { label: "Longest wait", value: `${wait.years} yrs`, logo: wait.fid, detail: `${byId[wait.fid].short}, ${wait.from}–${wait.to ?? "today"}` },
      { label: `${latest.year} champion`, value: shortName(latest.championName, latest.champion), logo: latest.champion, detail: `${latest.result} vs ${latest.runnerUpName}` },
    ];
    tiles.forEach((t) => {
      const box = el("div", "stat");
      const value = el("div", "value");
      if (t.logo) value.append(logo(t.logo));
      value.append(document.createTextNode(t.value));
      box.append(el("span", "label", t.label), value, el("span", "detail", t.detail));
      root.append(box);
    });
  })();

  /* ---------- Bar chart race ---------- */

  (function race() {
    const TOP = 10;
    const tally = new Map();
    const reached = new Map();
    const lastName = new Map();
    const frames = [null, ...seasons].map((s, i) => {
      if (s) {
        tally.set(s.champion, (tally.get(s.champion) ?? 0) + 1);
        reached.set(s.champion, i);
        lastName.set(s.champion, s.championName);
      }
      const ranked = [...tally.keys()]
        .map((fid) => ({ fid, n: tally.get(fid), since: reached.get(fid), name: lastName.get(fid) }))
        .sort((a, b) => b.n - a.n || a.since - b.since)
        .slice(0, TOP);
      return { year: s ? s.year : seasons[0].year - 1, s, ranked };
    });

    const state = { idx: Viz.reduceMotion ? frames.length - 1 : 0, playing: false, timer: null };
    const dateEl = document.getElementById("race-date");
    const tickerEl = document.getElementById("race-ticker");
    const playBtn = document.getElementById("race-play");
    const scrub = document.getElementById("race-scrub");
    const speedSel = document.getElementById("race-speed");
    scrub.max = frames.length - 1;
    Viz.legend("race-legend", [
      { label: "American League", color: LEAGUE.AL.color },
      { label: "National League", color: LEAGUE.NL.color },
    ]);

    const rowH = 40;
    const barH = 24;
    const logoSize = 28;
    const margin = { top: 24, right: 64, bottom: 8, left: 190 };
    const height = margin.top + rowH * TOP + margin.bottom;
    const svg = d3.select("#race-chart").append("svg").attr("role", "img");
    const grid = svg.append("g");
    const bars = svg.append("g");
    let width = 0;
    let narrow = false;
    const x = d3.scaleLinear();
    const frameDuration = () => 520 / +speedSel.value;
    const yPos = (i) => margin.top + i * rowH + (rowH - barH) / 2;

    function update(duration) {
      const frame = frames[state.idx];
      const maxN = d3.max(frame.ranked, (d) => d.n) ?? 0;
      x.domain([0, Math.max(5, maxN * 1.05)]).range([0, width - margin.left - margin.right]);
      const t = svg.transition().duration(duration).ease(d3.easeLinear);
      svg.attr("aria-label", `Most World Series titles after ${frame.year}: ` + frame.ranked.map((d) => `${byId[d.fid].name} ${d.n}`).join(", "));
      const ticks = x.ticks(narrow ? 4 : 6).filter(Number.isInteger);
      grid.selectAll("g.tick").data(ticks, (d) => d).join(
        (enter) => {
          const g = enter.append("g").attr("class", "tick").attr("opacity", 0).attr("transform", (d) => `translate(${margin.left + x(d)},0)`);
          g.append("line").attr("class", (d) => (d === 0 ? "baseline" : "gridline")).attr("y1", margin.top - 6).attr("y2", height - margin.bottom);
          g.append("text").attr("class", "tick-label").attr("y", margin.top - 12).attr("text-anchor", "middle").text((d) => d);
          return g;
        },
        (u) => u,
        (exit) => exit.transition(t).attr("opacity", 0).remove(),
      ).transition(t).attr("opacity", 1).attr("transform", (d) => `translate(${margin.left + x(d)},0)`);

      const rows = bars.selectAll("g.row").data(frame.ranked, (d) => d.fid).join(
        (enter) => {
          const g = enter.append("g").attr("class", "row").attr("opacity", 0).attr("transform", `translate(${margin.left},${yPos(TOP)})`);
          g.append("path").attr("class", "mark").attr("fill", (d) => leagueColor(d.fid)).property("_w", 0);
          g.append("text").attr("class", "label-name").attr("x", -10).attr("y", barH / 2).attr("dy", "0.35em").attr("text-anchor", "end");
          g.append("g").attr("class", "logo-slot").each(function (d) {
            svgLogo(d3.select(this), d.fid, logoSize);
          }).attr("transform", `translate(${logoSize / 2 + 4},${barH / 2})`);
          g.append("text").attr("class", "label-value").attr("y", barH / 2).attr("dy", "0.35em").property("_v", 0);
          return g;
        },
        (u) => u,
        (exit) => exit.transition(t).attr("opacity", 0).attr("transform", `translate(${margin.left},${yPos(TOP)})`).remove(),
      );
      // The name the franchise had at its latest title in this frame: the Brooklyn Dodgers become Los Angeles in 1959.
      rows.select("text.label-name").text((d) => (narrow ? shortName(d.name, d.fid) : d.name));
      rows.transition(t).attr("opacity", 1).attr("transform", (d, i) => `translate(${margin.left},${yPos(i)})`);
      rows.select("path").transition(t).attrTween("d", function (d) {
        const i = d3.interpolate(this._w, x(d.n));
        return (k) => barPath(0, 0, (this._w = i(k)), barH);
      });
      rows.select("g.logo-slot").transition(t).attr("transform", (d) => `translate(${x(d.n) + logoSize / 2 + 4},${barH / 2})`);
      rows.select("text.label-value").transition(t)
        .attr("x", (d) => x(d.n) + logoSize + 10)
        .tween("text", function (d) {
          const i = d3.interpolateRound(this._v, d.n);
          return (k) => (this.textContent = this._v = i(k));
        });
      dateEl.textContent = String(frame.year);
      scrub.value = state.idx;
      tickerEl.replaceChildren();
      const s = frame.s;
      if (!s) tickerEl.textContent = "Press play to start in 1903, the first World Series.";
      else tickerEl.append(logo(s.champion), el("strong", null, `${s.year} · ${s.championName}`),
        document.createTextNode(` def. ${s.runnerUpName} ${s.result}${s.mvps.length ? ` · MVP: ${mvpText(s)}` : ""}`));
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
      margin.left = narrow ? 92 : 190;
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
      io.observe(document.getElementById("race-chart"));
    }
    table("race-table", ["Franchise", "Titles", "Years won"], d3.sort(counts, (d) => -d[1]).map(([fid, n]) =>
      [byId[fid].name, String(n), seasons.filter((s) => s.champion === fid).map((s) => s.year).join(", ")]));
  })();

  /* ---------- Stacked columns: American League (bottom) / National League (top) ---------- */

  function stackedColumns({ chartId, groups, title }) {
    const maxN = d3.max(groups, (g) => g.list.length);
    responsive(chartId, (width) => {
      const container = d3.select(`#${chartId}`);
      container.selectAll("*").remove();
      const height = 260;
      const margin = { top: 20, right: 8, bottom: 28, left: 28 };
      const x = d3.scaleBand().domain(groups.map((g) => g.label)).range([margin.left, width - margin.right]).padding(0.35);
      const y = d3.scaleLinear().domain([0, maxN]).nice().range([height - margin.bottom, margin.top]);
      const colW = Math.min(48, x.bandwidth());
      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", title);
      const axis = svg.append("g").attr("class", "axis");
      y.ticks(5).filter(Number.isInteger).forEach((v) => {
        axis.append("line").attr("class", v === 0 ? "baseline" : "gridline").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", y(v)).attr("y2", y(v));
        axis.append("text").attr("x", margin.left - 8).attr("y", y(v)).attr("dy", "0.35em").attr("text-anchor", "end").text(v);
      });
      const short = x.bandwidth() < 64;
      groups.forEach((g) => axis.append("text").attr("x", x(g.label) + x.bandwidth() / 2).attr("y", height - 8).attr("text-anchor", "middle").text(short && g.short ? g.short : g.label));
      const col = svg.selectAll("g.col").data(groups).join("g").attr("class", "col mark-group")
        .attr("transform", (g) => `translate(${x(g.label) + (x.bandwidth() - colW) / 2},0)`);
      col.append("rect").attr("x", -6).attr("y", margin.top).attr("width", colW + 12).attr("height", height - margin.top - margin.bottom).attr("fill", "transparent");
      col.each(function (g) {
        const a = g.list.filter((s) => s.league === "AL").length;
        const n = g.list.length - a;
        const sel = d3.select(this);
        const base = y(0);
        const aTop = y(a);
        const top = y(a + n);
        if (a > 0) sel.append("path").attr("class", "mark").attr("fill", LEAGUE.AL.color).attr("d", n > 0 ? `M0,${base}V${aTop}H${colW}V${base}Z` : columnPath(0, aTop, colW, base - aTop));
        if (n > 0) sel.append("path").attr("class", "mark").attr("fill", LEAGUE.NL.color).attr("d", columnPath(0, top, colW, (a > 0 ? aTop - 2 : base) - top));
        sel.append("text").attr("class", "label-value").attr("x", colW / 2).attr("y", top - 6).attr("text-anchor", "middle").text(g.list.length);
      });
      tooltipOn(col, (t, g) => {
        t.append(ttTitle(g.label));
        t.append(Viz.ttRow(LEAGUE.AL.color, g.list.filter((s) => s.league === "AL").length, "American League"));
        t.append(Viz.ttRow(LEAGUE.NL.color, g.list.filter((s) => s.league === "NL").length, "National League"));
        t.append(ttNote(g.list.map((s) => `${s.year} ${shortName(s.championName, s.champion)}`).join(", ")));
      });
    });
  }

  /* ---------- American League vs National League ---------- */

  (function leagues() {
    const al = seasons.filter((s) => s.league === "AL").length;
    const nl = seasons.length - al;
    const root = document.getElementById("versus");
    const side = (code, n, right) => {
      const box = el("div", `side${right ? " right" : ""}`);
      const name = el("div", "name");
      const key = el("i");
      key.style.setProperty("--c", LEAGUE[code].color);
      if (right) name.append(document.createTextNode(LEAGUE[code].label), key);
      else name.append(key, document.createTextNode(LEAGUE[code].label));
      box.append(name, el("div", "big", String(n)));
      return box;
    };
    root.append(side("AL", al), el("div", "mid", `${seasons.length} Series`), side("NL", nl, true));
    const split = el("div", "split");
    [["AL", al], ["NL", nl]].forEach(([code, n]) => {
      const seg = el("div");
      seg.style.setProperty("--c", LEAGUE[code].color);
      seg.style.flex = String(n);
      split.append(seg);
    });
    root.after(split);
    // The Yankees alone account for a large share of the American League's edge.
    const nyy = titleCount("NYY");
    const since = seasons.filter((s) => s.year >= 2000);
    split.after(el("p", "split-note", `Without the Yankees' ${nyy} titles the American League trails ${al - nyy}–${nl}. Since 2000: American League ${since.filter((s) => s.league === "AL").length}, National League ${since.filter((s) => s.league === "NL").length}.`));
    Viz.legend("decade-legend", [{ label: "American League", color: LEAGUE.AL.color }, { label: "National League", color: LEAGUE.NL.color }]);
    const decades = d3.groups(seasons, (s) => Math.floor(s.year / 10) * 10);
    stackedColumns({ chartId: "decade-chart", groups: decades.map(([d, list]) => ({ label: `${d}s`, short: `'${String(d).slice(2)}s`, list })), title: "World Series titles by decade, American League vs National League" });
    table("decade-table", ["Decade", "American League", "National League", "Champions"], decades.map(([d, list]) => [
      `${d}s`, String(list.filter((s) => s.league === "AL").length), String(list.filter((s) => s.league === "NL").length),
      list.map((s) => `${s.year} ${shortName(s.championName, s.champion)}`).join(", "),
    ]));
  })();

  /* ---------- Champions wall ---------- */

  (function wall() {
    const root = document.getElementById("wall-grid");
    d3.groups(seasons, (s) => Math.floor(s.year / 10) * 10).forEach(([decade, list]) => {
      root.append(el("p", "decade", `${decade}s`));
      list.forEach((s) => {
        const tile = el("div", "tile");
        tile.setAttribute("role", "listitem");
        tile.setAttribute("aria-label", `${s.year}: ${s.championName} def. ${s.runnerUpName} ${s.result}`);
        tile.style.setProperty("--c", LEAGUE[s.league].color);
        tile.append(el("span", "year", String(s.year)), logo(s.champion), el("span", "team", shortName(s.championName, s.champion)));
        tooltipOnNode(tile, (t) => seriesTooltip(t, s));
        root.append(tile);
      });
    });
  })();

  /* ---------- Titles by franchise ---------- */

  (function byFranchise() {
    const root = document.getElementById("franchise-columns");
    const maxN = d3.max(counts.values());
    ["AL", "NL"].forEach((lg) => {
      const teams = franchises.filter((f) => f.conference === lg);
      const card = el("div", "conf-card");
      const h = el("h3");
      const key = el("i");
      key.style.setProperty("--c", LEAGUE[lg].color);
      h.append(key, document.createTextNode(LEAGUE[lg].label), el("span", null, `${d3.sum(teams, (f) => titleCount(f.id))} titles`));
      card.append(h);
      let zeroHeader = false;
      d3.sort(teams, (a, b) => titleCount(b.id) - titleCount(a.id) || d3.ascending(a.name, b.name)).forEach((f) => {
        const n = titleCount(f.id);
        if (n === 0 && !zeroHeader) {
          card.append(el("p", "zero-head", "Still waiting"));
          zeroHeader = true;
        }
        const row = el("div", `franchise-row${n ? "" : " zero"}`);
        const bar = el("div", "bar");
        bar.style.setProperty("--c", LEAGUE[lg].color);
        bar.style.width = `${(n / maxN) * 100}%`;
        const wrap = el("div");
        wrap.append(bar);
        row.append(logo(f.id), el("span", "name", f.name), wrap, el("span", "n", n ? String(n) : "–"));
        const won = seasons.filter((s) => s.champion === f.id);
        const lost = seasons.filter((s) => s.runnerUp === f.id);
        tooltipOnNode(row, (t) => {
          t.append(ttTitle(f.name), Viz.ttRow(LEAGUE[lg].color, n, n === 1 ? "title" : "titles"));
          if (won.length) t.append(ttNote(won.map((s) => s.year).join(", ")));
          t.append(ttNote(lost.length ? `Lost ${lost.length}: ${lost.map((s) => s.year).join(", ")}` : won.length ? "Never lost a World Series" : "Never reached a World Series"));
          const names = [...new Set(won.map((s) => s.championName))].filter((nm) => nm !== f.name);
          if (names.length) t.append(ttNote(`Also as: ${names.join(", ")}`));
        });
        card.append(row);
      });
      root.append(card);
    });
  })();

  /* ---------- Droughts ---------- */

  (function droughts() {
    const root = document.getElementById("drought-list");
    const top = gaps.slice(0, 15);
    const start = d3.min(top, (g) => g.from);
    const end = latest.year + 1;
    const pos = (y) => `${((y - start) / (end - start)) * 100}%`;
    const axis = el("div", "drought-axis");
    const ticks = el("div", "ticks");
    d3.range(Math.ceil(start / 20) * 20, end, 20).forEach((y) => {
      const tick = el("span", y % 40 ? "minor" : null, String(y));
      tick.style.left = pos(y);
      ticks.append(tick);
    });
    axis.append(el("span"), el("span"), ticks, el("span"));
    root.append(axis);
    top.forEach((g) => {
      const f = byId[g.fid];
      const row = el("div", "drought-row");
      const name = el("div", "name", f.short);
      name.append(el("small", null, g.open ? `${g.from} – still waiting` : `${g.from} – ${g.to}`));
      const track = el("div", "track");
      const bar = el("span", g.open ? "open" : null);
      bar.style.setProperty("--c", leagueColor(g.fid));
      bar.style.left = pos(g.from);
      bar.style.width = `calc(${pos((g.to ?? end))} - ${pos(g.from)})`;
      track.append(bar);
      row.append(logo(g.fid), name, track, el("span", "n", String(g.years)));
      const lost = seasons.filter((s) => s.runnerUp === g.fid && s.year > g.from && (!g.to || s.year < g.to));
      tooltipOnNode(row, (t) => {
        t.append(ttTitle(f.name), Viz.ttRow(leagueColor(g.fid), `${g.years} years`, g.open ? `since the ${g.from} title` : `between the ${g.from} and ${g.to} titles`));
        if (lost.length) t.append(ttNote(`World Series lost in between: ${lost.map((s) => s.year).join(", ")}`));
      });
      root.append(row);
    });
    const never = franchises.filter((f) => !titleCount(f.id));
    root.append(el("p", "footnote", `Never won: ${never.map((f) => f.short).join(", ")}. The Seattle Mariners are the only franchise that has never reached a World Series.`));
  })();

  /* ---------- Most repeated World Series ---------- */

  (function repeated() {
    const root = document.getElementById("pairs-list");
    const pairs = d3.groups(seasons, (s) => [s.champion, s.runnerUp].sort().join("|"))
      .filter(([, list]) => list.length >= 2)
      .sort((a, b) => b[1].length - a[1].length || b[1][b[1].length - 1].year - a[1][a[1].length - 1].year);
    pairs.slice(0, 12).forEach(([key, list]) => {
      const [a, b] = key.split("|");
      const wa = list.filter((s) => s.champion === a).length;
      const wb = list.length - wa;
      const [first, second] = wa >= wb ? [a, b] : [b, a];
      const row = el("div", "pair-row");
      const countBox = el("div", "count", String(list.length));
      countBox.append(el("small", null, "Series"));
      const players = el("div", "players");
      [first, second].forEach((fid, i) => {
        const span = el("span");
        span.append(logo(fid), document.createTextNode(byId[fid].name));
        players.append(span);
        if (i === 0) players.append(el("span", "vs", "vs"));
      });
      const h2h = el("div", "h2h", wa === wb ? `Tied ${wa}–${wb}` : `${byId[first].short} ${Math.max(wa, wb)}–${Math.min(wa, wb)}`);
      const meta = el("div", "meta", list.map((s) => `${s.year} ${shortName(s.championName, s.champion)} ${s.result}`).join(" · "));
      row.append(countBox, players, h2h, meta);
      root.append(row);
    });
  })();

  /* ---------- Most World Series lost ---------- */

  (function runnersUp() {
    const root = document.getElementById("runners-table");
    const lost = d3.groups(seasons, (s) => s.runnerUp)
      .map(([fid, list]) => ({ fid, list, won: titleCount(fid) }))
      .sort((a, b) => b.list.length - a.list.length || b.won - a.won);
    const t = el("table");
    const head = el("tr");
    [["Franchise"], ["Series lost", "num", "Lost"], ["Series played", "num", "Played"], ["Titles", "num"], ["Lost Series", "years"]].forEach(([h, cls, short]) => {
      const th = el("th", cls);
      th.append(el("span", short ? "long" : null, h));
      if (short) th.append(el("span", "short", short));
      head.append(th);
    });
    t.append(head);
    lost.forEach(({ fid, list, won }) => {
      const tr = el("tr");
      const years = list.map((s) => `${s.year} (${shortName(s.championName, s.champion)})`).join(", ");
      const name = el("td");
      const span = el("span", "who");
      span.append(logo(fid), document.createTextNode(byId[fid].name));
      name.append(span, el("div", "sub", years));
      tr.append(name, el("td", "num strong", String(list.length)), el("td", "num", String(list.length + won)), el("td", "num", String(won)), el("td", "years", years));
      t.append(tr);
    });
    root.replaceChildren(t);
  })();

  /* ---------- Series length ---------- */

  (function series() {
    Viz.legend("series-legend", [{ label: "American League champion", color: LEAGUE.AL.color }, { label: "National League champion", color: LEAGUE.NL.color }]);
    const sevens = seasons.filter((s) => s.bestOf === 7);
    const NAMES = { "4–0": "Sweep (4–0)", "4–1": "In 5 (4–1)", "4–2": "In 6 (4–2)", "4–3": "Game 7 (4–3)" };
    const groups = Object.keys(NAMES).map((r) => ({ label: NAMES[r], short: r, list: sevens.filter((s) => s.result === r) }));
    stackedColumns({ chartId: "series-chart", groups, title: "Best-of-seven World Series by length" });
    table("series-table", ["Result", "Total", "American League", "National League", "Years"], groups.map((g) => [
      g.label, String(g.list.length), String(g.list.filter((s) => s.league === "AL").length), String(g.list.filter((s) => s.league === "NL").length),
      g.list.map((s) => s.year).join(", "),
    ]));
  })();

  /* ---------- World Series MVPs ---------- */

  (function mvp() {
    const root = document.getElementById("mvp-list");
    const awards = seasons.flatMap((s) => s.mvps.map((name, i) => ({ s, name, pitcher: s.mvpPitcher[i] })));
    const groups = d3.sort(d3.groups(awards, (a) => a.name), (a, b) => b[1].length - a[1].length || a[1][0].s.year - b[1][0].s.year);
    const multi = groups.filter(([, list]) => list.length >= 2);
    multi.forEach(([name, list]) => {
      const row = el("div", "mvp-row");
      const tokens = el("div", "tokens");
      list.forEach(({ s }) => {
        const team = s.mvpOnLoser ? s.runnerUp : s.champion;
        const token = el("span", "token");
        token.setAttribute("aria-label", `${s.year}, ${byId[team].name}`);
        token.append(logo(team));
        tooltipOnNode(token, (t) => seriesTooltip(t, s));
        tokens.append(token);
      });
      row.append(el("span", "who", name), tokens, el("span", "n", String(list.length)));
      root.append(row);
    });
    const years = seasons.filter((s) => s.mvps.length);
    const shared = years.filter((s) => s.mvps.length > 1);
    const pitchers = awards.filter((a) => a.pitcher).length;
    const onLoser = years.filter((s) => s.mvpOnLoser);
    root.after(el("p", "mvp-more",
      `${groups.length - multi.length} more players have won it once, for ${groups.length} winners in ${years.length} Series. ` +
      `Pitchers have taken ${pitchers} of the ${awards.length} awards. ` +
      `Shared awards: ${shared.map((s) => `${s.year} (${mvpText(s)})`).join("; ")}. ` +
      `Only ${onLoser.map((s) => `${mvpText(s)} (${s.year})`).join(", ")} won it for the losing team.`));
  })();

  document.getElementById("sources").replaceChildren(...data.meta.sources.flatMap((u, i) => {
    const a = el("a", null, decodeURIComponent(u.split("/wiki/")[1]).replace(/_/g, " "));
    a.href = u;
    return i ? [document.createTextNode(", "), a] : [a];
  }));
  document.getElementById("data-through").textContent = `Covers every World Series through ${latest.year}.`;
})();
