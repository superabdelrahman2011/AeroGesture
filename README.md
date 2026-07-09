# AeroGesture

A lightweight dualunit distributed flight system for flying a quadcopter using bare-hand gestures Instead of straining a drone's battery with demanding computer vision tasks on a flying processor the video is streamed back to a separate groundbased system (like a Raspberry Pi or a laptop) to handle processing ensuring that the flying unit is feather light and free from edge AI overheating issues

# System Overview

The system is divided into two main hardware components that communicate wirelessly via a low-latency local Wi-Fi connection


[ PIECE 1: THE GROUND STATION ]              [ PIECE 2: THE AIRBORNE UNIT ]
┌────────────────────────────────┐              ┌────────────────────────────────┐
│   Raspberry Pi 3 / Laptop      │              │         ESP32-S3-CAM           │
│  - Catches Wi-Fi video feed    │              │  - Broadcasts raw video stream │
│  - MediaPipe tracking (21 pts) │              │  - Listens for UDP flight data │
└───────────────┬────────────────┘              └───────────────▲────────────────┘
                │                                               │
                │ (UDP Control Data)                            │ (Wi-Fi Video Stream)
                └───────────────────────────────────────────────┘
                                                                │
                                                ┌───────────────▼────────────────┐
                                                │     F4 Flight Controller       │
                                                │  - Interprets MSP serial data  │
                                                │  - Commands 4x 8520 motors     │
                                                └────────────────────────────────┘

# required componenets and pricing

`Ground Station` 

Raspberry Pi 3 Model B+ (or a standard Windows laptop) $35 Runs the gesture tracking software and handles flight path calculations.

 Wi-Fi Connectivity: Integrated.
Intercepts the video stream and broadcasts command packets back.
 
`The Drone`

1) 75mm or 85mm Frame:$6.
 A tiny, durable micro-whoop frame with built-in propeller guards

2) ESP32-S3-CAM (N16R8 model): ~$12.
 Acts as the Wi-Fi hotspot, streams video, and receives the UDP control signals.
 
3) 1S Brushed F4Flight Controller: $30.
 Runs Betaflight and directly controls the motors.
     
4) 8520 Brushed Motors (4-pack): $10. High-speed,  coreless motors driven by the onboard MOSFETs.
     
5) 1S LiPo Battery (BT2.0 connector):$6.Main power source.
      
6) 5V Step-Up Boost Regulator: $4. Prevents voltage sags/brownouts when the motors draw heavy power.
      
 Total Estimated Hardware Expenses: $103 (Drops to around $68 if you just use a laptop instead of buying a Raspberry Pi).
      
`Data flow`
      
 1) The Video Transmission:
  On powerup the drones ESP32-S3-CAM creates a local Wi-Fi access point
 called AeroGesture_Net It streams video at 30 FPS down to the ground station

 2) Gesture Recognition: 
 The ground station captures the stream and uses MediaPipe to track 21 key joints on your hand To calculate throttle, it measures the vertical distance between your wrist and index fingertip:delta Y= Wrist_y-IndexTip_y
 
 3) Control Signal Delivery:
 The ground station translates your hand position into Roll Pitch Throttle and Yaw values packs them into tight binary UDP packets and beams them back to the drones IP (192.168.4.1)

 4) Execution on the Drone:
 The ESP32 catches the UDP packets and passes them to the F4 Flight Controller over a direct serial (UART) connection using MultiWii Serial Protocol (MSP) commands. Betaflight processes these inputs to spin the motors and move the drone 
 
 `Betaflight Configuration`

 **To allow the flight controller to receive control inputs over the serial wire instead of a standard radio receiver:**

1) Connect the flight controller to your computer via USB and open Betaflight Configurator

2) Go to the Ports tab Find the UART wired to your ESP32s TX/RX pins turn on MSP for that port and leave the baud rate at 115200
 3) Go to the Configuration Receiver tab Set the Receiver Mode to Serialbased receiver and choose MSP RX input as the provider (or run feature RX_MSP directly in the CLI tab)

4) Click Save and Reboot

 `Project StructurePlaintext`

├── .gitignore
├── README.md
├── GroundStation/
│   └── gesture_brain.py  <-- Python gesture tracking script (Ground)
└── DroneFirmware/
    └── esp32_streamer.ino <-- Arduino Wi-Fi AP & receiver code (Drone)

**Important Safety Warning**

Remove the propellers from your drone before testing on your desk. Never plug in the 1S flight battery while configuring serial settings or testing code with the blades attached. Any small delay in your script or a glitch in the wireless communication can instantly jump the motors to full throttle, which will ruin your gear or cause injury.
