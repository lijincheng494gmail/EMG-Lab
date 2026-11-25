#!/usr/bin/env python3
"""Reproduce the archived EMG-Lab recording summaries, tables and figures.

Run from any directory: python scripts/analyze_recordings.py
Requires NumPy, SciPy and Matplotlib. Raw CSV files are never modified.
All amplitudes remain in device counts. Spectra use cycles/received frame.
The ten activity intervals are selected retrospectively, not event ground truth.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy
from scipy import signal


ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("ch1_mean", "ch1_adc", "ch1_power", "ch1_level",
          "ch2_mean", "ch2_adc", "ch2_power", "ch2_level")
RECORDS = [
    ("F01", "20261125_223305_3a8c7d.csv", "Floating CH2 lead, first capture"),
    ("F02", "20261125_223514_6791e0.csv", "Floating CH2 lead, after reconnect"),
    ("S01", "20261125_230211_2835c7.csv", "Initial single-channel recording"),
    ("S02", "20261125_231208_8ff529.csv", "Single-channel, knee reference and stronger effort"),
    ("D01", "20261125_232138_110cad.csv", "Dual-channel triceps and biceps recording"),
]
CONDITIONS = [
    "Neutral arm, intended co-contraction",
    "Extended elbow, intended co-contraction",
    "Extended elbow, intended triceps activation",
    "Flexed elbow, intended co-contraction",
    "Flexed elbow, intended biceps activation",
]
COLORS = ("#226ba3", "#d26924")


@dataclass
class Recording:
    ident: str
    path: Path
    description: str
    frame: np.ndarray
    host: np.ndarray
    t: np.ndarray
    values: np.ndarray
    source_kinds: list[str]

    @property
    def x(self):
        return self.values[:, [1, 5]].astype(float)


def load_recording(path, ident, description):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        needed = {"frame", "host_elapsed_s", "source_kind", *FIELDS}
        if not needed.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing expected columns in {path.name}")
        rows = list(reader)
    if len(rows) < 2:
        raise ValueError(f"Too few rows in {path.name}")
    frame = np.asarray([int(r["frame"]) for r in rows], dtype=np.int64)
    host = np.asarray([float(r["host_elapsed_s"]) for r in rows])
    values = np.asarray([[int(r[k]) for k in FIELDS] for r in rows], dtype=np.int64)
    if not np.all(np.isfinite(host)) or np.any(np.diff(host) < 0):
        raise ValueError(f"Non-finite or decreasing host timestamps in {path.name}")
    if host[-1] <= host[0]:
        raise ValueError(f"No positive time span in {path.name}")
    return Recording(ident, path, description, frame, host, host - host[0],
                     values, sorted(set(r["source_kind"] for r in rows)))


def centered_rms(x):
    """RMS after subtracting this segment's own mean; ddof=0."""
    x = np.asarray(x, dtype=float)
    return np.sqrt(np.mean((x - x.mean(axis=0)) ** 2, axis=0))


def spectrum(x, nperseg=2048):
    n = min(nperseg, len(x))
    return signal.welch(x, fs=1.0, window="hann", nperseg=n,
                        noverlap=n // 2, detrend="constant", scaling="density")


def summarize(rec):
    dt = np.diff(rec.host)
    span = float(rec.t[-1])
    result = {
        "record_id": rec.ident, "filename": rec.path.name,
        "description": rec.description,
        "sha256": hashlib.sha256(rec.path.read_bytes()).hexdigest(),
        "size_bytes": rec.path.stat().st_size, "rows": len(rec.frame),
        "first_host_elapsed_s": float(rec.host[0]),
        "last_host_elapsed_s": float(rec.host[-1]), "host_span_s": span,
        "received_frames_per_s": float((len(rec.frame) - 1) / span),
        "first_frame_index": int(rec.frame[0]), "last_frame_index": int(rec.frame[-1]),
        "nonunit_frame_increments": int(np.count_nonzero(np.diff(rec.frame) != 1)),
        "equal_adjacent_host_timestamps": int(np.count_nonzero(dt == 0)),
        "equal_adjacent_host_timestamp_pct": float(100 * np.mean(dt == 0)),
        "decreasing_host_timestamps": int(np.count_nonzero(dt < 0)),
        "source_kinds": rec.source_kinds, "channels": {}, "device_fields": {},
    }
    for c in range(2):
        x = rec.x[:, c]
        f, p = spectrum(x)
        peak = int(np.argmax(p[1:])) + 1
        result["channels"][f"ch{c+1}"] = {
            "mean_counts": float(x.mean()), "centered_rms_counts": float(centered_rms(x)),
            "minimum_counts": int(x.min()), "maximum_counts": int(x.max()),
            "zero_count": int(np.count_nonzero(x == 0)),
            "code_4095_count": int(np.count_nonzero(x == 4095)),
            "boundary_code_pct": float(100 * np.mean((x == 0) | (x == 4095))),
            "largest_positive_psd_peak_cycles_per_frame": float(f[peak]),
        }
    for i, name in enumerate(FIELDS):
        x = rec.values[:, i]
        result["device_fields"][name] = {
            "minimum": int(x.min()), "maximum": int(x.max()),
            "unique_values": int(len(np.unique(x))),
        }
    return result


def interval_mask(rec, lo, hi):
    return (rec.t >= lo) & (rec.t < hi)


def one_second_bins(rec):
    result = []
    for lo in range(int(np.floor(rec.t[-1])) + 1):
        mask = interval_mask(rec, lo, lo + 1)
        if not np.any(mask):
            raise ValueError("An empty host-time bin requires manual review")
        rms = centered_rms(rec.x[mask])
        result.append({"start_s": lo, "end_s": lo + 1, "frames": int(mask.sum()),
                       "ch1_centered_rms_counts": float(rms[0]),
                       "ch2_centered_rms_counts": float(rms[1]),
                       "selected_at_45_counts": bool(max(rms) > 45)})
    return result


def active_intervals(rec, bins):
    selected = np.asarray([r["selected_at_45_counts"] for r in bins])
    edges = np.diff(np.r_[False, selected, False].astype(int))
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    if len(starts) != 10:
        raise ValueError("Expected ten intervals for the archived condition order; "
                         "review labels before analyzing another dataset")
    result = []
    for i, (lo, hi) in enumerate(zip(starts, ends)):
        m = interval_mask(rec, lo, hi)
        rest_lo, rest_hi = float(lo) - 3.5, float(lo) - .5
        rest = interval_mask(rec, rest_lo, rest_hi)
        rms, rrms = centered_rms(rec.x[m]), centered_rms(rec.x[rest])
        result.append({
            "repetition": i + 1, "condition": i // 2 + 1,
            "repeat_within_condition": i % 2 + 1,
            "intended_action": CONDITIONS[i // 2],
            "start_s": int(lo), "end_s": int(hi), "frames": int(m.sum()),
            "ch1_centered_rms_counts": float(rms[0]),
            "ch2_centered_rms_counts": float(rms[1]),
            "prior_rest_start_s": rest_lo, "prior_rest_end_s": rest_hi,
            "prior_rest_frames": int(rest.sum()),
            "prior_rest_ch1_centered_rms_counts": float(rrms[0]),
            "prior_rest_ch2_centered_rms_counts": float(rrms[1]),
        })
    return result


def condition_means(intervals):
    return [{
        "condition": c, "intended_action": CONDITIONS[c - 1], "repetitions": 2,
        "ch1_mean_of_rep_centered_rms_counts": float(np.mean([
            r["ch1_centered_rms_counts"] for r in intervals if r["condition"] == c])),
        "ch2_mean_of_rep_centered_rms_counts": float(np.mean([
            r["ch2_centered_rms_counts"] for r in intervals if r["condition"] == c])),
    } for c in range(1, 6)]


def boundary_sensitivity(rec, intervals):
    result = []
    for trim in (0.0, .25, .5):
        rms = np.asarray([centered_rms(rec.x[interval_mask(
            rec, r["start_s"] + trim, r["end_s"] - trim)]) for r in intervals])
        means = rms.reshape(5, 2, 2).mean(axis=1)
        for c in range(5):
            result.append({"trim_each_edge_s": trim, "condition": c + 1,
                           "ch1_mean_centered_rms_counts": float(means[c, 0]),
                           "ch2_mean_centered_rms_counts": float(means[c, 1]),
                           "ch2_condition5_over_condition3": float(means[4, 1] / means[2, 1])})
    return result


def single_phases(rec, halfwidth=.005):
    f_all, p_all = spectrum(rec.x[:, 1])
    positive = np.flatnonzero((f_all > 0) & (f_all < .25))
    f0 = float(f_all[positive[np.argmax(p_all[positive])]])
    result = []
    for lo in range(0, 35, 5):
        x = rec.x[interval_mask(rec, lo, lo + 5), 1]
        if len(x) < 2:
            continue
        f, p = spectrum(x, nperseg=1024)
        excluded = (np.abs(f - f0) <= halfwidth) | (np.abs(f - 2 * f0) <= halfwidth)
        df = float(f[1] - f[0])
        result.append({
            "record_id": rec.ident, "start_s": lo,
            "nominal_end_s": lo + 5, "observed_last_row_s": float(
                rec.t[interval_mask(rec, lo, lo + 5)][-1]),
            "scheduled_phase": "rest" if lo % 10 == 0 else "activity",
            "frames": len(x), "ch2_centered_rms_counts": float(centered_rms(x)),
            "ch2_boundary_code_pct": float(100 * np.mean((x == 0) | (x == 4095))),
            "selected_peak_cycles_per_frame": f0, "excluded_halfwidth_cycles_per_frame": halfwidth,
            "sqrt_outside_bands_psd_power_counts": float(np.sqrt(np.sum(p[~excluded]) * df)),
        })
    excluded_all = ((np.abs(f_all - f0) <= halfwidth) |
                    (np.abs(f_all - 2 * f0) <= halfwidth))
    meta = {"record_id": rec.ident, "selected_peak_cycles_per_frame": f0,
            "halfwidth_cycles_per_frame": halfwidth,
            "full_record_selected_bands_power_fraction": float(p_all[excluded_all].sum() / p_all.sum())}
    return result, meta


def band_sensitivity(rec):
    result = []
    for halfwidth in (.003, .005, .01, .015):
        phases, _ = single_phases(rec, halfwidth)
        key = "sqrt_outside_bands_psd_power_counts"
        rest = np.mean([r[key] for r in phases if r["scheduled_phase"] == "rest"])
        active = np.mean([r[key] for r in phases if r["scheduled_phase"] == "activity"])
        result.append({"excluded_halfwidth_cycles_per_frame": halfwidth,
                       "mean_rest_outside_bands_amplitude_counts": float(rest),
                       "mean_activity_outside_bands_amplitude_counts": float(active),
                       "activity_over_rest_ratio": float(active / rest)})
    return result


def save_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def table(headers, rows):
    return ("| " + " | ".join(headers) + " |\n| " + " | ".join(["---"] * len(headers)) +
            " |\n" + "\n".join("| " + " | ".join(map(str, r)) + " |" for r in rows))


def write_results(path, summaries, intervals, means, phases, band_meta, band_sens, edge_sens):
    total = sum(s["rows"] for s in summaries)
    txt = f"""# Recomputed results

Generated by [`scripts/analyze_recordings.py`](../scripts/analyze_recordings.py).
This appendix reports the supplied CSVs. It does not infer device sample timing,
muscle force, electrical safety, or unseen packet loss.

## Recording overview

There are **{total:,} received frames** in five files. Host spans use the first
and last row; rate is `(rows - 1) / span`. This convention differs slightly from
`rows / stopwatch duration` in earlier console tests.

"""
    txt += table(["ID", "Rows", "Host span (s)", "Received frames/s", "CH1 centered RMS", "CH2 centered RMS", "CH2 code-boundary %"], [
        [s["record_id"], f'{s["rows"]:,}', f'{s["host_span_s"]:.6f}', f'{s["received_frames_per_s"]:.5f}',
         f'{s["channels"]["ch1"]["centered_rms_counts"]:.2f}', f'{s["channels"]["ch2"]["centered_rms_counts"]:.2f}',
         f'{s["channels"]["ch2"]["boundary_code_pct"]:.2f}'] for s in summaries])
    txt += "\n\nAll amplitudes above are in device counts. CH1 boundary occupancy is 0% in all five files.\n\n"
    txt += "## Timestamp and frame checks\n\n"
    txt += table(["ID", "Duplicate adjacent host times", "Duplicate fraction %", "Nonunit host-frame increments", "Decreasing host times"], [
        [s["record_id"], s["equal_adjacent_host_timestamps"], f'{s["equal_adjacent_host_timestamp_pct"]:.3f}',
         s["nonunit_frame_increments"], s["decreasing_host_timestamps"]] for s in summaries])
    txt += "\n\nHost indices are assigned by the receiving program. A continuous index cannot establish that every hardware sample arrived.\n\n"
    txt += "## D01: retrospective activity intervals\n\nEach row was selected using one-second bins with centered RMS >45 counts in either channel.\nTime is relative to the first CSV row. CH1 is the triceps lead; CH2 is the biceps lead.\n\n"
    txt += table(["Rep", "Condition", "Host interval (s)", "CH1 RMS", "CH2 RMS", "Prior-rest CH1 RMS", "Prior-rest CH2 RMS"], [
        [r["repetition"], f'C{r["condition"]}', f'{r["start_s"]}–{r["end_s"]}',
         f'{r["ch1_centered_rms_counts"]:.2f}', f'{r["ch2_centered_rms_counts"]:.2f}',
         f'{r["prior_rest_ch1_centered_rms_counts"]:.2f}', f'{r["prior_rest_ch2_centered_rms_counts"]:.2f}'] for r in intervals])
    txt += "\n\nPrior rest is `[start − 3.5 s, start − 0.5 s)`. It is another retrospective comparison interval.\n\n"
    txt += "## D01: mean of the two repetition-level amplitudes\n\n"
    txt += table(["Condition", "Intended action", "CH1 mean RMS", "CH2 mean RMS"], [
        [f'C{r["condition"]}', r["intended_action"],
         f'{r["ch1_mean_of_rep_centered_rms_counts"]:.2f}', f'{r["ch2_mean_of_rep_centered_rms_counts"]:.2f}'] for r in means])
    txt += "\n\nThese are equal-weight averages of two RMS values, not RMS computed on pooled samples. They are not normalized force or between-person estimates.\n\n"
    txt += "## S01 and S02: planned five-second phases\n\nPhase boundaries follow the proposed schedule; no synchronized event log was supplied.\nThe final rest phase ends when each file ends. The outside-band quantity is the square root\nof the Welch PSD integral outside two selected bands, **not** a filtered-waveform RMS.\n\n"
    txt += table(["ID", "Scheduled phase", "Nominal interval (s)", "CH2 RMS", "Boundary %", "Outside-band amplitude"], [
        [r["record_id"], r["scheduled_phase"], f'{r["start_s"]}–{r["nominal_end_s"]}',
         f'{r["ch2_centered_rms_counts"]:.2f}', f'{r["ch2_boundary_code_pct"]:.2f}',
         f'{r["sqrt_outside_bands_psd_power_counts"]:.2f}'] for r in phases])
    txt += "\n\nBand choices are retrospective. Per-phase Welch uses up to 1,024 frames, 50% overlap, Hann windows and constant detrending.\n\n"
    txt += table(["ID", "Selected peak (cycles/frame)", "Band halfwidth", "Power in two bands (%)"], [
        [r["record_id"], f'{r["selected_peak_cycles_per_frame"]:.9f}', r["halfwidth_cycles_per_frame"],
         f'{100*r["full_record_selected_bands_power_fraction"]:.2f}'] for r in band_meta])
    txt += "\n\nFull-record band fractions use 2,048-frame Welch segments. Both bands are centered at `f0` and `2f0`.\n\n"
    txt += "## Sensitivity checks\n\n### S02: changing the excluded-band width\n\n"
    txt += table(["Halfwidth (cycles/frame)", "Rest mean amplitude", "Activity mean amplitude", "Activity/rest"], [
        [r["excluded_halfwidth_cycles_per_frame"], f'{r["mean_rest_outside_bands_amplitude_counts"]:.2f}',
         f'{r["mean_activity_outside_bands_amplitude_counts"]:.2f}', f'{r["activity_over_rest_ratio"]:.3f}'] for r in band_sens])
    txt += "\n\n### D01: trimming both edges of the same ten intervals\n\n"
    txt += table(["Seconds trimmed per edge", "CH2 C5/C3 amplitude ratio"], [
        [r["trim_each_edge_s"], f'{r["ch2_condition5_over_condition3"]:.3f}'] for r in edge_sens if r["condition"] == 1])
    txt += "\n\nThese checks describe sensitivity to selected analysis settings. They do not turn retrospective labels or one participant into independent validation.\n\n"
    txt += "## File identity\n\nThe original CSV bytes are preserved. SHA-256 values, all device-field ranges, versions and full-precision metrics are in [`data/derived/summary.json`](../data/derived/summary.json).\n"
    path.write_text(txt, encoding="utf-8")


def rolling_centered_rms(x, window=60):
    # Valid trailing windows only. Center within each window to avoid a DC term.
    means = np.convolve(x, np.ones(window) / window, mode="valid")
    means2 = np.convolve(x * x, np.ones(window) / window, mode="valid")
    return np.sqrt(np.maximum(means2 - means * means, 0))


def make_figures(folder, records, summaries, intervals, means, phases):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titleweight": "bold", "axes.titlesize": 11,
                         "figure.facecolor": "white", "axes.facecolor": "white",
                         "savefig.facecolor": "white", "axes.grid": True,
                         "grid.alpha": .18, "grid.linewidth": .6,
                         "svg.hashsalt": "emg-lab-analysis-v1.1"})
    folder.mkdir(parents=True, exist_ok=True)

    def save(fig, name):
        fig.savefig(folder / f"{name}.png", dpi=170, bbox_inches="tight")
        fig.savefig(folder / f"{name}.svg", bbox_inches="tight", metadata={"Date": None})
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.8), layout="constrained")
    yy = np.arange(len(summaries))
    labels = ["F01  Floating lead", "F02  Reconnected", "S01  Initial single", "S02  Repositioned", "D01  Dual channel"]
    vals = [s["channels"]["ch2"]["boundary_code_pct"] for s in summaries]
    axes[0].barh(yy, vals, color=COLORS[1], height=.55)
    for y, v in zip(yy, vals):
        axes[0].text(v + 1.4, y, f"{v:.2f}%", va="center", fontsize=9)
    axes[0].set(yticks=yy, yticklabels=labels, xlim=(0, 114), xlabel="Rows at code 0 or 4095 (%)",
                title="CH2 boundary-code occupancy")
    axes[0].invert_yaxis()
    for c, color in enumerate(COLORS):
        rms = [s["channels"][f"ch{c+1}"]["centered_rms_counts"] for s in summaries]
        axes[1].barh(yy + (c - .5) * .29, rms, height=.27, color=color, label=f"CH{c+1}")
    axes[1].set(yticks=yy, yticklabels=[s["record_id"] for s in summaries], xscale="log",
                xlabel="Whole-record centered RMS (counts; log scale)", title="Recorded amplitude across input conditions")
    axes[1].invert_yaxis()
    axes[1].legend(frameon=False, loc="lower right")
    fig.suptitle("Five archived captures: input quality and amplitude", fontsize=15, fontweight="bold")
    save(fig, "quality_overview")

    rec = records[-1]
    fig, axes = plt.subplots(3, 1, figsize=(13, 8.1), sharex=True, layout="constrained",
                             gridspec_kw={"height_ratios": [1, 1, 1.4]})
    for c in range(2):
        axes[c].plot(rec.t, rec.x[:, c] - rec.x[:, c].mean(), color=COLORS[c], lw=.38)
        axes[c].set_ylabel("Centered counts")
        axes[c].set_title(f"CH{c+1}: {'triceps' if c==0 else 'biceps'} lead; record mean removed", loc="left")
    for c in range(2):
        axes[2].plot(rec.t[59:], rolling_centered_rms(rec.x[:, c]), color=COLORS[c],
                     lw=1.15, ls="-" if c == 0 else "--", label=f"CH{c+1} {'triceps' if c==0 else 'biceps'}")
    axes[2].set(ylabel="Centered RMS (counts)", xlabel="Host receipt time relative to first recorded row (s)",
                title="Trailing centered RMS over 60 received frames")
    axes[2].legend(frameon=False, loc="upper left", ncol=2)
    for row in intervals:
        for ax in axes:
            ax.axvspan(row["start_s"], row["end_s"], color="#786b9b", alpha=.085, zorder=-10)
        axes[0].text((row["start_s"] + row["end_s"]) / 2, .97,
                     f'C{row["condition"]}.{row["repeat_within_condition"]}',
                     transform=axes[0].get_xaxis_transform(), ha="center", va="top", fontsize=8,
                     bbox={"facecolor": "white", "alpha": .8, "edgecolor": "none", "pad": 1.5})
    axes[-1].set_xlim(0, rec.t[-1])
    fig.suptitle("D01: ten activity intervals in one dual-channel recording", fontsize=15, fontweight="bold")
    save(fig, "dual_channel_activity")

    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.7), sharey=True, layout="constrained")
    for c, ax in enumerate(axes):
        color = COLORS[c]
        for cond in range(1, 6):
            v = [r[f"ch{c+1}_centered_rms_counts"] for r in intervals if r["condition"] == cond]
            ax.scatter(cond - .06, v[0], c=color, marker="o", s=44, label="Repetition 1" if cond == 1 else None)
            ax.scatter(cond + .06, v[1], c=color, marker="s", s=40, label="Repetition 2" if cond == 1 else None)
            ax.plot([cond - .23, cond + .23], [np.mean(v)] * 2, c="#292635", lw=2,
                    label="Mean of two RMS values" if cond == 1 else None)
            ax.text(cond, max(v) + 9, f"{np.mean(v):.2f}", ha="center", fontsize=9)
        ax.set(xlim=(.5, 5.5), ylim=(0, 210), xticks=range(1, 6), xticklabels=["C1", "C2", "C3", "C4", "C5"],
               xlabel="Intended condition (two consecutive repetitions each)",
               title=f"CH{c+1}: {'triceps' if c==0 else 'biceps'} lead")
    axes[0].set_ylabel("Within-segment centered RMS (device counts)")
    axes[0].legend(frameon=False, fontsize=8, loc="upper left")
    fig.suptitle("D01: amplitudes by intended condition", fontsize=15, fontweight="bold")
    save(fig, "condition_profiles")

    fig, axes = plt.subplots(3, 2, figsize=(12, 8.9), sharex=True, layout="constrained")
    choices = [(records[0], 1), (records[1], 1), (records[2], 1), (records[3], 1), (records[4], 0), (records[4], 1)]
    for ax, (r, c) in zip(axes.flat, choices):
        f, p = spectrum(r.x[:, c])
        ax.semilogy(f[1:], p[1:], color=COLORS[c], lw=.9)
        ax.set(xlim=(0, .5), title=f'{r.ident} · CH{c+1}', ylabel="PSD [counts² / (cycles/frame)]")
    for ax in axes[-1]:
        ax.set_xlabel("Normalized frequency (cycles per received frame)")
    fig.suptitle("Welch spectra without assuming a physical sampling rate", fontsize=15, fontweight="bold")
    save(fig, "normalized_spectra")

    fig, axes = plt.subplots(2, 1, figsize=(11.8, 6.7), sharex=True, layout="constrained")
    for i, ident in enumerate(("S01", "S02")):
        rows = [r for r in phases if r["record_id"] == ident]
        axes[0].plot(range(7), [r["ch2_centered_rms_counts"] for r in rows],
                     color=("#777282", COLORS[1])[i], marker="o", label=ident)
    s2 = [r for r in phases if r["record_id"] == "S02"]
    axes[1].plot(range(7), [r["sqrt_outside_bands_psd_power_counts"] for r in s2],
                 color=COLORS[1], marker="o", label="S02: square root of outside-band PSD integral")
    for ax in axes:
        for i in (1, 3, 5):
            ax.axvspan(i - .45, i + .45, color="#786b9b", alpha=.11, zorder=-10)
        ax.legend(frameon=False, fontsize=9)
        ax.set_xlim(-.4, 6.4)
    axes[0].set(ylabel="Centered RMS (counts)", title="CH2 amplitude in scheduled phases")
    axes[1].set(ylabel="Outside-band amplitude (counts)", xlabel="Scheduled phase; boundaries were not synchronized to a device event log",
                title="Exploratory spectral exclusion in S02", xticks=range(7),
                xticklabels=["Rest\n0–5 s", "Activity\n5–10 s", "Rest\n10–15 s", "Activity\n15–20 s", "Rest\n20–25 s", "Activity\n25–30 s", "Rest\n30 s–end"])
    fig.suptitle("Single-channel attempts: interference and retrospective phase comparisons", fontsize=14, fontweight="bold")
    save(fig, "single_channel_comparison")
    return matplotlib.__version__


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="EMG-Lab repository root")
    parser.add_argument("--skip-figures", action="store_true", help="Write tables and results without Matplotlib")
    args = parser.parse_args()
    root = args.root.resolve()
    derived, reports = root / "data/derived", root / "reports"
    derived.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    records = [load_recording(root / "data/raw" / name, ident, desc) for ident, name, desc in RECORDS]
    summaries = [summarize(r) for r in records]
    bins = one_second_bins(records[-1])
    intervals = active_intervals(records[-1], bins)
    means = condition_means(intervals)
    edge_sens = boundary_sensitivity(records[-1], intervals)
    p1, m1 = single_phases(records[2])
    p2, m2 = single_phases(records[3])
    phases = p1 + p2
    band_sens = band_sensitivity(records[3])
    flat_summary = []
    for s in summaries:
        for c, cs in s["channels"].items():
            flat_summary.append({"record_id": s["record_id"], "filename": s["filename"],
                                 "rows": s["rows"], "host_span_s": s["host_span_s"],
                                 "received_frames_per_s": s["received_frames_per_s"], "channel": c, **cs})
    for name, rows in [
        ("recording_summary.csv", flat_summary), ("dual_channel_1s_bins.csv", bins),
        ("dual_channel_intervals.csv", intervals), ("dual_channel_conditions.csv", means),
        ("dual_channel_boundary_sensitivity.csv", edge_sens),
        ("single_channel_phases.csv", phases), ("single_channel_band_sensitivity.csv", band_sens),
    ]:
        save_csv(derived / name, rows)
    write_results(reports / "RESULTS.md", summaries, intervals, means, phases, [m1, m2], band_sens, edge_sens)
    versions = {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}
    if not args.skip_figures:
        versions["matplotlib"] = make_figures(reports / "figures", records, summaries, intervals, means, phases)
    payload = {
        "analysis_version": "1.1", "recording_date_as_reported": "2026-11-25",
        "total_received_frames": sum(s["rows"] for s in summaries),
        "versions": versions,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "method": {
            "amplitude_unit": "device counts; no voltage or force calibration",
            "centered_rms": "sqrt(mean((x - mean(x))**2)); population normalization",
            "time_axis": "host_elapsed_s minus first host_elapsed_s within each CSV",
            "physical_sampling_rate": "unknown",
            "psd": "Welch; fs=1; Hann; nperseg=min(2048,n); 50% overlap; constant detrending",
            "activity_selection": "retrospective 1 s host bins; either channel centered RMS >45 counts; merge consecutive bins",
            "condition_labels": "author-reported order; each of five intended actions repeated twice",
            "single_channel_phase_labels": "assumed proposed 5 s alternating schedule; no event log supplied",
            "single_channel_exclusion": "peaks f0 and 2*f0; halfwidth0.005 cycles/frame; nperseg1024 per phase",
        },
        "recordings": summaries, "dual_channel_intervals": intervals,
        "dual_channel_conditions": means, "single_channel_band_metadata": [m1, m2],
        "single_channel_band_sensitivity": band_sens,
        "dual_channel_boundary_sensitivity": edge_sens,
    }
    (derived / "summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Analyzed {len(records)} files, {payload['total_received_frames']:,} received frames.")
    print(f"Derived tables: {derived}")
    print(f"Numeric appendix: {reports / 'RESULTS.md'}")
    if not args.skip_figures:
        print(f"Figures: {reports / 'figures'}")


if __name__ == "__main__":
    main()
