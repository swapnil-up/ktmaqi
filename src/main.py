"""Orchestrate the full AQI pipeline."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src import fetch, store, analyze, render


def main():
    api_key = os.environ.get("OPENAQ_API_KEY", "")
    if not api_key:
        print("WARNING: OPENAQ_API_KEY not set — stations will be empty")

    store.init_db()

    locations = []
    if api_key:
        try:
            locations = fetch.get_locations(api_key)
            print(f"Found {len(locations)} locations in Nepal")
        except Exception as e:
            print(f"ERROR fetching locations: {e}")

    if locations:
        store.upsert_locations(locations)
        store.mark_inactive({l["id"] for l in locations})
        loc_ids = [l["id"] for l in locations]

        cached = store.load_sensor_map()
        sensor_map, measurements = fetch.fetch_all(api_key, loc_ids, cached)
        print(f"Got {len(measurements)} PM2.5 readings")

        # Persist new sensor mappings
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

    forecast = {}
    try:
        forecast = fetch.get_forecast()
        print(f"Got forecast: {len(forecast.get('time', []))} hours")
    except Exception as e:
        print(f"ERROR fetching forecast: {e}")

    stations = analyze.trends()
    print(f"Analyzed {len(stations)} stations")

    exercise_window = analyze.best_exercise_window(forecast)
    if exercise_window:
        print(f"Best exercise today: {exercise_window['start']}:00-{exercise_window['end']}:00")

    render.render(forecast, stations, exercise_window)
    print("Done")


if __name__ == "__main__":
    main()
