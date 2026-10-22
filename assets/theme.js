// Shared by every page: the site navigation, the sport accent color and the light/dark toggle.
(function () {
  const root = document.documentElement;
  // The site root, from this script's own location (assets/theme.js), so links work at any depth.
  const SITE = new URL("..", document.currentScript.src);

  try {
    const saved = localStorage.getItem("theme");
    if (saved) root.dataset.theme = saved;
  } catch (e) {}

  // Every page, grouped by sport. Paths are relative to the site root.
  const MAP = [
    { sport: "tennis", label: "Tennis", pages: [
      ["tennis/big-three/", "The Big Three"], ["tennis/grand-slams/", "Grand Slams"], ["tennis/masters-1000/", "Masters 1000"],
      ["tennis/atp-records/", "ATP Records"], ["tennis/grand-slams-women/", "Women's Grand Slams"], ["tennis/wta-1000/", "WTA 1000"],
      ["tennis/wta-records/", "WTA Records"], ["tennis/finals/", "ATP & WTA Finals"], ["tennis/number-one/", "World No. 1"], ["tennis/age-records/", "Age Records"],
    ] },
    { sport: "football", label: "Football", pages: [
      ["football/world-cup/", "FIFA World Cup"], ["football/ballon-dor/", "Ballon d'Or"], ["football/champions-league/", "Champions League"],
      ["football/copa-libertadores/", "Copa Libertadores"], ["football/world-club-champions/", "World Club Champions"],
      ["football/argentine-primera/", "Argentina"], ["football/serie-a/", "Serie A"], ["football/la-liga/", "La Liga"],
      ["football/premier-league/", "England"], ["football/ligue-1/", "Ligue 1"], ["football/bundesliga/", "Germany"],
      ["football/brasileirao/", "Brasileirão"],
    ] },
    { sport: "olympics", label: "Olympics", pages: [
      ["olympics/", "Olympic Games"], ["swimming/olympics/", "Swimming"], ["tennis/olympics/", "Tennis"],
      ["football/olympics/", "Football"], ["boxing/olympics/", "Boxing"],
    ] },
    { sport: "basketball", label: "Basketball", pages: [["basketball/nba-rings/", "NBA Rings"], ["basketball/international/", "World Cup & Olympics"]] },
    { sport: "team", label: "Team sports", pages: [
      ["handball/international/", "Handball"], ["rugby/international/", "Rugby"], ["volleyball/international/", "Volleyball"],
      ["hockey/international/", "Field hockey"],
    ] },
    { sport: "american-football", label: "NFL", pages: [["american-football/super-bowl/", "Super Bowl"]] },
    { sport: "ice-hockey", label: "NHL", pages: [["ice-hockey/stanley-cup/", "Stanley Cup"]] },
    { sport: "chess", label: "Chess", pages: [["chess/", "Chess"]] },
    { sport: "motorsport", label: "Motorsport", pages: [["motorsport/formula-1/", "Formula 1"]] },
  ];
  // Sport accents follow the page's first folder (swimming pages count as Olympics in the menu).
  const here = location.href.startsWith(SITE.href) ? location.href.slice(SITE.href.length).replace(/index\.html$/, "").split(/[?#]/)[0] : "";
  const folder = here.split("/")[0];
  if (folder) root.dataset.sport = folder;
  // The menu group holding this page (Olympic tennis sits under Olympics, not Tennis).
  const active = MAP.find((g) => g.pages.some(([p]) => here === p)) ?? MAP.find((g) => g.pages.some(([p]) => here.startsWith(p))) ?? null;

  function current() {
    if (root.dataset.theme) return root.dataset.theme;
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function nav() {
    const bar = el("nav", "site-nav");
    bar.setAttribute("aria-label", "Site");
    const inner = el("div", "wrap nav-inner");
    const brand = el("a", "brand");
    brand.href = SITE.href;
    brand.append(el("span", null, "Sports"), el("strong", null, "Stats"));
    const menu = el("button", "nav-menu", "Menu");
    menu.type = "button";
    menu.setAttribute("aria-expanded", "false");
    const groups = el("div", "nav-groups");
    MAP.forEach((g) => {
      const d = el("details", `nav-group${g === active ? " active" : ""}`);
      d.dataset.sport = g.sport;
      const s = el("summary", null, g.label);
      const drop = el("div", "nav-drop");
      g.pages.forEach(([path, label]) => {
        const a = el("a", null, label);
        a.href = new URL(path, SITE).href;
        if (here === path) a.setAttribute("aria-current", "page");
        drop.append(a);
      });
      d.append(s, drop);
      d.addEventListener("toggle", () => {
        if (d.open) groups.querySelectorAll("details[open]").forEach((o) => o !== d && (o.open = false));
      });
      groups.append(d);
    });
    menu.addEventListener("click", () => {
      const open = bar.classList.toggle("menu-open");
      menu.setAttribute("aria-expanded", String(open));
    });
    document.addEventListener("click", (e) => {
      if (!bar.contains(e.target)) groups.querySelectorAll("details[open]").forEach((o) => (o.open = false));
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") groups.querySelectorAll("details[open]").forEach((o) => (o.open = false));
    });

    const toggle = el("button", "theme-toggle");
    toggle.type = "button";
    const sync = () => {
      const dark = current() === "dark";
      toggle.textContent = dark ? "☀" : "☾";
      toggle.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    };
    toggle.addEventListener("click", () => {
      root.dataset.theme = current() === "dark" ? "light" : "dark";
      try {
        localStorage.setItem("theme", root.dataset.theme);
      } catch (e) {}
      sync();
      document.dispatchEvent(new CustomEvent("themechange"));
    });
    sync();
    inner.append(brand, groups, menu, toggle);
    bar.append(inner);
    return bar;
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.body.prepend(nav());
  });
})();
