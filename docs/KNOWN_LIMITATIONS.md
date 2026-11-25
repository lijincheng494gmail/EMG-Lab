# Known limitations and interpretation boundaries

EMG-Lab demonstrates an operational software workflow and documents observations from one commercial board and one owner's self-recordings. The following distinctions make the results easier to reuse correctly.

## Measurement

| Unresolved point | Consequence for interpretation |
|---|---|
| Physical sampling clock and exported-sample timing | Reception rate is reported as frames/s; Hz conversion remains conditional |
| ADC architecture, effective resolution and physical range | 0/4095 are provisional boundary codes; 12-bit appearance is not calibration |
| Gain, offset and channel matching | Waveforms remain in counts; cross-channel force ratios are unsupported |
| Analog and firmware filter responses | The full measurement bandwidth and aliasing protection are unknown |
| Dual-channel sampling skew | A displayed lag is not a verified physiological delay between muscles |
| Device “mean”, “power” and “effort” algorithms | These fields remain opaque indicators and are not primary physiological endpoints |
| Packet sequence/checksum absence | Malformed-line counts cannot quantify undetected complete-frame loss |
| Equipment electrical certification | Battery power and wireless transport do not themselves establish human-use safety |

The parameter table's 4.7–5 V and tutorial's 9 V battery wording refer to a supply arrangement that was not independently resolved. The project should not be used to infer an interchangeable input voltage or a schematic-level pinout.

## Software and timing

- Host timestamps mark batch arrival, not individual ADC conversions. Duplicate times are expected when a serial read contains several frames.
- The live buffer contains at most 12,000 frames. Recording writes valid frames independently of that plotting limit.
- Optional forward-backward filtering analyzes each selected window, with edge effects. It is not a causal stream filter with measured end-to-end latency.
- Markers identify a host click and next accepted frame. They are not hardware-synchronized events.
- The importer reconstructs row ordering for analysis. An index in an imported file is not evidence of device packet continuity.
- The server is a localhost prototype. Internet deployment, multi-user authentication, clinical use and production fault tolerance are outside this release.

## Historical data

The five supplied CSVs are preserved as source observations. Original event sidecars, exact electrode spacing, contact impedance, measured force, exact joint angles, manufacturer firmware version and acquisition clock measurements were not supplied.

The final session includes two consecutive repetitions of each of five intended conditions in one person. The order was not randomized, and posture changed with conditions. These data support a documented engineering demonstration and descriptive exploration. They cannot separate all effects of posture, order, fatigue, effort, electrode movement and intended activation.

The later knee-reference session also used stronger contractions. A before/after improvement therefore does not identify the reference site as its cause. A forehead reference in the final session is reported as historical context, not a general setup recommendation.

Activity intervals were reconstructed retrospectively. They are approximate and were chosen with knowledge of the signal. Treat them as exploratory labels and retain that distinction when reusing them.

## What the release does and does not establish

| Evidence included | Supported description | Unsupported extension |
|---|---|---|
| Mac screenshots, serial captures and software | Commercial-board integration and local acquisition workflow | Universal macOS/device compatibility or certified instrument performance |
| Floating-input and disconnect tests | Large changes associated with wiring state | Complete analog noise model or proof of a specific component defect |
| Repeated activation-associated signal changes | Exploratory activity-dependent observations | Verified isolation of a muscle or decoded motor commands |
| RMS and spectral analysis | Transparent numerical descriptions of received data | Calibrated force, clinical diagnosis or proof of fatigue |
| Synthetic held-out regression | Functioning feature/split/fit/evaluation pipeline | Measured EMG-to-force accuracy or population generalization |
| Interactive inverse-problem chapter | Educational explanation of identifiability | Motor-unit decomposition implemented and validated on this board |

## Priorities for a stronger next study

The largest improvements would come from trustworthy timing and labels, not from adding many algorithms: obtain the device's exported sampling specification and filter/gain information; use a consistent documented electrode configuration; preserve event metadata; measure an independent force or motion target if prediction is the goal; and collect independent repeated sessions for a specified question.
