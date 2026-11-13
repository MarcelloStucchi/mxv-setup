# mxv-setup

Horizontal scrolling and workspace switching for the Logitech MX Vertical on Linux with GNOME. Hold the Forward button (the upper thumb button) and:

- roll the wheel to scroll sideways
- move the mouse left or right to switch GNOME workspace, like a four-finger swipe on a touchpad

Let go and the mouse behaves as before. The cursor stays still while you hold Forward, so the left/right movement doesn't drag it across the screen.

## Who it is for

The MX Vertical has one vertical wheel, with no tilt and no thumb wheel, so it can't scroll sideways on its own. Logitech's Options+ software doesn't run on Linux. If you use this mouse on a GNOME desktop and work with wide spreadsheets or long lines of code, or you miss the touchpad's workspace swipe, this daemon gives you both through one button.

Tested on Fedora 44 with GNOME on Wayland and Python 3.14, using GNOME's default horizontal workspaces and its Super+Page Up and Super+Page Down shortcuts. The mouse works through a Logitech Unifying receiver and over Bluetooth. Other distributions and desktops need small adjustments, described in [Installing on a different machine](#installing-on-a-different-machine). Another mouse with a spare button should also work if you change `MXV_DEVICE` and `MXV_MODIFIER`, but that is untested.

You give up one thing: Forward stops working as the "forward" button in browsers and file managers. The daemon uses it only as a modifier and never passes it on.

## How it works

`mxv-hscroll.py` is a small [python-evdev](https://github.com/gvalkov/python-evdev) daemon that runs as the root systemd service `mxv-hscroll`. It grabs the mouse exclusively (`EVIOCGRAB`) and re-emits every event through a virtual uinput mouse named `mxv-hscroll-virtual`. With Forward released, the virtual mouse sends exactly what the real one sent. With Forward held:

- The daemon turns `REL_WHEEL` and `REL_WHEEL_HI_RES` events into `REL_HWHEEL` and `REL_HWHEEL_HI_RES`, so the wheel scrolls sideways.
- It adds up horizontal movement (`REL_X`). Once the total passes `MXV_WS_THRESHOLD` counts, it presses GNOME's switch-workspace shortcut through a second virtual device, the keyboard `mxv-hscroll-keys`. On Wayland a background process can't tell the compositor directly to change workspace, so the daemon types the shortcut GNOME already listens for.
- It drops pointer movement, if `MXV_FREEZE_POINTER=1`.

The daemon finds the mouse by the start of its evdev name. `Logitech MX Vertical` matches both the receiver name and the Bluetooth name (`Logitech MX Vertical Advanced Ergonomic Mouse`), and the `/dev/input/event*` number can change between boots without breaking anything. If the mouse disconnects, the daemon looks for it every two seconds and grabs it again when it comes back.

### Why not Solaar rules

[Solaar](https://github.com/pwr-Solaar/Solaar) can divert the scroll wheel and run rules on it, but the MX Vertical supports only low-resolution wheel diversion (HID++ feature `0x2130`), not high-resolution (`0x2121`). With the wheel diverted, all vertical scrolling goes through Solaar and uinput and turns coarse and laggy. The daemon leaves normal scrolling native and steps in only while Forward is down.

## Requirements

- Linux with systemd
- Python 3 with python-evdev (`python3-evdev` on Fedora, Debian and Ubuntu). Install it explicitly; see [Troubleshooting](#the-service-keeps-restarting-with-no-module-named-evdev).
- Solaar, or at least its `logitech_receiver` Python library, to un-divert the Forward button. The mouse stores that setting in its own firmware, so you need Solaar only once per mouse.
- GNOME, for the default workspace shortcuts. On other desktops, put their switch-workspace shortcuts in `MXV_WS_PREV` and `MXV_WS_NEXT`.

## Install

On Fedora with GNOME and the default workspace shortcuts:

```sh
sudo dnf install python3-evdev
git clone https://github.com/MarcelloStucchi/mxv-setup.git
cd mxv-setup
sudo bash install.sh
```

With pkexec, pass the full path (`pkexec bash "$PWD/install.sh"`), because pkexec starts in root's home folder. Then hold Forward and try the wheel and a left/right move.

The installer makes these changes to your system:

1. It sets the Forward button (control ID 86) to "Regular" in the mouse firmware through `logitech_receiver`. If Solaar isn't installed or the mouse isn't found, it skips this step, which is fine when the button was never diverted.
2. It copies the daemon to `/usr/local/bin/mxv-hscroll.py`.
3. It writes the settings to `/etc/mxv-hscroll.env`. On a reinstall it keeps your `MXV_MODIFIER` and `MXV_INVERT` values and resets everything else to the defaults in [Configuration](#configuration), so save a copy first if you tuned the workspace settings.
4. It writes `/etc/systemd/system/mxv-hscroll.service`, enables it at boot and starts it.

The service runs as root because only root can write to `/dev/uinput` on a default system, and grabbing the mouse needs access to `/dev/input`.

## Installing on a different machine

On another distribution or desktop, go step by step:

1. Install python-evdev: `sudo dnf install python3-evdev` on Fedora, `sudo apt install python3-evdev` on Debian and Ubuntu.
2. Un-divert the Forward button. A diverted button sends HID++ notifications to Solaar and never reaches evdev, so the daemon sees nothing. In the Solaar window, select the MX Vertical, open Key/Button Diversion and set Forward Button to Regular. `install.sh` does the same through the `logitech_receiver` library. Don't use the `solaar config` command for this; see [Troubleshooting](#solaar-config-doesnt-change-the-setting).
3. Check which evdev code Forward sends. Logitech mice normally send `BTN_EXTRA` (276). Stop the service if it's running, run `sudo evtest`, pick the MX Vertical and press Forward. The `EV_KEY` code you see (276, or maybe a `KEY_FORWARD`) goes into `MXV_MODIFIER`.
4. Check your workspace shortcuts:
   ```sh
   gsettings get org.gnome.desktop.wm.keybindings switch-to-workspace-left
   gsettings get org.gnome.desktop.wm.keybindings switch-to-workspace-right
   gsettings get org.gnome.desktop.wm.keybindings switch-to-workspace-up
   gsettings get org.gnome.desktop.wm.keybindings switch-to-workspace-down
   ```
   Pick a combination that is actually bound and write it as python-evdev key names joined by `+`. For example, `<Super>Page_Up` becomes `KEY_LEFTMETA+KEY_PAGEUP`. On another desktop, use its own switch-workspace shortcut.
5. Run `sudo bash install.sh`, or do its steps by hand. Then put the values from steps 3 and 4 in `/etc/mxv-hscroll.env` and restart the service.

### With Claude Code

You can let Claude Code do the checks above. Open it in the cloned folder and paste:

> I have the `mxv-setup` folder with `install.sh`, `mxv-hscroll.py` and `README.md`. I want the setup from the README on THIS machine: while I hold the Forward button of my Logitech MX Vertical, the wheel scrolls horizontally and moving the mouse left or right switches GNOME workspace. Read the README, check this machine's prerequisites (distribution and init system, GNOME on Wayland or X11, the workspace keybindings, the evdev code of the Forward button, and whether Solaar has the button diverted), then adapt and run the installation and explain each step to me.

## Configuration

All settings live in `/etc/mxv-hscroll.env`. After editing it, run `sudo systemctl restart mxv-hscroll`.

| Variable | Default | Meaning |
|---|---|---|
| `MXV_DEVICE` | `Logitech MX Vertical` | Start of the evdev device name to grab |
| `MXV_MODIFIER` | `276` | evdev code of the Forward button (`BTN_EXTRA`) |
| `MXV_INVERT` | `0` | `1` reverses the horizontal scroll direction |
| `MXV_WS_ENABLE` | `1` | `0` turns off workspace switching and keeps only horizontal scroll |
| `MXV_WS_THRESHOLD` | `250` | Mouse counts to move before a switch; lower is more sensitive |
| `MXV_WS_COOLDOWN_MS` | `350` | Minimum time between two switches, in milliseconds |
| `MXV_WS_INVERT` | `0` | `1` swaps the two directions |
| `MXV_WS_PREV` | `KEY_LEFTMETA+KEY_PAGEUP` | Keys sent when the mouse moves right (GNOME: workspace on the left) |
| `MXV_WS_NEXT` | `KEY_LEFTMETA+KEY_PAGEDOWN` | Keys sent when the mouse moves left (GNOME: workspace on the right) |
| `MXV_FREEZE_POINTER` | `1` | `1` keeps the cursor still while Forward is held |

The defaults are the values `install.sh` writes. If a variable is missing from the file, the daemon uses its built-in default, which is the same for every variable except `MXV_WS_THRESHOLD` (400 instead of 250).

Keep each comment on its own line. systemd's `EnvironmentFile` doesn't strip a trailing `# comment` from a value line.

## Troubleshooting

### Holding Forward does nothing

The button is probably diverted in Solaar. A diverted button sends HID++ notifications instead of a normal click, so neither evdev nor the daemon sees it. Set Forward Button back to Regular in Solaar (step 2 of [Installing on a different machine](#installing-on-a-different-machine)). The mouse keeps this setting in its firmware, so it carries over to other computers.

### `solaar config` doesn't change the setting

On Solaar 1.1.19 with Python 3.14, writes through `solaar config <device> <setting> <value>` crash with `TypeError: Unable to marshal str as an array` in `Gio.Application.run`, and the setting stays as it was. Reads work. Use the Solaar window, or the library call that `install.sh` makes: `setting.write_key_value(86, 0, save=True)`, where 86 is the Forward button and 0 means Regular.

### The service keeps restarting with `No module named 'evdev'`

The package manager probably removed python3-evdev as an orphan. That happens when it came in only as a Solaar dependency and Solaar was uninstalled later. Install it explicitly (`sudo dnf install python3-evdev`) so it counts as user-installed.

### Checking the service

```sh
systemctl status mxv-hscroll          # is it running
journalctl -u mxv-hscroll -f          # live log: grabbed device and active settings
sudo systemctl restart mxv-hscroll    # after editing /etc/mxv-hscroll.env
```

## Uninstall

```sh
sudo systemctl disable --now mxv-hscroll
sudo rm /usr/local/bin/mxv-hscroll.py /etc/mxv-hscroll.env /etc/systemd/system/mxv-hscroll.service
sudo systemctl daemon-reload
```

The Forward button stays un-diverted in the mouse, so after uninstalling it works as a normal Forward button again.

## License

Copyright (C) 2026 Marcello Stucchi

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. See [LICENSE](LICENSE) for the full text.

## Credits

Developed with Claude, Anthropic's AI assistant, in Claude Code.
