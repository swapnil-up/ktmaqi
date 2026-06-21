"""Fetch air quality data from pollution.gov.np GSS API (government network)."""

import json
import urllib.request
from datetime import datetime, timezone, timedelta

GSS_BASE = "https://pollution.gov.np/gss/api"

PM25_PARAM_NAMES = {"PM2.5 Inst", "PM2.5 avg 1 hr", "PM2.5 avg 10 mins"}
PM10_PARAM_NAMES = {"PM10 Inst", "PM10 avg 1 hr", "PM10 Avg 10 min"}


def _request(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def get_stations():
    """Fetch all stations with their metadata and PM series IDs.

    Returns list of {id, name, identifier, lat, lon, pm25_series_id}.
    """
    raw = _request(f"{GSS_BASE}/station")
    out = []
    for s in raw:
        pm25_id = None
        for ds in s.get("data_source", []):
            for p in ds.get("parameters", []):
                if p.get("parameter_name") == "PM2.5 Inst":
                    pm25_id = p["id"]
        if pm25_id:
            out.append({
                "id": s["id"],
                "name": s["name"],
                "identifier": s.get("identifier", ""),
                "latitude": s.get("latitude"),
                "longitude": s.get("longitude"),
                "pm25_series_id": pm25_id,
            })
    return out


def get_stations_full():
    """Fetch all stations with ALL parameter series IDs.

    Returns list of dict with full metadata.
    """
    raw = _request(f"{GSS_BASE}/station")
    out = []
    for s in raw:
        params = {}
        pm25_series_id = None
        pm10_series_id = None
        for ds in s.get("data_source", []):
            for p in ds.get("parameters", []):
                pname = p.get("parameter_name", "").strip()
                pid = p["id"]
                params[pname] = pid
                if pname in PM25_PARAM_NAMES and pm25_series_id is None:
                    pm25_series_id = pid
                if pname in PM10_PARAM_NAMES and pm10_series_id is None:
                    pm10_series_id = pid

        entry = {
            "id": s["id"],
            "name": s["name"],
            "identifier": s.get("identifier", ""),
            "latitude": s.get("latitude"),
            "longitude": s.get("longitude"),
            "elevation": s.get("elevation"),
            "parameters": params,
            "pm25_series_id": pm25_series_id,
            "pm10_series_id": pm10_series_id,
        }
        out.append(entry)
    return out


def get_observation(series_id, date_from=None, date_to=None):
    """Fetch observations for a given series.

    Returns {parameter_name, series_name, data: [{datetime, value}]}.
    """
    url = f"{GSS_BASE}/observation?series_id={series_id}"
    if date_from:
        url += f"&date_from={date_from}"
    if date_to:
        url += f"&date_to={date_to}"
    return _request(url)


def latest_readings(hours_back=24):
    """Fetch latest PM2.5 readings for all stations.

    Returns {station_name: {pm25, measured_at, source}}.
    """
    stations = get_stations()
    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%SZ")

    results = {}
    for st in stations:
        try:
            obs = get_observation(st["pm25_series_id"], date_from=date_from)
        except Exception as e:
            print(f"  SKIP {st['name']}: observation error {e}")
            continue
        data = obs.get("data", [])
        if not data:
            results[st["name"]] = {
                "pm25": None,
                "measured_at": None,
                "source": "gss",
                "gss_id": st["id"],
                "latitude": st["latitude"],
                "longitude": st["longitude"],
            }
            continue

        latest = data[-1]
        try:
            dt = datetime.fromisoformat(latest["datetime"].replace("Z", "+00:00"))
        except Exception:
            dt = None
        results[st["name"]] = {
            "pm25": latest["value"],
            "measured_at": dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None,
            "source": "gss",
            "gss_id": st["id"],
            "latitude": st["latitude"],
            "longitude": st["longitude"],
            "series_id": st["pm25_series_id"],
        }
    return results


def get_all_latest():
    """Fetch single latest PM2.5 for all GSS stations (efficient)."""
    stations = get_stations()
    results = []
    for st in stations:
        try:
            obs = get_observation(st["pm25_series_id"], date_to=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        except Exception as e:
            print(f"  WARN: {st['name']}: {e}")
            continue
        data = obs.get("data", [])
        if not data:
            continue
        latest = data[-1]
        results.append({
            "name": st["name"],
            "gss_id": st["id"],
            "latitude": st["latitude"],
            "longitude": st["longitude"],
            "pm25": latest["value"],
            "measured_at": latest["datetime"],
        })
    return results
