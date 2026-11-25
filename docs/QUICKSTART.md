# Quick start

You can inspect the complete software workflow with the built-in demo or the included recordings. Hardware is needed only for live acquisition. The browser page talks to a Python service on your own computer.

## 1. Start the local application

### macOS

Extract the project ZIP in Finder. Open Terminal, type `bash ` **with the space**, drag the project's `run.command` file from Finder into that Terminal window, and press Return. The resulting command will look like:

```bash
bash /path/to/EMG-Lab/run.command
```

The launcher reuses `~/emg-lab-venv` if you created it earlier. Otherwise it uses or creates `.venv` inside the project and installs missing runtime packages. Initial installation needs internet access; routine acquisition and replay do not use a cloud service.

Your browser should open at **http://127.0.0.1:8765/**. If it does not, copy that address into the browser. Keep the Terminal window open while using the application. Press **Control+C** in Terminal to stop it.

If you are already in the project directory, the equivalent command is:

```bash
bash run.command
```

For a busy local web port, use `bash run.command --port 8766` and visit the address printed by the launcher. Opening `web/index.html` directly from Finder will not start the Python service. The separate educational notes at [`index.html`](index.html) can be opened as an offline HTML file.

### Windows

Open PowerShell in the extracted folder containing `server.py`. With Python 3.10 or later installed, run these commands. If your installation uses `python` instead of `py`, use `python` in the first line.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe server.py
```

Open **http://127.0.0.1:8765/** if the browser does not open automatically. Keep PowerShell open while using the app. For hardware acquisition, Windows needs to recognize the USB receiver as a serial port. In the app, replace the prefilled Mac port name with the COM port assigned to your receiver. The project recordings were made on macOS. The Windows hardware path has not been tested for this release.

## 2. First run without hardware

1. In the **left sidebar**, under **DATA SOURCE**, click **Run synthetic demo**. No serial port is opened in this mode.
2. Stay on **01 / Live acquisition**. Two waveforms and the receipt counters should begin updating. The source badge says **SYNTHETIC STREAM**.
3. Select **02 / Signal analysis** in the sidebar. The **Preprocessing & analysis settings** panel appears at the top of this page.
4. Inspect the processed waveform, RMS, amplitude spectrum, PSD, ACF and CCF. The built-in demo uses its known 300 Hz generating rate.
5. Click **Disconnect** in the sidebar when finished. This stops the generator; its last buffer remains available for inspection.

Use the **中文** button in the top-right header to switch the interface language. **Pause display** pauses plotting only: it does not stop acquisition or an active recording.

## 3. Replay the included real dual-channel recording

This path demonstrates the actual saved data without requiring the board.

1. Select **03 / Experiments & replay** in the sidebar.
2. In the **Import & replay** panel, use the file chooser to open:

   ```text
   data/raw/20261125_232138_110cad.csv
   ```

3. The sidebar's **Displayed dataset** changes to **Imported CSV**. This recording contains 30,835 rows. Its import badge states that provenance has not been independently verified by the application; the dataset's documented source is described in [`data/README.md`](../data/README.md).
4. Select **01 / Live acquisition** to see the replay waveform, or **02 / Signal analysis** for calculations on the selected segment. The page name “Live acquisition” also serves as the waveform viewer when an imported dataset is selected.
5. The **replay bar above the page** has a slider, a play button and **End**. The slider selects the **end** of the displayed window. With a 1,000-frame window and the slider at 3,000, the view contains replay rows 2,000–2,999. **End** selects the last window; it does not analyze the entire 30,835-row recording at once.
6. The play button advances through frames for visual inspection. Its speed is illustrative and is not a recovery of the device's acquisition timing.

### Settings for the supplied real data

| Setting | Location | Initial choice |
| --- | --- | --- |
| Displayed dataset | Left sidebar | **Imported CSV** |
| Window size (frames) | Left sidebar | **1000** |
| Sampling rate (Hz) | Left sidebar | **Leave blank** |
| Independently verified sampling rate | Left sidebar | **Unchecked** |
| Remove window mean | Top of **02 / Signal analysis** | **Checked** |
| Digital filter | Top of **02 / Signal analysis** | **None** |
| RMS window (frames) | Top of **02 / Signal analysis** | **60** |

For the final dual-channel session, **CH1 was triceps and CH2 was biceps**, according to the author's session notes. The five intended activation conditions each had two consecutive repetitions. The report explains the approximate reconstructed intervals; the original CSV does not contain exact synchronized trial boundaries.

Leaving sampling rate blank keeps the spectrum in **cycles/frame** and lags in **frames**. The observed reception rate must not be silently treated as a verified physiological sampling rate. The app's **Use reception rate as assumption** button applies only to the current stream and labels that choice as an assumption.

The app centers the **whole displayed window** before calculating its trailing RMS. The report centers each selected experimental segment separately and also uses different PSD segment lengths for some figures. Therefore a value obtained by dragging the app's replay slider is not expected to match every report value. Use the reproducible report script for those tables and figures.

## 4. Connect the existing receiver for a live stream

For the established, verified bench wiring, close any `screen`, serial assistant or earlier Python program that might already have the serial port open. Use the commercial board's own documented power connection and its wireless USB receiver; confirm the particular hardware wiring separately from this software guide.

1. In **DATA SOURCE**, click **↻** to refresh ports if needed. Select the actual receiver port. In the original Mac session it was `/dev/cu.usbserial-10`; another connection may receive a different name.
2. Set **Baud rate** to **115200** and click **Connect**.
3. Look for **Streaming**, increasing **Valid frames**, and the **LIVE DEVICE** badge. A recognized serial port alone does not establish that the board is sending valid frames.
4. Keep **Sampling rate** blank initially. View the two ADC fields in counts and the boundary-code percentages.

A disconnected input can sit quietly near a bias value. A cable whose electrodes are floating in air can show large oscillations or many 0/4095 values. Neither observation alone is a successful muscle recording. See the illustrated hardware guide and technical report for the actual setup and interpretation.

## 5. Record, annotate and retrieve a session

Select **Current stream** under **Displayed dataset**, then open **03 / Experiments & replay**:

1. Enter an **Experiment label** in the **Record a session** panel and click **Start recording**.
2. To annotate an event, type a label such as `rest_start` into **Event marker** and click **Add marker**. The marker points to the next host frame, with a host receipt-time reference; it is not a hardware-synchronized trigger.
3. Click **Stop recording**. The **Saved recordings** list shows the new session. Use **CSV** and **JSON** to download the paired files, or click **Replay** to inspect the saved CSV.
4. The original pair is also in the project's `recordings/` directory, unless `--data-dir` was used. Share both files when available so that labels, settings and markers travel with the data.

The CSV retains all eight valid device fields and host batch receipt times. Filtering and display settings do not overwrite the raw record. The JSON preserves the session label, sampling-rate basis, timing information and markers. **Disconnect** also closes an active recording. The `recordings/` directory is excluded from Git by default so that future private captures are not accidentally added with the public examples.

## 6. Try the regression example

Open **04 / Regression**, then click **Load synthetic labeled example** and **Fit & evaluate**. This loads a different demonstration dataset with explicit numeric targets and trial IDs. With the default 60-frame window, the example produces **90 training and 30 held-out windows**.

The built-in relationship is intentionally simple, so a high R² checks the implementation. It is not the performance of a model trained on the real biceps/triceps recordings. The included real recordings have no independent measured force target; the software should refuse to fit them as a supervised regression dataset.

## 7. Common questions

| Symptom | What to check |
| --- | --- |
| “No such file” when launching | Drag the actual `run.command` into Terminal after typing `bash `; avoid guessing the extracted folder name. |
| Browser cannot reach the local page | Keep Terminal running; use the exact `127.0.0.1` address and port it prints. |
| Serial port busy | Close other programs that opened the receiver, then reconnect. |
| Waiting / no recent frames | Confirm the selected receiver, board power and its wireless link. The software cannot infer the board's power state from a USB-port name. |
| Filter asks for a sampling rate | Keep **Digital filter = None** for unknown-rate data, or enter an independently supported rate and document its basis. |
| CSV regression has no usable labels | This is expected for the real sessions. Load the synthetic example, or supply an independently measured `target` and appropriate `trial` labels in a separate supervised dataset. |
| Replay metrics differ from the report | Match the selected rows, centering method and analysis parameters. The report script gives the exact published calculation. |

## 中文速查

- **Windows 启动：**在包含 `server.py` 的目录打开 PowerShell，依次运行上方 [Windows](#windows) 小节的三条命令。连接实机时，把预填的 Mac 串口名换成接收器实际对应的 COM 口。
- **macOS 启动：**解压后打开终端，输入 `bash `，把 `run.command` 拖进去，回车。保持终端运行，网页地址默认 `http://127.0.0.1:8765/`；结束时在终端按 Control+C。
- **不插设备也能看：**左栏点 **Run synthetic demo / 启动模拟演示**，或进入 **03 / Experiments & replay / 实验与回放**，导入 `data/raw/20261125_232138_110cad.csv`。
- **显示与分析设置：**左栏是显示窗口 **1000 帧**、采样率 **留空**；点 **02 / Signal analysis / 信号分析** 后，顶部面板里勾选 **Remove window mean / 移除窗口均值**，滤波选 **None / 无**，RMS 窗口填 **60 帧**。
- **最后这份双通道记录：**CH1 三头肌，CH2 二头肌。滑块控制显示窗口的终点，**End / 末尾** 表示最后一段，不是整段自动汇总。
- **实机连接：**确认已有硬件接线后，左栏选接收器串口（当时是 `/dev/cu.usbserial-10`），波特率 **115200**，点 **Connect / 连接设备**。有效帧递增才说明正在收到可解析数据。
- **保存：**在 **实验与回放** 页面填标签，点 **开始记录**；可添加事件标记；结束后点 **停止记录**，把同名 **CSV + JSON** 一起保留。
- **报告复算：**安装 `requirements-analysis.txt` 后运行 `python scripts/analyze_recordings.py`。软件当前窗口的均值处理与报告分段处理不完全相同，数字不应直接硬对。

For exact endpoint and numerical definitions, see [API.md](API.md). For test evidence, see [TEST_STATUS.md](../TEST_STATUS.md).
