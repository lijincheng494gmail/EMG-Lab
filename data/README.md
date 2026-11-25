# Recorded data and derived results

This directory contains **five device-export CSVs with 71,287 received frames**
from the author's bench tests and exploratory self-recordings on 25 November
2026. `raw/` preserves the supplied file bytes. `derived/` contains reproducible
summaries produced by [`scripts/analyze_recordings.py`](../scripts/analyze_recordings.py).

The short IDs below are report labels. They do not replace the original filenames.

## Recording inventory

| ID | Original CSV | Rows | Context reported by the author |
| --- | --- | ---: | --- |
| F01 | [20261125_223305_3a8c7d.csv](raw/20261125_223305_3a8c7d.csv) | 9,387 | CH2 lead connected to the board, electrode ends floating; CH1 unused |
| F02 | [20261125_223514_6791e0.csv](raw/20261125_223514_6791e0.csv) | 9,572 | Same intended wiring as F01, with a software reconnect between captures |
| S01 | [20261125_230211_2835c7.csv](raw/20261125_230211_2835c7.csv) | 10,817 | Initial biceps attempt on CH2; reference near the wrist in the supplied setup image |
| S02 | [20261125_231208_8ff529.csv](raw/20261125_231208_8ff529.csv) | 10,676 | Biceps on CH2; author reported moving the red reference electrode to the knee and using stronger contractions |
| D01 | [20261125_232138_110cad.csv](raw/20261125_232138_110cad.csv) | 30,835 | CH1 triceps, CH2 biceps; author reported a forehead reference and five intended actions, each repeated twice |

The location descriptions are historical metadata. These files do not validate
an electrode-placement recommendation. In particular, reference location,
contact, posture, and effort were not independently controlled between S01 and
S02. The experiment contains one participant and one session, not five
independent participants.

## CSV schema

| Column | Meaning | Unit / caveat |
| --- | --- | --- |
| `frame` | Sequential index assigned by the receiving application | Host index, not a device sequence counter |
| `host_elapsed_s` | Time assigned by the application on receipt of a serial batch | Seconds from connection; can repeat across rows and need not begin at zero |
| `ch1_mean`, `ch2_mean` | First manufacturer-defined value for each channel | Opaque device field; not necessarily the current sample mean |
| `ch1_adc`, `ch2_adc` | Manufacturer-described lightly filtered digitized channel values | Device counts; gain, physical voltage conversion and firmware filter response are not established |
| `ch1_power`, `ch2_power` | Manufacturer-defined activity or power values | Algorithm and calibration unverified; not watts |
| `ch1_level`, `ch2_level` | Manufacturer-defined effort-level fields | Uncalibrated integer values; not measured muscle force |
| `source_kind` | App provenance label | `device` for every row in these five files |

The word `raw` means **the unmodified received CSV export**. The electronics and
firmware have already processed the physical signal. These files are not
unfiltered electrode voltages and do not contain every byte received on the
serial connection. Malformed serial frames were not written as ordinary CSV rows.

No missing cells, decreasing timestamps or nonunit host-frame increments were
found in the five supplied exports. Duplicate adjacent timestamps are present,
which is consistent with assigning one receipt time to multiple parsed frames.
These checks cannot measure lost packets before the host parser or establish a
uniform physical sampling rate. An unused, stable channel is not a physiological
control measurement.

## Timing and labels

The report re-zeros each file using its first `host_elapsed_s`. It computes
reception rate as `(number_of_rows - 1) / (last_time - first_time)` and uses
**cycles per received frame** for spectral frequency. Received frames/s is not
automatically the ADC sampling rate. There are no hardware timestamps in this
schema.

The original session JSON files and synchronized event markers were not supplied.
Consequently:

- S01/S02 phase labels follow the proposed alternating five-second schedule.
- D01 activity spans come from a retrospective one-second-bin threshold rule.
- D01 condition names follow the author's reported order. They describe what the
  author intended to do; selective recruitment is not verified by those names.

## Reproduce

From the repository root, with the analysis dependencies installed:

```bash
python3 -m pip install -r requirements-analysis.txt
python3 scripts/analyze_recordings.py
```

For tables only, `python3 scripts/analyze_recordings.py --skip-figures` avoids the
Matplotlib import. Raw files are read only. Generated files can be overwritten by
rerunning the script. The numerical calculations use NumPy and SciPy; plots use
Matplotlib. No fitted random model is used in this analysis.

| Generated file | Contents |
| --- | --- |
| [summary.json](derived/summary.json) | Full-precision results, original-file SHA-256 hashes and sizes, dependency versions, field ranges and method settings |
| [recording_summary.csv](derived/recording_summary.csv) | One row per recording and channel: amplitude, range, boundary occupancy and host reception rate |
| [dual_channel_1s_bins.csv](derived/dual_channel_1s_bins.csv) | One-second-bin amplitudes and activity-selection flag |
| [dual_channel_intervals.csv](derived/dual_channel_intervals.csv) | Ten selected intervals, author-intended condition labels and preceding-rest summaries |
| [dual_channel_conditions.csv](derived/dual_channel_conditions.csv) | Equal-weight mean of the two repetition-level RMS values for each intended condition |
| [dual_channel_boundary_sensitivity.csv](derived/dual_channel_boundary_sensitivity.csv) | Results after trimming 0, 0.25 or 0.5 seconds from each interval edge |
| [single_channel_phases.csv](derived/single_channel_phases.csv) | Seven nominal phases per single-channel recording; centered RMS and exploratory outside-band PSD amplitude |
| [single_channel_band_sensitivity.csv](derived/single_channel_band_sensitivity.csv) | Sensitivity to four excluded-band widths in S02 |

Read the [technical report](../reports/TECHNICAL_REPORT.md) for interpretation and
the [generated numerical appendix](../reports/RESULTS.md) for the complete tables.

## Reuse context

These are exploratory self-recordings shared for an engineering demonstration.
They do not support diagnosis, force calibration, population inference or a
classification benchmark. The accompanying plots and descriptive labels are
analysis outputs, not independent ground truth. The synthetic regression example
under `examples/` is a separate dataset and is not mixed into this collection.
