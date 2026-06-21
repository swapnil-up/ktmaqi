"""Fetch air quality data from OpenAQ and Open-Meteo (v3 API)."""

import json
import time
import urllib.request
import urllib.error

OPENAQ_BASE = "https://api.openaq.org/v3"
OPEN_METEO_AQ = "https://air-quality-api.open-meteo.com/v1/air-quality"

KATHMANDU_LAT = 27.7172
KATHMANDU_LON = 85.3240

PARAM_PM25 = 2  # OpenAQ v3 parameter id for pm25


def _request(url, api_key=None):
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def get_locations(api_key):
    """Fetch all monitoring locations in Nepal.

    Returns list of {id, name, latitude, longitude}.
    """
    countries = _request(f"{OPENAQ_BASE}/countries?limit=200", api_key)
    np_id = None
    for c in countries.get("results", []):
        if c.get("code") == "NP":
            np_id = c["id"]
            break
    if np_id is None:
        raise ValueError("Country NP not found in OpenAQ")

    raw = _request(
        f"{OPENAQ_BASE}/locations?countries_id={np_id}&limit=200",
        api_key,
    )
    results = []
    for loc in raw.get("results", []):
        coords = loc.get("coordinates", {})
        results.append({
            "id": loc["id"],
            "name": loc.get("name", f"Station {loc['id']}"),
            "latitude": coords.get("latitude"),
            "longitude": coords.get("longitude"),
        })
    return results


def _get_sensors_for_location(api_key, location_id):
    """Fetch sensors for ONE location. Returns {sensor_id: parameter_name}."""
    data = _request(
        f"{OPENAQ_BASE}/locations/{location_id}/sensors", api_key
    )
    mapping = {}
    for s in data.get("results", []):
        p = s.get("parameter", {})
        mapping[s["id"]] = p.get("name")  # e.g. "pm25", "pm10"
    return mapping


import time

def fetch_all(api_key, location_ids, cached_sensors=None):
    """Fetch sensors (if uncached) + latest PM2.5 for all locations in one pass.

    Returns (sensor_map, readings):
      sensor_map: {location_id: {sensor_id: parameter_name}}
      readings:   {location_id: {value, unit, measured_at}}
    """
    if cached_sensors is None:
        cached_sensors = {}
    sensor_map = dict(cached_sensors)
    readings = {}

    for lid in location_ids:
        # Fetch sensors for this location if not cached
        if lid not in sensor_map:
            try:
                sensor_map[lid] = _get_sensors_for_location(api_key, lid)
            except urllib.error.HTTPError as e:
                print(f"  WARN: sensors for {lid}: HTTP {e.code}")
                time.sleep(1)
                continue
            except Exception as e:
                print(f"  WARN: sensors for {lid}: {e}")
                time.sleep(1)
                continue

        time.sleep(0.5)

        # Fetch latest readings
        try:
            data = _request(
                f"{OPENAQ_BASE}/locations/{lid}/latest", api_key
            )
        except urllib.error.HTTPError as e:
            print(f"  WARN: latest for {lid}: HTTP {e.code}")
            time.sleep(1)
            continue
        except Exception as e:
            print(f"  WARN: latest for {lid}: {e}")
            time.sleep(1)
            continue

        # Find PM2.5 reading
        pm25_sensors = {
            sid for sid, pname in sensor_map.get(lid, {}).items()
            if pname == "pm25"
        }
        if not pm25_sensors:
            time.sleep(0.5)
            continue

        for r in data.get("results", []):
            if r["sensorsId"] not in pm25_sensors:
                continue
            val = r["value"]
            if val is None or val < 1.0:  # skip sentinel and noise
                continue
            readings[lid] = {
                "value": val,
                "unit": "µg/m³",
                "measured_at": r["datetime"]["utc"],
            }
            break

        time.sleep(0.5)

    return sensor_map, readings


def get_forecast(lat=KATHMANDU_LAT, lon=KATHMANDU_LON, hours=72):
    """Fetch hourly AQI forecast from Open-Meteo CAMS.

    Returns dict with 'time', 'pm2_5', 'pm10', 'european_aqi'.
    """
    url = (
        f"{OPEN_METEO_AQ}?latitude={lat}&longitude={lon}"
        f"&hourly=pm2_5,pm10,european_aqi"
        f"&timezone=auto&forecast_hours={hours}"
    )
    data = _request(url)
    return data.get("hourly", {})
