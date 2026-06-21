"""Enrich locations with GSS government station metadata."""

import math
from src import gss, store

MATCH_DIST_KM = 3.0


def _haversine(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _gss_loc_id(gss_id):
    """Negative ID for GSS-only stations to avoid collision with OpenAQ IDs."""
    return -(gss_id + 1000000)


def enrich():
    """Fetch GSS stations, match to existing OpenAQ locations, add new ones.

    1. For each GSS station, find nearest OpenAQ location within 3km.
    2. Update matched locations with gss_station_id and source='openaq,gss'.
    3. Create new location entries for unmatched GSS stations.
    """
    gss_stations = gss.get_stations_full()
    print(f"GSS: {len(gss_stations)} stations from government API")

    # Only match against non-GSS locations (openaq or openaq,gss)
    existing = store.query(
        "SELECT id, name, latitude, longitude, source FROM locations WHERE latitude IS NOT NULL AND source != 'gss'"
    )

    existing_gss = {
        r["id"] for r in store.query("SELECT id FROM locations WHERE source='gss'")
    }

    matched = 0
    new_count = 0

    for gs in gss_stations:
        if gs["latitude"] is None or gs["longitude"] is None:
            continue

        best_dist = float("inf")
        best_loc = None

        for loc in existing:
            if loc["latitude"] is None:
                continue
            d = _haversine(
                gs["latitude"], gs["longitude"],
                loc["latitude"], loc["longitude"],
            )
            if d < best_dist:
                best_dist = d
                best_loc = loc

        if best_loc and best_dist < MATCH_DIST_KM:
            matched += 1
            # If this GSS station was previously GSS-only, mark it inactive
            gss_loc_id = _gss_loc_id(gs["id"])
            if gss_loc_id in existing_gss:
                store.query("UPDATE locations SET is_active=0 WHERE id=?", [gss_loc_id])
                existing_gss.discard(gss_loc_id)
            # Update the existing OpenAQ entry
            store.query(
                "UPDATE locations SET source=?, gss_station_id=? WHERE id=?",
                ["openaq,gss", gs["id"], best_loc["id"]],
            )
            print(f"  MATCH {gs['name']} <-> {best_loc['name']} ({best_dist:.2f} km)")
        else:
            # Check if we already have this GSS station in DB
            gss_loc_id = _gss_loc_id(gs["id"])
            if gss_loc_id in existing_gss:
                print(f"  SKIP {gs['name']} — already in DB")
                continue
            # Create new GSS-only entry
            loc = {
                "id": gss_loc_id,
                "name": gs["name"],
                "latitude": gs["latitude"],
                "longitude": gs["longitude"],
                "source": "gss",
                "gss_station_id": gs["id"],
            }
            store.upsert_locations([loc])
            new_count += 1
            reason = f"({best_dist:.2f} km from '{best_loc['name']}')" if best_loc else "(no nearby location)"
            print(f"  NEW  {gs['name']} {reason}")

    print(f"\nEnrichment complete: {matched} matched, {new_count} new GSS stations")
    return matched, new_count
