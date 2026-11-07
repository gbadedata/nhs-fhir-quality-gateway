"""Map ODS GP practice records to FHIR R4 Organization resources that claim the
UK Core Organization profile (fhir.r4.ukcore.stu2 2.0.2).

Profile conformance is checked by the official HL7 validator, not by this module;
see ``conformance/``. This module only builds the resources.
"""
from __future__ import annotations

from html import escape

from .epraccur import Practice

UK_CORE_ORGANIZATION = "https://fhir.hl7.org.uk/StructureDefinition/UKCore-Organization"
ODS_CODE_SYSTEM = "https://fhir.nhs.uk/Id/ods-organization-code"
ORG_PERIOD_EXTENSION = "http://hl7.org/fhir/StructureDefinition/organization-period"
HL7_ORG_TYPE = "http://terminology.hl7.org/CodeSystem/organization-type"


def _iso(day) -> str | None:
    return day.isoformat() if day else None


def to_organization(practice: Practice) -> dict:
    period = {"start": _iso(practice.open_date)}
    if practice.close_date:
        period["end"] = _iso(practice.close_date)
    resource = {
        "resourceType": "Organization",
        "id": practice.code,
        "meta": {"profile": [UK_CORE_ORGANIZATION]},
        "text": {"status": "generated", "div": (
            '<div xmlns="http://www.w3.org/1999/xhtml">'
            f"{escape(practice.name)} ({escape(practice.code)}), GP practice, ODS status {escape(practice.status)}, "
            f"{escape(practice.postcode)}</div>")},
        "extension": [{"url": ORG_PERIOD_EXTENSION, "valuePeriod": period}],
        "identifier": [{"system": ODS_CODE_SYSTEM, "value": practice.code}],
        # FHIR 'active' is a boolean. ODS DORMANT and INACTIVE codes are not in
        # use, so both map to false; PROPOSED practices are not yet open.
        "active": practice.status == "ACTIVE",
        "type": [{"coding": [{"system": HL7_ORG_TYPE, "code": "prov", "display": "Healthcare Provider"}]}],
        "name": practice.name,
        "address": [{
            "use": "work",
            "line": practice.address_lines,
            "city": practice.town,
            "postalCode": practice.postcode,
            "country": "GB",
        }],
    }
    if practice.telephone:
        # ODS notes this is the number for prescribing purposes, not necessarily reception.
        resource["telecom"] = [{"system": "phone", "value": practice.telephone, "use": "work"}]
    if practice.commissioner_code:
        resource["partOf"] = {
            "identifier": {"system": ODS_CODE_SYSTEM, "value": practice.commissioner_code},
            "display": "Commissioning Sub ICB Location (ODS RE4 relationship)",
        }
    return resource


def to_bundle(practices: list[Practice]) -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"fullUrl": f"https://example.org/fhir/Organization/{p.code}", "resource": to_organization(p)}
            for p in practices
        ],
    }
