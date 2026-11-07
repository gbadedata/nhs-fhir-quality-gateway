"""Parse and quality-check the NHS ODS ``epraccur`` report (prescribing cost centres).

The column layout follows the ODS Reference Data Catalogue "Legacy .csv Field
Mapping" for epraccur.csv (27 positional columns, no header row):
https://www.odsdatasearchandexport.nhs.uk/referenceDataCatalogue/565791179.html

Two things in that specification matter most and were wrong in the first version
of this project:

* Column 13 (status) now carries the full status name (ACTIVE, INACTIVE, DORMANT,
  PROPOSED). The legacy file used single letters (A, C, D, P). Both are accepted.
* Column 26 (prescribing setting) now carries a non-primary role ID such as RO76
  (GP practice), sometimes pipe-separated (``RO76|RO268``). The legacy file used a
  number (4 = GP practice). Both are accepted.

The file also contains Welsh practices (codes starting ``W``) and closed or dormant
codes. A "current GP practices in England" count must exclude all of those.
"""
from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
import io
import re

EXPECTED_COLUMNS = 27

# 0-based positions from the ODS field mapping (column number minus one).
COL = {
    "code": 0, "name": 1, "nhs_region": 2, "icb": 3,
    "address1": 4, "address2": 5, "address3": 6, "town": 7, "county": 8, "postcode": 9,
    "open_date": 10, "close_date": 11, "status": 12, "subtype": 13, "commissioner": 14,
    "telephone": 17, "provider_purchaser": 23, "role": 25,
}

GP_PRACTICE_ROLE = "RO76"
LEGACY_GP_PRACTICE_SETTING = "4"

STATUS_NAMES = {"ACTIVE", "INACTIVE", "DORMANT", "PROPOSED"}
LEGACY_STATUS = {"A": "ACTIVE", "C": "INACTIVE", "D": "DORMANT", "P": "PROPOSED"}

# NHS England region codes used in column 3 (national grouping).
NHS_REGIONS = {
    "Y56": "London", "Y58": "South West", "Y59": "South East", "Y60": "Midlands",
    "Y61": "East of England", "Y62": "North West", "Y63": "North East and Yorkshire",
}

# Code formats from the catalogue's "Code Format" table for prescribing cost centres.
CODE_FORMATS = {
    "England": re.compile(r"^[A-HJ-NPWY]\d{5}$"),
    "Alderney": re.compile(r"^ALD\d{3}$"),
    "Guernsey": re.compile(r"^GUE\d{3}$"),
    "Jersey": re.compile(r"^JER\d{3}$"),
}
UK_POSTCODE = re.compile(r"^[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}$")


@dataclass
class Practice:
    code: str
    name: str
    status: str
    nation: str
    nhs_region_code: str
    icb_code: str
    commissioner_code: str
    address_lines: list[str]
    town: str
    postcode: str
    open_date: date
    close_date: date | None
    telephone: str
    roles: list[str]

    @property
    def is_current(self) -> bool:
        return self.status == "ACTIVE"


@dataclass
class ParseResult:
    practices: list[Practice] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    other_prescribing_settings: Counter = field(default_factory=Counter)
    source_rows: int = 0


def _date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None


def nation_of(code: str) -> str:
    """Nation implied by an ODS prescribing cost centre code.

    ``W`` codes are Welsh; ``Y`` is shared by England and the Isle of Man, so the
    caller uses the NHS region column to tell those apart.
    """
    if code.startswith("W"):
        return "Wales"
    for nation, pattern in CODE_FORMATS.items():
        if pattern.fullmatch(code):
            return nation
    return "Unknown"


def roles_of(raw: str) -> list[str]:
    return [part.strip().upper() for part in raw.split("|") if part.strip()]


def is_gp_practice(roles: list[str]) -> bool:
    return GP_PRACTICE_ROLE in roles or LEGACY_GP_PRACTICE_SETTING in roles


def parse(raw: bytes) -> ParseResult:
    """Parse epraccur bytes into GP practices, rejected rows and soft warnings.

    Rows that are not GP practices (walk-in centres, community services, prisons,
    PCN cost centres and so on) are counted by role and set aside, not rejected.
    """
    text = raw.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text, newline=""))
    result = ParseResult()
    seen: set[str] = set()
    for line_number, row in enumerate(reader, start=1):
        if not any(cell.strip() for cell in row):
            continue
        result.source_rows += 1
        if len(row) != EXPECTED_COLUMNS:
            result.rejected.append({"line": line_number, "code": row[0] if row else "",
                                    "reasons": [f"expected_{EXPECTED_COLUMNS}_columns_got_{len(row)}"]})
            continue
        value = {key: row[pos].strip() for key, pos in COL.items()}
        roles = roles_of(value["role"])
        if not is_gp_practice(roles):
            result.other_prescribing_settings[value["role"] or "(blank)"] += 1
            continue

        code = value["code"].upper()
        reasons: list[str] = []
        nation = nation_of(code)
        if nation == "Unknown":
            reasons.append("invalid_ods_code_format")
        if code in seen:
            reasons.append("duplicate_ods_code")
        for required in ("name", "address1", "town", "postcode", "open_date"):
            if not value[required]:
                reasons.append(f"missing_{required}")
        status = LEGACY_STATUS.get(value["status"].upper(), value["status"].upper())
        if status not in STATUS_NAMES:
            reasons.append("unknown_status")
        opened = _date(value["open_date"]) if value["open_date"] else None
        closed = _date(value["close_date"]) if value["close_date"] else None
        if value["open_date"] and opened is None:
            reasons.append("invalid_open_date")
        if value["close_date"] and closed is None:
            reasons.append("invalid_close_date")
        if opened and closed and closed < opened:
            reasons.append("closed_before_opened")
        if status == "ACTIVE" and value["close_date"]:
            reasons.append("active_with_close_date")
        if status == "INACTIVE" and not value["close_date"]:
            reasons.append("inactive_without_close_date")
        if reasons:
            result.rejected.append({"line": line_number, "code": code, "reasons": reasons})
            continue
        seen.add(code)

        postcode = value["postcode"].upper()
        if not UK_POSTCODE.fullmatch(postcode):
            result.warnings.append({"code": code, "warning": "postcode_not_in_standard_uk_format"})
        if status == "ACTIVE" and not value["telephone"]:
            result.warnings.append({"code": code, "warning": "active_practice_without_telephone"})
        if nation == "England" and code.startswith("Y") and value["nhs_region"] not in NHS_REGIONS:
            nation = "Isle of Man or unmapped"

        result.practices.append(Practice(
            code=code, name=value["name"], status=status, nation=nation,
            nhs_region_code=value["nhs_region"], icb_code=value["icb"],
            commissioner_code=value["commissioner"],
            address_lines=[v for v in (value["address1"], value["address2"], value["address3"]) if v],
            town=value["town"], postcode=postcode, open_date=opened, close_date=closed,
            telephone=value["telephone"], roles=roles,
        ))
    if result.source_rows == 0:
        raise ValueError("The ODS file contains no records")
    if not result.practices and not result.rejected:
        raise ValueError("No GP practice (RO76) records found; check that this is the epraccur report")
    return result


def financial_year(day: date) -> str:
    start = day.year if day.month >= 4 else day.year - 1
    return f"{start}-{str(start + 1)[2:]}"


def summarise(result: ParseResult, retrieved: date | None = None) -> dict:
    """Counts a service manager would ask for, with the denominators made explicit."""
    practices = result.practices
    by_status = Counter(p.status for p in practices)
    by_nation_status = Counter((p.nation, p.status) for p in practices)
    england_current = [p for p in practices if p.nation == "England" and p.is_current]
    by_region = Counter(NHS_REGIONS.get(p.nhs_region_code, "Unmapped") for p in england_current)

    # ODS notes that legacy archive rules mean closures before April 2017 are
    # incomplete, so the closure series starts in 2017-18.
    closures = Counter(financial_year(p.close_date) for p in practices
                       if p.close_date and p.nation == "England" and p.close_date >= date(2017, 4, 1))
    openings = Counter(financial_year(p.open_date) for p in practices
                       if p.nation == "England" and p.open_date >= date(2017, 4, 1))
    years = sorted(set(closures) | set(openings))
    reasons = Counter(reason for item in result.rejected for reason in item["reasons"])
    return {
        "source_rows": result.source_rows,
        "gp_practice_records": len(practices) + len(result.rejected),
        "gp_practice_records_accepted": len(practices),
        "gp_practice_records_rejected": len(result.rejected),
        "rejection_reasons": dict(sorted(reasons.items())),
        "warnings": dict(sorted(Counter(w["warning"] for w in result.warnings).items())),
        "non_gp_prescribing_cost_centres": sum(result.other_prescribing_settings.values()),
        "non_gp_settings_by_role": dict(result.other_prescribing_settings.most_common()),
        "by_status": dict(sorted(by_status.items())),
        "by_nation_and_status": {f"{n} / {s}": c for (n, s), c in sorted(by_nation_status.items())},
        "current_gp_practices_england": len(england_current),
        "current_gp_practices_england_by_region": dict(sorted(by_region.items())),
        "england_openings_and_closures_by_financial_year": [
            {"financial_year": y, "opened": openings.get(y, 0), "closed": closures.get(y, 0)} for y in years
        ],
        "latest_year_is_partial": bool(retrieved and years and years[-1] == financial_year(retrieved)),
    }
