/* Formula 1: how every title was won, driver and constructor records, and the circuits. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote, ttRow } = Viz;
  const raw = await d3.json(document.body.dataset.src);
  const { drivers, constructors, champions } = raw;
  const F = Football({ clubs: {}, countries: raw.countries });
  const withFlag = (code, text) => {
    const span = el("span", "club");
    span.append(F.flag(code), document.createTextNode(text));
    return span;
  };
  const driverLabel = (id) => withFlag(drivers[id]?.nation, drivers[id]?.name ?? id);
  const teams = (c) => c.constructors.map((id) => constructors[id]?.name ?? id).join(" and ");

  /* ---------- How the titles were won ---------- */

  const seasons = champions.filter((c) => c.marginPct != null);
  const lastRace = (c) => c.roundsLeft === 0;
  const COLOR = { last: "var(--series-2)", early: "var(--series-1)" };
  Viz.legend("margin-legend", [{ label: "Decided at the last race", color: COLOR.last }, { label: "Clinched earlier", color: COLOR.early }]);
  const decidedLast = seasons.filter(lastRace).length;
  document.getElementById("margin-note").textContent =
    `${decidedLast} of ${seasons.length} titles went down to the last race. The margin is the source's, in points, over the runner-up.`;

  function renderMargins(width) {
    const root = document.getElementById("margin-chart");
    const narrow = width < 640;
    const height = narrow ? 220 : 280;
    const m = { t: 10, r: 8, b: 26, l: 40 };
    const x = d3.scaleBand().domain(seasons.map((c) => c.season)).range([m.l, width - m.r]).padding(0.2);
    const y = d3.scaleLinear().domain([0, d3.max(seasons, (c) => c.marginPct)]).nice().range([height - m.b, m.t]);
    const svg = d3.create("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img").attr("aria-label", "Title margin by season");
    const yt = y.ticks(5);
    svg.append("g").selectAll("line").data(yt).join("line").attr("class", (d) => (d === 0 ? "baseline" : "gridline"))
      .attr("x1", m.l).attr("x2", width - m.r).attr("y1", y).attr("y2", y);
    svg.append("g").attr("class", "axis").selectAll("text").data(yt).join("text")
      .attr("x", m.l - 6).attr("y", (d) => y(d) + 4).attr("text-anchor", "end").text((d) => `${d}%`);
    svg.append("g").attr("class", "axis").selectAll("text").data(seasons.filter((c) => c.season % (narrow ? 20 : 10) === 0)).join("text")
      .attr("x", (c) => x(c.season) + x.bandwidth() / 2).attr("y", height - 8).attr("text-anchor", "middle").text((c) => c.season);
    const bars = svg.append("g").selectAll("path").data(seasons).join("path")
      .attr("fill", (c) => (lastRace(c) ? COLOR.last : COLOR.early))
      .attr("d", (c) => Viz.columnPath(x(c.season), y(c.marginPct), x.bandwidth(), y(0) - y(c.marginPct), Math.min(3, x.bandwidth() / 2)));
    Viz.tooltipOn(bars, (t, c) => {
      t.append(ttTitle(`${c.season} · ${drivers[c.driver].name}`),
        ttRow(lastRace(c) ? COLOR.last : COLOR.early, `${c.margin} points`, ` ahead (${c.marginPct.toFixed(1)}% of his total)`),
        ttNote(`${teams(c)} · ${c.wins} wins · clinched ${c.clinched}${c.roundsLeft ? `, ${c.roundsLeft} rounds left` : ""}`));
    });
    root.replaceChildren(svg.node());
  }
  Viz.responsive("margin-chart", renderMargins);

  const marginRows = (list) => list.map((c) => c);
  F.richTable(document.getElementById("closest-table"), [
    { label: "Season", render: (c) => String(c.season) },
    { label: "Champion", render: (c) => F.withSub(driverLabel(c.driver), `${teams(c)} · clinched ${c.clinched}`) },
    { label: "Margin", cls: "num strong", render: (c) => `${c.margin} pt${c.margin === 1 ? "" : "s"}` },
  ], marginRows(seasons.slice().sort((a, b) => a.marginPct - b.marginPct || a.season - b.season).slice(0, 10)));
  F.richTable(document.getElementById("dominant-table"), [
    { label: "Season", render: (c) => String(c.season) },
    { label: "Champion", render: (c) => F.withSub(driverLabel(c.driver), `${teams(c)} · ${c.roundsLeft ? `${c.roundsLeft} round${c.roundsLeft === 1 ? "" : "s"} to spare` : "decided at the last race"}`) },
    { label: "Margin", cls: "num strong", render: (c) => `${c.marginPct.toFixed(0)}%` },
  ], marginRows(seasons.slice().sort((a, b) => b.marginPct - a.marginPct).slice(0, 10)));

  /* ---------- Records ---------- */

  const groups = [...new Set(raw.records.map((r) => r.group))];
  const pick = document.getElementById("records-pick");
  let group = groups[0];
  function fillPicker() {
    pick.replaceChildren(...raw.records.filter((r) => r.group === group).map((r) => {
      const o = el("option", null, r.label);
      o.value = String(raw.records.indexOf(r));
      return o;
    }));
    renderRecord(+pick.value);
  }
  function renderRecord(i) {
    const rec = raw.records[i];
    // Column 0 is the rank, column 1 the driver or constructor; the rest as published.
    const rest = rec.columns.map((c, k) => ({ c, k })).filter(({ k }) => k > 1);
    const long = (text) => text.length > 40;
    F.richTable(document.getElementById("records-table"), [
      { label: "#", cls: "rank", render: (r) => r.cells[0] },
      { label: rec.columns[1], render: (r) => {
        const longCells = rest.filter(({ k }) => long(r.cells[k]));
        const label = withFlag(r.nation, r.cells[1]);
        return longCells.length ? F.withSub(label, longCells.map(({ k }) => r.cells[k]).join(" · ")) : label;
      } },
      ...rest.map(({ c, k }) => ({ label: c, cls: rec.rows.every((r) => long(r.cells[k])) ? "hide-all" : /^[\d.,%\s]+$/.test(rec.rows[0].cells[k]) ? "num" : "", render: (r) => (long(r.cells[k]) ? "" : r.cells[k]) })),
    ], rec.rows);
  }
  Viz.segmented("records-group", groups.map((g) => ({ key: g, label: g })), group, (g) => { group = g; fillPicker(); });
  pick.addEventListener("change", () => renderRecord(+pick.value));
  fillPicker();

  /* ---------- Circuits ---------- */

  const circuits = raw.circuits;
  const byNation = d3.rollups(circuits, (v) => ({ races: d3.sum(v, (c) => c.races), circuits: v }), (c) => c.nation)
    .map(([nation, v]) => ({ nation, ...v })).sort((a, b) => b.races - a.races);
  document.getElementById("circuits-lede").textContent =
    `${circuits.length} circuits in ${byNation.length} countries have hosted ${d3.format(",")(d3.sum(circuits, (c) => c.races))} World Championship Grands Prix. The circuits that hosted the most, and the countries.`;
  const VIEWS = {
    circuits: () => F.rankList(document.getElementById("circuits-list"), circuits.slice(0, 25).map((c) => ({
      icon: F.flag(c.nation), label: c.name, value: c.races, second: c.location, color: "var(--series-1)",
      tip: (t) => t.append(ttTitle(c.name), ttNote(`${c.type} · ${c.location} · ${c.grandsPrix.join(", ")}`), ttNote(c.seasons)),
    })), ["Circuit", "Races", "Location"]),
    nations: () => F.rankList(document.getElementById("circuits-list"), byNation.slice(0, 25).map((n) => ({
      icon: F.flag(n.nation), label: F.countryName(n.nation), value: n.races, second: `${n.circuits.length} circuit${n.circuits.length === 1 ? "" : "s"}`, color: "var(--series-1)",
      tip: (t) => t.append(ttTitle(F.countryName(n.nation)), ttNote(n.circuits.map((c) => `${c.name} ${c.races}`).join(" · "))),
    })), ["Country", "Races", "Circuits"]),
  };
  Viz.segmented("circuits-tabs", [{ key: "circuits", label: "Circuits" }, { key: "nations", label: "Countries" }], "circuits", (k) => VIEWS[k]());
  VIEWS.circuits();
})();
