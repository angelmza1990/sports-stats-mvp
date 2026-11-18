// Render a bar chart race of titles as an MP4 (1920×1080, 30 fps) for YouTube; --vertical makes a 1080×1920 Short.
//
//   npm install --no-save puppeteer-core@23.11.1
//   FFMPEG=/path/to/ffmpeg CHROME=/path/to/chrome node scripts/make_race_video.mjs argentina|argentina-pro|liga-mx|nba|nfl|nhl|libertadores|champions-league [--vertical] [--preview]
//
// Each title is one step: the winner's bar grows by one while the panel names the tournament, the champion and
// the runner-up. --preview renders a few still frames as PNG instead of the whole video. Output goes to videos/
// (not committed). Team names and logos are trademarks of their owners; the logos come from ESPN's public CDN.
import { spawn } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import puppeteer from "puppeteer-core";

const ROOT = resolve(new URL("..", import.meta.url).pathname);
const CHROME = process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const FFMPEG = process.env.FFMPEG || "ffmpeg";
const FPS = 30;
const json = (path) => JSON.parse(readFileSync(resolve(ROOT, path), "utf8"));
const CREDIT = "Datos: Wikipedia (CC BY-SA 4.0) · angelmza1990.github.io/sports-stats-mvp";
const soccerLogo = (id) => (id ? `https://a.espncdn.com/combiner/i?img=/i/teamlogos/soccer/500-dark/${id}.png&h=160&w=160` : null);
const proLogo = (league, code) => (code ? `https://a.espncdn.com/combiner/i?img=/i/teamlogos/${league}/500-dark/${code}.png&h=160&w=160` : null);
const nbaLogo = (code) => (code ? `https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500-dark/${code}.png&h=160&w=160` : null);

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

const TEXT = { recent: "Últimos campeones", champion: "Campeón", unit: "títulos" };

function argentina({ proOnly = false } = {}) {
  const d = json("football/argentine-primera/data/argentine-primera.json");
  const titles = proOnly ? d.titles.filter((t) => t.era === "professional") : d.titles;
  const ASSOC = {
    AAmF: "Asociación Amateurs de Football (torneo paralelo)",
    FAF: "Federación Argentina de Football (torneo paralelo)",
    LAF: "Liga Argentina de Football (profesional)",
  };
  const KIND = {
    "": "Campeonato de Primera División", Apertura: "Torneo Apertura", Clausura: "Torneo Clausura", Nacional: "Campeonato Nacional",
    Metropolitano: "Campeonato Metropolitano", Inicial: "Torneo Inicial", Final: "Torneo Final", "Transición": "Torneo de Transición",
    Liga: "Campeón de Liga (tabla anual)", "(H)": "Copa de Honor", "(C)": "Copa Campeonato", "(O)": "Copa de Oro",
  };
  const events = titles.map((t) => {
    const suffix = t.season.replace(/^\d{4}(–\d{2,4})?\s*/, "");
    const year = t.season.match(/^\d{4}(–\d{2,4})?/)[0];
    let name = ASSOC[suffix] ?? KIND[suffix] ?? suffix;
    if (!ASSOC[suffix] && t.split && !suffix) name = "Asociación Argentina de Football (año de cisma)";
    const shortName = ASSOC[suffix] ? suffix : suffix === "Liga" ? "Liga (anual)" : KIND[suffix] && suffix ? KIND[suffix].replace(/^(Torneo|Campeonato) (de )?/, "") : "";
    return {
      winner: t.champion, big: year, name, short: `${year} ${shortName}`.trim(),
      tag: proOnly ? "" : t.era === "professional" ? "Era profesional" : "Era amateur",
      note: t.runnerUp ? `Subcampeón: ${d.clubs[t.runnerUp]?.name ?? t.runnerUp}` : "",
    };
  });
  const teams = Object.fromEntries([...new Set(events.map((e) => e.winner))].map((id) => [id, {
    name: d.clubs[id].name, logo: soccerLogo(d.clubs[id].crest), color: COLORS.argentina[id] ?? muted(id),
  }]));
  const first = titles[0].year, last = titles[titles.length - 1].season;
  if (proOnly) return { file: "argentina-titulos-era-profesional", secondsPerEvent: 0.55, events, teams,
    title: "Fútbol argentino: campeones de la era profesional",
    subtitle: `Todos los títulos de Primera División desde el profesionalismo, ${first} a ${last}`,
    credit: CREDIT, text: { ...TEXT, unit: "títulos" } };
  return { file: "argentina-titulos-primera-division", secondsPerEvent: 0.55, events, teams,
    title: "Fútbol argentino: campeones de Primera División",
    subtitle: `Todos los títulos de liga, ${first} a ${last} · eras amateur y profesional, como los cuenta la AFA`,
    credit: CREDIT, text: { ...TEXT, unit: "títulos" } };
}

function ligaMx() {
  const d = json("football/liga-mx/data/liga-mx.json");
  const NAMES = { Ape: "Apertura", Cla: "Clausura", Inv: "Invierno", Ver: "Verano", Guard: "Guard1anes", Bic: "Bicentenario", Prode: "Prode", Mex: "México" };
  const events = titles.map((t) => {
    const m = t.season.match(/^([A-Za-z]+)–(\d{4})$/);
    let big, name, short;
    if (m) {
      const label = m[1] === "Mex" || m[1] === "Prode" ? `${NAMES[m[1]]} ${m[2].slice(2)}` : `${NAMES[m[1]] ?? m[1]} ${m[2]}`;
      big = m[2]; name = `Torneo ${label}`; short = label;
    } else {
      big = t.season; name = `Temporada ${t.season}`; short = t.season;
    }
    return { winner: t.champion, big, name, short, tag: m ? "Torneos cortos" : "Temporadas largas",
      note: t.runnerUp ? `Subcampeón: ${d.clubs[t.runnerUp]?.name ?? t.runnerUp}` : "" };
  });
  // The short tournaments began in 1996; the 1970 and 1986 World Cup years and Prode 85 were short ones too.
  events.forEach((e, i) => { if (e.tag === "Torneos cortos" && Number(e.big) < 1996) e.tag = "Torneo especial"; });
  const teams = Object.fromEntries([...new Set(events.map((e) => e.winner))].map((id) => [id, {
    name: d.clubs[id].name, logo: soccerLogo(d.clubs[id].crest), color: COLORS["liga-mx"][id] ?? muted(id),
  }]));
  return { file: "liga-mx-campeones", secondsPerEvent: 0.7, events, teams,
    title: "Fútbol mexicano: campeones de liga",
    subtitle: `Todos los títulos de la era profesional, ${d.titles[0].season} a ${short(d.titles[d.titles.length - 1].season)}`,
    credit: CREDIT, text: { ...TEXT, unit: "títulos" } };
  function short(s) { const m = s.match(/^([A-Za-z]+)–(\d{4})$/); return m ? `${NAMES[m[1]]} ${m[2]}` : s; }
}

function nba() {
  const d = json("basketball/nba-rings/data/nba-rings.json");
  const fr = Object.fromEntries(d.franchises.map((f) => [f.id, f]));
  const events = d.seasons.map((s) => ({
    winner: s.champion, big: String(s.year), name: `Finales de la NBA ${s.year}`, short: String(s.year),
    winnerName: s.championName, tag: s.conference === "East" ? (s.year < 1971 ? "División Este" : "Conferencia Este") : (s.year < 1971 ? "División Oeste" : "Conferencia Oeste"),
    note: `${s.result} ante ${s.runnerUpName}${fr[s.champion] && fr[s.champion].name !== s.championName ? ` · hoy ${fr[s.champion].name}` : ""}`,
  }));
  const teams = Object.fromEntries([...new Set(events.map((e) => e.winner))].map((id) => {
    const f = fr[id] ?? { name: d.seasons.find((s) => s.champion === id).championName };
    return [id, { name: f.short ?? f.name, logo: nbaLogo(f.logo), color: COLORS.nba[id] ?? muted(id) }];
  }));
  return { file: "nba-anillos", secondsPerEvent: 0.9, events, teams,
    title: "NBA: anillos de campeón por franquicia",
    subtitle: `Todos los campeones, ${d.seasons[0].year} a ${d.seasons[d.seasons.length - 1].year} · los títulos cuentan para la franquicia actual`,
    credit: CREDIT, text: { ...TEXT, unit: "anillos" } };
}

// The NFL title of every season since 1920: the NFL Championship until 1969, the Super Bowl since 1970.
function nfl() {
  const d = json("american-football/super-bowl/data/super-bowl.json");
  const fr = Object.fromEntries(json("data/nfl/franchises.json").franchises.map((f) => [f.id, f]));
  const games = Object.fromEntries(d.games.map((g) => [g.number, g]));
  const events = d.leagueTitles.map((t) => {
    const sb = t.via.startsWith("Super Bowl") ? games[t.via.replace("Super Bowl ", "")] : null;
    return {
      winner: t.champion, big: String(t.season), name: sb ? `${t.via} (temporada ${t.season})` : `Campeonato de la NFL ${t.season}`,
      short: sb ? t.via.replace("Super Bowl", "SB") : String(t.season), winnerName: t.championName,
      tag: sb ? "Era del Super Bowl" : "Antes del Super Bowl",
      note: `${sb ? `${sb.winPts}–${sb.losePts} ` : ""}ante ${t.runnerUpName ?? "–"}${fr[t.champion] && fr[t.champion].name !== t.championName ? ` · hoy ${fr[t.champion].name}` : ""}`,
    };
  });
  const teams = Object.fromEntries([...new Set(events.map((e) => e.winner))].map((id) => {
    const f = fr[id] ?? { name: d.leagueTitles.find((t) => t.champion === id).championName };
    return [id, { name: f.short ?? f.name, logo: proLogo("nfl", f.logo), color: COLORS.nfl[id] ?? muted(id) }];
  }));
  const last = d.leagueTitles[d.leagueTitles.length - 1];
  return { file: "nfl-campeonatos", secondsPerEvent: 0.85, events, teams,
    title: "NFL: campeonatos por franquicia",
    subtitle: `Cada campeón desde 1920: el Campeonato de la NFL hasta 1969 y el Super Bowl desde 1970 (${last.via}, temporada ${last.season})`,
    credit: CREDIT, text: { ...TEXT, unit: "títulos" } };
}

function nhl() {
  const d = json("ice-hockey/stanley-cup/data/stanley-cup.json");
  const fr = Object.fromEntries(json("data/nhl/franchises.json").franchises.map((f) => [f.id, f]));
  const events = d.seasons.map((s) => ({
    winner: s.champion, big: String(s.year), name: `Final de la Stanley Cup ${s.year}`, short: String(s.year), winnerName: s.championName,
    tag: s.league && s.league !== "NHL" ? `Campeón de la ${s.league}` : "NHL",
    note: `${s.result} ante ${s.runnerUpName}${fr[s.champion] && fr[s.champion].name !== s.championName ? ` · hoy ${fr[s.champion].name}` : ""}`,
  }));
  const teams = Object.fromEntries([...new Set(events.map((e) => e.winner))].map((id) => {
    const f = fr[id] ?? { name: d.seasons.find((s) => s.champion === id).championName };
    return [id, { name: f.short ?? f.name, logo: proLogo("nhl", f.logo), color: COLORS.nhl[id] ?? muted(id) }];
  }));
  return { file: "nhl-stanley-cup", secondsPerEvent: 0.85, events, teams,
    title: "NHL: Stanley Cups por franquicia",
    subtitle: `Cada campeón desde ${d.seasons[0].year} hasta ${d.seasons[d.seasons.length - 1].year} · 1919 y 2005 no se jugaron`,
    credit: CREDIT, text: { ...TEXT, unit: "copas" } };
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
  const name = (id) => CLUB_ES[id] ?? d.clubs[id]?.name ?? id;
  const events = d.finals.map((f) => {
    const legs = (f.legs ?? []).map((l) => l.score + (l.note === "penalties" ? " (pen.)" : "")).join(" y ");
    return { winner: f.champion, big: String(f.year), name: opts.name(f), short: opts.short(f), tag: COUNTRY_ES[f.championCountry] ?? d.countries[f.championCountry]?.name ?? "",
      note: `${legs ? `${legs} ante ` : "Ante "}${f.runnerUp ? name(f.runnerUp) : "–"}` };
  });
  const teams = Object.fromEntries([...new Set(events.map((e) => e.winner))].map((id) => [id, {
    name: name(id), logo: soccerLogo(d.clubs[id]?.crest), color: COLORS[opts.colors][id] ?? muted(id),
  }]));
  return { ...opts.meta(d), events, teams, credit: CREDIT, text: { ...TEXT, unit: "títulos" } };
}

const libertadores = () => cup("copa-libertadores", { colors: "libertadores",
  name: (f) => `Final de la Copa Libertadores ${f.season}`, short: (f) => f.season,
  meta: (d) => ({ file: "copa-libertadores-campeones", secondsPerEvent: 1.0, title: "Copa Libertadores: campeones por club",
    subtitle: `Todas las finales, ${d.finals[0].season} a ${d.finals[d.finals.length - 1].season}` }),
});
const championsLeague = () => cup("champions-league", { colors: "champions-league",
  name: (f) => `Final de la ${f.year < 1993 ? "Copa de Europa" : "Champions League"} ${f.season}`, short: (f) => f.season,
  meta: (d) => ({ file: "champions-league-campeones", secondsPerEvent: 1.0, title: "Champions League: campeones por club",
    subtitle: `Todas las finales de la Copa de Europa y la Champions League, ${d.finals[0].season} a ${d.finals[d.finals.length - 1].season}` }),
});

const BUILDERS = { argentina, "argentina-pro": () => argentina({ proOnly: true }), "liga-mx": ligaMx, nba, nfl, nhl, libertadores, "champions-league": championsLeague };
const key = process.argv[2];
if (!BUILDERS[key]) {
  console.error(`usage: node scripts/make_race_video.mjs ${Object.keys(BUILDERS).join("|")} [--vertical] [--preview]`);
  process.exit(1);
}
const preview = process.argv.includes("--preview");
const vertical = process.argv.includes("--vertical");
const config = BUILDERS[key]();
// Shorts: 1080×1920 and under a minute or so, so the titles go by faster.
if (vertical) Object.assign(config, { vertical: true, file: `${config.file}-short`, secondsPerEvent: Number(process.env.SECONDS_PER_EVENT) || 0.33 });
const [W, H] = vertical ? [1080, 1920] : [1920, 1080];
const out = resolve(ROOT, "videos");
mkdirSync(out, { recursive: true });

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
  // Hold the first frame (2 s, 1 s on Shorts), play every title, hold the final standings (6 s, 4 s on Shorts).
  const per = Math.round(config.secondsPerEvent * FPS);
  const times = [...Array((vertical ? 1 : 2) * FPS).fill(0), ...Array.from({ length: n * per }, (_, i) => i / per), ...Array((vertical ? 4 : 6) * FPS).fill(n)];
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
