/* Winners pages of the individual sports (cycling's Grand Tours, golf's majors, MotoGP, the Dakar): the race, the
   leaders by person, nation and team, and every winner. Each page passes its own wording and extra columns:

     Champions(raw, {
       first: "1903",                      // the race's empty frame
       detail: (e) => "string",            // the winners table's sub line (margin, vehicle...)
     }) -> { F, raw, name, person, comp, events }
*/
window.Champions = function (raw, opts) {
  "use strict";
  opts = opts || {};

  const { el, ttTitle, ttNote } = Viz;
  const { people, events, competitions, meta } = raw;
  const comps = Object.fromEntries(competitions.map((c) => [c.key, c]));
  const many = competitions.length > 1;
  const unit = meta.unit;

  // One lookup for people, nations and teams (prefixed ids), so the race can switch between them.
  const entities = {};
  Object.entries(people).forEach(([id, p]) => (entities[`p:${id}`] = { name: p.name, country: p.nation, crest: null }));
  Object.keys(raw.countries).forEach((c) => (entities[`n:${c}`] = { name: raw.countries[c].name, country: c, crest: null }));
  events.forEach((e) => e.team && (entities[`t:${e.team}`] = { name: e.team, country: null, crest: null }));
  const F = Football({ clubs: entities, countries: raw.countries });
  const name = (id) => people[id]?.name ?? id;
  const nationName = (c) => raw.countries[c]?.name ?? c;
  const person = (id, nationCode = people[id]?.nation) => {
    const span = el("span", "club");
    span.append(F.flag(nationCode), document.createTextNode(name(id)));
    return span;
  };
  const plural = (n, word = unit) => `${n} ${n === 1 ? word.replace(/s$/, "") : word}`;
  const ranges = (ys) => ys.reduce((out, y) => {
    const last = out[out.length - 1];
    if (last && y === last[1] + 1) last[1] = y;
    else out.push([y, y]);
    return out;
  }, []).map(([p, q]) => (p === q ? String(p) : `${p}–${q}`)).join(", ");

  /* ---------- Stat tiles ---------- */

  const byPerson = d3.rollups(events, (v) => v, (e) => e.winner).sort((a, b) => b[1].length - a[1].length || a[1][0].year - b[1][0].year);
  const byNation = d3.rollups(events, (v) => v.length, (e) => e.nation).sort((a, b) => b[1] - a[1]);
  const latest = events[events.length - 1];
  const [topId, topList] = byPerson[0];
  F.statTiles("stats", [
    { label: many ? "Winners crowned" : "Championships", value: String(events.length), detail: `${events[0].year} to ${meta.through}, ${byPerson.length} different winners` },
    { label: `Most ${unit}`, value: String(topList.length), detail: name(topId) },
    { label: "Leading nation", value: String(byNation[0][1]), detail: `${nationName(byNation[0][0])}, of ${byNation.length} nations` },
    { label: "Latest", value: name(latest.winner).split(" ").slice(-1)[0], detail: `${latest.year}${many ? ` ${comps[latest.comp].label}` : ""}, ${nationName(latest.nation)}` },
  ]);

  /* ---------- Race ---------- */

  const METRICS = [
    { key: "people", label: meta.person === "Rider" ? "Riders" : `${meta.person}s`, id: (e) => `p:${e.winner}`, color: () => "var(--series-1)" },
    { key: "nations", label: "Nations", id: (e) => `n:${e.nation}`, color: () => "var(--series-2)" },
    ...(meta.team ? [{ key: "teams", label: `${meta.team}s`, id: (e) => `t:${e.team}`, color: () => "var(--series-3)" }] : []),
  ];
  const raceState = { comp: "all", metric: "people" };
  const framesFor = () => {
    const metric = METRICS.find((m) => m.key === raceState.metric);
    const list = events.filter((e) => (raceState.comp === "all" || e.comp === raceState.comp) && (metric.key !== "teams" || e.team))
      .map((e) => ({ ...e, champion: metric.id(e) }));
    return F.titleFrames(list, (e) => String(e.year), opts.first ?? String(list[0].year - 1));
  };
  const race = F.race(framesFor(), {
    colorOf: (id) => METRICS.find((m) => m.key === raceState.metric).color(id),
    icons: false,
    emptyTicker: "Press play to start with the first winner.",
    ticker: (e) => [el("strong", null, `${e.year}${many ? ` · ${comps[e.comp].label}` : ""} · ${name(e.winner)}`),
      document.createTextNode(` · ${nationName(e.nation)}${e.team ? ` · ${e.team}` : ""}`)],
    frameMs: many && raceState.comp === "all" ? 380 : 560,
  });
  const rerace = () => {
    d3.selectAll("#race-chart g.row").remove(); // repaint bars in the metric's color
    race.setFrames(framesFor());
  };
  if (many) Viz.segmented("race-comp", [{ key: "all", label: "All" }, ...competitions], "all", (k) => { raceState.comp = k; rerace(); });
  Viz.segmented("race-metric", METRICS, "people", (k) => { raceState.metric = k; rerace(); });

  /* ---------- Leaders ---------- */

  const leaderState = { comp: "all" };
  function renderLeaders() {
    const pick = (e) => leaderState.comp === "all" || e.comp === leaderState.comp;
    const rows = d3.rollups(events.filter(pick), (v) => v, (e) => e.winner)
      .map(([id, list]) => ({ id, list, n: list.length }))
      .sort((a, b) => b.n - a.n || a.list[0].year - b.list[0].year).slice(0, 30);
    let rank = 0;
    rows.forEach((r, i) => (r.rank = i && rows[i - 1].n === r.n ? rank : (rank = i + 1)));
    F.richTable(document.getElementById("people-table"), [
      { label: "#", cls: "num rank", render: (r) => String(r.rank) },
      { label: meta.person, render: (r) => F.withSub(person(r.id), ranges([...new Set(r.list.map((e) => e.year))])) },
      ...(many && leaderState.comp === "all" ? competitions.map((c) => ({
        label: c.label, short: c.short ?? c.label.split(" ")[0], cls: "num hide-sm", render: (r) => String(r.list.filter((e) => e.comp === c.key).length || "–"),
      })) : []),
      { label: "Total", cls: "num strong", render: (r) => String(r.n) },
    ], rows);
    const nations = d3.rollups(events.filter(pick), (v) => v, (e) => e.nation).sort((a, b) => b[1].length - a[1].length).slice(0, 20);
    F.rankList(document.getElementById("nations-list"), nations.map(([c, list]) => ({
      icon: F.flag(c), label: nationName(c), value: list.length, second: `${new Set(list.map((e) => e.winner)).size} winners`, color: "var(--series-2)",
      tip: (t) => t.append(ttTitle(nationName(c)), ttNote(d3.rollups(list, (v) => v.length, (e) => e.winner).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([id, n]) => `${name(id)} ${n}`).join(" · "))),
    })), ["Nation", unit[0].toUpperCase() + unit.slice(1), ""]);
    if (meta.team) {
      const teams = d3.rollups(events.filter((e) => pick(e) && e.team), (v) => v, (e) => e.team).sort((a, b) => b[1].length - a[1].length).slice(0, 20);
      F.rankList(document.getElementById("teams-list"), teams.map(([t, list]) => ({
        icon: el("span"), label: t, value: list.length, second: ranges([...new Set(list.map((e) => e.year))]).split(", ").slice(-1)[0], color: "var(--series-3)",
        tip: (tt) => tt.append(ttTitle(t), ttNote(`${plural(list.length)}: ${ranges([...new Set(list.map((e) => e.year))])}`)),
      })), [meta.team, unit[0].toUpperCase() + unit.slice(1), "Last"]);
    }
  }
  if (many) Viz.segmented("leaders-comp", [{ key: "all", label: "All" }, ...competitions], "all", (k) => { leaderState.comp = k; renderLeaders(); });
  renderLeaders();

  /* ---------- Every winner ---------- */

  function renderWinners(comp) {
    const list = events.filter((e) => comp === "all" || e.comp === comp).slice().reverse();
    F.richTable(document.getElementById("winners-table"), [
      { label: "Year", render: (e) => (many && comp === "all" ? F.withSub(document.createTextNode(String(e.year)), comps[e.comp].label) : String(e.year)) },
      { label: meta.person, render: (e) => {
        const nth = events.filter((x) => x.winner === e.winner && (x.year < e.year || (x.year === e.year && events.indexOf(x) <= events.indexOf(e)))).length;
        return F.withSub(person(e.winner, e.nation), [nationName(e.nation), nth > 1 ? `${nth}${["th", "st", "nd", "rd"][nth % 10 > 3 || [11, 12, 13].includes(nth % 100) ? 0 : nth % 10]} ${unit.replace(/s$/, "")}` : null].filter(Boolean).join(" · "));
      } },
      ...(opts.detail ? [{ label: opts.detailLabel ?? "", cls: "hide-sm", render: (e) => opts.detail(e) ?? "" }] : []),
    ], list);
  }
  if (many) Viz.segmented("winners-comp", [{ key: "all", label: "All" }, ...competitions], "all", renderWinners);
  renderWinners("all");
  document.getElementById("data-through").textContent = `Covers every winner through ${meta.through}.`;

  return { F, raw, name, person, nationName, comps, events, plural, ranges };
};
