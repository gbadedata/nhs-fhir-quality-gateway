"""Rebuild the committed synthetic fixtures (run from the repository root).

The invalid fixture carries four deliberate defects, chosen so that some are
caught by the HL7 validator (layer 1) and some only by the gateway's
cross-resource rules (layer 2). See docs/two_layer_validation.md.
"""
import copy
import json
from pathlib import Path

from fhir_gateway.generate import FHIR_BASE, make_bundle

ROOT = Path(__file__).resolve().parents[1]


def write(bundle: dict, name: str) -> None:
    (ROOT / "fixtures" / name).write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")


def invalid_bundle() -> dict:
    bundle = make_bundle(4, 41)
    entries = bundle["entry"]
    # Defect 1: an exact duplicate Patient entry (same type, id and fullUrl).
    entries.append(copy.deepcopy(entries[0]))
    # Defect 2: an Observation that points at an Encounter that does not exist.
    orphan = copy.deepcopy(entries[2])
    orphan["resource"]["id"] = "obs-SYN-9001"
    orphan["resource"]["encounter"]["reference"] = "Encounter/enc-SYN-9999"
    orphan["fullUrl"] = f"{FHIR_BASE}/Observation/obs-SYN-9001"
    entries.append(orphan)
    # Defect 3: patient 2's Observation linked to patient 3's Encounter.
    mismatch = copy.deepcopy(entries[6])
    mismatch["resource"]["id"] = "obs-SYN-9002"
    mismatch["resource"]["encounter"]["reference"] = "Encounter/enc-SYN-0003"
    mismatch["fullUrl"] = f"{FHIR_BASE}/Observation/obs-SYN-9002"
    entries.append(mismatch)
    # Defect 4: an Observation recorded a day before its Encounter started.
    early = copy.deepcopy(entries[10])
    early["resource"]["id"] = "obs-SYN-9003"
    early["resource"]["effectiveDateTime"] = "2025-07-01T09:00:00+00:00"
    early["fullUrl"] = f"{FHIR_BASE}/Observation/obs-SYN-9003"
    entries.append(early)
    return bundle


if __name__ == "__main__":
    write(make_bundle(90, 41), "synthetic_bundle.json")
    write(invalid_bundle(), "invalid_bundle.json")
    print("fixtures rebuilt")
