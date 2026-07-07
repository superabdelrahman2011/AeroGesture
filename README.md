# Project AeroGesture

An open-source, dual-unit distributed flight system that enables zero-wearable, bare-hand quadcopter control. By offloading heavy computer vision calculations from the flying vehicle onto a stationary ground controller, the system avoids the weight, heating, and power limitations typical of on-board edge AI.

---

## Dual-Unit Architecture Overview

The system is physically split into two separate hardware pieces that maintain a continuous, low-latency data loop over a local Wi-Fi link.

```text
 [ PIECE 1: THE GROUND STATION ]                  [ PIECE 2: THE AIRBORNE UNIT ]
┌────────────────────────────────┐              ┌────────────────────────────────┐
│      Raspberry Pi 3 Brain      │              │         ESP32-S3-CAM           │
│  - Captures incoming Wi-Fi stream            │  - Broadcasts raw video stream │
│  - MediaPipe tracking (21 joints)             │  - Receives UDP flight packets │
└───────────────┬────────────────┘              └───────────────▲────────────────┘
                │                                               │
                │ (UDP Control Packets)                         │ (Wi-Fi Video Stream)
                └───────────────────────────────────────────────┘
                                                                │
                                                ┌───────────────▼────────────────┐
                                                │     F4 Flight Controller       │
                                                │  - Translates MSP serial links │
                                                │  - Drives 4x 8520 motors       │
                                                └────────────────────────────────┘

 Component Separation BreakdownPiece 1: The Ground Brain (Stationary Desk Unit)Hardware: Raspberry Pi 3 (or Windows Dev Machine) equipped with a Wi-Fi network interface card.  Core Role: Acts as the high-powered algorithmic engine. It processes the incoming video frame-by-frame, handles the coordinate tracking, and calculates real-time flight vectors.  Software Stack: Python 3, OpenCV (opencv-python), and Google MediaPipe (mediapipe). 

 Piece 2: The Sky Unit (The Flying Vehicle)Hardware Frame: 75mm/85mm plastic micro-whoop frame with integrated propeller ducts.  Primary Sensor: ESP32-S3-CAM (N16R8 variant) executing connectionless wireless bridging.  Flight Controller: 1S Brushed F4 Flight Controller running open-source Betaflight firmware.  Propulsion: 4x 8520 coreless high-speed brushed motors wired through onboard MOSFETs.  Power Rail: 1S LiPo Battery (BT2.0 connector) paired with an ultra-lightweight 5V Step-Up boost regulator module to prevent system brownouts during heavy motor draws. 

 Wireless Handshake & Data FlowThe Video Feed: The Sky Unit's ESP32-S3-CAM spins up a local Wi-Fi network access point (AeroGesture_Net). It captures raw video and streams it down to the ground station at a targeted 30 frames per second.  The Tracking Math: The Ground Station intercepts the stream. The MediaPipe library tracks 21 coordinate points on the user's hand. The script calculates vertical distance variations between the wrist and the fingertips to determine pilot intent:  $$\Delta Y = \text{Wrist}_y - \text{IndexTip}_y$$The Control Feed: The Ground Station packs the mapped control values (Roll, Pitch, Throttle, Yaw) into tiny binary UDP packets and beams them back to the drone's IP address (192.168.4.1).  The Execution: The ESP32-S3-CAM catches the UDP packets and routes them directly to the F4 Flight Controller over a physical hardware serial line (UART) using MultiWii Serial Protocol (MSP) packets. Betaflight spins the motors up or down to execute the movement[cite: 1].  
 
 Repository Directory StructureOrganize your project files inside this repository using the following layout:Plaintext├── README.md                 <-- This structural documentation file
├── GroundStation/            <-- Piece 1 Files
│   └── gesture_brain.py      <-- Ground-based Python tracking script
└── DroneFirmware/            <-- Piece 2 Files
    └── esp32_streamer.ino    <-- Onboard ESP32 AP & wireless receiver code

 Critical Safety MandatePropeller Removal during Bench Testing: Never connect the 1S flight battery while testing internal firmware logic or adjusting serial telemetry configs with the flight blades attached[cite: 1]. Unexpected timing loops, communication skips, or unmapped variables can trigger immediate, full-throttle motor lock-up, resulting in equipment damage or physical injury[cite: 1].
