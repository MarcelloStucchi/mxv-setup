#!/usr/bin/env python3
"""MX Vertical power-button helper.

While the Forward (upper thumb) button is held:
  * the scroll wheel scrolls horizontally (REL_WHEEL -> REL_HWHEEL), and
  * moving the mouse left/right switches GNOME workspaces (like the touchpad
    4-finger swipe), by injecting the compositor's workspace keybinding.

It grabs the mouse at the evdev layer and re-emits all events through a virtual
mouse, so normal behaviour (pointer, clicks, vertical scroll) is untouched when
the button is not held. Configured entirely via environment variables; see
/etc/mxv-hscroll.env."""
import os
import time

import evdev
from evdev import ecodes as e

def _clean(v):
    # tolerate inline "# comments" and whitespace (systemd EnvironmentFile keeps them)
    return v.split("#", 1)[0].strip() if v is not None else v


def _int_env(name, default):
    v = _clean(os.environ.get(name))
    try:
        return int(v) if v else default
    except ValueError:
        return default


def _bool_env(name, default="0"):
    return _clean(os.environ.get(name, default)) == "1"


def _str_env(name, default):
    v = _clean(os.environ.get(name))
    return v if v else default


NAME = _str_env("MXV_DEVICE", "Logitech MX Vertical")
MODIFIER = _int_env("MXV_MODIFIER", e.BTN_EXTRA)
INVERT = _bool_env("MXV_INVERT")

WS_ENABLE = _bool_env("MXV_WS_ENABLE", "1")
WS_THRESHOLD = _int_env("MXV_WS_THRESHOLD", 400)
WS_COOLDOWN = _int_env("MXV_WS_COOLDOWN_MS", 350) / 1000.0
WS_INVERT = _bool_env("MXV_WS_INVERT")
WS_PREV_STR = _str_env("MXV_WS_PREV", "KEY_LEFTMETA+KEY_PAGEUP")    # workspace-left
WS_NEXT_STR = _str_env("MXV_WS_NEXT", "KEY_LEFTMETA+KEY_PAGEDOWN")  # workspace-right
FREEZE_PTR = _bool_env("MXV_FREEZE_POINTER", "1")

WHEEL_MAP = {e.REL_WHEEL: e.REL_HWHEEL}
if hasattr(e, "REL_WHEEL_HI_RES") and hasattr(e, "REL_HWHEEL_HI_RES"):
    WHEEL_MAP[e.REL_WHEEL_HI_RES] = e.REL_HWHEEL_HI_RES


def parse_combo(s):
    keys = []
    for tok in s.split("+"):
        tok = tok.strip()
        if not tok:
            continue
        code = getattr(e, tok, None)
        if code is None:
            print(f"[mxv-hscroll] WARNING: unknown key '{tok}' in '{s}'", flush=True)
            continue
        keys.append(code)
    return keys


PREV = parse_combo(WS_PREV_STR)
NEXT = parse_combo(WS_NEXT_STR)
# mouse moved right -> left workspace (PREV); mouse moved left -> right workspace (NEXT)
RIGHT_COMBO, LEFT_COMBO = (NEXT, PREV) if WS_INVERT else (PREV, NEXT)
ALL_KEYS = sorted(set(PREV) | set(NEXT))


def find_device():
    for path in evdev.list_devices():
        try:
            d = evdev.InputDevice(path)
        except OSError:
            continue
        caps = d.capabilities()
        # Prefix match: the same mouse is "Logitech MX Vertical" through the
        # Unifying receiver but "Logitech MX Vertical Advanced Ergonomic Mouse"
        # over Bluetooth. Never match our own virtual devices.
        if (
            d.name.startswith(NAME)
            and not d.name.startswith("mxv-hscroll")
            and e.EV_REL in caps
            and e.EV_KEY in caps
        ):
            return d
        d.close()
    return None


def run(dev):
    print(
        f"[mxv-hscroll] grabbed {dev.path} ({dev.name}); modifier={MODIFIER} "
        f"hscroll_invert={INVERT} ws={'on' if WS_ENABLE else 'off'} "
        f"ws_threshold={WS_THRESHOLD} ws_invert={WS_INVERT}",
        flush=True,
    )
    ui = evdev.UInput.from_device(dev, name="mxv-hscroll-virtual")
    kbd = evdev.UInput({e.EV_KEY: ALL_KEYS}, name="mxv-hscroll-keys") if ALL_KEYS else None
    dev.grab()
    active = False
    accum_x = 0
    last_switch = 0.0

    def tap(combo):
        if not kbd or not combo:
            return
        for k in combo:
            kbd.write(e.EV_KEY, k, 1)
        kbd.syn()
        time.sleep(0.02)
        for k in reversed(combo):
            kbd.write(e.EV_KEY, k, 0)
        kbd.syn()

    try:
        for ev in dev.read_loop():
            # Forward button = pure modifier; never passed through.
            if ev.type == e.EV_KEY and ev.code == MODIFIER:
                active = ev.value != 0
                accum_x = 0
                continue
            if active:
                # wheel -> horizontal scroll
                if ev.type == e.EV_REL and ev.code in WHEEL_MAP:
                    val = -ev.value if INVERT else ev.value
                    ui.write(e.EV_REL, WHEEL_MAP[ev.code], val)
                    continue
                # horizontal motion -> workspace switch
                if ev.type == e.EV_REL and ev.code == e.REL_X:
                    if WS_ENABLE:
                        accum_x += ev.value
                        now = time.monotonic()
                        if now - last_switch >= WS_COOLDOWN:
                            if accum_x >= WS_THRESHOLD:
                                tap(RIGHT_COMBO)
                                accum_x = 0
                                last_switch = now
                            elif accum_x <= -WS_THRESHOLD:
                                tap(LEFT_COMBO)
                                accum_x = 0
                                last_switch = now
                    if FREEZE_PTR:
                        continue
                # freeze vertical pointer drift during the gesture
                if ev.type == e.EV_REL and ev.code == e.REL_Y and FREEZE_PTR:
                    continue
            if ev.type == e.EV_SYN:
                ui.syn()
                continue
            ui.write(ev.type, ev.code, ev.value)
    finally:
        try:
            dev.ungrab()
        except OSError:
            pass
        ui.close()
        if kbd:
            kbd.close()


def main():
    print(f"[mxv-hscroll] starting; looking for a device named '{NAME}*'", flush=True)
    while True:
        dev = find_device()
        if dev is None:
            time.sleep(2)
            continue
        try:
            run(dev)
        except OSError as ex:
            print(f"[mxv-hscroll] device lost ({ex}); waiting to reconnect...", flush=True)
            try:
                dev.close()
            except Exception:
                pass
            time.sleep(2)


if __name__ == "__main__":
    main()
