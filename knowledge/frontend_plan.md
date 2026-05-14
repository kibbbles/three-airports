# Frontend Plan — Three DMV Airports

A data-driven blog post styled after Max Woolf's writing: narrative prose, charts as
evidence, clean typography, no clutter. Deployed as a static site on GitHub Pages.
Eventually becomes the second card on a personal landing page (after UFC/Kabe's Maybes).

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| Site framework | **Astro** | Builds to pure static HTML, native GitHub Pages deploy, "islands" load client JS only where needed |
| Globe | **Globe.gl** | Beautiful out of the box, lightweight Three.js wrapper, built for flight arc animations |
| Interactive dashboard | **Crossfilter + D3** | Linked multi-chart filtering, embedded mid-scroll as an Astro island |
| Charts (static) | **Plotly** | Already exported as self-contained HTML; embed via `<iframe>` or re-render from JSON |
| Styling | **CSS custom properties + prose layout** | Max Woolf style: wide readable column, neutral/dark background, no UI framework overhead |
| Deploy | **GitHub Actions → GitHub Pages** | Free, automatic on push to `main` |

No React, no Next.js — the landing page integration can handle that later. Astro islands
give component isolation without a full SPA.

---

## Narrative Structure

The post is told in first person. You grew up in the DMV, IAD is your airport for
international travel (Taiwan — IAD→TSA is in the dataset), and you recently flew
Tampa for a cruise. The data confirms and complicates things you already felt.

### Section 0 — Hero

- Full-width **Globe.gl** globe, auto-rotating
- Two arc layers rendered on load:
  - **Domestic** (from `routes.geojson`): 217 routes, colored by late rate (green → red)
  - **International** (from `t100_intl_dmv.parquet` → `intl_routes.json`): IAD/DCA/BWI
    outbound international routes, arc thickness scaled by passenger volume, muted color
    to visually separate from domestic
- IAD→TSA arc highlighted with a label ("my route to Taiwan")
- Tagline overlay: *"Ten years of flights. Three airports. One DMV kid."*

### Section 1 — Introduction

- 2–3 paragraphs: personal context, the three airports and their personalities
  (IAD = international/United hub, DCA = perimeter-restricted/American hub, BWI = Southwest/value)
- Stat cards pulled from `airport_summary.json`:
  - Total flights per airport (2015–2025)
  - Overall late rate
  - Cancellation rate
- Sparkline charts (by-year late rate) for each airport — COVID dip visible

### Section 2 — When Delays Happen

- Narrative: morning flights are more reliable, summer and winter are worst
- **Heatmap trio** — the three `heatmap_[AIRPORT].html` embeds side by side
  (hour of departure × month, late rate color scale)
- Key callout: BWI evening flights in July/August are the worst combination

### Section 3 — The Route Explorer *(Crossfilter dashboard — mid-scroll)*

- Full-width interactive section, loaded as an Astro island (client:visible)
- **Four linked panels** driven by Crossfilter on `routes.geojson` properties:
  1. **Bar chart** — late rate by destination (sorted descending), click to filter
  2. **Scatter plot** — mean delay vs mean fare, colored by airport
  3. **Bar chart** — flight frequency by carrier
  4. **Data table** — selected routes with all key metrics
- Filter controls: airport selector (IAD / DCA / BWI), cluster selector (k-means 0–5)
- Introductory sentence sets the scene: *"217 routes. Filter by airport, cluster, or
  carrier to find the ones worth worrying about."*

### Section 4 — Route Clusters

- Narrative: HDBSCAN found 2 meaningful clusters + noise; k-means (k=6) gives finer
  structure. What do the clusters mean in plain English?
- **Globe.gl second instance** (smaller, embedded inline) — arcs colored by k-means
  cluster rather than late rate, cluster legend to the side
- Cluster character table derived from `model_summary.json` + `routes.geojson` properties:
  describe each of the 6 k-means clusters in one sentence (high-frequency reliable,
  thin leisure routes, etc.)
- Call out Cluster 1 (the 5-route outlier HDBSCAN found) by name

### Section 5 — Anomalous Routes

- Narrative: Isolation Forest flagged 87 routes that persistently misbehave post-2022.
  BWI has the most (42), DCA next (30), IAD least (15). BWI→ATL flagged every year for
  5 consecutive years.
- **Dot-plot / bump chart** — top 15 most-anomalous routes, years flagged shown as
  filled dots on a timeline
- Personal hook: did any of the user's own routes (IAD→TPA, IAD→TSA) show up?
  Check and annotate if so.

### Section 6 — What the Models Say

- Narrative: Prophet forecasts late rate by airport through 2026. BWI has been running
  above forecast since 2022 (avg gap +0.040). IAD and DCA are roughly on trend.
- **Line chart per airport** — actual late rate vs Prophet forecast, shaded confidence
  band, gap highlighted post-2022
- GAM callout box: *"Weather adds signal but fog alone isn't the story (p=0.88).
  Carrier and NAS delays dominate."* AUC 0.674.
- One-sentence note on the silhouette score (0.2552) and what it means: the clusters
  are real but not sharply separated — this is a continuous spectrum of route quality,
  not discrete buckets.

### Section 7 — Limitations

Short, honest section. Builds trust rather than eroding it.

- **No international delay data** — T100 international gives passenger volume only;
  BTS on-time performance is domestic flights only. IAD→TSA delay experience not in
  the dataset.
- **No international fare data** — DB1B is domestic only by design; no public
  equivalent exists for international routes.
- **NOAA coverage ends August 2025** — 4.5% of rows have no weather data (flights
  after that date). Weather features are excluded from those rows.
- **DB1B is a 10% ticket sample** — fare figures are estimates, not census values.
- **T100 is capacity/volume, not individual flights** — carrier share and seat counts
  are monthly aggregates joined at route+month grain.

### Section 8 — Conclusion / Personal Takeaway

- 1–2 paragraphs: what this data says about flying out of the DMV as someone who
  actually does it. IAD is your airport for a reason — international reach, United
  hub connections, lower anomaly count than BWI.
- Closing line ties back to the personal hook.

---

## Data Layer

All frontend data lives in `data/exports/`. One additional export needed.

| File | Status | Feeds |
|---|---|---|
| `airports.json` | ✅ exported | Globe marker coords |
| `routes.geojson` | ✅ exported | Globe domestic arcs, Crossfilter dashboard |
| `airport_summary.json` | ✅ exported | Section 1 stat cards, sparklines |
| `heatmaps.json` + HTML | ✅ exported | Section 2 heatmap embeds |
| `model_summary.json` | ✅ exported | Section 6 charts, Section 3 cluster legend |
| `intl_routes.json` | ❌ needs export | Globe international arc layer |

### `intl_routes.json` schema (to build in `10_exports.ipynb`)

Aggregate `t100_intl_dmv.parquet` to one row per origin–dest pair (sum passengers,
mean departures per month across all years and carriers):

```json
[
  {
    "origin": "IAD",
    "dest": "LHR",
    "dest_city": "London, United Kingdom",
    "dest_country": "United Kingdom",
    "total_passengers": 3849695,
    "o_lat": 38.9531, "o_lon": -77.4565,
    "d_lat": 51.4775, "d_lon": -0.4614
  }
]
```

Needs a `INTL_AIRPORT_COORDS` lookup for foreign airports in the notebook.
Priority coords: all unique DEST values in `t100_intl_dmv` where ORIGIN is IAD/DCA/BWI.

---

## Component Breakdown

```
src/
  pages/
    index.astro          ← blog post page
  components/
    GlobeHero.astro      ← Section 0, Globe.gl, client:load
    StatCards.astro      ← Section 1 airport summary cards
    Sparkline.astro      ← by-year late rate mini chart
    HeatmapEmbed.astro   ← Section 2, wraps plotly HTML iframe
    RouteExplorer.astro  ← Section 3, Crossfilter island, client:visible
    ClusterGlobe.astro   ← Section 4, second Globe.gl instance, client:visible
    AnomalyDotPlot.astro ← Section 5, D3 dot plot
    ForecastChart.astro  ← Section 6, Prophet line chart
  styles/
    global.css           ← prose layout, typography, color tokens
  data/                  ← symlink or copy of data/exports/ JSON files
```

---

## Design Tokens

Inspired by Max Woolf's aesthetic: dark background, high-contrast text, accent color
per airport, generous whitespace, no decorative chrome.

```css
--bg:           #0f1117;
--surface:      #1a1d27;
--text:         #e8e8e8;
--muted:        #888;
--iad:          #4e9af1;   /* blue  */
--dca:          #f97316;   /* orange */
--bwi:          #22c55e;   /* green */
--late-low:     #22c55e;
--late-high:    #ef4444;
--font-prose:   'Inter', system-ui, sans-serif;
--font-mono:    'JetBrains Mono', monospace;
--max-width:    740px;     /* prose column */
--wide-width:   1100px;    /* charts / globe full bleed */
```

---

## Build & Deploy

```yaml
# .github/workflows/deploy.yml
- uses: withastro/action@v2
- deploy to github-pages on push to main
```

Astro config:
```js
// astro.config.mjs
export default defineConfig({
  site: 'https://kibbbles.github.io',
  base: '/three-airports',
  output: 'static',
})
```

---

## Outstanding Decisions

- [ ] Does the landing page live on the same Astro site or is this a standalone repo?
      Affects whether `base` path above is `/three-airports` or `/`
- [ ] Add a `data/` symlink in `src/` pointing to `data/exports/` at build time,
      or copy files into `public/data/` for static serving
- [ ] International airport coords lookup for `intl_routes.json` — build a coords dict
      for the ~150 unique foreign DEST codes, or use a public airport database (ourairports.com
      has a free CSV with IATA codes + lat/lon)
- [ ] Confirm GitHub repo name for the Pages URL (`kibbbles.github.io/three-airports`)

---

## Incremental Build Order

1. Astro scaffold + deploy pipeline (confirm GitHub Pages works with a placeholder)
2. `intl_routes.json` export (add Section 6 to `10_exports.ipynb`)
3. Global CSS + prose layout
4. Section 1 — stat cards (static, no JS)
5. Section 0 — Globe.gl hero (domestic arcs first, then international layer)
6. Section 2 — heatmap embeds
7. Section 3 — Crossfilter dashboard
8. Section 4 — cluster globe
9. Sections 5, 6 — anomaly dot plot, forecast chart
10. Section 7, 8 — limitations + conclusion copy
11. Landing page card integration
