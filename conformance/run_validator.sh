#!/usr/bin/env bash
# Layer 1 validation: run the official HL7 FHIR validator over this project's outputs.
#
#   conformance/run_validator.sh            # needs Java 17+ and internet for the first run
#
# Packages are pinned so results are reproducible. The validator downloads them
# from packages.fhir.org into ~/.fhir/packages on first use.
set -euo pipefail
cd "$(dirname "$0")/.."

VALIDATOR_VERSION="7.0.5"   # pinned so results are reproducible
JAR="${FHIR_VALIDATOR_JAR:-build/validator_cli-${VALIDATOR_VERSION}.jar}"
UK_CORE="fhir.r4.ukcore.stu2#2.0.2"
mkdir -p build conformance/results
if [ ! -f "$JAR" ]; then
  curl -sSL -o "$JAR" "https://github.com/hapifhir/org.hl7.fhir.core/releases/download/${VALIDATOR_VERSION}/validator_cli.jar"
fi

python -m fhir_gateway run --patients 90 --seed 41 --output build/synthetic >/dev/null
python -m ods_directory --output build/ods --bundle build/ods_organizations_bundle.json >/dev/null

# Synthetic clinical resources: base FHIR R4 (includes the R4 body temperature profile).
java -jar "$JAR" build/synthetic/synthetic_bundle.json fixtures/invalid_bundle.json \
  -version 4.0.1 -tx "${FHIR_TX:-n/a}" -output conformance/results/synthetic_r4.json >/dev/null || true

# Real ODS practices: every resource declares the UK Core Organization profile.
java -jar "$JAR" build/ods_organizations_bundle.json \
  -version 4.0.1 -ig "$UK_CORE" -tx "${FHIR_TX:-n/a}" -output conformance/results/ods_uk_core.json >/dev/null || true

python conformance/summarise.py
