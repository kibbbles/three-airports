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

## Current Section Order

| # | Section | Component | Status |
|---|---|---|---|
| 0 | Hero globe | `GlobeHero.astro` | ✅ shipped |
| — | Table of contents | inline in `index.astro` | ✅ shipped |
| 1 | Overview + stat cards | inline in `index.astro` | ✅ shipped |
| 2 | Volume over time | `FlightVolumeStreamgraph.astro` | ✅ shipped |
| 3 | Explore 2.7M flights | `CrossfilterDash.astro` | ✅ shipped |
| 4 | Fare comparison | `FareComparison.astro` | ✅ shipped |
| 4b | **Airline breakdown** | `AirlineBreakdown.astro` | 🔲 next |
| 5 | When delays happen | `SlopeChart.astro` | ✅ shipped |
| 6 | Misbehaving routes | `AnomalyList.astro` | ✅ shipped |
| 7 | Forecasts | `ForecastChart.astro` | ✅ shipped |
| 8 | Limitations | inline in `index.astro` | ✅ shipped |

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

### `AnomalyList.astro`
- Ranked list of 87 persistently anomalous routes (Isolation Forest, post-2022)
- Bar shows years flagged out of 5
- Data: `anomalies.json`

### `ForecastChart.astro`
- Prophet forecast vs actuals per airport, shaded 95% CI
- Data: `forecasts.json`

---

## Next: Airline Breakdown Section (4b)

**Narrative framing:** A separate section right after fare comparison. Opens with a
transition paragraph ("now that we know *what* the fares look like, here's *who's*
flying out of each airport and what they charge"). Presents correlation between carrier
mix and fare levels without claiming causation — United dominating IAD at 69%,
Southwest owning BWI at 61%, American leading DCA at 44% is interesting context,
not a proof.

**Charts:**
1. **Three pie/donut charts** — carrier market share by passenger volume per airport
   (top 6 carriers + Other). Colored by carrier, not airport.
2. **Grouped horizontal bar** — median fare per carrier, grouped by airport.
   Shows e.g. United at IAD vs Southwest at BWI on the same axis.
   Based on notebook `04_eda_db1b.ipynb` Section 7.

**Data export needed:** `carrier_breakdown.json`
- Script: `scripts/run_carrier_breakdown.py`
- Source: `data/processed/db1b_dmv.parquet`
- Schema:
  ```json
  {
    "carrier_names": { "WN": "Southwest", "UA": "United", ... },
    "carrier_colors": { "WN": "#ffb81c", "UA": "#002244", ... },
    "share": {
      "IAD": [{ "carrier": "UA", "pax": 2720553, "pct": 0.689 }, ...],
      "DCA": [...],
      "BWI": [...]
    },
    "fares": {
      "IAD": [{ "carrier": "UA", "name": "United", "median_fare": 265 }, ...],
      "DCA": [...],
      "BWI": [...]
    }
  }
  ```

**Component:** `AirlineBreakdown.astro`
- Client-side D3, same ResizeObserver pattern as other components
- Pie charts: `d3.pie` + `d3.arc`, one SVG per airport, 2×3 grid or row of 3
- Bar chart: horizontal bars grouped by airport, sorted by fare descending

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
| `carrier_breakdown.json` | **Airline breakdown** (to build) |

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

`intro` · `volume` · `explore` · `fares` · `airlines` *(to add)* · `delays` · `anomalous` · `forecast` · `limitations`
