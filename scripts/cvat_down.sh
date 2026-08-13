#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CVAT_DIR="${ROOT}/tools/cvat"
export CVAT_HOST="${CVAT_HOST:-localhost}"
cd "${CVAT_DIR}"
docker compose down
echo "CVAT stopped."
