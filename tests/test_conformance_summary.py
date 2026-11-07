"""The conformance step must fail loudly when the validator did not run."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from conformance.summarise import main


def outcome_bundle(*files):
    return {"resourceType": "Bundle", "entry": [{"resource": {
        "resourceType": "OperationOutcome",
        "extension": [{"url": "http://hl7.org/fhir/StructureDefinition/operationoutcome-file", "valueString": f"/x/{name}"}],
        "issue": [{"severity": severity, "details": {"text": "t"}} for severity in severities]}}
        for name, severities in files]}


class ConformanceSummaryTests(unittest.TestCase):
    def run_main(self, synthetic=None, ods=None):
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp)
            if synthetic is not None:
                (results / "synthetic_r4.json").write_text(json.dumps(synthetic))
            if ods is not None:
                (results / "ods_uk_core.json").write_text(json.dumps(ods))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return main(results, results / "no_bundle.json")

    def test_missing_outputs_fail(self):
        self.assertEqual(self.run_main(), 1)

    def test_clean_run_passes(self):
        synthetic = outcome_bundle(("synthetic_bundle.json", ["warning"]), ("invalid_bundle.json", ["error"]))
        ods = outcome_bundle(("ods_organizations_bundle.json", ["information"]))
        self.assertEqual(self.run_main(synthetic, ods), 0)

    def test_error_in_ods_bundle_fails(self):
        synthetic = outcome_bundle(("synthetic_bundle.json", []), ("invalid_bundle.json", ["error"]))
        ods = outcome_bundle(("ods_organizations_bundle.json", ["error"]))
        self.assertEqual(self.run_main(synthetic, ods), 1)

    def test_invalid_fixture_must_produce_errors(self):
        synthetic = outcome_bundle(("synthetic_bundle.json", []), ("invalid_bundle.json", []))
        ods = outcome_bundle(("ods_organizations_bundle.json", []))
        self.assertEqual(self.run_main(synthetic, ods), 1)


if __name__ == "__main__":
    unittest.main()
