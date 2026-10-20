/**
 * SolarFlow Sensor Node — Arduino sketch
 *
 * Reads temperature and humidity from a DHT22 sensor, shows the live
 * readings and the fan state on a 16x2 character LCD, controls a relay
 * for the ventilation fan, and communicates with the SolarFlow backend
 * over a 9600-baud serial connection using newline-delimited JSON.
 *
 * Hardware connections
 * --------------------
 *   DHT22 DATA pin  → Arduino digital pin 2 (with 10 kΩ pull-up to 3.3 V or 5 V)
 *   Relay IN pin    → Arduino digital pin 7
 *   Relay VCC       → Arduino 5 V
 *   Relay GND       → Arduino GND
 *
 *   LCD RS  → Arduino digital pin 12       LCD D4 → Arduino digital pin 5
 *   LCD EN  → Arduino digital pin 11       LCD D5 → Arduino digital pin 4
 *   LCD D6  → Arduino digital pin 3        LCD D7 → Arduino digital pin 6
 *   LCD VCC → Arduino 5 V                  LCD GND → Arduino GND
 *
 * Serial protocol (see firmware/PROTOCOL.md for full spec)
 * ---------------------------------------------------------
 *   Outgoing (reading):  {"type":"reading","temp":25.4,"humidity":68.2,"ts":12345}
 *   Outgoing (error):    {"type":"error","code":"sensor_fail"}
 *   Incoming (command):  {"cmd":"fan_on"} / {"cmd":"fan_off"} / {"cmd":"noop"}
 *   Outgoing (ack):      {"type":"ack","cmd":"fan_on","ok":true}
 *
 * Dependencies
 * ------------
 *   DHT sensor library by Adafruit (install via Arduino Library Manager)
 *   ArduinoJson  v6 or v7 (install via Arduino Library Manager)
 *   LiquidCrystal (bundled with the Arduino IDE — no installation needed)
 *
 * See firmware/PROTOCOL.md for the full wiring diagram, component values,
 * safety notes, and error-code reference.
 */

#include <DHT.h>
#include <ArduinoJson.h>

#include "lcd_display.h"

// ---------------------------------------------------------------------------
// ArduinoJson compatibility
//
// ArduinoJson 7 replaced the static StaticJsonDocument<N> with a
// dynamically-sized JsonDocument.  On AVR, ARDUINOJSON_AUTO_SHRINK is
// disabled, so the internal pool only ever grows and is reused across
// samples — there is no repeated reallocation churn.
//
// The alias below lets the sketch build against either major version.
// ---------------------------------------------------------------------------
#if ARDUINOJSON_VERSION_MAJOR >= 7
  #define JSON_DOC(size) JsonDocument
#else
  #define JSON_DOC(size) StaticJsonDocument<size>
#endif

// ---------------------------------------------------------------------------
// Pin assignments — change only these constants if you rewire the circuit
// ---------------------------------------------------------------------------
#define DHT_PIN       2    // DHT22 data line
#define RELAY_PIN     7    // Relay IN — HIGH = fan ON, LOW = fan OFF

// LCD 16x2 in 4-bit parallel mode (D0-D3 left unconnected)
#define LCD_RS_PIN   12    // Register select — command/data
#define LCD_EN_PIN   11    // Enable — latched on the falling edge
#define LCD_D4_PIN    5    // Data bit 4
#define LCD_D5_PIN    4    // Data bit 5
#define LCD_D6_PIN    3    // Data bit 6
#define LCD_D7_PIN    6    // Data bit 7

// ---------------------------------------------------------------------------
// Sensor type
// ---------------------------------------------------------------------------
#define DHT_TYPE      DHT22

// ---------------------------------------------------------------------------
// Thresholds that raise the WARN token on the LCD.  These mirror the
// crop thresholds used by the backend alert engine (30 °C / 85 %).
// ---------------------------------------------------------------------------
#define LCD_TEMP_WARN_C        30.0f
#define LCD_HUMIDITY_WARN_PCT  85.0f

// ---------------------------------------------------------------------------
// Timing constants (milliseconds)
// ---------------------------------------------------------------------------
#define READ_INTERVAL_MS     5000UL   // How often to sample the sensor
#define WATCHDOG_TIMEOUT_MS  60000UL  // If no valid command is received within
                                      // this window, keep the last fan state
                                      // (do not reset or change anything)

// ---------------------------------------------------------------------------
// Globals
// ---------------------------------------------------------------------------
DHT dht(DHT_PIN, DHT_TYPE);

LcdDisplay lcd(LCD_RS_PIN, LCD_EN_PIN,
               LCD_D4_PIN, LCD_D5_PIN, LCD_D6_PIN, LCD_D7_PIN);

unsigned long lastReadAt      = 0;   // millis() of most recent sensor read
unsigned long lastCommandAt   = 0;   // millis() of most recent valid command
bool          fanOn           = false; // Tracks the current relay state

// Small JSON input buffer — commands are short, 64 bytes is plenty
static char inputBuf[128];
static uint8_t inputLen = 0;

// ---------------------------------------------------------------------------
// setup()
// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(9600);

  // Configure relay pin; fan starts OFF for safety
  pinMode(RELAY_PIN, OUTPUT);
  setFan(false);

  // The HD44780 needs a short settle time after power-up before it
  // accepts commands.
  delay(100);
  lcd.begin();
  lcd.showBoot();
  lcd.setWarnThresholds(LCD_TEMP_WARN_C, LCD_HUMIDITY_WARN_PCT);

  dht.begin();

  // Brief startup delay to let the DHT22 stabilise
  delay(2000);

  // Announce readiness on the serial bus
  Serial.println(F("{\"type\":\"startup\",\"version\":\"1.1.0\"}"));

  // Force the first sample to happen on the first pass through loop().
  lastReadAt = millis() - READ_INTERVAL_MS;
}

// ---------------------------------------------------------------------------
// loop()
// ---------------------------------------------------------------------------
void loop() {
  unsigned long now = millis();

  // ----- 1. Read sensor at the configured interval -------------------------
  if (now - lastReadAt >= READ_INTERVAL_MS) {
    lastReadAt = now;
    readAndSendSensor(now);
  }

  // ----- 2. Process any incoming serial command (non-blocking) -------------
  processSerialInput();

  // ----- 3. Watchdog: if no command received within WATCHDOG_TIMEOUT_MS ----
  //          keep current state — do NOT reset the relay
  // (No action needed here; the engine simply does not change fanOn.)
}

// ---------------------------------------------------------------------------
// readAndSendSensor()
//   Reads the DHT22.  On success sends a JSON "reading" message.
//   On failure sends a JSON "error" message.
// ---------------------------------------------------------------------------
void readAndSendSensor(unsigned long ts) {
  float humidity    = dht.readHumidity();
  float temperature = dht.readTemperature();  // Celsius

  if (isnan(humidity) || isnan(temperature)) {
    // Sensor read failed — report the error and keep the current fan state
    Serial.println(F("{\"type\":\"error\",\"code\":\"sensor_fail\"}"));
    lcd.update(0.0f, 0.0f, fanOn, false);
    return;
  }

  // Build and send the JSON reading
  // Using a fixed-size document avoids heap fragmentation on AVR
  JSON_DOC(128) doc;
  doc["type"]     = "reading";
  doc["temp"]     = (float)((int)(temperature * 10 + 0.5)) / 10.0; // 1 dp
  doc["humidity"] = (float)((int)(humidity    * 10 + 0.5)) / 10.0; // 1 dp
  doc["ts"]       = ts;

  serializeJson(doc, Serial);
  Serial.println();  // newline delimiter

  // Mirror the readings and the current fan state on the LCD
  lcd.update(temperature, humidity, fanOn, true);
}

// ---------------------------------------------------------------------------
// processSerialInput()
//   Reads one character at a time from Serial without blocking.
//   When a complete newline-terminated JSON line is received, parses it
//   and dispatches the command.
// ---------------------------------------------------------------------------
void processSerialInput() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();

    if (c == '\n' || c == '\r') {
      if (inputLen > 0) {
        inputBuf[inputLen] = '\0';
        handleCommand(inputBuf, inputLen);
        inputLen = 0;
      }
    } else {
      if (inputLen < (sizeof(inputBuf) - 1)) {
        inputBuf[inputLen++] = c;
      }
      // Overflow guard: discard the overlong line
      else {
        inputLen = 0;
      }
    }
  }
}

// ---------------------------------------------------------------------------
// handleCommand()
//   Parses a null-terminated JSON command string, dispatches the hardware
//   action, and sends an acknowledgement.
//
//   Accepted commands: "fan_on", "fan_off", "noop"
//   Anything else is rejected with ok:false.
// ---------------------------------------------------------------------------
void handleCommand(const char* json, uint8_t len) {
  JSON_DOC(64) doc;
  DeserializationError err = deserializeJson(doc, json, len);

  if (err) {
    // Not valid JSON — send a parse-error ack
    Serial.println(F("{\"type\":\"ack\",\"cmd\":\"?\",\"ok\":false,\"err\":\"parse_error\"}"));
    return;
  }

  const char* cmd = doc["cmd"];
  if (cmd == nullptr) {
    Serial.println(F("{\"type\":\"ack\",\"cmd\":\"?\",\"ok\":false,\"err\":\"missing_cmd\"}"));
    return;
  }

  bool ok = true;

  if (strcmp(cmd, "fan_on") == 0) {
    setFan(true);
    lastCommandAt = millis();
  } else if (strcmp(cmd, "fan_off") == 0) {
    setFan(false);
    lastCommandAt = millis();
  } else if (strcmp(cmd, "noop") == 0) {
    lastCommandAt = millis();
    // No hardware change — just acknowledge
  } else {
    // Unknown command — reject; do NOT touch the relay
    ok = false;
  }

  // Build and send acknowledgement
  JSON_DOC(96) ack;
  ack["type"] = "ack";
  ack["cmd"]  = cmd;
  ack["ok"]   = ok;

  serializeJson(ack, Serial);
  Serial.println();
}

// ---------------------------------------------------------------------------
// setFan()
//   Controls the relay.  HIGH on the relay IN pin energises the coil,
//   closing the normally-open contact and completing the fan circuit.
// ---------------------------------------------------------------------------
void setFan(bool on) {
  bool changed = (fanOn != on);

  fanOn = on;
  digitalWrite(RELAY_PIN, on ? HIGH : LOW);

  // Keep the LCD fan row in step with the relay state
  if (changed) {
    lcd.refreshFanState(fanOn);
  }
}
