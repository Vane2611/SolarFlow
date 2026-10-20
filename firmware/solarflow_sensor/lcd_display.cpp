/**
 * SolarFlow LCD display driver — implementation
 */

#include "lcd_display.h"

#include <string.h>

namespace {

// ---------------------------------------------------------------------------
// Byte used inside a row buffer to mark where the custom degree glyph
// should be written.  It cannot be '\0' because that terminates the
// string early.
// ---------------------------------------------------------------------------
constexpr char DEGREE_PLACEHOLDER = '\x01';

// ---------------------------------------------------------------------------
// 5x8 bitmap of a degree sign — a small ring in the upper half of the
// character cell.  Declared non-const because LiquidCrystal::createChar()
// takes a mutable uint8_t[] in the library bundled with the Arduino IDE.
// ---------------------------------------------------------------------------
uint8_t DEGREE_GLYPH[8] = {
  0x00, 0x0C, 0x12, 0x12, 0x0C, 0x00, 0x00, 0x00
};

// ---------------------------------------------------------------------------
// Round to the nearest tenth and return the result as an integer count
// of tenths (25.4 → 254).  Negative values round away from zero so that
// -5.24 becomes -52 rather than -51.
// ---------------------------------------------------------------------------
int roundToTenths(float value) {
  return (value >= 0.0f)
      ? (int)(value * 10.0f + 0.5f)
      : -(int)(-value * 10.0f + 0.5f);
}

// ---------------------------------------------------------------------------
// Format a value as compactly as possible while keeping the rendered
// row within the 16-column display width.
//
//   -9.9 … 99.9  →  one decimal place  ("-9.9", "25.4", "99.9")
//   otherwise     →  whole degrees only ("-10", "100")
//
// Only integer conversions are used — the AVR build does not link the
// floating-point formatter.
// ---------------------------------------------------------------------------
void formatCompact(char* out, uint8_t outSize, float value) {
  int tenths = roundToTenths(value);

  if (tenths > -100 && tenths < 1000) {
    // Integer division truncates toward zero, so -52/10 == -5 and
    // -52%10 == -2; the absolute value of the remainder keeps the
    // fractional digit positive.
    snprintf(out, outSize, "%d.%d", tenths / 10, abs(tenths % 10));
  } else {
    snprintf(out, outSize, "%d", tenths / 10);
  }
}

}  // namespace

// ---------------------------------------------------------------------------
// Construction
// ---------------------------------------------------------------------------
LcdDisplay::LcdDisplay(uint8_t rsPin, uint8_t enPin,
                       uint8_t d4Pin, uint8_t d5Pin, uint8_t d6Pin, uint8_t d7Pin)
    : _lcd(rsPin, enPin, d4Pin, d5Pin, d6Pin, d7Pin),
      _warnTempC(32.0f),
      _warnHumidityPct(85.0f),
      _lastTemperatureC(0.0f),
      _lastHumidityPct(0.0f),
      _lastFanOn(false),
      _lastSensorOk(false),
      _ready(false) {
  // Prime the row caches with a value that can never occur on the
  // display so the first render always writes to the controller.
  memset(_row0, 0x01, sizeof(_row0));
  memset(_row1, 0x01, sizeof(_row1));
}

// ---------------------------------------------------------------------------
// begin()
// ---------------------------------------------------------------------------
void LcdDisplay::begin() {
  _lcd.begin(LCD_COLUMNS, LCD_ROWS);
  _lcd.clear();

  // createChar() must run after begin() and resets the display.
  _lcd.createChar(LCD_DEGREE_SLOT, DEGREE_GLYPH);

  _ready = true;
}

// ---------------------------------------------------------------------------
// showBoot()
// ---------------------------------------------------------------------------
void LcdDisplay::showBoot() {
  if (!_ready) {
    return;
  }

  char row[LCD_COLUMNS + 1];

  snprintf(row, sizeof(row), "  SolarFlow   ");
  writeRow(0, row);

  snprintf(row, sizeof(row), "  Starting...  ");
  writeRow(1, row);
}

// ---------------------------------------------------------------------------
// setWarnThresholds()
// ---------------------------------------------------------------------------
void LcdDisplay::setWarnThresholds(float temperatureC, float humidityPct) {
  _warnTempC     = temperatureC;
  _warnHumidityPct = humidityPct;
}

// ---------------------------------------------------------------------------
// update()
// ---------------------------------------------------------------------------
void LcdDisplay::update(float temperatureC, float humidityPct,
                        bool fanOn, bool sensorOk) {
  if (!_ready) {
    return;
  }

  _lastTemperatureC = temperatureC;
  _lastHumidityPct  = humidityPct;
  _lastFanOn        = fanOn;
  _lastSensorOk     = sensorOk;

  renderReadingsRow(temperatureC, humidityPct, sensorOk);
  renderStateRow(fanOn, sensorOk);
}

// ---------------------------------------------------------------------------
// refreshFanState()
// ---------------------------------------------------------------------------
void LcdDisplay::refreshFanState(bool fanOn) {
  if (!_ready) {
    return;
  }

  _lastFanOn = fanOn;
  renderStateRow(fanOn, _lastSensorOk);
}

// ---------------------------------------------------------------------------
// renderReadingsRow()
//   Row 0: "T:25.4°C H:68.2%"
// ---------------------------------------------------------------------------
void LcdDisplay::renderReadingsRow(float temperatureC, float humidityPct,
                                   bool sensorOk) {
  char row[LCD_COLUMNS + 1];

  if (!sensorOk) {
    // The last read failed — show placeholders rather than stale values.
    snprintf(row, sizeof(row), "T:--.-%cC H:--.-%%", DEGREE_PLACEHOLDER);
  } else {
    char tempText[8];
    char humText[8];

    formatCompact(tempText, sizeof(tempText), temperatureC);
    formatCompact(humText, sizeof(humText), humidityPct);

    snprintf(row, sizeof(row), "T:%s%cC H:%s%%",
             tempText, DEGREE_PLACEHOLDER, humText);
  }

  row[LCD_COLUMNS] = '\0';
  writeRow(0, row);
}

// ---------------------------------------------------------------------------
// renderStateRow()
//   Row 1: "FAN:ON  OK" / "FAN:OFF WARN" / "FAN:ON  ERR"
// ---------------------------------------------------------------------------
void LcdDisplay::renderStateRow(bool fanOn, bool sensorOk) {
  char row[LCD_COLUMNS + 1];

  bool warn = sensorOk &&
              (_lastTemperatureC >= _warnTempC ||
               _lastHumidityPct  >= _warnHumidityPct);

  const char* status;
  if (!sensorOk) {
    status = LCD_STATUS_ERR;
  } else if (warn) {
    status = LCD_STATUS_WARN;
  } else {
    status = LCD_STATUS_OK;
  }

  snprintf(row, sizeof(row), "FAN:%s %s", fanOn ? "ON " : "OFF", status);
  row[LCD_COLUMNS] = '\0';
  writeRow(1, row);
}

// ---------------------------------------------------------------------------
// writeRow()
//   Writes exactly LCD_COLUMNS characters to `row`, padding with spaces
//   so stale characters are erased.  Skips the write entirely when the
//   content is unchanged, which avoids visible flicker.
// ---------------------------------------------------------------------------
void LcdDisplay::writeRow(uint8_t row, char* text) {
  char* cache = (row == 0) ? _row0 : _row1;

  // Find the end of the string, then pad the remainder of the row.
  uint8_t len = 0;
  while (len < LCD_COLUMNS && text[len] != '\0') {
    len++;
  }
  for (uint8_t i = len; i < LCD_COLUMNS; i++) {
    text[i] = ' ';
  }

  bool changed = false;
  for (uint8_t i = 0; i < LCD_COLUMNS; i++) {
    if (text[i] != cache[i]) {
      changed = true;
      break;
    }
  }
  if (!changed) {
    return;
  }

  _lcd.setCursor(0, row);
  for (uint8_t i = 0; i < LCD_COLUMNS; i++) {
    if (text[i] == DEGREE_PLACEHOLDER) {
      _lcd.write((uint8_t)LCD_DEGREE_SLOT);
    } else {
      _lcd.print(text[i]);
    }
  }

  memcpy(cache, text, LCD_COLUMNS);
}
