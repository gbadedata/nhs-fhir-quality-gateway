# Two-layer validation

| Layer | Tool | Question | Examples it catches |
|---|---|---|---|
| 1. Conformance | Official HL7 FHIR validator, R4 4.0.1, UK Core 2.0.2 | Is each resource valid against the specification and declared profiles? | Missing required elements, invalid identifiers, cardinality, duplicate fullUrls, profile constraints such as the R4 body temperature profile |
| 2. Business rules | `fhir_gateway/validate.py` | Do the resources make sense together? | Observation linked to another patient's Encounter; reading timed outside its Encounter; reference to a resource that is not in the Bundle; privacy guard (synthetic IDs only, no names or addresses) |

## What happened when layer 1 was added

The first version relied on layer 2 alone and described its output as "FHIR R4-shaped". Its synthetic Bundle passed its own checks at 100%. The HL7 validator reported 270 errors on the same file:

- 90: identifier system `https://example.org/...`; example domains are not allowed in that context.
- 90 + 90: Observations for LOINC 8310-5 must conform to the R4 body temperature profile, which requires a `vital-signs` category.
- Warnings for fullUrls (`urn:uuid:...`) that relative references such as `Patient/pt-SYN-0001` could not resolve against.

The ODS Organization Bundle failed on fullUrls of the form `urn:oid:ods:A81001`, which are not valid OIDs.

All of these are fixed. The generator now uses an identifier namespace this project controls, includes the category, uses RESTful fullUrls and adds generated narrative. Layer 2 gained a `missing_vital_signs_category` rule so the gap cannot reopen unnoticed.

## Remaining warnings (synthetic Bundle)

- UCUM `Cel` cannot be confirmed without a terminology server.
- "All observations should have a performer" (best-practice recommendation). The synthetic data deliberately has no practitioners.
