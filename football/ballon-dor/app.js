/* Ballon d'Or: every winner since 1956. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote } = Viz;
  const raw = await d3.json(document.body.dataset.src);
  const winners = raw.winners;
  const slug = (s) => s.normalize("NFKD").replace(/[^\w]+/g, "-").toLowerCase();

  // One lookup for everything the race can rank: players, nations and clubs (prefixed ids).
  const entities = {};
  winners.forEach((w) => (entities[`p:${slug(w.player)}`] = { name: w.player, country: w.nation, crest: null }));
  Object.entries(raw.countries).forEach(([code, c]) => (entities[`n:${code}`] = { name: c.name, country: code, crest: null }));
  Object.entries(raw.clubs).forEach(([id, c]) => (entities[`c:${id}`] = { ...c }));
  const F = Football({ ...raw, clubs: { ...raw.clubs, ...entities } });
  const clubName = (id) => raw.clubs[id]?.name ?? id;
  const countryName = F.countryName;

  /* ---------- Stat tiles ---------- */

  const wins = d3.rollup(winners, (v) => v.length, (w) => w.player);
  const [leader, leaderN] = d3.greatest(wins, (d) => d[1]);
  const nations = d3.rollup(winners, (v) => v.length, (w) => w.nation);
  const [topNation, topNationN] = d3.greatest(nations, (d) => d[1]);
  const clubWins = d3.rollup(winners, (v) => v.length, (w) => w.club);
  const [topClub, topClubN] = d3.greatest(clubWins, (d) => d[1]);
  F.statTiles("stats", [
    { label: "Awards", value: String(winners.length), detail: `${winners[0].year} to ${winners[winners.length - 1].year}, ${wins.size} different winners` },
    { label: "Most wins", value: String(leaderN), detail: leader },
    { label: "Nations", value: String(nations.size), detail: `${countryName(topNation)} leads with ${topNationN}` },
    { label: "Club with most winners", value: String(topClubN), detail: clubName(topClub), club: topClub },
  ]);

  /* ---------- Bar chart race ---------- */

  const GROUPS = {
    player: { label: "Players", key: (w) => `p:${slug(w.player)}` },
    nation: { label: "Nationalities", key: (w) => `n:${w.nation}` },
    club: { label: "Club at the time", key: (w) => `c:${w.club}` },
    academy: { label: "Youth academy", key: (w) => (w.academy ? `c:${w.academy}` : null) },
  };
  const framesFor = (group) => F.titleFrames(
    winners.map((w) => ({ ...w, champion: GROUPS[group].key(w) })).filter((w) => w.champion),
    (w) => String(w.year), String(winners[0].year));
  const race = F.race(framesFor("player"), {
    colorOf: () => "var(--series-4)",
    icons: false,
    emptyTicker: "Press play to start with the first Ballon d'Or, 1956.",
    ticker: (w) => [F.flag(w.nation), el("strong", null, ` ${w.year} · ${w.player}`),
      document.createTextNode(` · ${clubName(w.club)}${w.academy ? ` · formed at ${clubName(w.academy)}` : ""}`)],
    frameMs: 650,
  });
  Viz.segmented("race-metric", Object.entries(GROUPS).map(([key, g]) => ({ key, label: g.label })), "player",
    (k) => race.setFrames(framesFor(k)));

  /* ---------- Every winner ---------- */

  const crestLabel = (id) => {
    const span = el("span", "club");
    span.append(F.crest(`c:${id}`), document.createTextNode(clubName(id)));
    return span;
  };
  F.richTable(document.getElementById("winners-table"), [
    { label: "Year", render: (w) => String(w.year) },
    {
      label: "Winner", render: (w) => {
        const span = el("span", "club");
        span.append(F.flag(w.nation), document.createTextNode(w.player));
        return F.withSub(span, `${clubName(w.club)} · formed at ${w.academy ? clubName(w.academy) : "–"}`);
      },
    },
    { label: "Nationality", cls: "hide-sm", render: (w) => countryName(w.nation) },
    { label: "Club", cls: "hide-sm", render: (w) => crestLabel(w.club) },
    { label: "Youth academy", cls: "hide-sm", render: (w) => (w.academy ? crestLabel(w.academy) : "–") },
    { label: "Youth career", cls: "years", render: (w) => w.youth.map((y) => `${y.name}${y.years ? ` (${y.years})` : ""}`).join(" → ") || "–" },
  ], winners.slice().reverse());

  /* ---------- Nations, clubs and academies ---------- */

  function breakdown(rootId, keyOf, iconOf, labelOf, header) {
    const groups = d3.groups(winners.filter((w) => keyOf(w)), keyOf)
      .sort((a, b) => b[1].length - a[1].length || new Set(b[1].map((w) => w.player)).size - new Set(a[1].map((w) => w.player)).size);
    F.rankList(document.getElementById(rootId), groups.map(([key, list]) => {
      const players = d3.rollups(list, (v) => v.map((w) => w.year), (w) => w.player).sort((a, b) => b[1].length - a[1].length);
      return {
        icon: iconOf(key), label: labelOf(key), value: list.length, second: players.length, color: "var(--series-4)",
        tip: (t) => {
          t.append(ttTitle(`${labelOf(key)}: ${list.length} ${list.length === 1 ? "award" : "awards"}`));
          players.forEach(([p, ys]) => t.append(Viz.ttRow("var(--series-4)", ys.length, `${p} (${ys.join(", ")})`)));
        },
      };
    }), [header, "Awards", "Winners"]);
  }
  breakdown("by-nation", (w) => w.nation, (c) => F.flag(c), countryName, "Nation");
  breakdown("by-club", (w) => w.club, (c) => F.crest(`c:${c}`), clubName, "Club");
  breakdown("by-academy", (w) => w.academy, (c) => F.crest(`c:${c}`), clubName, "Academy");

  const formedAtClub = winners.filter((w) => w.academy && w.academy === w.club).length;
  document.getElementById("academy-note").textContent =
    `${formedAtClub} of ${winners.length} awards went to a player who won it at the club that formed him.`;
  document.getElementById("data-through").textContent = `Covers every award through ${raw.meta.through}.`;
})();
