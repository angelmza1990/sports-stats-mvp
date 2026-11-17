// Render a bar chart race of titles as an MP4 (1920×1080, 30 fps) for YouTube.
//
//   npm install --no-save puppeteer-core@23.11.1
//   FFMPEG=/path/to/ffmpeg CHROME=/path/to/chrome node scripts/make_race_video.mjs argentina|liga-mx|nba [--preview]
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

function argentina() {
  const d = json("football/argentine-primera/data/argentine-primera.json");
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
  const events = d.titles.map((t) => {
    const suffix = t.season.replace(/^\d{4}(–\d{2,4})?\s*/, "");
    const year = t.season.match(/^\d{4}(–\d{2,4})?/)[0];
    let name = ASSOC[suffix] ?? KIND[suffix] ?? suffix;
    if (!ASSOC[suffix] && t.split && !suffix) name = "Asociación Argentina de Football (año de cisma)";
    const shortName = ASSOC[suffix] ? suffix : suffix === "Liga" ? "Liga (anual)" : KIND[suffix] && suffix ? KIND[suffix].replace(/^(Torneo|Campeonato) (de )?/, "") : "";
    return {
      winner: t.champion, big: year, name, short: `${year} ${shortName}`.trim(),
      tag: t.era === "professional" ? "Era profesional" : "Era amateur",
      note: t.runnerUp ? `Subcampeón: ${d.clubs[t.runnerUp]?.name ?? t.runnerUp}` : "",
    };
  });
  const teams = Object.fromEntries([...new Set(events.map((e) => e.winner))].map((id) => [id, {
    name: d.clubs[id].name, logo: soccerLogo(d.clubs[id].crest), color: COLORS.argentina[id] ?? muted(id),
  }]));
  const first = d.titles[0].year, last = d.titles[d.titles.length - 1].season;
  return { file: "argentina-titulos-primera-division", secondsPerEvent: 0.55, events, teams,
    title: "Fútbol argentino: campeones de Primera División",
    subtitle: `Todos los títulos de liga, ${first} a ${last} · eras amateur y profesional, como los cuenta la AFA`,
    credit: CREDIT, text: { ...TEXT, unit: "títulos" } };
}

function ligaMx() {
  const d = json("football/liga-mx/data/liga-mx.json");
  const NAMES = { Ape: "Apertura", Cla: "Clausura", Inv: "Invierno", Ver: "Verano", Guard: "Guard1anes", Bic: "Bicentenario", Prode: "Prode", Mex: "México" };
  const events = d.titles.map((t) => {
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

const BUILDERS = { argentina, "liga-mx": ligaMx, nba };
const key = process.argv[2];
if (!BUILDERS[key]) {
  console.error(`usage: node scripts/make_race_video.mjs ${Object.keys(BUILDERS).join("|")} [--preview]`);
  process.exit(1);
}
const preview = process.argv.includes("--preview");
const config = BUILDERS[key]();
const out = resolve(ROOT, "videos");
mkdirSync(out, { recursive: true });

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ["--no-sandbox"] });
const page = await browser.newPage();
page.on("pageerror", (e) => console.error("page error:", e.message));
await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
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
  // Hold the first frame two seconds, play every title, hold the final standings six seconds.
  const per = Math.round(config.secondsPerEvent * FPS);
  const times = [...Array(2 * FPS).fill(0), ...Array.from({ length: n * per }, (_, i) => i / per), ...Array(6 * FPS).fill(n)];
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
