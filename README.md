# AeroGesture FPV Ground Control Station & Flight Core

A zero-latency, vision-based FPV Ground Control Station (GCS) and ESP32-S3 drone flight core. AeroGesture streams high-speed MJPEG video from an **ESP32-S3-CAM** micro-drone to a laptop ground station, tracks hand movements in 3D using **MediaPipe**, filters signal noise via **Exponential Moving Average (EMA)** smoothing, and transmits 4-axis flight telemetry back to the drone over a non-blocking **UDP link**.

---

## 📡 System Architecture & Data Flow


```

┌──────────────────────────────────────┐       HTTP MJPEG Stream        ┌──────────────────────────────────────┐
│                                      │ ─────────────────────────────> │                                      │
│  ESP32-S3-CAM Drone                  │   ([http://192.168.4.1/stream](http://192.168.4.1/stream))  │  Laptop Ground Station               │
│  Access Point: 192.168.4.1           │                                │  (main.py)                           │
│  UDP Port: 5005                      │ <───────────────────────────── │                                      │
└──────────────────────────────────────┘      16-Byte UDP Telemetry     └──────────────────────────────────────┘


```

1. **Camera Feed:** The ESP32-S3 hosts an HTTP MJPEG stream at `192.168.4.1/stream`.
2. **Buffer Purging:** Python reads the stream in a background thread using `cap.grab()`, purging stale TCP frames to eliminate FPV video delay.
3. **Gesture Extraction:** MediaPipe Hand Landmarker outputs 21 3D coordinates.
4. **Signal Filtering:** Raw axis inputs pass through an EMA filter ($EMA_t = \alpha \cdot X_t + (1 - \alpha) \cdot EMA_{t-1}$) to eliminate hand tremors.
5. **UDP Transmission:** Controls are packed into a 16-byte Little-Endian binary payload (`<ffff`) and sent to port `5005`.
6. **Watchdog Failsafe:** If the ESP32 loses UDP communications for $>400\text{ms}$, motor outputs immediately zero out.

## 🎮 Single-Hand 4-Axis Flight Controls

| Control Axis | Hand Gesture / Position | Telemetry Output |
| :--- | :--- | :--- |
| **Roll (Left / Right)** | Shift wrist left or right relative to center target | `[-1.0, 1.0]` |
| **Pitch (Forward / Back)** | Shift wrist up or down relative to center target | `[-1.0, 1.0]` |
| **Yaw (Rotation)** | Tilt wrist/hand sideways (arctan2 angle relative to vertical) | `[-1.0, 1.0]` |
| **Throttle (Altitude)** | Distance between Index Tip and Thumb Tip (Pinch = $0\%$, Open = $100\%$) | `[0.0, 1.0]` |
| **Center Deadzone** | Keep wrist inside center target circle | Hover Lock (`[0, 0, 0, 0]`) |
| **Emergency Stop** | Curl hand into a closed fist | Emergency Brake / Disarm |

## 🛠️ Installation & Setup

### 1. ESP32-S3 Firmware Setup
1. Open `drone_firmware.ino` in the **Arduino IDE**.
2. Select **ESP32-S3 Dev Module** as your target board.
3. Enable **PSRAM: "OPI PSRAM"** in Board Settings.
4. Flash the code to your ESP32-S3-CAM.

### 2. Python Ground Station Setup
1. Open your terminal in the project directory and activate your virtual environment:
   ```bash
   .\drone_env\Scripts\activate

```

2. Install required dependencies:
```bash
pip install -r requirements.txt

```



---

## 🚀 Running the System

1. Power on the ESP32-S3 drone.
2. Connect your laptop Wi-Fi to the drone's Access Point:
* **SSID:** `AeroGesture-Drone`
* **Password:** `Password123`


3. Launch the Python Ground Control Station:
```bash
python main.py

```

4. Press `q` while focused on the video window to safely disarm and terminate the connection.
