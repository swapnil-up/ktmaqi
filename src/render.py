"""Render static HTML site."""

import os
from datetime import datetime, timezone, timedelta
from src import aqi as aqi_lib

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")

NPT = timezone(timedelta(hours=5, minutes=45))

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KTM AQI — Kathmandu Air Quality Intelligence</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #f5f5f5; color: #1a1a1a; line-height: 1.5; }}
.container {{ max-width: 960px; margin: 0 auto; padding: 16px; }}

header {{ background: #1a1a2e; color: white; padding: 24px 0; }}
header h1 {{ font-size: 1.6rem; font-weight: 700; }}
header p {{ font-size: 0.9rem; opacity: 0.7; }}
header .updated {{ font-size: 0.75rem; opacity: 0.5; margin-top: 4px; }}

.exercise-box {{
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white; border-radius: 12px; padding: 20px; margin: 20px 0 16px;
    text-align: center;
}}
.exercise-box h2 {{ font-size: 1rem; opacity: 0.85; margin-bottom: 4px; }}
.exercise-box .window {{ font-size: 1.5rem; font-weight: 700; }}

.forecast-strip {{ display: flex; gap: 4px; overflow-x: auto; padding: 12px 0; margin-bottom: 16px; }}
.forecast-hour {{ flex: 0 0 auto; width: 56px; text-align: center; }}
.forecast-hour .bar {{ width: 100%; border-radius: 4px 4px 0 0; min-height: 4px; margin-bottom: 4px; transition: height 0.2s; }}
.forecast-hour .label {{ font-size: 0.65rem; color: #666; }}

.station-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
                 gap: 12px; margin: 12px 0; }}
.station-card {{ border-radius: 10px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.station-card .name {{ font-weight: 600; font-size: 0.95rem; margin-bottom: 2px; }}
.station-card .aqi {{ font-size: 2rem; font-weight: 700; }}
.station-card .pm25 {{ font-size: 0.8rem; opacity: 0.8; }}
.station-card .trend {{ font-size: 0.8rem; margin-top: 4px; }}
.station-card .time {{ font-size: 0.7rem; opacity: 0.6; margin-top: 4px; }}

.empty-state {{ text-align: center; padding: 32px 16px; background: white; border-radius: 10px;
                color: #999; }}

.insights {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 16px 0; }}
.insight-card {{ background: white; border-radius: 10px; padding: 14px;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
.insight-card h3 {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em;
                   color: #666; margin-bottom: 4px; }}
.insight-card .value {{ font-size: 1.3rem; font-weight: 700; }}

footer {{ text-align: center; padding: 32px 0 16px; font-size: 0.75rem; color: #999; }}

@media (max-width: 600px) {{
    .insights {{ grid-template-columns: 1fr; }}
    .station-grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>

<header>
<div class="container">
<h1>KTM AQI</h1>
<p>Kathmandu Air Quality Intelligence</p>
<div class="updated">Updated {updated}</div>
</div>
</header>

<main class="container">

{exercise_html}

{forecast_html}

{insights_html}

<h2 style="margin-top:8px;font-size:1rem;">Station Readings</h2>

<div class="station-grid">
{stations_html}
</div>

<footer>
Data from OpenAQ (measured) + Open-Meteo CAMS (forecast) ·
Updates hourly · AQI via US EPA standard
</footer>

</main>
</body>
</html>"""


def _fmt_npt(iso_str):
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        local = dt.astimezone(NPT)
        return local.strftime("%b %d, %I:%M %p")
    except Exception:
        return iso_str


def _now_npt():
    return datetime.now(NPT).strftime("%b %d, %I:%M %p")


def _hour_label(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.astimezone(NPT).strftime("%-I%p").lower()
    except Exception:
        return "—"


def _aqi_color(aqi):
    if aqi is None:
        return "#ccc"
    if aqi <= 50: return "#00E400"
    if aqi <= 100: return "#FFFF00"
    if aqi <= 150: return "#FF7E00"
    if aqi <= 200: return "#FF0000"
    if aqi <= 300: return "#8F3F97"
    return "#7E0023"


def render_forecast(forecast):
    """Render hourly forecast strip for next 12h."""
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
        label = _hour_label(t)

        height = max(4, min(80, aqi * 0.4))
        items.append(
            f'<div class="forecast-hour">'
            f'<div class="bar" style="height:{height:.0f}px;background:{color}"></div>'
            f'<div class="label" style="font-weight:{600 if local.hour == current_hour else 400}">{label}</div>'
            f'<div class="label">{aqi}</div>'
            f'</div>'
        )

    if not items:
        return ""

    return f'<div class="forecast-strip">{"".join(items)}</div>'


def render(forecast, stations=None, exercise_window=None):
    if stations is None:
        stations = []

    has_data = bool(stations)

    # Exercise window
    if exercise_window:
        exercise_html = f"""
<div class="exercise-box">
    <h2>Best time for outdoor activity today</h2>
    <div class="window">{exercise_window['start']:02d}:00 – {exercise_window['end']:02d}:00</div>
    <div style="font-size:0.9rem;opacity:0.85;margin-top:4px;">
        Avg AQI: {exercise_window['avg_aqi']} ({aqi_lib.aqi_info(exercise_window['avg_aqi'])['label']})
    </div>
</div>"""
    else:
        if stations and max((s["aqi"] for s in stations if s["aqi"]), default=0) > 150:
            exercise_html = """
<div class="exercise-box" style="background:linear-gradient(135deg,#e74c3c,#c0392b);">
    <h2>Outdoor activity not recommended today</h2>
    <div style="font-size:1rem;opacity:0.9;">AQI levels are high across the valley</div>
</div>"""
        else:
            exercise_html = ""

    forecast_html = render_forecast(forecast)

    # Insights
    if has_data:
        sorted_s = sorted(stations, key=lambda x: x["aqi"] if x["aqi"] is not None else 999)
        worst = sorted_s[-1] if sorted_s else None
        best = sorted_s[0] if sorted_s else None
        insights_html = f"""
<div class="insights">
    <div class="insight-card">
        <h3>Worst now</h3>
        <div class="value">{worst['name'] if worst else '—'}</div>
        <div style="font-size:0.8rem;color:#666;">AQI {worst['aqi'] if worst is not None else '—'}</div>
    </div>
    <div class="insight-card">
        <h3>Best now</h3>
        <div class="value">{best['name'] if best else '—'}</div>
        <div style="font-size:0.8rem;color:#666;">AQI {best['aqi'] if best is not None else '—'}</div>
    </div>
</div>"""
    elif forecast:
        forecast_aqis = []
        for v in forecast.get("pm2_5", []):
            if v is not None:
                a = aqi_lib.pm25_to_aqi(v)
                if a:
                    forecast_aqis.append(a)
        avg = round(sum(forecast_aqis) / len(forecast_aqis)) if forecast_aqis else None
        insights_html = f"""
<div class="insights">
    <div class="insight-card">
        <h3>Today's Avg Forecast</h3>
        <div class="value">{avg if avg else '—'}</div>
        <div style="font-size:0.8rem;color:#666;">{aqi_lib.aqi_info(avg)['label'] if avg else 'No data'}</div>
    </div>
    <div class="insight-card">
        <h3>Stations offline</h3>
        <div class="value" style="font-size:1rem;">waiting for data</div>
        <div style="font-size:0.8rem;color:#666;">Forecast shown instead</div>
    </div>
</div>"""
    else:
        insights_html = ""

    # Station cards
    if has_data:
        cards = ""
        for s in stations:
            aqi_val = s["aqi"] if s["aqi"] is not None else "—"
            pm25_str = f"{s['pm25']:.1f}" if s["pm25"] is not None and s["pm25"] >= 0 else "—"
            cards += f"""
<div class="station-card" style="background:{s['color']};color:{s['text_color']}">
    <div class="name">{s['name']}</div>
    <div class="aqi">{aqi_val}</div>
    <div class="pm25">PM2.5 {pm25_str} · {s['category']}</div>
    <div class="trend">{s['trend_label']}</div>
    <div class="time">{_fmt_npt(s['measured_at'])}</div>
</div>"""
        stations_html = cards
    else:
        stations_html = """
<div class="empty-state">
    <p><strong>No station data yet.</strong></p>
    <p style="margin-top:4px;">Real-time readings will appear once the pipeline connects to OpenAQ.</p>
</div>"""

    updated = _now_npt()

    html = HTML_TEMPLATE.format(
        updated=updated,
        exercise_html=exercise_html,
        forecast_html=forecast_html,
        insights_html=insights_html,
        stations_html=stations_html,
    )

    os.makedirs(PUBLIC_DIR, exist_ok=True)
    with open(os.path.join(PUBLIC_DIR, "index.html"), "w") as f:
        f.write(html)
    print(f"Rendered {os.path.join(PUBLIC_DIR, 'index.html')}")
