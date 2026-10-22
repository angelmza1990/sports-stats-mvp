/* Coaches and players with the most titles: shared by the club competition and national league pages.
   Fills <section id="people"> from data/people.json, next to the page's own dataset (for club names and crests). */
(async function () {
  "use strict";

  const root = document.getElementById("people");
  if (!root) return;
  const { el, ttTitle, ttNote } = Viz;
  const [page, people] = await Promise.all([d3.json(document.body.dataset.src), d3.json("data/people.json")]);
  const F = Football({ ...page, countries: { ...people.nations, ...page.countries } });
  const cup = people.meta.kind === "cup";

  const who = (name, nation) => {
    const span = el("span", "club");
    if (nation) span.append(F.flag(nation));
    span.append(document.createTextNode(name));
    return span;
  };
  const span = (list) => {
    const years = list.map((t) => t.season).sort();
    return years.length ? (years.length === 1 ? years[0] : `${years[0]} – ${years[years.length - 1]}`) : "";
  };

  /* ---------- Markup ---------- */

  const head = el("div", "block-head");
  head.append(el("h2", null, "Coaches and players"));
  head.append(el("p", null, cup
    ? "The coaches who won the most titles and reached the most finals, and the players who lifted the trophy most often."
    : "The coaches who won the most titles, every champion's coach, and the players with the most titles."));
  const coachCard = el("div", "card");
  coachCard.append(el("h3", "sub", "Coaches"));
  const controls = el("div", "controls");
  const tabs = el("div", "segmented");
  tabs.id = "people-coach-tabs";
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "Coach record");
  controls.append(tabs);
  if (cup) coachCard.append(controls);
  const coachList = el("div");
  coachList.id = "people-coaches";
  coachCard.append(coachList);
  if (people.meta.coachesNote) coachCard.append(el("p", "people-note", people.meta.coachesNote));
  root.append(head, coachCard);

  const seasonsCard = el("div", "card people-gap");
  seasonsCard.append(el("h3", "sub", cup ? "Every final's coaches" : "Every champion's coach"));
  const seasonsTable = el("div", "data-table tall");
  seasonsCard.append(seasonsTable);

  let playersCard = null;
  if (people.players.length) {
    playersCard = el("div", "card people-gap");
    playersCard.append(el("h3", "sub", "Players with the most titles"));
    const list = el("div");
    list.id = "people-players";
    playersCard.append(list);
    if (people.meta.playersNote) playersCard.append(el("p", "people-note", people.meta.playersNote));
  }
  const grid = el("div", playersCard ? "grid-2 people-gap" : "people-gap");
  if (playersCard) {
    playersCard.classList.remove("people-gap");
    seasonsCard.classList.remove("people-gap");
    grid.append(playersCard, seasonsCard);
  } else {
    grid.append(seasonsCard);
  }
  root.append(grid);

  // Credit the sources in the page footer.
  const footer = document.querySelector(".site-footer p");
  if (footer) {
    const note = el("p");
    note.append(el("strong", null, "Coaches and players: "));
    people.meta.sources.forEach((u, i) => {
      const a = el("a", null, decodeURIComponent(u.split("/wiki/")[1]).replace(/_/g, " ").replace(/^Anexo:/, ""));
      a.href = u;
      if (i) note.append(document.createTextNode(", "));
      note.append(a);
    });
    note.append(document.createTextNode(" (Wikipedia, CC BY-SA 4.0). Every coach's title is matched to that season's champion on this page."));
    footer.after(note);
  }

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

  /* ---------- Coaches ---------- */

  const coachTip = (c) => () => {
    const t = el("div");
    t.append(ttTitle(c.name));
    if (c.titles.length) {
      t.append(el("div", null, `Won ${c.titles.length}:`));
      d3.groups(c.titles, (x) => x.club).forEach(([club, list]) => t.append(Viz.ttRow("var(--gold)", list.length, `${F.clubName(club)} (${list.map((x) => x.season).join(", ")})`)));
    }
    if (c.lost.length) {
      t.append(el("div", null, `Lost ${c.lost.length} final${c.lost.length === 1 ? "" : "s"}:`));
      d3.groups(c.lost, (x) => x.club).forEach(([club, list]) => t.append(Viz.ttRow("var(--silver)", list.length, `${F.clubName(club)} (${list.map((x) => x.season).join(", ")})`)));
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
          icon: F.flag(c.nation),
          label: c.name,
          sub: `${clubsOf(list).map(F.clubName).join(", ")} · ${yearsOf(list)}`,
          value: mode === "finals" ? finals : titles,
          second: mode === "finals" ? `${titles} won` : cup ? `${finals} finals` : "",
          tip: coachTip(c),
        };
      });
    personList(coachList, rows, ["Coach", mode === "finals" ? "Finals" : "Titles", mode === "finals" ? "Won" : cup ? "Finals" : ""]);
  }
  if (cup) {
    Viz.segmented("people-coach-tabs", [{ key: "titles", label: "Most titles" }, { key: "finals", label: "Most finals" }], "titles", coaches);
  }
  coaches("titles");

  /* ---------- Every season ---------- */

  const bySeason = new Map();
  people.coaches.forEach((c) => {
    c.titles.forEach((t) => (bySeason.get(t.season) ?? bySeason.set(t.season, { season: t.season, won: [], lost: [] }).get(t.season)).won.push({ c, club: t.club }));
    c.lost.forEach((t) => (bySeason.get(t.season) ?? bySeason.set(t.season, { season: t.season, won: [], lost: [] }).get(t.season)).lost.push({ c, club: t.club }));
  });
  const order = new Map((page.finals ?? page.titles).map((t, i) => [t.season, i]));
  const seasons = [...bySeason.values()].sort((a, b) => (order.get(b.season) ?? 0) - (order.get(a.season) ?? 0));
  const coachCell = (list) => {
    const wrap = el("div");
    list.forEach(({ c }) => wrap.append(who(c.name, c.nation)));
    return wrap;
  };
  F.richTable(seasonsTable, [
    { label: cup ? "Final" : "Season", render: (s) => s.season },
    { label: cup ? "Winning coach" : "Coach", render: (s) => F.withSub(coachCell(s.won), s.won[0] ? F.clubName(s.won[0].club) : "") },
    ...(cup ? [{ label: "Runner-up's coach", cls: "hide-sm", render: (s) => (s.lost.length ? F.withSub(coachCell(s.lost), F.clubName(s.lost[0].club)) : "—") }] : []),
  ], seasons);

  /* ---------- Players ---------- */

  if (playersCard) {
    personList(document.getElementById("people-players"), people.players.slice(0, 20).map((p) => ({
      icon: F.flag(p.nation),
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
})();
