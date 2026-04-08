# Protocol Facts

This file records only facts we currently consider stable enough to encode into
InkOtter's product core for the first supported device family.

## Katasymbol E10 / T15-like Image Path

Verified facts:

- raster head height: `96 px`
- bytes per column: `12`
- `btbuf` data offset: `14`
- wide image page width: `332 columns`
- productive one-page fitted behavior uses `88 px` of content inside a `96 px` canvas
- actual-size rendering is device-faithful at about `8 px/mm`
- wide labels are carried as grouped `AA BB` image transfers
- the first page may use left-trim semantics in fitted/single-page style jobs
- multi-page document-faithful jobs do not require the same left-trim behavior

Conservative operating assumptions kept explicit in the device profile:

- visible top inset: `1 px`
- visible left cut margin: currently `0 px`
- fit-to-label printer-ready x offset: `-4 px`
- additional fit-to-label SVG x offset: `-4 px`
- actual-size SVG right bleed: `12 px`
- single-page / final-page extra right margin: `32 px`

These values are not treated as protocol facts. They exist to keep preview and
printer-ready output aligned with observed hardware behavior without introducing
speculative calibration logic into the normal path.

## Kernel Consequence

InkOtter should separate:

1. document understanding
2. layout choice
3. raster planning
4. render planning
5. protocol serialization

This prevents protocol code from silently re-deciding page width, anchor mode,
or scaling behavior.
