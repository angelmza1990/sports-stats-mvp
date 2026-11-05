/* The Dakar Rally: every winner in cars, bikes, trucks and quads since 1979. */
(async function () {
  "use strict";

  const raw = await d3.json(document.body.dataset.src);
  const C = Champions(raw, { first: "1978", detailLabel: "Vehicle", detail: (e) => e.vehicle || e.team || "" });
  const { F, events, comps, person } = C;

  const multi = d3.groups(events, (e) => e.winner).filter(([, v]) => new Set(v.map((e) => e.comp)).size > 1)
    .sort((a, b) => b[1].length - a[1].length);
  F.richTable(document.getElementById("multi-table"), [
    { label: "Winner", render: ([id, v]) => F.withSub(person(id), raw.competitions.filter((c) => v.some((e) => e.comp === c.key))
      .map((c) => `${c.label} ${v.filter((e) => e.comp === c.key).map((e) => e.year).join(", ")}`).join(" · ")) },
    { label: "Wins", cls: "num strong", render: ([, v]) => String(v.length) },
  ], multi);

  const arg = events.filter((e) => e.nation === "ARG").reverse();
  F.richTable(document.getElementById("arg-table"), [
    { label: "Year", render: (e) => F.withSub(document.createTextNode(String(e.year)), comps[e.comp].label) },
    { label: "Winner", render: (e) => F.withSub(person(e.winner, e.nation), e.vehicle || e.team || "") },
  ], arg);
  document.getElementById("extras-lede").textContent =
    `${multi.length} winners have won in more than one category. Argentina has ${arg.length} wins, ${arg.filter((e) => e.comp === "quads").length} of them in quads.`;
})();
