# KTM Data Products

Two static-site data products for Kathmandu.

## 1. AQI + Activity Intelligence (ktmaqi)

**Purpose:** Help people make decisions about outdoor activity based on air quality.

**Data sources:**
- OpenAQ API v3 (real-time station readings, free API key)
- Open-Meteo CAMS (forecasted AQI, no key needed)

**Pipeline (GitHub Actions, every hour):**
1. Fetch latest readings from OpenAQ for Nepal stations
2. Fetch forecast from Open-Meteo
3. Store in SQLite (appends hourly snapshots)
4. Run analysis queries
5. Render static HTML pages
6. Deploy to GitHub Pages

**Analysis outputs:**
- Current AQI per station (color-coded)
- 24h trend per station
- Safest exercise window today
- 7-day trend (which stations improving/worsening)
- School-hour exposure estimates

**Tech choices:**
- Python stdlib only (urllib, sqlite3) — zero external deps
- No framework, no build step
- Static HTML/CSS, vanilla
- SQLite for storage (append-only, no migrations needed)

---

## 2. Food Price Intelligence

**Purpose:** Track commodity prices across Kathmandu markets.

**Data sources:**
- AMPIS (ampis.gov.np, 11 markets, daily wholesale)
- Kalimati (kalimatimarket.gov.np, 170 commodities, daily)
- NOC (noc.org.np, fuel/LPG prices)

**Pipeline (GitHub Actions, daily):**
1. Scrape HTML pages (BeautifulSoup)
2. Parse and normalize prices
3. Store in SQLite
4. Run analysis queries
5. Render static HTML pages
6. Deploy to GitHub Pages

**Analysis outputs:**
- Cheapest market per commodity today
- 7d/30d price trends
- Volatility ranking
- Cross-market savings

**Tech choices:**
- Python + BeautifulSoup for scraping (necessity — HTML sources)
- Otherwise same stack as AQI
- Scraping is low-risk: gov sites redesign rarely

---

## Resilience principles (both)

- No servers, no hosted databases
- GitHub Actions with pinned Python version
- Static site on GitHub Pages
- Append-only SQLite (no schema changes needed)
- All dependencies pinned with hash
- Graceful degradation if a source is down
- Plain HTML/CSS, no JS framework
