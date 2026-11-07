"""FHIR-subset ingestion: audit metadata, SQLite tables and rejection evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

from .validate import _path, _reference, partition_bundle

SQL = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS patient (
 id TEXT PRIMARY KEY, birth_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS encounter (
 id TEXT PRIMARY KEY, patient_id TEXT NOT NULL REFERENCES patient(id),
 status TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observation (
 id TEXT PRIMARY KEY, patient_id TEXT NOT NULL REFERENCES patient(id),
 encounter_id TEXT NOT NULL REFERENCES encounter(id), observed_at TEXT NOT NULL,
 code TEXT NOT NULL, value_celsius REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS appointment (
 id TEXT PRIMARY KEY, patient_id TEXT NOT NULL REFERENCES patient(id),
 status TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
 source_sha256 TEXT NOT NULL, source_entries INTEGER NOT NULL,
 accepted_resources INTEGER NOT NULL, quarantined_resources INTEGER NOT NULL,
 loaded_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""


def ingest(bundle_path: str | Path, db_path: str | Path, quarantine_path: str | Path) -> dict:
    bundle_path, db_path, quarantine_path = map(Path, (bundle_path, db_path, quarantine_path))
    original_bytes = bundle_path.read_bytes()
    source = json.loads(original_bytes)
    good, bad = partition_bundle(source)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    quarantine_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SQL)
        with conn:
            # Reverse dependent order of delete for referential integrity.
            for table in ("observation", "appointment", "encounter", "patient"):
                conn.execute(f"DELETE FROM {table}")
            for resource in good:
                kind = resource["resourceType"]
                if kind == "Patient":
                    conn.execute("INSERT INTO patient VALUES(?,?)", (resource["id"], resource["birthDate"]))
                elif kind == "Encounter":
                    conn.execute("INSERT INTO encounter VALUES(?,?,?,?,?)", (
                        resource["id"], _reference(resource, "subject", resource_type="Patient"),
                        resource["status"], _path(resource, "period", "start"), _path(resource, "period", "end")))
                elif kind == "Observation":
                    conn.execute("INSERT INTO observation VALUES(?,?,?,?,?,?)", (
                        resource["id"], _reference(resource, "subject", resource_type="Patient"),
                        _reference(resource, "encounter", resource_type="Encounter"), resource["effectiveDateTime"],
                        "LOINC:8310-5", resource["valueQuantity"]["value"]))
                elif kind == "Appointment":
                    conn.execute("INSERT INTO appointment VALUES(?,?,?,?,?)", (
                        resource["id"], _reference(resource, "participant", 0, "actor", resource_type="Patient"),
                        resource["status"], resource["start"], resource["end"]))
            conn.execute("INSERT INTO audit(source_sha256,source_entries,accepted_resources,quarantined_resources) VALUES(?,?,?,?)", (
                hashlib.sha256(original_bytes).hexdigest(), len(source["entry"]), len(good), len(bad)))
    quarantine_path.write_text(json.dumps(bad, indent=2), encoding="utf-8")
    return {"source_entries": len(source["entry"]), "accepted": len(good), "quarantined": len(bad),
            "sha256": hashlib.sha256(original_bytes).hexdigest()}
