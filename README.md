# ultrasonic-like-arduino

**Arduino-style HC-SR04 ultrasonic distance sensor control for Python — via PyFirmata2.**

Control an HC-SR04 (or compatible) ultrasonic distance sensor connected to an Arduino running StandardFirmata, using a simple, intuitive API inspired by the Arduino ecosystem.

---

## Features

- **HC-SR04 distance measurement** — read distance in cm, mm, m, or inches
- **Arduino-like syntax** — `attach()`, `ping()`, `read()`, `detach()`
- **Noise filtering** — `read_median()` and `read_average()` for stable readings
- **Context manager** — `with Board(...) as board:`
- **Utility functions** — `delay()`, `millis()`
- **Custom exceptions** — clean error handling
- **Built on PyFirmata2** — uses callbacks, not blocking loops

---

## Installation

```bash
# Install from source
pip install -e path/to/ultrasonic-like-arduino
```

**Requirements:**
- Python 3.8+
- Arduino running [StandardFirmata](https://github.com/firmata/arduino) (File → Examples → Firmata → StandardFirmata)
- pyFirmata2
- pyserial

---

## Wiring — HC-SR04 to Arduino

| HC-SR04 | Arduino        |
|---------|----------------|
| VCC     | 5V             |
| GND     | GND            |
| TRIG    | Digital pin 9  |
| ECHO    | Digital pin 10 |

> **Note:** The HC-SR04 uses 5V logic. For 3.3V Arduino boards (e.g. Due), use a level shifter or voltage divider on the ECHO pin.

---

## Quick Start

```python
from ultrasonic_like_arduino import Board, UltrasonicSensor

# Connect to your Arduino
board = Board("COM3")  # Windows: "COM3", Linux: "/dev/ttyUSB0", Mac: "/dev/cu.usbmodem14101"

# Create and attach the sensor
sensor = UltrasonicSensor()
sensor.attach(trig=9, echo=10)

# Read distance
distance = sensor.read()        # in cm (default)
print(f"Distance: {distance} cm")

distance = sensor.read('in')    # in inches
print(f"Distance: {distance} in")

# Raw pulse duration (like Arduino's pulseIn)
pulse = sensor.ping()
print(f"Pulse: {pulse} µs")

# Noise-reduced readings
median = sensor.read_median(samples=7)
avg = sensor.read_average(samples=5)

# Cleanup
sensor.detach()
board.close()
```

---

## API Reference

### Board

| Method | Description |
|--------|-------------|
| `Board(port)` | Connect to Arduino on `port` |
| `get_active_board()` | Get the most recently created Board (singleton) |
| `is_connected()` | Check if the board connection is open |
| `close()` | Stop sampling and close the serial connection |

### UltrasonicSensor

| Method | Description |
|--------|-------------|
| `attach(trig, echo)` | Bind sensor to trigger and echo pins |
| `detach()` | Release sensor pins |
| `attached()` | Check if sensor is attached |
| `ping()` | Measure echo pulse in microseconds (or `-1` on timeout) |
| `read(unit='cm')` | Measure distance in cm/mm/m/in (or `-1.0` on timeout) |
| `read_median(samples=5, unit='cm')` | Median of N readings for noise reduction |
| `read_average(samples=5, unit='cm')` | Average of N readings |
| `last_distance` | Property — last measured distance in cm |

### Utilities

| Function | Description |
|----------|-------------|
| `delay(ms)` | Pause for `ms` milliseconds |
| `millis()` | Returns current time in milliseconds |

---

## Example — Continuous Reading

```python
from ultrasonic_like_arduino import Board, UltrasonicSensor, delay

board = Board("COM3")
sensor = UltrasonicSensor()
sensor.attach(trig=9, echo=10)

try:
    while True:
        dist = sensor.read()
        if dist != -1.0:
            print(f"Distance: {dist:6.2f} cm")
        else:
            print("Out of range")
        delay(100)  # 100 ms between readings
except KeyboardInterrupt:
    print("\nStopped by user")
finally:
    sensor.detach()
    board.close()
```

---

## Limitations

- **Measurement accuracy** is limited by serial communication latency between
  the PC and Arduino (~1–10 ms). This wrapper is suitable for obstacle
  avoidance and presence detection rather than precision metrology.
- **Minimum reliable distance** is approximately 5–10 cm. Objects closer
  than this may produce unreliable readings.
- For high-precision or high-speed applications, consider a native Arduino
  sketch with serial output instead of Firmata.

---

## License

MIT — see [LICENSE](LICENSE).

## Author

Arnav-AP
