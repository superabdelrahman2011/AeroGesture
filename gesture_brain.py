import cv2
import mediapipe as mp
import socket
import struct
import time
import threading
import numpy as np

# ==========================================
# ⚙️ SYSTEM CONFIGURATION (TEST MODE)
# ==========================================
USE_WEBCAM = True        # Set to True for testing without drone hardware
WEBCAM_INDEX = 0         # Default laptop camera
DRONE_IP = "192.168.4.1" # Target IP when drone arrives
UDP_PORT = 5005

ALPHA_SMOOTH = 0.25      # EMA Filter factor (0.1 = smooth, 0.9 = fast)
DEADZONE_RADIUS = 50     # Pixels from screen center for Hover Lock

# Setup Non-Blocking UDP Socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setblocking(False)

# ==========================================
# 🚀 THREADED VIDEO ENGINE
# ==========================================
class ThreadedVideoStream:
    """Fetches frames in a background thread to prevent GUI lag."""
    def __init__(self, src):
        self.cap = cv2.VideoCapture(src)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.grabbed, self.frame = False, None
        self.started = False
        self.read_lock = threading.Lock()

    def start(self):
        if self.started:
            return self
        self.started = True
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()
        return self

    def update(self):
        while self.started:
            grabbed, frame = self.cap.read()
            if not grabbed:
                time.sleep(0.01)
                continue
            with self.read_lock:
                self.grabbed = grabbed
                self.frame = frame

    def read(self):
        with self.read_lock:
            if self.frame is None:
                return False, None
            return self.grabbed, self.frame.copy()

    def stop(self):
        self.started = False
        if self.cap.isOpened():
            self.cap.release()

# ==========================================
# 🧹 EXPONENTIAL MOVING AVERAGE (EMA) FILTER
# ==========================================
class EMAFilter:
    def __init__(self, alpha=0.25):
        self.alpha = alpha
        self.value = None

    def filter(self, val):
        if self.value is None:
            self.value = val
        else:
            self.value = self.alpha * val + (1 - self.alpha) * self.value
        return self.value

    def reset(self):
        self.value = None

# ==========================================
# 🛠️ GESTURE MATH & HUD DRAWING
# ==========================================
def calculate_hand_telemetry(landmarks, w, h, cx, cy):
    wrist = np.array([landmarks[0].x * w, landmarks[0].y * h])
    middle_mcp = np.array([landmarks[9].x * w, landmarks[9].y * h])
    index_tip = np.array([landmarks[8].x * w, landmarks[8].y * h])
    thumb_tip = np.array([landmarks[4].x * w, landmarks[4].y * h])

    # 1. Roll & Pitch (Wrist Offset relative to Center)
    dx = wrist[0] - cx
    dy = wrist[1] - cy
    dist_from_center = np.linalg.norm([dx, dy])

    if dist_from_center > DEADZONE_RADIUS:
        raw_roll = np.clip(dx / (w / 2.5), -1.0, 1.0)
        raw_pitch = np.clip(-dy / (h / 2.5), -1.0, 1.0) # Inverted Y
    else:
        raw_roll, raw_pitch = 0.0, 0.0

    # 2. Yaw (Wrist to Middle Knuckle Angle)
    hand_vector = middle_mcp - wrist
    angle_rad = np.arctan2(hand_vector[0], -hand_vector[1])
    angle_deg = np.degrees(angle_rad)
    raw_yaw = np.clip(angle_deg / 45.0, -1.0, 1.0)

    # 3. Throttle (Pinch gesture)
    palm_scale = np.linalg.norm(middle_mcp - wrist)
    pinch_dist = np.linalg.norm(index_tip - thumb_tip)
    ratio = pinch_dist / (palm_scale + 1e-5)
    raw_throttle = np.clip((ratio - 0.2) / 0.8, 0.0, 1.0)

    return raw_pitch, raw_roll, raw_yaw, raw_throttle, wrist.astype(int)

def is_fist_gesture(landmarks):
    wrist = np.array([landmarks[0].x, landmarks[0].y])
    finger_tips = [8, 12, 16, 20]
    total_dist = sum([np.linalg.norm(np.array([landmarks[tip].x, landmarks[tip].y]) - wrist) for tip in finger_tips])
    return (total_dist / len(finger_tips)) < 0.25

def draw_hud(frame, pitch, roll, yaw, throttle, status, color, fps):
    h, w, _ = frame.shape
    cx, cy = w // 2, h // 2

    # Deadzone Target Circle
    cv2.circle(frame, (cx, cy), DEADZONE_RADIUS, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.line(frame, (cx - 15, cy), (cx + 15, cy), (255, 255, 255), 1)
    cv2.line(frame, (cx, cy - 15), (cx, cy + 15), (255, 255, 255), 1)

    # Artificial Horizon Line
    horizon_y = int(cy + (pitch * 100))
    angle = roll * 45
    M = cv2.getRotationMatrix2D((cx, horizon_y), angle, 1.0)
    pt1 = np.dot(M, [cx - 80, horizon_y, 1]).astype(int)
    pt2 = np.dot(M, [cx + 80, horizon_y, 1]).astype(int)
    cv2.line(frame, tuple(pt1), tuple(pt2), (0, 255, 255), 2, cv2.LINE_AA)

    # Throttle Gauge Bar
    bar_x = w - 40
    bar_top = 100
    bar_height = h - 200
    fill_height = int(throttle * bar_height)
    cv2.rectangle(frame, (bar_x, bar_top), (bar_x + 15, bar_top + bar_height), (100, 100, 100), 1)
    cv2.rectangle(frame, (bar_x, bar_top + bar_height - fill_height), (bar_x + 15, bar_top + bar_height), (0, 255, 0), -1)
    cv2.putText(frame, "THR", (bar_x - 10, bar_top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    # Telemetry Text
    mode_label = "TEST MODE (WEBCAM)" if USE_WEBCAM else "LIVE DRONE"
    cv2.putText(frame, f"MODE: {mode_label}", (20, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(frame, f"STATUS: {status}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    cv2.putText(frame, f"FPS: {fps:.1f}", (w - 100, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.putText(frame, f"PITCH: {pitch:+.2f} | ROLL: {roll:+.2f}", (20, h - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(frame, f"YAW:   {yaw:+.2f} | THRT: {throttle:.2f}", (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return frame

# ==========================================
# 🎮 MAIN INITIALIZATION
# ==========================================
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

pitch_filter = EMAFilter(ALPHA_SMOOTH)
roll_filter = EMAFilter(ALPHA_SMOOTH)
yaw_filter = EMAFilter(ALPHA_SMOOTH)
throttle_filter = EMAFilter(ALPHA_SMOOTH)

src = WEBCAM_INDEX if USE_WEBCAM else f"http://{DRONE_IP}/stream"
print(f"[+] Starting AeroGesture Test Video Stream...")
vs = ThreadedVideoStream(src).start()
time.sleep(1.0)

last_time = time.time()

try:
    while True:
        grabbed, frame = vs.read()
        if not grabbed or frame is None:
            time.sleep(0.01)
            continue

        frame = cv2.flip(frame, 1) # Mirror feed for natural control
        h, w, _ = frame.shape
        cx, cy = w // 2, h // 2

        curr_time = time.time()
        fps = 1.0 / (curr_time - last_time + 1e-5)
        last_time = curr_time

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)

        pitch, roll, yaw, throttle = 0.0, 0.0, 0.0, 0.0
        status_text = "NO HAND (HOVER LOCK)"
        status_color = (0, 0, 255)

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                if is_fist_gesture(hand_landmarks.landmark):
                    status_text = "EMERGENCY BRAKE"
                    status_color = (0, 165, 255)
                    for f in [pitch_filter, roll_filter, yaw_filter, throttle_filter]:
                        f.reset()
                else:
                    rp, rr, ry, rt, wrist_pt = calculate_hand_telemetry(hand_landmarks.landmark, w, h, cx, cy)
                    pitch = pitch_filter.filter(rp)
                    roll = roll_filter.filter(rr)
                    yaw = yaw_filter.filter(ry)
                    throttle = throttle_filter.filter(rt)

                    status_text = "ACTIVE PILOTING"
                    status_color = (0, 255, 0)
                    cv2.line(frame, (cx, cy), tuple(wrist_pt), status_color, 2, cv2.LINE_AA)

        frame = draw_hud(frame, pitch, roll, yaw, throttle, status_text, status_color, fps)

        # Transmit UDP Packet (non-blocking, won't crash if no drone is connected)
        packet = struct.pack('<ffff', float(pitch), float(roll), float(yaw), float(throttle))
        try:
            sock.sendto(packet, (DRONE_IP, UDP_PORT))
        except Exception:
            pass

        cv2.imshow("AeroGesture Ground Station [TEST MODE]", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    vs.stop()
    cv2.destroyAllWindows()
    sock.close()
