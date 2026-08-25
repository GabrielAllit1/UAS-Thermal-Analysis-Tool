# AI Autopilot UX

The primary product contract is **operator-in, deliverable-out**. A normal user should not need to understand adapters, model families, stitching backends, calibration internals, or report assembly to complete a mission.

The default desktop flow is:

1. Choose a flight folder or select mission files.
2. The application recursively discovers supported thermal/geospatial inputs, creates project context, infers a conservative inspection profile from folder/file metadata, chooses the output destination, and selects local AI routes automatically.
3. Autopilot runs radiometric gating, stitching when appropriate, deterministic anomaly analysis, local AI evidence interpretation, annotations, and packaging.
4. The completed mission presents the deliverable location and portable client viewer. No second report-generation step is required.

Advanced controls remain available, but they are not part of the required path.

## Claim boundary

AI may route models, interpret already-established findings, summarize evidence, and draft client/engineering narrative. Source radiometry, temperature matrices, geospatial transforms, canonical finding geometry, delta-T, severity, and confidence remain deterministic authorities.
