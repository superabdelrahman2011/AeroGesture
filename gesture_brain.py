import cv2
import mediapipe as mp
import socket
import struct

# Network Configuration
DRONE_IP = "192.168.4.1"
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Stream URL from ESP32-S3-CAM
STREAM_URL = f"http://{DRONE_IP}/stream"

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

# Open the video stream
cap = cv2.VideoCapture(STREAM_URL)

if not cap.isOpened():
    print(f"Error: Unable to connect to stream at {STREAM_URL}")
    exit()

print("Connected to stream. Tracking hand gestures...")

try:
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            print("Dropped frame, retrying...")
            continue

        # Flip horizontally for natural mirroring, convert to RGB
        frame = cv2.flip(frame, 1)
        h, w, c = frame.shape
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process frame with MediaPipe
        results = hands.process(rgb_frame)

        # Default RC values (1500 is mid-point/neutral for Roll, Pitch, Yaw)
        roll = 1500
        pitch = 1500
        throttle = 1000  # Default to zero throttle
        yaw = 1500

        if results.multi_hand_landmarks:
            for hand_lms in results.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, hand_lms, mp_hands.HAND_CONNECTIONS)

                # Get pixel coordinates for wrist and index finger tip
                wrist = hand_lms.landmark[mp_hands.HandLandmark.WRIST]
                index_tip = hand_lms.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]

                # Calculate vertical delta (y increases downwards in image coordinates)
                delta_y = wrist.y - index_tip.y

                # Map delta_y to Betaflight RC throttle range (1000 to 2000)
                # Adjust constraints based on your comfortable hand extension range
                min_delta = 0.1
                max_delta = 0.4
                
                clamped_delta = max(min_delta, min(delta_y, max_delta))
                throttle = int(1000 + ((clamped_delta - min_delta) / (max_delta - min_delta)) * 1000)
                
                # Visual telemetry overlay
                cv2.putText(frame, f"Throttle: {throttle}", (30, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Pack values into a tight binary structural packet (4 integers = 16 bytes)
        # Format string: 'iiii' represents 4 signed 4-byte integers
        packet = struct.pack('iiii', roll, pitch, throttle, yaw)
        
        # Dispatch connectionless telemetry packet to the airborne unit
        sock.sendto(packet, (DRONE_IP, UDP_PORT))

        # Show tracking window
        cv2.imshow("AeroGesture Ground Station Target Link", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
    sock.close()
