# ODS GP practice directory

## Source

`epraccur` from the ODS Data Search and Export service: every prescribing cost centre in England, Wales, the Isle of Man and the Channel Islands. GP practices are the subset with non-primary role `RO76`. The file has no header row; its 27 positional columns are defined in the ODS Reference Data Catalogue ("Legacy .csv Field Mapping").

## What changed between the legacy file and the current one

| Column | Legacy | Current | Handling |
|---|---|---|---|
| 13 Status | `A`, `C`, `D`, `P` | `ACTIVE`, `INACTIVE`, `DORMANT`, `PROPOSED` | Both accepted; legacy letters mapped |
| 26 Prescribing setting | Number (`4` = GP practice) | Role ID (`RO76`), pipe-separated when there are several | Both accepted |
| 3 National grouping | From the commissioner | From the practice postcode | Used for NHS England region |

## Checks on each GP practice row

Rejected to `quarantine.json` with reasons: wrong column count; code not matching the published format for its nation; duplicate code; missing name, address line 1, town, postcode or open date; unparseable dates; close date before open date; `ACTIVE` with a close date; `INACTIVE` without one; unknown status.

Kept with a warning: postcode not in standard UK format; active practice without a telephone number.

The 7 November 2026 snapshot passes every rejection check. That is a result about this file, not a reason to drop the checks.

## Counting "GP practices in England"

15,692 rows -> 7,499 non-GP settings set aside by role -> 8,193 GP practice records -> exclude 1,573 inactive and 60 dormant -> exclude 398 active Welsh practices (`W` codes) -> **6,162**.

## UK Core mapping

| ODS | Organization element |
|---|---|
| Organisation code | `id`, `identifier` (system `https://fhir.nhs.uk/Id/ods-organization-code`) |
| Status | `active` (true only for `ACTIVE`) |
| Open and close dates | `organization-period` extension |
| Name | `name` |
| Address lines, town, postcode | `address` |
| Prescribing telephone | `telecom` (ODS notes this is not necessarily the reception number) |
| Commissioner (Sub ICB Location) | `partOf` as a logical reference by ODS code |
| GP practice | `type` = `prov` (HL7 organization-type, the UK Core binding) |

Every resource declares `meta.profile` UK Core Organization and passes the HL7 validator with no errors or warnings (`conformance/results/`).
