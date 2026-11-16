from __future__ import annotations

import sqlite3
from typing import Any

from basin_warning.observations.hydro_event import ContractError, utc_now


def prepare_notifications(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS river_reaches(
        reach_id TEXT PRIMARY KEY, downstream_id TEXT, travel_hours REAL NOT NULL,
        FOREIGN KEY(downstream_id) REFERENCES river_reaches(reach_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS station_reaches(
        station_id TEXT PRIMARY KEY, reach_id TEXT NOT NULL,
        FOREIGN KEY(reach_id) REFERENCES river_reaches(reach_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS alert_notices(
        notice_id TEXT PRIMARY KEY, reach_id TEXT NOT NULL, observation_id TEXT NOT NULL,
        observation_version INTEGER NOT NULL, status TEXT NOT NULL
        CHECK(status IN ('pending','delivered','acknowledged','cancelled')),
        issued_at TEXT NOT NULL, delivered_at TEXT, acknowledged_at TEXT,
        FOREIGN KEY(reach_id) REFERENCES river_reaches(reach_id)
    )""")


def register_reach(connection: sqlite3.Connection, reach_id: str,
                   downstream_id: str | None, travel_hours: float) -> None:
    prepare_notifications(connection)
    if not reach_id.strip() or type(travel_hours) not in (float, int) or not 0 <= travel_hours <= 720:
        raise ContractError("reach requires a bounded downstream travel time")
    if downstream_id == reach_id:
        raise ContractError("reach cannot drain into itself")
    if downstream_id and not connection.execute("SELECT 1 FROM river_reaches WHERE reach_id=?", (downstream_id,)).fetchone():
        raise ContractError("downstream reach must be registered first")
    old = connection.execute("SELECT downstream_id,travel_hours FROM river_reaches WHERE reach_id=?", (reach_id,)).fetchone()
    if old:
        if (old[0], old[1]) != (downstream_id, travel_hours):
            raise ContractError("published river topology cannot change silently")
        return
    connection.execute("INSERT INTO river_reaches VALUES(?,?,?)", (reach_id, downstream_id, travel_hours))


def assign_station(connection: sqlite3.Connection, station_id: str, reach_id: str) -> None:
    prepare_notifications(connection)
    if not station_id.strip() or not connection.execute("SELECT 1 FROM river_reaches WHERE reach_id=?", (reach_id,)).fetchone():
        raise ContractError("station requires known reach")
    old = connection.execute("SELECT reach_id FROM station_reaches WHERE station_id=?", (station_id,)).fetchone()
    if old and old[0] != reach_id:
        raise ContractError("station reach reassignment requires explicit review")
    connection.execute("INSERT OR IGNORE INTO station_reaches VALUES(?,?)", (station_id, reach_id))


def issue_notice(connection: sqlite3.Connection, notice_id: str, reach_id: str,
                 observation_id: str, observation_version: int) -> dict[str, Any]:
    prepare_notifications(connection)
    if not notice_id.strip() or not connection.execute("SELECT 1 FROM river_reaches WHERE reach_id=?", (reach_id,)).fetchone():
        raise ContractError("notice requires known reach")
    evidence = connection.execute("SELECT 1 FROM record_versions WHERE record_id=? AND version=?",
                                  (observation_id, observation_version)).fetchone()
    if not evidence:
        raise ContractError("notice observation version is unknown")
    old = connection.execute("SELECT * FROM alert_notices WHERE notice_id=?", (notice_id,)).fetchone()
    if old:
        if (old["reach_id"], old["observation_id"], old["observation_version"]) != (
                reach_id, observation_id, observation_version):
            raise ContractError("notice identity cannot be reassigned")
        return dict(old)
    connection.execute("INSERT INTO alert_notices VALUES(?,?,?,?,?, ?,NULL,NULL)",
                       (notice_id, reach_id, observation_id, observation_version, "pending", utc_now()))
    return dict(connection.execute("SELECT * FROM alert_notices WHERE notice_id=?", (notice_id,)).fetchone())


def update_notice(connection: sqlite3.Connection, notice_id: str, status: str) -> dict[str, Any]:
    prepare_notifications(connection)
    row = connection.execute("SELECT * FROM alert_notices WHERE notice_id=?", (notice_id,)).fetchone()
    if row is None:
        raise ContractError("unknown notice")
    allowed = {"pending": {"cancelled", "delivered"}, "delivered": {"acknowledged"}}
    if row["status"] != status:
        if status not in allowed.get(row["status"], set()):
            raise ContractError("invalid notice status transition")
        connection.execute("UPDATE alert_notices SET status=?, delivered_at=CASE WHEN ?='delivered' THEN ? ELSE delivered_at END, acknowledged_at=CASE WHEN ?='acknowledged' THEN ? ELSE acknowledged_at END WHERE notice_id=?",
                           (status, status, utc_now(), status, utc_now(), notice_id))
    return dict(connection.execute("SELECT * FROM alert_notices WHERE notice_id=?", (notice_id,)).fetchone())


def reach_notices(connection: sqlite3.Connection, reach_id: str) -> list[dict[str, Any]]:
    prepare_notifications(connection)
    return [dict(row) for row in connection.execute(
        "SELECT * FROM alert_notices WHERE reach_id=? ORDER BY issued_at,notice_id", (reach_id,))]
