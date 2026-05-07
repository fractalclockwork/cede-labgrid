# SSH keys for Pi bootstrap (`authorized_keys_file`)

## Do you need this for end-to-end testing?

| Goal | Need `authorized_keys_file`? |
|------|-------------------------------|
| **Hands-on** first login with keyboard + monitor, or serial console | **No** — use the OS default / Imager-defined password if applicable. |
| **Non-interactive E2E** (scripts, CI-style checks, `ssh -o BatchMode=yes`) | **Strongly recommended** — avoids passwords in automation and matches how most gateways are operated remotely. |

CEDE does **not** set a password in cloud-init; keys are the supported way to get **passwordless SSH on first boot** from your Dev-Host. The rendered `users:` entry includes Pi-style **`groups`** (including **`sudo`**) and **`sudo: ALL=(ALL) NOPASSWD:ALL`** so the gateway user can run **`sudo`** after first boot.

---

## 1. Create or choose an SSH key pair (Dev-Host)

Use an existing key or create one (Ed25519 is a good default):

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -C "cede-dev-host" -N ""
```

The **public** file used by CEDE must end in **`.pub`** (e.g. `~/.ssh/id_ed25519.pub`).

---

## 2. Configure `lab/config/lab.yaml`

Copy from the example if needed:

```bash
cp lab/config/lab.example.yaml lab/config/lab.yaml
```

Edit **`lab.yaml`**:

1. **`hosts.pi.ssh_user`** — login user cloud-init will attach keys to (usually **`pi`** on Raspberry Pi OS Lite).
2. **`hosts.pi.ssh_host`** — use **`<hostname>.local`** for mDNS (must match **`raspberry_pi_bootstrap.hostname`** → e.g. hostname `cede-pi` → `cede-pi.local`).
3. **`raspberry_pi_bootstrap.authorized_keys_file`** — absolute path or **`~/.ssh/id_ed25519.pub`**. Tilde is resolved for the **invoking user** even when you use **`sudo ./.venv/bin/python ...`** (so `~` is not misread as **`/root/.ssh`**).

Example:

```yaml
hosts:
  pi:
    ssh_host: cede-pi.local
    ssh_user: pi
    # ...

raspberry_pi_bootstrap:
  hostname: cede-pi
  authorized_keys_file: "~/.ssh/id_ed25519.pub"
```

Validate:

```bash
make -C lab/docker test-config
# or (uv): make test-config-local
```

---

## 3. Test before touching the SD card (render-only)

Confirm the public key is embedded in rendered **`user-data`**:

```bash
cd ~/src/cede   # repo root
uv sync         # if using uv
uv run python lab/pi/bootstrap/pi_bootstrap.py render
grep -E 'ssh-(ed25519|rsa)' lab/pi/cloud-init/rendered/user-data
```

You should see **`ssh_authorized_keys`** under **`users:`** for **`hosts.pi.ssh_user`**. If **`grep`** finds nothing, check that **`authorized_keys_file`** points to a readable **`.pub`** file with at least one non-comment line.

**Offline E2E tests (temp `.pub` + isolated render dir, no SD / Pi):**

```bash
uv run pytest lab/tests/test_ssh_key_sharing_e2e.py -q
```

---

## 4. Deploy keys onto the image or SD card

Keys must be on the **boot** partition **before** the Pi’s **first** boot that should apply them (or re-flash / re-inject and boot again).

Pick one path:

| Flow | Commands (repo root; adjust device paths) |
|------|---------------------------------------------|
| **YAML flash from URL** | `uv run python lab/pi/bootstrap/pi_bootstrap.py flash --device /dev/sdX --yes` |
| **Local `.img` after fetch/expand/patch** | `sudo ./.venv/bin/python lab/pi/bootstrap/pi_bootstrap.py patch-image --image lab/pi/dist/your.img --yes` then `sudo ./.venv/bin/python lab/pi/bootstrap/pi_bootstrap.py flash-file --device /dev/sdX --image lab/pi/dist/your.img --yes` |
| **Card already written** | `sudo ./.venv/bin/python lab/pi/bootstrap/pi_bootstrap.py prepare-boot --device /dev/sdX --yes` |

Use **`sudo ./.venv/bin/python`** (or **`./lab/pi/bootstrap/pi_bootstrap_sudo.sh`**) instead of **`sudo uv run`** — see [cli-flash.md](cli-flash.md).

---

## Host keys (avoid editing `~/.ssh/known_hosts`)

Each SD re-flash installs a **new** sshd host key. OpenSSH then errors with **REMOTE HOST IDENTIFICATION HAS CHANGED** until that hostname is removed from whatever **`KnownHostsFile`** tracks it. Prefer **not** to run **`ssh-keygen -f ~/.ssh/known_hosts -R …`** on your Dev-Host primary file: it is shared with real servers where key rotation semantics differ.

Instead, keep gateway/lab fingerprints in a **separate file** (e.g. **`~/.ssh/cede_gateway_known_hosts`**) and pass **`UserKnownHostsFile`** / **`StrictHostKeyChecking=accept-new`** from the shell or **`~/.ssh/config`** when you **`ssh`** to the gateway (examples below).

Manual one-off (paste host as needed):

```bash
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 \
  -o UserKnownHostsFile="$HOME/.ssh/cede_gateway_known_hosts" \
  -o StrictHostKeyChecking=accept-new \
  -o ConnectTimeout=10 \
  pi@cede-pi.local true && echo OK
```

After **re-imaging** the Pi, drop the lab file or a single host line — **not** the global known_hosts:

```bash
rm -f "$HOME/.ssh/cede_gateway_known_hosts"
# or: ssh-keygen -f "$HOME/.ssh/cede_gateway_known_hosts" -R cede-pi.local
```

Optional **`~/.ssh/config`** stanza (adjust **`Host`** / **`User`** / key path):

```sshconfig
Host cede-pi cede-pi.local
    User pi
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    UserKnownHostsFile ~/.ssh/cede_gateway_known_hosts
    StrictHostKeyChecking accept-new
```

---

## 5. Test SSH after the Pi boots

1. Ethernet to LAN (or Wi‑Fi if configured under **`raspberry_pi_bootstrap.wifi`**).
2. Wait for cloud-init — **first boot can take 15–30 minutes** while **`package_upgrade`** runs; **`Connection refused`** on port 22 usually means sshd is not listening **yet**, not that the hostname is wrong. Repatch with current **`lib_sdcard.sh`** so the FAT partition gets an empty **`ssh`** file (early sshd). Retry **`ssh`** while **`ping`** succeeds.

CEDE does **not** set a password for **`pi`**. If **`authorized_keys_file`** was missing when you built the image, SSH opens but **key authentication fails** and password login may not work — fix **`lab.yaml`**, re-render, **`prepare-boot`** / **`patch-image`**, re-boot (see § 6).

### “Too many authentication failures”

OpenSSH tries **every key** loaded in **`ssh-agent`** before offering password entry. After **`MaxAuthTries`** (often **6**), the server disconnects — even if you intended to type a password.

**Always pin one identity** when connecting:

```bash
ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 pi@cede-pi.local
```

Password-only attempt (no agent keys tried):

```bash
ssh -o IdentitiesOnly=yes -o PubkeyAuthentication=no pi@cede-pi.local
```

**Non-interactive check** (E2E):

```bash
ssh -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=10 \
  -i ~/.ssh/id_ed25519 \
  pi@cede-pi.local exit
```

---

## 6. Rotate or fix keys

1. Update **`authorized_keys_file`** or replace the **`.pub`** file contents.
2. Run **`pi_bootstrap.py render`** again.
3. Re-inject boot only (no full re-download): **`prepare-boot`** on the Dev-Host with the card inserted, or **`patch-image`** if you maintain a golden `.img`.

---

## Security notes

- **`lab/config/lab.yaml`** is **gitignored** — keep secrets and machine-specific paths there.
- Only **public** keys belong in **`authorized_keys_file`**; never commit private keys.
- Prefer **`authorized_keys_file`** over putting Wi‑Fi PSKs in YAML; use **`psk_file`** for Wi‑Fi when possible.

---

## See also

- [sdcard.md](sdcard.md) — full SD / first-boot flow  
- [cli-flash.md](cli-flash.md) — imaging, **`sudo` + uv PATH**, golden image  
