# InkOtter

<p align="center">
  <img src="assets/icons/inkotter.svg" alt="InkOtter mascot" width="220" />
</p>

> **Labels, unleashed.**  
> **Open printing for closed devices.**

Repository: <https://github.com/dasarne/inkotter>

InkOtter brings label printing to Linux for proprietary Bluetooth label printers that normally only work with vendor apps.

The project is designed around a small reusable printing core, device-specific drivers, and user-facing frontends such as a CLI and a Qt desktop GUI.

## Current Status

InkOtter `1.0.1` ships with a complete first production-ready driver:

- `Katasymbol E10`

The current implementation supports:

- printing `SVG`, `PNG`, and `JPG`
- Bluetooth RFCOMM transport
- document-faithful wide label printing
- actual-size SVG printing
- a minimal CLI
- a first Qt desktop GUI

## Print Model

InkOtter now uses a deliberately explicit print model:

- internal image data stays free of printer-specific outer margins
- preview-visible media margins come from the selected printer profile
- printer/protocol margins are applied only in the printer-ready / `btbuf` path

That keeps preview and print consistent without baking hardware-specific edge
offsets into the internal image geometry.

## Installation

For detailed Linux installation and desktop integration instructions, see [docs/INSTALLATION.md](docs/INSTALLATION.md).

### Install From A Local Checkout

```bash
cd InkOtter
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

For GUI support, install the GUI extra:

```bash
pip install -e .[gui]
```

This installs two entry points:

- `inkotter`
- `inkotter-gui`

### Dependencies

InkOtter currently depends on:

- Python `3.11+`
- `Pillow`
- `CairoSVG`

Optional dependency:

- `PySide6` (required for `inkotter-gui`)

If `CairoSVG` is not available, SVG rendering can fall back to a local `inkscape` executable.

## Starting InkOtter

### Command Line

```bash
inkotter --help
```

### Desktop GUI

```bash
inkotter-gui
```

## Local Desktop Integration

For Linux desktop testing, InkOtter includes:

- icon asset: `assets/icons/inkotter.svg`
- desktop launcher template: `packaging/linux/inkotter.desktop`
- local installer helper: `packaging/linux/install-local.sh`

After installing InkOtter into your current Python environment, you can install the desktop launcher locally with:

```bash
./packaging/linux/install-local.sh
```

That installs:

- `~/.local/share/icons/hicolor/scalable/apps/inkotter.svg`
- `~/.local/share/applications/inkotter.desktop`

The installer writes a launcher that prefers:

- `./.venv/bin/inkotter-gui` from the current checkout
- otherwise `inkotter-gui` from your `PATH`

If KDE does not show the launcher immediately, run:

```bash
kbuildsycoca6
```

## How To Use It

### 1. Check Bluetooth / Printer Discovery

```bash
inkotter --list-printers
```

This lists visible Bluetooth devices.

### 2. Print A File

```bash
inkotter label.svg
```

You can also print raster files:

```bash
inkotter label.png
inkotter label.jpg
```

### 3. Print In Actual Document Size

For SVG files with explicit physical dimensions, use:

```bash
inkotter --no-scale label.svg
```

This prints the SVG in its document size instead of fitting it into the default label geometry.

### 4. Preview The Job Without Sending It

```bash
inkotter --dry-run label.svg
```

## Current CLI Options

```bash
inkotter [--no-scale] [--mac MAC] [--channel N] [--scan-seconds N] [--list-printers] [--dry-run] <image>
```

Important options:

- `--list-printers` lists visible Bluetooth devices
- `--mac` selects a printer explicitly instead of auto-discovery
- `--no-scale` prints SVGs in actual document size
- `--dry-run` builds the print job without sending it

## Supported Printers

| Printer | Status |
| --- | --- |
| `Katasymbol E10` | Working |

More devices are intended to be added through drivers.

## Extending InkOtter

InkOtter is designed to grow through device profiles and drivers.

If your printer is not supported yet, the long-term plan is that you can add:

- a device profile
- protocol facts
- transport specifics where necessary

For contribution workflow and driver contribution guidance, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Known Scope

The first supported device family uses a verified T15-like image path and grouped `AA BB` transfers for wide labels.

Preview media margins and printer/protocol margins are modeled separately on
purpose. If a future printer needs different physical edge distances, the
profile should change those values instead of shifting the internal artwork.

Large dark filled areas may still show hardware-specific banding or stripe artifacts even when the generated raster data is correct. That is currently considered a printer-side behavior, not necessarily a software bug.

## Motivation

Many label printers are locked behind proprietary mobile apps.

InkOtter exists to make those devices usable from Linux and open desktop systems without depending on vendor software.

The practical motivation is simple:

- many vendor tools are phone-only even though label design and file preparation are usually better on a desktop
- those apps often want unnecessary permissions such as location access before Bluetooth use
- desktop workflows with SVG, PNG, file management, and keyboard-driven tooling are simply better suited for serious label work
- printing should not require handing document flow and device access to a closed mobile app

## Contributing

Contributions are welcome, especially:

- new device drivers
- protocol documentation
- rendering improvements
- packaging and desktop integration
- UI improvements

Driver contributions are explicitly welcome. InkOtter is intended to grow by adding clean device facts and small device-specific profiles instead of importing historical reverse-engineering clutter into the product core.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Project Vision

InkOtter aims to become:

> A universal, open printing layer for unsupported label printers on Linux.
