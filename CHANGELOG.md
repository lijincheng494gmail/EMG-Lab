# Changelog

## v1.1 — GitHub portfolio package — 2026-11-25

### Added

- English and Chinese project home pages, illustrated hardware/operation documentation, protocol and architecture references, numerical methods and implementation limits.
- Five original device CSV files, a reproducible analysis script, derived tables, figures and a detailed exploratory technical report.
- Original setup photographs and historical Mac screenshots with explicit context.
- Author contribution and AI-assistance statement, citation metadata, and instructions for running the application.
- Application integration test and synthetic-import sampling-rate regression test, plus a GitHub Actions test workflow (remote execution is not claimed).

### Corrected

- An imported file marked `synthetic` no longer automatically acquires a 300 Hz sampling rate. The built-in generator and bundled example loader retain their documented known rate.
- Large frame-number tick formatting, nonnegative spectral/RMS display bounds, and the stale serial “waiting” message after frames arrive.
- Notes status statements updated to reflect owner-reported Mac operation and the included real recordings. Interactive notes are separately labeled v0.2; all six chapters and 25 modules remain.

### Evidence boundaries

The author's Mac screenshots document the earlier v1.0 application. v1.1 changes have development-environment checks, not a new physical-board validation. Recorded counts, device sampling timing and physiological meaning remain subject to the limitations documented in the report. No repository upload or GitHub Pages deployment is performed by this archive.

## v1.0 — Local acquisition prototype — 2026-11-25

Local Python server, serial reader, bilingual browser interface, synthetic demo, recording/replay, signal analysis, synthetic OLS workflow, six-chapter notes and initial automated tests. Subsequently used by the author on a Mac with the commercial receiver, producing the recordings and screenshots now included in v1.1.
