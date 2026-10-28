/* Great Rivalries: the big clubs' rivalries country by country, every official match and friendly, with the head to head worked out here. */
(async function () {
  "use strict";

  const { el, responsive, tooltipOn, tooltipOnNode, ttTitle, ttNote, ttRow, barPath, columnPath } = Viz;
  const index = await d3.json("data/index.json");
  const byId = new Map(index.rivalries.map((r) => [r.id, r]));
  const COLOR = { a: "var(--team-a)", b: "var(--team-b)", d: "var(--draw)" };
  const STAGES = [["league", "League"], ["state", "State championships"], ["regional", "Interstate tournaments"], ["cup", "Domestic cups"],
    ["super", "Super cups"], ["intl", "International"], ["all", "Every meeting"]];
  const COUNTRIES = ["ARG", "URU", "BRA", "ENG", "ESP", "ITA", "FRA", "GER"].filter((c) => index.groups.some((g) => g.country === c));
  const fmtDate = d3.utcFormat("%-d %b %Y");
  const fmtMonth = d3.utcFormat("%b %Y");
  const parse = d3.utcParse("%Y-%m-%d");
  const Fi = Football(index);
  const files = new Map();

  async function load(id) {
    if (!files.has(id)) {
      const d = await d3.json(`data/${id}.json`);
      [...d.matches, ...d.friendlies, ...(d.recent ?? [])].forEach((m) => (m.when = parse(m.date)));
      files.set(id, d);
    }
    return files.get(id);
  }

  let data, F, A, B, view = "official";

  /* ---------- Helpers ---------- */

  const winner = (m) => (m.hs > m.as ? m.home : m.as > m.hs ? m.away : null);
  const gf = (m, t) => (m.home === t ? m.hs : m.as);
  const short = (id) => data.teams.find((t) => t.id === id)?.short ?? id;
  const name = (id) => data.teams.find((t) => t.id === id)?.name ?? id;
  const color = (id) => (id === A ? COLOR.a : id === B ? COLOR.b : "var(--ink-muted)");
  const dateText = (m) => (m.approxDate === "year" ? `≈ ${m.when.getUTCFullYear()}` : m.approxDate ? `≈ ${fmtMonth(m.when)}` : fmtDate(m.when));
  const year = (m) => m.when.getUTCFullYear();
  const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

  function record(ms) {
    const r = { n: ms.length, a: 0, b: 0, d: 0, ga: 0, gb: 0 };
    ms.forEach((m) => {
      const w = winner(m);
      if (w === A) r.a++;
      else if (w === B) r.b++;
      else r.d++;
      r.ga += gf(m, A);
      r.gb += gf(m, B);
    });
    return r;
  }

  function scoreLine(m) {
    return `${short(m.home)} ${m.hs}–${m.as} ${short(m.away)}`;
  }

  function extra(m) {
    const bits = [];
    if (m.aet) bits.push("a.e.t.");
    if (m.pens) bits.push(`${m.pens[0]}–${m.pens[1]} pens`);
    if (m.decided) bits.push(m.decided);
    return bits.join(" · ");
  }

  function compRound(m) {
    return [m.comp, m.round, m.leg].filter(Boolean).join(" · ");
  }

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

  function segmented(rootId, options, initial, onChange) {
    const root = document.getElementById(rootId);
    root.replaceChildren();
    Viz.segmented(rootId, options, initial, onChange);
  }

  // A fresh chart container each render, so old resize observers never draw into the new view.
  function freshChart(id) {
    const old = document.getElementById(id);
    const node = el("div", old.className);
    node.id = id;
    old.replaceWith(node);
    return node;
  }

  /* ---------- Rivalry picker: a tab per country, a card per rivalry ---------- */

  const countryTabs = document.getElementById("country-tabs");
  const picker = document.getElementById("picker");
  let country = null;

  function countryButtons() {
    countryTabs.replaceChildren();
    COUNTRIES.forEach((code) => {
      const b = el("button");
      b.type = "button";
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", String(code === country));
      const info = index.countries[code];
      const flag = el("img", "flag");
      flag.alt = "";
      flag.src = Viz.flagUrl(info.flag);
      const n = index.rivalries.filter((r) => groupOf(r).country === code).length;
      b.append(flag, el("span", null, info.name), el("small", null, String(n)));
      b.addEventListener("click", () => {
        if (code === country) return;
        const first = index.rivalries.find((r) => groupOf(r).country === code);
        select(first.id);
      });
      countryTabs.append(b);
    });
  }

  const groupOf = (r) => index.groups.find((g) => g.id === r.group);

  function rivalryCards(currentId) {
    picker.replaceChildren();
    index.groups.filter((g) => g.country === country).forEach((g) => {
      const list = index.rivalries.filter((r) => r.group === g.id);
      if (g.region) picker.append(el("h3", "picker-region", g.region));
      const grid = el("div", "picker-grid");
      grid.setAttribute("role", "tablist");
      grid.setAttribute("aria-label", g.region ? `${g.name}, ${g.region}` : g.name);
      list.forEach((r) => {
        const b = el("button");
        b.type = "button";
        b.setAttribute("role", "tab");
        b.setAttribute("aria-selected", String(r.id === currentId));
        const crests = el("span", "crests");
        r.teams.forEach((t) => crests.append(Fi.crest(t.id)));
        const meta = r.mode === "summary" ? `${r.record.n} matches · totals only`
          : `${r.record.n} ${r.allMeetings ? "meetings" : "matches"} since ${r.first}`;
        b.append(crests, el("strong", null, r.name), el("small", null, meta));
        b.addEventListener("click", () => select(r.id));
        grid.append(b);
      });
      picker.append(grid);
    });
  }

  function applyColors() {
    const c = Viz.isDark() ? data.colors.dark : data.colors.light;
    document.body.style.setProperty("--team-a", c[0]);
    document.body.style.setProperty("--team-b", c[1]);
  }
  Viz.onThemeChange(() => data && applyColors());

  let selecting = 0;
  async function select(id) {
    const ticket = ++selecting;
    const next = await load(id);
    if (ticket !== selecting) return;  // a later click won
    data = next;
    F = Football(data);
    [A, B] = data.teams.map((t) => t.id);
    country = groupOf(byId.get(id)).country;
    document.body.dataset.rivalry = id;
    applyColors();
    countryButtons();
    rivalryCards(id);
    try {
      history.replaceState(null, "", `#${id}`);
    } catch (e) {}
    render();
  }

  /* ---------- Everyone against everyone ---------- */

  function groupMatrix() {
    const g = groupOf(byId.get(data.id));
    const list = index.rivalries.filter((r) => r.group === g.id);
    const clubs = [...new Set(list.flatMap((r) => r.teams.map((t) => t.id)))];
    const section = document.getElementById("group");
    section.hidden = clubs.length < 3;
    if (section.hidden) return;
    document.getElementById("group-title").textContent = `${g.label}, everyone against everyone`;
    const pairing = (x, y) => list.find((r) => r.teams.some((t) => t.id === x) && r.teams.some((t) => t.id === y));
    const fromRow = (r, row) => (r.teams[0].id === row ? { w: r.record.a, d: r.record.d, l: r.record.b } : { w: r.record.b, d: r.record.d, l: r.record.a });
    const totals = new Map(clubs.map((c) => {
      const t = { w: 0, d: 0, l: 0 };
      clubs.forEach((o) => {
        const r = c !== o && pairing(c, o);
        if (!r) return;
        const x = fromRow(r, c);
        t.w += x.w;
        t.d += x.d;
        t.l += x.l;
      });
      return [c, t];
    }));
    clubs.sort((p, q) => (totals.get(q).w - totals.get(q).l) - (totals.get(p).w - totals.get(p).l));
    const clubName = (id) => index.clubs[id]?.name ?? id;
    const t = el("table", "matrix");
    const head = el("tr");
    head.append(el("th", null, ""));
    clubs.forEach((c) => {
      const th = el("th", "num");
      th.append(Fi.crest(c));
      th.title = clubName(c);
      th.setAttribute("aria-label", clubName(c));
      head.append(th);
    });
    head.append(el("th", "num", "Total"));
    t.append(head);
    clubs.forEach((row) => {
      const tr = el("tr");
      const name = el("th", "matrix-club");
      name.scope = "row";
      name.append(Fi.crest(row), el("span", "matrix-name", clubName(row)));
      name.title = clubName(row);
      tr.append(name);
      clubs.forEach((col) => {
        const td = el("td", "num matrix-cell");
        if (row === col) {
          td.classList.add("diag");
          tr.append(td);
          return;
        }
        const r = pairing(row, col);
        const x = fromRow(r, row);
        const b = el("button", `matrix-pair${r.id === data.id ? " current" : ""}${x.w > x.l ? " ahead" : x.w < x.l ? " behind" : ""}`);
        b.type = "button";
        b.append(el("span", "w", String(x.w)), el("span", "dl", `${x.d}–${x.l}`));
        b.setAttribute("aria-label", `${clubName(row)} against ${clubName(col)}: ${x.w} wins, ${x.d} draws, ${x.l} losses${r.mode === "summary" ? " (published totals)" : ""}. Open ${r.name}`);
        b.addEventListener("click", () => {
          select(r.id);
          document.getElementById("summary").scrollIntoView({ behavior: Viz.reduceMotion ? "auto" : "smooth" });
        });
        tooltipOnNode(b, (tip) => {
          tip.append(ttTitle(r.name), ttNote(`${clubName(row)}: ${x.w} wins · ${x.d} draws · ${x.l} losses`),
            ttNote(r.mode === "summary" ? "Published totals" : `${r.record.n} ${r.allMeetings ? "meetings, friendlies included" : "official matches"}`));
        });
        td.append(b);
        tr.append(td);
      });
      const tot = totals.get(row);
      const n = tot.w + tot.d + tot.l;
      tr.append(el("td", "num matrix-total", `${tot.w}–${tot.d}–${tot.l}`), el("td", "num matrix-pct hide-sm", `${d3.format(".0%")(n ? tot.w / n : 0)} won`));
      t.append(tr);
    });
    head.append(el("th", "num hide-sm", ""));
    document.getElementById("group-matrix").replaceChildren(t);
    const summaries = list.filter((r) => r.mode === "summary").length;
    document.getElementById("group-lede").textContent = "Each club's official record against every other club of the group: read across a row for its wins, then draws–losses. " +
      "Select a pairing to open it." + (summaries ? ` ${summaries === 1 ? "One pairing uses" : `${summaries} pairings use`} the totals their sources publish.` : "");
  }

  /* ---------- Head-to-head card ---------- */

  function versus(prefix, ms) {
    return versusRecord(prefix, record(ms));
  }

  function versusRecord(prefix, r) {
    const head = document.getElementById(`${prefix}versus`);
    head.replaceChildren();
    const side = (id, wins, right) => {
      const s = el("div", `rv-side${right ? " right" : ""}`);
      const txt = el("div");
      txt.append(el("div", "rv-name", name(id)), el("div", "rv-wins", String(wins)), el("div", "rv-label", wins === 1 ? "win" : "wins"));
      s.append(F.crest(id, "crest"), txt);
      return s;
    };
    const mid = el("div", "rv-mid");
    mid.append(el("div", "rv-draws", String(r.d)), el("div", "rv-label", r.d === 1 ? "draw" : "draws"));
    head.append(side(A, r.a), mid, side(B, r.b, true));
    head.setAttribute("aria-label", `${name(A)} ${r.a} wins, ${r.d} draws, ${name(B)} ${r.b} wins`);
    split(document.getElementById(`${prefix}split`), [{ n: r.a, color: COLOR.a }, { n: r.d, color: COLOR.d }, { n: r.b, color: COLOR.b }]);
    const goals = document.getElementById(`${prefix}goals`);
    goals.replaceChildren();
    const g = (id, n) => {
      const s = el("span");
      s.append(el("strong", null, n == null ? "–" : String(n)), document.createTextNode(` goals by ${short(id)}`));
      return s;
    };
    goals.append(g(A, r.ga), el("span", null, plural(r.n, "match", "matches")), g(B, r.gb));
    return r;
  }

  function stats(ms) {
    const root = document.getElementById("stats");
    root.replaceChildren();
    const r = record(ms);
    const last = ms[ms.length - 1];
    // The current run of the side that won the latest match, or of draws.
    const lw = winner(last);
    let run = 0;
    for (let i = ms.length - 1; i >= 0; i--) {
      const w = winner(ms[i]);
      if (lw ? w === lw : w === null) run++;
      else break;
    }
    let unbeaten = 0, side = null;
    for (let i = ms.length - 1; i >= 0; i--) {
      const w = winner(ms[i]);
      if (w === null) {
        unbeaten++;
        continue;
      }
      if (side === null) side = w;
      if (w === side) unbeaten++;
      else break;
    }
    F.statTiles("stats", [
      { label: "Official matches", value: String(r.n), detail: `${year(ms[0])}–${year(last)}` },
      { label: "Goals", value: String(r.ga + r.gb), detail: `${d3.format(".2f")((r.ga + r.gb) / r.n)} per match` },
      { label: "Latest match", value: `${last.hs}–${last.as}`, detail: `${scoreLine(last)} · ${fmtDate(last.when)}` },
      side
        ? { label: "Current run", value: String(unbeaten), detail: `${short(side)} unbeaten (${plural(run, lw ? "win" : "draw")} in a row)`, club: side }
        : { label: "Current run", value: String(unbeaten), detail: "draws in a row" },
    ]);
  }

  /* ---------- The lead over time ---------- */

  function timeline(ms) {
    let diff = 0, ra = 0, rb = 0, rd = 0;
    const pts = ms.map((m) => {
      const w = winner(m);
      if (w === A) (diff++, ra++);
      else if (w === B) (diff--, rb++);
      else rd++;
      return { m, diff, ra, rb, rd };
    });
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
      `${short(A)} led by as many as ${Math.max(0, maxA.diff)}${maxA.diff > 0 ? ` (${year(maxA.m)})` : ""}; ` +
      `${short(B)} by as many as ${Math.max(0, -maxB.diff)}${maxB.diff < 0 ? ` (${year(maxB.m)})` : ""}. ` +
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
      const margin = { top: 20, right: 14, bottom: 26, left: narrow ? 34 : 40 };
      const height = narrow ? 260 : 340;
      const x = d3.scaleUtc().domain(d3.extent(pts, (p) => p.m.when)).range([margin.left, width - margin.right]);
      const ext = Math.max(4, d3.max(pts, (p) => Math.abs(p.diff)));
      const y = d3.scaleLinear().domain([-ext, ext]).nice().range([height - margin.bottom, margin.top]);
      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img")
        .attr("aria-label", `Head-to-head lead after each of ${pts.length} matches. Today: ${lead(now)}.`);

      const axis = svg.append("g").attr("class", "axis");
      y.ticks(narrow ? 5 : 7).forEach((v) => {
        axis.append("line").attr("class", v === 0 ? "baseline" : "gridline").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", y(v)).attr("y2", y(v));
        axis.append("text").attr("x", margin.left - 6).attr("y", y(v)).attr("dy", "0.32em").attr("text-anchor", "end").text(v > 0 ? `+${v}` : v < 0 ? `+${-v}` : "0");
      });
      x.ticks(narrow ? 5 : 10).forEach((t) => {
        axis.append("text").attr("x", x(t)).attr("y", height - 6).attr("text-anchor", "middle").text(t.getUTCFullYear());
      });
      axis.append("text").attr("class", "label-muted").attr("x", margin.left + 6).attr("y", margin.top - 6).text(`↑ ${short(A)} ahead`);
      axis.append("text").attr("class", "label-muted").attr("x", margin.left + 6).attr("y", height - margin.bottom - 6).text(`↓ ${short(B)} ahead`);

      const step = [{ m: { when: pts[0].m.when }, diff: 0 }, ...pts];
      const area = (f) => d3.area().curve(d3.curveStepAfter).x((p) => x(p.m.when)).y0(y(0)).y1((p) => y(f(p.diff)));
      svg.append("path").attr("d", area((v) => Math.max(0, v))(step)).attr("fill", COLOR.a).attr("fill-opacity", 0.28);
      svg.append("path").attr("d", area((v) => Math.min(0, v))(step)).attr("fill", COLOR.b).attr("fill-opacity", 0.28);
      svg.append("path").attr("d", d3.line().curve(d3.curveStepAfter).x((p) => x(p.m.when)).y((p) => y(p.diff))(step))
        .attr("fill", "none").attr("stroke", "var(--ink-2)").attr("stroke-width", 2).attr("stroke-linejoin", "round");

      // The biggest lead of each side, and today's.
      const mark = (p, c, label, anchor) => {
        svg.append("circle").attr("cx", x(p.m.when)).attr("cy", y(p.diff)).attr("r", 4.5).attr("fill", c).attr("stroke", "var(--surface)").attr("stroke-width", 2);
        svg.append("text").attr("class", "label-value").attr("x", x(p.m.when) + (anchor === "end" ? -8 : 8)).attr("y", y(p.diff) + (p.diff >= 0 ? -8 : 16))
          .attr("text-anchor", anchor).text(label);
      };
      const anchorAt = (p) => (x(p.m.when) > width * 0.7 ? "end" : "start");
      if (maxA.diff > 0) mark(maxA, COLOR.a, `+${maxA.diff}`, anchorAt(maxA));
      if (maxB.diff < 0) mark(maxB, COLOR.b, `+${-maxB.diff}`, anchorAt(maxB));
      const end = pts[pts.length - 1];
      if (end !== maxA && end !== maxB) mark(end, now > 0 ? COLOR.a : now < 0 ? COLOR.b : COLOR.d, "", "end");

      // Crosshair: the nearest match to the pointer.
      const cross = svg.append("g").attr("pointer-events", "none").style("display", "none");
      cross.append("line").attr("class", "gridline").attr("y1", margin.top).attr("y2", height - margin.bottom).attr("stroke", "var(--ink-muted)");
      const cdot = cross.append("circle").attr("r", 5).attr("stroke", "var(--surface)").attr("stroke-width", 2);
      const bisect = d3.bisector((p) => p.m.when).center;
      const show = (event, p) => {
        cross.style("display", null).attr("transform", `translate(${x(p.m.when)},0)`);
        cdot.attr("cy", y(p.diff)).attr("fill", color(winner(p.m)));
        Viz.showTip(event, (t) => {
          t.append(ttTitle(`${dateText(p.m)} · Match ${p.m.n}`));
          t.append(ttRow(color(winner(p.m)), `${p.m.hs}–${p.m.as}`, ` ${short(p.m.home)} v ${short(p.m.away)}`));
          t.append(ttNote(compRound(p.m)));
          if (extra(p.m)) t.append(ttNote(extra(p.m)));
          t.append(ttNote(`After it: ${short(A)} ${p.ra} · draws ${p.rd} · ${short(B)} ${p.rb} (${lead(p.diff)})`));
        });
      };
      const overlay = svg.append("rect").attr("class", "hit").attr("x", margin.left).attr("y", margin.top)
        .attr("width", width - margin.left - margin.right).attr("height", height - margin.top - margin.bottom).attr("fill", "transparent")
        .attr("tabindex", 0).attr("aria-label", "Explore the matches; use the left and right arrow keys");
      let idx = pts.length - 1;
      overlay.on("pointermove pointerenter", (event) => {
        const [px] = d3.pointer(event);
        idx = bisect(pts, x.invert(px));
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

  /* ---------- By competition ---------- */

  function competitions(ms, published) {
    const root = document.getElementById("comp-table");
    const t = el("table");
    const head = el("tr");
    const th = (text, cls) => {
      const c = el("th", cls);
      c.append(text);
      return c;
    };
    const teamHead = (id) => {
      const s = el("span", "who");
      s.append(dot(color(id)), document.createTextNode(short(id)));
      return s;
    };
    head.append(th("Competition"), th("P", "num"), th(teamHead(A), "num"), th("D", "num"), th(teamHead(B), "num"), th("Goals", "num hide-sm"), th("", "hide-sm"));
    t.append(head);
    const row = (label, r, cls) => {
      const tr = el("tr", cls);
      const bar = el("div", "wdl-bar");
      split(bar, [{ n: r.a, color: COLOR.a }, { n: r.d, color: COLOR.d }, { n: r.b, color: COLOR.b }]);
      const barCell = el("td", "hide-sm");
      barCell.append(bar);
      tr.append(el("td", null, label), el("td", "num", String(r.n)), el("td", `num${r.a > r.b ? " win" : ""}`, String(r.a)),
        el("td", "num", String(r.d)), el("td", `num${r.b > r.a ? " win" : ""}`, String(r.b)),
        el("td", "num hide-sm", r.ga == null || r.gb == null ? "–" : `${r.ga}–${r.gb}`), barCell);
      t.append(tr);
    };
    if (published) {
      published.comps.forEach((c) => row(c.comp, c));
      row(published.comps.length ? "All official matches" : "Every meeting", published.total, "total-row");
      root.replaceChildren(t);
      return;
    }
    STAGES.forEach(([stage, label]) => {
      const list = ms.filter((m) => m.stage === stage);
      if (!list.length) return;
      const comps = d3.groupSort(list, (g) => -g.length, (m) => m.comp);
      const gr = el("tr", "group-row");
      const cell = el("td", null, label);
      cell.colSpan = 7;
      gr.append(cell);
      t.append(gr);
      comps.forEach((c) => row(c, record(list.filter((m) => m.comp === c))));
      if (comps.length > 1) row(`All ${label.toLowerCase()}`, record(list), "total-row");
    });
    row("All official matches", record(ms), "total-row");
    root.replaceChildren(t);
  }

  /* ---------- Scorelines ---------- */

  function scorelines(ms, chartId, legendId, tableId) {
    const lines = d3.rollups(ms, (v) => ({
      a: v.filter((m) => winner(m) === A).length,
      b: v.filter((m) => winner(m) === B).length,
      d: v.filter((m) => !winner(m)).length,
      list: v,
    }), (m) => `${Math.max(m.hs, m.as)}–${Math.min(m.hs, m.as)}`)
      .map(([k, v]) => ({ k, ...v, n: v.list.length, draw: v.d > 0 }))
      .sort((p, q) => q.n - p.n || d3.ascending(p.k, q.k));
    const top = lines.slice(0, 14);
    Viz.legend(legendId, [
      { label: `${short(A)} win`, color: COLOR.a }, { label: "Draw", color: COLOR.d }, { label: `${short(B)} win`, color: COLOR.b },
    ]);
    const node = freshChart(chartId);
    responsive(node, (width) => {
      const container = d3.select(node);
      container.selectAll("*").remove();
      const rowH = 26, barH = 16;
      const margin = { top: 4, right: 40, bottom: 4, left: 46 };
      const height = margin.top + top.length * rowH + margin.bottom;
      const x = d3.scaleLinear().domain([0, d3.max(top, (l) => l.n)]).range([0, width - margin.left - margin.right]);
      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img")
        .attr("aria-label", "Most frequent scorelines: " + top.slice(0, 5).map((l) => `${l.k} ${l.n} times`).join(", "));
      svg.append("line").attr("class", "baseline").attr("x1", margin.left).attr("x2", margin.left).attr("y1", 0).attr("y2", height);
      const g = svg.selectAll("g.row").data(top).join("g").attr("class", "row mark-group")
        .attr("transform", (d, i) => `translate(${margin.left},${margin.top + i * rowH})`);
      g.append("rect").attr("x", -margin.left).attr("width", width).attr("height", rowH).attr("fill", "transparent");
      g.each(function (d) {
        const parts = [["a", COLOR.a], ["d", COLOR.d], ["b", COLOR.b]].filter(([k]) => d[k]);
        let x0 = 0;
        parts.forEach(([k, c], i) => {
          const w = Math.max(0, x(d[k]) - (i < parts.length - 1 ? 2 : 0));
          const last = i === parts.length - 1;
          d3.select(this).append("path").attr("class", "mark").attr("fill", c)
            .attr("d", last ? barPath(x0, (rowH - barH) / 2, w, barH) : `M${x0},${(rowH - barH) / 2}h${w}v${barH}h${-w}Z`);
          x0 += x(d[k]);
        });
      });
      g.append("text").attr("class", "label-name").attr("x", -10).attr("y", rowH / 2).attr("dy", "0.35em").attr("text-anchor", "end").text((d) => d.k);
      g.append("text").attr("class", "label-value").attr("x", (d) => x(d.n) + 6).attr("y", rowH / 2).attr("dy", "0.35em").text((d) => d.n);
      tooltipOn(g, (t, d) => {
        t.append(ttTitle(`${d.k} · ${plural(d.n, "time")}`));
        if (d.draw) t.append(ttRow(COLOR.d, d.d, " draws"));
        else {
          t.append(ttRow(COLOR.a, d.a, ` won by ${short(A)}`));
          t.append(ttRow(COLOR.b, d.b, ` won by ${short(B)}`));
        }
        const latest = d.list[d.list.length - 1];
        t.append(ttNote(`Latest: ${scoreLine(latest)}, ${dateText(latest)}`));
      });
    });
    if (tableId) {
      Viz.table(tableId, ["Score", "Times", `${short(A)} wins`, "Draws", `${short(B)} wins`],
        lines.map((l) => [l.k, String(l.n), String(l.a), String(l.d), String(l.b)]));
    }
  }

  /* ---------- Venues ---------- */

  function venues(ms) {
    const root = document.getElementById("venue-cards");
    root.replaceChildren();
    const groups = [
      { title: `${name(A)} at home`, team: A, list: ms.filter((m) => !m.neutral && m.home === A) },
      { title: `${name(B)} at home`, team: B, list: ms.filter((m) => !m.neutral && m.home === B) },
      { title: "Neutral venues", list: ms.filter((m) => m.neutral) },
    ];
    groups.forEach((g) => {
      const card = el("div", "card venue-card");
      const h = el("h3");
      if (g.team) h.append(F.crest(g.team));
      h.append(document.createTextNode(g.title));
      const r = record(g.list);
      card.append(h, el("p", "venue-sub", g.list.length ? plural(r.n, "match", "matches") : "No matches"));
      if (g.list.length) {
        const bar = el("div", "rv-split");
        split(bar, [{ n: r.a, color: COLOR.a }, { n: r.d, color: COLOR.d }, { n: r.b, color: COLOR.b }]);
        const nums = el("div", "venue-nums");
        const n = (c, v, label) => {
          const s = el("span");
          s.append(dot(c), el("strong", null, String(v)), document.createTextNode(label));
          return s;
        };
        nums.append(n(COLOR.a, r.a, ` ${short(A)}`), n(COLOR.d, r.d, " draws"), n(COLOR.b, r.b, ` ${short(B)}`));
        card.append(bar, nums);
        const gp = el("p", "venue-sub");
        gp.style.margin = "10px 0 0";
        gp.textContent = `Goals ${r.ga}–${r.gb}`;
        card.append(gp);
      }
      root.append(card);
    });
  }

  /* ---------- Decades ---------- */

  function decades(ms) {
    const rows = d3.rollups(ms, (v) => record(v), (m) => Math.floor(year(m) / 10) * 10).sort((p, q) => p[0] - q[0]);
    Viz.legend("decade-legend", [
      { label: `${short(A)} wins`, color: COLOR.a }, { label: "Draws", color: COLOR.d }, { label: `${short(B)} wins`, color: COLOR.b },
    ]);
    const node = freshChart("decade-chart");
    responsive(node, (width) => {
      const container = d3.select(node);
      container.selectAll("*").remove();
      const narrow = width < 560;
      const margin = { top: 14, right: 8, bottom: 24, left: 28 };
      const height = 240;
      const x = d3.scaleBand().domain(rows.map((r) => r[0])).range([margin.left, width - margin.right]).padding(0.22);
      const y = d3.scaleLinear().domain([0, d3.max(rows, (r) => r[1].n)]).nice().range([height - margin.bottom, margin.top]);
      const svg = container.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img")
        .attr("aria-label", "Results by decade: " + rows.map(([dec, r]) => `${dec}s ${short(A)} ${r.a}, draws ${r.d}, ${short(B)} ${r.b}`).join("; "));
      const axis = svg.append("g").attr("class", "axis");
      y.ticks(4).forEach((v) => {
        axis.append("line").attr("class", v === 0 ? "baseline" : "gridline").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", y(v)).attr("y2", y(v));
        axis.append("text").attr("x", margin.left - 6).attr("y", y(v)).attr("dy", "0.32em").attr("text-anchor", "end").text(v);
      });
      rows.forEach(([dec], i) => {
        if (narrow && i % 2) return;
        axis.append("text").attr("x", x(dec) + x.bandwidth() / 2).attr("y", height - 6).attr("text-anchor", "middle").text(narrow ? `'${String(dec).slice(2)}` : `${dec}s`);
      });
      const g = svg.selectAll("g.col").data(rows).join("g").attr("class", "col mark-group");
      g.append("rect").attr("x", (d) => x(d[0]) - 2).attr("width", x.bandwidth() + 4).attr("y", margin.top).attr("height", height - margin.top - margin.bottom).attr("fill", "transparent");
      g.each(function ([dec, r]) {
        const parts = [[r.a, COLOR.a], [r.d, COLOR.d], [r.b, COLOR.b]].filter(([n]) => n);
        let base = 0;
        parts.forEach(([n, c], i) => {
          const top = i === parts.length - 1;
          const y0 = y(base), y1 = y(base + n);
          const h = Math.max(0, y0 - y1 - (top ? 0 : 2));
          d3.select(this).append("path").attr("class", "mark").attr("fill", c)
            .attr("d", top ? columnPath(x(dec), y1, x.bandwidth(), h) : `M${x(dec)},${y1 + 2}h${x.bandwidth()}v${h}h${-x.bandwidth()}Z`);
          base += n;
        });
      });
      tooltipOn(g, (t, [dec, r]) => {
        t.append(ttTitle(`${dec}s · ${plural(r.n, "match", "matches")}`));
        t.append(ttRow(COLOR.a, r.a, ` ${short(A)} wins`), ttRow(COLOR.d, r.d, " draws"), ttRow(COLOR.b, r.b, ` ${short(B)} wins`));
        t.append(ttNote(`Goals ${r.ga}–${r.gb}`));
      });
    });
  }

  /* ---------- Knockout ties and finals ---------- */

  function tieLegs(t) {
    if (t.legs) return t.legs.map((l) => ({ ...l, ...(l.n ? data.matches.find((m) => m.n === l.n) ?? {} : {}) }));
    return t.matches.map((n) => data.matches.find((m) => m.n === n));
  }

  function tally(rootId, list, label) {
    const root = document.getElementById(rootId);
    root.replaceChildren();
    if (!list.length) {
      root.append(el("p", "empty-note", `They have never met in ${label}.`));
      return;
    }
    const wa = list.filter((t) => t.winner === A).length;
    const wb = list.filter((t) => t.winner === B).length;
    const shared = list.length - wa - wb;
    const box = el("div", "tally");
    const side = (id, n, right) => {
      const s = el("div", `side${right ? " right" : ""}`);
      s.append(F.crest(id), el("span", "num", String(n)));
      return s;
    };
    box.append(side(A, wa), el("div", "mid", plural(list.length, label === "a final" ? "final" : "tie")), side(B, wb, true));
    root.append(box);
    const split2 = el("div", "rv-split");
    split(split2, [{ n: wa, color: COLOR.a }, { n: shared, color: COLOR.d }, { n: wb, color: COLOR.b }]);
    root.append(split2);
    const pens = list.filter((t) => /penalt/.test(t.how ?? "")).length;
    const notes = [];
    if (shared) notes.push(`${plural(shared, "shared trophy", "shared trophies")}`);
    if (pens) notes.push(`${plural(pens, "decided on penalties", "decided on penalties")}`);
    const last = list[list.length - 1];
    notes.push(`latest: ${last.season} ${last.comp}, ${last.winner === "shared" ? "shared" : short(last.winner)}`);
    root.append(el("p", "tally-note", notes.join(" · ").replace(/^./, (c) => c.toUpperCase())));
  }

  function tieList(list) {
    const root = document.getElementById("ties-list");
    root.replaceChildren();
    if (!list.length) {
      root.append(el("p", "empty-note", "None."));
      return;
    }
    [...list].reverse().forEach((t) => {
      const row = el("div", "tie-row");
      const legs = tieLegs(t).filter(Boolean);
      const what = el("div");
      const title = el("div", "tie-what", `${t.comp} · ${t.round}`);
      if (t.final) title.append(el("span", "tie-tag", "Final"));
      what.append(title);
      if (!legs.length) {
        const win = el("div", "tie-winner");
        win.append(F.crest(t.winner), document.createTextNode(t.final ? `${short(t.winner)} won` : `${short(t.winner)} through`));
        if (t.how) win.append(el("span", "tie-tag", t.how));
        row.append(el("div", "tie-year", t.season), what, win);
        root.append(row);
        return;
      }
      const legText = legs.map((l, i) => {
        const tag = l.leg === "replay" ? "Replay: " : legs.length > 1 && l.leg !== "replay" ? `${i === 0 ? "1st" : i === 1 ? "2nd" : `${i + 1}th`} leg: ` : "";
        return `${tag}${short(l.home)} ${l.hs}–${l.as} ${short(l.away)}${l.aet ? " (a.e.t.)" : ""}`;
      }).join(" · ");
      const agg = (() => {
        const real = legs.filter((l) => l.leg !== "replay");
        if (real.length < 2) return "";
        const ga = d3.sum(real, (l) => gf(l, A)), gb = d3.sum(real, (l) => gf(l, B));
        return ` · Aggregate ${short(A)} ${ga}–${gb} ${short(B)}`;
      })();
      what.append(el("div", "tie-legs", legText + agg));
      const win = el("div", "tie-winner");
      if (t.winner === "shared") win.append(document.createTextNode("Shared"));
      else win.append(F.crest(t.winner), document.createTextNode(t.final ? `${short(t.winner)} won` : `${short(t.winner)} through`));
      if (t.how && t.how !== "shared") win.append(el("span", "tie-tag", t.how));
      row.append(el("div", "tie-year", t.season), what, win);
      root.append(row);
    });
  }

  function knockouts() {
    const ties = data.ties;
    tally("ties-summary", ties.filter((t) => !t.final), "a knockout tie");
    tally("finals-summary", ties.filter((t) => t.final), "a final");
    segmented("ties-tabs", [{ key: "all", label: `All (${ties.length})` }, { key: "finals", label: `Finals (${ties.filter((t) => t.final).length})` }], "all",
      (k) => tieList(k === "finals" ? ties.filter((t) => t.final) : ties));
    tieList(ties);
    const lede = document.getElementById("ties-lede");
    const legless = ties.length && ties.every((t) => !(t.legs?.length) && !t.matches.length);
    lede.textContent = "Every time one knocked the other out of a cup, over one match, two legs or replays, and every final between them" +
      (data.country === "ARG" ? ", as listed by Spanish Wikipedia (league play-offs included)."
        : legless ? ", as the source lists them: it names who went through, not the scores of every leg."
          : ". Group stages are left out.");
  }

  /* ---------- Records ---------- */

  function recList(rootId, rows) {
    const root = document.getElementById(rootId);
    root.replaceChildren();
    const list = el("div", "rec-list");
    rows.forEach((r) => {
      const row = el("div", "rec-row");
      const main = el("div", "rec-main", r.main);
      main.append(el("span", "rec-sub", r.sub));
      row.append(dot(r.color), main, el("div", "rec-value", r.value));
      list.append(row);
    });
    root.append(list);
  }

  function records(ms) {
    const wins = ms.filter(winner).sort((p, q) => Math.abs(q.hs - q.as) - Math.abs(p.hs - p.as) || (q.hs + q.as) - (p.hs + p.as) || p.n - q.n);
    const best = (team) => wins.filter((m) => winner(m) === team).slice(0, 4);
    recList("biggest", [...best(A), ...best(B)].map((m) => ({
      color: color(winner(m)), main: scoreLine(m), sub: `${dateText(m)} · ${compRound(m)}`, value: `+${Math.abs(m.hs - m.as)}`,
    })));
    const fests = [...ms].sort((p, q) => (q.hs + q.as) - (p.hs + p.as) || p.n - q.n).slice(0, 6);
    recList("goalfests", fests.map((m) => ({
      color: color(winner(m)), main: scoreLine(m), sub: `${dateText(m)} · ${compRound(m)}`, value: plural(m.hs + m.as, "goal"),
    })));

    // Longest runs: wins in a row, unbeaten, draws in a row.
    const runs = (test) => {
      let best = { n: 0 }, cur = 0, start = 0;
      ms.forEach((m, i) => {
        if (test(m)) {
          if (!cur) start = i;
          cur++;
          if (cur > best.n) best = { n: cur, from: ms[start], to: m };
        } else cur = 0;
      });
      return best;
    };
    const span = (r) => (r.n ? `${year(r.from)}${year(r.from) !== year(r.to) ? `–${year(r.to)}` : ""}` : "");
    const rows = [
      [A, "wins in a row", runs((m) => winner(m) === A)], [B, "wins in a row", runs((m) => winner(m) === B)],
      [A, "unbeaten", runs((m) => winner(m) !== B)], [B, "unbeaten", runs((m) => winner(m) !== A)],
      [null, "draws in a row", runs((m) => !winner(m))],
    ];
    recList("streaks", rows.map(([team, label, r]) => ({
      color: team ? color(team) : COLOR.d, main: team ? `${name(team)}, ${label}` : `Draws in a row`,
      sub: r.n ? `${span(r)}: ${dateText(r.from)} to ${dateText(r.to)}` : "", value: plural(r.n, "match", "matches"),
    })));
  }

  /* ---------- Players ---------- */

  function leaders(rootId, list, key) {
    const root = document.getElementById(rootId);
    root.replaceChildren();
    if (!list?.length) {
      root.append(el("p", "empty-note", "Not published by the sources."));
      return;
    }
    const block = (rows, parent) => {
      const max = d3.max(rows, (r) => r[key]);
      let rank = 0, prev = null;
      rows.forEach((r, i) => {
        if (r[key] !== prev) rank = i + 1;
        prev = r[key];
        const row = el("div", "leader-row");
        const who = el("div", "who");
        who.append(el("strong", null, r.name));
        const team = el("span");
        team.append(dot(color(r.team)), document.createTextNode(r.team === "both" ? "Both clubs" : short(r.team)));
        if (key === "goals" && r.apps) team.append(document.createTextNode(` · ${plural(r.apps, "match", "matches")}`));
        who.append(team);
        const barWrap = el("div");
        const bar = el("div", "bar");
        bar.style.setProperty("--c", color(r.team));
        bar.style.width = `${(r[key] / max) * 100}%`;
        barWrap.append(bar);
        row.append(el("span", "rank", String(rank)), who, barWrap, el("span", "val", String(r[key])));
        parent.append(row);
      });
    };
    if (data.leadersByTeam) {
      const wrap = el("div", "leader-split");
      [A, B].forEach((team) => {
        const col = el("div");
        const h = el("h4");
        h.append(F.crest(team), document.createTextNode(name(team)));
        col.append(h);
        block(list.filter((r) => r.team === team).slice(0, 5), col);
        wrap.append(col);
      });
      root.append(wrap);
    } else block(list.slice(0, 10), root);
  }

  /* ---------- Match list ---------- */

  function matchTable(rootId, ms, filters) {
    const root = document.getElementById(rootId);
    const render = (list) => {
      const t = el("table");
      const head = el("tr");
      [["Date"], ["Competition"], ["Home", "match-team right"], ["", ""], ["Away", "match-team"], ["Scorers", "match-goals"]].forEach(([h, cls]) => head.append(el("th", cls, h)));
      t.append(head);
      [...list].reverse().forEach((m) => {
        const tr = el("tr");
        const w = winner(m);
        const team = (id, right) => {
          const td = el("td", `match-team${right ? " right" : ""}${w === id ? " won" : ""}`);
          const s = el("span", "club");
          s.append(F.crest(id), document.createTextNode(short(id)));
          td.append(s);
          return td;
        };
        const score = el("td", "match-score");
        score.append(document.createTextNode(`${m.hs}–${m.as}`));
        if (m.aet || m.pens) score.append(el("small", null, [m.aet ? "a.e.t." : "", m.pens ? `${m.pens[0]}–${m.pens[1]} p` : ""].filter(Boolean).join(" ")));
        const comp = el("td", "match-comp", m.comp);
        const sub = [m.round, m.leg, m.stage === "league" ? m.season : null, m.venue && m.neutral ? m.venue : null].filter(Boolean).join(" · ");
        if (sub) comp.append(el("small", null, sub));
        const goals = [m.goalsHome, m.goalsAway].some(Boolean) ? `${m.goalsHome || "–"} / ${m.goalsAway || "–"}` : "";
        const dateCell = el("td", "num", dateText(m));
        dateCell.style.textAlign = "left";
        tr.append(dateCell, comp, team(m.home, true), score, team(m.away), el("td", "match-goals", goals));
        if (m.decided) tooltipOnNode(score, (tip) => tip.append(ttTitle(scoreLine(m)), ttNote(m.decided)));
        t.append(tr);
      });
      root.replaceChildren(t);
      if (filters) document.getElementById("matches-count").textContent = `Showing ${plural(list.length, "match", "matches")}. Scorers are listed home side first.`;
    };
    if (!filters) return render(ms);
    const select = document.getElementById("match-comp");
    select.replaceChildren();
    const comps = d3.groupSort(ms, (g) => -g.length, (m) => m.comp);
    [["", `All competitions (${ms.length})`], ...comps.map((c) => [c, `${c} (${ms.filter((m) => m.comp === c).length})`])].forEach(([v, label]) => {
      const o = el("option", null, label);
      o.value = v;
      select.append(o);
    });
    let result = "all";
    const apply = () => render(ms.filter((m) => (!select.value || m.comp === select.value) &&
      (result === "all" || (result === "d" ? !winner(m) : winner(m) === (result === "a" ? A : B)))));
    select.onchange = apply;
    segmented("match-result", [{ key: "all", label: "All" }, { key: "a", label: `${short(A)} wins` }, { key: "d", label: "Draws" }, { key: "b", label: `${short(B)} wins` }], "all",
      (k) => ((result = k), apply()));
    apply();
  }

  /* ---------- Friendlies ---------- */

  function friendlies() {
    const fr = data.friendlies;
    const has = fr.length > 0;
    ["fr-scores-card", "fr-table-card"].forEach((id) => (document.getElementById(id).hidden = !has));
    document.getElementById("fr-card").hidden = !has && !data.friendlySummary;
    const lede = document.getElementById("friendlies-lede");
    if (!has && data.friendlySummary) {
      lede.textContent = "The source gives only the totals of the friendlies and unofficial tournaments between them. They don't count in the official head to head.";
      versusRecord("fr-", data.friendlySummary);
      return;
    }
    if (!has) {
      lede.textContent = "The sources don't list this rivalry's friendlies match by match.";
      return;
    }
    lede.textContent = `Exhibition games, pre-season tournaments and tributes, ${year(fr[0])}–${year(fr[fr.length - 1])}. They don't count in the official head to head.` +
      (data.friendliesNote ? ` ${data.friendliesNote}` : "");
    versus("fr-", fr);
    scorelines(fr, "fr-scores-chart", "fr-scores-legend");
    matchTable("fr-table", fr, false);
  }

  /* ---------- Footer ---------- */

  function footer() {
    const src = document.getElementById("source");
    src.replaceChildren();
    const a = el("a", null, data.source.label);
    a.href = data.source.url;
    src.append(a);
    (data.source.extra ?? []).forEach((x) => {
      src.append(document.createTextNode(`; ${x.what} from `));
      const l = el("a", null, x.label);
      l.href = x.url;
      src.append(l);
    });
    document.getElementById("data-through").textContent = data.dataThrough ? `Matches through ${fmtDate(parse(data.dataThrough))}.` : "";
    const notes = document.getElementById("notes");
    notes.querySelectorAll(".rv-note").forEach((n) => n.remove());
    (data.notes ?? []).forEach((n) => notes.append(el("span", "rv-note", ` ${n}`)));
  }

  /* ---------- Render ---------- */

  function setView(v) {
    view = v;
    document.getElementById("official").hidden = v !== "official";
    document.getElementById("friendly").hidden = v !== "friendly";
    document.getElementById("view-note").textContent = data.allMeetings
      ? "The source lists every meeting without its competition, so friendlies are included."
      : v === "official" ? "Official matches only. Friendlies have their own tab." : "Friendlies don't count in the official record.";
  }

  // Sections that need every match; a rivalry with published totals only shows the rest.
  const MATCH_SECTIONS = ["timeline", "scores", "venues", "decades", "records"];

  function summaryStats() {
    const t = data.summary.total;
    const recent = data.recent ?? [];
    const last = recent[recent.length - 1];
    const finals = data.ties.filter((x) => x.final);
    document.getElementById("stats").replaceChildren();
    F.statTiles("stats", [
      { label: "Official matches", value: String(t.n), detail: data.summary.since ? `since ${data.summary.since}` : "published totals" },
      t.ga != null && t.gb != null
        ? { label: "Goals", value: String(t.ga + t.gb), detail: `${d3.format(".2f")((t.ga + t.gb) / t.n)} per match` }
        : { label: "Draws", value: String(t.d), detail: `${d3.format(".0%")(t.d / t.n)} of the matches` },
      last ? { label: "Latest match", value: `${last.hs}–${last.as}`, detail: `${scoreLine(last)} · ${fmtDate(last.when)}` }
        : { label: "Knockout ties", value: String(data.ties.filter((x) => !x.final).length), detail: "listed by the source" },
      { label: "Finals", value: String(finals.length), detail: finals.length ? `${short(A)} ${finals.filter((x) => x.winner === A).length} · ${short(B)} ${finals.filter((x) => x.winner === B).length}` : "between them" },
    ]);
  }

  function render() {
    const summaryMode = data.mode === "summary";
    const ms = data.matches;
    const friendlyCount = data.friendlies.length || data.friendlySummary?.n || 0;
    if (summaryMode) {
      versusRecord("rv-", data.summary.total);
      summaryStats();
    } else {
      versus("rv-", ms);
      stats(ms);
    }
    groupMatrix();
    const tabs = data.allMeetings
      ? [{ key: "official", label: `Every meeting (${ms.length})` }]
      : [{ key: "official", label: `Official (${summaryMode ? data.summary.total.n : ms.length})` }, ...(friendlyCount ? [{ key: "friendly", label: `Friendlies (${friendlyCount})` }] : [])];
    if (!tabs.some((t) => t.key === view)) view = "official";
    segmented("view-tabs", tabs, view, setView);
    setView(view);
    MATCH_SECTIONS.forEach((id) => (document.getElementById(id).hidden = summaryMode));
    document.getElementById("competitions").hidden = Boolean(data.allMeetings);
    if (summaryMode) {
      competitions(null, data.summary);
      document.getElementById("competitions-lede").textContent = data.summary.comps.length
        ? "The totals the source publishes for each competition; it doesn't list every match."
        : "The source publishes one total for every meeting between them, friendlies included.";
    } else {
      document.getElementById("competitions-lede").textContent = "The record in every competition they have met in, from the league to the continental cups.";
      timeline(ms);
      competitions(ms);
      scorelines(ms, "scores-chart", "scores-legend", "scores-table");
      venues(ms);
      decades(ms);
      records(ms);
    }
    knockouts();
    const players = document.getElementById("players-lede");
    players.textContent = "The top scorers and the players with the most appearances in official matches of the rivalry" +
      (data.leadersByTeam ? ", five for each club." : ".");
    leaders("scorers", data.scorers, "goals");
    leaders("apps", data.appearances, "apps");
    const recent = summaryMode ? data.recent ?? [] : ms;
    document.getElementById("matches").hidden = summaryMode && !recent.length;
    document.getElementById("match-controls").hidden = summaryMode;
    document.getElementById("matches-title").textContent = summaryMode ? "The latest matches" : data.allMeetings ? "Every meeting" : "Every official match";
    document.getElementById("matches-lede").textContent = summaryMode ? "The most recent official matches the source lists, latest first." : "Most recent first.";
    if (summaryMode) {
      matchTable("match-table", recent, false);
      document.getElementById("matches-count").textContent = "";
    } else matchTable("match-table", ms, true);
    friendlies();
    footer();
  }

  const fromHash = location.hash.slice(1);
  await select(byId.has(fromHash) ? fromHash : index.rivalries[0].id);
  addEventListener("hashchange", () => {
    const id = location.hash.slice(1);
    if (byId.has(id) && id !== data.id) select(id);
  });
})();
