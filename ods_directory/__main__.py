"""CLI: audit the NHS ODS GP practice file and build UK Core Organization resources.

    python -m ods_directory                      # committed snapshot in data/ods/
    python -m ods_directory --download           # fetch today's file from ODS (needs internet)
    python -m ods_directory --input epraccur.csv --retrieved 2026-11-07
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
import urllib.request

from .epraccur import parse, summarise
from .fhir import to_bundle
from .report import render

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "ods" / "MANIFEST.json"
SOURCE_URL = "https://www.odsdatasearchandexport.nhs.uk/api/getReport?report=epraccur"
MAX_BYTES = 25_000_000


def fetch(url: str = SOURCE_URL, timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "nhs-fhir-quality-gateway/0.2", "Accept": "text/csv"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES:
        raise ValueError("ODS response was empty or unexpectedly large")
    return data


def write_sqlite(practices, path: Path, digest: str) -> None:
    path.unlink(missing_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE gp_practice (code TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL, nation TEXT NOT NULL,
              nhs_region_code TEXT, icb_code TEXT, commissioner_code TEXT, town TEXT, postcode TEXT NOT NULL,
              open_date TEXT NOT NULL, close_date TEXT, CHECK (close_date IS NULL OR close_date >= open_date));
            CREATE TABLE source_audit (sha256 TEXT NOT NULL, gp_practice_rows INTEGER NOT NULL);""")
        db.executemany("INSERT INTO gp_practice VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
            (p.code, p.name, p.status, p.nation, p.nhs_region_code, p.icb_code, p.commissioner_code, p.town,
             p.postcode, p.open_date.isoformat(), p.close_date.isoformat() if p.close_date else None) for p in practices])
        db.execute("INSERT INTO source_audit VALUES (?,?)", (digest, len(practices)))


def run(raw: bytes, output: Path, manifest: dict, retrieved: date, bundle_path: Path | None = None) -> dict:
    digest = hashlib.sha256(raw).hexdigest()
    result = parse(raw)
    summary = summarise(result, retrieved)
    summary["source_sha256"] = digest
    current = [p for p in result.practices if p.is_current and p.nation == "England"]
    output.mkdir(parents=True, exist_ok=True)

    full_bundle = to_bundle(current)
    sample = {**full_bundle, "entry": full_bundle["entry"][:20]}
    (output / "sample_bundle.json").write_text(json.dumps(sample, indent=2) + "\n", encoding="utf-8")
    if bundle_path:
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        bundle_path.write_text(json.dumps(full_bundle) + "\n", encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "quarantine.json").write_text(json.dumps(result.rejected, indent=2) + "\n", encoding="utf-8")
    write_sqlite(result.practices, output / "ods_gp_practices.sqlite", digest)

    conformance_file = ROOT / "conformance" / "results" / "ods_uk_core_summary.json"
    conformance = json.loads(conformance_file.read_text()) if conformance_file.exists() else None
    render(summary, manifest, conformance, output / "index.html")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", type=Path, help="An epraccur CSV downloaded from ODS")
    source.add_argument("--download", action="store_true", help="Download the current file from ODS")
    parser.add_argument("--retrieved", type=date.fromisoformat, help="Retrieval date of --input (YYYY-MM-DD)")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "ods")
    parser.add_argument("--bundle", type=Path, default=ROOT / "build" / "ods_organizations_bundle.json",
                        help="Where to write the full Bundle of current practices (not committed)")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    entry = manifest["files"][0]
    if args.download:
        raw, retrieved = fetch(), date.today()
        entry = {**entry, "retrieved": retrieved.isoformat(), "bytes": len(raw),
                 "sha256": hashlib.sha256(raw).hexdigest(), "path": "(downloaded)"}
    elif args.input:
        raw = args.input.read_bytes()
        retrieved = args.retrieved or date.today()
        entry = {**entry, "retrieved": retrieved.isoformat(), "bytes": len(raw),
                 "sha256": hashlib.sha256(raw).hexdigest(), "path": str(args.input)}
    else:
        raw = (ROOT / entry["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise SystemExit("data/ods/epraccur.csv does not match the SHA-256 in MANIFEST.json")
        retrieved = date.fromisoformat(entry["retrieved"])
    summary = run(raw, args.output, {**manifest, "files": [entry]}, retrieved, args.bundle)
    print(f"{summary['current_gp_practices_england']:,} active GP practices in England "
          f"({summary['gp_practice_records']:,} GP practice records in file). Report: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
