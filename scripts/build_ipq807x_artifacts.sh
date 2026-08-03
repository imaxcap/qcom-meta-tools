#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${1:-${ROOT_DIR}/dist/ipq807x}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
GENERATED_MACHID_DIR="${ROOT_DIR}/ipq807x/machid_xml"

cleanup() {
    rm -rf "${GENERATED_MACHID_DIR}"
}
trap cleanup EXIT

rm -rf "${OUTPUT_DIR}" "${GENERATED_MACHID_DIR}"
mkdir -p "${OUTPUT_DIR}/mibib" "${OUTPUT_DIR}/cdt"

cd "${ROOT_DIR}"

"${PYTHON_BIN}" prepareSingleImage.py \
    --arch ipq807x \
    --fltype nor,nand,norplusnand,emmc,norplusemmc \
    --genpart \
    --in "${OUTPUT_DIR}/mibib"

"${PYTHON_BIN}" prepareSingleImage.py \
    --arch ipq807x \
    --gencdt \
    --in "${OUTPUT_DIR}/cdt"

"${PYTHON_BIN}" - "${OUTPUT_DIR}" <<'PY'
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

output_dir = Path(sys.argv[1])
config = ET.parse("ipq807x/config.xml").getroot()

expected_cdt = {
    f"cdt-{entry.findtext('board')}_{entry.findtext('memory')}.bin"
    for entry in config.findall("./data[@type='MACH_ID_BOARD_MAP']/entry")
}
actual_cdt = {path.name for path in (output_dir / "cdt").glob("cdt-*.bin")}

missing_cdt = sorted(expected_cdt - actual_cdt)
unexpected_cdt = sorted(actual_cdt - expected_cdt)
if missing_cdt or unexpected_cdt:
    raise SystemExit(
        f"CDT output mismatch: missing={missing_cdt}, unexpected={unexpected_cdt}"
    )

required_mibib = {
    "nor-system-partition-ipq807x.bin",
    "nand-system-partition-ipq807x.bin",
    "nand-system-partition-ipq807x-m4096-p256KiB.bin",
    "nand-system-partition-ipq807x-qcn9000.bin",
    "norplusnand-system-partition-ipq807x.bin",
    "norplusnand-system-partition-ipq807x-m4096-p256KiB.bin",
    "norplusnand-system-partition-ipq807x-qcn9000.bin",
    "gpt_main0.bin",
    "gpt_backup0.bin",
    "gpt_main1.bin",
    "gpt_backup1.bin",
    "norplusemmc-system-partition-ipq807x.bin",
}
actual_mibib = {path.name for path in (output_dir / "mibib").iterdir() if path.is_file()}
missing_mibib = sorted(required_mibib - actual_mibib)
if missing_mibib:
    raise SystemExit(f"Missing MIBIB outputs: {missing_mibib}")

empty_files = sorted(
    str(path.relative_to(output_dir))
    for path in output_dir.rglob("*")
    if path.is_file() and path.stat().st_size == 0
)
if empty_files:
    raise SystemExit(f"Empty output files: {empty_files}")

print(f"Validated {len(actual_cdt)} CDT files and {len(actual_mibib)} MIBIB files")
PY

(
    cd "${OUTPUT_DIR}"
    find cdt mibib -type f -print0 \
        | sort -z \
        | xargs -0 sha256sum > SHA256SUMS
)

printf 'IPQ807x artifacts generated in %s\n' "${OUTPUT_DIR}"
