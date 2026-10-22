/* Super Bowl: every chart on the page, built with D3 v7. */
(async function () {
  "use strict";

  const { el, table, responsive, tooltipOn, tooltipOnNode, ttTitle, ttNote, barPath, columnPath } = Viz;
  const data = await d3.json(document.body.dataset.src);

  const franchises = data.franchises;
  const byId = Object.fromEntries(franchises.map((f) => [f.id, f]));
  const games = data.games;
  const league = data.leagueTitles;
  const lastGame = games[games.length - 1];

  const CONF = {
    AFC: { label: "AFC", long: "American Football Conference", early: "AFL", color: "var(--afc)" },
    NFC: { label: "NFC", long: "National Football Conference", early: "NFL", color: "var(--nfc)" },
  };
  const confColor = (conf) => (conf ? CONF[conf].color : "var(--defunct)");
  const teamConf = (fid) => byId[fid]?.conference ?? null;

  /* ---------- Logos ---------- */

  const LOGO_BASE = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/nfl";
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
      // A missing dark variant falls back to the light logo, then to a badge.
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
    g.append("image")
      .attr("data-logo", f.logo)
      .attr("href", logoUrl(f.logo))
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

  /** Short label for a historical name: "Baltimore Colts" -> "Colts". */
  function shortName(name, fid) {
    const f = byId[fid];
    if (f && name.endsWith(f.short)) return f.short;
    return name.split(" ").slice(-1)[0];
  }
  const score = (g) => `${g.winPts}–${g.losePts}`;
  const confWord = (g) => (g.year <= 1970 ? `${CONF[g.conference].early} champion` : `${g.conference} champion`);

  function gameTooltip(t, g) {
    t.append(ttTitle(`Super Bowl ${g.number} · ${g.year}`));
    t.append(Viz.ttRow(confColor(g.conference), score(g), `${g.championName} def. ${g.runnerUpName}`));
    t.append(ttNote(`${confWord(g)} · ${g.venue}, ${g.city}`));
    if (g.mvp.length) t.append(ttNote(`MVP: ${g.mvp.join(" and ")}${g.mvpOnLoser ? ", from the losing team" : ""}`));
  }

  const sbCount = d3.rollup(games, (v) => v.length, (g) => g.champion);
  const leagueCount = d3.rollup(league, (v) => v.length, (r) => r.champion);

  /* ---------- Stat tiles ---------- */

  (function stats() {
    const root = document.getElementById("stats");
    const max = d3.max(sbCount.values());
    const leaders = [...sbCount].filter(([, n]) => n === max).map(([fid]) => fid);
    const [lgLeader, lgN] = d3.greatest(leagueCount, (d) => d[1]);
    let best = { fid: null, len: 0 };
    let run = { fid: null, len: 0 };
    games.forEach((g) => {
      run = g.champion === run.fid ? { ...run, len: run.len + 1 } : { fid: g.champion, len: 1, from: g.year };
      if (run.len > best.len) best = { ...run, to: g.year };
    });
    const afc = games.filter((g) => g.conference === "AFC").length;
    const tiles = [
      { label: "Most Super Bowls", value: String(max), logo: leaders[0], detail: leaders.map((f) => byId[f].short).join(" and ") },
      { label: "Most NFL titles", value: String(lgN), logo: lgLeader, detail: `${byId[lgLeader].name}, since 1920` },
      { label: "AFC vs NFC", value: `${afc}–${games.length - afc}`, detail: `in ${games.length} Super Bowls` },
      { label: `Super Bowl ${lastGame.number}`, value: byId[lastGame.champion].short, logo: lastGame.champion, detail: `${score(lastGame)} vs ${lastGame.runnerUpName}` },
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

  const RACE = {
    sb: {
      label: "Super Bowls",
      items: games.map((g) => ({ year: g.year, champion: g.champion, name: g.championName, title: `Super Bowl ${g.number} · ${g.year}`, text: ` def. ${g.runnerUpName} ${score(g)}${g.mvp.length ? ` · MVP: ${g.mvp.join(" and ")}` : ""}` })),
      start: "Press play to start with Super Bowl I, January 1967.",
    },
    league: {
      label: "All NFL titles",
      items: league.map((r) => ({ year: r.season, champion: r.champion, name: r.championName, title: `${r.season} season`, text: ` · ${r.via}${r.runnerUpName ? ` vs ${r.runnerUpName}` : ""}` })),
      start: "Press play to start with the 1920 season.",
    },
  };

  (function race() {
    const TOP = 10;
    let frames = [];
    let mode = "sb";
    function buildFrames() {
      const items = RACE[mode].items;
      const tally = new Map();
      const reached = new Map();
      const lastName = new Map();
      frames = [null, ...items].map((s, i) => {
        if (s) {
          tally.set(s.champion, (tally.get(s.champion) ?? 0) + 1);
          reached.set(s.champion, i);
          lastName.set(s.champion, s.name);
        }
        const ranked = [...tally.keys()]
          .map((fid) => ({ fid, n: tally.get(fid), since: reached.get(fid), name: lastName.get(fid) }))
          .sort((a, b) => b.n - a.n || a.since - b.since)
          .slice(0, TOP);
        return { year: s ? s.year : items[0].year - 1, item: s, ranked };
      });
    }
    buildFrames();

    const state = { idx: Viz.reduceMotion ? frames.length - 1 : 0, playing: false, timer: null };
    const dateEl = document.getElementById("race-date");
    const tickerEl = document.getElementById("race-ticker");
    const playBtn = document.getElementById("race-play");
    const scrub = document.getElementById("race-scrub");
    const speedSel = document.getElementById("race-speed");
    scrub.max = frames.length - 1;

    Viz.legend("race-legend", [
      { label: "AFC", color: CONF.AFC.color },
      { label: "NFC", color: CONF.NFC.color },
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
    const frameDuration = () => (mode === "league" ? 420 : 650) / +speedSel.value;
    const yPos = (i) => margin.top + i * rowH + (rowH - barH) / 2;

    function update(duration) {
      const frame = frames[state.idx];
      const maxN = d3.max(frame.ranked, (d) => d.n) ?? 0;
      x.domain([0, Math.max(5, maxN * 1.05)]).range([0, width - margin.left - margin.right]);
      const t = svg.transition().duration(duration).ease(d3.easeLinear);
      svg.attr("aria-label", `Most ${RACE[mode].label} after ${frame.year}: ` + frame.ranked.map((d) => `${byId[d.fid].name} ${d.n}`).join(", "));

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
          g.append("path").attr("class", "mark").attr("fill", (d) => confColor(teamConf(d.fid))).property("_w", 0);
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
      rows.select("text.label-name").text((d) => (narrow ? shortName(d.name, d.fid) : byId[d.fid].defunct ? d.name : byId[d.fid].name));
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
      const s = frame.item;
      if (!s) tickerEl.textContent = RACE[mode].start;
      else tickerEl.append(logo(s.champion), el("strong", null, `${s.title} · ${s.name}`), document.createTextNode(s.text));
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

    function tableView() {
      const counts = mode === "sb" ? sbCount : leagueCount;
      const items = RACE[mode].items;
      table("race-table", ["Franchise", mode === "sb" ? "Super Bowls" : "Titles", "Years won"], d3.sort(counts, (d) => -d[1]).map(([fid, n]) =>
        [byId[fid].name, String(n), items.filter((s) => s.champion === fid).map((s) => s.year).join(", ")]));
    }
    Viz.segmented("race-mode", Object.entries(RACE).map(([key, r]) => ({ key, label: r.label })), mode, (k) => {
      pause();
      mode = k;
      buildFrames();
      scrub.max = frames.length - 1;
      bars.selectAll("*").remove();
      state.idx = frames.length - 1;
      update(0);
      pause();
      tableView();
    });
    tableView();

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
  })();

  /* ---------- Stacked columns (AFC bottom / NFC top) ---------- */

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
      groups.forEach((g) => {
        axis.append("text").attr("x", x(g.label) + x.bandwidth() / 2).attr("y", height - 8).attr("text-anchor", "middle").text(short && g.short ? g.short : g.label);
      });
      const col = svg.selectAll("g.col").data(groups).join("g").attr("class", "col mark-group")
        .attr("transform", (g) => `translate(${x(g.label) + (x.bandwidth() - colW) / 2},0)`);
      col.append("rect").attr("x", -6).attr("y", margin.top).attr("width", colW + 12).attr("height", height - margin.top - margin.bottom).attr("fill", "transparent");
      col.each(function (g) {
        const a = g.list.filter((s) => s.conference === "AFC").length;
        const n = g.list.length - a;
        const sel = d3.select(this);
        const base = y(0);
        const aTop = y(a);
        const top = y(a + n);
        if (a > 0) sel.append("path").attr("class", "mark").attr("fill", CONF.AFC.color).attr("d", n > 0 ? `M0,${base}V${aTop}H${colW}V${base}Z` : columnPath(0, aTop, colW, base - aTop));
        if (n > 0) sel.append("path").attr("class", "mark").attr("fill", CONF.NFC.color).attr("d", columnPath(0, top, colW, (a > 0 ? aTop - 2 : base) - top));
        sel.append("text").attr("class", "label-value").attr("x", colW / 2).attr("y", top - 6).attr("text-anchor", "middle").text(g.list.length);
      });
      tooltipOn(col, (t, g) => {
        t.append(ttTitle(g.label));
        t.append(Viz.ttRow(CONF.AFC.color, g.list.filter((s) => s.conference === "AFC").length, "AFC"));
        t.append(Viz.ttRow(CONF.NFC.color, g.list.filter((s) => s.conference === "NFC").length, "NFC"));
        t.append(ttNote(g.list.map((s) => `${s.year} ${shortName(s.championName, s.champion)}`).join(", ")));
      });
    });
  }

  /* ---------- AFC vs NFC ---------- */

  (function conferences() {
    const afc = games.filter((g) => g.conference === "AFC").length;
    const nfc = games.length - afc;
    const root = document.getElementById("versus");
    const side = (conf, n, right) => {
      const box = el("div", `side${right ? " right" : ""}`);
      const name = el("div", "name");
      const key = el("i");
      key.style.setProperty("--c", CONF[conf].color);
      if (right) name.append(document.createTextNode(CONF[conf].label), key);
      else name.append(key, document.createTextNode(CONF[conf].label));
      box.append(name, el("div", "big", String(n)));
      return box;
    };
    root.append(side("AFC", afc), el("div", "mid", `${games.length} Super Bowls`), side("NFC", nfc, true));
    const split = el("div", "split");
    [["AFC", afc], ["NFC", nfc]].forEach(([conf, n]) => {
      const seg = el("div");
      seg.style.setProperty("--c", CONF[conf].color);
      seg.style.flex = String(n);
      split.append(seg);
    });
    root.after(split);
    const merged = games.filter((g) => g.year > 1970);
    const mAfc = merged.filter((g) => g.conference === "AFC").length;
    split.after(el("p", "split-note", `AFL vs NFL before the merger (Super Bowls I–IV): ${afc - mAfc}–${nfc - (merged.length - mAfc)}. Since the 1970 merger: AFC ${mAfc}, NFC ${merged.length - mAfc}.`));

    Viz.legend("decade-legend", [{ label: "AFC", color: CONF.AFC.color }, { label: "NFC", color: CONF.NFC.color }]);
    const decades = d3.groups(games, (g) => Math.floor(g.year / 10) * 10);
    stackedColumns({ chartId: "decade-chart", groups: decades.map(([d, list]) => ({ label: `${d}s`, short: `'${String(d).slice(2)}s`, list })), title: "Super Bowls by decade, AFC vs NFC" });
    table("decade-table", ["Decade", "AFC", "NFC", "Champions"], decades.map(([d, list]) => [
      `${d}s`, String(list.filter((g) => g.conference === "AFC").length), String(list.filter((g) => g.conference === "NFC").length),
      list.map((g) => `${g.year} ${shortName(g.championName, g.champion)}`).join(", "),
    ]));
  })();

  /* ---------- Champions wall ---------- */

  (function wall() {
    const root = document.getElementById("wall-grid");
    d3.groups(games, (g) => Math.floor(g.year / 10) * 10).forEach(([decade, list]) => {
      root.append(el("p", "decade", `${decade}s`));
      list.forEach((g) => {
        const tile = el("div", "tile");
        tile.setAttribute("role", "listitem");
        tile.setAttribute("aria-label", `Super Bowl ${g.number}, ${g.year}: ${g.championName} def. ${g.runnerUpName} ${score(g)}`);
        tile.style.setProperty("--c", confColor(g.conference));
        tile.append(el("span", "year", `${g.number} · ${g.year}`), logo(g.champion), el("span", "team", shortName(g.championName, g.champion)));
        tooltipOnNode(tile, (t) => gameTooltip(t, g));
        root.append(tile);
      });
    });
  })();

  /* ---------- Titles by franchise ---------- */

  (function byFranchise() {
    const root = document.getElementById("franchise-columns");
    const note = document.getElementById("defunct-note");
    function render(mode) {
      root.replaceChildren();
      const counts = mode === "sb" ? sbCount : leagueCount;
      const items = mode === "sb" ? games.map((g) => ({ year: g.year, champion: g.champion, name: g.championName })) : league.map((r) => ({ year: r.season, champion: r.champion, name: r.championName }));
      const n = (fid) => counts.get(fid) ?? 0;
      const maxN = d3.max(counts.values());
      ["AFC", "NFC"].forEach((conf) => {
        const teams = franchises.filter((f) => f.conference === conf);
        const card = el("div", "conf-card");
        const h = el("h3");
        const key = el("i");
        key.style.setProperty("--c", CONF[conf].color);
        h.append(key, document.createTextNode(CONF[conf].long), el("span", null, `${d3.sum(teams, (f) => n(f.id))} ${mode === "sb" ? "Super Bowls" : "titles"}`));
        card.append(h);
        let zeroHeader = false;
        d3.sort(teams, (a, b) => n(b.id) - n(a.id) || d3.ascending(a.name, b.name)).forEach((f) => {
          const k = n(f.id);
          if (k === 0 && !zeroHeader) {
            card.append(el("p", "zero-head", "Still waiting"));
            zeroHeader = true;
          }
          const row = el("div", `franchise-row${k ? "" : " zero"}`);
          const bar = el("div", "bar");
          bar.style.setProperty("--c", CONF[conf].color);
          bar.style.width = `${(k / maxN) * 100}%`;
          const wrap = el("div");
          wrap.append(bar);
          const label = el("span", "name", f.name);
          if (mode === "league") {
            const pre = league.filter((r) => r.champion === f.id && r.season < 1970).length;
            if (pre) label.append(el("span", "pre", `${pre} pre-1970`));
          }
          row.append(logo(f.id), label, wrap, el("span", "n", k ? String(k) : "–"));
          if (k) {
            const won = items.filter((s) => s.champion === f.id);
            tooltipOnNode(row, (t) => {
              t.append(ttTitle(f.name), Viz.ttRow(CONF[conf].color, k, mode === "sb" ? (k === 1 ? "Super Bowl" : "Super Bowls") : (k === 1 ? "NFL title" : "NFL titles")));
              t.append(ttNote(won.map((s) => s.year).join(", ")));
              const names = [...new Set(won.map((s) => s.name))].filter((nm) => nm !== f.name);
              if (names.length) t.append(ttNote(`Also as: ${names.join(", ")}`));
            });
          }
          card.append(row);
        });
        root.append(card);
      });
      const defunct = franchises.filter((f) => f.defunct && n(f.id));
      note.textContent = defunct.length ? `Plus ${defunct.map((f) => `${f.name}: ${n(f.id)}`).join(", ")} (defunct).` : "";
    }
    Viz.segmented("franchise-mode", [{ key: "sb", label: "Super Bowls" }, { key: "league", label: "All NFL titles" }], "sb", render);
    render("sb");
  })();

  /* ---------- Most repeated Super Bowls ---------- */

  (function repeated() {
    const root = document.getElementById("pairs-list");
    const pairs = d3.groups(games, (g) => [g.champion, g.runnerUp].sort().join("|"))
      .filter(([, list]) => list.length >= 2)
      .sort((a, b) => b[1].length - a[1].length || b[1][b[1].length - 1].year - a[1][a[1].length - 1].year);
    pairs.forEach(([key, list]) => {
      const [a, b] = key.split("|");
      const wa = list.filter((g) => g.champion === a).length;
      const wb = list.length - wa;
      const [first, second] = wa >= wb ? [a, b] : [b, a];
      const row = el("div", "pair-row");
      const countBox = el("div", "count", String(list.length));
      countBox.append(el("small", null, "Super Bowls"));
      const players = el("div", "players");
      [first, second].forEach((fid, i) => {
        const span = el("span");
        span.append(logo(fid), document.createTextNode(byId[fid].name));
        players.append(span);
        if (i === 0) players.append(el("span", "vs", "vs"));
      });
      const h2h = el("div", "h2h", wa === wb ? `Tied ${wa}–${wb}` : `${byId[first].short} ${Math.max(wa, wb)}–${Math.min(wa, wb)}`);
      const meta = el("div", "meta", list.map((g) => `${g.number} (${g.year}) ${shortName(g.championName, g.champion)} ${score(g)}`).join(" · "));
      row.append(countBox, players, h2h, meta);
      root.append(row);
    });
  })();

  /* ---------- Most Super Bowls lost ---------- */

  (function runnersUp() {
    const root = document.getElementById("runners-table");
    const lost = d3.groups(games, (g) => g.runnerUp)
      .map(([fid, list]) => ({ fid, list, won: sbCount.get(fid) ?? 0 }))
      .sort((a, b) => b.list.length - a.list.length || b.won - a.won);
    const t = el("table");
    const head = el("tr");
    [["Franchise"], ["Super Bowls lost", "num", "Lost"], ["Super Bowls played", "num", "Played"], ["Won", "num"], ["Defeats", "years"]].forEach(([h, cls, short]) => {
      const th = el("th", cls);
      th.append(el("span", short ? "long" : null, h));
      if (short) th.append(el("span", "short", short));
      head.append(th);
    });
    t.append(head);
    lost.forEach(({ fid, list, won }) => {
      const tr = el("tr");
      const years = list.map((g) => `${g.year} (${shortName(g.championName, g.champion)})`).join(", ");
      const name = el("td");
      const span = el("span", "who");
      span.append(logo(fid), document.createTextNode(byId[fid].name));
      name.append(span, el("div", "sub", years));
      tr.append(name, el("td", "num strong", String(list.length)), el("td", "num", String(list.length + won)), el("td", "num", String(won)), el("td", "years", years));
      t.append(tr);
    });
    root.replaceChildren(t);
  })();

  /* ---------- Margins of victory ---------- */

  (function margins() {
    Viz.legend("margin-legend", [{ label: "AFC winner", color: CONF.AFC.color }, { label: "NFC winner", color: CONF.NFC.color }]);
    const BUCKETS = [[1, 3, "1–3 points", "1–3"], [4, 7, "4–7 points", "4–7"], [8, 14, "8–14 points", "8–14"], [15, 24, "15–24 points", "15–24"], [25, 99, "25 or more", "25+"]];
    const margin = (g) => g.winPts - g.losePts;
    stackedColumns({
      chartId: "margin-chart",
      groups: BUCKETS.map(([a, b, label, short]) => ({ label, short, list: games.filter((g) => margin(g) >= a && margin(g) <= b) })),
      title: "Super Bowls by winning margin",
    });
    const cols = [
      { label: "Game", render: (g) => `${g.number} · ${g.year}` },
      { label: "Winner", render: (g) => { const s = el("span", "who"); s.append(logo(g.champion), document.createTextNode(shortName(g.championName, g.champion))); return s; } },
      { label: "Score", cls: "num strong", render: (g) => score(g) },
      { label: "Loser", cls: "hide-sm", render: (g) => shortName(g.runnerUpName, g.runnerUp) },
    ];
    const render = (id, rows) => {
      const t = el("table");
      const head = el("tr");
      cols.forEach((c) => head.append(el("th", c.cls, c.label)));
      t.append(head);
      rows.forEach((g) => {
        const tr = el("tr");
        cols.forEach((c) => {
          const td = el("td", c.cls);
          const v = c.render(g);
          td.append(typeof v === "string" ? document.createTextNode(v) : v);
          tr.append(td);
        });
        tooltipOnNode(tr, (tt) => gameTooltip(tt, g));
        t.append(tr);
      });
      document.getElementById(id).replaceChildren(t);
    };
    render("blowout-table", d3.sort(games, (a, b) => margin(b) - margin(a) || b.winPts - a.winPts).slice(0, 8));
    render("closest-table", d3.sort(games, (a, b) => margin(a) - margin(b) || a.year - b.year).slice(0, 8));
  })();

  /* ---------- Super Bowl MVP leaders ---------- */

  (function mvp() {
    const root = document.getElementById("mvp-list");
    const awards = games.flatMap((g) => g.mvp.map((name) => ({ name, g })));
    const groups = d3.sort(d3.groups(awards, (a) => a.name), (a, b) => b[1].length - a[1].length || a[1][0].g.year - b[1][0].g.year);
    const multi = groups.filter(([, list]) => list.length >= 2);
    multi.forEach(([name, list]) => {
      const row = el("div", "mvp-row");
      const tokens = el("div", "tokens");
      list.forEach(({ g }) => {
        const team = g.mvpOnLoser ? g.runnerUp : g.champion;
        const token = el("span", "token");
        token.setAttribute("aria-label", `Super Bowl ${g.number}, ${byId[team].name}`);
        token.append(logo(team));
        tooltipOnNode(token, (t) => gameTooltip(t, g));
        tokens.append(token);
      });
      row.append(el("span", "who", name), tokens, el("span", "n", String(list.length)));
      root.append(row);
    });
    root.after(el("p", "mvp-more", `${groups.length - multi.length} more players have won the award once, for ${groups.length} winners in ${games.length} Super Bowls (Super Bowl XII had co-MVPs).`));
  })();

  /* ---------- Host cities ---------- */

  (function hosts() {
    const root = document.getElementById("host-list");
    const cities = d3.sort(d3.groups(games, (g) => g.city), (a, b) => b[1].length - a[1].length || a[1][0].year - b[1][0].year);
    const max = cities[0][1].length;
    root.replaceChildren();
    cities.forEach(([city, list]) => {
      const row = el("div", "franchise-row");
      const bar = el("div", "bar");
      bar.style.setProperty("--c", "var(--sport)");
      bar.style.width = `${(list.length / max) * 100}%`;
      const wrap = el("div");
      wrap.append(bar);
      const label = el("span", "name", city);
      label.append(el("span", "pre", [...new Set(list.map((g) => g.venue))].join(", ")));
      row.append(el("span"), label, wrap, el("span", "n", String(list.length)));
      tooltipOnNode(row, (t) => {
        t.append(ttTitle(city));
        list.forEach((g) => t.append(Viz.ttRow(confColor(g.conference), `${g.number}`, `${g.year} · ${g.venue} · ${shortName(g.championName, g.champion)} ${score(g)}`)));
      });
      root.append(row);
    });
  })();

  document.getElementById("sources").replaceChildren(...data.meta.sources.flatMap((u, i) => {
    const a = el("a", null, decodeURIComponent(u.split("/wiki/")[1]).replace(/_/g, " "));
    a.href = u;
    return i ? [document.createTextNode(", "), a] : [a];
  }));
  document.getElementById("data-through").textContent = `Covers every Super Bowl through Super Bowl ${lastGame.number} (${lastGame.year}).`;
})();
