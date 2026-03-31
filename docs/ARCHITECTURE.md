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

### 5. Protocol

Responsibility:

- build `btbuf`
- compress payloads
- build frame sequences

### 6. Transport

Responsibility:

- discover printers
- open RFCOMM
- send frames and collect results

### 7. App Frontends

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
- Bluetooth discovery hints
- frame command identities for image jobs

## Canonical Planning Flow

1. `DocumentSpec`
2. `LayoutPlan`
3. `RasterPlan`
4. `RenderPlan`
5. protocol materialization
6. transport send
