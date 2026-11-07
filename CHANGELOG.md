# Changelog

## 0.2.0 (2026-11-07)

- Ran the ODS path on the real `epraccur` file for the first time. Fixed status handling (`ACTIVE`/`INACTIVE`/`DORMANT`, plus legacy letters): v0.1 counted 8,193 "valid GP practices"; the correct count of active practices in England is 6,162. Welsh practices are now separated.
- Rebuilt the parser from the ODS Reference Data Catalogue field mapping: code format by nation, mandatory fields, date and status consistency, legacy prescribing-setting `4`.
- Organization resources now declare and pass UK Core Organization 2.0.2 (organisation period, type, address lines, commissioner as `partOf`). v0.1 used invalid `urn:oid:ods:...` fullUrls.
- Added layer 1 validation with the official HL7 FHIR validator (`conformance/`), run in CI. It found 270 errors in v0.1's synthetic Bundle that the in-house checks had accepted; all fixed.
- Invalid fixture now carries four defects showing which layer catches what.
- Committed the ODS snapshot with a SHA-256 manifest and pinned regression tests (56 tests in total).
- Replaced `real_ods/` with `ods_directory/`; rewrote README and docs.

## 0.1.0

Synthetic FHIR-shaped pipeline with in-house checks; untested ODS import.
