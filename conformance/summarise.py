"""Condense HL7 validator OperationOutcome output into small committed summaries.

Exit status is non-zero if the synthetic Bundle or the ODS Bundle has any error,
so CI fails when conformance regresses. The deliberately invalid fixture is
expected to have errors and is reported, not enforced.
"""
from collections import Counter
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent / "results"


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


def main() -> int:
    failures = 0
    report = {}
    for name in ("synthetic_r4.json", "ods_uk_core.json"):
        path = HERE / name
        if not path.exists():
            continue
        for source, issues in outcomes(path):
            key = Path(source).name
            report[key] = summary(issues)
            errors = report[key]["by_severity"]["fatal"] + report[key]["by_severity"]["error"]
            if errors and "invalid" not in key:
                failures += 1
    (HERE / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    if "ods_organizations_bundle.json" in report:
        bundle = json.loads((Path(__file__).resolve().parents[1] / "build" / "ods_organizations_bundle.json").read_text())
        (HERE / "ods_uk_core_summary.json").write_text(json.dumps({
            "resources": len(bundle["entry"]),
            "validator": "validator_cli.jar",
            "profile": "https://fhir.hl7.org.uk/StructureDefinition/UKCore-Organization",
            "package": "fhir.r4.ukcore.stu2#2.0.2",
            "by_severity": report["ods_organizations_bundle.json"]["by_severity"],
            "note": "Run without a terminology server (-tx n/a), so code-system membership is not checked. "
                    "Warnings are listed in conformance/results/summary.json.",
        }, indent=2) + "\n")
    print(json.dumps({k: v["by_severity"] for k, v in report.items()}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
