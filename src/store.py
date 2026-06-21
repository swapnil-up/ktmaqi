"""SQLite store for AQI measurements."""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "aqi.db")


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _migrate(db):
    for col_def in [
        "source TEXT NOT NULL DEFAULT 'openaq'",
        "gss_station_id INTEGER",
    ]:
        try:
            db.execute(f"ALTER TABLE locations ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass


def init_db():
    with _conn() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                is_active INTEGER DEFAULT 1,
                source TEXT NOT NULL DEFAULT 'openaq',
                gss_station_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS sensors (
                id INTEGER PRIMARY KEY,
                location_id INTEGER NOT NULL,
                parameter TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                parameter TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT,
                measured_at TEXT NOT NULL,
                FOREIGN KEY (location_id) REFERENCES locations(id)
            );

            CREATE INDEX IF NOT EXISTS idx_meas_loc_param_time
                ON measurements(location_id, parameter, measured_at DESC);
        """)
        _migrate(db)


def upsert_locations(locations):
    with _conn() as db:
        for loc in locations:
            source = loc.get("source", "openaq")
            gss_id = loc.get("gss_station_id")
            db.execute(
                """INSERT INTO locations (id, name, latitude, longitude, is_active, source, gss_station_id)
                   VALUES (?, ?, ?, ?, 1, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       name=excluded.name,
                       latitude=excluded.latitude,
                       longitude=excluded.longitude,
                       source=excluded.source,
                       gss_station_id=excluded.gss_station_id,
                       is_active=1""",
                (loc["id"], loc["name"], loc["latitude"], loc["longitude"], source, gss_id),
            )


def upsert_sensors(sensor_map):
    """sensor_map: {location_id: {sensor_id: parameter_name}}"""
    with _conn() as db:
        for lid, sensors in sensor_map.items():
            for sid, pname in sensors.items():
                db.execute(
                    """INSERT INTO sensors (id, location_id, parameter)
                       VALUES (?, ?, ?)
                       ON CONFLICT(id) DO NOTHING""",
                    (sid, lid, pname),
                )


def load_sensor_map():
    """Return {location_id: {sensor_id: parameter_name}} from cache."""
    rows = query("SELECT id, location_id, parameter FROM sensors")
    result = {}
    for r in rows:
        result.setdefault(r["location_id"], {})[r["id"]] = r["parameter"]
    return result


def location_ids_with_sensors():
    """Return set of location_ids that already have sensor data cached."""
    rows = query("SELECT DISTINCT location_id FROM sensors")
    return {r["location_id"] for r in rows}


def insert_measurement(location_id, parameter, value, unit, measured_at):
    with _conn() as db:
        db.execute(
            """INSERT INTO measurements (location_id, parameter, value, unit, measured_at)
               VALUES (?, ?, ?, ?, ?)""",
            (location_id, parameter, value, unit, measured_at),
        )


def query(sql, params=None):
    with _conn() as db:
        cur = db.execute(sql, params or [])
        return [dict(r) for r in cur.fetchall()]


def mark_inactive(active_ids):
    with _conn() as db:
        db.execute(
            "UPDATE locations SET is_active = 0 WHERE id NOT IN ({})".format(
                ",".join("?" for _ in active_ids)
            ),
            list(active_ids),
        )
