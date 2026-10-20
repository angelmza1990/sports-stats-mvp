/* Tennis age records: world No. 1s, Grand Slam and Finals champions, and the career Grand Slam. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote } = Viz;
  const data = await d3.json(document.body.dataset.src);
  const F = Football({
    nationMode: true,
    clubs: Object.fromEntries(Object.entries(data.nations).map(([c, n]) => [c, { name: n.name, country: c, crest: null }])),
    countries: data.nations,
  });
  const SLAM_NAME = Object.fromEntries(data.slams.map((s) => [s.key, s.name]));
  const SLAM_COLOR = Object.fromEntries(data.slams.map((s, i) => [s.key, `var(--series-${i + 1})`]));
  const SHORT = { AO: "AO", FR: "RG", WB: "Wim", US: "USO" };
  const DAY = 86400000;
  const parse = (s) => new Date(`${s}T00:00:00Z`);

  /** Age on a date as whole years plus days since the last birthday. */
  function age(born, on) {
    const b = parse(born);
    const d = parse(on);
    let years = d.getUTCFullYear() - b.getUTCFullYear();
    const birthday = (y) => new Date(Date.UTC(y, b.getUTCMonth(), b.getUTCDate()));
    if (birthday(d.getUTCFullYear()) > d) years -= 1;
    const days = Math.round((d - birthday(b.getUTCFullYear() + years)) / DAY);
    return { years, days, value: (d - b) / DAY / 365.2425 };
  }
  const ageText = (a) => `${a.years} years, ${a.days} day${a.days === 1 ? "" : "s"}`;
  const ageShort = (a) => `${a.years}y ${a.days}d`;
  const dateText = (s) => parse(s).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  const who = (name, nation) => {
    const span = el("span", "club");
    span.append(F.flag(nation));
    span.append(document.createTextNode(name));
    return span;
  };
  const ageCell = (a) => {
    const wrap = el("span", "age");
    wrap.append(el("strong", null, String(a.years)), document.createTextNode(` y ${a.days} d`));
    wrap.title = ageText(a);
    return wrap;
  };

  // One resize observer per chart; switching tour swaps the drawing function and redraws.
  const charts = {};
  function chart(id, draw) {
    if (charts[id]) {
      charts[id].draw = draw;
      charts[id].redraw();
    } else {
      charts[id] = { draw };
      charts[id].redraw = Viz.responsive(id, (width) => charts[id].draw(width));
    }
  }

  let tour = "atp";
  const T = () => data.tours[tour];
  const renders = [];
  Viz.segmented("tour", [{ key: "atp", label: "Men" }, { key: "wta", label: "Women" }], tour, (k) => {
    tour = k;
    renders.forEach((r) => r());
  });
  document.getElementById("sources").replaceChildren(
    ...data.meta.sources.flatMap((u, i) => {
      const a = el("a", null, decodeURIComponent(u.split("/wiki/")[1]).replace(/_/g, " "));
      a.href = u;
      return i ? [document.createTextNode(", "), a] : [a];
    }),
  );

  /** One title per player: their youngest (or oldest) title in the rows given. */
  function perPlayer(rows, oldest) {
    const best = new Map();
    rows.forEach((r) => {
      const cur = best.get(r.name);
      if (!cur || (oldest ? r.age.value > cur.age.value : r.age.value < cur.age.value)) best.set(r.name, r);
    });
    return [...best.values()].sort((a, b) => (oldest ? b.age.value - a.age.value : a.age.value - b.age.value));
  }

  /* ---------- Stat tiles ---------- */

  function stats() {
    const t = T();
    const no1 = t.numberOnes.map((p) => ({ ...p, a: age(p.born, p.first), z: age(p.born, p.last) }));
    const young = d3.least(no1, (p) => p.a.value);
    const old = d3.greatest(no1, (p) => p.z.value);
    const slams = t.slams.map((r) => ({ ...r, age: age(r.born, r.date) }));
    const ys = d3.least(slams, (r) => r.age.value);
    const os = d3.greatest(slams, (r) => r.age.value);
    document.getElementById("stats").replaceChildren();
    F.statTiles("stats", [
      { label: "Youngest No. 1", value: ageShort(young.a), detail: `${young.name}, ${dateText(young.first)}`, club: young.nation },
      { label: "Oldest No. 1", value: ageShort(old.z), detail: `${old.name}, ${dateText(old.last)}${old.current ? " (current)" : ""}`, club: old.nation },
      { label: "Youngest major champion", value: ageShort(ys.age), detail: `${ys.name}, ${SLAM_NAME[ys.event]} ${ys.year}`, club: ys.nation },
      { label: "Oldest major champion", value: ageShort(os.age), detail: `${os.name}, ${SLAM_NAME[os.event]} ${os.year}`, club: os.nation },
    ]);
  }
  renders.push(stats);

  /* ---------- World No. 1 ---------- */

  function numberOnes() {
    const rows = T().numberOnes.map((p) => ({ ...p, a: age(p.born, p.first), z: age(p.born, p.last) }))
      .sort((x, y) => x.a.value - y.a.value);
    Viz.legend("no1-legend", [{ label: "Age from first to last week at No. 1", color: "var(--sport)" }, { label: "Current No. 1", color: "var(--series-2)" }]);
    chart("no1-chart", (width) => {
      const box = d3.select("#no1-chart");
      box.selectAll("*").remove();
      const narrow = width < 600;
      const rowH = 22;
      const margin = { top: 24, right: 16, bottom: 8, left: narrow ? 112 : 170 };
      const height = margin.top + rows.length * rowH + margin.bottom;
      const x = d3.scaleLinear().domain([15, Math.ceil(d3.max(rows, (r) => r.z.value) + 1)]).range([margin.left, width - margin.right]);
      const svg = box.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("width", width).attr("height", height);
      const ticks = x.ticks(narrow ? 5 : 10);
      svg.append("g").selectAll("line").data(ticks).join("line").attr("class", "gridline")
        .attr("x1", (d) => x(d)).attr("x2", (d) => x(d)).attr("y1", margin.top - 4).attr("y2", height - margin.bottom);
      svg.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", (d) => x(d)).attr("y", margin.top - 10)
        .attr("text-anchor", "middle").text((d) => d);
      const g = svg.append("g").selectAll("g").data(rows).join("g").attr("transform", (d, i) => `translate(0 ${margin.top + i * rowH})`);
      g.append("text").attr("class", "reign-label").attr("x", margin.left - 8).attr("y", rowH / 2 + 4).attr("text-anchor", "end")
        .text((d) => (narrow ? d.name.split(" ").slice(-1)[0] : d.name));
      const bar = g.append("rect").attr("x", (d) => x(d.a.value)).attr("y", 5).attr("height", rowH - 10).attr("rx", 3)
        .attr("width", (d) => Math.max(4, x(d.z.value) - x(d.a.value)))
        .attr("fill", (d) => (d.current ? "var(--series-2)" : "var(--sport)"));
      Viz.tooltipOn(bar, (d) => {
        const t = el("div");
        t.append(ttTitle(d.name));
        t.append(el("div", null, `First No. 1: ${dateText(d.first)}, aged ${ageText(d.a)}`));
        t.append(el("div", null, `${d.current ? "Still No. 1 on" : "Last No. 1"}: ${dateText(d.last)}, aged ${ageText(d.z)}`));
        return t;
      });
    });

    const tabs = {
      young: { label: "Youngest to reach No. 1", sort: (a, b) => a.a.value - b.a.value, date: "first", age: "a" },
      oldFirst: { label: "Oldest to reach No. 1", sort: (a, b) => b.a.value - a.a.value, date: "first", age: "a" },
      old: { label: "Oldest at No. 1", sort: (a, b) => b.z.value - a.z.value, date: "last", age: "z" },
    };
    const table = (key) => {
      const tab = tabs[key];
      const sorted = rows.slice().sort(tab.sort);
      F.richTable(document.getElementById("no1-table"), [
        { label: "#", cls: "num rank", render: (r) => String(sorted.indexOf(r) + 1) },
        { label: "Player", render: (r) => who(r.name, r.nation) },
        { label: "Age", render: (r) => ageCell(r[tab.age]) },
        { label: key === "old" ? "Last week at No. 1" : "First week at No. 1", cls: "years", render: (r) => dateText(r[tab.date]) + (key === "old" && r.current ? " (current)" : "") },
      ], sorted);
    };
    const host = document.getElementById("no1-tabs");
    if (!host.childElementCount) Viz.segmented("no1-tabs", Object.entries(tabs).map(([key, t]) => ({ key, label: t.label })), "young", (k) => { no1Tab = k; table(k); });
    table(no1Tab);
  }
  let no1Tab = "young";
  renders.push(numberOnes);

  /* ---------- Age scatter (champion's age by year) ---------- */

  function scatter(id, rows, colorOf) {
    chart(id, (width) => {
      const box = d3.select(`#${id}`);
      box.selectAll("*").remove();
      if (!rows.length) return;
      const narrow = width < 600;
      const height = narrow ? 240 : 300;
      const margin = { top: 12, right: 12, bottom: 26, left: 34 };
      const years = d3.extent(rows, (r) => r.year);
      const x = d3.scaleLinear().domain([years[0] - 1, years[1] + 1]).range([margin.left, width - margin.right]);
      const y = d3.scaleLinear().domain([Math.floor(d3.min(rows, (r) => r.age.value)) - 1, Math.ceil(d3.max(rows, (r) => r.age.value)) + 1])
        .range([height - margin.bottom, margin.top]);
      const svg = box.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("width", width).attr("height", height);
      const yt = y.ticks(6);
      svg.append("g").selectAll("line").data(yt).join("line").attr("class", "gridline")
        .attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", (d) => y(d)).attr("y2", (d) => y(d));
      svg.append("g").selectAll("text").data(yt).join("text").attr("class", "tick-label").attr("x", margin.left - 6).attr("y", (d) => y(d) + 4)
        .attr("text-anchor", "end").text((d) => d);
      const xt = x.ticks(narrow ? 5 : 10).filter(Number.isInteger);
      svg.append("g").selectAll("text").data(xt).join("text").attr("class", "tick-label").attr("x", (d) => x(d)).attr("y", height - 6)
        .attr("text-anchor", "middle").text((d) => d);
      const dots = svg.append("g").selectAll("circle").data(rows).join("circle")
        .attr("cx", (r) => x(r.year + (parse(r.date).getUTCMonth() / 12) - 0.5)).attr("cy", (r) => y(r.age.value)).attr("r", narrow ? 3 : 4)
        .attr("fill", colorOf).attr("fill-opacity", 0.85).attr("stroke", "var(--surface)").attr("stroke-width", 1);
      Viz.tooltipOn(dots, (r) => {
        const t = el("div");
        t.append(ttTitle(r.name));
        t.append(el("div", null, `${r.label} · ${dateText(r.date)}`));
        t.append(ttNote(`Aged ${ageText(r.age)}`));
        return t;
      });
    });
  }

  function ageTables(youngId, oldId, rows, eventLabel) {
    const cols = (list) => [
      { label: "#", cls: "num rank", render: (r) => String(list.indexOf(r) + 1) },
      { label: "Player", render: (r) => who(r.name, r.nation) },
      { label: "Age", render: (r) => ageCell(r.age) },
      { label: "Title", cls: "title-cell", render: (r) => eventLabel(r) },
    ];
    const young = perPlayer(rows, false).slice(0, 10);
    const old = perPlayer(rows, true).slice(0, 10);
    F.richTable(document.getElementById(youngId), cols(young), young);
    F.richTable(document.getElementById(oldId), cols(old), old);
  }

  /* ---------- Grand Slams ---------- */

  let slamEvent = "All";
  let slamEra = "all";
  function slams() {
    const rows = T().slams
      .filter((r) => (slamEvent === "All" || r.event === slamEvent) && (slamEra === "all" || r.openEra))
      .map((r) => ({ ...r, age: age(r.born, r.date), label: `${SLAM_NAME[r.event]} ${r.year}` }));
    Viz.legend("slam-legend", slamEvent === "All" ? data.slams.map((s) => ({ label: s.name, color: SLAM_COLOR[s.key] })) : []);
    scatter("slam-chart", rows, (r) => SLAM_COLOR[r.event]);
    ageTables("slam-young", "slam-old", rows, (r) => (slamEvent === "All" ? r.label : String(r.year)));
  }
  Viz.segmented("slam-event", [{ key: "All", label: "All majors" }, ...data.slams.map((s) => ({ key: s.key, label: s.name }))], slamEvent, (k) => {
    slamEvent = k;
    slams();
  });
  Viz.segmented("slam-era", [{ key: "all", label: "All time" }, { key: "open", label: "Open Era" }], slamEra, (k) => {
    slamEra = k;
    slams();
  });
  renders.push(slams);

  /* ---------- ATP / WTA Finals ---------- */

  function finals() {
    const t = T();
    document.getElementById("finals-title").textContent = `${t.finalsName} champions by age`;
    document.getElementById("finals-lede").textContent = `Every champion of the ${t.finalsName}, the season-ending championship for the year's best players, since ${d3.min(t.finals, (r) => r.year)}.`;
    const rows = t.finals.map((r) => ({ ...r, age: age(r.born, r.date), label: `${t.finalsName} ${r.year}` }));
    scatter("finals-chart", rows, () => "var(--sport)");
    ageTables("finals-young", "finals-old", rows, (r) => String(r.year));
  }
  renders.push(finals);

  /* ---------- Career Grand Slam ---------- */

  function careerSlam() {
    const rows = T().careerSlams.map((r) => {
      const titles = data.slams.map((s) => ({ key: s.key, ...r.titles[s.key], age: age(r.born, r.titles[s.key].date) }));
      return { ...r, titles, age: age(r.born, r.date), first: d3.min(titles, (t) => t.date) };
    }).sort((a, b) => a.age.value - b.age.value);
    const label = (r) => (r.set > 1 ? `${r.name} (${r.set === 2 ? "2nd" : r.set === 3 ? "3rd" : `${r.set}th`} time)` : r.name);
    Viz.legend("career-legend", data.slams.map((s) => ({ label: s.name, color: SLAM_COLOR[s.key] })));
    chart("career-chart", (width) => {
      const box = d3.select("#career-chart");
      box.selectAll("*").remove();
      const narrow = width < 600;
      const rowH = 28;
      const margin = { top: 24, right: 16, bottom: 8, left: narrow ? 120 : 230 };
      const height = margin.top + rows.length * rowH + margin.bottom;
      const x = d3.scaleLinear()
        .domain([Math.floor(d3.min(rows, (r) => d3.min(r.titles, (t) => t.age.value))) - 1, Math.ceil(d3.max(rows, (r) => r.age.value)) + 1])
        .range([margin.left, width - margin.right]);
      const svg = box.append("svg").attr("viewBox", `0 0 ${width} ${height}`).attr("width", width).attr("height", height);
      const ticks = x.ticks(narrow ? 5 : 10);
      svg.append("g").selectAll("line").data(ticks).join("line").attr("class", "gridline")
        .attr("x1", (d) => x(d)).attr("x2", (d) => x(d)).attr("y1", margin.top - 4).attr("y2", height - margin.bottom);
      svg.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", (d) => x(d)).attr("y", margin.top - 10)
        .attr("text-anchor", "middle").text((d) => d);
      const g = svg.append("g").selectAll("g").data(rows).join("g").attr("transform", (d, i) => `translate(0 ${margin.top + i * rowH + rowH / 2})`);
      g.append("text").attr("class", "reign-label").attr("x", margin.left - 10).attr("y", 4).attr("text-anchor", "end")
        .text((d) => (narrow ? `${d.name.split(" ").slice(-1)[0]}${d.set > 1 ? ` (${d.set})` : ""}` : label(d)));
      g.append("line").attr("class", "career-span").attr("x1", (d) => x(d3.min(d.titles, (t) => t.age.value))).attr("x2", (d) => x(d.age.value));
      g.selectAll("circle.done").data((d) => [d]).join("circle").attr("class", "done").attr("cx", (d) => x(d.age.value)).attr("r", 8)
        .attr("fill", "none").attr("stroke", (d) => SLAM_COLOR[d.completed]).attr("stroke-width", 2);
      const dots = g.selectAll("circle.title").data((d) => d.titles.map((t) => ({ ...t, row: d }))).join("circle").attr("class", "title")
        .attr("cx", (t) => x(t.age.value)).attr("r", 5).attr("fill", (t) => SLAM_COLOR[t.key]).attr("stroke", "var(--surface)").attr("stroke-width", 1);
      Viz.tooltipOn(dots, (t) => {
        const n = el("div");
        n.append(ttTitle(label(t.row)));
        n.append(el("div", null, `${SLAM_NAME[t.key]} ${t.year}, aged ${ageText(t.age)}`));
        if (t.key === t.row.completed) n.append(ttNote("Completed the career Grand Slam"));
        return n;
      });
    });

    F.richTable(document.getElementById("career-table"), [
      { label: "#", cls: "num rank", render: (r) => String(rows.indexOf(r) + 1) },
      { label: "Player", render: (r) => who(label(r), r.nation) },
      { label: "Completed at", render: (r) => `${SLAM_NAME[r.completed]} ${r.titles.find((t) => t.key === r.completed).year}` },
      { label: "Age", render: (r) => ageCell(r.age) },
      { label: "From first to fourth", short: "Span", cls: "years", render: (r) => {
        const span = age(r.first, r.date);
        return span.years ? `${span.years} y ${span.days} d` : `${span.days} days`;
      } },
      ...data.slams.map((s) => ({ label: SHORT[s.key], cls: "num hide-sm", render: (r) => String(r.titles.find((t) => t.key === s.key).year) })),
    ], rows);
  }
  renders.push(careerSlam);

  renders.forEach((r) => r());
})();
