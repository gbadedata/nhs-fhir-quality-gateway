"""CLI: python -m fhir_gateway run --output build"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .generate import make_bundle, write_bundle
from .pipeline import ingest
from .quality import summarise, write_metrics
from .report import render


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic FHIR-style quality gateway")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--patients", type=int, default=90)
    parser.add_argument("--seed", type=int, default=41)
    parser.add_argument("--input", type=Path, help="Optional synthetic Bundle JSON")
    parser.add_argument("--output", type=Path, default=Path("build"))
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    source = args.input or out / "synthetic_bundle.json"
    if args.input is None:
        write_bundle(make_bundle(args.patients, args.seed), source)
    audit = ingest(source, out / "fhir_quality.sqlite", out / "quarantine.json")
    metrics = summarise(out / "fhir_quality.sqlite", out / "quarantine.json")
    write_metrics(metrics, out / "quality.json")
    render(metrics, out / "index.html")
    print(json.dumps({"audit": audit, "report": str(out / "index.html")}, indent=2))


if __name__ == "__main__":
    main()
