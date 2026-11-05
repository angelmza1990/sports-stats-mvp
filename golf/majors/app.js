/* Golf's majors: every champion of the Masters, the U.S. Open, The Open and the PGA Championship. */
(async function () {
  "use strict";

  const raw = await d3.json(document.body.dataset.src);
  const C = Champions(raw, {});
  const { F, events, comps, person } = C;

  // The career Grand Slam: all four majors, and the year the set was completed.
  const slam = d3.groups(events, (e) => e.winner).filter(([, v]) => new Set(v.map((e) => e.comp)).size === 4)
    .map(([id, v]) => ({ id, v, done: d3.max(raw.competitions, (c) => d3.min(v.filter((e) => e.comp === c.key), (e) => e.year)) }))
    .sort((a, b) => a.done - b.done);
  F.richTable(document.getElementById("slam-table"), [
    { label: "Golfer", render: (r) => F.withSub(person(r.id), raw.competitions.map((c) => `${c.label} ${r.v.filter((e) => e.comp === c.key).length}`).join(" · ")) },
    { label: "Completed", cls: "num strong", render: (r) => String(r.done) },
    { label: "Majors", cls: "num", render: (r) => String(r.v.length) },
  ], slam);

  const seasons = d3.groups(events, (e) => `${e.year}|${e.winner}`).filter(([, v]) => v.length > 1).map(([, v]) => v)
    .sort((a, b) => b.length - a.length || b[0].year - a[0].year);
  F.richTable(document.getElementById("seasons-table"), [
    { label: "Year", render: (v) => String(v[0].year) },
    { label: "Golfer", render: (v) => F.withSub(person(v[0].winner), v.map((e) => comps[e.comp].label).join(", ")) },
    { label: "Majors", cls: "num strong", render: (v) => String(v.length) },
  ], seasons);
  document.getElementById("extras-lede").textContent =
    `${slam.length} golfers have won all four majors. ${seasons.filter((v) => v.length >= 3).length} times a golfer won three in one year, and ${seasons.filter((v) => v.length === 2).length} times two.`;
})();
