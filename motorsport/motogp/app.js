/* MotoGP: every premier-class world champion since 1949. */
(async function () {
  "use strict";

  const raw = await d3.json(document.body.dataset.src);
  const C = Champions(raw, { detailLabel: "Constructor", detail: (e) => `${e.team}${e.wins != null ? ` · ${e.wins} wins` : ""}` });
  const { F, events, person } = C;

  const share = events.filter((e) => e.wins != null && e.races).map((e) => ({ ...e, p: e.wins / e.races }));
  F.richTable(document.getElementById("dominant-table"), [
    { label: "Year", render: (e) => String(e.year) },
    { label: "Champion", render: (e) => F.withSub(person(e.winner, e.nation), `${e.team} · ${e.wins} of ${e.races} Grands Prix`) },
    { label: "Won", cls: "num strong", render: (e) => `${Math.round(e.p * 100)}%` },
  ], share.sort((a, b) => b.p - a.p || b.wins - a.wins).slice(0, 20));
  const least = share.slice().sort((a, b) => a.p - b.p)[0];
  document.getElementById("extras-lede").textContent =
    `The champions who won the biggest share of the season's Grands Prix. At the other end, ${C.name(least.winner)} won the ${least.year} title with ${least.wins} win${least.wins === 1 ? "" : "s"} in ${least.races} races.`;
})();
