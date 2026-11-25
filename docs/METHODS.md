# Analysis and experimental methods

This document describes how the software computes its outputs and how the bundled self-recordings are interpreted. Numerical results and figures are in the [technical report](../reports/TECHNICAL_REPORT.md); data provenance is in [data/README.md](../data/README.md).

## 1. Observation and units

Let $x_c[n]$ be a transmitted waveform value from channel $c$, using protocol fields 2 and 6. It is a manufacturer-filtered ADC-like count. Without confirmed gain, offset, resolution and reference voltage, it is not converted to microvolts or millivolts.

In a selected segment of $N$ values, EMG-Lab reports the raw mean and range. The boundary-code percentage is

$$
100\,N^{-1}\sum_n\mathbf{1}\{x[n]\in\{0,4095\}\}.
$$

This is a transparent diagnostic of repeated boundary values. It does not prove which analog or digital stage saturated. Zero boundary occupancy also does not demonstrate a clean physiological signal.

## 2. Mean removal, RMS and variance

For a chosen segment:

$$
\bar{x}=N^{-1}\sum_n x[n],\qquad y[n]=x[n]-\bar{x],
$$

$$
\operatorname{RMS}(y)=\sqrt{N^{-1}\sum_n y[n]^2},\qquad
\operatorname{MAV}(y)=N^{-1}\sum_n|y[n]|.
$$

With this centering, RMS equals the **population** standard deviation of the original segment, using denominator $N$. The identity for uncentered data is

$$
\operatorname{RMS}(x)^2=\operatorname{Var}_N(x)+\bar{x}^{\,2}.
$$

The displayed application removes one mean from the complete selected analysis window, then computes trailing RMS within that processed window. It does not re-center every trailing subwindow. The report's activity-segment summaries center each specified segment independently. These procedures answer related questions but need not produce identical numbers.

The device's transmitted `ch1_mean` and `ch2_mean` indicators are not used as baseline estimates.

## 3. Sliding RMS

For a trailing window of $w$ frames, away from the start:

$$
r[n]=\sqrt{\frac1w\sum_{j=n-w+1}^{n}y[j]^2}.
$$

At the start of the selected window, the application uses the available prefix and its actual length. A larger window reduces short-term variation and blurs activity boundaries. A 60-frame window is not automatically a 200-ms window: that conversion would require a justified 300-frame/s sampling assumption.

Overlapping windows share observations. They are not independent experimental repetitions.

## 4. Optional digital filters

The application implements Butterworth low-pass, high-pass and band-pass choices, plus a notch option. A frequency in Hz is accepted only when a sampling rate has been supplied. Cutoffs must lie below the stated Nyquist frequency. The notch uses quality factor $Q=30$.

Filtering uses forward-backward second-order sections on the currently selected window. SciPy documents this operation as forward-backward filtering; it uses data on both sides of an interior point. It therefore describes window analysis, not a causal hardware filter or measured device bandwidth. Edge behavior and short windows require care. [SciPy reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfiltfilt.html)

The recorded CSV remains unchanged. An attractive filtered curve cannot recover information already lost to clipping or aliasing.

## 5. FFT and Welch PSD

The FFT view subtracts the selected-window mean, applies a periodic Hann window and scales the one-sided amplitude by the window sum. Interior positive-frequency amplitudes are doubled; DC and an even-length Nyquist bin are not. Amplitude remains in counts.

The application PSD uses Welch averaging with up to 256 frames per segment, half-segment overlap and constant detrending. The report uses longer, explicitly documented segments where useful for spectral inspection. Welch estimation averages modified periodograms from overlapping segments. [SciPy reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html)

With unknown sample rate, the calculation uses $f_s=1$ for **normalized frequency**, so the horizontal axis is cycles/frame and density is counts²/(cycles/frame). This does not assert one physical sample per second. Integrated PSD is computed as

$$
P\approx\Delta f\sum_k S[k].
$$

Windowing, segment detrending and finite-record effects mean this estimate need not exactly equal the raw, uncentered RMS squared. Mean and median frequency summarize the estimated spectrum; they do not establish muscle fatigue.

Narrow spectral peaks in the recordings are described as possible interference. A peak mapping near 50 Hz after multiplying by the mean reception rate is **consistent with** mains interference under that rate assumption, not an independent measurement of the ADC clock or proof of the source.

## 6. ACF and cross-correlation

The application centers each input sequence before correlation. For ACF it uses the full-sequence energy in the denominator:

$$
r_{xx}[k]=\frac{\sum_{n=0}^{N-1-k}(x[n]-\bar{x})(x[n+k]-\bar{x})}{\sum_{n=0}^{N-1}(x[n]-\bar{x})^2}.
$$

For CCF it computes SciPy's `correlate(y, x)` and normalizes by the product of the complete centered-sequence norms. With this order, a positive peak lag means that CH2 follows CH1. This is not the Pearson correlation of two separately re-centered, truncated sequences at every lag. [SciPy convention](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.correlate.html)

For constant inputs the normalized quantity is undefined and is reported as unavailable. The displayed peak is the largest signed coefficient, not necessarily the largest absolute coefficient. At zero lag, the normalized result agrees with Pearson correlation for the same nonconstant inputs.

Correlation can be computed on waveforms or RMS envelopes. The envelopes are smoother and overlapping-window dependence changes their correlation structure. ACF repetition suggests temporal structure; CCF alignment suggests an association. Neither establishes neural causality, electrical isolation, muscle force or anatomical selectivity.

## 7. Regression demonstration

The implemented model is

$$
\widehat{z}=\beta_0+\beta_1\operatorname{RMS}_{CH1}+\beta_2\operatorname{RMS}_{CH2}.
$$

Features come from non-overlapping, fully labeled windows. Windows do not cross a stated trial boundary. The fit uses ordinary least squares with an intercept. When trial labels are provided, the last approximately 25% of distinct trials in first-seen order are held out. Without trials, the last approximately 25% of windows are held out chronologically and the output identifies this as within-recording evaluation.

The application reports held-out RMSE, MAE and $R^2$. A constant test target makes $R^2$ undefined. Rank-deficient training features are rejected. The bundled labeled dataset is generated to have a simple relationship with its features; a high score checks that the software pipeline works. The measured self-recordings contain no independent force or movement targets, so this release makes no real-world prediction-performance claim.

## 8. Historical self-recording conditions

All descriptions below record what the owner reported doing. They are not a prospective validated electrode-placement protocol.

The first two saved sessions were floating-cable bench recordings; the owner reconnected between runs. The first single-channel activation attempt had a wrist-region reference and substantial interference/boundary values. In the next attempt, the owner moved the reference to the knee and used stronger contractions. Because both factors changed, improved signal behavior cannot be attributed to reference placement alone.

For the final dual-channel session, CH1 was assigned to the triceps and CH2 to the biceps; the owner reported a forehead reference. Five intended actions were performed, each in two consecutive repetitions, with approximately five-second rest intervals:

| Condition | Owner-described posture | Intended action | Repetitions |
|---|---|---|---:|
| C1 | Neutral arm position | Biceps and triceps together | 2 |
| C2 | Extended elbow | Both muscles together | 2 |
| C3 | Extended elbow | Triceps, while trying to relax biceps | 2 |
| C4 | Flexed elbow | Both muscles together | 2 |
| C5 | Flexed elbow | Biceps, while trying to relax triceps | 2 |

These are intention labels from the owner's account. Elbow angles, force, motor-unit discharge and true isolation of either muscle were not independently measured.

## 9. Retrospective segmentation and evidence level

The report uses host-relative time and a stated activity rule to identify ten approximate activity intervals. In one-second bins, centered RMS above 45 counts in either channel flags activity; contiguous flagged bins form candidate intervals. Pairing consecutive intervals follows the owner's confirmed action order. The exact intervals and calculations are saved with the report.

This threshold was chosen after observing the session. It is an exploratory segmentation method, not an independently validated onset detector. Boundaries are not synchronized stimulus/event timestamps. The five condition summaries aggregate two repetitions each; thousands of frames do not increase the number of independently performed actions.

Cross-channel counts cannot be read as a muscle-force ratio because placement and channel gains were not calibrated. Activity in both channels during an intended selective action could reflect co-contraction, crosstalk, motion, common interference or other aspects of the measurement. The data establish usable recording and exploratory signal differences, not unique physiological mechanisms.

## 10. Reference electrode observations

The report preserves wrist, knee and forehead locations as historical setup information. It does not recommend the latter two as universally superior. SENIAM's placement guidance makes reference location application-dependent and discusses sensor location, orientation, spacing and fixation. Its general reference examples include the wrist, C7 and ankle; it does not validate this kit's knee/forehead configuration. [SENIAM guidance](https://seniam.org/fixation.htm)

A future reference-site comparison would hold posture, effort, measuring-electrode placement, cable routing and acquisition settings constant, then repeat and counterbalance the site changes. That controlled comparison was not performed in this release.
