"""Condense HL7 validator OperationOutcome output into small committed summaries.

Exit status is non-zero when:

* a validator output file is missing, or does not cover all three expected
  inputs (so CI cannot pass just because the validator never ran), or
* the synthetic Bundle or the ODS Bundle has any error or fatal issue.

The deliberately invalid fixture is expected to have errors; it is reported,
and it must have at least one error, but it does not fail the build.
"""
from collections import Counter
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent / "results"
ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ("synthetic_r4.json", "ods_uk_core.json")
EXPECTED_INPUTS = ("synthetic_bundle.json", "invalid_bundle.json", "ods_organizations_bundle.json")


def outcomes(path: Path) -> list[tuple[str, list[dict]]]:
    data = json.loads(path.read_text())
    resources = [e["resource"] for e in data.get("entry", [])] or [data]
    found = []
    for outcome in resources:
        source = next((x.get("valueString") for x in outcome.get("extension", []) if "file" in x.get("url", "")), "?")
        found.append((source, outcome.get("issue", [])))
    return found


def summary(issues: list[dict]) -> dict:
    by_severity = Counter(i["severity"] for i in issues)
    messages = Counter((i["severity"], i.get("details", {}).get("text", "")[:200]) for i in issues
                       if i["severity"] in ("fatal", "error", "warning"))
    return {"by_severity": {k: by_severity.get(k, 0) for k in ("fatal", "error", "warning", "information")},
            "top_messages": [{"severity": s, "count": n, "message": m} for (s, m), n in messages.most_common(8)]}


def main(results: Path = HERE, bundle: Path = ROOT / "build" / "ods_organizations_bundle.json") -> int:
    problems = [f"missing validator output {name}" for name in OUTPUTS if not (results / name).exists()]
    report = {}
    for name in OUTPUTS:
        if (results / name).exists():
            for source, issues in outcomes(results / name):
                report[Path(source).name] = summary(issues)
    problems += [f"validator produced no result for {name}" for name in EXPECTED_INPUTS if name not in report]

    for name, result in report.items():
        errors = result["by_severity"]["fatal"] + result["by_severity"]["error"]
        if name == "invalid_bundle.json":
            if errors == 0:
                problems.append("the invalid fixture produced no errors; the validator may not be checking anything")
        elif errors:
            problems.append(f"{name}: {errors} error(s)")

    (results / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    if "ods_organizations_bundle.json" in report and bundle.exists():
        resources = len(json.loads(bundle.read_text())["entry"])
        (results / "ods_uk_core_summary.json").write_text(json.dumps({
            "resources": resources,
            "validator": "validator_cli.jar",
            "profile": "https://fhir.hl7.org.uk/StructureDefinition/UKCore-Organization",
            "package": "fhir.r4.ukcore.stu2#2.0.2",
            "by_severity": report["ods_organizations_bundle.json"]["by_severity"],
            "note": "Run without a terminology server (-tx n/a), so code-system membership is not checked. "
                    "Warnings are listed in conformance/results/summary.json.",
        }, indent=2) + "\n")
    print(json.dumps({k: v["by_severity"] for k, v in report.items()}, indent=2))
    for problem in problems:
        print(f"CONFORMANCE FAILURE: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
