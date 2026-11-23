// Title, description and hashtags for uploading each race video (YouTube, Instagram, TikTok), in Spanish or English.
// The facts in the description (the podium, the latest champion, the span) come from the same data as the video.

const COPY = {
  argentina: {
    es: { title: "Todos los campeones del fútbol argentino (1891–2026)", short: "¿Quién es el más campeón del fútbol argentino? 🇦🇷🏆",
      hook: "Más de 130 años de Primera División, título a título: de los clubes ingleses de la era amateur al River–Boca de hoy.",
      ask: "¿Sabías que Alumni fue el club con más títulos de la era amateur? Contanos qué campeonato te sorprendió más 👇",
      tags: ["#futbolargentino", "#riverplate", "#bocajuniors", "#ligaprofesional", "#AFA"] },
    en: { title: "Every Argentine football champion (1891–2026)", short: "Who has won the most titles in Argentina? 🇦🇷🏆",
      hook: "Over 130 years of the Argentine top flight in one race, from the British clubs of the amateur era to River and Boca.",
      ask: "Did you know Alumni won the most titles of the amateur era? Which title surprised you most? 👇",
      tags: ["#argentinefootball", "#riverplate", "#bocajuniors", "#soccer", "#football"] },
  },
  "argentina-pro": {
    es: { title: "River vs Boca: campeones de la era profesional del fútbol argentino", short: "River vs Boca: ¿quién ganó más desde 1931? ⚽",
      hook: "Solo la era profesional, desde 1931: torneos largos, Metropolitanos, Nacionales, Aperturas y Clausuras.",
      ask: "¿Cuál fue el mejor equipo de la era profesional? Te leemos 👇",
      tags: ["#futbolargentino", "#riverplate", "#bocajuniors", "#superclasico", "#ligaprofesional"] },
    en: { title: "River vs Boca: Argentina's champions of the professional era", short: "River vs Boca: who has won more since 1931? ⚽",
      hook: "Only the professional era, since 1931: long seasons, Metropolitanos, Nacionales, Aperturas and Clausuras.",
      ask: "Which was the best team of the professional era? Tell us 👇",
      tags: ["#argentinefootball", "#riverplate", "#bocajuniors", "#superclasico", "#soccer"] },
  },
  "argentina-nacional": {
    es: { title: "Ligas y copas: todos los títulos nacionales del fútbol argentino", short: "Ligas + copas: ¿quién tiene más títulos en Argentina? 🏆",
      hook: "Cada liga y cada copa nacional oficial, de la Copa Chevallier Boutell de 1900 a la Copa Argentina y el Trofeo de Campeones.",
      ask: "¿Las copas nacionales deberían valer lo mismo que una liga? Opiná 👇",
      tags: ["#futbolargentino", "#copaargentina", "#riverplate", "#bocajuniors", "#racing"] },
    en: { title: "Leagues and cups: every national title in Argentine football", short: "Leagues + cups: who has the most titles in Argentina? 🏆",
      hook: "Every official league and national cup, from the 1900 Chevallier Boutell Cup to today's Copa Argentina and Trofeo de Campeones.",
      ask: "Should a national cup count as much as a league title? 👇",
      tags: ["#argentinefootball", "#copaargentina", "#riverplate", "#bocajuniors", "#soccer"] },
  },
  "argentina-nacional-pro": {
    es: { title: "Títulos nacionales de la era profesional: ligas y copas desde 1931", short: "Ligas y copas desde 1931: ¿quién manda? 🇦🇷",
      hook: "Ligas y copas nacionales desde el profesionalismo: la Copa Escobar, la Copa Argentina, las Supercopas y más.",
      ask: "¿Qué título nacional te gustaría que vuelva a jugarse? 👇",
      tags: ["#futbolargentino", "#copaargentina", "#supercopaargentina", "#riverplate", "#bocajuniors"] },
    en: { title: "National titles of Argentina's professional era: leagues and cups since 1931", short: "Leagues and cups since 1931: who rules Argentina? 🇦🇷",
      hook: "Leagues and national cups since the professional era began: Copa Escobar, Copa Argentina, the Supercopas and more.",
      ask: "Which old national cup should come back? 👇",
      tags: ["#argentinefootball", "#copaargentina", "#riverplate", "#bocajuniors", "#soccer"] },
  },
  "argentina-total": {
    es: { title: "El más campeón de Argentina: ligas, copas e internacionales (1891–2026)", short: "El más ganador de Argentina, con internacionales incluidos 🌎🏆",
      hook: "Todos los títulos oficiales: ligas, copas nacionales, Libertadores, Intercontinentales y las copas rioplatenses que cuenta la AFA.",
      ask: "¿Quién es el más grande del fútbol argentino? Defendé a tu club 👇",
      tags: ["#futbolargentino", "#riverplate", "#bocajuniors", "#independiente", "#copalibertadores"] },
    en: { title: "Argentina's most successful club: leagues, cups and international titles", short: "Argentina's biggest winner, international titles included 🌎🏆",
      hook: "Every official title: leagues, national cups, Copa Libertadores, Intercontinental Cups and the Río de la Plata cups the AFA counts.",
      ask: "Who is the biggest club in Argentina? Defend your team 👇",
      tags: ["#argentinefootball", "#riverplate", "#bocajuniors", "#independiente", "#libertadores"] },
  },
  "argentina-total-pro": {
    es: { title: "Todos los títulos de la era profesional: ligas, copas e internacionales", short: "Desde 1931, con copas internacionales: ¿quién gana? 🏆",
      hook: "La era profesional completa: ligas, copas nacionales y todos los títulos internacionales desde 1931.",
      ask: "¿Boca o River? ¿O te sorprendió Independiente? 👇",
      tags: ["#futbolargentino", "#bocajuniors", "#riverplate", "#independiente", "#copalibertadores"] },
    en: { title: "Every title of Argentina's professional era: leagues, cups and international", short: "Since 1931, international cups included: who wins? 🏆",
      hook: "The whole professional era: leagues, national cups and every international title since 1931.",
      ask: "Boca or River? Or did Independiente surprise you? 👇",
      tags: ["#argentinefootball", "#bocajuniors", "#riverplate", "#independiente", "#libertadores"] },
  },
  "liga-mx": {
    es: { title: "Todos los campeones de la Liga MX (1943–2026)", short: "Chivas vs América: ¿quién es el más campeón de México? 🇲🇽",
      hook: "Cada título de la era profesional del fútbol mexicano, de las temporadas largas a los torneos cortos.",
      ask: "¿Chivas o América? Que gane el mejor 👇",
      tags: ["#ligamx", "#futbolmexicano", "#chivas", "#clubamerica", "#cruzazul"] },
    en: { title: "Every Liga MX champion (1943–2026)", short: "Chivas vs América: who is Mexico's biggest champion? 🇲🇽",
      hook: "Every title of Mexican football's professional era, from the long seasons to the short tournaments.",
      ask: "Chivas or America? 👇",
      tags: ["#ligamx", "#mexicanfootball", "#chivas", "#clubamerica", "#soccer"] },
  },
  nba: {
    es: { title: "NBA: anillos de campeón por franquicia (1947–2026)", short: "Celtics vs Lakers: la carrera por los anillos de la NBA 🏀",
      hook: "Todas las Finales de la NBA desde 1947. Cada anillo cuenta para la franquicia actual: los Minneapolis Lakers son los Lakers.",
      ask: "¿Celtics o Lakers? ¿Quién termina arriba en 10 años? 👇",
      tags: ["#NBA", "#basquet", "#celtics", "#lakers", "#nbafinals"] },
    en: { title: "NBA championships by franchise (1947–2026)", short: "Celtics vs Lakers: the race for NBA rings 🏀",
      hook: "Every NBA Finals since 1947. Each ring counts for today's franchise, so the Minneapolis Lakers are the Lakers.",
      ask: "Celtics or Lakers: who's on top in 10 years? 👇",
      tags: ["#NBA", "#basketball", "#celtics", "#lakers", "#nbafinals"] },
  },
  nfl: {
    es: { title: "NFL: campeonatos por franquicia, del 1920 al Super Bowl", short: "¿Qué franquicia tiene más títulos en la NFL? 🏈",
      hook: "Más de 100 años de NFL: los campeonatos antes del Super Bowl y todos los Super Bowls, con el resultado de cada final.",
      ask: "¿Packers, Patriots o Steelers? ¿Quién es la mejor franquicia? 👇",
      tags: ["#NFL", "#superbowl", "#futbolamericano", "#packers", "#patriots"] },
    en: { title: "NFL championships by franchise, from 1920 to the Super Bowl", short: "Which franchise has the most NFL titles? 🏈",
      hook: "Over 100 years of the NFL: the championships before the Super Bowl and every Super Bowl, with the score of each final.",
      ask: "Packers, Patriots or Steelers: who's the best franchise ever? 👇",
      tags: ["#NFL", "#superbowl", "#football", "#packers", "#patriots"] },
  },
  nhl: {
    es: { title: "NHL: Stanley Cups por franquicia (1915–2026)", short: "¿Quién ganó más Stanley Cups? 🏒",
      hook: "Cada Stanley Cup desde 1915, incluidas las ligas rivales de los primeros años.",
      ask: "¿Llegará alguien a las Stanley Cups de los Canadiens? 👇",
      tags: ["#NHL", "#stanleycup", "#hockey", "#canadiens", "#hockeysobrehielo"] },
    en: { title: "NHL: Stanley Cups by franchise (1915–2026)", short: "Who has won the most Stanley Cups? 🏒",
      hook: "Every Stanley Cup since 1915, including the rival leagues of the early years.",
      ask: "Will anyone ever catch the Canadiens? 👇",
      tags: ["#NHL", "#stanleycup", "#hockey", "#habs", "#icehockey"] },
  },
  "argentina-internacional": {
    es: { title: "Fútbol argentino: todos los títulos internacionales por club", short: "¿Quién es el Rey de Copas argentino? Boca vs Independiente 🏆🌎",
      hook: "Cada copa internacional ganada por un club argentino: Libertadores, Sudamericana, Intercontinentales, Recopas, Supercopas y las copas rioplatenses.",
      ask: "¿Boca o Independiente: quién es el verdadero Rey de Copas? 👇",
      tags: ["#futbolargentino", "#reydecopas", "#bocajuniors", "#independiente", "#copalibertadores"] },
    en: { title: "Argentine football: every international title by club", short: "Argentina's King of Cups: Boca vs Independiente 🏆🌎",
      hook: "Every international cup won by an Argentine club: Libertadores, Sudamericana, Intercontinental, Recopa, Supercopa and the Río de la Plata cups.",
      ask: "Boca or Independiente: who is the real King of Cups? 👇",
      tags: ["#argentinefootball", "#kingofcups", "#bocajuniors", "#independiente", "#copalibertadores"] },
  },
  "sudamerica-internacional": {
    es: { title: "Sudamérica: todos los títulos internacionales por club", short: "¿Quién ganó más copas internacionales en Sudamérica? 🌎🏆",
      hook: "Todos los clubes del continente, todas las copas: Libertadores, Sudamericana, Intercontinental, Mundial de Clubes, Recopa, Mercosur, Merconorte, Suruga y las rioplatenses.",
      ask: "¿Qué club sudamericano es el más grande a nivel internacional? 👇",
      tags: ["#futbolsudamericano", "#conmebol", "#copalibertadores", "#copasudamericana", "#reydecopas"] },
    en: { title: "South America: every international title by club", short: "Which South American club has won the most international cups? 🌎🏆",
      hook: "Every club on the continent, every cup: Libertadores, Sudamericana, Intercontinental, Club World Cup, Recopa, Mercosur, Merconorte, Suruga and the Río de la Plata cups.",
      ask: "Which is South America's biggest club internationally? 👇",
      tags: ["#southamericanfootball", "#conmebol", "#copalibertadores", "#copasudamericana", "#soccer"] },
  },
  libertadores: {
    es: { title: "Copa Libertadores: todos los campeones (1960–2025)", short: "¿Quién es el Rey de Copas? Todos los campeones de la Libertadores 🏆",
      hook: "Todas las finales de la Copa Libertadores, con el resultado de cada partido y el país de cada campeón.",
      ask: "¿Quién gana la próxima Libertadores? 👇",
      tags: ["#copalibertadores", "#libertadores", "#conmebol", "#independiente", "#bocajuniors"] },
    en: { title: "Copa Libertadores: every champion (1960–2025)", short: "Who is South America's King of Cups? 🏆",
      hook: "Every Copa Libertadores final, with the score of each leg and the champion's country.",
      ask: "Who wins the next Libertadores? 👇",
      tags: ["#copalibertadores", "#libertadores", "#conmebol", "#southamericanfootball", "#soccer"] },
  },
  "champions-league": {
    es: { title: "Champions League: todos los campeones de Europa (1956–2026)", short: "Real Madrid y la carrera de la Champions League ⭐",
      hook: "Todas las finales de la Copa de Europa y la Champions League, con el resultado y el país de cada campeón.",
      ask: "¿Alguien podrá alcanzar al Real Madrid? 👇",
      tags: ["#championsleague", "#UCL", "#realmadrid", "#futboleuropeo", "#uefa"] },
    en: { title: "Champions League: every European champion (1956–2026)", short: "Real Madrid and the Champions League race ⭐",
      hook: "Every European Cup and Champions League final, with the score and the champion's country.",
      ask: "Will anyone ever catch Real Madrid? 👇",
      tags: ["#championsleague", "#UCL", "#realmadrid", "#football", "#uefa"] },
  },
  "tenis-slams-atp": {
    es: { title: "Grand Slams de la Era Abierta: Djokovic, Nadal, Federer y todos los campeones", short: "La carrera por los Grand Slams: Djokovic, Nadal, Federer 🎾",
      hook: "Todos los Grand Slams masculinos desde Roland Garros 1968, con el rival y el marcador de cada final.",
      ask: "¿Quién es el GOAT? ¿Y llegará Alcaraz o Sinner a esos números? 👇",
      tags: ["#tenis", "#grandslam", "#djokovic", "#nadal", "#federer", "#alcaraz"] },
    en: { title: "Open Era Grand Slams: Djokovic, Nadal, Federer and every champion", short: "The Grand Slam race: Djokovic, Nadal, Federer 🎾",
      hook: "Every men's Grand Slam since Roland Garros 1968, with the opponent and score of each final.",
      ask: "Who's the GOAT? And can Alcaraz or Sinner get there? 👇",
      tags: ["#tennis", "#grandslam", "#djokovic", "#nadal", "#federer", "#alcaraz"] },
  },
  "tenis-slams-wta": {
    es: { title: "Grand Slams femeninos de la Era Abierta: Serena, Graf, Evert, Navratilova", short: "Serena vs Graf: la carrera por los Grand Slams 🎾",
      hook: "Todos los Grand Slams femeninos desde Roland Garros 1968, con la rival y el marcador de cada final.",
      ask: "¿Serena o Graf? ¿Quién es la mejor de la historia? 👇",
      tags: ["#tenis", "#grandslam", "#serenawilliams", "#steffigraf", "#WTA"] },
    en: { title: "Women's Open Era Grand Slams: Serena, Graf, Evert, Navratilova", short: "Serena vs Graf: the Grand Slam race 🎾",
      hook: "Every women's Grand Slam since Roland Garros 1968, with the opponent and score of each final.",
      ask: "Serena or Graf: who's the greatest ever? 👇",
      tags: ["#tennis", "#grandslam", "#serenawilliams", "#steffigraf", "#WTA"] },
  },
  "tenis-masters": {
    es: { title: "Masters 1000: todos los campeones desde 1990", short: "¿Quién ganó más Masters 1000? 🎾",
      hook: "Cada torneo Masters 1000 desde la creación de la categoría en 1990: Indian Wells, Miami, Montecarlo, Madrid, Roma y más.",
      ask: "¿Cuál es tu Masters 1000 favorito? 👇",
      tags: ["#tenis", "#masters1000", "#ATP", "#djokovic", "#nadal"] },
    en: { title: "Masters 1000: every champion since 1990", short: "Who has won the most Masters 1000 titles? 🎾",
      hook: "Every Masters 1000 since the series began in 1990: Indian Wells, Miami, Monte Carlo, Madrid, Rome and more.",
      ask: "What's your favorite Masters 1000? 👇",
      tags: ["#tennis", "#masters1000", "#ATP", "#djokovic", "#nadal"] },
  },
  "tenis-numero-1-atp": {
    es: { title: "Semanas como número 1 del ranking ATP (1973–2026)", short: "¿Quién estuvo más semanas como número 1? 🎾👑",
      hook: "Cada semana en la cima del ranking ATP desde 1973, año por año. Las semanas del ranking congelado de 2020 no cuentan para nadie.",
      ask: "¿Alguien podrá superar las semanas de Djokovic? 👇",
      tags: ["#tenis", "#ATP", "#numero1", "#djokovic", "#federer", "#sinner"] },
    en: { title: "Weeks at No. 1 in the ATP rankings (1973–2026)", short: "Who spent the most weeks at No. 1? 🎾👑",
      hook: "Every week at the top of the ATP rankings since 1973, year by year. The frozen 2020 ranking counts for nobody.",
      ask: "Will anyone ever beat Djokovic's weeks at No. 1? 👇",
      tags: ["#tennis", "#ATP", "#worldnumber1", "#djokovic", "#federer", "#sinner"] },
  },
  "tenis-numero-1-wta": {
    es: { title: "Semanas como número 1 del ranking WTA (1975–2026)", short: "Graf, Navratilova, Serena: las reinas del número 1 🎾👑",
      hook: "Cada semana en la cima del ranking WTA desde 1975, año por año. Las semanas del ranking congelado de 2020 no cuentan para nadie.",
      ask: "¿Quién fue la número 1 más dominante? 👇",
      tags: ["#tenis", "#WTA", "#numero1", "#steffigraf", "#serenawilliams"] },
    en: { title: "Weeks at No. 1 in the WTA rankings (1975–2026)", short: "Graf, Navratilova, Serena: the queens of No. 1 🎾👑",
      hook: "Every week at the top of the WTA rankings since 1975, year by year. The frozen 2020 ranking counts for nobody.",
      ask: "Who was the most dominant No. 1 ever? 👇",
      tags: ["#tennis", "#WTA", "#worldnumber1", "#steffigraf", "#serenawilliams"] },
  },
};

export function metadata(key, config) {
  const en = config.file.endsWith("-en");
  const c = COPY[key][en ? "en" : "es"];
  // Final standings, as in the last frame (ties ranked by who got there first).
  const count = {}, reached = {};
  config.events.forEach((e, i) => { count[e.winner] = (count[e.winner] ?? 0) + (e.add ?? 1); reached[e.winner] = i; });
  const top = Object.keys(count).sort((a, b) => count[b] - count[a] || reached[a] - reached[b]).slice(0, 3);
  const unit = config.text.unit || (en ? "weeks" : "semanas");
  const podium = top.map((id, i) => `${["🥇", "🥈", "🥉"][i]} ${config.teams[id].name}: ${count[id]}`).join("\n");
  const last = config.events.at(-1);
  const lastName = last.winnerName ?? config.teams[last.winner].name;
  const latest = config.text.unit
    ? `${en ? "Latest champion" : "Último campeón"}: ${lastName} (${last.name}${last.name.includes(last.big) ? "" : ` ${last.big}`})`
    : `${en ? "Current No. 1" : "Número 1 actual"}: ${lastName}`;
  const general = en ? ["#StatRace", "#barchartrace", "#sportsstats"] : ["#StatRace", "#barchartrace", "#estadisticas"];
  const hashtags = [...(config.vertical ? ["#shorts"] : []), ...c.tags, ...general].join(" ");
  const description = [
    c.hook,
    `${config.subtitle}.`,
    `${en ? `Top 3 (${unit})` : `Podio (${unit})`}:\n${podium}`,
    latest,
    c.ask,
    `${config.credit}.`,
  ].join("\n\n");
  return { title: config.vertical ? c.short : c.title, description, hashtags };
}
