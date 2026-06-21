"""One-time backfill: fetch 30 days of historical hourly PM2.5 data."""

import os
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src import fetch, store

BACKFILL_DAYS = 30
DELAY = 0.5  # seconds between API calls


def backfill():
    api_key = os.environ.get("OPENAQ_API_KEY", "")
    if not api_key:
        print("ERROR: OPENAQ_API_KEY not set")
        return

    store.init_db()
    sensor_map = store.load_sensor_map()
    if not sensor_map:
        print("No sensor map found. Run main.py first to discover sensors.")
        return

    # Collect all pm25 sensor IDs with their location IDs
    pm25_sensors = []
    for lid, sensors in sensor_map.items():
        for sid, pname in sensors.items():
            if pname == "pm25":
                pm25_sensors.append((lid, sid))

    print(f"Found {len(pm25_sensors)} PM2.5 sensors to backfill")

    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=BACKFILL_DAYS)).strftime("%Y-%m-%dT00:00:00Z")
    date_to = now.strftime("%Y-%m-%dT23:59:59Z")

    total_inserted = 0
    total_errors = 0

    for idx, (lid, sid) in enumerate(pm25_sensors):
        try:
            url = (
                f"{fetch.OPENAQ_BASE}/sensors/{sid}/measurements/hourly"
                f"?limit=1000&sort=asc"
                f"&datetime_from={date_from}&datetime_to={date_to}"
            )
            data = fetch._request(url, api_key)
            results = data.get("results", [])
        except Exception as e:
            print(f"  [{idx+1}/{len(pm25_sensors)}] sensor {sid} (loc {lid}): {e}")
            total_errors += 1
            time.sleep(DELAY)
            continue

        inserted = 0
        for r in results:
            val = r["value"]
            if val is None or val < 1.0:
                continue
            dt_str = r["period"]["datetimeFrom"]["utc"]
            store.insert_measurement(lid, "pm25", val, "µg/m³", dt_str)
            inserted += 1

        total_inserted += inserted
        status = "OK" if results else "empty"
        print(f"  [{idx+1}/{len(pm25_sensors)}] sensor {sid} (loc {lid}): "
              f"{inserted} rows ({status})")

        time.sleep(DELAY)

    print(f"\nDone. Inserted {total_inserted} measurements "
          f"({total_errors} errors) for {len(pm25_sensors)} sensors.")


if __name__ == "__main__":
    backfill()
