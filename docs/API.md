# Software architecture and local API — v1.1

This document describes the implementation in [`server.py`](../server.py) and [`web/app.js`](../web/app.js). It is intended for readers who want to inspect or extend the acquisition software. It does not describe new firmware or a custom analog circuit.

## 1. Components

| Component | Implementation | Responsibility |
| --- | --- | --- |
| Commercial acquisition board | Existing analog front end, ADC and MCU firmware | Produce the manufacturer's eight-field serial stream |
| Wireless USB receiver | Existing module, presented as a serial device | Deliver bytes to macOS; observed port `/dev/cu.usbserial-10` |
| Serial reader | `Lab.run`, `Framer`, pySerial | Assemble fragmented reads into frames and count malformed lines |
| Session state | `Lab`, protected by a reentrant lock | Keep the most recent 12,000 frames, receipt statistics, recording and replay state |
| Local HTTP service | Python `ThreadingHTTPServer` | Serve the UI and numerical APIs on `127.0.0.1` |
| Browser interface | HTML, CSS, vanilla JavaScript, Canvas | Poll the state approximately every 400 ms and draw the selected window |
| Numerical analysis | NumPy and SciPy functions | Window statistics, filtering, RMS, spectra, correlations and OLS |
| Disk output | CSV and JSON | Preserve valid device fields, host receipt times, session metadata and markers |

The app opens a serial port for reading and does not write application commands to it. Opening a serial port can still change serial control-line state according to the driver; “receive only” is not a hardware-isolation guarantee. GitHub Pages can serve the static notes, but the Python service and hardware connection run on the local computer.

## 2. Device frame and stored fields

Default baud rate: **115200**. The application uses pySerial's default 8 data bits, no parity and one stop bit. The manufacturer describes a CRLF prefix followed by eight ASCII integers separated by commas. In a continuous stream, the next CRLF also terminates the previous payload:

```text
\r\n2107,2112,5,0,2111,2103,6,0\r\n...
```

The parser synchronizes at a newline, discards the initial incomplete or uncertain line, strips surrounding whitespace, requires exactly eight integer fields, and accepts signed values containing up to ten digits. It does not treat a valid integer as a calibrated physical measurement. Malformed lines increment a counter; they are not inserted into the numeric CSV. A partial line longer than 4,096 bytes is discarded to bound parser memory.

| Payload position | CSV field | Manufacturer description / treatment |
| --- | --- | --- |
| 1 | `ch1_mean` | CH1 device-computed “mean”; retain as reported |
| 2 | `ch1_adc` | CH1 manufacturer-described lightly filtered ADC value; the plotted waveform |
| 3 | `ch1_power` | CH1 device-specific power output; algorithm and physical units unverified |
| 4 | `ch1_level` | CH1 device-specific effort level; not calibrated force |
| 5 | `ch2_mean` | CH2 device-computed “mean”; retain as reported |
| 6 | `ch2_adc` | CH2 manufacturer-described lightly filtered ADC value; the plotted waveform |
| 7 | `ch2_power` | CH2 device-specific power output |
| 8 | `ch2_level` | CH2 device-specific effort level |

The app's calculated mean and variance are recomputed from the selected ADC data. They do not come from the manufacturer's `*_mean` fields. The source files include values of 0 and 4095; their frequency is reported as **provisional boundary-code occupancy**, without claiming independent verification of ADC resolution.

A saved CSV has this header:

```csv
frame,host_elapsed_s,ch1_mean,ch1_adc,ch1_power,ch1_level,ch2_mean,ch2_adc,ch2_power,ch2_level,source_kind
```

`frame` is a host counter assigned after parsing. `host_elapsed_s` is monotonic time since the current connection opened. Frames arriving in one read batch share a timestamp. `source_kind` is `device` or `synthetic` for recordings made by this software. No device-side sequence number or acquisition timestamp is available in this protocol.

The paired JSON file records the label, source, port, baud, start/end UTC times, selected sampling-rate value and basis, boundary-code assumption, valid/malformed frame counts and markers. Each marker includes its host time and the next host frame number. Display filtering never modifies the raw saved fields.

## 3. UI settings and their API equivalents

For the bundled hardware CSVs, the conservative starting settings are **sampling rate blank**, **Remove window mean checked**, **Digital filter None**, **RMS window 60 frames**. This makes no assumption about the physical sample clock.

| UI label | JSON key | Default / meaning |
| --- | --- | --- |
| Sampling rate (Hz) | `fs` | `null`; unknown |
| Independently verified sampling rate | `fs_confirmed` | `false`; a user declaration, not an app measurement |
| Remove window mean | `center` | `true`; subtract the mean of the whole selected window |
| Digital filter | `filter` | `"none"`, or `"lowpass"`, `"highpass"`, `"bandpass"`, `"notch"` |
| Low (Hz) | `low` | `20`; high-pass or band-pass lower cutoff |
| High (Hz) | `high` | `100`; low-pass or band-pass upper cutoff |
| Notch (Hz) | `notch` | `50`; Q = 30 |
| RMS window (frames) | `window` | `60` |
| Maximum lag (frames) | `lag` | `120`; restricted to at most half the selected length and 500 |
| Correlate RMS envelopes | `corr_rms` | `false`; otherwise correlate the processed waveforms |

The analysis request also contains `source` (`"stream"` or `"replay"`), `n` (selected frames, at most 12,000), and optional replay `end` (exclusive row position). At least eight frames are required for analysis. Import indexes restart at zero in CSV row order; original `frame` values are not used as replay indexes. Imported host times are retained but do not establish a uniform sampling clock.

Example JSON body for `/api/analyze`:

```json
{
  "source": "replay",
  "n": 1000,
  "end": 3000,
  "config": {
    "fs": null,
    "fs_confirmed": false,
    "center": true,
    "filter": "none",
    "window": 60,
    "lag": 120,
    "corr_rms": false
  }
}
```

### Sampling-rate provenance

- `unknown`: frequencies are in cycles/frame and correlations use frame lags.
- `user-assumed`: the user entered a rate; Hz and milliseconds are conditional on that assumption. The “Use reception rate as assumption” button does this explicitly.
- `user-confirmed`: the user marked the entered rate as independently verified. The software has not itself measured the device clock.
- `synthetic-known`: only the built-in generator or built-in labeled example has its defined 300 Hz rate supplied automatically.

In v1.1, importing a CSV whose rows say `source_kind=synthetic` identifies its **declared provenance**, not its sampling rate. Such an import defaults to `unknown`, even if it originally came from the built-in generator. The user can supply the generating rate when it is known.

## 4. Numerical definitions

All amplitude values remain in **device counts**. The following choices are implemented rather than inferred from plot appearance:

- **Mean removal:** one mean for the entire selected channel window, followed by optional filtering. It is not an independently estimated resting baseline.
- **Filtering:** fourth-order Butterworth low/high/band-pass, or IIR notch Q = 30, applied with `sosfiltfilt`. At least 40 frames and a supplied sampling rate are required. This is zero-phase analysis of the displayed window; edge effects can change as that window moves. It is not a causal real-time hardware filter.
- **RMS/MAV/variance/SD:** calculated on processed values. Raw mean, raw SD and min/max use the unprocessed ADC field. Variance and SD use division by N, not N − 1.
- **Sliding RMS:** a trailing window over processed values. The first points use the available shorter prefix, so the returned array has one value per input frame.
- **FFT:** one-sided amplitude spectrum after mean removal and a periodic Hann window; coherent-gain normalization; doubled positive frequencies excluding DC and the even-length Nyquist bin.
- **Welch PSD:** segment length `min(256, N)`, 50% overlap, constant detrending and density scaling. The frequency scale is Hz only when a rate is supplied. Total spectral power uses the sum of PSD bins times bin spacing. It need not equal the uncentered raw RMS squared.
- **ACF:** subtract the channel mean, correlate with itself, then divide by its total squared magnitude. The denominator is fixed over lags, so finite-record ACF peaks shrink as overlap decreases.
- **CCF:** `scipy.signal.correlate(CH2, CH1)` after global centering, divided by the product of channel norms. Positive lag means CH2 follows CH1 under this convention. The reported peak is the maximum signed CCF value within the requested lag range, not the largest absolute correlation. Constant signals return an undefined correlation.
- **Regression:** an intercept plus two processed RMS features; non-overlapping windows that stay within a contiguous trial segment; windows without a full numeric target are omitted. At least 12 usable windows are required. With trial labels, the last roughly 25% of distinct trials in first-seen order are held out; at least three trials are required. Otherwise the last roughly 25% of windows are held out chronologically. Training features must have full rank. RMSE, MAE and R² describe only the held-out subset; R² is undefined for a constant held-out target.

The script used for the published case-study figures has its own explicit analysis settings. In particular, longer PSD segments and individually centered experimental segments should not be confused with this UI's moving-window defaults. See [`scripts/analyze_recordings.py`](../scripts/analyze_recordings.py).

## 5. HTTP endpoints

Default base URL: `http://127.0.0.1:8765`. JSON requests use `Content-Type: application/json`. Unless stated otherwise, success returns JSON and validation errors return status 400 with `{"error": "..."}`. Unknown routes return 404; unrelated Host/Origin values return 403.

| Method | Path | Request / result |
| --- | --- | --- |
| GET | `/` | Main local UI |
| GET | `/app.js`, `/style.css` | UI assets |
| GET | `/notes` | Self-contained interactive notes |
| GET | `/api/ports` | Available serial ports with device path and description |
| GET | `/api/state?n=1000` | Current connection status, recent rows, rate, counters, recording and replay metadata |
| POST | `/api/connect` | `{"mode":"live","port":"/dev/cu.usbserial-10","baud":115200}` or `{"mode":"demo"}` |
| POST | `/api/disconnect` | `{}`; stops the reader and any active recording |
| POST | `/api/window` | Selection object; returns rows and built-in-rate flag |
| POST | `/api/analyze` | Selection plus config; returns metrics, processed series, RMS, spectra and correlations |
| POST | `/api/record/start` | `{"label":"E03","config":{}}`; returns a recording ID |
| POST | `/api/record/stop` | `{}`; closes CSV and completes JSON metadata |
| POST | `/api/mark` | `{"label":"rest_start"}`; append a host-timed marker |
| GET | `/api/records` | List saved recording IDs in the configured recordings directory |
| GET | `/api/download/<id>.csv` | Download valid device fields and host receipt times |
| GET | `/api/download/<id>.json` | Download session metadata and markers |
| POST | `/api/replay` | UTF-8 CSV body with `Content-Type: text/csv`; optional URL-encoded `X-Filename` |
| POST | `/api/example` | `{}`; load the built-in labeled synthetic dataset |
| GET | `/example.csv` | Download the synthetic example |
| POST | `/api/regression` | `{"config":{"window":60}}`; fit the full imported labeled dataset |

The maximum request body is 32 MiB; CSV import allows at most 200,000 data rows and requires all eight device-field names. Optional `target` and `trial` columns support regression. A `source_kind` column is recommended to retain provenance. Older `check.py` files without host timestamps are accepted. Imported files are held in memory and do not overwrite the originals.

For the row format returned by `/api/state` and `/api/window`, each row is:

```json
[0, 0.123, [2107, 2112, 5, 0, 2111, 2103, 6, 0]]
```

The three elements are the host/replay frame index, host time or `null`, and the eight integer fields. The response field historically named `demo` in `/api/window` means that the selected source is a built-in synthetic source with known rate; use `replay_demo` and `replay_known_fs` from state to distinguish declared synthetic provenance from the known built-in rate.

## 6. Local operation and persistence

`run.command` reuses `~/emg-lab-venv` when available, otherwise a project `.venv`, otherwise creates one. It installs missing pySerial/NumPy/SciPy imports and runs `server.py`. It has no frontend package manager or build step. The notes and UI use local assets.

```bash
bash run.command
# Or, from an already prepared Python environment:
python server.py --no-browser --port 8765 --data-dir ./recordings
```

The service binds to `127.0.0.1`, rejects nonlocal Host and unrelated Origin headers, and serves only the named UI files, notes and valid recording filenames. It does not upload recordings. This remains a local development server; exposing it to a public network is outside the project design.

To reproduce software checks:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

The data-report dependency set adds Matplotlib:

```bash
python -m pip install -r requirements-analysis.txt
python scripts/analyze_recordings.py
```

See [`TEST_STATUS.md`](../TEST_STATUS.md) for the exact tested environment and the distinction between software tests and hardware evidence.
