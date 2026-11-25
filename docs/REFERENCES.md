# References and evidence sources

Access/review date: 25 November 2026. The project combines device documentation, official numerical-library references, educational background and its own source data. A reference to a method is not validation of this particular board or experiment.

## Device-specific sources

1. **Sichiray / 思知瑞产品资料库, “双通道肌电传感器”.** Product instructions supplied by the project owner in the project conversation. Source for the eight-field ASCII interface, 115200 baud, electrode color descriptions, stated analog-output range, conversion-time wording and conflicting supply descriptions. The repository summarizes the interface; it does not reproduce the complete manual, bundled proprietary Windows software or vendor contact details.
2. **Sichiray, dual-channel EMG sensor product page.** [Official page](https://www.sichiray.com/portfolio/items/emg-sensor). Confirms the described analog acquisition and MCU processing architecture. The accessible product page is shorter than the owner-supplied instructions and does not independently settle timing, gain or electrical-safety questions.

## Surface EMG methodology

3. **SENIAM: Placement and fixation of the sensor.** [Official recommendations](https://seniam.org/fixation.htm). Discusses bipolar electrode spacing, alignment with fibers, secure fixation and application-dependent reference locations. The official page was available through indexed retrieval; direct page fetches were intermittent during preparation.
4. **SENIAM: Determination of sensor location.** [Official recommendations](https://www.seniam.org/sensorlocation.htm). Background for why sensor location, neighboring muscles, tendons and motor points affect surface observations. This release does not claim that its historical photographs implement a verified SENIAM montage.
5. **Hermens HJ, Freriks B, Disselhorst-Klug C, Rau G.** Development of recommendations for SEMG sensors and sensor placement procedures. *Journal of Electromyography and Kinesiology*. 2000;10(5):361–374. [DOI: 10.1016/S1050-6411(00)00027-4](https://doi.org/10.1016/S1050-6411(00)00027-4). [PubMed record](https://pubmed.ncbi.nlm.nih.gov/11018445/). Original methodology reference underlying SENIAM. Do not infer a specific knee/forehead protocol from the citation.

## Numerical methods and implementation

6. **SciPy, `scipy.signal.welch`.** [Official documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html). Welch PSD, window/segment settings and density scaling.
7. **SciPy, `scipy.signal.correlate`.** [Official documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.correlate.html). Discrete correlation definition and input-order convention. EMG-Lab explicitly applies its own centering and normalization.
8. **SciPy, `scipy.signal.sosfiltfilt`.** [Official documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfiltfilt.html). Forward-backward filtering with second-order sections and edge padding.
9. **SciPy, `scipy.signal.periodogram`.** [Official documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.periodogram.html). Background for the periodogram demonstration in the notes.

## Background reading used by the interactive notes

10. **OpenStax, Anatomy and Physiology 2e, 12.4: The Action Potential.** [Chapter](https://openstax.org/books/anatomy-and-physiology-2e/pages/12-4-the-action-potential).
11. **OpenStax, Anatomy and Physiology 2e, 10.3: Muscle Fiber Contraction and Relaxation.** [Chapter](https://openstax.org/books/anatomy-and-physiology-2e/pages/10-3-muscle-fiber-contraction-and-relaxation).
12. **Analog Devices, Basics of Band-Limited Sampling and Aliasing.** [Technical article](https://www.analog.com/en/resources/technical-articles/basics-of-bandlimited-sampling-and-aliasing.html).
13. **Analog Devices, Types of ADCs and DACs.** [Technical article](https://www.analog.com/en/resources/technical-articles/types-of-adcs-and-dacs.html).

These background links are retained from the earlier educational notes. The diagrams and interactive values are project-created teaching models; they are not vendor circuit schematics or measured cell/EMG data.

## Project evidence

- [Original supplied CSV files and their provenance](../data/README.md).
- [Reproducible analysis script](../scripts/analyze_recordings.py).
- [Technical report](../reports/TECHNICAL_REPORT.md) and [generated results](../reports/RESULTS.md).
- [Software verification status](../TEST_STATUS.md).

Statements about this project's measurements should cite the data/report, not a general reference. Statements about circuit specifications should identify whether they are manufacturer-described, measured, assumed or unknown.
