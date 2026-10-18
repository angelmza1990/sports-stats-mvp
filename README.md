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

## How it works

```
├── index.html                    # Portfolio landing page
├── assets/                       # Shared theme (light/dark) and styles
├── tennis/big-three/             # The Big Three infographic
│   ├── index.html
│   ├── app.js                    # All charts (D3 v7)
│   ├── style.css
│   └── data/big-three.json       # Generated dataset
├── scripts/build_big_three.py    # Data pipeline
└── data/manual/                  # Hand-curated results newer than the source data
```

The site is plain HTML, CSS and JavaScript with no build step, served by GitHub Pages.

### Rebuilding the data

```bash
python3 scripts/build_big_three.py            # uses cached raw files in data/raw/
python3 scripts/build_big_three.py --refresh  # re-downloads the raw match files
```

The script downloads ATP match results, extracts every title and every Big Three head-to-head match, and **checks the result against the official totals** (Grand Slams, Masters 1000, ATP Finals, titles and head-to-head records). The build fails if any number is off.

Rules applied:

- Walkovers are excluded from head-to-head and win-loss records, as on the ATP site.
- Team events (ATP Cup, United Cup, Laver Cup, Davis Cup) don't count as titles; the Olympics do.
- Dates are the estimated day of each final (the source data only has the start of each tournament).

### Running locally

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

## Data & credits

- Match data: [Jeff Sackmann / Tennis Abstract](https://www.tennisabstract.com/) ATP dataset, via an [archive mirror](https://github.com/Aneeshers/tennis-sackmann-archive). Licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
- Results newer than the dataset are added by hand in [`data/manual/`](data/manual/), each with a source link.

## License

Code is released under the [MIT License](LICENSE). The data keeps its original CC BY-NC-SA 4.0 license.
