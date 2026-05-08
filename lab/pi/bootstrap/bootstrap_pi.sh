#!/usr/bin/env bash
# CEDE Raspberry Pi gateway bootstrap (idempotent). Target: Raspberry Pi OS Lite
# (Bookworm or later), e.g. Raspberry Pi 3 Model B / B+ with 64-bit OS recommended.
#
# Usage:
#   sudo ./bootstrap_pi.sh --hostname cede-gateway
#   sudo CEDE_HOSTNAME=cede-gateway ./bootstrap_pi.sh
#
# Optional env:
#   CEDE_GATEWAY_USER — non-root user to add to docker,dialout,i2c,disk (default: first sudo user or $SUDO_USER)

set -euo pipefail

HOSTNAME="${CEDE_HOSTNAME:-}"
SKIP_DOCKER=0
SKIP_APT_UPGRADE=0

die() {
  echo "error: $*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hostname)
      HOSTNAME="${2:-}"
      shift 2
      ;;
    --skip-docker)
      SKIP_DOCKER=1
      shift
      ;;
    --skip-apt-upgrade)
      SKIP_APT_UPGRADE=1
      shift
      ;;
    -h|--help)
      sed -n '1,20p' "$0"
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

[[ "$(id -u)" -eq 0 ]] || die "run as root (sudo)"

if [[ -z "${HOSTNAME}" ]]; then
  die "set --hostname or CEDE_HOSTNAME"
fi

GATEWAY_USER="${CEDE_GATEWAY_USER:-}"
if [[ -z "${GATEWAY_USER}" ]]; then
  if [[ -n "${SUDO_USER:-}" ]]; then
    GATEWAY_USER="${SUDO_USER}"
  else
    GATEWAY_USER="$(logname 2>/dev/null || true)"
  fi
fi

export DEBIAN_FRONTEND=noninteractive

echo "==> Setting hostname to ${HOSTNAME}"
hostnamectl set-hostname "${HOSTNAME}"
if grep -q "127.0.1.1" /etc/hosts; then
  sed -i "s/^127.0.1.1.*/127.0.1.1\t${HOSTNAME}/" /etc/hosts
else
  printf '127.0.1.1\t%s\n' "${HOSTNAME}" >> /etc/hosts
fi

echo "==> APT update"
apt-get update

if [[ "${SKIP_APT_UPGRADE}" -eq 0 ]]; then
  echo "==> APT upgrade (noninteractive)"
  apt-get upgrade -y -o Dpkg::Options::="--force-confold"
fi

echo "==> Installing gateway packages"
apt-get install -y --no-install-recommends \
  openssh-server \
  git \
  ca-certificates \
  curl \
  rsync \
  python3 \
  python3-serial \
  python3-venv \
  python3-pip \
  picotool \
  avrdude \
  i2c-tools \
  libusb-1.0-0 \
  udev \
  usbutils

echo "==> Enabling I2C (for Hello Lab Test 7 / Linux i2c-tools)"
if command -v raspi-config >/dev/null 2>&1; then
  raspi-config nonint do_i2c 0
else
  echo "raspi-config not found; enable I2C manually if needed (boot config / overlay)."
fi

if [[ "${SKIP_DOCKER}" -eq 0 ]]; then
  echo "==> Installing Docker (Engine + Compose plugin)"
  if ! command -v docker >/dev/null 2>&1; then
    apt-get install -y --no-install-recommends docker.io docker-compose-plugin
    systemctl enable --now docker
  fi
else
  echo "==> Skipping Docker (--skip-docker)"
fi

if [[ -n "${GATEWAY_USER}" ]] && id "${GATEWAY_USER}" >/dev/null 2>&1; then
  echo "==> Groups for ${GATEWAY_USER}: dialout, plugdev, i2c, gpio, docker, disk"
  usermod -aG dialout,plugdev,i2c,gpio "${GATEWAY_USER}" 2>/dev/null || true
  # gpio group may not exist on all images
  getent group gpio >/dev/null && usermod -aG gpio "${GATEWAY_USER}" || true
  if getent group disk >/dev/null; then
    usermod -aG disk "${GATEWAY_USER}"
  fi
  if [[ "${SKIP_DOCKER}" -eq 0 ]] && getent group docker >/dev/null; then
    usermod -aG docker "${GATEWAY_USER}"
  fi
fi

echo "==> Arduino CLI (user-local install)"
SH_USER_HOME=""
if [[ -n "${GATEWAY_USER}" ]] && [[ "${GATEWAY_USER}" != "root" ]] && id "${GATEWAY_USER}" >/dev/null 2>&1; then
  SH_USER_HOME="$(getent passwd "${GATEWAY_USER}" | cut -d: -f6)"
fi
if [[ -n "${SH_USER_HOME}" ]] && [[ -d "${SH_USER_HOME}" ]]; then
  sudo -u "${GATEWAY_USER}" -H bash -c '
    set -e
    mkdir -p "${HOME}/.local/bin"
    if ! command -v arduino-cli >/dev/null 2>&1; then
      curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh \
        | BINDIR="${HOME}/.local/bin" sh
    fi
    export PATH="${HOME}/.local/bin:${PATH}"
    arduino-cli config init || true
    arduino-cli core update-index
    arduino-cli core install arduino:avr
  '
fi

echo "==> Python tools for orchestration/tests (system pip --user)"
pip_install() {
  python3 -m pip install --upgrade pip setuptools wheel
  python3 -m pip install --break-system-packages pyserial pyyaml jsonschema pytest smbus2 2>/dev/null \
    || python3 -m pip install pyserial pyyaml jsonschema pytest smbus2
}
pip_install

UDEV_RULES="/etc/udev/rules.d/99-cede-serial.rules"
if [[ ! -f "${UDEV_RULES}" ]]; then
  echo "==> Installing stub udev rules (${UDEV_RULES})"
  cat <<'EOF' >"${UDEV_RULES}"
# CEDE: optional tighten rules per bench (VID:PID). Defaults rely on /dev/serial/by-id/.
# SUBSYSTEM=="tty", ATTRS{idVendor}=="2e8a", MODE="0660", GROUP="dialout"
EOF
  udevadm control --reload-rules || true
  udevadm trigger || true
fi

echo ""
echo "Bootstrap finished."
echo " - Hostname: ${HOSTNAME}"
echo " - Re-login (or reboot) for group membership (docker, dialout, disk)."
echo " - Do not git clone the full CEDE repo on the gateway—Dev-Host builds firmware and rsyncs flash deps (sync_gateway_flash_deps.sh)."
echo " - Dev-Host: build ARM64 gateway images: make -C lab/docker build-gateway-images"
echo " - Optional HDMI kiosk dashboard: see lab/pi/docs/dashboard-hdmi.md"
