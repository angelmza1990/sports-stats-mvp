# Sports Stats

Interactive sports infographics built with [D3.js](https://d3js.org/) and open data.

**Live site:** https://angelmza1990.github.io/sports-stats-mvp/

## Infographics

### 🎾 [The Big Three](https://angelmza1990.github.io/sports-stats-mvp/tennis/big-three/)

Federer, Nadal and Djokovic by the numbers:

- **The race for the record:** an animated bar chart race of cumulative Grand Slams, Masters 1000 titles, ATP Finals and all titles, month by month since 2001
- **Who got there faster?** Titles won by age
- **Each one had a kingdom:** Grand Slam titles by tournament
- **Masters 1000, event by event**
- **Head to head:** all 150 matches between them, split by surface, event and stage, with a match-by-match timeline
- **Titles by surface**

| | Grand Slams | Masters 1000 | ATP Finals | Titles | Head to head |
|---|---:|---:|---:|---:|---|
| Novak Djokovic | 24 | 40 | 7 | 102 | 31–29 vs Nadal, 27–23 vs Federer |
| Rafael Nadal | 22 | 36 | 0 | 92 | 24–16 vs Federer |
| Roger Federer | 20 | 28 | 6 | 103 | |

### 🎾 [Grand Slams](https://angelmza1990.github.io/sports-stats-mvp/tennis/grand-slams/)

Every Open Era men's singles major since Roland Garros 1968:

- **The race for the most majors:** an animated bar chart race of the top 10 champions, updated after every Slam and split by tournament
- **Most titles:** overall and at the Australian Open, Roland Garros, Wimbledon and the US Open
- **Most runner-up finishes:** tables of finals lost at each major
- **Nations:** how many countries have won each Slam, with titles and number of champions per country
- **Match records:** most matches won and played at each major
- **The most repeated finals**

### 🏀 [NBA Rings](https://angelmza1990.github.io/sports-stats-mvp/basketball/nba-rings/)

Every NBA championship since 1947:

- **The race for the most rings:** an animated bar chart race of championships by franchise, season by season, with team logos
- **East vs West:** the conference split overall and by decade
- **Every champion:** one tile per season with the Finals result and MVP
- **Rings by franchise:** all 30 teams grouped by conference, including the ones still waiting
- **The most repeated Finals** and a table of **Finals lost** by franchise
- **How the Finals were won:** sweeps to Game 7s
- **Finals MVP leaders**

### ⚽ [Copa Libertadores](https://angelmza1990.github.io/sports-stats-mvp/football/copa-libertadores/) and [Champions League](https://angelmza1990.github.io/sports-stats-mvp/football/champions-league/)

Two pages with the same structure, one per competition:

- **The race for the most titles:** an animated bar chart race by club, with crests and flags
- **Champions and runners-up:** by club, or every final with its score
- **The most repeated finals**
- **Titles and runners-up by country**
- **All-time club records:** most wins, goals and participations
- **Player records:** all-time top scorers and most appearances

## How it works

```
├── index.html                    # Portfolio landing page
├── assets/                       # Shared theme (light/dark) and styles
├── tennis/big-three/             # The Big Three infographic
│   ├── index.html
│   ├── app.js                    # All charts (D3 v7)
│   ├── style.css
│   └── data/big-three.json       # Generated dataset
├── tennis/grand-slams/           # Grand Slams infographic
├── basketball/nba-rings/         # NBA Rings infographic
├── football/                     # Copa Libertadores + Champions League (shared football.js)
├── scripts/
│   ├── tennis_data.py            # Shared ATP + Wikipedia draw helpers
│   ├── build_big_three.py        # Big Three data pipeline
│   ├── build_grand_slams.py      # Grand Slams data pipeline
│   ├── build_nba_rings.py        # NBA data pipeline
│   ├── build_football.py         # Football data pipeline
│   └── wikitables.py             # Generic Wikipedia table parser
├── data/
│   ├── manual/                   # Hand-curated tennis results and nationality fixes
│   ├── nba/franchises.json       # Every NBA franchise and its historical names
│   └── football/clubs.json       # Football clubs, their Wikipedia aliases and crest ids
└── .github/workflows/            # Automatic data updates
```

The site is plain HTML, CSS and JavaScript with no build step, served by GitHub Pages.

### Automatic updates

A [GitHub Actions workflow](.github/workflows/update-data.yml) rebuilds every dataset **twice a year**, on July 1 (after the NBA Finals) and December 31 (after the ATP Finals), commits any changes and republishes the site. It can also be run by hand from the Actions tab. If a dataset fails validation, the previous version is kept and the run is marked as failed.

### Rebuilding the data

```bash
python3 scripts/build_big_three.py --refresh  # tennis: re-downloads the raw match files
python3 scripts/build_grand_slams.py --refresh # tennis: Open Era Grand Slams
python3 scripts/build_nba_rings.py --refresh  # NBA: re-downloads the Wikipedia table
python3 scripts/build_football.py --refresh   # football: both competitions
```

Leave out `--refresh` to use the cached copies in `data/raw/`.

**Tennis.** The script downloads ATP match results, extracts every title and every Big Three head-to-head match, and **checks the result against the official totals** (Grand Slams, Masters 1000, ATP Finals, titles and head-to-head records). The build fails if any number is off.

Rules applied:

- Walkovers are excluded from head-to-head and win-loss records, as on the ATP site.
- Team events (ATP Cup, United Cup, Laver Cup, Davis Cup) don't count as titles; the Olympics do.
- Dates are the estimated day of each final (the source data only has the start of each tournament).

**Grand Slams.** The script reads every Grand Slam match since Roland Garros 1968 from the same ATP files. Any major the files don't cover yet is rebuilt match by match from its Wikipedia draw page (all 127 matches must parse, or the build fails). Nationality is the one represented at the time: a small [override file](data/manual/slam_nationality_overrides.csv) corrects players the ATP lists under today's country (Lendl and Kodeš for Czechoslovakia, for example). The build checks title totals for the all-time leaders and the number of editions of each major.

**NBA.** The script reads Wikipedia's [List of NBA champions](https://en.wikipedia.org/wiki/List_of_NBA_champions) table, maps every historical team name to its current franchise (the Minneapolis Lakers count for the Lakers, the Seattle SuperSonics for the Thunder) and checks that every season is present and that all titles through 2026 match the known totals. A new team name makes the build fail until it is added to [`data/nba/franchises.json`](data/nba/franchises.json).

**Football.** The script reads each competition's list of finals, all-time club table, all-time top scorers and most-appearance table from Wikipedia, and maps clubs to crests through [`data/football/clubs.json`](data/football/clubs.json) (a club missing from that file still appears, with a lettered badge). It checks that there is one final per season and that every club's title count matches the known history.

### Running locally

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

## Data & credits

- Match data: [Jeff Sackmann / Tennis Abstract](https://www.tennisabstract.com/) ATP dataset, via an [archive mirror](https://github.com/Aneeshers/tennis-sackmann-archive). Licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
- Tennis results newer than the dataset are added by hand in [`data/manual/`](data/manual/), each with a source link, or rebuilt from Wikipedia draw pages (CC BY-SA 4.0).
- Flags: [Flagpedia](https://flagpedia.net) (flagcdn.com).
- NBA championships: [Wikipedia](https://en.wikipedia.org/wiki/List_of_NBA_champions), CC BY-SA 4.0.
- Football finals, club records and player records: Wikipedia (CC BY-SA 4.0).
- NBA team logos and football club crests are loaded from ESPN's public CDN. Team names, logos and crests are trademarks of their respective owners, shown for identification only. This project is not affiliated with the NBA, CONMEBOL or UEFA.

## License

Code is released under the [MIT License](LICENSE). Data keeps its original license (CC BY-NC-SA 4.0 for the ATP match data, CC BY-SA 4.0 for Wikipedia).
