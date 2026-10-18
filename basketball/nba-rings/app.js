/* NBA Rings: every chart on the page, built with D3 v7. */
(async function () {
  "use strict";

  const { el, table, responsive, showTip, hideTip, tooltipOn, tooltipOnNode, ttTitle, ttNote, barPath, columnPath } = Viz;
  const data = await d3.json("data/nba-rings.json");

  const franchises = data.franchises;
  const byId = Object.fromEntries(franchises.map((f) => [f.id, f]));
  const seasons = data.seasons;
  const lastYear = seasons[seasons.length - 1].year;

  const CONF = {
    East: { label: "Eastern", color: "var(--east)" },
    West: { label: "Western", color: "var(--west)" },
  };
  const confColor = (conf) => (conf ? CONF[conf].color : "var(--defunct)");

  /* ---------- Logos ---------- */

  const LOGO_BASE = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba";
  const logoUrl = (code) => `${LOGO_BASE}/${Viz.isDark() ? "500-dark" : "500"}/${code}.png&h=96&w=96`;
  const badgeText = (f) => (f.id === "BLB" ? "BAL" : f.id);

  /** An <img> logo, or a lettered badge for teams without one (or if the image fails). */
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
    img.addEventListener("error", () => img.replaceWith(badge()), { once: true });
    return img;
  }

  /** Append a logo (or badge) to an SVG group, centered on (0,0). */
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
      .on("error", badge);
  }

  Viz.onThemeChange(() => {
    document.querySelectorAll("img[data-logo]").forEach((img) => (img.src = logoUrl(img.dataset.logo)));
    document.querySelectorAll("image[data-logo]").forEach((img) => img.setAttribute("href", logoUrl(img.dataset.logo)));
  });

  /** Short label for a historical name: "Minneapolis Lakers" -> "Lakers". */
  function shortName(name, fid) {
    const f = byId[fid];
    if (name.endsWith(f.short)) return f.short;
    return name.split(" ").slice(-1)[0];
  }

  function seasonTooltip(t, s) {
    t.append(ttTitle(`${s.year} NBA Finals`));
    t.append(Viz.ttRow(confColor(s.conference), s.result, `${s.championName} def. ${s.runnerUpName}`));
    t.append(ttNote(`Won from the ${s.year >= 1971 ? `${s.conference}ern Conference` : `${s.conference}ern Division`}`));
    if (s.mvp) {
      const listed = s.mvpListedAs ? ` (then ${s.mvpListedAs})` : "";
      t.append(ttNote(`Finals MVP: ${s.mvp}${listed}${s.mvpOnLoser ? ", from the losing team" : ""}`));
    }
  }

  const counts = d3.rollup(seasons, (v) => v.length, (s) => s.champion);
  const ringCount = (fid) => counts.get(fid) ?? 0;

  /* ---------- Stat tiles ---------- */

  (function stats() {
    const root = document.getElementById("stats");
    const [leader, leaderRings] = d3.greatest(counts, (d) => d[1]);

    // Longest run of consecutive titles.
    let best = { fid: null, len: 0, from: 0, to: 0 };
    let run = { fid: null, len: 0, from: 0 };
    seasons.forEach((s) => {
      run = s.champion === run.fid ? { ...run, len: run.len + 1 } : { fid: s.champion, len: 1, from: s.year };
      if (run.len > best.len) best = { ...run, to: s.year };
    });
    const latest = seasons[seasons.length - 1];

    const tiles = [
      { label: "Most rings", value: String(leaderRings), logo: leader, detail: byId[leader].name },
      { label: "Longest streak", value: String(best.len), logo: best.fid, detail: `${byId[best.fid].short}, ${best.from}–${best.to}` },
      {
        label: "Franchises with a ring",
        value: String(counts.size),
        detail: (() => {
          const defunct = [...counts.keys()].filter((fid) => byId[fid].defunct).length;
          const active = franchises.filter((f) => !f.defunct).length;
          return `${counts.size - defunct} of ${active} current teams${defunct ? ` + ${defunct} defunct` : ""}`;
        })(),
      },
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
    const years = [seasons[0].year - 1, ...seasons.map((s) => s.year)];

    // frames[i] = after the season years[i]: ranked [{fid, n, name}]
    const tally = new Map();
    const reached = new Map(); // fid -> year it reached its current count
    const lastName = new Map();
    const frames = years.map((year, i) => {
      const s = i > 0 ? seasons[i - 1] : null;
      if (s) {
        tally.set(s.champion, (tally.get(s.champion) ?? 0) + 1);
        reached.set(s.champion, s.year);
        lastName.set(s.champion, s.championName);
      }
      const ranked = [...tally.keys()]
        .map((fid) => ({ fid, n: tally.get(fid), since: reached.get(fid), name: lastName.get(fid) }))
        .sort((a, b) => b.n - a.n || a.since - b.since)
        .slice(0, TOP);
      return { year, season: s, ranked };
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
    const margin = { top: 24, right: 64, bottom: 8, left: 170 };
    const height = margin.top + rowH * TOP + margin.bottom;
    const svg = d3.select("#race-chart").append("svg").attr("role", "img");
    const grid = svg.append("g");
    const bars = svg.append("g");
    let width = 0;
    let narrow = false;
    const x = d3.scaleLinear();

    const frameDuration = () => 650 / +speedSel.value;
    const yPos = (i) => margin.top + i * rowH + (rowH - barH) / 2;

    function update(duration) {
      const frame = frames[state.idx];
      const maxN = d3.max(frame.ranked, (d) => d.n) ?? 0;
      x.domain([0, Math.max(5, maxN * 1.05)]).range([0, width - margin.left - margin.right]);
      const t = svg.transition().duration(duration).ease(d3.easeLinear);

      svg.attr("aria-label", `Most NBA titles after ${frame.year}: ` + frame.ranked.map((d) => `${byId[d.fid].name} ${d.n}`).join(", "));

      const ticks = x.ticks(narrow ? 4 : 6).filter(Number.isInteger);
      grid.selectAll("g.tick").data(ticks, (d) => d).join(
        (enter) => {
          const g = enter.append("g").attr("class", "tick").attr("opacity", 0)
            .attr("transform", (d) => `translate(${margin.left + x(d)},0)`);
          g.append("line").attr("class", (d) => (d === 0 ? "baseline" : "gridline")).attr("y1", margin.top - 6).attr("y2", height - margin.bottom);
          g.append("text").attr("class", "tick-label").attr("y", margin.top - 12).attr("text-anchor", "middle").text((d) => d);
          return g;
        },
        (update) => update,
        (exit) => exit.transition(t).attr("opacity", 0).remove()
      ).transition(t).attr("opacity", 1).attr("transform", (d) => `translate(${margin.left + x(d)},0)`);

      const rows = bars.selectAll("g.row").data(frame.ranked, (d) => d.fid).join(
        (enter) => {
          const g = enter.append("g").attr("class", "row").attr("opacity", 0)
            .attr("transform", `translate(${margin.left},${yPos(TOP)})`);
          g.append("path").attr("class", "mark").attr("fill", (d) => confColor(byId[d.fid].conference)).property("_w", 0);
          g.append("text").attr("class", "label-name").attr("x", -10).attr("y", barH / 2).attr("dy", "0.35em").attr("text-anchor", "end");
          g.append("g").attr("class", "logo-slot").each(function (d) {
            svgLogo(d3.select(this), d.fid, logoSize);
          }).attr("transform", `translate(${logoSize / 2 + 4},${barH / 2})`);
          g.append("text").attr("class", "label-value").attr("y", barH / 2).attr("dy", "0.35em").property("_v", 0);
          return g;
        },
        (update) => update,
        (exit) => exit.transition(t).attr("opacity", 0).attr("transform", `translate(${margin.left},${yPos(TOP)})`).remove()
      );

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

      dateEl.textContent = frame.year < seasons[0].year ? "1946" : String(frame.year);
      scrub.value = state.idx;
      renderTicker(frame.season);
    }

    function renderTicker(s) {
      tickerEl.replaceChildren();
      if (!s) {
        tickerEl.textContent = "Press play to start in 1947, the first BAA Finals.";
        return;
      }
      tickerEl.append(logo(s.champion), el("strong", null, `${s.year} · ${s.championName}`),
        document.createTextNode(` def. ${s.runnerUpName} ${s.result}${s.mvp ? ` · Finals MVP: ${s.mvp}` : ""}`));
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
      margin.left = narrow ? 92 : 170;
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

    const totals = d3.sort(counts, (d) => -d[1]);
    table("race-table", ["Franchise", "Rings", "Seasons won"], totals.map(([fid, n]) =>
      [byId[fid].name, String(n), seasons.filter((s) => s.champion === fid).map((s) => s.year).join(", ")]));
  })();

  /* ---------- East vs West ---------- */

  (function eastWest() {
    const east = seasons.filter((s) => s.conference === "East").length;
    const west = seasons.length - east;
    const era = seasons.filter((s) => s.year >= 1971);
    const eraEast = era.filter((s) => s.conference === "East").length;

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
    root.append(side("East", east), el("div", "mid", `${seasons.length} Finals`), side("West", west, true));

    const split = el("div", "split");
    [["East", east], ["West", west]].forEach(([conf, n]) => {
      const seg = el("div");
      seg.style.setProperty("--c", CONF[conf].color);
      seg.style.flex = String(n);
      split.append(seg);
    });
    root.after(split);
    split.after(el("p", "split-note",
      `Since the conferences were formed in 1971: East ${eraEast}, West ${era.length - eraEast}.`));

    Viz.legend("decade-legend", [
      { label: "Eastern", color: CONF.East.color },
      { label: "Western", color: CONF.West.color },
    ]);

    const decades = d3.groups(seasons, (s) => Math.floor(s.year / 10) * 10);
    stackedColumns({
      chartId: "decade-chart",
      groups: decades.map(([decade, list]) => ({ label: `${decade}s`, short: `'${String(decade).slice(2)}s`, list })),
      title: "NBA titles by decade, East vs West",
    });
    table("decade-table", ["Decade", "East", "West", "Champions"], decades.map(([decade, list]) => [
      `${decade}s`,
      String(list.filter((s) => s.conference === "East").length),
      String(list.filter((s) => s.conference === "West").length),
      list.map((s) => `${s.year} ${shortName(s.championName, s.champion)}`).join(", "),
    ]));
  })();

  /** Columns stacked East (bottom) / West (top), with a 2px surface gap between segments. */
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
        axis.append("text").attr("x", x(g.label) + x.bandwidth() / 2).attr("y", height - 8).attr("text-anchor", "middle")
          .text(short && g.short ? g.short : g.label);
      });

      const col = svg.selectAll("g.col").data(groups).join("g").attr("class", "col mark-group")
        .attr("transform", (g) => `translate(${x(g.label) + (x.bandwidth() - colW) / 2},0)`);
      col.append("rect").attr("x", -6).attr("y", margin.top).attr("width", colW + 12).attr("height", height - margin.top - margin.bottom).attr("fill", "transparent");
      col.each(function (g) {
        const e = g.list.filter((s) => s.conference === "East").length;
        const w = g.list.length - e;
        const sel = d3.select(this);
        const base = y(0);
        const eTop = y(e);
        const top = y(e + w);
        // East segment: square both ends when West sits on top of it.
        if (e > 0) {
          sel.append("path").attr("class", "mark").attr("fill", CONF.East.color)
            .attr("d", w > 0 ? `M0,${base}V${eTop}H${colW}V${base}Z` : columnPath(0, eTop, colW, base - eTop));
        }
        if (w > 0) {
          const segBase = e > 0 ? eTop - 2 : base;
          sel.append("path").attr("class", "mark").attr("fill", CONF.West.color).attr("d", columnPath(0, top, colW, segBase - top));
        }
        sel.append("text").attr("class", "label-value").attr("x", colW / 2).attr("y", top - 6).attr("text-anchor", "middle").text(g.list.length);
      });
      tooltipOn(col, (t, g) => {
        const e = g.list.filter((s) => s.conference === "East");
        const w = g.list.filter((s) => s.conference === "West");
        t.append(ttTitle(g.label));
        t.append(Viz.ttRow(CONF.East.color, e.length, "East"));
        t.append(Viz.ttRow(CONF.West.color, w.length, "West"));
        t.append(ttNote(g.list.map((s) => `${s.year} ${shortName(s.championName, s.champion)}`).join(", ")));
      });
    });
  }

  /* ---------- Champions wall ---------- */

  (function wall() {
    const root = document.getElementById("wall-grid");
    d3.groups(seasons, (s) => Math.floor(s.year / 10) * 10).forEach(([decade, list]) => {
      root.append(el("p", "decade", `${decade}s`));
      list.forEach((s) => {
        const tile = el("div", "tile");
        tile.setAttribute("role", "listitem");
        tile.setAttribute("aria-label", `${s.year}: ${s.championName} def. ${s.runnerUpName} ${s.result}`);
        tile.style.setProperty("--c", confColor(s.conference));
        tile.append(el("span", "year", String(s.year)), logo(s.champion), el("span", "team", shortName(s.championName, s.champion)));
        tooltipOnNode(tile, (t) => seasonTooltip(t, s));
        root.append(tile);
      });
    });
  })();

  /* ---------- Rings by franchise ---------- */

  (function byFranchise() {
    const root = document.getElementById("franchise-columns");
    const maxN = d3.max(counts.values());
    ["East", "West"].forEach((conf) => {
      const teams = franchises.filter((f) => f.conference === conf);
      const total = d3.sum(teams, (f) => ringCount(f.id));
      const card = el("div", "conf-card");
      const h = el("h3");
      const key = el("i");
      key.style.setProperty("--c", CONF[conf].color);
      h.append(key, document.createTextNode(`${CONF[conf].label} Conference`), el("span", null, `${total} rings`));
      card.append(h);

      const sorted = d3.sort(teams, (a, b) => ringCount(b.id) - ringCount(a.id) || d3.ascending(a.name, b.name));
      let zeroHeader = false;
      sorted.forEach((f) => {
        const n = ringCount(f.id);
        if (n === 0 && !zeroHeader) {
          card.append(el("p", "zero-head", "Still waiting"));
          zeroHeader = true;
        }
        const row = el("div", `franchise-row${n ? "" : " zero"}`);
        const bar = el("div", "bar");
        bar.style.setProperty("--c", CONF[conf].color);
        bar.style.width = `${(n / maxN) * 100}%`;
        const barWrap = el("div");
        barWrap.append(bar);
        row.append(logo(f.id), el("span", "name", f.name), barWrap, el("span", "n", n ? String(n) : "–"));
        if (n) {
          const won = seasons.filter((s) => s.champion === f.id);
          tooltipOnNode(row, (t) => {
            t.append(ttTitle(f.name), Viz.ttRow(CONF[conf].color, n, n === 1 ? "ring" : "rings"));
            t.append(ttNote(won.map((s) => s.year).join(", ")));
            const names = [...new Set(won.map((s) => s.championName))].filter((nm) => nm !== f.name);
            if (names.length) t.append(ttNote(`Also as: ${names.join(", ")}`));
          });
        }
        card.append(row);
      });
      root.append(card);
    });

    const defunct = franchises.filter((f) => f.defunct && ringCount(f.id));
    document.getElementById("defunct-note").textContent = defunct.length
      ? `Plus ${defunct.map((f) => `${f.name}: ${ringCount(f.id)}`).join(", ")} (defunct).`
      : "";
  })();

  /* ---------- Series length ---------- */

  (function seriesLength() {
    Viz.legend("series-legend", [
      { label: "Eastern winner", color: CONF.East.color },
      { label: "Western winner", color: CONF.West.color },
    ]);
    const RESULTS = ["4–0", "4–1", "4–2", "4–3"];
    const NAMES = { "4–0": "Sweep (4–0)", "4–1": "In 5 (4–1)", "4–2": "In 6 (4–2)", "4–3": "Game 7 (4–3)" };
    const groups = RESULTS.map((r) => ({ label: NAMES[r], short: r, list: seasons.filter((s) => s.result === r) }));
    stackedColumns({ chartId: "series-chart", groups, title: "NBA Finals by series length" });
    table("series-table", ["Result", "Total", "East", "West", "Seasons"], groups.map((g) => [
      g.label, String(g.list.length),
      String(g.list.filter((s) => s.conference === "East").length),
      String(g.list.filter((s) => s.conference === "West").length),
      g.list.map((s) => s.year).join(", "),
    ]));
  })();

  /* ---------- Finals MVP leaders ---------- */

  (function mvp() {
    const root = document.getElementById("mvp-list");
    const withMvp = seasons.filter((s) => s.mvp);
    const groups = d3.sort(d3.groups(withMvp, (s) => s.mvp), (a, b) => b[1].length - a[1].length || a[1][0].year - b[1][0].year);
    const multi = groups.filter(([, list]) => list.length >= 2);
    multi.forEach(([name, list]) => {
      const row = el("div", "mvp-row");
      const tokens = el("div", "tokens");
      list.forEach((s) => {
        // The MVP's team: the champion, except when the award went to the losing side.
        const team = s.mvpOnLoser ? s.runnerUp : s.champion;
        const teamName = s.mvpOnLoser ? s.runnerUpName : s.championName;
        const token = el("span", "token");
        token.setAttribute("aria-label", `${s.year}, ${teamName}`);
        token.append(logo(team));
        tooltipOnNode(token, (t) => seasonTooltip(t, s));
        tokens.append(token);
      });
      row.append(el("span", "who", name), tokens, el("span", "n", String(list.length)));
      root.append(row);
    });
    const singles = groups.length - multi.length;
    root.after(el("p", "mvp-more", `${singles} more players have won the award once, for ${groups.length} winners in ${withMvp.length} Finals.`));
  })();

  document.getElementById("data-through").textContent = `Covers every Finals through ${lastYear}.`;
})();
