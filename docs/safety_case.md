# Safety boundary and hazard log (illustrative, NOT a formal clinical safety case)

## Intended use

Demonstrate standards conformance and data-quality techniques on public ODS organisation data and fully synthetic FHIR R4 clinical records. No clinical workflow, patient safety claims, real records, treatment decisions, user authentication or NHS deployment.

## Explicit non-claims

- Conformance is checked by the HL7 validator (base R4 for synthetic clinical resources, UK Core Organization for ODS practices). That is not clinical risk management, and the project is **not** NHS approved.
- **NOT** clinically validated or audited by a Clinical Safety Officer.
- **NOT** intended for medical use or use with real personal health data.

## Engineering hazard scenarios

| Scenario | Impact if repurposed in a live service | Existing demonstration control | Required formal next steps |
| --- | --- | --- | --- |
| Observation linked to wrong patient | Potential clinical misattribution | Cross-check `Observation.subject` equals `Encounter.subject` | Identity, consent and national patient matching standards |
| Data silently dropped | Missing or incorrect health history | Quarantine with reason codes and entry index | Operational alerts, reconciliation and clinical workflow escalation |
| Duplicate messages | Double counting in reports | Duplicate `(resourceType, id)` check | Versioning, idempotency keys and resource update semantics |
| Wrong measurement semantics | Unsafe interpretation | Fixed example LOINC and UCUM codes; no diagnosis | Terminology validation, clinical quality assurance |
| Misread as FHIR compliant | Unsafe integration assumption | Prominent subset disclaimers | Certified/appropriate validators and UK Core-specific profile tests |
| Patient-identifiable inputs | Privacy violation | Synthetic-only fixtures and IDs | DPIA, data security controls, lawful basis and authorised environment |

## What would be needed to progress

1. Recruit and involve clinical staff, informatics specialists, patients and service representatives to clarify real use cases.
2. Agree lawful basis, access model, privacy impact assessment and data-processing responsibilities.
3. Select a specific FHIR R4 release, relevant published UK Core profiles, technical contracts and terminology-validation services.
4. Establish appropriate clinical risk management under DCB0129 / DCB0160 where applicable, including a qualified Clinical Safety Officer, hazard analysis, documented mitigations, assurance and deployment governance.
5. Add audit trails, secure integration/authentication, incident response, safe failure/retry/reconciliation, load testing, observability and supplier responsibilities.

Reference: https://digital.nhs.uk/services/clinical-safety/clinical-risk-management-standards
