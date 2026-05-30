# Frontend Plan — Three DMV Airports

A data-driven blog post told in first person. Deployed as a static site on GitHub Pages.

---

## Stack

| Layer | Choice |
|---|---|
| Site framework | **Astro** — static output, GitHub Pages deploy, scoped CSS per component |
| Globe | **Globe.gl** — Three.js wrapper, domestic + international arc layers, filter buttons |
| Charts | **D3 v7** — all charts are client-side D3 inside `<script>` blocks, no Plotly |
| Styling | CSS custom properties, dark theme, prose layout |
| Deploy | GitHub Actions → GitHub Pages (`kibbbles.github.io/three-airports`) |

No React, no UI framework, no iframes.

---

## Section Order

| # | Section | Component | Status |
|---|---|---|---|
| 0 | Hero globe | `GlobeHero.astro` | ✅ shipped |
| — | Table of contents | inline in `index.astro` | ✅ shipped |
| 1 | Overview + stat cards | inline in `index.astro` | ✅ shipped |
| 2 | Volume over time | `FlightVolumeStreamgraph.astro` | ✅ shipped |
| 3 | Explore 2.7M flights | `CrossfilterDash.astro` | ✅ shipped |
| 4 | Fare comparison | `FareComparison.astro` | ✅ shipped |
| 4b | Airline breakdown | `AirlineBreakdown.astro` | ✅ shipped |
| 5 | When delays happen | `SlopeChart.astro` | ✅ shipped |
| 6 | Misbehaving routes | `AnomalyList.astro` | ✅ shipped |
| 7 | Forecasts | `ForecastChart.astro` | ✅ shipped |
| 8 | Cancellations | `CancellationChart.astro` | ✅ shipped |
| 9 | Weather and delays | `WeatherDelays.astro` | 🔲 planned |
| 10 | Carrier on-time | `CarrierOnTime.astro` | ✅ shipped |
| 11 | Conclusion | inline in `index.astro` | 🔲 planned |
| 12 | Limitations | inline in `index.astro` | ✅ shipped (move to end) |

---

## Shipped Components

### `GlobeHero.astro`
- Full-viewport auto-rotating globe
- Two arc layers: domestic (colored IAD/DCA/BWI) + international (thickness = passenger volume)
- Filter buttons (All / IAD / DCA / BWI) filter arc data
- Hover (desktop) and touch (mobile) enable pinch zoom, pause auto-rotate, fade overlay
- Data: `routes.geojson` (domestic), `intl_routes.json` (international)

### `FlightVolumeStreamgraph.astro`
- D3 stacked area chart, 2015–2026 monthly flight counts
- COVID shaded band (Mar 2020 – Dec 2021)
- Hover tooltip: airport breakdown + "Total N" centered footer
- Data: `route_monthly.json`

### `CrossfilterDash.astro`
- Linked brush-filter dashboard: date, hour, delay, distance histograms
- Airport toggle buttons, reset button
- Header shows selected date range + flights + routes
- Data: `crossfilter_data.json`

### `FareComparison.astro`
- Three charts sharing a single tooltip element (`#fare-tooltip`):
  1. Line chart — avg fare by year per airport
  2. Dumbbell — all 52 shared destinations, dots per airport, volume bar behind
  3. Horizontal bar — IAD fare premium vs cheapest airport per route
- Tooltip inner CSS uses `<style is:global>` (Astro scoping doesn't reach `innerHTML`)
- Data: `fare_comparison.json`

### `SlopeChart.astro`
- Static SVG (server-rendered), 4 panels: Spring / Summer / Fall / Winter
- Each panel: morning (6–10am) vs evening (6–10pm) late rate per airport
- Static labels show relative % change (e.g. `IAD +192%`)
- Hover tooltip shows exact `X% → Y%` for all three airports
- Data: `heatmaps.json`

### `AirlineBreakdown.astro`
- Three donut charts — carrier market share by passenger volume per airport (top 6 + Other)
- Three horizontal bar charts — median one-way fare per carrier, shared x-axis across airports
- Lollipop/beeswarm — within-carrier fare premium vs BWI, two tracks: IAD (blue) and DCA (orange)
- Hub premium analysis powered by `hub_premium.json` (within-carrier, same-route IAD/DCA vs BWI)
- Data: `carrier_breakdown.json`, `hub_premium.json`

### `AnomalyList.astro`
- Ranked list of 87 persistently anomalous routes (Isolation Forest, post-2022)
- Bar shows years flagged out of 5
- Data: `anomalies.json`

### `ForecastChart.astro`
- Prophet forecast vs actuals per airport, shaded 95% CI
- Data: `forecasts.json`

---

## Data Files (`frontend/public/data/`)

| File | Feeds |
|---|---|
| `routes.geojson` | Globe domestic arcs, crossfilter |
| `intl_routes.json` | Globe international arcs |
| `airport_summary.json` | Stat cards |
| `heatmaps.json` | Slope chart |
| `route_monthly.json` | Streamgraph |
| `crossfilter_data.json` | Crossfilter dashboard |
| `fare_comparison.json` | Fare comparison charts |
| `anomalies.json` | Anomaly list |
| `forecasts.json` | Forecast chart |
| `carrier_breakdown.json` | Airline breakdown (donut + fare bars) |
| `hub_premium.json` | Airline breakdown (lollipop / beeswarm) |
| `carrier_ontime.json` | Carrier on-time dot plot |

---

## Design Tokens (`frontend/src/styles/global.css`)

```css
--bg:        #0f1117;
--surface:   #1a1d27;
--text:      #e8e8e8;
--muted:     #888;
--iad:       #4e9af1;
--dca:       #f97316;
--bwi:       #22c55e;
--max-width: 740px;
```

Font: avoid Inter — use a less common, more distinctive choice.

---

## Dropped from Original Plan

- **Plotly / iframe embeds** — replaced by native D3
- **Cluster globe (Section 4)** — cut, too much visual overlap with hero
- **HDBSCAN section** — cut, not compelling enough for blog format
- **Sparklines** — cut, stat cards + streamgraph cover the trend story
- **Conclusion section** — may revisit; limitations + TOC serves as natural close
- **Heatmap trio** — replaced by slope chart (more readable, more specific finding)

---

## TOC Anchor IDs

`intro` · `volume` · `explore` · `fares` · `airlines` · `delays` · `anomalous` · `forecast` · `limitations`
