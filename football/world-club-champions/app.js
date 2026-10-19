/* World Club Champions: Intercontinental Cup + FIFA Club World Cup + FIFA Intercontinental Cup. */
(async function () {
  "use strict";

  const { el } = Viz;
  const data = await d3.json(document.body.dataset.src);
  const F = Football(data);
  const { clubName, countryName, scoreText } = F;
  const all = data.finals;
  const COMPS = data.meta.competitions; // {IC: "Intercontinental Cup", ...}
  const SHORT = { IC: "IC", CWC: "CWC", FIC: "FIC" };

  const CONFEDS = ["UEFA", "CONMEBOL", "CONCACAF", "AFC", "CAF", "OFC"];
  const CONFED_NAMES = {
    UEFA: "Europe (UEFA)", CONMEBOL: "South America (CONMEBOL)", CONCACAF: "North & Central America (CONCACAF)",
    AFC: "Asia (AFC)", CAF: "Africa (CAF)", OFC: "Oceania (OFC)",
  };
  const CONFED_COLOR = { UEFA: "var(--series-1)", CONMEBOL: "var(--series-2)" };
  const confedColor = (c) => CONFED_COLOR[c] ?? "var(--ink-muted)";
  const confedOfClub = new Map(all.flatMap((f) => [[f.champion, f.championConfederation], [f.runnerUp, f.runnerUpConfederation]]));
  const finalLabel = (f) => `${f.year} ${SHORT[f.competition]}`;
  // West German clubs count for Germany in country totals.
  const nation = (code) => ({ FRG: "GER" })[code] ?? code;

  /* ---------- Stat tiles ---------- */

  const titles = d3.rollup(all, (v) => v.length, (f) => f.champion);
  const [leader, leaderN] = d3.greatest(titles, (d) => d[1]);
  const byConfed = d3.rollup(all, (v) => v.length, (f) => f.championConfederation);
  F.statTiles("stats", [
    { label: "World titles awarded", value: String(all.length), detail: [...d3.rollup(all, (v) => v.length, (f) => f.competition)].map(([k, n]) => `${n} ${SHORT[k]}`).join(" · ") },
    { label: "Different champions", value: String(titles.size), detail: `from ${new Set(all.map((f) => nation(f.championCountry))).size} countries` },
    { label: "Most titles", value: String(leaderN), detail: clubName(leader), club: leader },
    { label: "Europe vs South America", value: `${byConfed.get("UEFA") ?? 0}–${byConfed.get("CONMEBOL") ?? 0}`, detail: "titles by confederation" },
  ]);

  /* ---------- Bar chart race (all competitions) ---------- */

  Viz.legend("race-legend", [
    { label: "Europe (UEFA)", color: CONFED_COLOR.UEFA },
    { label: "South America (CONMEBOL)", color: CONFED_COLOR.CONMEBOL },
  ]);
  F.race(F.titleFrames(all, finalLabel, String(all[0].year)), {
    colorOf: (id) => confedColor(confedOfClub.get(id)),
    emptyTicker: "Press play to start with the first Intercontinental Cup, 1960.",
    ticker: (f) => [F.crest(f.champion), el("strong", null, `${f.year} ${COMPS[f.competition]} · ${clubName(f.champion)}`),
      document.createTextNode(` def. ${clubName(f.runnerUp)}, ${scoreText(f)}`)],
  });

  /* ---------- Sections scoped by the competition filter ---------- */

  function render(scope) {
    const finals = scope === "ALL" ? all : all.filter((f) => f.competition === scope);
    const compsInScope = scope === "ALL" ? Object.keys(COMPS) : [scope];

    // Titles by club
    const ids = new Set(finals.flatMap((f) => [f.champion, f.runnerUp]));
    const rows = [...ids].map((id) => ({ id, won: finals.filter((f) => f.champion === id), lost: finals.filter((f) => f.runnerUp === id) }))
      .sort((a, b) => b.won.length - a.won.length || b.lost.length - a.lost.length || d3.ascending(clubName(a.id), clubName(b.id)));
    const years = (list) => list.map(finalLabel).join(", ") || "–";
    F.richTable(document.getElementById("clubs-table"), [
      { label: "Club", render: (r) => F.withSub(F.clubLabel(r.id, true), `Won: ${years(r.won)} · Lost: ${years(r.lost)}`) },
      { label: "Titles", cls: "num strong", render: (r) => String(r.won.length) },
      ...(compsInScope.length > 1 ? compsInScope.map((c) => ({ label: SHORT[c], cls: "num hide-sm", render: (r) => String(r.won.filter((f) => f.competition === c).length) })) : []),
      { label: "Runners-up", short: "R-up", cls: "num", render: (r) => String(r.lost.length) },
      { label: "Won", cls: "years", render: (r) => years(r.won) },
      { label: "Lost", cls: "years", render: (r) => years(r.lost) },
    ], rows);

    // Confederations
    const confedGroups = CONFEDS.map((c) => {
      const won = finals.filter((f) => f.championConfederation === c);
      const icon = el("i", "confed-key");
      icon.style.setProperty("--c", confedColor(c));
      return {
        label: CONFED_NAMES[c], icon, won,
        lost: finals.filter((f) => f.runnerUpConfederation === c),
        winners: d3.groups(won, (f) => f.champion).sort((a, b) => b[1].length - a[1].length),
      };
    }).filter((g) => g.won.length || g.lost.length);
    F.groupRows(document.getElementById("confederations-list"), confedGroups, "Confederation");

    const versus = document.getElementById("versus");
    versus.replaceChildren();
    const side = (c, right) => {
      const n = finals.filter((f) => f.championConfederation === c).length;
      const box = el("div", `side${right ? " right" : ""}`);
      const name = el("div", "name");
      const key = el("i");
      key.style.setProperty("--c", confedColor(c));
      if (right) name.append(document.createTextNode(CONFED_NAMES[c]), key);
      else name.append(key, document.createTextNode(CONFED_NAMES[c]));
      box.append(name, el("div", "big", String(n)));
      return box;
    };
    versus.append(side("UEFA"), el("div", "mid", `${finals.length} finals`), side("CONMEBOL", true));

    // Countries
    const codes = new Set(finals.flatMap((f) => [nation(f.championCountry), nation(f.runnerUpCountry)]));
    const countryGroups = [...codes].map((code) => {
      const won = finals.filter((f) => nation(f.championCountry) === code);
      return {
        label: countryName(code), icon: F.flag(code), won,
        lost: finals.filter((f) => nation(f.runnerUpCountry) === code),
        winners: d3.groups(won, (f) => f.champion).sort((a, b) => b[1].length - a[1].length),
      };
    }).sort((a, b) => b.won.length - a.won.length || b.lost.length - a.lost.length);
    document.getElementById("country-note").textContent =
      `${countryGroups.filter((g) => g.won.length).length} countries have produced a world champion and ${countryGroups.length} have reached a final. West Germany is counted with Germany.`;
    F.groupRows(document.getElementById("countries-list"), countryGroups, "Country");

    // Repeated finals and every final
    F.repeatedFinals(document.getElementById("pairs-list"), finals, (f) => `${finalLabel(f)} ${clubName(f.champion)} (${scoreText(f)})`);
    F.richTable(document.getElementById("finals-table"), [
      { label: "Year", render: (f) => String(f.year) },
      { label: "Competition", short: "Comp.", render: (f) => SHORT[f.competition] },
      { label: "Champion", render: (f) => F.clubLabel(f.champion, true) },
      { label: "Score", cls: "score", render: (f) => scoreText(f) },
      { label: "Runner-up", render: (f) => F.clubLabel(f.runnerUp, true) },
    ], finals.slice().reverse());
  }

  Viz.segmented("competition-filter", [
    { key: "ALL", label: "All" },
    ...Object.entries(COMPS).map(([key, label]) => ({ key, label })),
  ], "ALL", render);
  render("ALL");

  document.getElementById("data-through").textContent = `Covers every final through ${data.meta.through}.`;
})();
