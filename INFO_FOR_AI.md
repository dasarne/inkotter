# InkOtter AI Notes

InkOtter is the clean-slate successor to the older research/reference repo.

## Product Goal

Provide open, installable printing for otherwise closed label devices.

First supported device:

- Katasymbol E10

## Current Kernel Direction

The intended stable flow is:

1. `DocumentSpec`
2. `LayoutPlan`
3. `RasterPlan`
4. `RenderPlan`
5. protocol/materialization
6. transport

The key rule is: do not bury user-intent decisions inside protocol code.

## What Counts As Settled Knowledge

For the Katasymbol E10 / T15-like raster family, the following are currently
considered facts and should be modeled explicitly, not rediscovered:

- `96 px` head height
- `12` bytes per column
- `btbuf` data offset `14`
- `332 px` page width for wide labels
- `8 px/mm` as the device-faithful actual-size raster density
- productive one-page fitted rendering uses an `88 px` content height inside a `96 px` canvas
- multi-page wide image jobs are sent as grouped `AA BB` transfers

## Modeling Bias

Prefer:

- explicit dataclasses
- clear layer boundaries
- device profiles with facts
- small pure functions

Avoid:

- reverse-engineering-era speculative branches in the product core
- burying geometry decisions inside protocol serialization
- premature GUI complexity before the kernel is stable
