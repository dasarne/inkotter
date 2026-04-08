# Installation

InkOtter currently targets Linux desktops and is developed primarily against KDE/Qt environments.

## Requirements

- Python `3.11+`
- Bluetooth support with RFCOMM access
- a working local Python environment

Optional but recommended:

- `inkscape` for SVG rendering that matches interactive Inkscape output more closely

## Install From A Local Checkout

```bash
git clone https://github.com/dasarne/inkotter.git
cd inkotter
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

This installs:

- `inkotter`
- `inkotter-gui`

## Start The GUI

```bash
source .venv/bin/activate
inkotter-gui
```

## Start The CLI

```bash
source .venv/bin/activate
inkotter --help
```

## Local Desktop Integration

InkOtter ships a local desktop installer helper:

```bash
./packaging/linux/install-local.sh
```

Important:

- run this command as the same desktop user who should see InkOtter in the launcher menu
- do not run it as `root` unless you explicitly want installation into root's local profile
- use `./packaging/linux/install-local.sh` (relative path), not `/packaging/linux/install-local.sh`

That installs:

- `~/.local/share/icons/hicolor/scalable/apps/inkotter.svg`
- `~/.local/share/applications/inkotter.desktop`

The installer writes a launcher that prefers:

- `./.venv/bin/inkotter-gui` from the current checkout
- otherwise `inkotter-gui` from your `PATH`

If KDE does not pick up the launcher immediately, refresh the application database:

```bash
kbuildsycoca6
```

If InkOtter still does not appear in your menu:

1. Check whether the launcher was installed into root's profile by mistake:

```bash
ls -l /root/.local/share/applications/inkotter.desktop
```

2. Re-run the installer as your normal desktop user from the repository root:

```bash
cd /path/to/inkotter
./packaging/linux/install-local.sh
kbuildsycoca6
```

3. Verify the launcher file exists for your user:

```bash
ls -l ~/.local/share/applications/inkotter.desktop
grep '^Exec=' ~/.local/share/applications/inkotter.desktop
grep '^TryExec=' ~/.local/share/applications/inkotter.desktop
```

`Exec` and `TryExec` should both point to a valid executable (for example `.../.venv/bin/inkotter-gui`).

## Bluetooth Notes

- InkOtter prints directly over Bluetooth RFCOMM.
- Depending on your Linux setup, Bluetooth access may require group membership, a compatible system configuration, or elevated privileges.
- `inkotter --list-printers` is the quickest way to test whether the printer is visible from your current environment.

## SVG Notes

- InkOtter can render SVG through CairoSVG.
- If `inkscape` is installed locally, InkOtter prefers it for SVG rendering because text and font handling usually match desktop authoring tools better.

## First Print Test

```bash
inkotter --list-printers
inkotter test.svg
```

For an SVG with explicit physical dimensions:

```bash
inkotter --no-scale test.svg
```
