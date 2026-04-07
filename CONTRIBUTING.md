# Contributing

InkOtter is intentionally built as a small, knowledge-based printing core. Contributions are welcome, but the project should stay lean.

## What Is Especially Helpful

- new device profiles
- validated protocol facts
- printer discovery improvements
- rendering and preview improvements
- packaging and desktop integration
- documentation and installation polish

## Driver Contributions

Driver contributions are explicitly welcome.

The preferred InkOtter style is:

- add stable device facts as explicit profile data
- keep protocol knowledge in the device and protocol layers
- keep the core pipeline generic
- avoid importing diagnostic or reverse-engineering helpers into the product path unless they are clearly needed

For a new printer, the expected shape is usually:

1. add or extend a device profile in `src/inkotter/devices/`
2. add protocol facts needed by the transport/materialization path
3. verify layout, raster, and preview behavior with real hardware
4. document stable facts in `docs/PROTOCOL_FACTS.md` or a new focused device document if needed

## Principles

- prefer facts over hypotheses
- prefer small explicit data structures over hidden heuristics
- prefer maintainable V2 code over carrying V1 complexity forward
- keep the render/layout/raster/protocol layers separated

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## Validation

Before sending changes, at minimum:

- run the relevant CLI or GUI workflow
- verify real hardware behavior if your change affects device behavior
- run `python3 -m py_compile` on changed Python modules

## Discussion

Repository: <https://github.com/dasarne/inkotter>

If you want to contribute support for a printer, opening an issue with:

- printer model
- observed Bluetooth name
- sample captures or protocol facts
- photos of real print output

is a good start.
