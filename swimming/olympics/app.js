/* Olympic swimming: medals by nation and swimmer, and the podium of every event. */
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
  const STROKES = ["Freestyle", "Backstroke", "Breaststroke", "Butterfly", "Medley", "Relay"];
  const name = (c) => nations[c]?.name ?? c;
  const nationOf = (slot) => slot.team ?? slot.swimmers[0].nation;
  const GENDERS = [
    { key: "Men", label: "Men", test: (e) => e.gender === "Men" },
    { key: "Women", label: "Women", test: (e) => e.gender === "Women" },
    { key: "All", label: "All events (incl. mixed relay)", test: () => true },
  ];

  let scope = GENDERS[0];
  let events = [];
  let race;
  let stroke = "All";

  Viz.legend("medals-legend", MEDALS.map((m) => ({ label: m[0].toUpperCase() + m.slice(1), color: COLOR[m] })));

  /** Every medal in the events: {event, year, medal, slot}. */
  const medals = (list) => list.flatMap((ev) => ev.results.flatMap((r) => MEDALS.flatMap((m) => r[m].map((slot) => ({ ev, r, medal: m, slot })))));

  /* ---------- Stat tiles ---------- */

  function stats() {
    document.getElementById("stats").replaceChildren();
    const all = medals(events);
    const golds = all.filter((x) => x.medal === "gold");
    const goldNations = d3.rollup(golds, (v) => v.length, (x) => nationOf(x.slot));
    const [topNation, topN] = d3.greatest(goldNations, (d) => d[1]);
    const swimmers = data.swimmers.filter((s) => scope.key === "All" || s.gender === scope.key);
    const best = swimmers.slice().sort((a, b) => b.gold - a.gold || b.silver - a.silver)[0];
    F.statTiles("stats", [
      { label: "Events on the programme", value: String(events.filter((e) => e.current).length), detail: `plus ${events.filter((e) => !e.current).length} discontinued` },
      { label: "Gold medals awarded", value: String(golds.length), detail: `${goldNations.size} nations have won one` },
      { label: "Most gold medals", value: String(topN), detail: name(topNation), club: topNation },
      { label: "Most golds by a swimmer", value: String(best.gold), detail: `${best.name} (${best.gold + best.silver + best.bronze} medals)` },
    ]);
  }

  /* ---------- Race: gold medals by nation, Games by Games ---------- */

  function frames() {
    const games = [...new Set(events.flatMap((e) => e.results.map((r) => r.year)))].sort((a, b) => a - b);
    const tally = new Map();
    const reached = new Map();
    const out = [{ label: String(games[0]), event: null, ranked: [] }];
    games.forEach((year, i) => {
      const won = d3.rollup(medals(events).filter((x) => x.r.year === year && x.medal === "gold"), (v) => v.length, (x) => nationOf(x.slot));
      won.forEach((n, c) => {
        tally.set(c, (tally.get(c) || 0) + n);
        reached.set(c, i);
      });
      const ranked = [...tally].map(([id, n]) => ({ id, n, since: reached.get(id) })).sort((a, b) => b.n - a.n || a.since - b.since).slice(0, 10);
      const top = d3.greatest(won, (d) => d[1]);
      const city = events.flatMap((e) => e.results).find((r) => r.year === year)?.city ?? "";
      out.push({ label: String(year), event: { year, city, top }, ranked });
    });
    return out;
  }

  /* ---------- Medal table ---------- */

  function medalTable() {
    const list = medals(events.filter((e) => stroke === "All" || e.stroke === stroke));
    const rows = d3.rollups(list, (v) => Object.fromEntries(MEDALS.map((m) => [m, v.filter((x) => x.medal === m).length])), (x) => nationOf(x.slot))
      .map(([nation, c]) => ({ nation, ...c, total: c.gold + c.silver + c.bronze }))
      .sort((a, b) => b.gold - a.gold || b.silver - a.silver || b.bronze - a.bronze);
    const maxT = d3.max(rows, (r) => r.total) || 1;
    F.richTable(document.getElementById("medals-table"), [
      { label: "#", cls: "num rank", render: (r) => String(rows.indexOf(r) + 1) },
      { label: "Nation", render: (r) => F.clubLabel(r.nation) },
      ...MEDALS.map((m) => ({ label: m[0].toUpperCase() + m.slice(1), short: m[0].toUpperCase(), cls: `num${m === "gold" ? " strong" : ""}`, render: (r) => String(r[m]) })),
      { label: "Total", cls: "num", render: (r) => String(r.total) },
      {
        label: "", cls: "hide-sm", render: (r) => {
          const bar = el("div", "medal-bar");
          bar.style.width = `${(r.total / maxT) * 100}%`;
          MEDALS.forEach((m) => {
            if (!r[m]) return;
            const s = el("span");
            s.style.setProperty("--c", COLOR[m]);
            s.style.flex = String(r[m]);
            bar.append(s);
          });
          return bar;
        },
      },
    ], rows);
  }

  /* ---------- Most decorated swimmers ---------- */

  function swimmersTable() {
    const rows = data.swimmers.filter((s) => scope.key === "All" || s.gender === scope.key)
      .map((s) => ({ ...s, total: s.gold + s.silver + s.bronze }))
      .sort((a, b) => b.total - a.total || b.gold - a.gold || b.silver - a.silver).slice(0, 40);
    const who = (s) => {
      const span = el("span", "club");
      span.append(F.flag(s.nation), document.createTextNode(s.name));
      return span;
    };
    F.richTable(document.getElementById("swimmers-table"), [
      { label: "#", cls: "num rank", render: (s) => String(rows.indexOf(s) + 1) },
      { label: "Swimmer", render: (s) => who(s) },
      { label: "Games", cls: "years hide-sm", render: (s) => (s.first === s.last ? String(s.first) : `${s.first}–${s.last}`) },
      ...MEDALS.map((m) => ({ label: m[0].toUpperCase() + m.slice(1), short: m[0].toUpperCase(), cls: `num${m === "gold" ? " strong" : ""}`, render: (s) => String(s[m]) })),
      { label: "Total", cls: "num", render: (s) => String(s.total) },
    ], rows);
  }

  /* ---------- Results by event ---------- */

  const select = document.getElementById("event-select");
  select.addEventListener("change", () => renderEvent(select.value));

  function fillSelect() {
    select.replaceChildren();
    const groups = [...STROKES.map((s) => ({ label: s, list: events.filter((e) => e.current && e.stroke === s) })),
      { label: "Discontinued events", list: events.filter((e) => !e.current) }];
    groups.filter((g) => g.list.length).forEach((g) => {
      const og = document.createElement("optgroup");
      og.label = g.label;
      g.list.forEach((e) => {
        const o = el("option", null, `${scope.key === "All" || e.gender === "Mixed" ? `${e.gender} · ` : ""}${e.name}`);
        o.value = e.key;
        og.append(o);
      });
      select.append(og);
    });
    renderEvent(select.value);
  }

  function medalCell(slots) {
    if (!slots.length) return el("span", "muted", "not awarded");
    const wrap = el("div");
    slots.forEach((slot) => {
      if (slot.team) {
        const row = el("div", "medalist");
        const head = el("span", "club");
        head.append(F.flag(slot.team), document.createTextNode(name(slot.team)));
        row.append(head);
        if (slot.time) row.append(el("span", "time", slot.time));
        row.append(el("div", "team", slot.swimmers.map((s) => s.name).join(", ")));
        wrap.append(row);
      } else {
        slot.swimmers.forEach((s) => {
          const row = el("div", "medalist");
          const head = el("span", "club");
          head.append(F.flag(s.nation), document.createTextNode(s.name));
          row.append(head);
          if (slot.time) row.append(el("span", "time", slot.time));
          wrap.append(row);
        });
      }
    });
    return wrap;
  }

  function renderEvent(key) {
    const ev = events.find((e) => e.key === key) ?? events[0];
    const years = ev.results.map((r) => r.year);
    document.getElementById("event-meta").textContent =
      `${ev.gender} · ${ev.stroke}${ev.current ? "" : " · discontinued"} · ${years.length} ${years.length === 1 ? "edition" : "editions"}, ${years[0]}${years.length > 1 ? `–${years[years.length - 1]}` : ""}`;

    const all = medals([ev]);
    const byNation = d3.rollups(all.filter((x) => x.medal === "gold"), (v) => v, (x) => nationOf(x.slot)).sort((a, b) => b[1].length - a[1].length).slice(0, 8);
    F.rankList(document.getElementById("event-nations"), byNation.map(([c, v]) => ({
      icon: F.flag(c), label: name(c), value: v.length, color: "var(--gold)",
      second: all.filter((x) => nationOf(x.slot) === c).length,
      tip: (t) => { t.append(ttTitle(`${name(c)} · ${v.length} gold`)); t.append(ttNote(v.map((x) => x.r.year).join(", "))); },
    })), ["Nation", "Gold", "Medals"]);

    const people = d3.rollups(all.flatMap((x) => x.slot.swimmers.map((s) => ({ ...x, s }))), (v) => v, (x) => x.s.name)
      .map(([k, v]) => ({ name: k, nation: d3.greatest(v, (x) => x.r.year).s.nation, v, gold: v.filter((x) => x.medal === "gold").length }))
      .sort((a, b) => b.v.length - a.v.length || b.gold - a.gold).slice(0, 8);
    F.rankList(document.getElementById("event-swimmers"), people.map((p) => ({
      icon: F.flag(p.nation), label: p.name, value: p.v.length, second: p.gold, color: "var(--ink-2)",
      tip: (t) => { t.append(ttTitle(p.name)); p.v.forEach((x) => t.append(Viz.ttRow(COLOR[x.medal], x.r.year, x.medal))); },
    })), ["Swimmer", "Medals", "Gold"]);

    const box = document.getElementById("event-table");
    F.richTable(box, [
      { label: "Games", render: (r) => F.withSub(el("strong", null, String(r.year)), r.city) },
      ...MEDALS.map((m) => ({ label: m[0].toUpperCase() + m.slice(1), render: (r) => medalCell(r[m]) })),
    ], ev.results.slice().reverse());
    box.querySelector("table")?.classList.add("results-table");
  }

  /* ---------- Switch between men, women and every event ---------- */

  function render(key) {
    scope = GENDERS.find((g) => g.key === key);
    events = data.events.filter(scope.test);
    stats();
    if (race) race.setFrames(frames());
    else {
      race = F.race(frames(), {
        colorOf: () => "var(--gold)",
        frameMs: 900,
        emptyTicker: "Press play to start at Athens 1896.",
        ticker: (e) => (e.top
          ? [F.flag(e.top[0]), el("strong", null, ` ${e.year} ${e.city}`), document.createTextNode(` · most golds: ${name(e.top[0])} (${e.top[1]})`)]
          : [el("strong", null, `${e.year} ${e.city}`)]),
      });
    }
    medalTable();
    swimmersTable();
    fillSelect();
  }

  Viz.segmented("medals-stroke", [{ key: "All", label: "All" }, ...STROKES.map((s) => ({ key: s, label: s }))], "All", (k) => {
    stroke = k;
    medalTable();
  });
  Viz.segmented("gender", GENDERS, "Men", render);
  render("Men");

  const src = document.getElementById("sources");
  data.meta.sources.forEach((url, i) => {
    const a = el("a", null, decodeURIComponent(url.split("/wiki/")[1]).replace(/_/g, " "));
    a.href = url;
    src.append(a);
    if (i < data.meta.sources.length - 1) src.append(document.createTextNode(" and "));
  });
  document.getElementById("data-through").textContent = `Covers every Games through ${data.meta.through}.`;
})();
