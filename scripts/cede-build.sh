#!/usr/bin/env bash
# Build a CEDE application inside its Docker toolchain container.
#
# Reads cede_app.yaml from the app directory to determine the target type,
# then runs the appropriate containerized build (pico-dev or arduino-dev).
#
# Usage:
#   cede-build.sh /path/to/app
#   cede-build.sh .                    (build the app in the current directory)
#   CEDE_IMAGE_ID=abc123 cede-build.sh /path/to/app
#
# The app directory must be inside the cede-labgrid workspace (Docker mount).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"

APP_DIR="${1:-.}"
APP_DIR="$(cd "${APP_DIR}" && pwd -P)"

MANIFEST="${APP_DIR}/cede_app.yaml"
if [[ ! -f "${MANIFEST}" ]]; then
  echo "error: no cede_app.yaml found in ${APP_DIR}" >&2
  exit 1
fi

yaml_field() {
  grep -E "^${1}:" "${MANIFEST}" 2>/dev/null | head -1 | sed "s/^${1}:[[:space:]]*//" | tr -d '"'"'" || true
}

TARGET="$(yaml_field target)"
if [[ -z "${TARGET}" ]]; then
  echo "error: cede_app.yaml missing 'target:' field" >&2
  exit 1
fi

# App path relative to workspace root (Docker mounts /workspace at REPO_ROOT).
REL_APP="${APP_DIR#"${REPO_ROOT}/"}"
if [[ "${REL_APP}" == "${APP_DIR}" ]]; then
  echo "error: app directory must be inside the cede-labgrid workspace (${REPO_ROOT})" >&2
  exit 1
fi

APP_NAME="$(basename "${APP_DIR}")"
COMPOSE="docker compose -f ${REPO_ROOT}/lab/docker/docker-compose.yml"
CEDE_IMAGE_ID="${CEDE_IMAGE_ID:-}"
ID_FLAG=""
if [[ -n "${CEDE_IMAGE_ID}" ]]; then
  ID_FLAG="-e CEDE_IMAGE_ID=${CEDE_IMAGE_ID}"
fi

case "${TARGET}" in
  pico)
    PICO_BOARD="${PICO_BOARD:-pico}"
    echo "==> build Pico firmware: ${REL_APP} (board=${PICO_BOARD})" >&2
    # shellcheck disable=SC2086
    ${COMPOSE} run --rm ${ID_FLAG} pico-dev bash -lc "
      set -e
      cd /workspace/${REL_APP}
      rm -rf build && mkdir build && cd build
      cmake -GNinja -DCMAKE_BUILD_TYPE=Release -DPICO_BOARD=${PICO_BOARD} ..
      ninja
      grep -oP '(?<=CEDE_IMAGE_ID \")[A-Za-z0-9._-]+' cede_build_id.h > ${APP_NAME}.uf2.digest
    "
    echo "==> built: ${REL_APP}/build/${APP_NAME}.uf2" >&2
    ;;

  uno)
    echo "==> build Uno firmware: ${REL_APP}" >&2
    # shellcheck disable=SC2086
    ${COMPOSE} run --rm ${ID_FLAG} arduino-dev bash -lc "
      set -e
      cd /workspace/${REL_APP}
      bash tools/gen_cede_image_id.sh
      mkdir -p build
      arduino-cli compile --fqbn arduino:avr:uno --output-dir build .
      grep -oP '(?<=CEDE_IMAGE_ID \")[A-Za-z0-9._-]+' cede_build_id.h > build/${APP_NAME}.ino.hex.digest
    "
    echo "==> built: ${REL_APP}/build/${APP_NAME}.ino.hex" >&2
    ;;

  pi)
    echo "==> Pi apps don't require a container build step" >&2
    echo "    use: make deploy  (syncs to gateway via cede-deploy.sh)" >&2
    ;;

  *)
    echo "error: unknown target '${TARGET}' in cede_app.yaml" >&2
    exit 1
    ;;
esac
