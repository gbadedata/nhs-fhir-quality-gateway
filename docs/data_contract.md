# Synthetic clinical Bundle contract (layer 2)

Layer 1 (HL7 validator) checks the Bundle against FHIR R4. This file describes the additional, narrower rules layer 2 enforces for this demonstration.

## Input

JSON top-level `{"resourceType":"Bundle","type":"collection","entry":[{"resource":{...}}, ...]}`. The demonstrator intentionally ignores entry-level routing / request fields. Only local synthetic IDs matching `*-SYN-*` are permitted (a privacy guard for a public repository). fullUrls are RESTful (`.../fhir/{type}/{id}`) so relative references resolve.

| Resource | Required subset | Referential checks |
| --- | --- | --- |
| `Patient` | `id`, ISO `birthDate`, synthetic `identifier[0]` in this project's namespace, value equal to ID; no name, telecom, address, photo or contact | None |
| `Encounter` | `id`, `status`, `subject.reference`, `period.start/end` | referenced Patient exists |
| `Observation` | `id`, `status=final`, `category` vital-signs, `subject.reference`, `encounter.reference`, `code.coding[0]`, `valueQuantity`, `effectiveDateTime` | Patient + Encounter exist; Encounter's patient matches; date within Encounter period |
| `Appointment` | `id`, `status`, `participant[0].actor.reference`, `start/end` | referenced Patient exists |

Supported observation coding: LOINC `8310-5` (body temperature). Quantity: numeric, UCUM `Cel`. Date/time values must include an offset or `Z`; periods must be chronological.

These checks are limited, necessary demonstrations and not sufficient for actual syntactic or semantic conformance. For example, the real FHIR specification defines additional cardinalities, valid elements, terminology and invariants not implemented here.

## Processing rules

1. Reject structurally invalid resources with reason codes.
2. Reject repeated `(resourceType, id)` pairs within a Bundle. The **first valid** occurrence is kept.
3. Check existence of referenced resources in dependency order, rather than relying on Bundle order.
4. Quarantine unresolved references and patient mismatches; their dependents are also rejected.
5. Insert accepted resources into SQLite under foreign-key constraints.
6. Replace prior tables on each run, retaining historical audit entries, and provide an SHA-256 source digest.

## Known limitations

- No update semantics, version histories, extensions, resource URL dereferencing or transaction Bundles.
- No personal or patient identifier integration; local IDs are entirely invented.
- No clinical appropriateness rules for observations. The code does not interpret the body-temperature values.
- No streaming data, cross-system reconciliation or concurrency.
