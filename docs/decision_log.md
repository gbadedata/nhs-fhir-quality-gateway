# Architecture decisions

## 001: FHIR R4-shaped subset, not full conformance (superseded by 006)

**Why:** A small but transparent implementation can demonstrate structural checks, data lineage and cross-resource linking without implying it supports the vast FHIR specification. Limitation is intentionally repeated in code, report and README.

## 002: Four common resource types

`Patient`, `Encounter`, `Observation` and `Appointment` illustrate linkage across administration and clinical-events data. The model does not represent a complete patient journey or determine any treatment.

## 003: Deterministic synthetic bundles

Avoids sharing personal data or claiming access to patient records. It also makes CI and debugging reproducible. Invented observations must not be mistaken for population-level evidence.

## 004: Two-phase validation

First check shape and duplicates, then reference consistency. This allows forward references within bundles and isolates invalid parents from their dependents. Quarantine entries retain original position and reason code for investigation.

## 005: Zero-dependency CLI and quality report

Works offline and demonstrates the data engineering core in under a minute, without running a server. Scale, UK Core terminology validation and operational security remain outside scope.

## 006 (v0.2): Use the official validator as an independent oracle

A validator written by the same person who wrote the generator shares the generator's blind spots. The HL7 validator found 270 errors that the in-house checks had passed. Layer 1 is now the HL7 validator; the in-house rules are layer 2 and cover only what the standard cannot express.

## 007: Run the real-data path on real data before calling it done

The ODS parser was tested on invented rows and counted closed and dormant practices as current. The committed snapshot and its pinned counts are now part of the test suite.

## 008: Build from the publisher's specification, keep legacy compatibility

Column meanings come from the ODS Reference Data Catalogue. Both the current and the legacy encodings of status and prescribing setting are accepted.

## 009: Claim UK Core only where it is checked

ODS Organization resources declare and pass UK Core Organization. Synthetic clinical resources claim base R4 only.
