/**
 * SolarFlow LCD display driver
 *
 * Thin wrapper around the Arduino `LiquidCrystal` library for a 16x2
 * character LCD wired in 4-bit parallel mode.  The display mirrors the
 * live greenhouse readings so an operator can check conditions without
 * opening the web dashboard:
 *
 *      ┌────────────────┐
 *      │T:25.4°C H:68.2%│   ← temperature + humidity
 *      │FAN:ON  OK      │   ← fan state + status token
 *      └────────────────┘
 *
 * Status tokens shown next to the fan state:
 *
 *   OK    readings are healthy and below the configured thresholds
 *   WARN  temperature or humidity reached the configured threshold
 *   ERR   the last sensor read failed (values show as `--.-`)
 *
 * Wiring (see firmware/PROTOCOL.md for the complete diagram):
 *
 *   RS  → Arduino pin 12        D4 → Arduino pin 5
 *   EN  → Arduino pin 11        D5 → Arduino pin 4
 *   D6  → Arduino pin 3         D7 → Arduino pin 6
 *   VCC → 5 V                   GND → GND
 *
 * The HD44780 controller needs roughly 40 ms of settle time after
 * power-up before it accepts commands — call `begin()` after a short
 * delay.
 *
 * This header is intentionally free of floating-point `printf`: the AVR
 * build does not link the float formatter, so every value is converted
 * to an integer count of tenths before it is formatted.
 */

#ifndef SOLARFLOW_LCD_DISPLAY_H
#define SOLARFLOW_LCD_DISPLAY_H

#include <Arduino.h>
#include <LiquidCrystal.h>

// ---------------------------------------------------------------------------
// Display geometry
// ---------------------------------------------------------------------------
constexpr uint8_t LCD_COLUMNS = 16;
constexpr uint8_t LCD_ROWS    = 2;

// ---------------------------------------------------------------------------
// Custom character slot used for the degree sign
// ---------------------------------------------------------------------------
constexpr uint8_t LCD_DEGREE_SLOT = 0;

// ---------------------------------------------------------------------------
// Status tokens
// ---------------------------------------------------------------------------
constexpr char LCD_STATUS_OK[]   = "OK  ";
constexpr char LCD_STATUS_WARN[] = "WARN";
constexpr char LCD_STATUS_ERR[]  = "ERR ";

class LcdDisplay {
 public:
  // -------------------------------------------------------------------------
  // Construction
  // -------------------------------------------------------------------------
  // Pins are the 4-bit parallel interface of an HD44780-compatible LCD:
  // RS, EN and the four data lines D4-D7.  D0-D3 are left unconnected.
  LcdDisplay(uint8_t rsPin, uint8_t enPin,
             uint8_t d4Pin, uint8_t d5Pin, uint8_t d6Pin, uint8_t d7Pin);

  // -------------------------------------------------------------------------
  // Lifecycle
  // -------------------------------------------------------------------------
  // Initialise the controller, create the degree glyph and clear the
  // screen.  Call once, after the power-up settle delay.
  void begin();

  // Show the splash screen while the DHT22 stabilises.
  void showBoot();

  // -------------------------------------------------------------------------
  // Configuration
  // -------------------------------------------------------------------------
  // Thresholds above which the status token switches to WARN.  Defaults
  // are deliberately permissive so the display works before the caller
  // supplies crop-specific values.
  void setWarnThresholds(float temperatureC, float humidityPct);

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------
  // Render both rows.  `sensorOk` is false when the last read failed;
  // the readings are then displayed as `--.-`.
  void update(float temperatureC, float humidityPct, bool fanOn, bool sensorOk);

  // Re-render the fan row only — used when the relay state changes
  // between sensor samples.
  void refreshFanState(bool fanOn);

 private:
  void renderReadingsRow(float temperatureC, float humidityPct, bool sensorOk);
  void renderStateRow(bool fanOn, bool sensorOk);
  void writeRow(uint8_t row, char* text);

  LiquidCrystal _lcd;

  // Last rendered content of each row — used to skip redundant writes so
  // the display does not flicker when nothing has changed.
  char _row0[LCD_COLUMNS];
  char _row1[LCD_COLUMNS];

  float _warnTempC;
  float _warnHumidityPct;

  float _lastTemperatureC;
  float _lastHumidityPct;
  bool  _lastFanOn;
  bool  _lastSensorOk;

  bool  _ready;
};

#endif  // SOLARFLOW_LCD_DISPLAY_H
