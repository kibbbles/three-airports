# Three DMV Airports

A personal data story about IAD, DCA, and BWI — the three airports serving the Washington DC metro area. Built from 10 years of BTS flight records, NOAA weather data, and fare data, exploring delay patterns, route clusters, anomalies, and forecasts through the lens of someone who grew up flying out of the DMV.

**Live site:** https://kibbbles.github.io/three-airports

## Data Sources

- BTS On-Time Performance (2015–2026)
- BTS T-100 Domestic & International Segment
- BTS DB1B Fare Survey
- NOAA Hourly Weather (IAD, DCA, BWI)

## Repo Structure

```
notebooks/   — data exploration, modeling, and export notebooks
src/         — ingestion and processing scripts
data/        — raw downloads and processed parquets (gitignored except exports/)
frontend/    — Astro static site (deploys to GitHub Pages)
knowledge/   — planning docs
```
