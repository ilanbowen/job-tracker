#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-job-tracker-app:local}"

docker build -t "${IMAGE_NAME}" .
docker save "${IMAGE_NAME}" | sudo k3s ctr images import -

echo "Imported ${IMAGE_NAME} into k3s."
