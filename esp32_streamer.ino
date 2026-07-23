#include "esp_camera.h"
#include <WiFi.h>
#include <WiFiUdp.h>
#include "esp_http_server.h"

// ==========================================
// 📡 NETWORK CONFIGURATION
// ==========================================
const char* ssid = "AeroGesture-Drone";
const char* password = "Password123";
const int UDP_PORT = 5005;

// ==========================================
// 🎯 CAMERA PINOUT (ESP32-S3-CAM / FREENOVE)
// ==========================================
#define PWDN_GPIO_NUM    -1
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM    15
#define SIOD_GPIO_NUM    4
#define SIOC_GPIO_NUM    5
#define Y9_GPIO_NUM      16
#define Y8_GPIO_NUM      17
#define Y7_GPIO_NUM      18
#define Y6_GPIO_NUM      12
#define Y5_GPIO_NUM      10
#define Y4_GPIO_NUM      8
#define Y3_GPIO_NUM      9
#define Y2_GPIO_NUM      11
#define VSYNC_GPIO_NUM   6
#define HREF_GPIO_NUM    7
#define PCLK_GPIO_NUM    13

// ==========================================
// 📦 TELEMETRY PACKET (Explicit Alignment)
// ==========================================
struct __attribute__((packed)) TelemetryPacket {
    float pitch;    // -1.0 to 1.0
    float roll;     // -1.0 to 1.0
    float yaw;      // -1.0 to 1.0
    float throttle; //  0.0 to 1.0
};

TelemetryPacket currentCmd = {0.0f, 0.0f, 0.0f, 0.0f};
WiFiUDP udp;
httpd_handle_t stream_httpd = NULL;

unsigned long lastPacketTime = 0;
const unsigned long FAILSAFE_TIMEOUT_MS = 400;

// ==========================================
// 🎥 MJPEG STREAM HANDLER
// ==========================================
#define PART_BOUNDARY "123456789000000000000987654321"
static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* _STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* _STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

static esp_err_t stream_handler(httpd_req_t *req) {
    camera_fb_t * fb = NULL;
    esp_err_t res = ESP_OK;
    char part_buf[64];

    res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
    if (res != ESP_OK) return res;

    while (true) {
        fb = esp_camera_fb_get();
        if (!fb) {
            res = ESP_FAIL;
        } else {
            size_t hlen = snprintf(part_buf, 64, _STREAM_PART, fb->len);
            res = httpd_resp_send_chunk(req, part_buf, hlen);
            if (res == ESP_OK) res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
            if (res == ESP_OK) res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
            esp_camera_fb_return(fb);
            fb = NULL;
        }
        if (res != ESP_OK) break;
    }
    return res;
}

void startCameraServer() {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;

    httpd_uri_t stream_uri = {
        .uri       = "/stream",
        .method    = HTTP_GET,
        .handler   = stream_handler,
        .user_ctx  = NULL
    };

    if (httpd_start(&stream_httpd, &config) == ESP_OK) {
        httpd_register_uri_handler(stream_httpd, &stream_uri);
    }
}

// Optional Motor Output Driver Hook
void updateMotorOutputs(float p, float r, float y, float t) {
    // Convert normalized [-1.0, 1.0] controls to PWM values (0-255)
    // Example: ledcWrite(MOTOR_CHANNEL_1, pwm_val);
}

void setup() {
    Serial.begin(115200);

    // 1. Configure Camera
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sccb_sda = SIOD_GPIO_NUM;
    config.pin_sccb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.frame_size = FRAMESIZE_VGA;
    config.pixel_format = PIXFORMAT_JPEG;
    config.grab_mode = CAMERA_GRAB_LATEST; // Flush internal hardware buffer
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.jpeg_quality = 12;
    config.fb_count = 2;

    if (esp_camera_init(&config) != ESP_OK) {
        Serial.println("[-] Camera Initialization Failed!");
        return;
    }

    // 2. Start Wi-Fi AP
    WiFi.mode(WIFI_AP);
    IPAddress local_IP(192, 168, 4, 1);
    IPAddress gateway(192, 168, 4, 1);
    IPAddress subnet(255, 255, 255, 0);
    WiFi.softAPConfig(local_IP, gateway, subnet);
    WiFi.softAP(ssid, password);
    WiFi.setTxPower(WIFI_POWER_19_5dBm); // Max transmission range

    // 3. Start Camera HTTP Server & UDP Listener
    startCameraServer();
    udp.begin(UDP_PORT);
    Serial.println("[+] AeroGesture Firmware Ready at 192.168.4.1");
}

void loop() {
    int packetSize = udp.parsePacket();
    if (packetSize == sizeof(TelemetryPacket)) {
        udp.read((char*)&currentCmd, sizeof(TelemetryPacket));
        lastPacketTime = millis();

        updateMotorOutputs(currentCmd.pitch, currentCmd.roll, currentCmd.yaw, currentCmd.throttle);
    }

    // Watchdog Failsafe
    if (millis() - lastPacketTime > FAILSAFE_TIMEOUT_MS) {
        currentCmd = {0.0f, 0.0f, 0.0f, 0.0f};
        updateMotorOutputs(0, 0, 0, 0);
    }

    delay(1);
}
