#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-job-tracker-app:local}"

printf 'Building %s...\n' "${IMAGE_NAME}"
docker build -t "${IMAGE_NAME}" .

printf 'Verifying linkedin_lookup module exists inside the image...\n'
docker run --rm "${IMAGE_NAME}" python -c "import linkedin_lookup.main; print('linkedin_lookup import OK')"

printf 'Removing old k3s image tag if present...\n'
sudo k3s ctr images rm "docker.io/library/${IMAGE_NAME}" >/dev/null 2>&1 || true
sudo k3s ctr images rm "${IMAGE_NAME}" >/dev/null 2>&1 || true
sudo k3s ctr -n k8s.io images rm "docker.io/library/${IMAGE_NAME}" >/dev/null 2>&1 || true
sudo k3s ctr -n k8s.io images rm "${IMAGE_NAME}" >/dev/null 2>&1 || true

printf 'Importing %s into k3s...\n' "${IMAGE_NAME}"
docker save "${IMAGE_NAME}" | sudo k3s ctr images import -

printf 'Imported %s into k3s.\n' "${IMAGE_NAME}"
