/* Shared charts for the football competition pages (Copa Libertadores, Champions League). */
(async function () {
  "use strict";

  const { el, table, responsive, tooltipOn, tooltipOnNode, ttTitle, ttNote, barPath } = Viz;
  const data = await d3.json(document.body.dataset.src);
  const { clubs, countries, finals } = data;

  // West German clubs count for Germany in country totals (as on UEFA's own tables).
  const MERGE = { FRG: "GER" };
  const nation = (code) => MERGE[code] ?? code;
  const countryName = (code) => countries[code]?.name ?? code;
  const clubName = (id) => clubs[id]?.name ?? id;
  const fit = (text, narrow, max = 15) => (narrow && text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text);
  const NOTE = { penalties: "pens", "extra time": "a.e.t.", playoff: "playoff", replay: "replay" };
  const scoreText = (f) => f.legs.map((l) => l.score + (l.note ? ` ${NOTE[l.note] ?? l.note}` : "")).join(", ");

  /* ---------- Crests and flags ---------- */

  const CREST = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/soccer";
  const crestUrl = (id, dark = Viz.isDark()) => `${CREST}/${dark ? "500-dark" : "500"}/${id}.png&h=80&w=80`;
  const initials = (name) => name.replace(/[^A-Za-zÀ-ÿ ]/g, "").split(" ").filter(Boolean).slice(0, 3).map((w) => w[0]).join("").toUpperCase();

  function crest(id, cls = "crest") {
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
    img.addEventListener("error", function onError() {
      // Fall back to the light crest, then to a lettered badge.
      if (img.src !== crestUrl(club.crest, false)) img.src = crestUrl(club.crest, false);
      else img.replaceWith(badge());
    });
    return img;
  }

  function svgCrest(g, id, size) {
    const club = clubs[id];
    g.selectAll("*").remove();
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
    img.src = `https://flagcdn.com/${iso}.svg`;
    img.alt = countryName(code);
    img.title = countryName(code);
    img.loading = "lazy";
    img.addEventListener("error", () => img.replaceWith(fallback()), { once: true });
    return img;
  }

  function svgFlag(g, code) {
    const iso = countries[code]?.flag;
    g.append("rect").attr("width", 20).attr("height", 15).attr("rx", 2).attr("fill", "var(--wash)").attr("stroke", "var(--border)");
    if (iso) g.append("image").attr("href", `https://flagcdn.com/${iso}.svg`).attr("width", 20).attr("height", 15).attr("preserveAspectRatio", "xMidYMid slice");
  }

  /** Crest + club name (+ optional flag) in one inline element. */
  function clubLabel(id, withFlag = false) {
    const span = el("span", "club");
    if (withFlag) span.append(flag(clubs[id]?.country));
    span.append(crest(id), document.createTextNode(clubName(id)));
    return span;
  }

  /* ---------- Country colors (top three title-winning nations, the rest gray) ---------- */

  const nationTitles = d3.rollups(finals, (v) => ({ n: v.length, first: v[0].year }), (f) => nation(f.championCountry))
    .sort((a, b) => b[1].n - a[1].n || a[1].first - b[1].first);
  const COLOR_SLOTS = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];
  const nationColor = new Map(nationTitles.slice(0, 3).map(([code], i) => [code, COLOR_SLOTS[i]]));
  const colorOf = (code) => nationColor.get(nation(code)) ?? "var(--ink-muted)";
  const raceLegend = [
    ...nationTitles.slice(0, 3).map(([code]) => ({ label: countryName(code), color: nationColor.get(code) })),
    { label: "Other countries", color: "var(--ink-muted)" },
  ];

  /* ---------- Stat tiles ---------- */

  (function stats() {
    const titles = d3.rollup(finals, (v) => v.length, (f) => f.champion);
    const [leader, n] = d3.greatest(titles, (d) => d[1]);
    const nations = new Set(finals.map((f) => nation(f.championCountry)));
    const tiles = [
      { label: "Finals played", value: String(finals.length), detail: `${finals[0].season} to ${finals[finals.length - 1].season}` },
      { label: "Different champions", value: String(titles.size), detail: `${d3.sum(titles.values(), (v) => v === 1)} won it once` },
      { label: "Most titles", value: String(n), detail: clubName(leader), club: leader },
      {
        label: "Champion countries",
        value: String(nations.size),
        detail: (() => {
          const top = nationTitles.filter(([, v]) => v.n === nationTitles[0][1].n).map(([code]) => countryName(code));
          return top.length > 1 ? `${top.join(" and ")} tied on ${nationTitles[0][1].n}` : `${top[0]} leads with ${nationTitles[0][1].n}`;
        })(),
      },
    ];
    const root = document.getElementById("stats");
    tiles.forEach((t) => {
      const box = el("div", "stat");
      const value = el("div", "value");
      if (t.club) value.append(crest(t.club, "crest crest-lg"));
      value.append(document.createTextNode(t.value));
      box.append(el("span", "label", t.label), value, el("span", "detail", t.detail));
      root.append(box);
    });
  })();

  /* ---------- Bar chart race ---------- */

  (function race() {
    const TOP = 10;
    Viz.legend("race-legend", raceLegend);
    const tally = new Map();
    const reached = new Map();
    const frames = [{ final: null, ranked: [] }];
    finals.forEach((f, i) => {
      tally.set(f.champion, (tally.get(f.champion) ?? 0) + 1);
      reached.set(f.champion, i);
      const ranked = [...tally.entries()]
        .map(([id, n]) => ({ id, n, since: reached.get(id) }))
        .sort((a, b) => b.n - a.n || a.since - b.since)
        .slice(0, TOP);
      frames.push({ final: f, ranked });
    });

    const state = { idx: Viz.reduceMotion ? frames.length - 1 : 0, playing: false, timer: null };
    const dateEl = document.getElementById("race-date");
    const tickerEl = document.getElementById("race-ticker");
    const playBtn = document.getElementById("race-play");
    const scrub = document.getElementById("race-scrub");
    const speedSel = document.getElementById("race-speed");
    scrub.max = frames.length - 1;

    const rowH = 38;
    const barH = 24;
    const crestSize = 28;
    const margin = { top: 24, right: 64, bottom: 8, left: 200 };
    const height = margin.top + rowH * TOP + margin.bottom;
    const svg = d3.select("#race-chart").append("svg").attr("role", "img");
    const grid = svg.append("g");
    const bars = svg.append("g");
    let width = 0;
    let narrow = false;
    const x = d3.scaleLinear();
    const frameDuration = () => 600 / +speedSel.value;
    const yPos = (i) => margin.top + i * rowH + (rowH - barH) / 2;

    function update(duration) {
      const frame = frames[state.idx];
      const maxN = d3.max(frame.ranked, (d) => d.n) ?? 0;
      x.domain([0, Math.max(4, maxN * 1.05)]).range([0, width - margin.left - margin.right]);
      const t = svg.transition().duration(duration).ease(d3.easeLinear);
      svg.attr("aria-label", `Most titles after ${frame.final ? frame.final.season : "the first final"}: ` +
        frame.ranked.map((d) => `${clubName(d.id)} ${d.n}`).join(", "));

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
          g.append("path").attr("class", "mark").attr("fill", (d) => colorOf(clubs[d.id]?.country)).property("_w", 0);
          g.append("text").attr("class", "label-name").attr("x", -34).attr("y", barH / 2).attr("dy", "0.35em").attr("text-anchor", "end");
          g.append("g").attr("transform", `translate(-28,${(barH - 15) / 2})`).each(function (d) { svgFlag(d3.select(this), clubs[d.id]?.country); });
          g.append("g").attr("class", "crest-slot").each(function (d) { svgCrest(d3.select(this), d.id, crestSize); })
            .attr("transform", `translate(${crestSize / 2 + 4},${barH / 2})`);
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
      rows.select("text.label-value").transition(t).attr("x", (d) => x(d.n) + crestSize + 10)
        .tween("text", function (d) {
          const i = d3.interpolateRound(this._v, d.n);
          return (k) => (this.textContent = this._v = i(k));
        });

      const f = frame.final;
      dateEl.textContent = f ? f.season : String(finals[0].year);
      scrub.value = state.idx;
      tickerEl.replaceChildren();
      if (!f) {
        tickerEl.textContent = `Press play to start with the first final, ${finals[0].season}.`;
      } else {
        tickerEl.append(crest(f.champion), el("strong", null, `${f.season} · ${clubName(f.champion)}`),
          document.createTextNode(` def. ${clubName(f.runnerUp)}, ${scoreText(f)}`));
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
      io.observe(document.getElementById("race-chart"));
    }
  })();

  /* ---------- Generic HTML table with crest/flag cells ---------- */

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
      const tr = el("tr");
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

  /* ---------- Champions and runners-up ---------- */

  (function championsTable() {
    const root = document.getElementById("champions-table");
    const byClub = () => {
      const ids = new Set(finals.flatMap((f) => [f.champion, f.runnerUp]));
      const rows = [...ids].map((id) => ({
        id,
        won: finals.filter((f) => f.champion === id),
        lost: finals.filter((f) => f.runnerUp === id),
      })).sort((a, b) => b.won.length - a.won.length || b.lost.length - a.lost.length || d3.ascending(clubName(a.id), clubName(b.id)));
      const seasons = (list) => list.map((f) => f.season).join(", ") || "–";
      richTable(root, [
        { label: "Club", render: (r) => withSub(clubLabel(r.id, true), `Won: ${seasons(r.won)} · Lost: ${seasons(r.lost)}`) },
        { label: "Titles", cls: "num strong", render: (r) => String(r.won.length) },
        { label: "Runners-up", short: "R-up", cls: "num", render: (r) => String(r.lost.length) },
        { label: "Finals", cls: "num", render: (r) => String(r.won.length + r.lost.length) },
        { label: "Seasons won", cls: "years", render: (r) => seasons(r.won) },
        { label: "Seasons runner-up", cls: "years", render: (r) => seasons(r.lost) },
      ], rows);
    };
    const everyFinal = () => {
      richTable(root, [
        { label: "Season", render: (f) => f.season },
        { label: "Champion", render: (f) => clubLabel(f.champion, true) },
        { label: "Score", cls: "score", render: (f) => scoreText(f) },
        { label: "Runner-up", render: (f) => clubLabel(f.runnerUp, true) },
      ], finals.slice().reverse());
    };
    Viz.segmented("champions-tabs", [{ key: "club", label: "By club" }, { key: "final", label: "Every final" }], "club",
      (k) => (k === "club" ? byClub() : everyFinal()));
    byClub();
  })();

  /* ---------- Most repeated finals ---------- */

  (function repeatedFinals() {
    const root = document.getElementById("pairs-list");
    const pairs = d3.groups(finals, (f) => [f.champion, f.runnerUp].sort().join("|"))
      .filter(([, list]) => list.length >= 2)
      .sort((a, b) => b[1].length - a[1].length || b[1][b[1].length - 1].year - a[1][a[1].length - 1].year)
      .slice(0, 12);
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
      const meta = el("div", "meta", list.map((f) => `${f.season} ${clubName(f.champion)} (${scoreText(f)})`).join(" · "));
      row.append(count, players, h2h, meta);
      root.append(row);
    });
  })();

  /* ---------- Countries ---------- */

  (function countriesSection() {
    const codes = new Set(finals.flatMap((f) => [nation(f.championCountry), nation(f.runnerUpCountry)]));
    const rows = [...codes].map((code) => {
      const won = finals.filter((f) => nation(f.championCountry) === code);
      const lost = finals.filter((f) => nation(f.runnerUpCountry) === code);
      return { code, won, lost, winners: d3.groups(won, (f) => f.champion).sort((a, b) => b[1].length - a[1].length) };
    }).sort((a, b) => b.won.length - a.won.length || b.lost.length - a.lost.length);

    const withTitles = rows.filter((r) => r.won.length).length;
    document.getElementById("country-note").textContent =
      `${withTitles} countries have produced a champion and ${rows.length} have reached a final.` +
      (finals.some((f) => f.championCountry === "FRG" || f.runnerUpCountry === "FRG") ? " West Germany is counted with Germany." : "");

    const maxN = d3.max(rows, (r) => Math.max(r.won.length, r.lost.length)) || 1;
    const root = document.getElementById("countries-list");
    const head = el("div", "country-head");
    head.append(el("span"), el("span", null, "Country"), el("span", null, "Titles"), el("span", "num", "Titles"),
      el("span", null, "Runners-up"), el("span", "num", "R-up"), el("span", "num", "Clubs"));
    root.append(head);
    rows.forEach((r) => {
      const row = el("div", "country-row");
      const bar = (n, cls) => {
        const wrap = el("div", "bar-wrap");
        const b = el("div", `bar ${cls}`);
        b.style.width = `${(n / maxN) * 100}%`;
        wrap.append(b);
        return wrap;
      };
      row.append(flag(r.code), el("span", "name", countryName(r.code)), bar(r.won.length, "won"), el("span", "num strong", String(r.won.length)),
        bar(r.lost.length, "lost"), el("span", "num", String(r.lost.length)), el("span", "num", String(r.winners.length)));
      tooltipOnNode(row, (t) => {
        t.append(ttTitle(`${countryName(r.code)}: ${r.won.length} titles, ${r.lost.length} runners-up`));
        r.winners.forEach(([id, list]) => t.append(Viz.ttRow("var(--ink-2)", list.length, clubName(id))));
        if (!r.winners.length) t.append(ttNote("No titles yet"));
      });
      root.append(row);
    });
  })();

  /* ---------- All-time club records ---------- */

  (function clubRecords() {
    const METRICS = [
      { key: "w", label: "Most wins", unit: "wins" },
      { key: "gf", label: "Most goals", unit: "goals" },
      { key: "part", label: "Most participations", unit: "seasons" },
    ];
    let metric = "w";
    const top = () => data.alltime.slice().sort((a, b) => b[metric] - a[metric]).slice(0, 15);
    const container = d3.select("#records-chart");

    function draw(width) {
      const m = METRICS.find((d) => d.key === metric);
      const list = top();
      container.selectAll("*").remove();
      const narrow = width < 560;
      const rowH = 34;
      const barH = 18;
      const margin = { top: 4, right: 64, bottom: 4, left: narrow ? 150 : 210 };
      const height = margin.top + list.length * rowH + margin.bottom;
      const x = d3.scaleLinear().domain([0, d3.max(list, (r) => r[metric])]).range([0, width - margin.left - margin.right]);
      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", `${m.label}, all time`);
      svg.append("line").attr("class", "baseline").attr("x1", margin.left).attr("x2", margin.left).attr("y1", 0).attr("y2", height);
      const g = svg.selectAll("g.row").data(list).join("g").attr("class", "row mark-group")
        .attr("transform", (d, i) => `translate(${margin.left},${margin.top + i * rowH})`);
      g.append("rect").attr("x", -margin.left).attr("width", width).attr("height", rowH).attr("fill", "transparent");
      g.append("text").attr("class", "label-name").attr("x", -56).attr("y", rowH / 2).attr("dy", "0.35em").attr("text-anchor", "end").text((d) => fit(clubName(d.club), narrow));
      g.append("g").attr("transform", `translate(-50,${(rowH - 15) / 2})`).each(function (d) { svgFlag(d3.select(this), d.country); });
      g.append("g").attr("transform", `translate(-14,${rowH / 2})`).each(function (d) { svgCrest(d3.select(this), d.club, 22); });
      g.append("path").attr("class", "mark").attr("fill", "var(--ink-2)").attr("d", (d) => barPath(0, (rowH - barH) / 2, x(d[metric]), barH));
      g.append("text").attr("class", "label-value").attr("x", (d) => x(d[metric]) + 8).attr("y", rowH / 2).attr("dy", "0.35em").text((d) => d[metric]);
      tooltipOn(g, (t, d) => {
        t.append(ttTitle(clubName(d.club)));
        t.append(Viz.ttRow("var(--ink-2)", d[metric], m.unit));
        t.append(ttNote(`${d.part} seasons · ${d.pld} played · ${d.w}W ${d.d}D ${d.l}L · goals ${d.gf}–${d.ga}`));
      });
    }

    function renderTable() {
      table("records-table", ["Club", "Country", "Seasons", "Played", "W", "D", "L", "GF", "GA"],
        top().map((r) => [clubName(r.club), countryName(r.country), String(r.part), String(r.pld), String(r.w), String(r.d), String(r.l), String(r.gf), String(r.ga)]));
    }

    const rerender = responsive("records-chart", draw);
    renderTable();
    Viz.segmented("records-tabs", METRICS, metric, (k) => {
      metric = k;
      rerender();
      renderTable();
    });
  })();

  /* ---------- Players ---------- */

  (function players() {
    const root = document.getElementById("players-table");
    const playerCell = (p) => {
      const span = el("span", "club");
      span.append(flag(p.nation), document.createTextNode(p.player));
      return withSub(span, p.clubs.join(", "));
    };
    const views = {
      scorers: () => richTable(root, [
        { label: "#", cls: "num rank", render: (p) => String(p.rank) },
        { label: "Player", render: playerCell },
        { label: "Goals", cls: "num strong", render: (p) => String(p.goals) },
        { label: "Apps", cls: "num", render: (p) => (p.apps != null ? String(p.apps) : "–") },
        { label: "Goals per game", short: "Ratio", cls: "num", render: (p) => (p.apps ? (p.goals / p.apps).toFixed(2) : "–") },
        { label: "Clubs", cls: "years", render: (p) => p.clubs.join(", ") },
      ], ranked(data.scorers, "goals").slice(0, 25)),
      appearances: () => richTable(root, [
        { label: "#", cls: "num rank", render: (p) => String(p.rank) },
        { label: "Player", render: playerCell },
        { label: "Appearances", short: "Apps", cls: "num strong", render: (p) => String(p.apps) },
        { label: "Years", cls: "num", render: (p) => p.years ?? "–" },
        { label: "Clubs", cls: "years", render: (p) => p.clubs.join(", ") },
      ], ranked(data.appearances, "apps").slice(0, 25)),
    };
    function ranked(list, key) {
      const sorted = list.slice().sort((a, b) => b[key] - a[key]);
      return sorted.map((p, i) => ({ ...p, rank: i > 0 && sorted[i - 1][key] === p[key] ? null : i + 1 }))
        .map((p, i, arr) => ({ ...p, rank: p.rank ?? arr.slice(0, i).reverse().find((q) => q.rank)?.rank }));
    }
    Viz.segmented("players-tabs", [{ key: "scorers", label: "Top scorers" }, { key: "appearances", label: "Most appearances" }], "scorers",
      (k) => views[k]());
    views.scorers();
  })();

  document.getElementById("data-through").textContent = `Covers every final through ${data.meta.through}.`;
})();
