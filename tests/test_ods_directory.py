"""Tests for the ODS GP practice parser, quality rules and UK Core mapping.

Synthetic rows use the real 27-column epraccur layout with invented codes and
names. The final test class runs against the committed real snapshot.
"""
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from ods_directory.epraccur import parse, summarise
from ods_directory.fhir import UK_CORE_ORGANIZATION, to_bundle, to_organization
from ods_directory.__main__ import run

ROOT = Path(__file__).resolve().parents[1]


def row(code="A99001", name="EXAMPLE SURGERY", status="ACTIVE", role="RO76", opened="20100401",
        closed="", region="Y56", postcode="AB1 2CD", width=27):
    cells = [""] * 27
    for pos, value in ((0, code), (1, name), (2, region), (3, "QAB"), (4, "1 TEST STREET"), (7, "TESTTOWN"),
                       (9, postcode), (10, opened), (11, closed), (12, status), (13, "B"), (14, "99X"),
                       (17, "01234 567890"), (21, "1"), (23, "99X"), (25, role)):
        cells[pos] = value
    out = io.StringIO()
    csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator="\r\n").writerow(cells[:width])
    return out.getvalue()


def file_of(*rows: str) -> bytes:
    return "".join(rows).encode()


class StatusAndRoleTests(unittest.TestCase):
    def test_full_status_names_from_current_file(self):
        result = parse(file_of(row("A99001"), row("A99002", status="INACTIVE", closed="20200331"),
                               row("A99003", status="DORMANT")))
        self.assertEqual({p.code: p.status for p in result.practices},
                         {"A99001": "ACTIVE", "A99002": "INACTIVE", "A99003": "DORMANT"})
        self.assertEqual([p.code for p in result.practices if p.is_current], ["A99001"])

    def test_legacy_single_letter_status_and_numeric_setting(self):
        result = parse(file_of(row("A99001", status="A", role="4"), row("A99002", status="C", role="4", closed="20200331")))
        self.assertEqual([p.status for p in result.practices], ["ACTIVE", "INACTIVE"])

    def test_non_gp_settings_are_set_aside_not_rejected(self):
        result = parse(file_of(row("A99001"), row("Y99001", role="RO247"), row("Y99002", role="RO80|RO87")))
        self.assertEqual(len(result.practices), 1)
        self.assertEqual(result.rejected, [])
        self.assertEqual(sum(result.other_prescribing_settings.values()), 2)

    def test_pipe_separated_roles_including_gp_practice(self):
        result = parse(file_of(row("A99001", role="RO76|RO268")))
        self.assertEqual(result.practices[0].roles, ["RO76", "RO268"])

    def test_welsh_practice_is_not_counted_as_england(self):
        result = parse(file_of(row("A99001"), row("W99001", region="")))
        summary = summarise(result)
        self.assertEqual(summary["current_gp_practices_england"], 1)
        self.assertEqual(summary["by_nation_and_status"]["Wales / ACTIVE"], 1)


class RejectionTests(unittest.TestCase):
    def reasons(self, *rows):
        return [r["reasons"] for r in parse(file_of(row("A99000"), *rows)).rejected]

    def test_duplicate_code(self):
        self.assertEqual(self.reasons(row("A99000")), [["duplicate_ods_code"]])

    def test_invalid_code_format(self):
        self.assertEqual(self.reasons(row("I12345")), [["invalid_ods_code_format"]])

    def test_active_with_close_date(self):
        self.assertEqual(self.reasons(row("A99001", closed="20200101")), [["active_with_close_date"]])

    def test_inactive_without_close_date(self):
        self.assertEqual(self.reasons(row("A99001", status="INACTIVE")), [["inactive_without_close_date"]])

    def test_close_before_open(self):
        self.assertEqual(self.reasons(row("A99001", status="INACTIVE", opened="20200101", closed="20190101")),
                         [["closed_before_opened"]])

    def test_impossible_date(self):
        self.assertIn("invalid_open_date", self.reasons(row("A99001", opened="20250231"))[0])

    def test_unknown_status(self):
        self.assertEqual(self.reasons(row("A99001", status="SUSPENDED")), [["unknown_status"]])

    def test_short_row(self):
        self.assertEqual(self.reasons(row("A99001", width=20)), [["expected_27_columns_got_20"]])

    def test_missing_postcode(self):
        self.assertEqual(self.reasons(row("A99001", postcode="")), [["missing_postcode"]])

    def test_wrong_file_is_refused(self):
        with self.assertRaises(ValueError):
            parse(file_of(row("Y99001", role="RO247")))


class UkCoreMappingTests(unittest.TestCase):
    def setUp(self):
        self.result = parse(file_of(row("A99001"), row("A99002", status="DORMANT"),
                                    row("A99003", status="INACTIVE", closed="20240630")))

    def test_profile_identifier_and_type(self):
        org = to_organization(self.result.practices[0])
        self.assertEqual(org["meta"]["profile"], [UK_CORE_ORGANIZATION])
        self.assertEqual(org["identifier"][0], {"system": "https://fhir.nhs.uk/Id/ods-organization-code", "value": "A99001"})
        self.assertEqual(org["type"][0]["coding"][0]["code"], "prov")

    def test_active_is_boolean_for_every_status(self):
        self.assertEqual([to_organization(p)["active"] for p in self.result.practices], [True, False, False])

    def test_operational_period_extension(self):
        closed = to_organization(self.result.practices[2])
        self.assertEqual(closed["extension"][0]["valuePeriod"], {"start": "2010-04-01", "end": "2024-06-30"})

    def test_bundle_fullurls_match_resource_ids(self):
        bundle = to_bundle(self.result.practices)
        for entry in bundle["entry"]:
            self.assertTrue(entry["fullUrl"].endswith(f"/Organization/{entry['resource']['id']}"))


class CommittedSnapshotTests(unittest.TestCase):
    """Regression tests on the real ODS file retrieved on 2026-11-07."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "data/ods/MANIFEST.json").read_text())["files"][0]
        cls.raw = (ROOT / cls.manifest["path"]).read_bytes()
        cls.summary = summarise(parse(cls.raw), date(2026, 11, 7))

    def test_file_matches_manifest(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), self.manifest["sha256"])
        self.assertEqual(len(self.raw), self.manifest["bytes"])

    def test_known_counts(self):
        self.assertEqual(self.summary["source_rows"], 15692)
        self.assertEqual(self.summary["gp_practice_records"], 8193)
        self.assertEqual(self.summary["by_status"], {"ACTIVE": 6560, "DORMANT": 60, "INACTIVE": 1573})
        self.assertEqual(self.summary["current_gp_practices_england"], 6162)
        self.assertEqual(self.summary["gp_practice_records_rejected"], 0)

    def test_regions_add_up(self):
        self.assertEqual(sum(self.summary["current_gp_practices_england_by_region"].values()),
                         self.summary["current_gp_practices_england"])

    def test_end_to_end_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            run(self.raw, out, {"files": [self.manifest]}, date(2026, 11, 7), out / "bundle.json")
            bundle = json.loads((out / "bundle.json").read_text())
            self.assertEqual(len(bundle["entry"]), 6162)
            self.assertTrue(all(e["resource"]["active"] for e in bundle["entry"]))
            self.assertIn("6,162", (out / "index.html").read_text())


if __name__ == "__main__":
    unittest.main()
