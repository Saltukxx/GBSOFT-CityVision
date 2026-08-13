#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CVAT_DIR="${ROOT}/tools/cvat"

if [[ ! -d "${CVAT_DIR}" ]]; then
  echo "CVAT yok. Kurulum için: bash scripts/cvat_install.sh"
  exit 1
fi

export CVAT_HOST="${CVAT_HOST:-localhost}"
cd "${CVAT_DIR}"
docker compose up -d
echo "CVAT → http://${CVAT_HOST}:8080"
echo "Admin yoksa:"
echo "  docker exec -it cvat_server bash -ic 'python3 ~/manage.py createsuperuser'"
