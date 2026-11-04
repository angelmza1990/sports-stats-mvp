/* NBA, NFL and NHL rivalries: the head to head season by season, regular season and playoffs, and (where every game
   has its score) the biggest wins. One front end; each page names its data file in <body data-src> and the data says
   what its league calls the Finals, whether playoffs are series or single games, and whether games can end level. */
(async function () {
  "use strict";

  const { el, responsive, ttTitle, ttNote, ttRow } = Viz;
  const all = await d3.json(document.body.dataset.src);
  const { franchises, league } = all;
  const byId = new Map(all.rivalries.map((r) => [r.id, r]));
  const COLOR = { a: "var(--team-a)", b: "var(--team-b)", d: "var(--draw)" };
  const LOGO_BASE = `https://a.espncdn.com/combiner/i?img=/i/teamlogos/${league.logo}`;
  const logoUrl = (code) => `${LOGO_BASE}/${Viz.isDark() ? "500-dark" : "500"}/${code}.png&h=96&w=96`;
  const FINAL = new RegExp(league.finalRe);
  const singleGames = league.playoffUnit === "game";

  let data, A, B;

  /* ---------- Helpers ---------- */

  const short = (id) => franchises[id]?.short ?? id;
  const name = (id) => franchises[id]?.name ?? id;
  const color = (id) => (id === A ? COLOR.a : id === B ? COLOR.b : COLOR.d);
  const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
  const isFinal = (s) => FINAL.test(s.round);
  const seriesOnly = (list) => list.filter((s) => !s.roundRobin);
  // "169–135" or, with ties, "96–109–6".
  const rec = (a, b, t = 0) => (t ? `${a}–${b}–${t}` : `${a}–${b}`);
  const leadText = (a, b, t = 0) => (a === b ? `Tied ${rec(a, b, t)}` : a > b ? `${short(A)} lead ${rec(a, b, t)}` : `${short(B)} lead ${rec(b, a, t)}`);
  const totals = (r) => [r.regular[0] + r.playoffs[0], r.regular[1] + r.playoffs[1], (r.regular[2] ?? 0) + (r.playoffs[2] ?? 0)];
  const firstSeason = (r) => String(Math.min(r.seasons[0]?.year ?? 9999, r.series[0]?.year ?? 9999));

  /** An <img> logo, or a lettered badge if the image fails. */
  function logo(fid, cls = "logo") {
    const f = franchises[fid];
    const badge = () => {
      const b = el("span", `badge ${cls === "logo" ? "" : cls}`, fid);
      b.setAttribute("aria-hidden", "true");
      return b;
    };
    if (!f?.logo) return badge();
    const img = el("img", cls);
    img.alt = "";
    img.loading = "lazy";
    img.decoding = "async";
    img.dataset.logo = f.logo;
    img.src = logoUrl(f.logo);
    img.addEventListener("error", () => img.replaceWith(badge()), { once: true });
    return img;
  }

  Viz.onThemeChange(() => {
    document.querySelectorAll("img[data-logo]").forEach((img) => (img.src = logoUrl(img.dataset.logo)));
    if (data) {
      applyColors();
      render();
    }
  });

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

  function dot(c) {
    const i = el("i", "team-dot");
    i.style.setProperty("--c", c);
    return i;
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
    columns.forEach((c) => {
      const th = el("th", c.cls);
      th.append(c.label);
      head.append(th);
    });
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
    return t;
  }

  const teamHead = (id) => {
    const s = el("span", "who");
    s.append(dot(color(id)), document.createTextNode(short(id)));
    return s;
  };
  const who = (id) => {
    const s = el("span", "who");
    if (!id) {
      s.append(document.createTextNode("Tie"));
      return s;
    }
    s.append(logo(id, "logo logo-sm"), document.createTextNode(short(id)));
    return s;
  };
  // A series result with the winner's games first; a single game's score with the winner's points first.
  const seriesText = (s) => {
    if (s.score) return `${Math.max(...s.score)}–${Math.min(...s.score)}${s.ot ? " OT" : ""}`;
    const [w, l] = s.a >= s.b ? [s.a, s.b] : [s.b, s.a];
    return `${rec(w, l, s.ties ?? 0)}${s.onGoals ? ` (goals ${Math.max(...s.onGoals)}–${Math.min(...s.onGoals)})` : ""}`;
  };

  /* ---------- The season list, with the running head to head ---------- */

  function timelineRows() {
    const years = [...new Set([...data.seasons.map((s) => s.year), ...data.series.map((s) => s.year)])].sort((p, q) => p - q);
    let ra = 0, rb = 0, rt = 0;
    return years.map((y) => {
      const season = data.seasons.find((s) => s.year === y);
      const series = data.series.filter((s) => s.year === y);
      ra += (season?.a ?? 0) + d3.sum(series, (s) => s.a);
      rb += (season?.b ?? 0) + d3.sum(series, (s) => s.b);
      rt += (season?.t ?? 0) + d3.sum(series, (s) => s.ties ?? 0);
      const label = season?.season ?? series[0].season;
      return { year: y, label, season, series, ra, rb, rt, diff: ra - rb };
    });
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
      r.teams.forEach((t) => crests.append(logo(t)));
      const [a, bb, t] = totals(r.record);
      const lead = a === bb ? `Tied ${rec(a, bb, t)}` : `${franchises[a > bb ? r.teams[0] : r.teams[1]].short} lead ${rec(Math.max(a, bb), Math.min(a, bb), t)}`;
      b.append(crests, el("strong", null, r.name), el("small", null, `${lead} · since ${firstSeason(r)}`));
      b.addEventListener("click", () => select(r.id));
      grid.append(b);
    });
    root.append(grid);
  }

  function applyColors() {
    const c = Viz.isDark() ? data.colors.dark : data.colors.light;
    document.body.style.setProperty("--team-a", c[0]);
    document.body.style.setProperty("--team-b", c[1]);
  }

  function select(id) {
    data = byId.get(id);
    [A, B] = data.teams;
    document.body.dataset.rivalry = id;
    applyColors();
    picker(id);
    try {
      history.replaceState(null, "", `#${id}`);
    } catch (e) {}
    render();
  }

  /* ---------- Summary ---------- */

  function versus() {
    const r = data.record;
    const [a, b, t] = totals(r);
    const head = document.getElementById("rv-versus");
    head.replaceChildren();
    const side = (id, wins, right) => {
      const s = el("div", `rv-side${right ? " right" : ""}`);
      const txt = el("div");
      txt.append(el("div", "rv-name", name(id)), el("div", "rv-wins", String(wins)), el("div", "rv-label", wins === 1 ? "win" : "wins"));
      s.append(logo(id, "logo rv-logo"), txt);
      return s;
    };
    const mid = el("div", "rv-mid");
    if (t) mid.append(el("div", "rv-draws", String(t)), el("div", "rv-label", t === 1 ? "tie" : "ties"));
    else mid.append(el("div", "rv-draws", String(a + b)), el("div", "rv-label", "games"));
    head.append(side(A, a), mid, side(B, b, true));
    head.setAttribute("aria-label", `${name(A)} ${a} wins, ${name(B)} ${b} wins${t ? `, ${t} ties` : ""}, in ${a + b + t} games`);
    split(document.getElementById("rv-split"), [{ n: a, color: COLOR.a }, { n: t, color: COLOR.d }, { n: b, color: COLOR.b }]);
    const detail = document.getElementById("rv-detail");
    detail.replaceChildren();
    const part = (strong, text) => {
      const s = el("span");
      s.append(el("strong", null, strong), document.createTextNode(` ${text}`));
      return s;
    };
    detail.append(part(rec(...r.regular), "in the regular season"), part(rec(...r.playoffs), "in the playoffs"));
  }

  function stats() {
    const root = document.getElementById("stats");
    root.replaceChildren();
    const r = data.record;
    const series = seriesOnly(data.series);
    const finals = series.filter(isFinal);
    const fa = finals.filter((s) => s.winner === A).length;
    const last = series[series.length - 1];
    const tile = (label, value, detail, club) => {
      const box = el("div", "stat");
      const v = el("div", "value");
      if (club) v.append(logo(club, "logo stat-logo"));
      v.append(document.createTextNode(value));
      box.append(el("span", "label", label), v, el("span", "detail", detail));
      root.append(box);
    };
    tile("Regular season", rec(...r.regular), `${short(A)}–${short(B)} in ${plural(data.seasons.length, "season")}`);
    if (singleGames) {
      tile("Playoff games", rec(...r.playoffs), series.length ? `${short(A)}–${short(B)} in ${plural(series.length, "game")}` : "never met in the playoffs");
    } else {
      tile("Playoff games", rec(...r.playoffs), `${short(A)}–${short(B)}`);
      tile("Playoff series", rec(r.series[0], r.series[1]), series.length ? `${short(A)}–${short(B)} in ${plural(series.length, "series", "series")}` : "never met in the playoffs");
    }
    if (finals.length) tile(league.final, String(finals.length), `${short(A)} won ${fa}, ${short(B)} ${finals.length - fa}`);
    else if (last) tile(singleGames ? "Latest playoff game" : "Latest series", seriesText(last), `${last.winner ? short(last.winner) : "Tie"} · ${last.round}, ${last.season}`, last.winner);
    const games = data.games ?? [];
    if (games.length && (singleGames || finals.length || !last)) {
      const big = d3.greatest(games, (g) => Math.abs(g.hs - g.as));
      const w = big.hs > big.as ? big.home : big.away;
      tile("Biggest win", `${Math.max(big.hs, big.as)}–${Math.min(big.hs, big.as)}`, `${short(w)} · ${big.date ? fmtDate(big.date) : big.season}${big.playoff ? " · playoffs" : ""}`, w);
    }
  }

  const fmtDate = (d) => new Date(`${d}T00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

  /* ---------- The lead over time ---------- */

  function timeline() {
    const pts = timelineRows();
    const maxA = d3.greatest(pts, (p) => p.diff);
    const maxB = d3.least(pts, (p) => p.diff);
    let changes = 0, sign = 0;
    pts.forEach((p) => {
      const s = Math.sign(p.diff);
      if (s && sign && s !== sign) changes++;
      if (s) sign = s;
    });
    const now = pts[pts.length - 1].diff;
    const lead = (v) => (v > 0 ? `${short(A)} +${v}` : v < 0 ? `${short(B)} +${-v}` : "level");
    document.getElementById("timeline-note").textContent =
      `${short(A)} led by as many as ${Math.max(0, maxA.diff)}${maxA.diff > 0 ? ` (${maxA.label})` : ""}; ` +
      `${short(B)} by as many as ${Math.max(0, -maxB.diff)}${maxB.diff < 0 ? ` (${maxB.label})` : ""}. ` +
      `The lead has changed hands ${plural(changes, "time")}. Today: ${lead(now)}.`;
    Viz.legend("timeline-legend", [
      { label: `${short(A)} ahead`, color: COLOR.a },
      { label: `${short(B)} ahead`, color: COLOR.b },
    ]);

    const node = freshChart("timeline-chart");
    responsive(node, (width) => {
      const container = d3.select(node);
      container.selectAll("*").remove();
      const narrow = width < 560;
      const margin = { top: 20, right: 14, bottom: 26, left: narrow ? 36 : 44 };
      const height = narrow ? 260 : 340;
      const x = d3.scaleLinear().domain([pts[0].year, pts[pts.length - 1].year + 1]).range([margin.left, width - margin.right]);
      const ext = Math.max(4, d3.max(pts, (p) => Math.abs(p.diff)));
      const y = d3.scaleLinear().domain([-ext, ext]).nice().range([height - margin.bottom, margin.top]);
      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img")
        .attr("aria-label", `Head-to-head lead after each of ${pts.length} seasons. Today: ${lead(now)}.`);

      const axis = svg.append("g").attr("class", "axis");
      y.ticks(narrow ? 5 : 7).forEach((v) => {
        axis.append("line").attr("class", v === 0 ? "baseline" : "gridline").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", y(v)).attr("y2", y(v));
        axis.append("text").attr("x", margin.left - 6).attr("y", y(v)).attr("dy", "0.32em").attr("text-anchor", "end").text(v > 0 ? `+${v}` : v < 0 ? `+${-v}` : "0");
      });
      x.ticks(narrow ? 5 : 10).filter((t) => Number.isInteger(t)).forEach((t) => {
        axis.append("text").attr("x", x(t)).attr("y", height - 6).attr("text-anchor", "middle").text(t);
      });
      axis.append("text").attr("class", "label-muted").attr("x", margin.left + 6).attr("y", margin.top - 6).text(`↑ ${short(A)} ahead`);
      axis.append("text").attr("class", "label-muted").attr("x", margin.left + 6).attr("y", height - margin.bottom - 6).text(`↓ ${short(B)} ahead`);

      // A step per season, held until the next one.
      const step = [{ year: pts[0].year, diff: 0 }, ...pts.map((p) => ({ year: p.year + 1, diff: p.diff, p }))];
      const area = (f) => d3.area().curve(d3.curveStepBefore).x((p) => x(p.year)).y0(y(0)).y1((p) => y(f(p.diff)));
      svg.append("path").attr("d", area((v) => Math.max(0, v))(step)).attr("fill", COLOR.a).attr("fill-opacity", 0.28);
      svg.append("path").attr("d", area((v) => Math.min(0, v))(step)).attr("fill", COLOR.b).attr("fill-opacity", 0.28);
      svg.append("path").attr("d", d3.line().curve(d3.curveStepBefore).x((p) => x(p.year)).y((p) => y(p.diff))(step))
        .attr("fill", "none").attr("stroke", "var(--ink-2)").attr("stroke-width", 2).attr("stroke-linejoin", "round");

      const mark = (p, c, label, anchor) => {
        const cx = x(p.year + 1);
        svg.append("circle").attr("cx", cx).attr("cy", y(p.diff)).attr("r", 4.5).attr("fill", c).attr("stroke", "var(--surface)").attr("stroke-width", 2);
        if (label) svg.append("text").attr("class", "label-value").attr("x", cx + (anchor === "end" ? -8 : 8)).attr("y", y(p.diff) + (p.diff >= 0 ? -8 : 16))
          .attr("text-anchor", anchor).text(label);
      };
      const anchorAt = (p) => (x(p.year) > width * 0.7 ? "end" : "start");
      if (maxA.diff > 0) mark(maxA, COLOR.a, `+${maxA.diff}`, anchorAt(maxA));
      if (maxB.diff < 0) mark(maxB, COLOR.b, `+${-maxB.diff}`, anchorAt(maxB));
      const end = pts[pts.length - 1];
      if (end !== maxA && end !== maxB) mark(end, now > 0 ? COLOR.a : now < 0 ? COLOR.b : COLOR.d, "", "end");

      const cross = svg.append("g").attr("pointer-events", "none").style("display", "none");
      cross.append("line").attr("class", "gridline").attr("y1", margin.top).attr("y2", height - margin.bottom).attr("stroke", "var(--ink-muted)");
      const cdot = cross.append("circle").attr("r", 5).attr("stroke", "var(--surface)").attr("stroke-width", 2);
      const show = (event, p) => {
        cross.style("display", null).attr("transform", `translate(${x(p.year + 1)},0)`);
        cdot.attr("cy", y(p.diff)).attr("fill", p.diff > 0 ? COLOR.a : p.diff < 0 ? COLOR.b : COLOR.d);
        Viz.showTip(event, (t) => seasonTip(t, p, lead));
      };
      const overlay = svg.append("rect").attr("class", "hit").attr("x", margin.left).attr("y", margin.top)
        .attr("width", width - margin.left - margin.right).attr("height", height - margin.top - margin.bottom).attr("fill", "transparent")
        .attr("tabindex", 0).attr("aria-label", "Explore the seasons; use the left and right arrow keys");
      let idx = pts.length - 1;
      const bisect = d3.bisector((p) => p.year + 0.5).center;
      overlay.on("pointermove pointerenter", (event) => {
        const [px] = d3.pointer(event);
        idx = Math.max(0, Math.min(pts.length - 1, bisect(pts, x.invert(px) - 0.5)));
        show(event, pts[idx]);
      }).on("pointerleave blur", () => {
        cross.style("display", "none");
        Viz.hideTip();
      }).on("focus", (event) => show(event, pts[idx])).on("keydown", (event) => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        idx = Math.max(0, Math.min(pts.length - 1, idx + (event.key === "ArrowRight" ? 1 : -1)));
        show(event, pts[idx]);
      });
    });
  }

  function seasonTip(t, p, lead) {
    t.append(ttTitle(`${p.label} season`));
    if (p.season) {
      const s = p.season;
      t.append(ttRow(s.a > s.b ? COLOR.a : s.b > s.a ? COLOR.b : COLOR.d, rec(s.a, s.b, s.t ?? 0), ` regular season, ${short(A)}–${short(B)}`));
    } else {
      t.append(ttNote("No regular-season meetings"));
    }
    p.series.forEach((s) => {
      t.append(ttRow(color(s.winner), seriesText(s), ` ${s.winner ? short(s.winner) : "Tie"} · ${s.round}${s.roundRobin ? " games" : ""}`));
    });
    if (lead) t.append(ttNote(`After it: ${leadText(p.ra, p.rb, p.rt)} (${lead(p.diff)})`));
  }

  /* ---------- Every season ---------- */

  function seasonsChart() {
    const pts = timelineRows();
    Viz.legend("seasons-legend", [
      { label: `${short(A)} wins`, color: COLOR.a },
      { label: `${short(B)} wins`, color: COLOR.b },
    ]);
    const node = freshChart("seasons-chart");
    responsive(node, (width) => {
      const container = d3.select(node);
      container.selectAll("*").remove();
      const narrow = width < 560;
      const margin = { top: 30, right: 10, bottom: 24, left: 30 };
      const height = narrow ? 240 : 300;
      const years = d3.range(pts[0].year, pts[pts.length - 1].year + 1);
      const x = d3.scaleBand().domain(years).range([margin.left, width - margin.right]).paddingInner(years.length > 60 ? 0.12 : 0.2);
      const ext = d3.max(data.seasons, (s) => Math.max(s.a, s.b)) || 1;
      const mid = margin.top + (height - margin.top - margin.bottom) / 2;
      const y = d3.scaleLinear().domain([0, ext]).range([0, (height - margin.top - margin.bottom) / 2 - 1]);
      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img")
        .attr("aria-label", `Regular-season wins of ${short(A)} and ${short(B)} in each of ${data.seasons.length} seasons, with every playoff meeting marked.`);
      const axis = svg.append("g").attr("class", "axis");
      y.ticks(Math.min(3, ext)).filter((v) => v > 0 && Number.isInteger(v)).forEach((v) => {
        [mid - y(v), mid + y(v)].forEach((yy) => axis.append("line").attr("class", "gridline").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", yy).attr("y2", yy));
        axis.append("text").attr("x", margin.left - 6).attr("y", mid - y(v)).attr("dy", "0.32em").attr("text-anchor", "end").text(v);
        axis.append("text").attr("x", margin.left - 6).attr("y", mid + y(v)).attr("dy", "0.32em").attr("text-anchor", "end").text(v);
      });
      axis.append("line").attr("class", "baseline").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", mid).attr("y2", mid);
      const decade = narrow || years.length > 90 ? 20 : 10;
      years.filter((yy) => yy % decade === 0).forEach((yy) => {
        axis.append("text").attr("x", x(yy) + x.bandwidth() / 2).attr("y", height - 6).attr("text-anchor", "middle").text(yy);
      });
      const bw = x.bandwidth();
      const r = Math.min(4, bw / 2);
      data.seasons.forEach((s) => {
        // Bars grow from the baseline, with the rounded end away from it; the 1px gap keeps the two sides apart.
        if (s.a) svg.append("path").attr("d", roundedBar(x(s.year), mid - 1 - y(s.a), bw, y(s.a), r, "top")).attr("fill", COLOR.a);
        if (s.b) svg.append("path").attr("d", roundedBar(x(s.year), mid + 1, bw, y(s.b), r, "bottom")).attr("fill", COLOR.b);
      });
      // Playoff meetings: a dot per series or game above the season, in the winner's color; the Finals get a ring.
      pts.forEach((p) => {
        p.series.forEach((s, i) => {
          const cx = x(p.year) + bw / 2, cy = margin.top - 12 - i * 9;
          const rr = Math.max(3, Math.min(4.5, bw / 2));
          if (isFinal(s)) svg.append("circle").attr("cx", cx).attr("cy", cy).attr("r", rr + 2.5).attr("fill", "none").attr("stroke", color(s.winner)).attr("stroke-width", 1.5);
          svg.append("circle").attr("cx", cx).attr("cy", cy).attr("r", rr).attr("fill", color(s.winner)).attr("stroke", "var(--surface)").attr("stroke-width", 1);
        });
      });
      pts.forEach((p) => {
        const hit = svg.append("rect").attr("class", "hit").attr("x", x(p.year) - (x.step() - bw) / 2).attr("y", 0)
          .attr("width", x.step()).attr("height", height - margin.bottom).attr("fill", "transparent");
        hit.on("pointerenter pointermove", (event) => Viz.showTip(event, (t) => seasonTip(t, p))).on("pointerleave", () => Viz.hideTip());
      });
    });

    const ties = league.ties && data.seasons.some((s) => s.t);
    const cols = [
      { label: "Season", render: (p) => p.label },
      { label: teamHead(A), cls: "num", render: (p) => (p.season ? String(p.season.a) : "–") },
      { label: teamHead(B), cls: "num", render: (p) => (p.season ? String(p.season.b) : "–") },
    ];
    if (ties) cols.push({ label: "Ties", cls: "num", render: (p) => (p.season?.t ? String(p.season.t) : "–") });
    cols.push(
      { label: "Playoffs", render: (p) => p.series.map((s) => `${s.winner ? short(s.winner) : "Tie"} ${seriesText(s)} (${s.round})`).join("; ") },
      { label: "Head to head", cls: "num", render: (p) => rec(p.ra, p.rb, p.rt) },
    );
    table("seasons-table", cols, [...pts].reverse());
  }

  function roundedBar(x0, y0, w, h, r, end) {
    const rr = Math.min(r, h, w / 2);
    if (h <= 0) return "";
    if (end === "top") {
      return `M${x0},${y0 + h}V${y0 + rr}Q${x0},${y0} ${x0 + rr},${y0}H${x0 + w - rr}Q${x0 + w},${y0} ${x0 + w},${y0 + rr}V${y0 + h}Z`;
    }
    return `M${x0},${y0}V${y0 + h - rr}Q${x0},${y0 + h} ${x0 + rr},${y0 + h}H${x0 + w - rr}Q${x0 + w},${y0 + h} ${x0 + w},${y0 + h - rr}V${y0}Z`;
  }

  /* ---------- Playoff meetings ---------- */

  function seriesTable() {
    const series = [...data.series].reverse();
    const lede = document.getElementById("playoffs-lede");
    if (!series.length) {
      lede.textContent = "They have never met in the playoffs.";
      document.getElementById("series-table").replaceChildren();
      return;
    }
    const n = seriesOnly(data.series).length;
    const finals = seriesOnly(data.series).filter(isFinal).length;
    const unit = singleGames ? "game" : "series";
    const many = singleGames ? "games" : "series";
    const inFinals = !finals ? "" : finals === n ? (n > 1 ? `, all of them in the ${league.final}` : `, in the ${league.final}`) : `, ${finals} of them in the ${league.final}`;
    lede.textContent = `${plural(n, unit, many)}${inFinals}, most recent first${singleGames ? ", with the score" : ", with the games each side won"}.`;
    table("series-table", [
      { label: "Season", render: (s) => s.season },
      { label: "Round", render: (s) => (s.roundRobin ? `${s.round} (games)` : s.round) },
      { label: "Winner", render: (s) => who(s.winner) },
      { label: singleGames ? "Score" : "Games", cls: "num", render: (s) => seriesText(s) },
    ], series.map((s) => ({ ...s, _cls: isFinal(s) ? "final-row" : null })));
  }

  /* ---------- Biggest wins (leagues with every game's score) ---------- */

  function biggest() {
    const section = document.getElementById("biggest");
    if (!section) return;
    const games = data.games ?? [];
    section.hidden = !games.length;
    if (!games.length) return;
    const winner = (g) => (g.hs > g.as ? g.home : g.as > g.hs ? g.away : null);
    const side = (id) => games.filter((g) => winner(g) === id).sort((p, q) => Math.abs(q.hs - q.as) - Math.abs(p.hs - p.as) || (q.hs + q.as) - (p.hs + p.as)).slice(0, 5);
    const rows = [...side(A).map((g) => ({ ...g, _team: A })), ...side(B).map((g) => ({ ...g, _team: B }))];
    const score = (g) => `${short(g.home)} ${g.hs}–${g.as} ${short(g.away)}${g.end ? ` (${g.end})` : ""}`;
    table("biggest-table", [
      { label: "Winner", render: (g) => who(g._team) },
      { label: "Score", render: (g) => score(g) },
      { label: "Margin", cls: "num strong", render: (g) => `+${Math.abs(g.hs - g.as)}` },
      { label: "When", cls: "num", render: (g) => `${g.date ? fmtDate(g.date) : g.season}${g.playoff ? " · playoffs" : ""}` },
    ], rows);
    const most = d3.greatest(games, (g) => g.hs + g.as);
    const ot = games.filter((g) => g.end).length;
    document.getElementById("biggest-note").textContent =
      `Most ${league.key === "nfl" ? "points" : "goals"} in a game: ${most.hs + most.as}, ${score(most)} (${most.date ? fmtDate(most.date) : most.season}).` +
      (ot ? ` ${plural(ot, "game")} went to overtime${league.key === "nhl" ? " or a shootout" : ""}.` : "");
  }

  /* ---------- Home and away ---------- */

  function venues() {
    const sum = (list, key) => [0, 1, 2].map((i) => d3.sum(list, (s) => s[key]?.[i] ?? 0));
    const rows = [["Regular season", data.seasons], ["Playoffs", data.series]].map(([label, list]) => ({
      label, atA: sum(list, "home-a"), atB: sum(list, "home-b"), neutral: sum(list, "neutral"),
    }));
    // NFL playoff games carry their home side instead of a split.
    if (singleGames) {
      const po = { atA: [0, 0, 0], atB: [0, 0, 0], neutral: [0, 0, 0] };
      data.series.forEach((s) => {
        const k = s.neutral ? "neutral" : s.home === A ? "atA" : "atB";
        po[k][s.winner === A ? 0 : s.winner === B ? 1 : 2]++;
      });
      Object.assign(rows[1], po);
    }
    const hasNeutral = rows.some((r) => d3.sum(r.neutral));
    const cell = (v) => {
      const s = el("span");
      s.append(el("strong", null, String(v[0])), document.createTextNode(`–${v[1]}${v[2] ? `–${v[2]}` : ""}`));
      return s;
    };
    const cols = [
      { label: "", render: (r) => r.label },
      { label: `At ${short(A)}`, cls: "num", render: (r) => cell(r.atA) },
      { label: `At ${short(B)}`, cls: "num", render: (r) => cell(r.atB) },
    ];
    if (hasNeutral) cols.push({ label: "Neutral site", cls: "num", render: (r) => cell(r.neutral) });
    const t = table("venue-table", cols, rows);
    t.prepend(el("caption", "caption-note", `${short(A)}–${short(B)}${league.ties ? "–ties" : ""} in each venue.`));
  }

  /* ---------- Footer ---------- */

  function footer() {
    const src = document.getElementById("source");
    src.replaceChildren();
    const a = el("a", null, data.source.label);
    a.href = data.source.url;
    src.append(a);
    const last = timelineRows().pop();
    document.getElementById("data-through").textContent = `Through the ${last.label} season.`;
    const notes = document.getElementById("notes");
    notes.querySelectorAll(".rv-note").forEach((n) => n.remove());
    (data.notes ?? []).forEach((n) => notes.append(el("span", "rv-note", ` ${n}`)));
  }

  function render() {
    versus();
    stats();
    timeline();
    seasonsChart();
    seriesTable();
    biggest();
    venues();
    footer();
  }

  const wanted = location.hash.slice(1);
  select(byId.has(wanted) ? wanted : all.rivalries[0].id);
})();
