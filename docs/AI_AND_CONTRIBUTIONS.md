# Author contributions and AI-assisted development

**Project lead:** Jincheng Li (李锦承)  
**Project period represented here:** November 2026  
**Release:** v1.1

## The work the author led

The project started with a commercial dual-channel muscle-electrical-signal module and a MacBook Pro. The author wanted to understand the measurement process, replace a Windows-oriented viewing workflow with a local Mac workflow, and retain a record of both the engineering and the experiments.

| Area | Author's role | Supporting artifact |
| --- | --- | --- |
| Requirements and design | Defined local acquisition, bilingual visualization, offline replay, analysis and educational-note requirements | [README](../README.md), [architecture](ARCHITECTURE.md) |
| Hardware integration | Connected the receiver through USB-C, selected the serial port, connected leads and operated the commercial board | [Hardware photographs](HARDWARE_GUIDE.md) |
| Software development | Directed AI-assisted construction and iteration of the Python backend and HTML/CSS/JavaScript frontend; used the resulting app during device testing | [Source](../server.py), [frontend](../web/), [test evidence](../TEST_STATUS.md) |
| Troubleshooting | Compared disconnected and floating-cable conditions, checked parsing, observed clipping and narrowband interference, and repeated recordings after setup changes | [Technical report](../reports/TECHNICAL_REPORT.md) |
| Data collection | Performed the supplied single-channel and dual-channel self-recordings, described electrode-location changes and confirmed the action order | [Original CSVs](../data/raw/), [data provenance](../data/README.md) |
| Analysis | Selected amplitude/spectral/correlation tools, discussed interpretations, and directed reproducible computation and reporting with AI assistance | [Analysis script](../scripts/analyze_recordings.py), [methods](METHODS.md) |
| Education and communication | Developed six interactive chapters with AI assistance and connected statistical concepts to practical acquisition problems | [Interactive notes](index.html) |

## What AI assistance covered

AI assistance contributed substantial code generation, UI implementation, explanatory text, analysis scripts, debugging suggestions, test generation and documentation. The author supplied the project goals, device information, actual device operation, experimental choices, observations, corrections, photographs and recordings. The packaged results should be assessed through the included source, data and test evidence.

## Hardware scope

The module contains a microcontroller, but this project integrates its published output. The project did not design the PCB, design the analog front end, fabricate an ADC, implement the device's wireless firmware, or write custom MCU acquisition firmware. Exact MCU model, gain, physical ADC characteristics and firmware timing are not independently established by the material in this release.

## Research scope

The algorithms are established methods implemented as an engineering learning toolkit. The recordings are a single person's exploratory sessions. The release does not claim a novel EMG algorithm, clinical validation, force-prediction accuracy on real data, or isolated recruitment of a particular muscle. The technical report distinguishes observations from interpretations and records how activity intervals were reconstructed.
