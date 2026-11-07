# Product brief: FHIR Quality Gateway

## Problem statement

An organisation wants to exchange information between systems, but inconsistent identifiers, missing links and invalid clinical-event timestamps can make integrated records unreliable. A management trainee should be able to explain both the potential benefits and the need for assurance before any real deployment.

## Stakeholders

Patients; clinicians; clinical safety officer; NHS digital teams; information governance; data engineers; EPR suppliers; service managers.

## User stories and evidence

| Story | Acceptance evidence |
| --- | --- |
| As a data engineer, I need to process linked synthetic FHIR-shaped records | Bundle loader for four resource types |
| As an analyst, I need to know which data is reliable for basic descriptive reporting | SQLite foreign keys, status/period checks and linkage metrics |
| As a quality lead, I need clear evidence when a message cannot be accepted | original entry indices and explicit reasons in quarantine |
| As a reviewer, I need reproducible positive and negative examples | included good/bad Bundle fixtures and unit tests |
| As an NHS programme team, I need no confusion about deployment readiness | repeated non-conformance and non-clinical disclaimers plus hazard log |

## Decision scenario for an NHS manager

A supplier demonstrates a successful interface using this small prototype. The **incorrect response** is to immediately approve integration into a hospital clinical system. Stronger judgement means involving clinicians and staff, identifying the required UK Core profiles and contracts, applying the right formal clinical safety and information governance processes, validating with appropriate standards-aware tools, and planning controlled testing and incident management. Digital enthusiasm must be balanced with patient safety, social awareness and collaboration.

## Added in version 0.2

- The official HL7 validator with pinned UK Core 2.0.2, run in CI.
- Real ODS GP practice data mapped to UK Core Organization.

## What a further iteration could add

- A real terminology service and canonical coding validation.
- Versioned, auditable FHIR resource updates and message retry semantics.
- Security controls, authentication, role-based authorisation and monitoring in an approved environment.
- Formal patient and clinician co-design, hazard identification and clinical risk management where applicable.

No such production features are claimed to exist in the prototype.
