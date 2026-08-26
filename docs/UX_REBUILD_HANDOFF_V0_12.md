# UAS Thermal Intelligence v0.12 — Consumer-Grade Mission UX Rebuild Handoff

## Why this tranche exists

The v0.11 desktop is functionally richer than its presentation suggests, but the Windows acceptance screenshots exposed two release-blocking classes of defects:

1. **The guided experience is not reliable on the target machine.** The bundled demo can fail while materializing its synthetic GeoTIFF because the local Rasterio/GDAL runtime cannot resolve an EPSG authority database (`proj.db`). The operator then sees a hard error before any value is demonstrated.
2. **The product still presents as an engineering control panel.** Too much internal state, implementation terminology, small typography, stacked informational sections, and dense navigation are exposed before the operator has completed a mission. The UI communicates architecture rather than outcome.

Treat both as product defects. Do not solve this tranche with another stylesheet-only pass.

## Product acceptance statement

> A first-time operator can open the application, immediately understand how to start, run a zero-setup guided mission, watch a clear autonomous progress experience, and land on a visually dominant inspection result with annotated thermal evidence, severity summary, findings, and one-click deliverables — without understanding adapters, model names, pipeline stages, CRS internals, or report plumbing.

## Normal user journey

1. **Home** — one primary decision: choose a mission folder or run the guided example.
2. **Autonomous processing** — a calm progress surface shows human-readable work such as validating thermal data, building the thermal map, detecting anomalies, reviewing evidence, and preparing the deliverable.
3. **Inspection result** — the dominant surface is the annotated thermal overview/digital inspection canvas. Findings, severity and evidence are visually inspectable.
4. **Handoff** — report, client viewer and deliverable folder are one click away.
5. **Advanced tools** — calibration, model routing, measurement tools, pipeline telemetry and specialist pages remain available, but are progressively disclosed rather than forming the default experience.

## UX rules

- No developer-console aesthetic on the default landing page.
- No raw local model names on the normal Home surface. Show `Local AI ready` or `Deterministic analysis ready`; expose exact routing only in advanced details.
- No all-caps wall of implementation labels.
- One strong visual hierarchy: brand → mission action → progress/result.
- Use plain-language verbs: `Choose mission folder`, `Run guided example`, `Review findings`, `Open report`.
- Technical claim boundaries remain strict. AI interpretation is supplemental; deterministic radiometry remains authoritative.
- Never claim field accuracy, certification, IEC compliance, or thermographer equivalence unless separately proven.
- No horizontal scrolling at 1024×600 or larger supported layouts.
- The application must remain navigable while background runtime discovery or processing runs.

## Reliability rules

- The bundled guided mission must not depend on an external EPSG database lookup. Use a self-contained synthetic local projected CRS WKT for demo files.
- Guided demo materialization must validate the generated radiometric files before intake.
- CI must execute the full guided demo processing path on Windows, not only instantiate the UI.
- Failures must be converted into concise operator guidance while retaining detailed diagnostics in telemetry/logs.

## Target Home states

### Ready
Large mission start card with two actions: `Choose mission folder` and `Run guided example`. A short `What Autopilot handles` strip explains Discover → Map → Detect → Review → Deliver.

### Running
Replace marketing/capability content with a focused mission-progress surface. Show current human-readable task, progress, source count, and that work remains local. Advanced telemetry is collapsed.

### Complete
Make the generated annotated thermal overview the largest object on screen. Beside it show finding count and severity distribution. Provide `Review findings`, `Open report`, `Open client viewer`, and `Open deliverable folder`.

## Navigation

Normal navigation should be concise:

- Home
- Projects
- Mission Data
- Thermal Review
- Findings
- Compare
- Reports
- Analytics
- Settings

Hide implementation/specialist pages by default and expose them through `Advanced tools`:

- Analysis
- Processing
- Exports
- Profiles
- Measure
- Pipeline

## Verification gates

Release only when all are true:

- Python 3.11 CI green.
- Python 3.12 CI green.
- Windows desktop smoke green.
- Windows guided-demo end-to-end test green.
- Responsive UI regression green at 1024×600 and 1366×768.
- Visual QA artifacts generated for Ready and completed-demo states.
- Guided demo produces the authoritative package including PDF, findings JSON/CSV, annotated thermal overview, quantitative thermal orthomosaic, portable viewer, processing report and manifest.
- No customer data, vendor SDK binaries, secrets or local machine paths enter source control.

## Implementation boundary

Reuse the existing v0.10/v0.11 quantitative and autonomous authorities. This tranche is allowed to replace the presentation layer and harden the bundled synthetic demo, but it must not create a second anomaly detector, second report generator, second intake authority or second AI-routing authority.
