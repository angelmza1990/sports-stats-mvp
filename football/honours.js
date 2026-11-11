/* Every trophy by club on a league page: league titles, national cups and international titles side by side.
   Reads data/honours.json (scripts/build_honours.py) into the #honours section. */
(async function () {
  "use strict";

  const section = document.getElementById("honours");
  if (!section) return;
  const { el, ttTitle, ttNote, ttRow } = Viz;
  const data = await d3.json(section.dataset.src || "data/honours.json");
  const F = Football({ clubs: data.clubs, countries: {} });
  const { clubName } = F;
  const comps = data.competitions;
  const KINDS = [
    { key: "league", label: "League titles", short: "Lg", color: "var(--series-1)" },
    { key: "cup", label: "National cups", short: "Cup", color: "var(--series-2)" },
    { key: "intl", label: "International", short: "Int", color: "var(--series-3)" },
  ].filter((k) => comps.some((c) => c.kind === k.key));
  const kindOf = Object.fromEntries(comps.map((c) => [c.key, c.kind]));
  const rows = data.rows.map((r) => {
    const by = Object.fromEntries(KINDS.map((k) => [k.key, 0]));
    Object.entries(r.titles).forEach(([c, n]) => (by[kindOf[c]] += n));
    return { ...r, by, total: d3.sum(Object.values(by)) };
  });
  const state = { kind: "all", view: "summary" };
  const value = (r) => (state.kind === "all" ? r.total : r.by[state.kind]);
  const num = (n) => (n ? String(n) : "–");
  const detail = (r, kind) => comps.filter((c) => c.kind === kind && r.titles[c.key]).map((c) => `${c.short} ${r.titles[c.key]}`).join(" · ");

  function scoped() {
    const list = rows.filter((r) => value(r) > 0);
    list.sort((a, b) => value(b) - value(a) || b.total - a.total || b.by.league - a.by.league || d3.ascending(clubName(a.club), clubName(b.club)));
    let rank = 0;
    list.forEach((r, i) => (r.rank = i && value(list[i - 1]) === value(r) ? rank : (rank = i + 1)));
    return list;
  }

  /* ---------- The chart: the leading clubs, one stacked bar each ---------- */

  function chart(width) {
    const list = scoped().slice(0, 12);
    const kinds = KINDS.filter((k) => state.kind === "all" || k.key === state.kind);
    const narrow = width < 560;
    const m = { t: 4, r: 40, b: 4, l: narrow ? 118 : 190 };
    const band = 28;
    const height = m.t + m.b + band * list.length;
    const x = d3.scaleLinear().domain([0, d3.max(list, value) || 1]).range([m.l, width - m.r]);
    const svg = d3.create("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img")
      .attr("aria-label", "Trophies of the clubs with the most, by kind");
    const g = svg.append("g").selectAll("g").data(list).join("g").attr("transform", (r, i) => `translate(0,${m.t + i * band})`);
    g.append("text").attr("fill", "var(--ink-2)").attr("font-size", 12).attr("x", m.l - 8).attr("y", band / 2 + 4).attr("text-anchor", "end")
      .text((r) => { const n = clubName(r.club); return narrow && n.length > 16 ? `${n.slice(0, 15)}…` : n; });
    g.each(function (r) {
      let x0 = 0;
      const parts = kinds.map((k) => ({ k, from: x0, n: r.by[k.key], to: (x0 += r.by[k.key]) })).filter((p) => p.n);
      const node = d3.select(this);
      parts.forEach((p, i) => {
        const x1 = x(p.from) + (i ? 1 : 0), x2 = x(p.to) - (i < parts.length - 1 ? 1 : 0);
        const shape = i === parts.length - 1
          ? node.append("path").attr("d", Viz.barPath(x1, 6, Math.max(0, x2 - x1), band - 12))
          : node.append("rect").attr("x", x1).attr("y", 6).attr("width", Math.max(0, x2 - x1)).attr("height", band - 12);
        shape.attr("fill", p.k.color);
      });
      node.append("text").attr("class", "label-muted").attr("x", x(value(r)) + 6).attr("y", band / 2 + 4).text(value(r));
      node.append("rect").attr("x", 0).attr("y", 0).attr("width", width).attr("height", band).attr("fill", "transparent");
    });
    Viz.tooltipOn(g, (t, r) => {
      t.append(ttTitle(`${clubName(r.club)}: ${r.total} trophies`));
      KINDS.forEach((k) => r.by[k.key] && t.append(ttRow(k.color, r.by[k.key], ` ${k.label.toLowerCase()}`), ttNote(detail(r, k.key))));
    });
    document.getElementById("honours-chart").replaceChildren(svg.node());
    Viz.legend("honours-legend", kinds.map((k) => ({ label: k.label, color: k.color })));
  }
  const rerender = Viz.responsive("honours-chart", chart);

  /* ---------- The table ---------- */

  function table() {
    const list = scoped();
    const kinds = KINDS.filter((k) => state.kind === "all" || k.key === state.kind);
    const club = { label: "Club", render: (r) => F.withSub(F.clubLabel(r.club), kinds.filter((k) => k.key !== "league").map((k) => detail(r, k.key)).filter(Boolean).join(" · ") || " ") };
    const columns = state.view === "summary" ? [
      ...kinds.map((k) => ({ label: k.label, short: k.short, cls: "num", render: (r) => num(r.by[k.key]) })),
    ] : comps.filter((c) => state.kind === "all" || c.kind === state.kind).map((c) => ({
      label: c.short, cls: "num", render: (r) => num(r.titles[c.key]),
    }));
    F.richTable(document.getElementById("honours-table"), [
      { label: "#", cls: "num rank hide-sm", render: (r) => String(r.rank) },
      state.view === "summary" ? club : { label: "Club", render: (r) => F.clubLabel(r.club) },
      ...columns,
      ...(state.kind === "all" || state.view === "competition" ? [{ label: "Total", short: "Tot", cls: "num strong", render: (r) => String(value(r)) }] : []),
    ], list);
    // Name each competition in the header, since the columns use short labels.
    if (state.view === "competition") {
      const shown = comps.filter((c) => state.kind === "all" || c.kind === state.kind);
      document.querySelectorAll("#honours-table th").forEach((th, i) => i >= 2 && shown[i - 2] && (th.title = shown[i - 2].label));
    }
  }

  const count = (kind) => d3.sum(rows, (r) => r.by[kind]);
  const lists = KINDS.map((k) => `${k.label.toLowerCase()} (${comps.filter((c) => c.kind === k.key).map((c) => c.label).join(", ")})`);
  const note = document.getElementById("honours-note");
  note.textContent = `${d3.sum(rows, (r) => r.total)} trophies won by ${rows.length} clubs: ${KINDS.map((k) => `${count(k.key)} ${k.label.toLowerCase()}`).join(", ")}. ` +
    `Counted: ${lists.join("; ")}. ${data.meta.notes.join(" ")} ` +
    "Shared titles count for each club; friendly and invitational trophies are left out" +
    (comps.some((c) => c.key === "ucl") ? ", and so is the Inter-Cities Fairs Cup, which UEFA does not count as one of its competitions." : ".");

  const redraw = () => { rerender(); table(); };
  Viz.segmented("honours-kind", [{ key: "all", label: "All trophies" }, ...KINDS.map((k) => ({ key: k.key, label: k.label }))], "all", (k) => { state.kind = k; redraw(); });
  Viz.segmented("honours-view", [{ key: "summary", label: "By kind" }, { key: "competition", label: "By competition" }], "summary", (k) => { state.view = k; table(); });
  table();
})();
