# LabGrid Manual Flash How-To

End-to-end walkthrough: build firmware, flash Pico and Uno through LabGrid,
and verify the serial banner + digest attestation.

## Prerequisites

| Component | Where | How to start |
|---|---|---|
| labgrid-coordinator | Dev-Host | `.venv/bin/labgrid-coordinator -l 0.0.0.0:20408` |
| labgrid-exporter | Pi (`cede-pi`) | `~/labgrid/venv/bin/labgrid-exporter ~/labgrid/exporter.yaml -c <DEV_HOST_IP>:20408 --name cede-pi` |
| Docker images | Dev-Host | `make -C lab/docker build-images` (first time only) |

Set a shell alias to avoid repeating the coordinator address:

```bash
export LG_COORDINATOR=192.168.1.111:20408
alias lgc='.venv/bin/labgrid-client -x $LG_COORDINATOR'
```

## 1. Build Firmware (Docker)

Build both targets with a digest sidecar — the digest embeds in the USB
serial banner so we can verify the exact firmware version on-device.

```bash
# Use the current git rev as the firmware digest token
DIGEST=$(git rev-parse --short=12 HEAD)

make -C lab/docker pico-build uno-build CEDE_IMAGE_ID="$DIGEST"
```

Verify the artifacts:

```bash
$ cat lab/pico/hello_lab/build/hello_lab.uf2.digest
aec771d88ba3

$ cat lab/uno/hello_lab/build/hello_lab.ino.hex.digest
aec771d88ba3
```

## 2. Verify LabGrid Infrastructure

Check that the coordinator sees the exporter and both serial ports.

```bash
$ lgc resources
cede-pi/cede-pico-port/NetworkSerialPort
cede-pi/cede-uno-port/NetworkSerialPort

$ lgc places
cede-pico
cede-uno
```

Verbose resource view shows udev serial IDs, device paths, and ser2net status:

```bash
$ lgc -v resources
Exporter 'cede-pi':
  Group 'cede-pico-port' (cede-pi/cede-pico-port/*):
    Resource 'USBSerialPort' (...):
      {'avail': True,
       'params': {'extra': {'path': '/dev/ttyACM0', 'proxy': 'cede-pi'},
                  'host': 'cede-pi', 'port': None, 'speed': 115200}}
  Group 'cede-uno-port' (cede-pi/cede-uno-port/*):
    Resource 'USBSerialPort' (...):
      {'avail': True,
       'params': {'extra': {'path': '/dev/ttyACM1', 'proxy': 'cede-pi'},
                  'host': 'cede-pi', 'port': None, 'speed': 115200}}
```

> `port: None` means the ser2net proxy isn't active yet — it starts when
> you **acquire** the place.

## 3. Flash Pico

### 3a. Acquire the place

Acquiring locks the resource and starts the ser2net proxy on a dynamic port.

```bash
$ lgc -p cede-pico acquire
acquired place cede-pico

$ lgc -p cede-pico show
Place 'cede-pico':
  acquired: hellway/plastic
  acquired resources:
    cede-pi/cede-pico-port/NetworkSerialPort/USBSerialPort
Acquired resource 'USBSerialPort' (...):
  {'params': {'host': 'cede-pi', 'port': 45221, 'speed': 115200}}
```

### 3b. Transfer the UF2 to the Pi

```bash
scp lab/pico/hello_lab/build/hello_lab.uf2 pi@cede-pi.local:/tmp/hello_lab.uf2
```

### 3c. Enter BOOTSEL mode via picotool

```bash
$ ssh pi@cede-pi.local 'picotool reboot -uf'
The device was asked to reboot into BOOTSEL mode.
```

Wait ~3 seconds for the RPI-RP2 mass storage to appear:

```bash
$ ssh pi@cede-pi.local 'readlink -f /dev/disk/by-label/RPI-RP2'
/dev/sda1
```

### 3d. Copy the UF2

```bash
ssh pi@cede-pi.local 'sudo mkdir -p /mnt/rpi-rp2 && \
  sudo mount /dev/sda1 /mnt/rpi-rp2 && \
  sudo cp /tmp/hello_lab.uf2 /mnt/rpi-rp2/ && \
  sync && sudo umount /mnt/rpi-rp2'
```

The Pico automatically reboots after the UF2 copy.

### 3e. Verify serial output via LabGrid

After the Pico reboots (~4 seconds), the ser2net proxy serves the serial
output on the port shown in `lgc -p cede-pico show`:

```bash
$ timeout 5 nc cede-pi.local 45221
CEDE hello_lab rp2 ok digest=aec771d88ba3 (i2c 0x42 @ GP0/1; uno lab 0x43; ...)
```

Confirm the `digest=` token matches the `.digest` sidecar from the build.

### 3f. Release the place

```bash
$ lgc -p cede-pico release
released place cede-pico
```

## 4. Flash Uno

### 4a. Acquire the place

```bash
$ lgc -p cede-uno acquire
acquired place cede-uno

$ lgc -p cede-uno show
Acquired resource 'USBSerialPort' (...):
  {'params': {'extra': {'path': '/dev/ttyACM1'},
              'host': 'cede-pi', 'port': 38801, 'speed': 115200}}
```

### 4b. Transfer the HEX to the Pi

```bash
scp lab/uno/hello_lab/build/hello_lab.ino.hex pi@cede-pi.local:/tmp/hello_lab.ino.hex
```

### 4c. Flash via avrdude

```bash
$ ssh pi@cede-pi.local \
    'avrdude -p atmega328p -c arduino -P /dev/ttyACM1 -b 115200 \
             -D -U flash:w:/tmp/hello_lab.ino.hex:i'

avrdude: AVR device initialized and ready to accept instructions
avrdude: device signature = 0x1e950f (probably m328p)
avrdude: writing 5408 bytes flash ...
Writing | ################################################## | 100% 1.08s
avrdude: 5408 bytes of flash written
avrdude: verifying flash memory against /tmp/hello_lab.ino.hex
Reading | ################################################## | 100% 0.77s
avrdude: 5408 bytes of flash verified
avrdude done.  Thank you.
```

### 4d. Verify serial output

The Uno resets after avrdude finishes. The ser2net connection may carry
stale data from the avrdude handshake, so read with a DTR toggle for a
clean banner:

```bash
$ ssh pi@cede-pi.local 'python3 -c "
import serial, time
s = serial.Serial(\"/dev/ttyACM1\", 115200, timeout=2)
s.dtr = False; time.sleep(0.1); s.dtr = True
time.sleep(2)
print(s.read(4096).decode(\"utf-8\", errors=\"replace\"))
s.close()
"'
CEDE hello_lab ok digest=aec771d88ba3 (i2c target 0x43; send m for uno→pico I2C test)
```

### 4e. Release the place

```bash
$ lgc -p cede-uno release
released place cede-uno
```

## 5. Monitoring with labgrid-client

### Live event monitoring

Watch coordinator events in real time (resource state changes, acquires,
releases):

```bash
lgc monitor
```

### Interactive serial console

For longer interactive sessions, `labgrid-client console` wraps
`microcom` (or `picocom`) over the ser2net proxy:

```bash
lgc -p cede-pico acquire
lgc -p cede-pico console      # Ctrl+\ to exit
lgc -p cede-pico release
```

> Requires `microcom` installed on the Dev-Host
> (`apt install microcom` or `brew install microcom`).

### Who has what locked

```bash
$ lgc who
hellway/plastic: cede-pico
```

## 6. Attestation Summary

| Step | Artifact | Digest |
|---|---|---|
| Docker `pico-build` | `hello_lab.uf2` | `hello_lab.uf2.digest` = `aec771d88ba3` |
| Docker `uno-build` | `hello_lab.ino.hex` | `hello_lab.ino.hex.digest` = `aec771d88ba3` |
| Pico serial banner | `CEDE hello_lab rp2 ok digest=aec771d88ba3` | **match** |
| Uno serial banner | `CEDE hello_lab ok digest=aec771d88ba3` | **match** |

The `.digest` sidecar is generated during the Docker build by extracting
the `CEDE_IMAGE_ID` from the compiled header. The firmware prints this
same token on every USB serial reset. The `CedeValidationDriver` (used
in automated pytest runs) compares the two automatically.

## 7. Automated pytest Flow (Reference)

Once the manual flow is verified, the same steps run unattended via:

```bash
pytest --lg-env env/remote.yaml -v lab/tests/test_pico_labgrid.py
pytest --lg-env env/remote.yaml -v lab/tests/test_uno_labgrid.py
```

These use the `CedeStrategy` (`off -> flashed -> validated`) which
invokes `PicotoolFlashDriver` / `AvrdudeFlashDriver` and
`CedeValidationDriver` automatically.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `lgc resources` empty | Check exporter is running: `ssh pi@cede-pi.local 'pgrep -la labgrid-export'` |
| `port: None` after acquire | ser2net not installed on Pi: `sudo apt install ser2net` |
| RPI-RP2 doesn't appear | Hold BOOTSEL button on Pico while reconnecting USB |
| avrdude "not in sync" | Check `/dev/ttyACM1` is the Uno (verify with `udevadm info`); another process may hold the port — release the labgrid place first |
| Garbled ser2net output after avrdude | Normal — avrdude resets the Uno via DTR. Reconnect or use the Python DTR-toggle method above |
| Exporter disconnects | Check coordinator is running on Dev-Host; exporter auto-reconnects |

## Infrastructure Setup (One-Time)

When building a fresh SD image, the cloud-init pipeline automatically
installs labgrid, ser2net, and the exporter systemd service — see
[sdcard.md](sdcard.md) and [rpi3-gateway-remote.md](rpi3-gateway-remote.md)
for the SD card bootstrap workflow.

### Create places (coordinator must be running)

```bash
lgc -p cede-pico create
lgc -p cede-pico add-match "cede-pi/cede-pico-port/*"
lgc -p cede-pico set-tags board=pico

lgc -p cede-uno create
lgc -p cede-uno add-match "cede-pi/cede-uno-port/*"
lgc -p cede-uno set-tags board=uno
```

### Discover USB serial IDs (on the Pi)

```bash
$ udevadm info /dev/ttyACM0 | grep ID_SERIAL_SHORT
E: ID_SERIAL_SHORT=E660C06213580D29     # Pico

$ udevadm info /dev/ttyACM1 | grep ID_SERIAL_SHORT
E: ID_SERIAL_SHORT=74137363737351117051  # Uno
```

These go into `env/cede-pi-exporter.yaml` and `env/remote.yaml`.
