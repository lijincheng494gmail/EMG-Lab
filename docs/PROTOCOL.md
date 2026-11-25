# Device interface and data dictionary

This document distinguishes the manufacturer-described interface from what the software actually receives and saves. Device information comes from the owner-supplied Chinese product instructions and the manufacturer's [dual-channel product page](https://www.sichiray.com/portfolio/items/emg-sensor). The full manual is not reproduced here.

## 1. Physical interface

| Item | Documented or observed value | Evidence and interpretation |
|---|---|---|
| Input channels | Two | Commercial board and supplied instructions |
| Electrode lead connector | 3.5 mm socket per channel | Supplied instructions and photographs; this is not an audio input |
| Lead colors | Green/yellow measuring pair; red reference | Manufacturer description; verify with the exact supplied lead |
| Board-to-host path | Wireless board link → USB receiver → serial device | Observed on the owner's Mac |
| Owner's serial device | `/dev/cu.usbserial-10` | Device path from that Mac; other computers may assign another path |
| Serial setting | 115200 baud, 8N1 in the application | Successful owner-reported acquisition |
| Analog output range | 0–3.3 V, per supplied instructions | Not an input-voltage calibration or measurement of electrode voltage |
| ADC conversion specification | 1.67 microseconds per conversion, per instructions | Does not identify the rate of transmitted samples |
| Supply wording | Parameter table: 4.7–5 V; tutorial: 9 V battery at the white connector | Connector/regulation distinction was not independently resolved; do not interchange these supplies based on this document |

This software uses the wireless receiver. It does not require wiring the board's analog outputs into a Mac or another ADC.

## 2. Text stream

The manual describes a CR/LF frame prefix followed by eight comma-separated integer strings. In a continuous stream, that delimiter also separates consecutive records. The receiving parser buffers bytes until LF (`0A`), strips surrounding CR/whitespace and validates the comma-separated fields.

Example payload:

```text
2107,2112,5,0,2111,2103,6,0
```

An example including the documented preceding delimiter is:

```text
0D 0A 32 31 30 37 2C 32 31 31 32 2C 35 2C 30 2C 32 31 31 31 2C 32 31 30 33 2C 36 2C 30
```

The payload is 27 ASCII bytes; CR/LF adds two bytes. The strings `2107` and `5` occupy four and one bytes respectively. This is text encoding, not a fixed-width binary ADC packet. Line lengths change with the numbers.

The hex example in the owner-supplied manual omitted the `30 2C` bytes corresponding to the fourth field `0,`. The eight-field text example and the real received frames are consistent. EMG-Lab parses the observed eight-field structure.

## 3. Eight fields

| Position, 1-based | CSV name | Manufacturer label | Use in this project |
|---:|---|---|---|
| 1 | `ch1_mean` | A0 mean | Retained device-defined indicator; not substituted for a measured baseline |
| 2 | `ch1_adc` | A0 output after simple filtering | CH1 waveform, in transmitted counts |
| 3 | `ch1_power` | A0 computed power | Retained device-defined indicator; units and algorithm unknown |
| 4 | `ch1_level` | A0 effort grade | Retained device-defined indicator; not calibrated force |
| 5 | `ch2_mean` | A1 mean | Retained device-defined indicator; not substituted for a measured baseline |
| 6 | `ch2_adc` | A1 output after simple filtering | CH2 waveform, in transmitted counts |
| 7 | `ch2_power` | A1 computed power | Retained device-defined indicator; units and algorithm unknown |
| 8 | `ch2_level` | A1 effort grade | Retained device-defined indicator; not calibrated force |

The names preserve the interface terminology. They do not establish that a device “mean” equals the average of the transmitted waveform, that “power” is in watts, or that “level” measures Newtons. EMG-Lab computes its own mean, variance and RMS from fields 2 and 6.

The reported waveform often lies between 0 and 4095. These are monitored as **provisional boundary codes**. This observation is consistent with a 12-bit-style output representation, but does not establish the ADC architecture, effective resolution or physical input rails.

## 4. Parsing rules in `server.py`

1. Accumulate incoming bytes across serial reads.
2. Synchronize on a newline and discard the initial partial candidate.
3. Split each subsequent complete line by ASCII comma.
4. Accept exactly eight signed decimal integer fields, each with 1–10 digits.
5. Count malformed complete candidates and continue receiving.
6. Bound an unterminated partial buffer; clear and resynchronize if it exceeds 4096 bytes.

The parser accepts integer values outside 0–4095. It does not clip them, infer an undocumented device range or replace questionable observations with convenient values. Empty lines are ignored. A malformed counter is not a complete transport-loss counter: there is no checksum or device sequence number in the supplied format.

## 5. Saved CSV format

```text
frame,host_elapsed_s,ch1_mean,ch1_adc,ch1_power,ch1_level,ch2_mean,ch2_adc,ch2_power,ch2_level,source_kind
```

| Added column | Definition |
|---|---|
| `frame` | Host-generated valid-frame index since the current connection |
| `host_elapsed_s` | Host monotonic batch-receipt time since connection, in seconds |
| `source_kind` | `device` or `synthetic` for new application exports |

The eight device fields are retained numerically. This is a record of valid parsed fields, not a byte-for-byte log of all serial traffic: malformed lines are counted, not saved in the CSV.

An imported historical file may omit host times or source-kind metadata. The program can still use frame order, but missing provenance cannot be reconstructed from the waveform. Replay indexes identify imported row order; do not treat them as device-generated sequence numbers.

## 6. JSON sidecar and event markers

New recordings include a JSON file with the session label, source, port, baud, start/end metadata, count, sampling-rate value/basis and markers. Each marker stores a label, UTC time, host elapsed time and the **next host frame index**. A mouse click is not synchronized to the device's ADC clock.

The five historical CSVs included in this release have no supplied sidecars. Their trial descriptions and retrospective intervals are documented in [data/README.md](../data/README.md) and the [technical report](../reports/TECHNICAL_REPORT.md).

## 7. Why 115200 is not the sample rate

For an actual 115200-bit/s UART bottleneck with one start bit, eight data bits and one stop bit:

$$
\text{byte capacity}=115200/10=11520\ \text{bytes/s}.
$$

For the 29-byte example:

$$
\text{ideal frame ceiling}=11520/29\approx397.24\ \text{frames/s}.
$$

This is a conditional transport calculation. Variable ASCII length, firmware scheduling, wireless transmission and buffering all affect observed reception. A 1.67-microsecond ADC conversion specification describes another part of the pipeline. Neither number establishes a uniform time step between exported waveform values.

Consequently, default analyses use **frames** and **cycles/frame**. Converting to seconds or Hz requires a stated, justified rate; an assumed reception rate must remain labeled as an assumption.
