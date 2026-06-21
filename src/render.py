"""Render static HTML site with Leaflet map."""

import json
import os
from datetime import datetime, timezone, timedelta
from src import aqi as aqi_lib

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
NPT = timezone(timedelta(hours=5, minutes=45))


def _fmt_npt(iso_str):
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.astimezone(NPT).strftime("%b %d, %I:%M %p")
    except Exception:
        return iso_str


def _now_npt():
    return datetime.now(NPT).strftime("%b %d, %I:%M %p")


def _aqi_color(aqi):
    if aqi is None:
        return "#ccc"
    if aqi <= 50:
        return "#00E400"
    if aqi <= 100:
        return "#FFFF00"
    if aqi <= 150:
        return "#FF7E00"
    if aqi <= 200:
        return "#FF0000"
    if aqi <= 300:
        return "#8F3F97"
    return "#7E0023"


def _hour_label(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.astimezone(NPT).strftime("%-I%p").lower()
    except Exception:
        return "—"


def render_forecast(forecast):
    times = forecast.get("time", [])
    vals = forecast.get("pm2_5", [])
    if not times or not vals:
        return ""
    now_npt = datetime.now(NPT)
    current_hour = now_npt.hour
    items = []
    for i, t in enumerate(times):
        if i >= 12:
            break
        if "T" not in t:
            continue
        try:
            dt = datetime.fromisoformat(t)
            local = dt.astimezone(NPT)
        except Exception:
            continue
        pm25 = vals[i] if i < len(vals) else None
        if pm25 is None:
            continue
        aqi = aqi_lib.pm25_to_aqi(pm25)
        if aqi is None:
            continue
        color = _aqi_color(aqi)
        height = max(4, min(80, aqi * 0.4))
        items.append(
            f'<div class="forecast-hour">'
            f'<div class="bar" style="height:{height:.0f}px;background:{color}"></div>'
            f'<div class="label" style="font-weight:{600 if local.hour == current_hour else 400}">{_hour_label(t)}</div>'
            f'<div class="label">{aqi}</div></div>'
        )
    if not items:
        return ""
    return f'<div class="forecast-strip">{"".join(items)}</div>'


def render_map(stations):
    """Generate the Leaflet map section with embedded station data."""
    if not stations:
        return ""
    features = []
    for s in stations:
        if s.get("latitude") and s.get("longitude"):
            src = s.get("source", "openaq")
            source_badge = ""
            if "gss" in src:
                source_badge = '<span style="font-size:0.65rem;background:#e8f5e9;color:#2e7d32;padding:1px 5px;border-radius:3px;margin-left:4px;">Govt</span>'
            features.append({
                "lat": s["latitude"],
                "lon": s["longitude"],
                "name": s["name"],
                "aqi": s["aqi"],
                "pm25": round(s["pm25"], 1) if s["pm25"] is not None else None,
                "color": s["color"],
                "text_color": s["text_color"],
                "category": s["category"],
                "trend": s["trend_label"],
                "time": _fmt_npt(s["measured_at"]),
                "source": s.get("source", "openaq"),
                "source_badge": source_badge,
            })
    data_json = json.dumps(features)

    return f"""
<div id="map"></div>
<div id="map-legend">
    <div><span style="background:#00E400"></span>Good (0-50)</div>
    <div><span style="background:#FFFF00"></span>Moderate (51-100)</div>
    <div><span style="background:#FF7E00"></span>Unhealthy (Sensitive)</div>
    <div><span style="background:#FF0000"></span>Unhealthy</div>
    <div><span style="background:#8F3F97"></span>Very Unhealthy</div>
    <div><span style="background:#7E0023"></span>Hazardous</div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
var stations = {data_json};
var map = L.map('map', {{ zoomControl: true, scrollWheelZoom: true }}).setView([27.7, 85.3], 10);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
    maxZoom: 19,
    subdomains: 'abcd',
    attribution: '&copy; <a href="https://carto.com/attributions">CARTO</a>'
}}).addTo(map);
var bounds = [];
stations.forEach(function(s) {{
    var radius = Math.max(8, Math.min(30, (s.aqi || 50) / 10));
    var marker = L.circleMarker([s.lat, s.lon], {{
        radius: radius,
        fillColor: s.color,
        color: '#333',
        weight: 1,
        opacity: 0.8,
        fillOpacity: 0.85
    }}).addTo(map);
    marker.bindPopup(
        '<strong>' + s.name + '</strong>' + s.source_badge + '<br>' +
        'AQI: <strong>' + (s.aqi ?? '--') + '</strong> (' + s.category + ')<br>' +
        'PM2.5: ' + (s.pm25 ?? '--') + ' µg/m³<br>' +
        'Trend: ' + s.trend + '<br>' +
        '<small>' + s.time + '</small>'
    );
    bounds.push([s.lat, s.lon]);
}});
if (bounds.length) map.fitBounds(bounds, {{ padding: [20, 20] }});
</script>"""


PAGE_TOP = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KTM AQI — Kathmandu Air Quality Intelligence</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #f5f5f5; color: #1a1a1a; line-height: 1.5; }
.container { max-width: 960px; margin: 0 auto; padding: 16px; }

header { background: #1a1a2e; color: white; padding: 24px 0; }
header h1 { font-size: 1.6rem; font-weight: 700; }
header p { font-size: 0.9rem; opacity: 0.7; }
header .updated { font-size: 0.75rem; opacity: 0.5; margin-top: 4px; }

.exercise-box {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white; border-radius: 12px; padding: 20px; margin: 20px 0 16px;
    text-align: center;
}
.exercise-box h2 { font-size: 1rem; opacity: 0.85; margin-bottom: 4px; }
.exercise-box .window { font-size: 1.5rem; font-weight: 700; }

.forecast-strip { display: flex; gap: 4px; overflow-x: auto; padding: 12px 0; margin-bottom: 16px; }
.forecast-hour { flex: 0 0 auto; width: 56px; text-align: center; }
.forecast-hour .bar { width: 100%; border-radius: 4px 4px 0 0; min-height: 4px; margin-bottom: 4px; }
.forecast-hour .label { font-size: 0.65rem; color: #666; }

.insights { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 16px 0; }
.insight-card { background: white; border-radius: 10px; padding: 14px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.insight-card h3 { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em;
                   color: #666; margin-bottom: 4px; }
.insight-card .value { font-size: 1.3rem; font-weight: 700; }

#map { height: 420px; border-radius: 10px; margin: 16px 0; z-index: 1; }
#map-legend {
    background: white; padding: 8px 12px; border-radius: 6px;
    font-size: 0.75rem; margin: -6px 0 16px; display: flex; gap: 12px; flex-wrap: wrap;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
#map-legend span { display: inline-block; width: 12px; height: 12px; border-radius: 50%;
                   margin-right: 3px; vertical-align: middle; }

.station-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
                gap: 10px; margin: 12px 0; }
.station-card { border-radius: 10px; padding: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.station-card .name { font-weight: 600; font-size: 0.85rem; margin-bottom: 2px; }
.station-card .aqi { font-size: 1.5rem; font-weight: 700; }
.station-card .pm25 { font-size: 0.75rem; opacity: 0.8; }
.station-card .trend { font-size: 0.75rem; margin-top: 2px; }
.station-card .time { font-size: 0.65rem; opacity: 0.6; margin-top: 2px; }

.empty-state { text-align: center; padding: 32px 16px; background: white; border-radius: 10px;
               color: #999; }

footer { text-align: center; padding: 32px 0 16px; font-size: 0.75rem; color: #999; }

@media (max-width: 600px) {
    .insights { grid-template-columns: 1fr; }
    .station-grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>

<header>
<div class="container">
<h1>KTM AQI</h1>
<p>Kathmandu Air Quality Intelligence</p>
<div class="updated">Updated {{UPDATED}}</div>
</div>
</header>

<main class="container">

{{EXERCISE}}

{{FORECAST}}

{{INSIGHTS}}

<h2 style="margin-top:8px;font-size:1rem;">Map</h2>
{{MAP}}

<h2 style="margin-top:16px;font-size:1rem;">Station Readings</h2>

<div class="station-grid">
{{STATIONS}}
</div>

<footer>
Data from OpenAQ + Nepal Government AQMS (measured) &middot; Open-Meteo CAMS (forecast) &middot;
Updates hourly &middot; AQI via US EPA standard
</footer>

</main>
</body>
</html>"""


def render(forecast, stations=None, exercise_window=None):
    if stations is None:
        stations = []

    has_data = bool(stations)

    # Exercise window
    if exercise_window:
        exercise = (
            '<div class="exercise-box">'
            f'<h2>Best time for outdoor activity today</h2>'
            f'<div class="window">{exercise_window["start"]:02d}:00 – {exercise_window["end"]:02d}:00</div>'
            f'<div style="font-size:0.9rem;opacity:0.85;margin-top:4px;">'
            f'Avg AQI: {exercise_window["avg_aqi"]} ({aqi_lib.aqi_info(exercise_window["avg_aqi"])["label"]})'
            f'</div></div>'
        )
    else:
        if stations and max((s["aqi"] for s in stations if s["aqi"]), default=0) > 150:
            exercise = (
                '<div class="exercise-box" style="background:linear-gradient(135deg,#e74c3c,#c0392b);">'
                '<h2>Outdoor activity not recommended today</h2>'
                '<div style="font-size:1rem;opacity:0.9;">AQI levels are high across the valley</div></div>'
            )
        else:
            exercise = ""

    forecast_html = render_forecast(forecast)

    # Insights
    if has_data:
        sorted_s = sorted(stations, key=lambda x: x["aqi"] if x["aqi"] is not None else 999)
        worst = sorted_s[-1] if sorted_s else None
        best = sorted_s[0] if sorted_s else None
        insights = (
            '<div class="insights">'
            f'<div class="insight-card"><h3>Worst now</h3>'
            f'<div class="value">{worst["name"] if worst else "—"}</div>'
            f'<div style="font-size:0.8rem;color:#666;">AQI {worst["aqi"] if worst is not None else "—"}</div></div>'
            f'<div class="insight-card"><h3>Best now</h3>'
            f'<div class="value">{best["name"] if best else "—"}</div>'
            f'<div style="font-size:0.8rem;color:#666;">AQI {best["aqi"] if best is not None else "—"}</div></div>'
            '</div>'
        )
    elif forecast:
        forecast_aqis = [a for v in forecast.get("pm2_5", [])
                         if v is not None and (a := aqi_lib.pm25_to_aqi(v)) is not None]
        avg = round(sum(forecast_aqis) / len(forecast_aqis)) if forecast_aqis else None
        insights = (
            '<div class="insights">'
            f'<div class="insight-card"><h3>Today\'s Avg Forecast</h3>'
            f'<div class="value">{avg if avg else "—"}</div>'
            f'<div style="font-size:0.8rem;color:#666;">{aqi_lib.aqi_info(avg)["label"] if avg else "No data"}</div></div>'
            '<div class="insight-card"><h3>Stations offline</h3>'
            '<div class="value" style="font-size:1rem;">waiting for data</div>'
            '<div style="font-size:0.8rem;color:#666;">Forecast shown instead</div></div>'
            '</div>'
        )
    else:
        insights = ""

    # Station cards
    if has_data:
        cards = ""
        for s in stations:
            aqi_val = s["aqi"] if s["aqi"] is not None else "—"
            pm25_str = f"{s['pm25']:.1f}" if s["pm25"] is not None and s["pm25"] >= 0 else "—"
            src = s.get("source", "openaq")
            source_tag = '<span style="font-size:0.6rem;opacity:0.7;background:rgba(255,255,255,0.2);padding:1px 4px;border-radius:3px;">GOVT</span>' if "gss" in src else ""
            cards += (
                f'<div class="station-card" style="background:{s["color"]};color:{s["text_color"]}">'
                f'<div class="name">{s["name"]} {source_tag}</div>'
                f'<div class="aqi">{aqi_val}</div>'
                f'<div class="pm25">PM2.5 {pm25_str} &middot; {s["category"]}</div>'
                f'<div class="trend">{s["trend_label"]}</div>'
                f'<div class="time">{_fmt_npt(s["measured_at"])}</div></div>'
            )
        stations_html = cards
    else:
        stations_html = (
            '<div class="empty-state">'
            '<p><strong>No station data yet.</strong></p>'
            '<p style="margin-top:4px;">Real-time readings will appear once the pipeline connects to OpenAQ.</p>'
            '</div>'
        )

    map_html = render_map(stations)

    html = PAGE_TOP
    for key, val in [
        ("UPDATED", _now_npt()),
        ("EXERCISE", exercise),
        ("FORECAST", forecast_html),
        ("INSIGHTS", insights),
        ("MAP", map_html),
        ("STATIONS", stations_html),
    ]:
        html = html.replace("{{" + key + "}}", val)

    os.makedirs(PUBLIC_DIR, exist_ok=True)
    with open(os.path.join(PUBLIC_DIR, "index.html"), "w") as f:
        f.write(html)
    print(f"Rendered {os.path.join(PUBLIC_DIR, 'index.html')}")
