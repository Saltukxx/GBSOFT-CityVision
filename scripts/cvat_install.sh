#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CVAT_DIR="${ROOT}/tools/cvat"

mkdir -p "${ROOT}/tools"
if [[ ! -d "${CVAT_DIR}/.git" ]]; then
  git clone --depth 1 https://github.com/cvat-ai/cvat.git "${CVAT_DIR}"
fi

export CVAT_HOST="${CVAT_HOST:-localhost}"
cd "${CVAT_DIR}"
docker compose pull
docker compose up -d

echo
echo "CVAT ayakta → http://${CVAT_HOST}:8080"
echo "Admin kullanıcı oluştur:"
echo "  docker exec -it cvat_server bash -ic 'python3 ~/manage.py createsuperuser'"
echo
echo "Sonra: docs/cvat-setup.md"
