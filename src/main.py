"""Orchestrate the full AQI pipeline."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src import fetch, store, analyze, render
from src.enrich import enrich


def main():
    api_key = os.environ.get("OPENAQ_API_KEY", "")
    if not api_key:
        print("WARNING: OPENAQ_API_KEY not set — stations will be empty")

    store.init_db()

    openaq_ids = set()

    # Step 1: Fetch and persist OpenAQ locations
    if api_key:
        try:
            locations = fetch.get_locations(api_key)
            print(f"Found {len(locations)} locations in Nepal")
        except Exception as e:
            print(f"ERROR fetching locations: {e}")
            locations = []

        if locations:
            store.upsert_locations(locations)
            openaq_ids = {l["id"] for l in locations}

    # Step 2: Enrich with GSS government station metadata
    gss_ids = set()
    try:
        matched, new_count = enrich()
    except Exception as e:
        print(f"ERROR during GSS enrichment: {e}")
    gss_rows = store.query("SELECT id FROM locations WHERE source='gss'")
    gss_ids = {r["id"] for r in gss_rows}

    # Step 3: Mark inactive — keep OpenAQ + GSS-only stations active
    all_active = openaq_ids | gss_ids
    if all_active:
        store.mark_inactive(all_active)

    # Step 4: Fetch sensors and PM2.5 readings for OpenAQ locations
    if openaq_ids:
        loc_ids = list(openaq_ids)
        cached = store.load_sensor_map()
        sensor_map, measurements = fetch.fetch_all(api_key, loc_ids, cached)
        print(f"Got {len(measurements)} PM2.5 readings")

        new_sensors = {
            lid: m for lid, m in sensor_map.items()
            if lid not in cached
        }
        if new_sensors:
            store.upsert_sensors(new_sensors)
            print(f"Cached sensors for {len(new_sensors)} new locations")

        for loc_id, m in measurements.items():
            store.insert_measurement(
                loc_id, "pm25", m["value"], m["unit"], m["measured_at"]
            )

    # Step 5: Forecast
    forecast = {}
    try:
        forecast = fetch.get_forecast()
        print(f"Got forecast: {len(forecast.get('time', []))} hours")
    except Exception as e:
        print(f"ERROR fetching forecast: {e}")

    # Step 6: Analyze and render
    stations = analyze.trends()
    print(f"Analyzed {len(stations)} stations")

    exercise_window = analyze.best_exercise_window(forecast)
    if exercise_window:
        print(f"Best exercise today: {exercise_window['start']}:00-{exercise_window['end']}:00")

    render.render(forecast, stations, exercise_window)
    print("Done")


if __name__ == "__main__":
    main()
