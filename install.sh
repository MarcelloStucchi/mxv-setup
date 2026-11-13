#!/usr/bin/env bash
# Portable installer for the MX Vertical "hold Forward" helper:
#   hold Forward + wheel  -> horizontal scroll
#   hold Forward + move L/R -> switch GNOME workspace
#
# Transfer this whole folder (mxv-setup/) to another machine and run:
#   pkexec bash install.sh
#
# Requirements on the target machine:
#   - python3-evdev            (the daemon)
#   - solaar / logitech_receiver (only to un-divert the Forward button; the mouse
#                                 remembers the un-divert in its own firmware, so a
#                                 machine where it was already un-diverted is fine)
set -uo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run as root:  pkexec bash $0" >&2; exit 1; }

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC_DAEMON="$HERE/mxv-hscroll.py"
DAEMON=/usr/local/bin/mxv-hscroll.py
ENVF=/etc/mxv-hscroll.env
UNIT=/etc/systemd/system/mxv-hscroll.service

[ -f "$SRC_DAEMON" ] || { echo "ERROR: $SRC_DAEMON not found (keep it next to install.sh)"; exit 1; }

echo "== 1/5 un-diverting the Forward button (best-effort via logitech_receiver) =="
python3 - <<'PY' || true
import sys
try:
    from logitech_receiver import base, device, receiver
except Exception as ex:
    print("  (skipped: logitech_receiver/Solaar not available:", ex, ")")
    sys.exit(0)

def enum():
    for di in base.receivers_and_devices():
        try:
            yield device.create_device(base, di) if di.isDevice else receiver.create_receiver(base, di)
        except Exception as ex:
            print("  open error:", ex)

target = None
for d in enum():
    if d is None:
        continue
    if getattr(d, "isDevice", False):
        cand = [d]
        try: d.ping()
        except Exception: pass
    else:
        try: cand = list(d)
        except Exception: cand = []
    for dev in cand:
        try: nm = (dev.name or "").lower()
        except Exception: nm = ""
        if "mx vertical" in nm:
            target = dev; break
    if target:
        break
if target is None:
    print("  (MX Vertical not found; if it was already un-diverted before, that's fine)")
    sys.exit(0)
try: target.ping()
except Exception: pass
dk = next((s for s in target.settings if s.name == "divert-keys"), None)
if dk is None:
    print("  (divert-keys setting unavailable)"); sys.exit(0)
try:
    dk.write_key_value(86, 0, save=True)   # 86 = Forward Button, 0 = Regular
    after = dict(dk.read(cached=False))
    print("  Forward button now:", "Regular(OK)" if after.get(86) == 0 else "STILL DIVERTED")
except Exception as ex:
    print("  write error:", ex)
PY

echo "== 2/5 installing daemon -> $DAEMON =="
install -m 0755 "$SRC_DAEMON" "$DAEMON"

echo "== 3/5 writing config -> $ENVF =="
OLD_MOD=276; OLD_INV=0
if [ -f "$ENVF" ]; then
  v=$(grep -E '^MXV_MODIFIER=' "$ENVF" | tail -1 | cut -d= -f2 || true); [ -n "${v:-}" ] && OLD_MOD=$v
  v=$(grep -E '^MXV_INVERT='   "$ENVF" | tail -1 | cut -d= -f2 || true); [ -n "${v:-}" ] && OLD_INV=$v
  echo "  (preserving MXV_MODIFIER=$OLD_MOD, MXV_INVERT=$OLD_INV; workspace settings reset to defaults)"
fi
cat > "$ENVF" <<EOF
# NOTE: systemd EnvironmentFile does NOT strip trailing "# comments" from a
# value line, so keep every comment on its own line (like these).

# Which mouse (PREFIX match on the evdev name: "Logitech MX Vertical" matches both
# the Unifying-receiver name and the Bluetooth name "Logitech MX Vertical Advanced
# Ergonomic Mouse"), and which evdev code the Forward button emits (276 = BTN_EXTRA).
MXV_DEVICE=Logitech MX Vertical
MXV_MODIFIER=$OLD_MOD

# Horizontal scroll (hold Forward + roll wheel). 1 = reverse direction.
MXV_INVERT=$OLD_INV

# Workspace swipe (hold Forward + move mouse left/right).
# MXV_WS_THRESHOLD   = mouse counts to move before switching (higher = less sensitive)
# MXV_WS_COOLDOWN_MS = minimum gap between switches
# MXV_WS_INVERT      = 1 swaps which direction goes which way
# MXV_WS_PREV        = keys sent when mouse moves RIGHT (= switch-to-workspace-left)
# MXV_WS_NEXT        = keys sent when mouse moves LEFT  (= switch-to-workspace-right)
# MXV_FREEZE_POINTER = 1 keeps the cursor still while Forward is held
MXV_WS_ENABLE=1
MXV_WS_THRESHOLD=250
MXV_WS_COOLDOWN_MS=350
MXV_WS_INVERT=0
MXV_WS_PREV=KEY_LEFTMETA+KEY_PAGEUP
MXV_WS_NEXT=KEY_LEFTMETA+KEY_PAGEDOWN
MXV_FREEZE_POINTER=1
EOF

echo "== 4/5 writing service -> $UNIT =="
cat > "$UNIT" <<EOF
[Unit]
Description=MX Vertical: hold Forward for horizontal scroll + workspace swipe
After=multi-user.target

[Service]
Type=simple
EnvironmentFile=$ENVF
ExecStart=/usr/bin/python3 $DAEMON
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

echo "== 5/5 enabling + starting service =="
systemctl daemon-reload
systemctl enable mxv-hscroll.service >/dev/null 2>&1 || true
systemctl restart mxv-hscroll.service
sleep 1
systemctl --no-pager is-active mxv-hscroll.service
journalctl -u mxv-hscroll -n 3 --no-pager 2>&1 | sed 's/^/  LOG: /' || true
echo
echo "DONE."
echo "  hold Forward + wheel       -> horizontal scroll"
echo "  hold Forward + move L/R     -> switch workspace"
echo "  tune:   edit $ENVF  then  systemctl restart mxv-hscroll"
echo "  logs:   journalctl -u mxv-hscroll -f"
