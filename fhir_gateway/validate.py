"""Cross-resource business rules for the synthetic clinical Bundle.

Layer 1 (standards conformance) is the official HL7 FHIR validator, run from
``conformance/``. This module is layer 2: rules a structure validator cannot
express, such as an Observation pointing at another patient's Encounter, or a
measurement timed outside the Encounter it belongs to. It also enforces the
repository's privacy guard (synthetic identifiers only, no personal fields).
"""
from __future__ import annotations

from datetime import date, datetime
import re

from .generate import SYNTHETIC_PATIENT_ID_SYSTEM

RESOURCE_TYPES = ("Patient", "Encounter", "Observation", "Appointment")
ID_PATTERN = re.compile(r"^[A-Za-z0-9.-]{1,64}$")


def _datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None
    except ValueError:
        return None


def _path(data: object, *fields: str | int) -> object:
    try:
        for field in fields:
            data = data[field]
        return data
    except (TypeError, KeyError, IndexError):
        return None


def _reference(resource: dict, *fields: str | int, resource_type: str) -> str | None:
    ref = _path(resource, *fields, "reference")
    if not isinstance(ref, str) or not ref.startswith(f"{resource_type}/"):
        return None
    resource_id = ref.split("/", 1)[1]
    return resource_id if ID_PATTERN.fullmatch(resource_id) else None


def validate_shape(resource: object) -> str | None:
    if not isinstance(resource, dict):
        return "not_a_resource_object"
    kind = resource.get("resourceType")
    if kind not in RESOURCE_TYPES:
        return "unsupported_resource_type"
    if not isinstance(resource.get("id"), str) or not ID_PATTERN.fullmatch(resource["id"]):
        return "invalid_resource_id"
    expected_prefix = {"Patient": "pt", "Encounter": "enc", "Observation": "obs", "Appointment": "apt"}[kind]
    if not re.fullmatch(rf"{expected_prefix}-SYN-[0-9]{{4}}", resource["id"]):
        return "non_synthetic_id"

    if kind == "Patient":
        if any(field in resource for field in ("name", "telecom", "address", "photo", "contact")):
            return "disallowed_personal_fields"
        if _path(resource, "identifier", 0, "system") != SYNTHETIC_PATIENT_ID_SYSTEM:
            return "invalid_synthetic_identifier_system"
        try:
            date.fromisoformat(resource["birthDate"])
        except (KeyError, TypeError, ValueError):
            return "invalid_birth_date"
        value = _path(resource, "identifier", 0, "value")
        if value != resource["id"]:
            return "invalid_synthetic_identifier"
    elif kind == "Encounter":
        if resource.get("status") not in ("finished", "in-progress"):
            return "invalid_encounter_status"
        if _reference(resource, "subject", resource_type="Patient") is None:
            return "missing_patient_reference"
        start, end = _datetime(_path(resource, "period", "start")), _datetime(_path(resource, "period", "end"))
        if not start or not end or start > end:
            return "invalid_encounter_period"
    elif kind == "Observation":
        if resource.get("status") != "final":
            return "invalid_observation_status"
        if _reference(resource, "subject", resource_type="Patient") is None:
            return "missing_patient_reference"
        if _reference(resource, "encounter", resource_type="Encounter") is None:
            return "missing_encounter_reference"
        if _path(resource, "category", 0, "coding", 0, "code") != "vital-signs":
            return "missing_vital_signs_category"
        coding = _path(resource, "code", "coding", 0)
        if not isinstance(coding, dict) or coding.get("system") != "http://loinc.org" or coding.get("code") != "8310-5":
            return "unsupported_observation_code"
        quantity = resource.get("valueQuantity")
        if not isinstance(quantity, dict) or quantity.get("system") != "http://unitsofmeasure.org" or quantity.get("code") != "Cel" or type(quantity.get("value")) not in (int, float):
            return "invalid_observation_quantity"
        if _datetime(resource.get("effectiveDateTime")) is None:
            return "invalid_observation_timestamp"
    elif kind == "Appointment":
        if resource.get("status") not in ("booked", "cancelled", "fulfilled"):
            return "invalid_appointment_status"
        if _reference(resource, "participant", 0, "actor", resource_type="Patient") is None:
            return "missing_patient_reference"
        start, end = _datetime(resource.get("start")), _datetime(resource.get("end"))
        if not start or not end or start > end:
            return "invalid_appointment_period"
    return None


def partition_bundle(bundle: object) -> tuple[list[dict], list[dict]]:
    if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle" or bundle.get("type") != "collection" or not isinstance(bundle.get("entry"), list):
        raise ValueError("Expected a FHIR-shaped collection Bundle with entry list")
    raw_resources: dict[str, dict[str, dict]] = {kind: {} for kind in RESOURCE_TYPES}
    accepted: list[dict] = []
    quarantine: list[dict] = []
    candidates: list[tuple[int, dict]] = []
    observed: set[tuple[str, str]] = set()
    for index, entry in enumerate(bundle["entry"]):
        resource = entry.get("resource") if isinstance(entry, dict) else None
        reason = validate_shape(resource)
        if reason:
            quarantine.append({"entry_index": index, "reason": reason, "resource_type": resource.get("resourceType") if isinstance(resource, dict) else None})
            continue
        key = resource["resourceType"], resource["id"]
        if key in observed:
            quarantine.append({"entry_index": index, "reason": "duplicate_resource_id", "resource_type": key[0]})
            continue
        observed.add(key)
        candidates.append((index, resource))
        raw_resources[key[0]][key[1]] = resource

    # Foreign-key validation checks only structurally accepted resources in dependency order.
    valid: dict[str, dict[str, dict]] = {kind: {} for kind in RESOURCE_TYPES}
    for kind in RESOURCE_TYPES:
        for index, resource in (item for item in candidates if item[1]["resourceType"] == kind):
            reason = None
            if kind == "Encounter":
                patient = _reference(resource, "subject", resource_type="Patient")
                if patient not in valid["Patient"]:
                    reason = "unresolved_patient_reference"
            elif kind == "Observation":
                patient = _reference(resource, "subject", resource_type="Patient")
                encounter = _reference(resource, "encounter", resource_type="Encounter")
                if patient not in valid["Patient"]:
                    reason = "unresolved_patient_reference"
                elif encounter not in valid["Encounter"]:
                    reason = "unresolved_encounter_reference"
                elif _reference(valid["Encounter"][encounter], "subject", resource_type="Patient") != patient:
                    reason = "encounter_patient_mismatch"
                else:
                    effective = _datetime(resource.get("effectiveDateTime"))
                    start = _datetime(_path(valid["Encounter"][encounter], "period", "start"))
                    end = _datetime(_path(valid["Encounter"][encounter], "period", "end"))
                    if not (start <= effective <= end):
                        reason = "observation_outside_encounter_period"
            elif kind == "Appointment":
                patient = _reference(resource, "participant", 0, "actor", resource_type="Patient")
                if patient not in valid["Patient"]:
                    reason = "unresolved_patient_reference"
            if reason:
                quarantine.append({"entry_index": index, "reason": reason, "resource_type": kind})
            else:
                accepted.append(resource)
                valid[kind][resource["id"]] = resource
    return accepted, sorted(quarantine, key=lambda item: item["entry_index"])
