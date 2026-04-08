# Architecture

## Goal

Keep the implementation small, layered, and device-extensible.

## Layers

### 1. Document

Responsibility:

- load PNG/JPG/SVG
- detect physical size where present
- expose a normalized document model

### 2. Layout

Responsibility:

- choose fit-to-label vs actual-size behavior
- decide whether a document stays single-page or becomes a wide label
- express user intent without touching protocol details

### 3. Raster Planning

Responsibility:

- derive the target canvas size for a device
- split wide canvases into device pages where required
- keep width/height/paging decisions explicit

### 4. Render

Responsibility:

- turn `DocumentSpec + LayoutPlan + RasterPlan` into a canonical render contract
- define source raster size, placement on the device canvas, and monochrome policy
- stay protocol-neutral: no `btbuf`, no framing, no transport

### 5. Canvas Variants

Responsibility:

- build the three explicit post-render canvas stages
- keep preview-visible and printer-ready geometry separate
- make device-specific output shifts visible before protocol materialization

Current stages:

- `rendered_canvas`: direct render result from `RenderPlan`
- `preview_canvas`: visible-area adjusted canvas used by the GUI/source preview
- `printer_ready_canvas`: final canvas used for `btbuf` packing

### 6. Preview

Responsibility:

- derive visible preview surfaces from the explicit canvas stages
- crop top inset / left cut area consistently
- materialize the graphic and physical strip previews without changing print geometry

### 7. Protocol

Responsibility:

- build `btbuf`
- compress payloads
- build frame sequences

### 8. Transport

Responsibility:

- discover printers
- open RFCOMM
- send frames and collect results

### 9. App Frontends

Responsibility:

- CLI
- later GUI / desktop entry / paste / file picker

## Device Drivers

Each supported printer family should provide:

- profile facts
- layout constraints
- protocol facts
- transport quirks if needed

The first driver is `katasymbol_e10`.

For the first kernel step, the device layer should already own facts such as:

- raster head height
- bytes per column
- `btbuf` data offset
- single-page and multi-page width semantics
- visible-area facts such as top inset and left cut margin
- preview/media margins for user-visible strip rendering
- printer-ready output offsets
- protocol page margins
- Bluetooth discovery hints
- frame command identities for image jobs

The current `RasterProfile` still contains these effect classes in one profile
object, but call sites should access them through explicit helper methods so the
meaning stays visible in code.

Current rule of thumb:

- internal canvas geometry should stay printer-agnostic
- preview-only outer whitespace should come from profile media-margin values
- printer/protocol compensation should happen in the printer-ready / `btbuf` path

## Canonical Planning Flow

1. `DocumentSpec`
2. `LayoutPlan`
3. `RasterPlan`
4. `RenderPlan`
5. `CanvasVariants`
6. preview surface / strip materialization
7. protocol materialization
8. transport send

## Current Non-Goals

- No speculative hardware calibration search during normal rendering.
- No separate preview-only geometry path that diverges from printer-ready placement.
- No large abstraction layers around a single supported printer family.
