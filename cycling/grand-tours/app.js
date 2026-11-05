/* The Grand Tours: every general classification winner of the Tour, the Giro and the Vuelta. */
(async function () {
  "use strict";

  const raw = await d3.json(document.body.dataset.src);
  const seconds = (m) => {
    if (!m || /pt/i.test(m)) return null;
    const part = (re) => +(m.match(re)?.[1] ?? 0);
    const s = part(/(\d+)\s*h/) * 3600 + part(/(\d+)\s*[′']/) * 60 + part(/(\d+)\s*[″"]/);
    return s || null;
  };
  const C = Champions(raw, { detailLabel: "Margin", detail: (e) => e.margin ?? "" });
  const { F, events, comps, name, person } = C;

  // Two Grand Tours in the same season.
  const doubles = d3.groups(events, (e) => `${e.year}|${e.winner}`).filter(([, v]) => v.length > 1).map(([, v]) => v).reverse();
  F.richTable(document.getElementById("doubles-table"), [
    { label: "Year", render: (v) => String(v[0].year) },
    { label: "Rider", render: (v) => F.withSub(person(v[0].winner), v.map((e) => comps[e.comp].label).join(" and ")) },
  ], doubles);

  // Winners of all three, with the year each was first won.
  const triple = d3.groups(events, (e) => e.winner).filter(([, v]) => new Set(v.map((e) => e.comp)).size === 3)
    .map(([id, v]) => ({ id, v, done: d3.max(raw.competitions, (c) => d3.min(v.filter((e) => e.comp === c.key), (e) => e.year)) }))
    .sort((a, b) => a.done - b.done);
  F.richTable(document.getElementById("triple-table"), [
    { label: "Rider", render: (r) => F.withSub(person(r.id), raw.competitions.map((c) => `${c.label.split(" ")[0]} ${r.v.filter((e) => e.comp === c.key).map((e) => e.year).join(", ")}`).join(" · ")) },
    { label: "Completed", cls: "num strong", render: (r) => String(r.done) },
  ], triple);
  document.getElementById("extras-lede").textContent =
    `${doubles.length} times a rider won two Grand Tours in one season; ${triple.length} riders won all three in their career. And the smallest winning margins, in time.`;

  const timed = events.map((e) => ({ ...e, s: seconds(e.margin) })).filter((e) => e.s);
  F.richTable(document.getElementById("closest-table"), [
    { label: "Margin", cls: "num strong", render: (e) => (e.s < 60 ? `${e.s}″` : `${Math.floor(e.s / 60)}′ ${String(e.s % 60).padStart(2, "0")}″`) },
    { label: "Winner", render: (e) => F.withSub(person(e.winner, e.nation), `${e.year} ${comps[e.comp].label}`) },
  ], timed.sort((a, b) => a.s - b.s || a.year - b.year).slice(0, 20));
})();
