"""Generate synthetic FHIR R4 resources for the clinical-linkage demonstration.

The output is checked against the base FHIR R4 specification (including the
body temperature vital-signs profile that R4 requires for LOINC 8310-5) by the
official HL7 validator in ``conformance/``. It does not claim UK Core profiles:
the synthetic Patient deliberately carries no NHS Number.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random

UTC = timezone.utc
# A namespace this project controls. example.org/example.com URIs are rejected by
# the HL7 validator in identifier systems, which the first version used.
BASE = "https://gbadedata.github.io/nhs-fhir-quality-gateway"
SYNTHETIC_PATIENT_ID_SYSTEM = f"{BASE}/Id/synthetic-patient"
FHIR_BASE = f"{BASE}/fhir"
VITAL_SIGNS_CATEGORY = {"coding": [{
    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
    "code": "vital-signs", "display": "Vital Signs"}]}


def narrative(summary: str) -> dict:
    """Minimal generated narrative (FHIR dom-6 best practice)."""
    from html import escape
    return {"status": "generated",
            "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{escape(summary)}</div>'}


def make_bundle(count: int = 90, seed: int = 41) -> dict:
    if count <= 0:
        raise ValueError("count must be positive")
    rng = random.Random(seed)
    entries: list[dict] = []
    base = datetime(2025, 7, 1, 9, tzinfo=UTC)
    for index in range(1, count + 1):
        suffix = f"SYN-{index:04d}"
        patient_id, encounter_id, observation_id, appointment_id = (
            f"pt-{suffix}", f"enc-{suffix}", f"obs-{suffix}", f"apt-{suffix}")
        encounter_start = base + timedelta(days=index, hours=index % 5)
        encounter_end = encounter_start + timedelta(minutes=30 + index % 30)
        observed = encounter_start + timedelta(minutes=10)
        appointment_start = encounter_start - timedelta(days=2)
        appointment_end = appointment_start + timedelta(minutes=20)
        birth_year = 1950 + (index * 7) % 55
        resources = [
            {
                "resourceType": "Patient", "id": patient_id,
                "birthDate": f"{birth_year}-01-15",
                "identifier": [{"system": SYNTHETIC_PATIENT_ID_SYSTEM, "value": patient_id}],
            },
            {
                "resourceType": "Encounter", "id": encounter_id, "status": "finished",
                "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
                "subject": {"reference": f"Patient/{patient_id}"},
                "period": {"start": encounter_start.isoformat(), "end": encounter_end.isoformat()},
            },
            {
                "resourceType": "Observation", "id": observation_id, "status": "final",
                "category": [VITAL_SIGNS_CATEGORY],
                "code": {"coding": [{"system": "http://loinc.org", "code": "8310-5", "display": "Body temperature"}]},
                "subject": {"reference": f"Patient/{patient_id}"},
                "encounter": {"reference": f"Encounter/{encounter_id}"},
                "effectiveDateTime": observed.isoformat(),
                "valueQuantity": {"value": round(rng.uniform(36.1, 37.6), 1),
                                  "unit": "degree Celsius", "system": "http://unitsofmeasure.org", "code": "Cel"},
            },
            {
                "resourceType": "Appointment", "id": appointment_id, "status": "fulfilled",
                "start": appointment_start.isoformat(), "end": appointment_end.isoformat(),
                "participant": [{"actor": {"reference": f"Patient/{patient_id}"}, "status": "accepted"}],
            },
        ]
        # RESTful fullUrls let the relative references (Patient/pt-SYN-0001) resolve
        # inside the Bundle, as the FHIR reference-resolution rules require.
        summaries = (
            f"Synthetic patient {patient_id}, born {birth_year}-01-15. Not a real person.",
            f"Finished ambulatory encounter {encounter_id} for {patient_id}.",
            f"Body temperature observation {observation_id} for {patient_id} (synthetic value).",
            f"Fulfilled appointment {appointment_id} for {patient_id}.",
        )
        for resource, summary in zip(resources, summaries):
            resource["text"] = narrative(summary)
        entries.extend({"fullUrl": f"{FHIR_BASE}/{r['resourceType']}/{r['id']}", "resource": r} for r in resources)
    return {"resourceType": "Bundle", "type": "collection", "entry": entries}


def write_bundle(bundle: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
