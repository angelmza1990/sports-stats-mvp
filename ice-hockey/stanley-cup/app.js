/* Stanley Cup: every chart on the page, built with D3 v7. */
(async function () {
  "use strict";

  const { el, table, responsive, tooltipOn, tooltipOnNode, ttTitle, ttNote, barPath, columnPath } = Viz;
  const data = await d3.json(document.body.dataset.src);

  const franchises = data.franchises;
  const byId = Object.fromEntries(franchises.map((f) => [f.id, f]));
  const seasons = data.seasons;
  const latest = seasons[seasons.length - 1];

  const CONF = {
    East: { label: "Eastern Conference", color: "var(--east)" },
    West: { label: "Western Conference", color: "var(--west)" },
  };
  const COUNTRY = {
    CAN: { label: "Canada", color: "var(--can)" },
    USA: { label: "United States", color: "var(--usa)" },
  };
  const confColor = (fid) => (byId[fid]?.conference ? CONF[byId[fid].conference].color : "var(--defunct)");

  /* ---------- Logos ---------- */

  const LOGO_BASE = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/nhl";
  const logoUrl = (code, dark = Viz.isDark()) => `${LOGO_BASE}/${dark ? "500-dark" : "500"}/${code}.png&h=96&w=96`;
  const badgeText = (f) => f.id;

  function logo(fid, className = "logo") {
    const f = byId[fid];
    const badge = () => {
      const b = el("span", `badge ${className === "logo" ? "" : className}`, badgeText(f));
      b.setAttribute("aria-hidden", "true");
      return b;
    };
    if (!f.logo) return badge();
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
    const badge = () => {
      g.selectAll("*").remove();
      g.append("circle").attr("class", "badge-circle").attr("r", size / 2 - 1);
      g.append("text").attr("class", "badge-text").attr("text-anchor", "middle").attr("dy", "0.35em").text(badgeText(f));
    };
    if (!f.logo) return badge();
    g.append("image").attr("data-logo", f.logo).attr("href", logoUrl(f.logo))
      .attr("x", -size / 2).attr("y", -size / 2).attr("width", size).attr("height", size)
      .on("error", function () {
        if (this.getAttribute("href").includes("500-dark")) this.setAttribute("href", logoUrl(f.logo, false));
        else badge();
      });
  }

  Viz.onThemeChange(() => {
    document.querySelectorAll("img[data-logo]").forEach((img) => (img.src = logoUrl(img.dataset.logo)));
    document.querySelectorAll("image[data-logo]").forEach((img) => img.setAttribute("href", logoUrl(img.dataset.logo)));
  });

  function shortName(name, fid) {
    const f = byId[fid];
    if (f && name.endsWith(f.short)) return f.short;
    // Historical names keep everything after the city: "Toronto St. Patricks" -> "St. Patricks".
    return name.replace(/\s*\(original\)$/, "").replace(CITY, "") || name;
  }
  const CITY = /^(Toronto|Montreal|Ottawa|Vancouver|Victoria|Seattle|Chicago|Detroit|New York|Boston|Quebec|Minnesota|Hartford|Atlanta|Kansas City|Colorado|Portland|Edmonton|Calgary|Mighty Ducks of) /;
  const displayName = (name) => name.replace(/\s*\(original\)$/, "");

  function finalTooltip(t, s) {
    t.append(ttTitle(`${s.year} Stanley Cup Final`));
    t.append(Viz.ttRow(COUNTRY[s.country].color, s.result, `${displayName(s.championName)} def. ${displayName(s.runnerUpName)}`));
    if (s.league !== "NHL") t.append(ttNote(`${s.league} champion`));
    if (s.mvp) t.append(ttNote(`Conn Smythe: ${s.mvp}${s.mvpOnLoser ? ", from the losing team" : ""}`));
  }

  const counts = d3.rollup(seasons, (v) => v.length, (s) => s.champion);
  const cupCount = (fid) => counts.get(fid) ?? 0;

  /* ---------- Stat tiles ---------- */

  (function stats() {
    const root = document.getElementById("stats");
    const [leader, n] = d3.greatest(counts, (d) => d[1]);
    let best = { fid: null, len: 0 };
    let run = { fid: null, len: 0 };
    seasons.forEach((s, i) => {
      const consecutive = i > 0 && seasons[i - 1].year === s.year - 1 || (i > 0 && seasons[i - 1].year === 2004 && s.year === 2006);
      run = s.champion === run.fid && consecutive ? { ...run, len: run.len + 1 } : { fid: s.champion, len: 1, from: s.year };
      if (run.len > best.len) best = { ...run, to: s.year };
    });
    const lastCanada = [...seasons].reverse().find((s) => s.country === "CAN");
    const tiles = [
      { label: "Most Cups", value: String(n), logo: leader, detail: byId[leader].name },
      { label: "Longest streak", value: String(best.len), logo: best.fid, detail: `${byId[best.fid].short}, ${best.from}–${best.to}` },
      { label: "Last Canadian champion", value: String(lastCanada.year), logo: lastCanada.champion, detail: displayName(lastCanada.championName) },
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
      { label: "Eastern Conference", color: CONF.East.color },
      { label: "Western Conference", color: CONF.West.color },
      { label: "Defunct", color: "var(--defunct)" },
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
      svg.attr("aria-label", `Most Stanley Cups after ${frame.year}: ` + frame.ranked.map((d) => `${byId[d.fid].name} ${d.n}`).join(", "));
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
          g.append("path").attr("class", "mark").attr("fill", (d) => confColor(d.fid)).property("_w", 0);
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
      rows.select("text.label-name").text((d) => (narrow ? shortName(d.name, d.fid) : byId[d.fid].defunct ? displayName(d.name) : byId[d.fid].name));
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
      if (!s) tickerEl.textContent = "Press play to start in 1915, the first Stanley Cup Final.";
      else tickerEl.append(logo(s.champion), el("strong", null, `${s.year} · ${displayName(s.championName)}`),
        document.createTextNode(` def. ${displayName(s.runnerUpName)} ${s.result}${s.mvp ? ` · Conn Smythe: ${s.mvp}` : ""}`));
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
    table("race-table", ["Franchise", "Cups", "Years won"], d3.sort(counts, (d) => -d[1]).map(([fid, n]) =>
      [byId[fid].name, String(n), seasons.filter((s) => s.champion === fid).map((s) => s.year).join(", ")]));
  })();

  /* ---------- Stacked columns: Canada (bottom) / United States (top) ---------- */

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
        const c = g.list.filter((s) => s.country === "CAN").length;
        const u = g.list.length - c;
        const sel = d3.select(this);
        const base = y(0);
        const cTop = y(c);
        const top = y(c + u);
        if (c > 0) sel.append("path").attr("class", "mark").attr("fill", COUNTRY.CAN.color).attr("d", u > 0 ? `M0,${base}V${cTop}H${colW}V${base}Z` : columnPath(0, cTop, colW, base - cTop));
        if (u > 0) sel.append("path").attr("class", "mark").attr("fill", COUNTRY.USA.color).attr("d", columnPath(0, top, colW, (c > 0 ? cTop - 2 : base) - top));
        sel.append("text").attr("class", "label-value").attr("x", colW / 2).attr("y", top - 6).attr("text-anchor", "middle").text(g.list.length);
      });
      tooltipOn(col, (t, g) => {
        t.append(ttTitle(g.label));
        t.append(Viz.ttRow(COUNTRY.CAN.color, g.list.filter((s) => s.country === "CAN").length, "Canada"));
        t.append(Viz.ttRow(COUNTRY.USA.color, g.list.filter((s) => s.country === "USA").length, "United States"));
        t.append(ttNote(g.list.map((s) => `${s.year} ${shortName(s.championName, s.champion)}`).join(", ")));
      });
    });
  }

  /* ---------- Canada vs United States ---------- */

  (function countries() {
    const can = seasons.filter((s) => s.country === "CAN").length;
    const usa = seasons.length - can;
    const root = document.getElementById("versus");
    const side = (code, n, right) => {
      const box = el("div", `side${right ? " right" : ""}`);
      const name = el("div", "name");
      const key = el("i");
      key.style.setProperty("--c", COUNTRY[code].color);
      if (right) name.append(document.createTextNode(COUNTRY[code].label), key);
      else name.append(key, document.createTextNode(COUNTRY[code].label));
      box.append(name, el("div", "big", String(n)));
      return box;
    };
    root.append(side("CAN", can), el("div", "mid", `${seasons.length} Cups`), side("USA", usa, true));
    const split = el("div", "split");
    [["CAN", can], ["USA", usa]].forEach(([code, n]) => {
      const seg = el("div");
      seg.style.setProperty("--c", COUNTRY[code].color);
      seg.style.flex = String(n);
      split.append(seg);
    });
    root.after(split);
    const since = seasons.filter((s) => s.year >= 1994);
    split.after(el("p", "split-note", `Since 1994: United States ${since.filter((s) => s.country === "USA").length}, Canada ${since.filter((s) => s.country === "CAN").length}. Canadian teams have reached ${since.filter((s) => s.runnerUpCountry === "CAN").length} Finals since then.`));
    Viz.legend("decade-legend", [{ label: "Canada", color: COUNTRY.CAN.color }, { label: "United States", color: COUNTRY.USA.color }]);
    const decades = d3.groups(seasons, (s) => Math.floor(s.year / 10) * 10);
    stackedColumns({ chartId: "decade-chart", groups: decades.map(([d, list]) => ({ label: `${d}s`, short: `'${String(d).slice(2)}s`, list })), title: "Stanley Cups by decade, Canada vs United States" });
    table("decade-table", ["Decade", "Canada", "United States", "Champions"], decades.map(([d, list]) => [
      `${d}s`, String(list.filter((s) => s.country === "CAN").length), String(list.filter((s) => s.country === "USA").length),
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
        tile.setAttribute("aria-label", `${s.year}: ${displayName(s.championName)} def. ${displayName(s.runnerUpName)} ${s.result}`);
        tile.style.setProperty("--c", COUNTRY[s.country].color);
        tile.append(el("span", "year", String(s.year)), logo(s.champion), el("span", "team", shortName(s.championName, s.champion)));
        tooltipOnNode(tile, (t) => finalTooltip(t, s));
        root.append(tile);
      });
    });
  })();

  /* ---------- Cups by franchise ---------- */

  (function byFranchise() {
    const root = document.getElementById("franchise-columns");
    const maxN = d3.max(counts.values());
    ["East", "West"].forEach((conf) => {
      const teams = franchises.filter((f) => f.conference === conf);
      const card = el("div", "conf-card");
      const h = el("h3");
      const key = el("i");
      key.style.setProperty("--c", CONF[conf].color);
      h.append(key, document.createTextNode(CONF[conf].label), el("span", null, `${d3.sum(teams, (f) => cupCount(f.id))} Cups`));
      card.append(h);
      let zeroHeader = false;
      d3.sort(teams, (a, b) => cupCount(b.id) - cupCount(a.id) || d3.ascending(a.name, b.name)).forEach((f) => {
        const n = cupCount(f.id);
        if (n === 0 && !zeroHeader) {
          card.append(el("p", "zero-head", "Still waiting"));
          zeroHeader = true;
        }
        const row = el("div", `franchise-row${n ? "" : " zero"}`);
        const bar = el("div", "bar");
        bar.style.setProperty("--c", CONF[conf].color);
        bar.style.width = `${(n / maxN) * 100}%`;
        const wrap = el("div");
        wrap.append(bar);
        row.append(logo(f.id), el("span", "name", f.name), wrap, el("span", "n", n ? String(n) : "–"));
        if (n) {
          const won = seasons.filter((s) => s.champion === f.id);
          tooltipOnNode(row, (t) => {
            t.append(ttTitle(f.name), Viz.ttRow(CONF[conf].color, n, n === 1 ? "Stanley Cup" : "Stanley Cups"));
            t.append(ttNote(won.map((s) => s.year).join(", ")));
            const names = [...new Set(won.map((s) => s.championName))].filter((nm) => nm !== f.name);
            if (names.length) t.append(ttNote(`Also as: ${names.join(", ")}`));
          });
        }
        card.append(row);
      });
      root.append(card);
    });
    const defunct = franchises.filter((f) => f.defunct && cupCount(f.id));
    document.getElementById("defunct-note").textContent = defunct.length
      ? `Plus ${defunct.map((f) => `${f.name}: ${cupCount(f.id)}`).join(", ")} (defunct).` : "";
  })();

  /* ---------- Most repeated Finals ---------- */

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
      countBox.append(el("small", null, "Finals"));
      const players = el("div", "players");
      [first, second].forEach((fid, i) => {
        const span = el("span");
        span.append(logo(fid), document.createTextNode(displayName(byId[fid].name)));
        players.append(span);
        if (i === 0) players.append(el("span", "vs", "vs"));
      });
      const h2h = el("div", "h2h", wa === wb ? `Tied ${wa}–${wb}` : `${byId[first].short} ${Math.max(wa, wb)}–${Math.min(wa, wb)}`);
      const meta = el("div", "meta", list.map((s) => `${s.year} ${shortName(s.championName, s.champion)} ${s.result}`).join(" · "));
      row.append(countBox, players, h2h, meta);
      root.append(row);
    });
  })();

  /* ---------- Most Finals lost ---------- */

  (function runnersUp() {
    const root = document.getElementById("runners-table");
    const lost = d3.groups(seasons, (s) => s.runnerUp)
      .map(([fid, list]) => ({ fid, list, won: cupCount(fid) }))
      .sort((a, b) => b.list.length - a.list.length || b.won - a.won);
    const t = el("table");
    const head = el("tr");
    [["Franchise"], ["Finals lost", "num", "Lost"], ["Finals played", "num", "Played"], ["Cups", "num"], ["Lost Finals", "years"]].forEach(([h, cls, short]) => {
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
      span.append(logo(fid), document.createTextNode(displayName(byId[fid].name)));
      name.append(span, el("div", "sub", years));
      tr.append(name, el("td", "num strong", String(list.length)), el("td", "num", String(list.length + won)), el("td", "num", String(won)), el("td", "years", years));
      t.append(tr);
    });
    root.replaceChildren(t);
  })();

  /* ---------- Series length ---------- */

  (function series() {
    Viz.legend("series-legend", [{ label: "Canadian champion", color: COUNTRY.CAN.color }, { label: "American champion", color: COUNTRY.USA.color }]);
    const sevens = seasons.filter((s) => s.year >= 1939);
    const NAMES = { "4–0": "Sweep (4–0)", "4–1": "In 5 (4–1)", "4–2": "In 6 (4–2)", "4–3": "Game 7 (4–3)" };
    const groups = Object.keys(NAMES).map((r) => ({ label: NAMES[r], short: r, list: sevens.filter((s) => s.result === r) }));
    stackedColumns({ chartId: "series-chart", groups, title: "Stanley Cup Finals by series length since 1939" });
    table("series-table", ["Result", "Total", "Canada", "United States", "Years"], groups.map((g) => [
      g.label, String(g.list.length), String(g.list.filter((s) => s.country === "CAN").length), String(g.list.filter((s) => s.country === "USA").length),
      g.list.map((s) => s.year).join(", "),
    ]));
  })();

  /* ---------- Conn Smythe leaders ---------- */

  (function mvp() {
    const root = document.getElementById("mvp-list");
    const withMvp = seasons.filter((s) => s.mvp);
    const groups = d3.sort(d3.groups(withMvp, (s) => s.mvp), (a, b) => b[1].length - a[1].length || a[1][0].year - b[1][0].year);
    const multi = groups.filter(([, list]) => list.length >= 2);
    multi.forEach(([name, list]) => {
      const row = el("div", "mvp-row");
      const tokens = el("div", "tokens");
      list.forEach((s) => {
        const team = s.mvpOnLoser ? s.runnerUp : s.champion;
        const token = el("span", "token");
        token.setAttribute("aria-label", `${s.year}, ${byId[team].name}`);
        token.append(logo(team));
        tooltipOnNode(token, (t) => finalTooltip(t, s));
        tokens.append(token);
      });
      row.append(el("span", "who", name), tokens, el("span", "n", String(list.length)));
      root.append(row);
    });
    const onLoser = withMvp.filter((s) => s.mvpOnLoser);
    root.after(el("p", "mvp-more", `${groups.length - multi.length} more players have won it once, for ${groups.length} winners in ${withMvp.length} playoffs. ${onLoser.length} went to a player from the losing team: ${onLoser.map((s) => `${s.mvp} (${s.year})`).join(", ")}.`));
  })();

  document.getElementById("sources").replaceChildren(...data.meta.sources.flatMap((u, i) => {
    const a = el("a", null, decodeURIComponent(u.split("/wiki/")[1]).replace(/_/g, " "));
    a.href = u;
    return i ? [document.createTextNode(", "), a] : [a];
  }));
  document.getElementById("data-through").textContent = `Covers every Final through ${latest.year}.`;
})();
