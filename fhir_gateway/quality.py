"""Non-clinical interoperability and referential-quality reporting."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from collections import Counter


def summarise(db_path: str | Path, quarantine_path: str | Path) -> dict:
    with sqlite3.connect(db_path) as conn:
        counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("patient", "encounter", "observation", "appointment")}
        appointment_status = dict(conn.execute("SELECT status, COUNT(*) FROM appointment GROUP BY status"))
        encounters_with_observations = conn.execute(
            "SELECT COUNT(DISTINCT encounter_id) FROM observation").fetchone()[0]
        latest_audit = conn.execute(
            "SELECT source_entries,accepted_resources,quarantined_resources,source_sha256 FROM audit ORDER BY rowid DESC LIMIT 1").fetchone()
        fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
    quarantined = json.loads(Path(quarantine_path).read_text(encoding="utf-8"))
    reasons = dict(sorted(Counter(item["reason"] for item in quarantined).items()))
    return {
        "metadata": {
            "scope": "Layer 2 cross-resource rules; layer 1 R4 conformance is checked by the HL7 validator in conformance/",
            "data": "entirely synthetic resources; never use real patient records",
            "exclusions": "no clinical inference, patient treatment, PHI ingestion or predictive scoring",
        },
        "counts": counts,
        "status": appointment_status,
        "quality": {
            "source_entries": latest_audit[0], "accepted_resources": latest_audit[1],
            "quarantined_resources": latest_audit[2],
            "acceptance_percentage": round(100 * latest_audit[1] / latest_audit[0], 2) if latest_audit[0] else None,
            "encounters_with_observations": encounters_with_observations,
            "encounters_with_observations_percentage": round(100 * encounters_with_observations / counts["encounter"], 2) if counts["encounter"] else None,
            "foreign_key_issues": len(fk_issues), "quarantine_reasons": reasons,
            "source_sha256": latest_audit[3],
        },
    }


def write_metrics(metrics: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
