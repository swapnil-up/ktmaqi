"""Analysis queries that turn raw data into insights."""

from datetime import datetime, timezone, timedelta

NPT = timezone(timedelta(hours=5, minutes=45))

from src import aqi as aqi_lib
from src import store


def current_conditions():
    """Latest AQI per station."""
    rows = store.query("""
        SELECT l.id, l.name, l.latitude, l.longitude,
               m.value, m.measured_at, l.source
        FROM locations l
        JOIN measurements m ON l.id = m.location_id
        WHERE m.parameter = 'pm25'
          AND l.is_active = 1
          AND m.id IN (
              SELECT MAX(id) FROM measurements
              WHERE parameter = 'pm25'
              GROUP BY location_id
          )
        ORDER BY m.value DESC
    """)
    out = []
    for r in rows:
        aqi = aqi_lib.pm25_to_aqi(r["value"])
        info = aqi_lib.aqi_info(aqi)
        out.append({
            "id": r["id"],
            "name": r["name"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "pm25": r["value"],
            "aqi": aqi,
            "category": info["label"],
            "color": info["color"],
            "text_color": info["text_color"],
            "measured_at": r["measured_at"],
            "source": r["source"],
        })
    return out


def hourly_avg_24h():
    """24-hour rolling average PM2.5 per station."""
    return store.query("""
        SELECT location_id, AVG(value) as avg_pm25
        FROM measurements
        WHERE parameter = 'pm25'
          AND measured_at >= datetime('now', '-1 day')
        GROUP BY location_id
    """)


def weekly_avg_24h():
    """7-day rolling average PM2.5 per station."""
    return store.query("""
        SELECT location_id, AVG(value) as avg_pm25
        FROM measurements
        WHERE parameter = 'pm25'
          AND measured_at >= datetime('now', '-7 days')
        GROUP BY location_id
    """)


def trends():
    """Compare recent (last 24h) vs week average to determine direction."""
    recent = {r["location_id"]: r["avg_pm25"] for r in hourly_avg_24h()}
    weekly = {r["location_id"]: r["avg_pm25"] for r in weekly_avg_24h()}
    current = current_conditions()

    for s in current:
        sid = s["id"]
        r = recent.get(sid)
        w = weekly.get(sid)
        if r is not None and w is not None and w > 0:
            diff_pct = ((r - w) / w) * 100
            if diff_pct < -10:
                s["trend"] = "improving"
                s["trend_label"] = f"↓ {abs(diff_pct):.0f}% vs week"
            elif diff_pct > 10:
                s["trend"] = "worsening"
                s["trend_label"] = f"↑ {diff_pct:.0f}% vs week"
            else:
                s["trend"] = "stable"
                s["trend_label"] = f"→ {diff_pct:.1f}% vs week"
        else:
            s["trend"] = "unknown"
            last_seen = s.get("measured_at")
            if last_seen:
                try:
                    dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                    s["trend_label"] = f"Offline since {dt.strftime('%b %d')}"
                except Exception:
                    s["trend_label"] = "Station offline"
            else:
                s["trend_label"] = "Station offline"

    return current


def best_exercise_window(forecast):
    """Best 2-hour window for outdoor activity *today* (NPT)."""
    if not forecast or "time" not in forecast:
        return None

    times = forecast["time"]
    pm25_vals = forecast.get("pm2_5", [])
    if not pm25_vals:
        return None

    today_npt = datetime.now(NPT).date()

    # Collect exercise-hour candidates for today only
    candidates = []
    for i, t in enumerate(times):
        if i >= len(pm25_vals) or pm25_vals[i] is None:
            continue
        try:
            dt = datetime.fromisoformat(t)
            local = dt.astimezone(NPT)
        except Exception:
            continue
        if local.date() != today_npt:
            continue
        hour = local.hour
        if 5 <= hour <= 9 or 16 <= hour <= 19:
            aqi = aqi_lib.pm25_to_aqi(pm25_vals[i])
            if aqi is not None:
                candidates.append({"hour": hour, "aqi": aqi})

    if len(candidates) < 2:
        return None

    # Find best consecutive pair within the same block
    blocks = {"morning": range(5, 10), "evening": range(16, 20)}
    best = None
    for block_name, block_hours in blocks.items():
        block = [c for c in candidates if c["hour"] in block_hours]
        for i in range(len(block) - 1):
            if block[i + 1]["hour"] - block[i]["hour"] == 1:
                avg = (block[i]["aqi"] + block[i + 1]["aqi"]) / 2
                if best is None or avg < best["avg_aqi"]:
                    best = {
                        "start": block[i]["hour"],
                        "end": block[i + 1]["hour"],
                        "avg_aqi": round(avg),
                    }
    return best


def station_rank(current):
    """Top 5 worst and best stations."""
    sorted_by_aqi = sorted(current, key=lambda s: s["aqi"] or 0)
    return {
        "worst": sorted_by_aqi[-5:][::-1] if len(sorted_by_aqi) >= 5 else sorted_by_aqi[::-1],
        "best": sorted_by_aqi[:5] if len(sorted_by_aqi) >= 5 else sorted_by_aqi,
    }
