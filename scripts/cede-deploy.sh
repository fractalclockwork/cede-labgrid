#!/usr/bin/env bash
# Deploy a CEDE application to its target.
#
# Reads cede_app.yaml from the app directory to determine the target type
# and gateway, then syncs/flashes the app.
#
# Usage:
#   cede-deploy.sh /path/to/app [--run] [--run-target bench]
#   cede-deploy.sh /path/to/app --gateway pi@other-pi.local --run
#
# Options:
#   --gateway HOST    SSH target (overrides cede_app.yaml gateway field)
#   --remote-root DIR Remote base directory for Pi apps (default: ~/cede/apps)
#   --run             After syncing, run `make run` on the target
#   --run-target T    Make target to run instead of `run` (implies --run)
#   --extra-args ARGS Extra arguments forwarded to the app's make target
#   --sync-only       Sync files only, do not run (default when --run is omitted)
#   --flash-only      Flash MCU firmware without serial validation
#
# The gateway is resolved in order: --gateway flag > cede_app.yaml gateway field > GATEWAY env var.
# MCU targets (pico/uno) use LabGrid for flashing. Requires coordinator + exporter.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"

usage() {
  sed -n '1,21p' "$0"
  exit "${1:-0}"
}

APP_DIR=""
GATEWAY_CLI=""
REMOTE_ROOT='~/cede/apps'
DO_RUN=0
RUN_TARGET="run"
EXTRA_ARGS=""
FLASH_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gateway)      GATEWAY_CLI="${2:?--gateway requires a value}"; shift 2 ;;
    --remote-root)  REMOTE_ROOT="${2:?--remote-root requires a value}"; shift 2 ;;
    --run)          DO_RUN=1; shift ;;
    --run-target)   RUN_TARGET="${2:?--run-target requires a value}"; DO_RUN=1; shift 2 ;;
    --extra-args)   EXTRA_ARGS="${2:-}"; shift 2 ;;
    --sync-only)    DO_RUN=0; shift ;;
    --flash-only)   FLASH_ONLY=1; shift ;;
    -h|--help)      usage 0 ;;
    -*)             echo "error: unknown option: $1" >&2; usage 1 ;;
    *)
      if [[ -z "${APP_DIR}" ]]; then
        APP_DIR="$1"; shift
      else
        echo "error: unexpected argument: $1" >&2; usage 1
      fi
      ;;
  esac
done

if [[ -z "${APP_DIR}" ]]; then
  echo "error: app directory required" >&2
  usage 1
fi

APP_DIR="$(cd "${APP_DIR}" && pwd -P)"

MANIFEST="${APP_DIR}/cede_app.yaml"
if [[ ! -f "${MANIFEST}" ]]; then
  echo "error: no cede_app.yaml found in ${APP_DIR}" >&2
  exit 1
fi

# Parse fields from cede_app.yaml (lightweight — no Python dependency).
yaml_field() {
  grep -E "^${1}:" "${MANIFEST}" 2>/dev/null | head -1 | sed "s/^${1}:[[:space:]]*//" | tr -d '"'"'" || true
}

TARGET="$(yaml_field target)"
APP_ID="$(yaml_field application_id)"
YAML_GATEWAY="$(yaml_field gateway)"
ENTRYPOINT="$(yaml_field entrypoint)"
BANNER_PREFIX="$(grep -E '^\s+banner_prefix:' "${MANIFEST}" 2>/dev/null | head -1 | sed 's/.*banner_prefix:[[:space:]]*//' | tr -d '"'"'" || true)"

if [[ -z "${TARGET}" ]]; then
  echo "error: cede_app.yaml missing 'target:' field" >&2
  exit 1
fi
if [[ -z "${APP_ID}" ]]; then
  APP_ID="$(basename "${APP_DIR}")"
fi

# Resolve gateway: CLI flag > yaml > env var.
resolve_gateway() {
  if [[ -n "${GATEWAY_CLI}" ]]; then
    echo "${GATEWAY_CLI}"
  elif [[ -n "${YAML_GATEWAY}" ]]; then
    echo "${YAML_GATEWAY}"
  elif [[ -n "${GATEWAY:-}" ]]; then
    echo "${GATEWAY}"
  else
    echo ""
  fi
}

case "${TARGET}" in
  pi)
    GW="$(resolve_gateway)"
    if [[ -z "${GW}" ]]; then
      echo "error: no gateway specified. Set 'gateway:' in cede_app.yaml, pass --gateway, or set GATEWAY env var." >&2
      exit 1
    fi

    REMOTE_APP="${REMOTE_ROOT}/${APP_ID}"
    echo "==> sync ${APP_DIR} -> ${GW}:${REMOTE_APP}/" >&2
    # shellcheck disable=SC2029
    ssh "${GW}" "mkdir -p ${REMOTE_APP}"
    rsync -az "${APP_DIR}/" "${GW}:${REMOTE_APP}/" \
      --exclude .venv --exclude __pycache__ --exclude '*.pyc'

    if [[ "${DO_RUN}" -eq 1 ]]; then
      echo "==> ${GW}: make -C ${REMOTE_APP} ${RUN_TARGET} (Ctrl+C stops)" >&2
      # shellcheck disable=SC2086
      ssh -t "${GW}" "make -C ${REMOTE_APP} ${RUN_TARGET} EXTRA_ARGS='${EXTRA_ARGS}'"
    else
      echo "==> synced to ${GW}:${REMOTE_APP}" >&2
    fi
    ;;

  pico)
    # Resolve the UF2 artifact from entrypoint field (e.g. build/*.uf2)
    ARTIFACT="$(cd "${APP_DIR}" && ls -1 ${ENTRYPOINT} 2>/dev/null | head -1)"
    if [[ -z "${ARTIFACT}" ]]; then
      echo "error: no artifact matching '${ENTRYPOINT}' found in ${APP_DIR}" >&2
      echo "hint: build the firmware first (make build, or make -C lab/docker pico-build)" >&2
      exit 1
    fi
    ARTIFACT_PATH="${APP_DIR}/${ARTIFACT}"

    echo "==> flash Pico via LabGrid: ${ARTIFACT_PATH}" >&2

    LG_ENV="${REPO_ROOT}/env/pico.yaml"
    LG_COORDINATOR="${LG_COORDINATOR:-192.168.1.111:20408}"

    # Acquire the place
    "${REPO_ROOT}/.venv/bin/labgrid-client" -x "${LG_COORDINATOR}" -p cede-pico acquire 2>/dev/null || true

    VALIDATE_FLAG=""
    if [[ "${FLASH_ONLY}" -eq 0 ]]; then
      VALIDATE_FLAG="--validate"
    fi

    DEPLOY_ARGS=(--env "${LG_ENV}" --coordinator "${LG_COORDINATOR}" --image "${ARTIFACT_PATH}")
    if [[ "${FLASH_ONLY}" -eq 0 ]]; then
      DEPLOY_ARGS+=(--validate)
    fi
    if [[ -n "${BANNER_PREFIX}" ]]; then
      DEPLOY_ARGS+=(--banner-prefix "${BANNER_PREFIX}")
    fi

    "${REPO_ROOT}/.venv/bin/python" -m cede_labgrid.cli.deploy "${DEPLOY_ARGS[@]}"
    ;;

  uno)
    ARTIFACT="$(cd "${APP_DIR}" && ls -1 ${ENTRYPOINT} 2>/dev/null | head -1)"
    if [[ -z "${ARTIFACT}" ]]; then
      echo "error: no artifact matching '${ENTRYPOINT}' found in ${APP_DIR}" >&2
      echo "hint: build the firmware first (make build, or make -C lab/docker uno-build)" >&2
      exit 1
    fi
    ARTIFACT_PATH="${APP_DIR}/${ARTIFACT}"

    echo "==> flash Uno via LabGrid: ${ARTIFACT_PATH}" >&2

    LG_ENV="${REPO_ROOT}/env/uno.yaml"
    LG_COORDINATOR="${LG_COORDINATOR:-192.168.1.111:20408}"

    "${REPO_ROOT}/.venv/bin/labgrid-client" -x "${LG_COORDINATOR}" -p cede-uno acquire 2>/dev/null || true

    DEPLOY_ARGS=(--env "${LG_ENV}" --coordinator "${LG_COORDINATOR}" --image "${ARTIFACT_PATH}")
    if [[ "${FLASH_ONLY}" -eq 0 ]]; then
      DEPLOY_ARGS+=(--validate)
    fi
    if [[ -n "${BANNER_PREFIX}" ]]; then
      DEPLOY_ARGS+=(--banner-prefix "${BANNER_PREFIX}")
    fi

    "${REPO_ROOT}/.venv/bin/python" -m cede_labgrid.cli.deploy "${DEPLOY_ARGS[@]}"
    ;;

  *)
    echo "error: unknown target '${TARGET}' in cede_app.yaml" >&2
    exit 1
    ;;
esac
