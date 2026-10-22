/* Coaches (and players) with the most titles: shared by the club competition, league and team sport pages.
   Fills <section id="people"> from a people dataset next to the page's own data (for club, team or
   franchise names and crests): data/people.json, or data/<competition>-people.json on pages with a
   competition selector (international/tournament.js announces each change with a "competitionchange" event). */
(async function () {
  "use strict";

  const root = document.getElementById("people");
  if (!root) return;
  const { el, ttTitle, ttNote } = Viz;
  const multi = document.body.dataset.datasets ? JSON.parse(document.body.dataset.datasets) : null;
  const pages = multi ? await Promise.all(multi.map((o) => d3.json(o.src))) : [await d3.json(document.body.dataset.src)];

  // Names and flags for whatever a title belongs to: clubs, national teams or NBA franchises.
  const teams = Object.assign({}, ...pages.map((p) => p.teams ?? {}));
  const franchises = Object.fromEntries(pages.flatMap((p) => p.franchises ?? []).map((f) => [f.id, { name: f.name, country: null, crest: null }]));
  const page = pages[0];
  const national = Object.keys(teams).length > 0;
  const baseClubs = national
    ? Object.fromEntries(Object.entries(teams).map(([c, t]) => [c, { name: t.name, country: c, crest: null }]))
    : { ...franchises, ...(page.clubs ?? {}) };
  const order = new Map();
  pages.forEach((p) => (p.finals ?? p.titles ?? p.editions ?? p.seasons ?? []).forEach((t, i) => order.set(String(t.season ?? t.year), i)));
  const yearOf = (s) => parseInt(s, 10) || 0;

  /** Ranked rows: flag, name with a detail line underneath, a bar, the count and a short note. */
  function personList(target, rows, headers) {
    target.replaceChildren();
    target.classList.toggle("person-list-short", !rows.some((r) => r.second));
    const max = d3.max(rows, (r) => r.value) || 1;
    const head = el("div", "person-head");
    head.append(el("span"), el("span", null, headers[0]), el("span", "num", headers[1]), el("span", "num", headers[2] ?? ""));
    target.append(head);
    rows.forEach((r) => {
      const row = el("div", "person-row");
      const main = el("div", "person-main");
      main.append(el("div", "person-name", r.label));
      if (r.sub) main.append(el("div", "person-sub", r.sub));
      const bar = el("div", "person-bar");
      const fill = el("span");
      fill.style.width = `${(r.value / max) * 100}%`;
      bar.append(fill);
      main.append(bar);
      row.append(r.icon ?? el("span"), main, el("span", "num person-value", String(r.value)), el("span", "num person-second", r.second ?? ""));
      if (r.tip) Viz.tooltipOnNode(row, r.tip);
      target.append(row);
    });
  }
  const yearsOf = (list) => {
    const ys = list.map((t) => parseInt(t.season, 10)).filter(Number.isFinite).sort((a, b) => a - b);
    return ys.length ? (ys[0] === ys[ys.length - 1] ? String(ys[0]) : `${ys[0]}–${ys[ys.length - 1]}`) : "";
  };

  let footerNote = null;

  function render(people) {
    root.replaceChildren();
    if (!people) return;
    const F = Football({ nationMode: national, clubs: baseClubs, countries: { ...people.nations, ...(page.countries ?? {}), ...teams } });
    const cup = people.meta.kind === "cup";
    const flagOf = (nation) => (nation ? F.flag(nation) : el("span"));
    const who = (name, nation) => {
      const span = el("span", "club");
      if (nation) span.append(F.flag(nation));
      span.append(document.createTextNode(name));
      return span;
    };
    const teamName = (id) => F.clubName(id);

    /* ---------- Markup ---------- */

    const hasPlayers = people.players.length > 0;
    const head = el("div", "block-head");
    head.append(el("h2", null, hasPlayers ? "Coaches and players" : "Winning coaches"));
    head.append(el("p", null, cup
      ? hasPlayers ? "The coaches who won the most titles and reached the most finals, and the players who lifted the trophy most often."
        : "The coaches who won the most titles and reached the most finals, and both coaches of every final."
      : hasPlayers ? "The coaches who won the most titles, every champion's coach, and the players with the most titles."
        : "The coaches who won the most titles, and the coach of every champion."));
    const coachCard = el("div", "card");
    coachCard.append(el("h3", "sub", "Coaches with the most titles"));
    const tabs = el("div", "segmented");
    tabs.id = "people-coach-tabs";
    tabs.setAttribute("role", "tablist");
    tabs.setAttribute("aria-label", "Coach record");
    if (cup) {
      const controls = el("div", "controls");
      controls.append(tabs);
      coachCard.append(controls);
    }
    const coachList = el("div");
    coachCard.append(coachList);
    if (people.meta.coachesNote) coachCard.append(el("p", "people-note", people.meta.coachesNote));
    root.append(head, coachCard);

    const seasonsCard = el("div", "card");
    seasonsCard.append(el("h3", "sub", cup ? "Every final's coaches" : "Every champion's coach"));
    const seasonsTable = el("div", "data-table tall");
    seasonsCard.append(seasonsTable);
    const grid = el("div", hasPlayers ? "grid-2 people-gap" : "people-gap");
    if (hasPlayers) {
      const playersCard = el("div", "card");
      playersCard.append(el("h3", "sub", "Players with the most titles"));
      const list = el("div");
      list.id = "people-players";
      playersCard.append(list);
      if (people.meta.playersNote) playersCard.append(el("p", "people-note", people.meta.playersNote));
      grid.append(playersCard);
    }
    grid.append(seasonsCard);
    root.append(grid);

    // Credit the sources in the page footer.
    const footer = document.querySelector(".site-footer p");
    if (footer) {
      footerNote?.remove();
      footerNote = el("p");
      footerNote.append(el("strong", null, hasPlayers ? "Coaches and players: " : "Coaches: "));
      people.meta.sources.forEach((u, i) => {
        const a = el("a", null, decodeURIComponent(u.split("/wiki/")[1]).replace(/_/g, " ").replace(/^Anexo:/, ""));
        a.href = u;
        if (i) footerNote.append(document.createTextNode(", "));
        footerNote.append(a);
      });
      footerNote.append(document.createTextNode(
        `${people.meta.sources.length > 2 ? " and other tournament pages" : ""} (Wikipedia, CC BY-SA 4.0). Every coach's title is matched to that edition's champion on this page.`));
      footer.after(footerNote);
    }

    /* ---------- Coaches ---------- */

    const coachTip = (c) => () => {
      const t = el("div");
      t.append(ttTitle(c.name));
      if (c.titles.length) {
        t.append(el("div", null, `Won ${c.titles.length}:`));
        d3.groups(c.titles, (x) => x.club).forEach(([club, list]) => t.append(Viz.ttRow("var(--gold)", list.length, `${teamName(club)} (${list.map((x) => x.season).join(", ")})`)));
      }
      if (c.lost.length) {
        t.append(el("div", null, `Lost ${c.lost.length} final${c.lost.length === 1 ? "" : "s"}:`));
        d3.groups(c.lost, (x) => x.club).forEach(([club, list]) => t.append(Viz.ttRow("var(--silver)", list.length, `${teamName(club)} (${list.map((x) => x.season).join(", ")})`)));
      }
      return t;
    };
    const clubsOf = (list) => [...new Set(list.map((x) => x.club))];
    function coaches(mode) {
      const rows = people.coaches
        .map((c) => ({ c, titles: c.titles.length, finals: c.titles.length + c.lost.length }))
        .filter((r) => (mode === "finals" ? r.finals : r.titles) > 0)
        .sort((a, b) => (mode === "finals" ? b.finals - a.finals || b.titles - a.titles : b.titles - a.titles || b.finals - a.finals))
        .slice(0, 15)
        .map(({ c, titles, finals }) => {
          const list = mode === "finals" ? [...c.titles, ...c.lost] : c.titles;
          return {
            icon: flagOf(c.nation),
            label: c.name,
            sub: `${clubsOf(list).map(teamName).join(", ")} · ${yearsOf(list)}`,
            value: mode === "finals" ? finals : titles,
            second: mode === "finals" ? `${titles} won` : cup ? `${finals} finals` : "",
            tip: coachTip(c),
          };
        });
      personList(coachList, rows, ["Coach", mode === "finals" ? "Finals" : "Titles", mode === "finals" ? "Won" : cup ? "Finals" : ""]);
    }
    if (cup) Viz.segmented("people-coach-tabs", [{ key: "titles", label: "Most titles" }, { key: "finals", label: "Most finals" }], "titles", coaches);
    coaches("titles");

    /* ---------- Every season ---------- */

    const bySeason = new Map();
    const slot = (s) => bySeason.get(s) ?? bySeason.set(s, { season: s, won: [], lost: [] }).get(s);
    people.coaches.forEach((c) => {
      c.titles.forEach((t) => slot(t.season).won.push({ c, club: t.club }));
      c.lost.forEach((t) => slot(t.season).lost.push({ c, club: t.club }));
    });
    const seasons = [...bySeason.values()].sort((a, b) => yearOf(b.season) - yearOf(a.season) || (order.get(b.season) ?? 0) - (order.get(a.season) ?? 0));
    const coachCell = (list) => {
      const wrap = el("div");
      list.forEach(({ c }) => wrap.append(who(c.name, c.nation)));
      return wrap;
    };
    F.richTable(seasonsTable, [
      { label: cup ? "Final" : national ? "Year" : "Season", render: (s) => s.season },
      { label: cup ? "Winning coach" : "Coach", render: (s) => F.withSub(coachCell(s.won), s.won[0] ? teamName(s.won[0].club) : "") },
      ...(cup ? [{ label: "Runner-up's coach", cls: "hide-sm", render: (s) => (s.lost.length ? F.withSub(coachCell(s.lost), teamName(s.lost[0].club)) : "—") }] : []),
    ], seasons);

    /* ---------- Players ---------- */

    if (hasPlayers) {
      personList(document.getElementById("people-players"), people.players.slice(0, 20).map((p) => ({
        icon: flagOf(p.nation),
        label: p.name,
        sub: p.detail,
        value: p.titles,
        second: "",
        tip: () => {
          const t = el("div");
          t.append(ttTitle(p.name), el("div", null, `${p.titles} titles`));
          if (p.detail) t.append(ttNote(p.detail));
          return t;
        },
      })), ["Player", "Titles", ""]);
    }
  }

  const load = (src) => d3.json(src).catch(() => null);
  if (multi) {
    const cache = {};
    const show = async (k) => render(await (cache[k] ??= load(`data/${k}-people.json`)));
    const requested = new URLSearchParams(location.search).get("c");
    show(multi.some((o) => o.key === requested) ? requested : multi[0].key);
    document.addEventListener("competitionchange", (e) => show(e.detail));
  } else {
    render(await load("data/people.json"));
  }
})();
