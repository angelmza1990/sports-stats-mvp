/* National league champions (Serie A, La Liga, English top flight, Ligue 1, Bundesliga, Brasileirão).
   The page sets data-src. data.meta.eras holds at most one "modern era" split (e.g. the Premier League since 1992). */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote } = Viz;
  const data = await d3.json(document.body.dataset.src);
  const F = Football(data);
  const { clubName } = F;
  const titles = data.titles;
  const ERA = data.meta.eras[0]; // undefined when the league has a single era

  const ERAS = [{ key: "all", label: "All eras", test: () => true }];
  if (ERA) {
    ERAS.push({ key: "modern", label: ERA.label, test: (t) => t.era === "modern" });
    ERAS.push({ key: "early", label: ERA.early, test: (t) => t.era === "early" });
  }
  const eraBy = Object.fromEntries(ERAS.map((e) => [e.key, e]));
  const seasonLabel = (t) => t.season;

  /* ---------- Stat tiles ---------- */

  const counts = d3.rollup(titles, (v) => v.length, (t) => t.champion);
  const [leader, leaderN] = d3.greatest(counts, (d) => d[1]);
  const topScorer = data.alltimeScorers[0];
  const tiles = [
    { label: "League titles awarded", value: String(titles.length), detail: `${titles[0].season} to ${titles[titles.length - 1].season}` },
    { label: "Most titles", value: String(leaderN), detail: clubName(leader), club: leader },
  ];
  if (ERA) {
    const modern = d3.rollup(titles.filter(eraBy.modern.test), (v) => v.length, (t) => t.champion);
    const [mLeader, mN] = d3.greatest(modern, (d) => d[1]);
    tiles.push({ label: `Most titles, ${ERA.label.replace(/^Since/, "since")}`, value: String(mN), detail: clubName(mLeader), club: mLeader });
  } else {
    tiles.push({ label: "Different champions", value: String(counts.size), detail: `${d3.sum(counts.values(), (n) => n === 1)} won it once` });
  }
  tiles.push({ label: "All-time top scorer", value: String(topScorer.goals), detail: topScorer.player });
  F.statTiles("stats", tiles);

  /* ---------- Bar chart race with an era switch ---------- */

  const framesFor = (key) => {
    const list = titles.filter(eraBy[key].test);
    return F.titleFrames(list, seasonLabel, String(list[0].year));
  };
  const race = F.race(framesFor("all"), {
    colorOf: () => "var(--series-1)",
    emptyTicker: `Press play to start with the first championship, ${titles[0].season}.`,
    ticker: (t) => [F.crest(t.champion), el("strong", null, `${t.season} · ${clubName(t.champion)}`),
      document.createTextNode(t.runnerUp ? `, ahead of ${clubName(t.runnerUp)}` : "")],
    frameMs: 380,
  });
  if (ERA) Viz.segmented("race-era", ERAS.slice(0, 2), "all", (k) => race.setFrames(framesFor(k)));
  else document.getElementById("race-era").remove();

  /* ---------- Sections scoped by the era filter ---------- */

  const seasonsText = (list) => list.map((t) => t.season).join(", ") || "–";
  const eraTag = (t) => el("span", `era-tag ${t.era === "modern" ? "professional" : ""}`, t.era === "modern" ? ERA.tag : ERA.earlyTag);

  function render(key) {
    const list = titles.filter(eraBy[key].test);
    const ids = new Set(list.flatMap((t) => [t.champion, t.runnerUp]).filter(Boolean));
    const rows = [...ids].map((id) => ({
      id,
      won: list.filter((t) => t.champion === id),
      lost: list.filter((t) => t.runnerUp === id),
    })).filter((r) => r.won.length)
      .sort((a, b) => b.won.length - a.won.length || b.lost.length - a.lost.length || d3.ascending(clubName(a.id), clubName(b.id)));
    F.richTable(document.getElementById("clubs-table"), [
      { label: "Club", render: (r) => F.withSub(F.clubLabel(r.id), `Won: ${seasonsText(r.won)}`) },
      { label: "Titles", cls: "num strong", render: (r) => String(r.won.length) },
      ...(ERA && key === "all" ? [
        { label: ERA.early, short: ERA.earlyTag, cls: "num hide-sm", render: (r) => String(r.won.filter((t) => t.era === "early").length) },
        { label: ERA.label, short: ERA.tag, cls: "num hide-sm", render: (r) => String(r.won.filter((t) => t.era === "modern").length) },
      ] : []),
      { label: "Runners-up", short: "R-up", cls: "num", render: (r) => String(r.lost.length) },
      { label: "Seasons won", cls: "years", render: (r) => seasonsText(r.won) },
    ], rows);

    F.richTable(document.getElementById("seasons-table"), [
      { label: "Season", render: (t) => t.season },
      { label: "Champion", render: (t) => F.clubLabel(t.champion) },
      { label: "Runner-up", cls: "hide-sm", render: (t) => (t.runnerUp ? F.clubLabel(t.runnerUp) : "–") },
      ...(ERA ? [{ label: "Era", cls: "hide-sm", render: eraTag }] : []),
    ], list.slice().reverse());
  }

  if (ERA) {
    Viz.segmented("era-filter", ERAS, "all", render);
  } else {
    document.getElementById("era-bar").remove();
  }
  render("all");

  /* ---------- All-time table ---------- */

  (function allTime() {
    const section = document.getElementById("alltime");
    if (!data.alltime.length) {
      section.remove();
      return;
    }
    const rows = data.alltime.slice().sort((a, b) => b.pts - a.pts || (b.gf - b.ga) - (a.gf - a.ga));
    const has = (k) => rows.some((r) => r[k] != null);
    const sign = (n) => (n > 0 ? `+${n}` : String(n));
    document.getElementById("alltime-note").textContent = `${data.meta.alltimePeriod}: ${rows.length} clubs. ${data.meta.alltimeNote}`;
    F.richTable(document.getElementById("alltime-table"), [
      { label: "#", cls: "num rank", render: (r) => String(rows.indexOf(r) + 1) },
      { label: "Club", render: (r) => F.clubLabel(r.club) },
      ...(has("seasons") ? [{ label: "Seasons", short: "S", cls: "num hide-sm", render: (r) => String(r.seasons ?? "–") }] : []),
      { label: "Played", short: "P", cls: "num", render: (r) => String(r.pld) },
      { label: "W", cls: "num", render: (r) => String(r.w) },
      { label: "D", cls: "num", render: (r) => String(r.d) },
      { label: "L", cls: "num", render: (r) => String(r.l) },
      ...(has("gf") ? [
        { label: "GF", cls: "num hide-sm", render: (r) => String(r.gf) },
        { label: "GA", cls: "num hide-sm", render: (r) => String(r.ga) },
        { label: "GD", cls: "num hide-sm", render: (r) => sign(r.gf - r.ga) },
      ] : []),
      { label: "Titles", cls: "num", render: (r) => String(counts.get(r.club) ?? 0) },
      { label: "Points", short: "Pts", cls: "num strong", render: (r) => String(r.pts) },
    ], rows);
    const src = document.getElementById("alltime-source");
    src.href = data.meta.alltimeSource;
  })();

  /* ---------- Top scorers ---------- */

  (function scorers() {
    const list = data.scorers;
    const byClub = d3.rollups(list.flatMap((sc) => sc.clubs.map((c) => ({ ...sc, club: c }))), (v) => v, (d) => d.club)
      .sort((a, b) => b[1].length - a[1].length).slice(0, 12);
    F.rankList(document.getElementById("scorer-clubs"), byClub.map(([club, v]) => ({
      icon: F.crest(club), label: clubName(club), value: v.length, second: new Set(v.map((d) => d.player)).size,
      tip: (t) => {
        t.append(ttTitle(`${clubName(club)}: ${v.length} top scorers`));
        t.append(ttNote(v.map((d) => `${d.season} ${d.player} (${d.goals})`).join(" · ")));
      },
    })), ["Club", "Times", "Players"]);

    const byPlayer = d3.rollups(list, (v) => v, (d) => d.player)
      .sort((a, b) => b[1].length - a[1].length || d3.max(b[1], (d) => d.goals) - d3.max(a[1], (d) => d.goals)).slice(0, 12);
    F.rankList(document.getElementById("scorer-players"), byPlayer.map(([player, v]) => ({
      icon: F.flag(v[0].nation), label: player, value: v.length, second: d3.max(v, (d) => d.goals),
      tip: (t) => {
        t.append(ttTitle(player));
        v.forEach((d) => t.append(Viz.ttRow("var(--ink-2)", d.goals, `${d.season} · ${d.clubs.map(clubName).join(" / ")}`)));
      },
    })), ["Player", "Titles", "Best"]);

    const playerCell = (name, nation, sub) => {
      const span = el("span", "club");
      if (nation) span.append(F.flag(nation));
      span.append(document.createTextNode(name));
      return sub ? F.withSub(span, sub) : span;
    };
    const clubsCell = (ids) => {
      const wrap = el("div", "stack-clubs");
      ids.forEach((c) => wrap.append(F.clubLabel(c)));
      return wrap;
    };
    const hasMatches = list.some((d) => d.matches);
    const views = {
      season: () => F.richTable(document.getElementById("scorers-table"), [
        { label: "Season", render: (d) => d.season },
        { label: "Top scorer", render: (d) => playerCell(d.player, d.nation, d.clubs.map(clubName).join(" / ")) },
        { label: "Club", cls: "hide-sm", render: (d) => clubsCell(d.clubs) },
        { label: "Goals", cls: "num strong", render: (d) => String(d.goals) },
        ...(hasMatches ? [{ label: "Matches", short: "M", cls: "num hide-sm", render: (d) => (d.matches ? String(d.matches) : "–") }] : []),
      ], list.slice().reverse()),
      alltime: () => F.richTable(document.getElementById("scorers-table"), [
        { label: "#", cls: "num rank", render: (d) => String(data.alltimeScorers.indexOf(d) + 1) },
        { label: "Player", render: (d) => playerCell(d.player, d.nation) },
        { label: "Career", cls: "years", render: (d) => d.career },
        { label: "Goals", cls: "num strong", render: (d) => String(d.goals) },
        { label: "Matches", short: "M", cls: "num", render: (d) => String(d.matches ?? "–") },
        { label: "Per match", short: "Ratio", cls: "num", render: (d) => (d.matches ? (d.goals / d.matches).toFixed(2) : "–") },
      ], data.alltimeScorers),
    };
    Viz.segmented("scorers-tabs", [{ key: "season", label: "Every season" }, { key: "alltime", label: "All-time scorers" }], "season", (k) => views[k]());
    views.season();
  })();

  document.getElementById("data-through").textContent = `Covers every title through ${data.meta.through}.`;
})();
