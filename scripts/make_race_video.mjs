// Render a bar chart race of titles as an MP4 (1920×1080, 30 fps) for YouTube; --vertical makes a 1080×1920 Short.
//
//   npm install --no-save puppeteer-core@23.11.1
//   FFMPEG=/path/to/ffmpeg CHROME=/path/to/chrome node scripts/make_race_video.mjs argentina|argentina-pro|argentina-nacional[-pro]|argentina-total[-pro]|liga-mx|nba|nfl|nhl|libertadores|champions-league|tenis-slams-atp|tenis-slams-wta|tenis-masters|tenis-numero-1-atp|tenis-numero-1-wta [--vertical] [--en] [--preview]
//
// Each title is one step: the winner's bar grows by one while the panel names the tournament, the champion and
// the runner-up. --preview renders a few still frames as PNG instead of the whole video. Output goes to videos/
// (not committed). Team names and logos are trademarks of their owners; the logos come from ESPN's public CDN.
import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { metadata } from "./video/metadata.mjs";
import { resolve } from "node:path";
import puppeteer from "puppeteer-core";

const ROOT = resolve(new URL("..", import.meta.url).pathname);
const CHROME = process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const FFMPEG = process.env.FFMPEG || "ffmpeg";
const FPS = 30;
// --en writes every text in English (files end in -en); Spanish otherwise.
const EN = process.argv.includes("--en");
const L = (es, en) => (EN ? en : es);
const json = (path) => JSON.parse(readFileSync(resolve(ROOT, path), "utf8"));
const CREDIT = L("Datos: Wikipedia (CC BY-SA 4.0)", "Data: Wikipedia (CC BY-SA 4.0)");
const soccerLogo = (id) => (id ? `https://a.espncdn.com/combiner/i?img=/i/teamlogos/soccer/500-dark/${id}.png&h=160&w=160` : null);
const proLogo = (league, code) => (code ? `https://a.espncdn.com/combiner/i?img=/i/teamlogos/${league}/500-dark/${code}.png&h=160&w=160` : null);
const nbaLogo = (code) => (code ? `https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500-dark/${code}.png&h=160&w=160` : null);

// Crests of old and small Argentine clubs that ESPN doesn't have, from Wikimedia Commons (and Tiro Federal's from
// English Wikipedia).
const WM = "https://upload.wikimedia.org/wikipedia/";
const OLD_CRESTS = {
  alumni: `${WM}commons/thumb/c/c7/Escudo_Alumni.png/250px-Escudo_Alumni.png`,
  "belgrano-ac": `${WM}commons/thumb/1/14/Belgrano_ac_logo.svg/250px-Belgrano_ac_logo.svg.png`,
  "club-atletico-central-cordoba-rosario": `${WM}commons/thumb/9/9b/Club_Atl%C3%A9tico_Central_C%C3%B3rdoba_Rosario%29.svg/250px-Club_Atl%C3%A9tico_Central_C%C3%B3rdoba_Rosario%29.svg.png`,
  "estudiantil-porteno": `${WM}commons/6/6c/Escudo_de_Estudiantil_Porte%C3%B1o.png`,
  "club-atletico-patronato-de-la-juventud-catolica": `${WM}commons/thumb/3/3c/Logo_of_CA_Patronato_%282023%29.png/250px-Logo_of_CA_Patronato_%282023%29.png`,
  porteno: `${WM}commons/thumb/b/ba/Escudo-porte%C3%B1o.png/250px-Escudo-porte%C3%B1o.png`,
  "club-sportivo-balcarce": `${WM}commons/thumb/3/3b/Sportivo_balcarce_logo.png/250px-Sportivo_balcarce_logo.png`,
  "lomas-ac": `${WM}commons/thumb/c/ca/Lomas_ac_newlogo.png/250px-Lomas_ac_newlogo.png`,
  "rosario-ac": `${WM}commons/thumb/b/bb/Atlet_rosario_logo.svg/250px-Atlet_rosario_logo.svg.png`,
  "san-isidro": `${WM}commons/thumb/6/6f/CA_san_isidro_logo.svg/250px-CA_san_isidro_logo.svg.png`,
  "club-atletico-tiro-federal-argentino": `${WM}en/thumb/b/b1/Tiro_federal_rosario_logo.png/250px-Tiro_federal_rosario_logo.png`,
};

// Bar fills in club colors (stripes and sashes as gradients); other clubs get a muted color of their own.
const stripes = (a, b, angle = 90, w = 16) => `repeating-linear-gradient(${angle}deg, ${a} 0 ${w}px, ${b} ${w}px ${2 * w}px)`;
const band = (a, b) => `linear-gradient(${a} 0 33%, ${b} 33% 67%, ${a} 67%)`;
const halves = (a, b) => `linear-gradient(${a} 0 50%, ${b} 50%)`;
const MUTED = ["#7b8798", "#8d7f9a", "#7f9a8d", "#9a8d7f", "#6f8fa8", "#a87f7f", "#8fa86f", "#a8956f"];
const muted = (id) => MUTED[[...id].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7) % MUTED.length];

const COLORS = {
  argentina: {
    "river-plate": "linear-gradient(115deg, #f1f1f1 0 42%, #d71920 42% 58%, #f1f1f1 58%)",
    "boca-juniors": band("#0b3d91", "#f2c200"),
    racing: stripes("#7cc3ea", "#f1f1f1"),
    independiente: "#d0021b",
    "san-lorenzo": stripes("#1b3f8b", "#c8102e", 90, 14),
    "velez-sarsfield": band("#f1f1f1", "#1b4fa0"),
    alumni: stripes("#d0021b", "#f1f1f1"),
    estudiantes: stripes("#d71920", "#f1f1f1", 90, 12),
    "newell-s-old-boys": halves("#111111", "#d3122a"),
    "lomas-ac": stripes("#1f7a3a", "#f1f1f1"),
    huracan: "linear-gradient(#f1f1f1 0 72%, #d71920 72%)",
    "rosario-central": stripes("#14408f", "#f6c400"),
    "belgrano-ac": "#5b7fb5",
    "argentinos-juniors": "#e2231a",
    quilmes: "linear-gradient(#f1f1f1 0 72%, #0b2a5b 72%)",
    "ferro-carril-oeste": "#0b7a3b",
    lanus: "#7a1f2b",
    "gimnasia-y-esgrima-lp": band("#f1f1f1", "#0b2a5b"),
    porteno: "#8e44ad",
    "estudiantil-porteno": "#c0392b",
  },
  "liga-mx": {
    "club-america": "linear-gradient(#ffd200 0 70%, #0a2a66 70%)",
    guadalajara: stripes("#d0021b", "#f1f1f1"),
    toluca: "#d0021b",
    "cruz-azul": "#1f4fb5",
    "club-leon": "#087f3b",
    uanl: "#f39200",
    "pumas-unam": "linear-gradient(#0b2240 0 70%, #c6a045 70%)",
    pachuca: halves("#0b2a6b", "#f1f1f1"),
    "santos-laguna": stripes("#138a36", "#f1f1f1"),
    monterrey: stripes("#0b2a5b", "#f1f1f1", 0, 7),
    atlante: stripes("#1f4fb5", "#c8102e"),
    atlas: halves("#d0021b", "#111111"),
    necaxa: stripes("#d0021b", "#f1f1f1", 90, 12),
    "club-puebla": "linear-gradient(115deg, #f1f1f1 0 42%, #1f4fb5 42% 58%, #f1f1f1 58%)",
    "c-d-veracruz": halves("#d0021b", "#0b2a6b"),
    "zacatepec-f-c": stripes("#0b7a3b", "#f1f1f1"),
  },
  nfl: {
    GB: "linear-gradient(#203731 0 65%, #ffb612 65%)", CHI: "linear-gradient(#0b162a 0 65%, #c83803 65%)", NYG: "linear-gradient(#0b2265 0 70%, #a71930 70%)",
    PIT: "linear-gradient(#ffb612 0 65%, #101820 65%)", NE: "linear-gradient(#002244 0 70%, #c60c30 70%)", WAS: "linear-gradient(#5a1414 0 65%, #ffb612 65%)",
    SF: "linear-gradient(#aa0000 0 65%, #b3995d 65%)", DAL: "linear-gradient(#003594 0 70%, #869397 70%)", PHI: "#004c54", LV: "linear-gradient(#a5acaf 0 65%, #000000 65%)",
    DEN: "linear-gradient(#fb4f14 0 65%, #002244 65%)", KC: "linear-gradient(#e31837 0 70%, #ffb81c 70%)", LAR: "linear-gradient(#003594 0 65%, #ffd100 65%)",
    BAL: "#241773", IND: "#002c5f", MIA: "linear-gradient(#008e97 0 70%, #fc4c02 70%)", TB: "linear-gradient(#d50a0a 0 70%, #34302b 70%)",
    SEA: "linear-gradient(#002244 0 70%, #69be28 70%)", NYJ: "#125740", NO: "linear-gradient(#d3bc8d 0 65%, #101820 65%)", DET: "#0076b6",
    CLE: "linear-gradient(#ff3c00 0 65%, #311d00 65%)", ARI: "#97233f", MIN: "linear-gradient(#4f2683 0 70%, #ffc62f 70%)", BUF: "#00338d",
    CIN: "#fb4f14", HOU: "#03202f", JAX: "#006778", TEN: "#4b92db", LAC: "#0080c6", ATL: "#a71930", CAR: "#0085ca",
  },
  nhl: {
    MTL: band("#af1e2d", "#192168"), TOR: "#00205b", DET: "#ce1126", BOS: "linear-gradient(#ffb81c 0 65%, #111111 65%)", CHI: "#cf0a2c",
    EDM: "linear-gradient(#041e42 0 65%, #ff4c00 65%)", PIT: "linear-gradient(#fcb514 0 65%, #111111 65%)", NYI: "linear-gradient(#00539b 0 70%, #f47d30 70%)",
    NYR: "linear-gradient(#0038a8 0 70%, #ce1126 70%)", TB: "#002868", COL: "linear-gradient(#6f263d 0 65%, #236192 65%)", NJ: halves("#ce1126", "#111111"),
    LA: "#a2aaad", ANA: "#f47a38", DAL: "#006847", CAR: "#ce1126", PHI: "#f74902", STL: "linear-gradient(#002f87 0 70%, #fcb514 70%)",
    WSH: "linear-gradient(#c8102e 0 70%, #041e42 70%)", CGY: "linear-gradient(#c8102e 0 70%, #f1be48 70%)", VGK: "linear-gradient(#b4975a 0 70%, #333f42 70%)",
    FLA: "linear-gradient(#c8102e 0 70%, #041e42 70%)", OTS: halves("#111111", "#c8102e"), OTT: halves("#111111", "#c8102e"), MTM: "#8a1538", VMI: "#6a2c5b", SMT: "#2b6cb0", VAN: "#00205b", NSH: "#ffb81c",
  },
  libertadores: {
    independiente: "#d0021b", "boca-juniors": band("#0b3d91", "#f2c200"), penarol: stripes("#f6c400", "#111111"),
    estudiantes: stripes("#d71920", "#f1f1f1", 90, 12), flamengo: stripes("#c8102e", "#111111", 0, 8),
    "river-plate": "linear-gradient(115deg, #f1f1f1 0 42%, #d71920 42% 58%, #f1f1f1 58%)", santos: "linear-gradient(#f1f1f1 0 75%, #111111 75%)",
    nacional: "linear-gradient(#f1f1f1 0 70%, #1b3f8b 70%)", olimpia: band("#f1f1f1", "#111111"), gremio: stripes("#0d80bf", "#111111", 90, 12),
    "sao-paulo": "linear-gradient(#f1f1f1 0 40%, #d71920 40% 55%, #111111 55% 70%, #f1f1f1 70%)", palmeiras: "#006437", cruzeiro: "#1b3f8b",
    "atletico-nacional": stripes("#0b7a3b", "#f1f1f1"), internacional: "#c8102e", "velez-sarsfield": band("#f1f1f1", "#1b4fa0"),
    "colo-colo": "linear-gradient(#f1f1f1 0 75%, #111111 75%)", "argentinos-juniors": "#e2231a", racing: stripes("#7cc3ea", "#f1f1f1"),
    "san-lorenzo": stripes("#1b3f8b", "#c8102e", 90, 14), corinthians: "linear-gradient(#f1f1f1 0 75%, #111111 75%)",
    fluminense: stripes("#8a1538", "#0b7a3b", 90, 12), "atletico-mineiro": stripes("#111111", "#f1f1f1"), botafogo: stripes("#111111", "#f1f1f1", 90, 12),
    "ldu-quito": "linear-gradient(#f1f1f1 0 75%, #c8102e 75%)", "once-caldas": "#f1f1f1", vasco: "linear-gradient(115deg, #111111 0 42%, #f1f1f1 42% 58%, #111111 58%)",
  },
  "champions-league": {
    "real-madrid": "linear-gradient(#f1f1f1 0 78%, #c9a227 78%)", milan: stripes("#d0021b", "#111111"), "bayern-munich": "#dc052d",
    liverpool: "#c8102e", barcelona: stripes("#a50044", "#004d98"), ajax: band("#f1f1f1", "#d2122e"), "inter-milan": stripes("#0068a8", "#111111"),
    "manchester-united": "#da291c", benfica: "#e30613", "nottingham-forest": "#dd0000", juventus: stripes("#111111", "#f1f1f1"),
    porto: stripes("#00428c", "#f1f1f1"), chelsea: "#034694", "paris-saint-germain": band("#004170", "#da291c"),
    "borussia-dortmund": "linear-gradient(#fde100 0 75%, #111111 75%)", "manchester-city": "#6cabdd", celtic: stripes("#018749", "#f1f1f1", 0, 7),
    "hamburger-sv": "linear-gradient(#f1f1f1 0 70%, #0a3a7c 70%)", "aston-villa": "linear-gradient(#670e36 0 70%, #95bfe5 70%)",
    psv: stripes("#ed1c24", "#f1f1f1"), "red-star-belgrade": stripes("#c8102e", "#f1f1f1"), marseille: "linear-gradient(#f1f1f1 0 75%, #2faee0 75%)",
    feyenoord: halves("#f1f1f1", "#d0021b"), "steaua-bucuresti": halves("#1b3f8b", "#d0021b"),
  },
  nba: {
    ATL: "#e03a3e", BOS: "linear-gradient(#007a33 0 75%, #ba9653 75%)", BKN: "#a7a9ac", CHA: "#00788c", CHI: "#ce1141",
    CLE: "linear-gradient(#860038 0 75%, #fdbb30 75%)", DAL: "#00538c", DEN: "linear-gradient(#0e2240 0 70%, #fec524 70%)",
    DET: "linear-gradient(#c8102e 0 70%, #1d42ba 70%)", GSW: "linear-gradient(#1d428a 0 65%, #ffc72c 65%)", HOU: "#ce1141",
    IND: "linear-gradient(#002d62 0 70%, #fdbb30 70%)", LAC: "linear-gradient(#c8102e 0 70%, #1d428a 70%)",
    LAL: "linear-gradient(#552583 0 65%, #fdb927 65%)", MEM: "#5d76a9", MIA: "#98002e", MIL: "linear-gradient(#00471b 0 75%, #eee1c6 75%)",
    MIN: "#236192", NOP: "linear-gradient(#0c2340 0 70%, #c8102e 70%)", NYK: "linear-gradient(#006bb6 0 70%, #f58426 70%)",
    OKC: "linear-gradient(#007ac1 0 70%, #ef3b24 70%)", ORL: "#0077c0", PHI: "linear-gradient(#006bb6 0 70%, #ed174c 70%)",
    PHX: "#e56020", POR: "#e03a3e", SAC: "#5a2d81", SAS: "#c4ced4", TOR: "#ce1141", UTA: "linear-gradient(#002b5c 0 70%, #f9a01b 70%)",
    WAS: "linear-gradient(#002b5c 0 70%, #e31837 70%)",
  },
};

const TEXT = { recent: L("Últimos campeones", "Latest champions"), champion: L("Campeón", "Champion"), unit: L("títulos", "titles") };
const vs = L("ante", "vs");
const now = (name) => ` · ${L("hoy", "now")} ${name}`;
const runnerUp = (name) => `${L("Subcampeón", "Runner-up")}: ${name}`;

function argentina({ proOnly = false } = {}) {
  const d = json("football/argentine-primera/data/argentine-primera.json");
  const titles = proOnly ? d.titles.filter((t) => t.era === "professional") : d.titles;
  const rival = L("torneo paralelo", "rival league");
  const ASSOC = {
    AAmF: `Asociación Amateurs de Football (${rival})`,
    FAF: `Federación Argentina de Football (${rival})`,
    LAF: `Liga Argentina de Football (${L("profesional", "professional")})`,
  };
  const KIND = EN ? {
    "": "Primera División championship", Apertura: "Apertura tournament", Clausura: "Clausura tournament", Nacional: "Nacional championship",
    Metropolitano: "Metropolitano championship", Inicial: "Inicial tournament", Final: "Final tournament", "Transición": "Transición tournament",
    Liga: "League champion on the annual table", "(H)": "Copa de Honor", "(C)": "Copa Campeonato", "(O)": "Copa de Oro",
  } : {
    "": "Campeonato de Primera División", Apertura: "Torneo Apertura", Clausura: "Torneo Clausura", Nacional: "Campeonato Nacional",
    Metropolitano: "Campeonato Metropolitano", Inicial: "Torneo Inicial", Final: "Torneo Final", "Transición": "Torneo de Transición",
    Liga: "Campeón de Liga por tabla anual", "(H)": "Copa de Honor", "(C)": "Copa Campeonato", "(O)": "Copa de Oro",
  };
  const SHORT = { "(H)": "Copa de Honor", "(C)": "Copa Campeonato", "(O)": "Copa de Oro", Liga: L("Liga (anual)", "League (annual)") };
  const events = titles.map((t) => {
    const suffix = t.season.replace(/^\d{4}(–\d{2,4})?\s*/, "");
    const year = t.season.match(/^\d{4}(–\d{2,4})?/)[0];
    let name = ASSOC[suffix] ?? KIND[suffix] ?? suffix;
    if (!ASSOC[suffix] && t.split && !suffix) name = `Asociación Argentina de Football (${L("año de cisma", "split year")})`;
    const shortName = SHORT[suffix] ?? suffix;
    return {
      winner: t.champion, big: year, name, short: `${year} ${shortName}`.trim(), era: t.era,
      when: Number(year.replace(/^(\d\d)(\d\d)–(\d\d)$/, "$1$3").replace(/^(\d{4})–(\d{4})$/, "$2")),
      tag: proOnly ? "" : t.era === "professional" ? L("Era profesional", "Professional era") : L("Era amateur", "Amateur era"),
      note: t.runnerUp ? runnerUp(d.clubs[t.runnerUp]?.name ?? t.runnerUp) : "",
    };
  });
  const teams = Object.fromEntries([...new Set(events.map((e) => e.winner))].map((id) => [id, {
    name: d.clubs[id].name, logo: soccerLogo(d.clubs[id].crest) ?? OLD_CRESTS[id] ?? null, color: COLORS.argentina[id] ?? muted(id),
  }]));
  const first = titles[0].year, last = titles[titles.length - 1].year;
  if (proOnly) return { file: "argentina-titulos-era-profesional", secondsPerEvent: 0.55, events, teams,
    title: L("Fútbol argentino: campeones de la era profesional", "Argentine football: champions of the professional era"),
    subtitle: L(`Todos los títulos de Primera División desde el profesionalismo, ${first} a ${last}`, `Every Primera División title since the game turned professional, ${first} to ${last}`),
    credit: CREDIT, text: TEXT };
  return { file: "argentina-titulos-primera-division", secondsPerEvent: 0.55, events, teams,
    title: L("Fútbol argentino: campeones de Primera División", "Argentine football: Primera División champions"),
    subtitle: L(`Todos los títulos de liga, ${first} a ${last} · eras amateur y profesional, como los cuenta la AFA`, `Every league title, ${first} to ${last} · amateur and professional eras, as the AFA counts them`),
    credit: CREDIT, text: TEXT };
}

function ligaMx() {
  const d = json("football/liga-mx/data/liga-mx.json");
  const NAMES = { Ape: "Apertura", Cla: "Clausura", Inv: L("Invierno", "Winter"), Ver: L("Verano", "Summer"), Guard: "Guard1anes", Bic: "Bicentenario", Prode: "Prode", Mex: L("México", "Mexico") };
  const events = d.titles.map((t) => {
    const m = t.season.match(/^([A-Za-z]+)–(\d{4})$/);
    let big, name, short;
    if (m) {
      const label = m[1] === "Mex" || m[1] === "Prode" ? `${NAMES[m[1]]} ${m[2].slice(2)}` : `${NAMES[m[1]] ?? m[1]} ${m[2]}`;
      big = m[2]; name = L(`Torneo ${label}`, `${label} tournament`); short = label;
    } else {
      big = t.season; name = L(`Temporada ${t.season}`, `${t.season} season`); short = t.season;
    }
    // The short tournaments began in 1996; the 1970 and 1986 World Cup years and Prode 85 were short ones too.
    const tag = !m ? L("Temporadas largas", "Long seasons") : Number(big) < 1996 ? L("Torneo especial", "Special tournament") : L("Torneos cortos", "Short tournaments");
    return { winner: t.champion, big, name, short, tag, note: t.runnerUp ? runnerUp(d.clubs[t.runnerUp]?.name ?? t.runnerUp) : "" };
  });
  const teams = Object.fromEntries([...new Set(events.map((e) => e.winner))].map((id) => [id, {
    name: d.clubs[id].name, logo: soccerLogo(d.clubs[id].crest), color: COLORS["liga-mx"][id] ?? muted(id),
  }]));
  return { file: "liga-mx-campeones", secondsPerEvent: 0.7, events, teams,
    title: L("Fútbol mexicano: campeones de liga", "Mexican football: league champions"),
    subtitle: L(`Todos los títulos de la era profesional, ${d.titles[0].season} a ${short(d.titles[d.titles.length - 1].season)}`, `Every title of the professional era, ${d.titles[0].season} to ${short(d.titles[d.titles.length - 1].season)}`),
    credit: CREDIT, text: TEXT };
  function short(s) { const m = s.match(/^([A-Za-z]+)–(\d{4})$/); return m ? `${NAMES[m[1]]} ${m[2]}` : s; }
}

function nba() {
  const d = json("basketball/nba-rings/data/nba-rings.json");
  const fr = Object.fromEntries(d.franchises.map((f) => [f.id, f]));
  const events = d.seasons.map((s) => ({
    winner: s.champion, big: String(s.year), name: L(`Finales de la NBA ${s.year}`, `${s.year} NBA Finals`), short: String(s.year),
    winnerName: s.championName, tag: EN ? `${s.conference === "East" ? "Eastern" : "Western"} ${s.year < 1971 ? "Division" : "Conference"}`
      : `${s.year < 1971 ? "División" : "Conferencia"} ${s.conference === "East" ? "Este" : "Oeste"}`,
    note: `${s.result} ${vs} ${s.runnerUpName}${fr[s.champion] && fr[s.champion].name !== s.championName ? now(fr[s.champion].name) : ""}`,
  }));
  const teams = Object.fromEntries([...new Set(events.map((e) => e.winner))].map((id) => {
    const f = fr[id] ?? { name: d.seasons.find((s) => s.champion === id).championName };
    return [id, { name: f.short ?? f.name, logo: nbaLogo(f.logo), color: COLORS.nba[id] ?? muted(id) }];
  }));
  return { file: "nba-anillos", secondsPerEvent: 0.9, events, teams,
    title: L("NBA: anillos de campeón por franquicia", "NBA: championship rings by franchise"),
    subtitle: L(`Todos los campeones, ${d.seasons[0].year} a ${d.seasons[d.seasons.length - 1].year} · los títulos cuentan para la franquicia actual`,
      `Every champion, ${d.seasons[0].year} to ${d.seasons[d.seasons.length - 1].year} · titles count for the current franchise`),
    credit: CREDIT, text: { ...TEXT, unit: L("anillos", "rings") } };
}

// The NFL title of every season since 1920: the NFL Championship until 1969, the Super Bowl since 1970.
function nfl() {
  const d = json("american-football/super-bowl/data/super-bowl.json");
  const fr = Object.fromEntries(json("data/nfl/franchises.json").franchises.map((f) => [f.id, f]));
  const games = Object.fromEntries(d.games.map((g) => [g.number, g]));
  const events = d.leagueTitles.map((t) => {
    const sb = t.via.startsWith("Super Bowl") ? games[t.via.replace("Super Bowl ", "")] : null;
    return {
      winner: t.champion, big: String(t.season), name: sb ? L(`${t.via} (temporada ${t.season})`, `${t.via} (${t.season} season)`) : L(`Campeonato de la NFL ${t.season}`, `${t.season} NFL Championship`),
      short: sb ? t.via.replace("Super Bowl", "SB") : String(t.season), winnerName: t.championName,
      tag: sb ? L("Era del Super Bowl", "Super Bowl era") : L("Antes del Super Bowl", "Before the Super Bowl"),
      note: `${sb ? `${sb.winPts}–${sb.losePts} ` : ""}${vs} ${t.runnerUpName ?? "–"}${fr[t.champion] && fr[t.champion].name !== t.championName ? now(fr[t.champion].name) : ""}`,
    };
  });
  const teams = Object.fromEntries([...new Set(events.map((e) => e.winner))].map((id) => {
    const f = fr[id] ?? { name: d.leagueTitles.find((t) => t.champion === id).championName };
    return [id, { name: f.short ?? f.name, logo: proLogo("nfl", f.logo), color: COLORS.nfl[id] ?? muted(id) }];
  }));
  const last = d.leagueTitles[d.leagueTitles.length - 1];
  return { file: "nfl-campeonatos", secondsPerEvent: 0.85, events, teams,
    title: L("NFL: campeonatos por franquicia", "NFL: championships by franchise"),
    subtitle: L(`Cada campeón desde 1920: el Campeonato de la NFL hasta 1969 y el Super Bowl desde 1970 (${last.via}, temporada ${last.season})`,
      `Every champion since 1920: the NFL Championship until 1969, the Super Bowl since 1970 (${last.via}, ${last.season} season)`),
    credit: CREDIT, text: TEXT };
}

function nhl() {
  const d = json("ice-hockey/stanley-cup/data/stanley-cup.json");
  const fr = Object.fromEntries(json("data/nhl/franchises.json").franchises.map((f) => [f.id, f]));
  const events = d.seasons.map((s) => ({
    winner: s.champion, big: String(s.year), name: L(`Final de la Stanley Cup ${s.year}`, `${s.year} Stanley Cup Final`), short: String(s.year), winnerName: s.championName,
    tag: s.league && s.league !== "NHL" ? L(`Campeón de la ${s.league}`, `${s.league} champion`) : "NHL",
    note: `${s.result} ${vs} ${s.runnerUpName}${fr[s.champion] && fr[s.champion].name !== s.championName ? now(fr[s.champion].name) : ""}`,
  }));
  const teams = Object.fromEntries([...new Set(events.map((e) => e.winner))].map((id) => {
    const f = fr[id] ?? { name: d.seasons.find((s) => s.champion === id).championName };
    return [id, { name: f.short ?? f.name, logo: proLogo("nhl", f.logo), color: COLORS.nhl[id] ?? muted(id) }];
  }));
  return { file: "nhl-stanley-cup", secondsPerEvent: 0.85, events, teams,
    title: L("NHL: Stanley Cups por franquicia", "NHL: Stanley Cups by franchise"),
    subtitle: L(`Cada campeón desde ${d.seasons[0].year} hasta ${d.seasons[d.seasons.length - 1].year} · 1919 y 2005 no se jugaron`,
      `Every champion from ${d.seasons[0].year} to ${d.seasons[d.seasons.length - 1].year} · not played in 1919 and 2005`),
    credit: CREDIT, text: { ...TEXT, unit: L("copas", "cups") } };
}

const COUNTRY_ES = {
  ARG: "Argentina", BRA: "Brasil", URU: "Uruguay", PAR: "Paraguay", COL: "Colombia", CHI: "Chile", ECU: "Ecuador", PER: "Perú", BOL: "Bolivia",
  ESP: "España", ITA: "Italia", ENG: "Inglaterra", GER: "Alemania", FRG: "Alemania Occidental", NED: "Países Bajos", POR: "Portugal",
  FRA: "Francia", SCO: "Escocia", ROU: "Rumania", YUG: "Yugoslavia", SRB: "Serbia", BEL: "Bélgica",
};
const CLUB_ES = { "bayern-munich": "Bayern Múnich", "inter-milan": "Inter", "red-star-belgrade": "Estrella Roja", "steaua-bucuresti": "Steaua Bucarest" };

// A continental cup from its finals: the score of each leg, the runner-up and the champion's country.
function cup(folder, opts) {
  const d = json(`football/${folder}/data/${folder}.json`);
  const name = (id) => (EN ? null : CLUB_ES[id]) ?? d.clubs[id]?.name ?? id;
  const events = d.finals.map((f) => {
    const legs = (f.legs ?? []).map((l) => l.score + (l.note === "penalties" ? " (pen.)" : "")).join(L(" y ", " and "));
    const country = (EN ? (f.championCountry === "FRG" ? "West Germany" : null) : COUNTRY_ES[f.championCountry]) ?? d.countries[f.championCountry]?.name ?? "";
    return { winner: f.champion, big: String(f.year), name: opts.name(f), short: opts.short(f), tag: country,
      note: `${legs ? `${legs} ${vs} ` : L("Ante ", "vs ")}${f.runnerUp ? name(f.runnerUp) : "–"}` };
  });
  const teams = Object.fromEntries([...new Set(events.map((e) => e.winner))].map((id) => [id, {
    name: name(id), logo: soccerLogo(d.clubs[id]?.crest), color: COLORS[opts.colors][id] ?? muted(id),
  }]));
  return { ...opts.meta(d), events, teams, credit: CREDIT, text: TEXT };
}

const libertadores = () => cup("copa-libertadores", { colors: "libertadores",
  name: (f) => L(`Final de la Copa Libertadores ${f.season}`, `${f.season} Copa Libertadores final`), short: (f) => f.season,
  meta: (d) => ({ file: "copa-libertadores-campeones", secondsPerEvent: 1.0, title: L("Copa Libertadores: campeones por club", "Copa Libertadores: champions by club"),
    subtitle: L(`Todas las finales, ${d.finals[0].season} a ${d.finals.at(-1).season}`, `Every final, ${d.finals[0].season} to ${d.finals.at(-1).season}`) }),
});
const championsLeague = () => cup("champions-league", { colors: "champions-league",
  name: (f) => L(`Final de la ${f.year < 1993 ? "Copa de Europa" : "Champions League"} ${f.season}`, `${f.season} ${f.year < 1993 ? "European Cup" : "Champions League"} final`), short: (f) => f.season,
  meta: (d) => ({ file: "champions-league-campeones", secondsPerEvent: 1.0, title: L("Champions League: campeones por club", "Champions League: champions by club"),
    subtitle: L(`Todas las finales de la Copa de Europa y la Champions League, ${d.finals[0].season} a ${d.finals.at(-1).season}`,
      `Every European Cup and Champions League final, ${d.finals[0].season} to ${d.finals.at(-1).season}`) }),
});

// Every title of the Argentine clubs, in order: league titles and national cups, and optionally the international
// titles (CONMEBOL, FIFA and the Río de la Plata cups the AFA counts), all eras or the professional one only.
function argentinaAll({ proOnly = false, intl = false } = {}) {
  const d = json("football/argentine-primera/data/argentine-primera.json");
  const x = json("football/argentine-primera/data/international.json");
  const keep = (e) => !proOnly || e.era === "professional";
  const eraTag = (era) => (proOnly ? "" : era === "professional" ? L(" · era profesional", " · professional era") : L(" · era amateur", " · amateur era"));
  const CUP_ES = EN ? {} : {
    "copa-de-competencia-chevallier-boutell": "Copa de Competencia Chevallier Boutell",
  };
  const INTL_ES = {
    libertadores: "Copa Libertadores", sudamericana: "Copa Sudamericana", supercopa: "Supercopa Libertadores", recopa: "Recopa Sudamericana",
    conmebol: "Copa CONMEBOL", mercosur: "Copa Mercosur", oro: "Copa de Oro", master: "Copa Master de Supercopa",
    interamericana: "Copa Interamericana", suruga: "Copa Suruga Bank", "tie-cup": L("Tie Cup (Copa de Competencia rioplatense)", "Tie Cup (Río de la Plata)"),
    cusenier: "Copa de Honor Cusenier", aldao: "Copa Aldao", "rio-de-la-plata": "Copa Campeonato del Río de la Plata",
    "escobar-gerona": "Copa Escobar-Gerona",
  };
  const league = argentina({ proOnly }).events.map((e, i) => ({ ...e, order: [e.when, 0, i],
    tag: `${L("Liga", "League")}${eraTag(e.era)}`, short: e.short.replace(/ (LAF|AAmF|FAF)$/, "") }));
  const cups = d.cups.flatMap((c) => c.editions.filter(keep).map((e, i) => ({
    winner: e.champion, big: e.season, name: CUP_ES[c.key] ?? c.name, short: `${e.season} ${(CUP_ES[c.key] ?? c.name).replace(/^Copa (de )?/, "")}`,
    tag: `${L("Copa nacional", "National cup")}${eraTag(e.era)}`, note: e.runnerUp ? runnerUp(d.clubs[e.runnerUp]?.name ?? e.runnerUp) : "",
    order: [e.year, 1, i],
  })));
  const world = (y) => (y < 2005 ? L("Copa Intercontinental", "Intercontinental Cup") : L("Mundial de Clubes FIFA", "FIFA Club World Cup"));
  const abroad = intl ? x.titles.filter(keep).map((t, i) => {
    const name = t.comp === "intercontinental" ? world(t.year) : INTL_ES[t.comp];
    return { winner: t.club, big: t.season, name, short: `${t.season} ${name.replace(/^Copa /, "")}`, tag: `${L("Internacional", "International")}${eraTag(t.era)}`, note: "", order: [t.year, 2, i] };
  }) : [];
  const cmp = (a, b) => a.order[0] - b.order[0] || a.order[1] - b.order[1] || a.order[2] - b.order[2];
  const events = [...league, ...cups, ...abroad].sort(cmp);
  const club = (id) => d.clubs[id] ?? x.clubs[id];
  const teams = Object.fromEntries([...new Set(events.map((e) => e.winner))].map((id) => [id, {
    name: club(id).name, logo: soccerLogo(club(id).crest) ?? OLD_CRESTS[id] ?? null, color: COLORS.argentina[id] ?? muted(id),
  }]));
  const span = `${events[0].big.slice(0, 4)} ${L("a", "to")} ${String(events.at(-1).order[0])}`;
  const what = intl ? L("Ligas, copas nacionales e internacionales", "Leagues, national cups and international titles") : L("Ligas y copas nacionales", "Leagues and national cups");
  const pro = L(" de la era profesional", " of the professional era");
  return {
    file: `argentina-titulos-${intl ? "totales" : "nacionales"}${proOnly ? "-era-profesional" : ""}`, secondsPerEvent: 0.4,
    events, teams,
    title: `${intl ? L("Fútbol argentino: todos los títulos", "Argentine football: every title") : L("Fútbol argentino: títulos nacionales", "Argentine football: national titles")}${proOnly ? pro : ""}`,
    subtitle: `${what}${proOnly ? L(" desde el profesionalismo", " since the professional era began") : L(", eras amateur y profesional", ", amateur and professional eras")}, ${span} · ${events.length} ${TEXT.unit}`,
    credit: CREDIT, text: TEXT,
  };
}

// Tennis: one step per title (Grand Slams, Masters 1000), or per player and calendar year for the weeks at No. 1.
// Players wear their flag; the leading players a color of their own, the others their country's.
const flag = (code) => (code ? `https://flagcdn.com/w160/${code}.png` : null);
const PLAYER_COLORS = {
  "Novak Djokovic": "#2f6db5", "Rafael Nadal": "#e8a317", "Roger Federer": "#d52b1e", "Pete Sampras": "#5a6fd6", "Bjorn Borg": "#3fa7d6",
  "Jimmy Connors": "#8b5cf6", "Ivan Lendl": "#16a34a", "Andre Agassi": "#ec4899", "John McEnroe": "#14b8a6", "Mats Wilander": "#facc15",
  "Carlos Alcaraz": "#f97316", "Jannik Sinner": "#22c55e", "Boris Becker": "#b91c1c", "Stefan Edberg": "#60a5fa", "Andy Murray": "#6366f1",
  "Serena Williams": "#a855f7", "Steffi Graf": "#ef4444", "Chris Evert": "#f59e0b", "Martina Navratilova": "#3b82f6", "Margaret Court": "#10b981",
  "Monica Seles": "#f472b6", "Billie Jean King": "#0ea5e9", "Evonne Goolagong": "#84cc16", "Venus Williams": "#c084fc", "Justine Henin": "#eab308",
  "Iga Swiatek": "#dc2626", "Martina Hingis": "#fb7185", "Aryna Sabalenka": "#f43f5e", "Ashleigh Barty": "#14b8a6", "Lindsay Davenport": "#818cf8",
  "Thomas Muster": "#b45309", "Lleyton Hewitt": "#059669", "Gustavo Kuerten": "#facc15", "Marcelo Rios": "#e11d48", "Daniil Medvedev": "#64748b",
  "Caroline Wozniacki": "#e11d48", "Amelie Mauresmo": "#2563eb", "Jelena Jankovic": "#9333ea", "Dinara Safina": "#7c3aed", "Simona Halep": "#facc15",
  "Angelique Kerber": "#16a34a", "Kim Clijsters": "#f97316", "Naomi Osaka": "#ef4444", "Jim Courier": "#f97316", "Marat Safin": "#ef4444", "Alexander Zverev": "#38bdf8", "Elena Rybakina": "#06b6d4",
};
// The No. 1 list spells some names differently.
Object.assign(PLAYER_COLORS, { "Björn Borg": PLAYER_COLORS["Bjorn Borg"], "Iga Świątek": PLAYER_COLORS["Iga Swiatek"],
  "Evonne Goolagong Cawley": PLAYER_COLORS["Evonne Goolagong"], "Amélie Mauresmo": PLAYER_COLORS["Amelie Mauresmo"], "Marcelo Ríos": PLAYER_COLORS["Marcelo Rios"] });
const SURFACE_ES = EN ? { Hard: "Hard court", Clay: "Clay", Grass: "Grass", Carpet: "Carpet" } : { Hard: "Pista dura", Clay: "Polvo de ladrillo", Grass: "Césped", Carpet: "Carpeta" };
function players(events, nations) {
  return Object.fromEntries([...new Set(events.map((e) => e.winner))].map((name) => {
    const ioc = events.findLast((e) => e.winner === name).ioc;
    return [name, { name, logo: flag(nations[ioc]?.flag), color: PLAYER_COLORS[name] ?? muted(name) }];
  }));
}
function tennisTitles(path, { file, title, subtitle, names = {}, unit = TEXT.unit, secondsPerEvent = 0.4 }) {
  if (EN) names = {};
  const d = json(path);
  const events = d.editions.filter((e) => e.champion).map((e) => ({
    winner: e.champion, ioc: e.championIoc, big: String(e.year), name: names[e.event] ?? e.event,
    short: `${e.year} ${names[e.event] ?? e.event}`, tag: SURFACE_ES[e.surface] ?? e.surface,
    note: e.runnerUp ? `Final: ${e.runnerUp}${e.score ? ` · ${e.score.replaceAll("-", "\u2011")}` : ""}` : "", // no break inside a set
  }));
  return { file, secondsPerEvent, events, teams: players(events, d.countries), title,
    subtitle: subtitle(d.editions[0].year, d.meta.through, events.length), credit: TENNIS_CREDIT,
    text: { ...TEXT, unit } };
}
const TENNIS_CREDIT = L("Datos: Jeff Sackmann / Tennis Abstract (CC BY-NC-SA 4.0) y Wikipedia (CC BY-SA 4.0)", "Data: Jeff Sackmann / Tennis Abstract (CC BY-NC-SA 4.0) and Wikipedia (CC BY-SA 4.0)");
const SLAMS_ES = { "Australian Open": "Abierto de Australia", "Roland Garros": "Roland Garros", Wimbledon: "Wimbledon", "US Open": "US Open" };
const MASTERS_ES = { "Monte Carlo": "Montecarlo", Rome: "Roma", Canada: "Canadá", Paris: "París", Hamburg: "Hamburgo", Stockholm: "Estocolmo" };
const slamsAtp = () => tennisTitles("tennis/grand-slams/data/grand-slams.json", { file: "tenis-grand-slams-atp", names: SLAMS_ES,
  title: L("Grand Slams: campeones de la Era Abierta", "Grand Slams: Open Era champions"),
  subtitle: (a, b, n) => L(`Individual masculino, de Roland Garros ${a} al ${b} · ${n} torneos`, `Men's singles, Roland Garros ${a} to ${b} · ${n} tournaments`) });
const slamsWta = () => tennisTitles("tennis/grand-slams-women/data/grand-slams-women.json", { file: "tenis-grand-slams-wta", names: SLAMS_ES,
  title: L("Grand Slams: campeonas de la Era Abierta", "Grand Slams: Open Era champions"),
  subtitle: (a, b, n) => L(`Individual femenino, de Roland Garros ${a} al ${b} · ${n} torneos`, `Women's singles, Roland Garros ${a} to ${b} · ${n} tournaments`) });
const masters = () => tennisTitles("tennis/masters-1000/data/masters-1000.json", { file: "tenis-masters-1000", names: MASTERS_ES, secondsPerEvent: 0.3,
  title: L("Masters 1000: todos los campeones", "Masters 1000: every champion"),
  subtitle: (a, b, n) => L(`Desde la creación de la categoría en ${a} hasta ${b.replace("Shanghai", "Shanghái")} · ${n} torneos`, `Since the series began in ${a}, through ${b} · ${n} tournaments`) });

// Weeks at No. 1, in steps of one player and one calendar year: a spell's weeks are spread over its days.
function numberOne(tour) {
  const d = json("tennis/number-one/data/number-one.json");
  const day = (s) => Date.parse(`${s}T00:00:00Z`);
  const events = [];
  for (const s of d.tours[tour].spells.filter((x) => x.name)) { // the 2020 freeze counts for nobody
    const a = day(s.start), b = day(s.end), span = Math.max(1, b - a);
    let done = 0;
    for (let y = new Date(a).getUTCFullYear(); y <= new Date(b).getUTCFullYear(); y++) {
      const upto = Math.min(b, Date.UTC(y + 1, 0, 1));
      const total = Math.round((s.weeks * (upto - a)) / span);
      if (total > done) events.push({ winner: s.name, ioc: s.nation, add: total - done, big: String(y), tag: "",
        name: L(`Número 1 del ranking ${tour.toUpperCase()}`, `${tour.toUpperCase()} world No. 1`),
        note: L(`+${total - done} semana${total - done === 1 ? "" : "s"} en ${y}`, `+${total - done} week${total - done === 1 ? "" : "s"} in ${y}`), short: String(y) });
      done = total;
    }
  }
  const women = tour === "wta";
  return { file: `tenis-semanas-numero-1-${tour}`, secondsPerEvent: 0.45, events, teams: players(events, d.nations),
    title: L(`Semanas como número 1 de la ${tour.toUpperCase()}`, `Weeks at No. 1 in the ${tour.toUpperCase()} rankings`),
    subtitle: L(`Todas las semanas al frente del ranking ${women ? "femenino, desde 1975" : "masculino, desde 1973"} hasta ${d.tours[tour].spells.at(-1).end.slice(0, 4)}`,
      `Every week at the top of the ${women ? "women's rankings, 1975" : "men's rankings, 1973"} to ${d.tours[tour].spells.at(-1).end.slice(0, 4)}`),
    credit: CREDIT, text: { ...TEXT, champion: L("Número 1", "No. 1"), unit: "" } };
}

// The background of each video: the sport's own (a pitch, a court, a rink) or a plain one, so that a Short and a
// video, or the Spanish and English cuts, of the same race never look the same.
const SPORT_THEME = { argentina: "pitch", "liga-mx": "pitch", libertadores: "pitch", "champions-league": "pitch", tenis: "court", nhl: "rink" };
const PLAIN_THEMES = ["arena", "dusk", "grain", "night"];
function theme(key) {
  const sport = SPORT_THEME[key] ?? SPORT_THEME[key.split("-")[0]];
  const cut = (vertical ? 1 : 0) + (EN ? 2 : 0); // 0 Spanish video, 1 Spanish Short, 2 English video, 3 English Short
  if (sport && (cut === 0 || cut === 3)) return sport;
  return PLAIN_THEMES[(Object.keys(BUILDERS).indexOf(key) + cut) % PLAIN_THEMES.length];
}

const BUILDERS = { argentina, "argentina-pro": () => argentina({ proOnly: true }),
  "argentina-nacional": () => argentinaAll(), "argentina-nacional-pro": () => argentinaAll({ proOnly: true }),
  "argentina-total": () => argentinaAll({ intl: true }), "argentina-total-pro": () => argentinaAll({ proOnly: true, intl: true }),
  "tenis-slams-atp": slamsAtp, "tenis-slams-wta": slamsWta, "tenis-masters": masters,
  "tenis-numero-1-atp": () => numberOne("atp"), "tenis-numero-1-wta": () => numberOne("wta"), "liga-mx": ligaMx, nba, nfl, nhl, libertadores, "champions-league": championsLeague };
const key = process.argv[2];
if (!BUILDERS[key]) {
  console.error(`usage: node scripts/make_race_video.mjs ${Object.keys(BUILDERS).join("|")} [--vertical] [--en] [--preview]`);
  process.exit(1);
}
const preview = process.argv.includes("--preview");
const vertical = process.argv.includes("--vertical");
const config = BUILDERS[key]();
// Shorts: 1080×1920, 59 seconds.
if (vertical) Object.assign(config, { vertical: true, file: `${config.file}-short` });
if (EN) config.file += "-en";
config.theme = theme(key);
const [W, H] = vertical ? [1080, 1920] : [1920, 1080];
const out = resolve(ROOT, "videos", EN ? "en" : "es", vertical ? "shorts" : "videos");
mkdirSync(out, { recursive: true });

// --meta writes the title, description and hashtags for the upload next to the video, and renders nothing.
if (process.argv.includes("--meta")) {
  const m = metadata(key, config);
  writeFileSync(`${out}/${config.file}.txt`, `${m.title}\n\n${m.description}\n\n${m.hashtags}\n`);
  console.log(JSON.stringify({ file: `${config.file}.mp4`, ...m }));
  process.exit(0);
}

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ["--no-sandbox"] });
const page = await browser.newPage();
page.on("pageerror", (e) => console.error("page error:", e.message));
await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
await page.goto(`file://${resolve(ROOT, "scripts/video/race.html")}`);
await page.evaluate((c) => window.setup(c), config);

const n = config.events.length;
if (preview) {
  for (const t of [0.8, Math.round(n * 0.4) + 0.5, n]) {
    await page.evaluate((x) => window.frame(x), t);
    await page.screenshot({ path: `${out}/${config.file}-preview-${Math.floor(t)}.png` });
  }
  console.log(`wrote previews to ${out}`);
} else {
  // Hold the first frame two seconds, play every event, hold the final standings six seconds. A Short lasts 59 s
  // whatever the number of events (1 s hold, 55 s race, 3 s hold), so it also fits Instagram stories and TikTok.
  const [hold0, hold1] = vertical ? [1, 3] : [2, 6];
  const raceFrames = vertical ? 55 * FPS : n * Math.round(config.secondsPerEvent * FPS);
  const times = [...Array(hold0 * FPS).fill(0), ...Array.from({ length: raceFrames }, (_, i) => (i * n) / raceFrames), ...Array(hold1 * FPS).fill(n)];
  const file = `${out}/${config.file}.mp4`;
  const ff = spawn(FFMPEG, ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", file], { stdio: ["pipe", "inherit", "inherit"] });
  const done = new Promise((ok, fail) => ff.on("close", (code) => (code ? fail(new Error(`ffmpeg exited ${code}`)) : ok())));
  let last = null;
  for (const [i, t] of times.entries()) {
    if (t !== last) await page.evaluate((x) => window.frame(x), t);
    last = t;
    const shot = await page.screenshot({ type: "jpeg", quality: 92 });
    if (!ff.stdin.write(shot)) await new Promise((r) => ff.stdin.once("drain", r));
    if (i % 300 === 0) process.stdout.write(`\r${config.file}: frame ${i}/${times.length}`);
  }
  ff.stdin.end();
  await done;
  console.log(`\nwrote ${file} (${(times.length / FPS).toFixed(0)} s)`);
}
await browser.close();
