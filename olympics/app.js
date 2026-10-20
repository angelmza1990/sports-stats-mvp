/* The Olympic Games: medal tables, hosts and the most decorated athletes, Summer and Winter. */
(async function () {
  "use strict";

  const { el, ttTitle, ttNote } = Viz;
  const data = await d3.json(document.body.dataset.src);
  const nations = data.nations;
  const F = Football({
    nationMode: true,
    clubs: Object.fromEntries(Object.entries(nations).map(([c, n]) => [c, { name: n.name, country: c, crest: null }])),
    countries: nations,
  });
  const MEDALS = ["gold", "silver", "bronze"];
  const COLOR = { gold: "var(--gold)", silver: "var(--silver)", bronze: "var(--bronze)" };
  const cap = (s) => s[0].toUpperCase() + s.slice(1);
  const name = (c) => nations[c]?.name ?? c;
  const SEASONS = [
    { key: "Summer", label: "Summer Games" },
    { key: "Winter", label: "Winter Games" },
    { key: "All", label: "All Games" },
  ];
  const gamesName = (g) => `${g.city} ${g.year}`;
  const label = (g) => `${g.year} ${g.season}`;
  // Ranking of a medal table: golds first, then silvers, then bronzes.
  const byMedals = (a, b) => b[1][0] - a[1][0] || b[1][1] - a[1][1] || b[1][2] - a[1][2];
  const total = (m) => m[0] + m[1] + m[2];
  const ordinal = (n) => n + ((n % 100 >= 11 && n % 100 <= 13) ? "th" : ["th", "st", "nd", "rd"][n % 10] ?? "th");

  let season = "Summer";
  let games = [];
  let race;
  let raceMetric = "gold";

  Viz.legend("alltime-legend", MEDALS.map((m) => ({ label: cap(m), color: COLOR[m] })));

  function medalBar(m, max) {
    const bar = el("div", "medal-bar");
    bar.style.width = `${(total(m) / max) * 100}%`;
    m.forEach((n, i) => {
      if (!n) return;
      const s = el("span");
      s.style.setProperty("--c", COLOR[MEDALS[i]]);
      s.style.flex = String(n);
      bar.append(s);
    });
    return bar;
  }

  const medalCols = (get) => [
    ...MEDALS.map((m, i) => ({ label: cap(m), short: m[0].toUpperCase(), cls: `num${i === 0 ? " strong" : ""}`, render: (r) => String(get(r)[i]) })),
    { label: "Total", cls: "num", render: (r) => String(total(get(r))) },
  ];

  /* ---------- Stat tiles ---------- */

  function stats() {
    document.getElementById("stats").replaceChildren();
    const medalled = new Set(games.flatMap((g) => Object.keys(g.medals)));
    const sums = alltimeRows();
    const top = sums.slice().sort((a, b) => total(b.m) - total(a.m))[0];
    const athletes = data.athletes.filter((a) => season === "All" || a.season === season);
    const best = athletes[0];
    F.statTiles("stats", [
      { label: "Games held", value: String(games.length), detail: `${gamesName(games[0])} to ${gamesName(games[games.length - 1])}` },
      { label: "Nations with a medal", value: String(medalled.size), detail: "teams as they competed" },
      { label: "Most medals", value: d3.format(",")(total(top.m)), detail: name(top.code), club: top.code },
      { label: "Most decorated athlete", value: String(best.gold + best.silver + best.bronze), detail: `${best.name}, ${best.gold} golds` },
    ]);
  }

  /* ---------- Race: medals by nation, Games by Games ---------- */

  function frames() {
    const idx = { gold: [0], all: [0, 1, 2] }[raceMetric];
    const tally = new Map();
    const reached = new Map();
    const out = [{ label: String(games[0].year), event: null, ranked: [] }];
    games.forEach((g, i) => {
      Object.entries(g.medals).forEach(([c, m]) => {
        const n = d3.sum(idx, (j) => m[j]);
        if (!n) return;
        tally.set(c, (tally.get(c) || 0) + n);
        reached.set(c, i);
      });
      const ranked = [...tally].map(([id, n]) => ({ id, n, since: reached.get(id) })).sort((a, b) => b.n - a.n || a.since - b.since).slice(0, 10);
      out.push({ label: season === "All" ? label(g) : String(g.year), event: g, ranked });
    });
    return out;
  }

  /* ---------- All-time medal table ---------- */

  let alltimeSort = "gold";
  function alltimeRows() {
    return Object.entries(data.alltime).map(([code, rec]) => {
      const parts = season === "All" ? ["Summer", "Winter"] : [season];
      const m = MEDALS.map((k) => d3.sum(parts, (p) => rec[p][k]));
      return { code, m, games: d3.sum(parts, (p) => rec[p].games) };
    }).filter((r) => total(r.m) > 0);
  }

  function alltime() {
    const rows = alltimeRows().sort((a, b) => (alltimeSort === "total" ? total(b.m) - total(a.m) || b.m[0] - a.m[0] : byMedals([0, a.m], [0, b.m])));
    const max = d3.max(rows, (r) => total(r.m)) || 1;
    F.richTable(document.getElementById("alltime-table"), [
      { label: "#", cls: "num rank", render: (r) => String(rows.indexOf(r) + 1) },
      { label: "Nation", render: (r) => F.clubLabel(r.code) },
      { label: "Games", cls: "num hide-sm", render: (r) => String(r.games) },
      ...medalCols((r) => r.m),
      { label: "", cls: "hide-sm", render: (r) => medalBar(r.m, max) },
    ], rows);
  }

  /* ---------- Who topped the medal table ---------- */

  function leaders() {
    const strip = document.getElementById("leader-strip");
    strip.replaceChildren();
    const key = el("div", "leader-key");
    const k1 = el("span");
    k1.append(el("i", "host"), document.createTextNode("host nation topped the table"));
    key.append(k1);
    if (season === "All") {
      const k2 = el("span");
      k2.append(el("i", "winter"), document.createTextNode("Winter Games"));
      key.append(k2);
    }
    const tops = games.map((g) => {
      const [code, m] = Object.entries(g.medals).sort(byMedals)[0];
      return { g, code, m };
    });
    tops.forEach(({ g, code, m }) => {
      const chip = el("div", `leader-chip${g.season === "Winter" && season === "All" ? " winter" : ""}${g.host === code ? " host" : ""}`);
      chip.append(el("strong", null, String(g.year)), F.flag(code), el("span", null, `${m[0]} gold`));
      chip.setAttribute("aria-label", `${label(g)}: ${name(code)}, ${m[0]} golds`);
      Viz.tooltipOnNode(chip, (t) => {
        t.append(ttTitle(`${gamesName(g)} · ${g.season}`));
        t.append(ttNote(`${name(code)} topped the table: ${m[0]} gold, ${m[1]} silver, ${m[2]} bronze`));
      });
      strip.append(chip);
    });
    strip.before(key);
    document.querySelectorAll(".leader-key").forEach((n, i, all) => i < all.length - 1 && n.remove());
    const counts = d3.rollups(tops, (v) => v, (t) => t.code).sort((a, b) => b[1].length - a[1].length);
    F.rankList(document.getElementById("leader-counts"), counts.map(([code, v]) => ({
      icon: F.flag(code), label: name(code), value: v.length, color: "var(--gold)",
      second: v.map((t) => t.g.year).slice(-1)[0],
      tip: (t) => { t.append(ttTitle(`${name(code)}: ${v.length} times on top`)); t.append(ttNote(v.map((x) => label(x.g)).join(", "))); },
    })), ["Nation", "Times on top", "Last"]);
  }

  /* ---------- Medal table of every Games ---------- */

  const select = document.getElementById("games-select");
  select.addEventListener("change", () => gamesTable(select.value));
  function fillSelect() {
    select.replaceChildren();
    ["Summer", "Winter"].filter((s) => season === "All" || s === season).forEach((s) => {
      const og = document.createElement("optgroup");
      og.label = `${s} Games`;
      games.filter((g) => g.season === s).slice().reverse().forEach((g) => {
        const o = el("option", null, `${g.year} ${g.city}`);
        o.value = label(g);
        og.append(o);
      });
      select.append(og);
    });
    gamesTable(select.value);
  }

  function gamesTable(key) {
    const g = games.find((x) => label(x) === key) ?? games[games.length - 1];
    const rows = Object.entries(g.medals).sort(byMedals).map(([code, m]) => ({ code, m }));
    const meta = document.getElementById("games-meta");
    meta.replaceChildren();
    if (g.host) meta.append(F.flag(g.host));
    meta.append(document.createTextNode(`${g.season} Games in ${g.city} · ${rows.length} nations won a medal · ${d3.sum(rows, (r) => r.m[0])} golds awarded`));
    const max = d3.max(rows, (r) => total(r.m)) || 1;
    F.richTable(document.getElementById("games-table"), [
      { label: "#", cls: "num rank", render: (r) => String(rows.indexOf(r) + 1) },
      { label: "Nation", render: (r) => (r.code === g.host ? F.withSub(F.clubLabel(r.code), "host") : F.clubLabel(r.code)) },
      ...medalCols((r) => r.m),
      { label: "", cls: "hide-sm", render: (r) => medalBar(r.m, max) },
    ], rows.map((r) => ({ ...r, _rowClass: r.code === g.host ? "split-row" : null })));
  }

  /* ---------- Hosts ---------- */

  function hosts() {
    const rows = games.map((g) => {
      const ranked = Object.entries(g.medals).sort(byMedals);
      const pos = ranked.findIndex(([c]) => c === g.host);
      return { g, pos: pos + 1, m: pos >= 0 ? ranked[pos][1] : null };
    });
    const summary = document.getElementById("hosts-summary");
    summary.replaceChildren();
    const byHost = d3.rollups(rows, (v) => v, (r) => r.g.host).sort((a, b) => b[1].length - a[1].length);
    byHost.forEach(([code, v]) => {
      const chip = el("span", "host-chip");
      chip.append(F.flag(code), el("strong", null, name(code)), document.createTextNode(` ${v.map((r) => r.g.year).join(", ")}`));
      summary.append(chip);
    });
    const upcoming = data.upcoming.filter((u) => season === "All" || u.season === season);
    F.richTable(document.getElementById("hosts-table"), [
      { label: "Games", render: (r) => (r.upcoming ? el("span", "upcoming", `${r.year} ${r.season}`) : F.withSub(el("strong", null, String(r.g.year)), r.g.season)) },
      { label: "City", render: (r) => (r.upcoming ? el("span", "upcoming", `${r.city}, ${r.country}`) : r.g.city) },
      { label: "Host nation", render: (r) => (r.upcoming ? el("span", "upcoming", "to come") : r.g.host ? F.clubLabel(r.g.host) : "–") },
      { label: "Host's place", cls: "num", render: (r) => (r.upcoming ? "" : r.pos ? ordinal(r.pos) : "no medal") },
      { label: "Host's medals", cls: "num hide-sm", render: (r) => (r.upcoming || !r.m ? "" : `${r.m[0]}–${r.m[1]}–${r.m[2]}`) },
    ], [...upcoming.slice().reverse().map((u) => ({ ...u, upcoming: true })), ...rows.slice().reverse()]);
  }

  /* ---------- Most decorated athletes ---------- */

  let athleteSort = "total";
  let gender = "All";
  let sport = "All";
  const sportSelect = document.getElementById("athletes-sport");
  sportSelect.addEventListener("change", () => {
    sport = sportSelect.value;
    athletes();
  });
  function fillSports() {
    const list = data.athletes.filter((a) => season === "All" || a.season === season);
    const sports = d3.rollups(list.flatMap((a) => a.sport.split(" / ")), (v) => v.length, (s) => s).sort((a, b) => b[1] - a[1]);
    sportSelect.replaceChildren(el("option", null, "All sports"));
    sportSelect.firstChild.value = "All";
    sports.forEach(([s, n]) => {
      const o = el("option", null, `${s} (${n})`);
      o.value = s;
      sportSelect.append(o);
    });
    if (!sports.some(([s]) => s === sport)) sport = "All";
    sportSelect.value = sport;
  }

  function athletes() {
    const list = data.athletes
      .filter((a) => (season === "All" || a.season === season) && (gender === "All" || a.gender === gender) && (sport === "All" || a.sport.split(" / ").includes(sport)))
      .map((a) => ({ ...a, total: a.gold + a.silver + a.bronze }))
      .sort((a, b) => (athleteSort === "gold" ? b.gold - a.gold || b.total - a.total : b.total - a.total || b.gold - a.gold))
      .slice(0, 50);
    const who = (a) => {
      const span = el("span", "club");
      a.nations.forEach((c) => span.append(F.flag(c)));
      span.append(document.createTextNode(a.name));
      return F.withSub(span, `${a.sport} · ${a.years}`);
    };
    F.richTable(document.getElementById("athletes-table"), [
      { label: "#", cls: "num rank", render: (a) => String(list.indexOf(a) + 1) },
      { label: "Athlete", render: who },
      { label: "Sport", cls: "hide-sm", render: (a) => a.sport },
      { label: "Games", cls: "years", render: (a) => `${a.years}${season === "All" ? ` · ${a.season}` : ""}` },
      ...MEDALS.map((m, i) => ({ label: cap(m), short: m[0].toUpperCase(), cls: `num${i === 0 ? " strong" : ""}`, render: (a) => String(a[m]) })),
      { label: "Total", cls: "num", render: (a) => String(a.total) },
    ], list);
  }

  /* ---------- Switch between Summer, Winter and all the Games ---------- */

  function render(key) {
    season = key;
    games = data.games.filter((g) => season === "All" || g.season === season);
    stats();
    if (race) race.setFrames(frames());
    else {
      race = F.race(frames(), {
        colorOf: () => "var(--sport)",
        frameMs: 800,
        emptyTicker: "Press play to start with the first Games.",
        ticker: (g) => {
          const [code, m] = Object.entries(g.medals).sort(byMedals)[0];
          return [F.flag(code), el("strong", null, ` ${gamesName(g)}`), document.createTextNode(` · ${g.season} Games · top of the table: ${name(code)} (${m[0]} gold)`)];
        },
      });
    }
    alltime();
    leaders();
    fillSelect();
    hosts();
    fillSports();
    athletes();
  }

  Viz.segmented("race-metric", [{ key: "gold", label: "Gold medals" }, { key: "all", label: "All medals" }], "gold", (k) => {
    raceMetric = k;
    race.setFrames(frames());
  });
  Viz.segmented("alltime-sort", [{ key: "gold", label: "By gold" }, { key: "total", label: "By total" }], "gold", (k) => {
    alltimeSort = k;
    alltime();
  });
  Viz.segmented("athletes-sort", [{ key: "total", label: "Most medals" }, { key: "gold", label: "Most golds" }], "total", (k) => {
    athleteSort = k;
    athletes();
  });
  Viz.segmented("athletes-gender", [{ key: "All", label: "All" }, { key: "M", label: "Men" }, { key: "F", label: "Women" }], "All", (k) => {
    gender = k;
    athletes();
  });
  Viz.segmented("season", SEASONS, "Summer", render);
  render("Summer");

  const src = document.getElementById("sources");
  data.meta.sources.forEach((url, i) => {
    const a = el("a", null, decodeURIComponent(url.split("/wiki/")[1]).replace(/_/g, " "));
    a.href = url;
    src.append(a);
    if (i < data.meta.sources.length - 1) src.append(document.createTextNode(", "));
  });
  document.getElementById("data-through").textContent = `Covers every Games through the ${data.meta.through}.`;
})();
