# MX Vertical — "hold Forward" power mode

Hold the **Forward** (upper thumb) button on a Logitech **MX Vertical** and:
- roll the wheel → **horizontal scroll**
- move the mouse **left/right** → **switch GNOME workspace** (like the touchpad 4-finger swipe)

This folder contains everything needed to reproduce it on another Linux machine.

---

## (IT) Come usare questo file su un altro PC

1. Copia **tutta questa cartella** (`install.sh`, `mxv-hscroll.py`, `README.md`) sull'altro PC.
2. Apri **Claude Code** in quella cartella e incolla il prompt qui sotto. Claude leggerà
   questo README, controllerà i prerequisiti di QUEL PC e adatterà l'installazione.
3. In alternativa, se l'altro PC è Fedora + GNOME come questo, puoi installare a mano:
   `pkexec bash install.sh` (poi tieni premuto Forward e prova rotella / movimento L-R).

### (IT) Prompt da incollare nell'altra istanza di Claude

> Ho una cartella `mxv-setup` con `install.sh`, `mxv-hscroll.py` e `README.md`. Voglio
> replicare su QUESTO PC la stessa configurazione descritta nel README: tenendo premuto il
> tasto Forward del mouse Logitech MX Vertical, la rotella scrolla in orizzontale e muovendo
> il mouse a sinistra/destra cambio workspace di GNOME. Leggi il README, verifica i
> prerequisiti di questo PC (distro/init, sessione GNOME Wayland o X11, i keybinding dei
> workspace, il codice evdev del tasto Forward, e se il tasto è "diverted" in Solaar) e poi
> adatta ed esegui l'installazione, spiegandomi i passaggi.

---

## What it is (for the other Claude)

A small **python-evdev daemon** run as a **root systemd service** (`mxv-hscroll`). It grabs the
mouse at the evdev layer (`EVIOCGRAB`), re-emits every event through a virtual `uinput` mouse so
normal behaviour is untouched, and **only while the Forward button is held**:
- maps `REL_WHEEL`/`REL_WHEEL_HI_RES` → `REL_HWHEEL`/`REL_HWHEEL_HI_RES` (horizontal scroll),
- accumulates `REL_X` and, past a threshold, injects the GNOME "switch workspace" keybinding
  through a virtual `uinput` keyboard (this is how you switch workspaces from a background
  process on Wayland — synthesize the shortcut the compositor already listens for),
- freezes pointer motion so it feels like a gesture.

Everything is driven by env vars in `/etc/mxv-hscroll.env`.

### Why this design (not Solaar rules)
The MX Vertical only supports **low-res** wheel diversion (HID++ feature `0x2130`), not hi-res
(`0x2121`). Doing it via Solaar's "Scroll Wheel Diversion" would route **all** vertical scrolling
through Solaar+uinput and make normal scrolling coarse/laggy. The evdev daemon leaves normal
scrolling 100% native and only acts while Forward is held.

---

## Files

| File | Purpose |
|------|---------|
| `mxv-hscroll.py` | the daemon (installed to `/usr/local/bin/mxv-hscroll.py`) |
| `install.sh` | un-diverts the Forward button, installs the daemon + `/etc/mxv-hscroll.env` + the systemd unit, enables & starts it |
| `README.md` | this file |

### What `install.sh` creates on the target
- `/usr/local/bin/mxv-hscroll.py`
- `/etc/mxv-hscroll.env`  (all tuning lives here)
- `/etc/systemd/system/mxv-hscroll.service`  (enabled → starts at boot)

---

## Reproduce — quick path (identical Fedora + GNOME machine)
```
pkexec bash install.sh
```
Then hold Forward and test wheel (horizontal) + left/right move (workspace).

## Reproduce — careful path (DIFFERENT machine; recommended)

1. **Install the runtime dependency** (the daemon imports `evdev`):
   - Fedora:  `sudo dnf install python3-evdev`   ← install EXPLICITLY so autoremove won't drop it
   - Debian/Ubuntu:  `sudo apt install python3-evdev`
   - (`solaar` is only needed to un-divert the button — see step 2.)

2. **Un-divert the Forward button.** If the button is "Diverted" in Solaar it sends HID++
   notifications and **never reaches evdev**, so nothing works. The un-divert is stored in the
   **mouse firmware**, so if this same mouse was already used on the origin PC it is probably
   already un-diverted — but verify. To set it: Solaar GUI → MX Vertical → *Key/Button Diversion*
   → **Forward Button = Regular**. (`install.sh` also does this programmatically via the
   `logitech_receiver` library; do NOT rely on `solaar config` CLI writes — see Gotchas.)

3. **Confirm the Forward button's evdev code.** Default is `BTN_EXTRA` = **276** (standard for
   Logitech). Verify by stopping the service and capturing: read the `Logitech MX Vertical` evdev
   node and press Forward; whatever `EV_KEY` code appears (276, or maybe a `KEY_FORWARD`) goes
   into `MXV_MODIFIER`.

4. **Check the workspace keybindings** and set `MXV_WS_PREV` / `MXV_WS_NEXT` to match:
   ```
   gsettings get org.gnome.desktop.wm.keybindings switch-to-workspace-left
   gsettings get org.gnome.desktop.wm.keybindings switch-to-workspace-right
   gsettings get org.gnome.desktop.wm.keybindings switch-to-workspace-up
   gsettings get org.gnome.desktop.wm.keybindings switch-to-workspace-down
   ```
   Pick a combo that is actually bound. Map the keys to `ecodes` names joined with `+`
   (e.g. `KEY_LEFTMETA+KEY_PAGEUP`). For non-GNOME desktops, use that DE's switch shortcut.

5. **Install & start:** `pkexec bash install.sh` (or run the steps it contains manually).

---

## Reference values from the SOURCE machine (this PC)
- OS: Fedora 44, **GNOME on Wayland**, system `python3` = 3.14
- Mouse: `Logitech MX Vertical` via Logitech Unifying receiver, or
  `Logitech MX Vertical Advanced Ergonomic Mouse` via Bluetooth (single evdev node; node number
  varies across reboots — the daemon matches by **name prefix**, not number, so both work)
- Forward button evdev code: `BTN_EXTRA` = **276**
- Workspaces are **horizontal**: `switch-to-workspace-left` includes `<Super>Page_Up`,
  `switch-to-workspace-right` includes `<Super>Page_Down`
- Mapping chosen: mouse **right → left workspace** (`Super+Page_Up`), mouse **left → right
  workspace** (`Super+Page_Down`)

---

## Tuning — `/etc/mxv-hscroll.env` (then `sudo systemctl restart mxv-hscroll`)
| Var | Meaning |
|-----|---------|
| `MXV_DEVICE` | evdev device-name **prefix** to grab (`Logitech MX Vertical` — matches both the receiver name and the Bluetooth name `Logitech MX Vertical Advanced Ergonomic Mouse`) |
| `MXV_MODIFIER` | evdev code of the Forward button (276 = BTN_EXTRA) |
| `MXV_INVERT` | `1` reverses horizontal-scroll direction |
| `MXV_WS_ENABLE` | `0` disables the workspace gesture (keep only hscroll) |
| `MXV_WS_THRESHOLD` | mouse counts to move before switching — **lower = more sensitive** (this PC uses 250) |
| `MXV_WS_COOLDOWN_MS` | min gap between switches |
| `MXV_WS_INVERT` | `1` swaps which direction goes which way |
| `MXV_WS_PREV` | keys sent when mouse moves RIGHT (default `KEY_LEFTMETA+KEY_PAGEUP`) |
| `MXV_WS_NEXT` | keys sent when mouse moves LEFT (default `KEY_LEFTMETA+KEY_PAGEDOWN`) |
| `MXV_FREEZE_POINTER` | `1` keeps the cursor still while Forward is held |

> NOTE: a systemd `EnvironmentFile` does **not** strip trailing `# comments` from a value line —
> keep comments on their own lines.

---

## Gotchas (learned the hard way on the source machine)
1. **`solaar config <dev> <setting> <value>` WRITES crash** on Solaar 1.1.19 + Python 3.14
   (`TypeError: Unable to marshal str as an array` in `Gio.Application.run`). Reads work; writes
   fail silently. Change settings via the **GUI** or the **`logitech_receiver` library**
   (`setting.write_key_value(86, 0, save=True)` → CID 86 = Forward, 0 = Regular). `install.sh`
   uses the library method.
2. **Diverted button = invisible to evdev.** Must be "Regular". Persists in mouse firmware.
3. **`python3-evdev` can get autoremoved** if it was only pulled in as a Solaar dependency and
   Solaar is later removed → service crash-loops with `ModuleNotFoundError: No module named
   'evdev'`. Install it **explicitly** so it's user-marked.
4. **uinput** must be writable — running the service as **root** avoids any permission setup
   (`/dev/uinput` is root-only by default).
5. Daemon finds the mouse **by evdev name**, so node renumbering across reboots is fine.

---

## Service commands
```
systemctl status mxv-hscroll            # state
journalctl -u mxv-hscroll -f            # live logs
sudo systemctl restart mxv-hscroll      # after editing the env file
# uninstall:
sudo systemctl disable --now mxv-hscroll
sudo rm /usr/local/bin/mxv-hscroll.py /etc/mxv-hscroll.env /etc/systemd/system/mxv-hscroll.service
sudo systemctl daemon-reload
```
