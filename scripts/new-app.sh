#!/usr/bin/env bash
# Scaffold a new standalone application from CEDE templates.
#
# Usage:
#   scripts/new-app.sh --name my_sensor --target pico --output ~/src/my_sensor
#   scripts/new-app.sh --name my_display --target uno  --output ~/src/my_display --cede
#
# Options:
#   --name    NAME     Application name (required)
#   --target  TARGET   pico or uno (required)
#   --output  DIR      Destination directory (required; must not exist)
#   --cede             Also copy CEDE integration overlay (tests/, cede/, cede_app.yaml)
#   --no-git           Skip git init
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATES="${REPO_ROOT}/templates"

NAME=""
TARGET=""
OUTPUT=""
CEDE=false
GIT_INIT=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)   NAME="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --cede)   CEDE=true; shift ;;
    --no-git) GIT_INIT=false; shift ;;
    -h|--help)
      sed -n '2,/^set /p' "$0" | grep '^#' | sed 's/^# \?//'
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${NAME}" ]]; then
  echo "error: --name is required" >&2; exit 1
fi
if [[ -z "${TARGET}" ]]; then
  echo "error: --target is required (pico or uno)" >&2; exit 1
fi
if [[ -z "${OUTPUT}" ]]; then
  echo "error: --output is required" >&2; exit 1
fi

# Validate target.
case "${TARGET}" in
  pico|uno) ;;
  *) echo "error: --target must be 'pico' or 'uno', got '${TARGET}'" >&2; exit 1 ;;
esac

# Validate name (alphanumeric + underscore, must start with letter).
if [[ ! "${NAME}" =~ ^[a-zA-Z][a-zA-Z0-9_]*$ ]]; then
  echo "error: --name must be alphanumeric with underscores, starting with a letter" >&2
  exit 1
fi

# Resolve output path.
OUTPUT="$(cd "$(dirname "${OUTPUT}")" 2>/dev/null && pwd)/$(basename "${OUTPUT}")" || {
  echo "error: parent directory of ${OUTPUT} does not exist" >&2; exit 1
}

if [[ -e "${OUTPUT}" ]]; then
  echo "error: ${OUTPUT} already exists" >&2; exit 1
fi

TEMPLATE_DIR="${TEMPLATES}/${TARGET}-app"
if [[ ! -d "${TEMPLATE_DIR}" ]]; then
  echo "error: template directory not found: ${TEMPLATE_DIR}" >&2; exit 1
fi

echo "==> Creating ${TARGET} application '${NAME}' at ${OUTPUT}"

# Copy template.
cp -r "${TEMPLATE_DIR}" "${OUTPUT}"

# Rename the .ino file for Uno (arduino-cli requires sketch name = directory name).
if [[ "${TARGET}" == "uno" ]]; then
  mv "${OUTPUT}/APP_NAME.ino" "${OUTPUT}/${NAME}.ino"
fi

# Replace placeholders.
find "${OUTPUT}" -type f | while read -r f; do
  if file -b --mime-type "$f" | grep -q '^text/'; then
    sed -i "s/{{APP_NAME}}/${NAME}/g" "$f"
  fi
done

# Copy CEDE overlay if requested.
if [[ "${CEDE}" == true ]]; then
  OVERLAY_DIR="${TEMPLATES}/cede-overlay"
  if [[ ! -d "${OVERLAY_DIR}" ]]; then
    echo "warning: CEDE overlay not found at ${OVERLAY_DIR}, skipping" >&2
  else
    echo "==> Adding CEDE integration overlay"

    # Copy cede/ directory.
    cp -r "${OVERLAY_DIR}/cede" "${OUTPUT}/cede"
    chmod +x "${OUTPUT}/cede/gen_build_id.sh"

    # Copy tests/ directory.
    cp -r "${OVERLAY_DIR}/tests" "${OUTPUT}/tests"

    # Copy and rename test file.
    if [[ -f "${OUTPUT}/tests/test_APP_NAME.py" ]]; then
      mv "${OUTPUT}/tests/test_APP_NAME.py" "${OUTPUT}/tests/test_${NAME}.py"
    fi

    # Copy cede_app.yaml.
    cp "${OVERLAY_DIR}/cede_app.yaml" "${OUTPUT}/cede_app.yaml"

    # Replace placeholders in overlay files.
    find "${OUTPUT}/cede" "${OUTPUT}/tests" "${OUTPUT}/cede_app.yaml" -type f | while read -r f; do
      if file -b --mime-type "$f" | grep -q '^text/'; then
        sed -i "s/{{APP_NAME}}/${NAME}/g" "$f"
        sed -i "s/{{CEDE_TARGET}}/${TARGET}/g" "$f"
      fi
    done
  fi
fi

# Git init.
if [[ "${GIT_INIT}" == true ]]; then
  (cd "${OUTPUT}" && git init -q && git add -A && git commit -q -m "Initial scaffold from cede-labgrid templates/${TARGET}-app")
  echo "==> Initialized git repository"
fi

echo ""
echo "Done. Your ${TARGET} application is at: ${OUTPUT}"
echo ""
echo "Next steps:"
echo "  cd ${OUTPUT}"
if [[ "${TARGET}" == "pico" ]]; then
  echo "  export PICO_SDK_PATH=~/pico-sdk   # or use: make docker-build"
fi
echo "  make build"
if [[ "${CEDE}" == true ]]; then
  echo ""
  echo "CEDE integration is enabled. Additional targets:"
  echo "  make docker-build      # build in CEDE container"
  echo "  make gateway-flash     # flash via Pi gateway"
  echo "  make test              # run hardware tests"
fi
