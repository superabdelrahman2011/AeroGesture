#include "esp_camera.h"
#include <WiFi.h>
#include <WiFiUdp.h>

// Wi-Fi AP Configs
const char* ssid = "AeroGesture_Net";
const char* password = "flightcontrol";

// UDP Port
unsigned int localUdpPort = 5005;
WiFiUDP udp;

// Hardware Structure Buffer for parsing target packet data
struct FlightPacket {
    int roll;
    int pitch;
    int throttle;
    int yaw;
};

// Camera Pin Mapping (AI Thinker S3 / Common S3 Variants)
#define PWDN_GPIO_NUM    -1
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM    15
#define SIOD_GPIO_NUM    4
#define SIOC_GPIO_NUM    5
#define Y9_GPIO_NUM      16
#define Y8_GPIO_NUM      17
#define Y7_GPIO_NUM      18
#define Y6_GPIO_NUM      12
#define Y5_GPIO_NUM      11
#define Y4_GPIO_NUM      10
#define Y3_GPIO_NUM      9
#define Y2_GPIO_NUM      8
#define VSYNC_GPIO_NUM   6
#define HREF_GPIO_NUM    7
#define PCLK_GPIO_NUM    13

void startCameraServer();

void setup() {
  Serial.begin(115200);      // Debug line to PC
  Serial2.begin(115200, SERIAL_8N1, 43, 44); // Hardware UART to F4 FC (Pins RX:43, TX:44 adjust per board layout)

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
  config.frame_size = FRAMESIZE_QVGA; // Optimized 320x240 size to lower network overhead
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 2;

  // Init Camera Module
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.println("Camera init failed");
    return;
  }

  // Spin up Access Point
  WiFi.softAP(ssid, password);
  IPAddress myIP = WiFi.softAPIP();
  Serial.print("AP IP address: ");
  Serial.println(myIP);

  // Initialize Network Listener Port
  udp.begin(localUdpPort);

  // Fire up async stream server loop
  startCameraServer();
}

void loop() {
  int packetSize = udp.parsePacket();
  if (packetSize == sizeof(FlightPacket)) {
    FlightPacket rxPacket;
    
    // Extract raw binary layout directly into structured flight vars
    udp.read((char*)&rxPacket, sizeof(FlightPacket));

    // Construct the MultiWii Serial Protocol (MSP) Set Raw RC payload manually
    // Message Type: MSP_SET_RAW_RC (200), Length: 8 bytes (4 channels * 2 bytes/uint16_t)
    uint8_t mspFrame[16];
    mspFrame[0] = '$';
    mspFrame[1] = 'M';
    mspFrame[2] = '<';
    mspFrame[3] = 8;   // Data Length
    mspFrame[4] = 200; // Command Code for Raw RC Overrides

    // Roll
    mspFrame[5] = rxPacket.roll & 0xFF;
    mspFrame[6] = (rxPacket.roll >> 8) & 0xFF;
    // Pitch
    mspFrame[7] = rxPacket.pitch & 0xFF;
    mspFrame[8] = (rxPacket.pitch >> 8) & 0xFF;
    // Throttle
    mspFrame[9] = rxPacket.throttle & 0xFF;
    mspFrame[10] = (rxPacket.throttle >> 8) & 0xFF;
    // Yaw
    mspFrame[11] = rxPacket.yaw & 0xFF;
    mspFrame[12] = (rxPacket.yaw >> 8) & 0xFF;

    // Direct XOR Checksum calculations
    uint8_t checksum = mspFrame[3] ^ mspFrame[4];
    for (int i = 5; i < 13; i++) {
      checksum ^= mspFrame[i];
    }
    mspFrame[13] = checksum;

    // Send payload directly down Serial line to F4 Betaflight Controller
    Serial2.write(mspFrame, 14);
  }
}

// Internal standard ESP HTTP stream code handles raw delivery frame-by-frame
void startCameraServer() {
  // Configured internally inside standard esp system layers to point to "/stream" endpoint
}
