# SolarFlow Hardware Communication Protocol

This document describes the serial protocol between the SolarFlow backend
and the Arduino sensor node, the wiring of the DHT22 sensor and relay
module, and the safety requirements for the fan circuit.

---

## 1. Physical layer

| Parameter     | Value             |
|---------------|-------------------|
| Transport     | USB-serial (UART) |
| Baud rate     | 9 600             |
| Data bits     | 8                 |
| Parity        | None              |
| Stop bits     | 1                 |
| Flow control  | None              |
| Line ending   | `\n` (LF)         |

Messages are **newline-delimited JSON**.  Each message is a single line of
UTF-8 text terminated by `\n` (0x0A).  Neither the host nor the Arduino
should send bare `\r\n`; the firmware accepts both LF and CR+LF for
robustness.

---

## 2. Message schemas

### 2.1 Startup announcement (Arduino → host)

Sent once after `setup()` completes.

```json
{"type":"startup","version":"1.0.0"}
```

| Field     | Type   | Description                       |
|-----------|--------|-----------------------------------|
| `type`    | string | Always `"startup"`                |
| `version` | string | Firmware semantic version string  |

---

### 2.2 Sensor reading (Arduino → host)

Sent every `READ_INTERVAL_MS` milliseconds (default 5 000 ms).

```json
{"type":"reading","temp":25.4,"humidity":68.2,"ts":12345}
```

| Field      | Type   | Description                                              |
|------------|--------|----------------------------------------------------------|
| `type`     | string | Always `"reading"`                                       |
| `temp`     | float  | Temperature in Celsius, rounded to one decimal place     |
| `humidity` | float  | Relative humidity in percent, rounded to one decimal place |
| `ts`       | uint32 | `millis()` value at time of read (rolls over after ~49 d) |

---

### 2.3 Sensor error (Arduino → host)

Sent when the DHT22 returns NaN for temperature or humidity.

```json
{"type":"error","code":"sensor_fail"}
```

| Field  | Type   | Description                                            |
|--------|--------|--------------------------------------------------------|
| `type` | string | Always `"error"`                                       |
| `code` | string | Error code — see [Section 5](#5-error-codes) for list  |

The current fan state is preserved on sensor failure.

---

### 2.4 Command (host → Arduino)

The host sends one of three allowlisted commands.

```json
{"cmd":"fan_on"}
{"cmd":"fan_off"}
{"cmd":"noop"}
```

| Field | Type   | Allowed values                    |
|-------|--------|-----------------------------------|
| `cmd` | string | `"fan_on"`, `"fan_off"`, `"noop"` |

Any other value in `cmd` is rejected; the relay is not touched.

---

### 2.5 Acknowledgement (Arduino → host)

Sent immediately after every received command.

```json
{"type":"ack","cmd":"fan_on","ok":true}
```

On parse error:

```json
{"type":"ack","cmd":"?","ok":false,"err":"parse_error"}
```

| Field  | Type    | Description                                         |
|--------|---------|-----------------------------------------------------|
| `type` | string  | Always `"ack"`                                      |
| `cmd`  | string  | The command string that was received                |
| `ok`   | boolean | `true` if the command was accepted and executed     |
| `err`  | string  | Present only on failure; see Section 5 for values   |

---

## 3. Startup sequence

```
Power on
   │
   ▼
Arduino runs setup()
   │  pinMode(RELAY_PIN, OUTPUT)
   │  setFan(false)          ← fan OFF for safety
   │  dht.begin()
   │  delay(2000)            ← DHT22 stabilisation
   │
   ▼
Arduino sends: {"type":"startup","version":"1.0.0"}
   │
   ▼
Arduino enters loop():
   ├─ Every 5 s → read DHT22 → send {"type":"reading",...}
   └─ Any time  → receive {"cmd":"..."} → execute → send {"type":"ack",...}
```

The host should wait for the `startup` message (or a 3-second timeout)
before sending the first command.

---

## 4. Watchdog behaviour

If no valid command is received within `WATCHDOG_TIMEOUT_MS` (default
60 000 ms), the Arduino **keeps the last known fan state**.  It does not
reset, does not turn the fan off, and does not change any pin state.

This ensures the greenhouse is not left in an unexpected state due to a
temporary host-side fault.  The host is responsible for re-asserting the
desired fan state after reconnecting.

---

## 5. Error codes

| Code           | Meaning                                               |
|----------------|-------------------------------------------------------|
| `sensor_fail`  | DHT22 returned NaN — sensor may be disconnected or    |
|                | faulty.  Fan state is preserved.                      |
| `parse_error`  | Received line is not valid JSON.                      |
| `missing_cmd`  | JSON parsed successfully but `cmd` key is absent.     |

---

## 6. Wiring diagram

```
                       Arduino Uno
                      ┌─────────────────────────────────┐
                      │                             5V  ○─┐
                      │                             GND ○─┤
                      │                                  │
       DHT22          │                                  │
   ┌──────────┐        │     ┌─────────────────────────┐  │
   │  1  VCC  ├────────┼─────┤ 3.3V or 5V (see note)   │  │
   │  2  DATA ├──┐     │     └─────────────────────────┘  │
   │  3  NC   │  │     │     Pin 2                         │
   │  4  GND  ├──┼─────┼──── GND                          │
   └──────────┘  │     │                                  │
                 └─────┤ Pin 2 (digital input)             │
                 │     │                                  │
           10 kΩ │     └─────────────────────────────────┘
                 │
                3.3V or 5V (same rail as DHT22 VCC)

    5V Relay Module           External power supply
   ┌──────────────┐            ┌───────────────┐
   │ VCC ─────────┼────────────┤ + (5 V DC)    │
   │ GND ─────────┼────────────┤ -             │
   │ IN  ─────────┼── Pin 7    └───────────────┘
   │ COM ─────────┼────────── Fan +            │
   │ NO  ─────────┼────────── Fan -  ──────────┤
   └──────────────┘            Fan negative to PSU -
```

**Component values:**

| Component             | Value / rating                       |
|-----------------------|--------------------------------------|
| DHT22 pull-up resistor | 10 kΩ (between DATA and VCC)        |
| Relay module          | 5 V coil, rated ≥ fan operating voltage |
| Fan                   | 5–12 V DC brushless, ≤ relay contact rating |
| External PSU          | Rated for fan current + 10 % margin  |

---

## 7. 5V relay module compatibility

- Most "5V relay modules" sold for Arduino include an optocoupler on the
  input side, allowing the Arduino 5 V logic level to drive the coil
  without exceeding the Uno's 40 mA pin current limit.
- Verify that the relay module has a dedicated `VCC`/`GND` pair for the
  coil **separate** from the `IN` signal pin.  Some bare relay boards
  (without optocouplers) draw enough current to brown out the Arduino 5 V
  rail; use an external 5 V supply for the coil in that case.
- The relay `IN` pin logic may be **active-LOW** on some modules.  If the
  fan turns on at startup (when the sketch sets `LOW`), invert the
  `setFan()` logic: `digitalWrite(RELAY_PIN, on ? LOW : HIGH)`.

---

## 8. Safety notes

### 8.1 Flyback diode

The fan motor is an inductive load.  When the relay contact opens, the
collapsing magnetic field in the motor windings generates a voltage spike
(back-EMF) that can damage the relay contacts and nearby electronics.

**Always fit a flyback diode (e.g. 1N4007) in parallel with the fan
terminals, cathode toward the positive rail.**

```
     +12V ──┬──────── Relay COM
            │
          [Fan]
            │
          [D1]  1N4007  (cathode stripe toward +12V)
            │
     GND  ──┴──────── Fan −
```

### 8.2 Fan power supply

- Never power the fan from the Arduino 5 V pin.  The Uno regulator is
  rated for approximately 500 mA total; a brushless fan may draw 200–
  800 mA at startup.
- Use a dedicated external power supply rated for at least the fan's
  stall current plus a 25 % safety margin.
- Connect the external PSU GND to Arduino GND (common ground reference).

### 8.3 Isolation

If using a mains-voltage fan, the relay module must be rated for mains
voltage (look for "250 V AC / 10 A" on the relay body).  Keep all mains
wiring on the load side of the relay away from Arduino signal wiring.
This sketch is written for low-voltage DC fans only.  Mains wiring
requires a qualified electrician and is outside the scope of this project.

---

## 9. Python host-side integration

The SolarFlow backend connects via `pyserial`.  Relevant config variables
(set in `backend/.env`):

```
SERIAL_PORT=COM3          # Windows — adjust to your port
# SERIAL_PORT=/dev/ttyUSB0  # Linux / macOS
SERIAL_BAUD=9600
SIMULATION_MODE=false     # Set to false to enable real hardware
```

The `HardwareInterface` class in `backend/app/services/hardware.py` handles
connection, command dispatch, and response parsing.  Only commands in
`ALLOWED_COMMANDS = frozenset({"fan_on", "fan_off", "noop"})` are ever
sent to the serial port; all other strings raise `ValueError` before any
I/O occurs.
