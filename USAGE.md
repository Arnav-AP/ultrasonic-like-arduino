# Usage Guide — ultrasonic-like-arduino

Complete documentation for the `ultrasonic-like-arduino` library — Arduino-style
HC-SR04 ultrasonic distance sensor control via PyFirmata2.

---

## Table of Contents

- [Installation](#installation)
- [Hardware Setup](#hardware-setup)
  - [Wiring](#wiring)
  - [Arduino Firmware](#arduino-firmware)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
  - [`Board`](#board)
  - [`UltrasonicSensor`](#ultrasonicsensor)
  - [Utility Functions](#utility-functions)
  - [Exception Hierarchy](#exception-hierarchy)
- [Advanced Usage](#advanced-usage)
  - [Multiple Sensors](#multiple-sensors)
  - [Context Manager](#context-manager)
  - [Noise Filtering](#noise-filtering)
  - [Unit Conversion](#unit-conversion)
  - [Continuous Monitoring](#continuous-monitoring)
  - [Parsed Output for Scripts](#parsed-output-for-scripts)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)

---

## Installation

```bash
# From the cloned repository directory
pip install -e path/to/ultrasonic-like-arduino

# Or install from the zip release
pip install ultrasonic-like-arduino.zip
```

**Requirements:**
- Python 3.8+
- Arduino board running StandardFirmata
- `pyfirmata2` (installed automatically with the package)
- `pyserial` (installed automatically with the package)

**Verify installation:**

```python
import ultrasonic_like_arduino
print(ultrasonic_like_arduino.__version__)  # 0.1.0
```

---

## Hardware Setup

### Wiring

Connect your HC-SR04 (or compatible) ultrasonic sensor to the Arduino:

| HC-SR04 | Arduino          |
|---------|------------------|
| VCC     | 5V               |
| GND     | GND              |
| TRIG    | Digital pin 9    |
| ECHO    | Digital pin 10   |

> **Note:** The HC-SR04 uses 5V logic. For 3.3V Arduino boards (e.g. Due),
> use a level shifter or voltage divider on the ECHO pin.

### Arduino Firmware

1. Open the Arduino IDE
2. Go to **File → Examples → Firmata → StandardFirmata**
3. Upload the sketch to your Arduino
4. Note which serial port the Arduino connects on:
   - **Windows:** `COM3`, `COM4`, etc.
   - **Linux:** `/dev/ttyUSB0`, `/dev/ttyACM0`
   - **macOS:** `/dev/cu.usbmodem14101`, `/dev/cu.usbserial-*`

---

## Quick Start

```python
from ultrasonic_like_arduino import Board, UltrasonicSensor

# 1. Connect to the Arduino
board = Board("COM3")  # Use your port

# 2. Create a sensor and attach it to pins
sensor = UltrasonicSensor()
sensor.attach(trig=9, echo=10)

# 3. Measure distance
distance = sensor.read()           # in cm (default)
print(f"Distance: {distance} cm")

distance = sensor.read('in')       # in inches
print(f"Distance: {distance} in")

distance = sensor.read('mm')       # in millimetres
print(f"Distance: {distance} mm")

distance = sensor.read('m')        # in metres
print(f"Distance: {distance} m")

# 4. Raw pulse duration (like Arduino's pulseIn)
pulse = sensor.ping()
print(f"Pulse: {pulse} µs")

# 5. Cleanup
sensor.detach()
board.close()
```

---

## API Reference

### `Board`

The `Board` class manages the serial connection to an Arduino running
StandardFirmata. It follows a **singleton pattern** — only one board can
be active at a time, and sensors automatically discover it.

#### `Board(port)`

Create a new board connection.

```python
from ultrasonic_like_arduino import Board

# Windows
board = Board("COM3")

# Linux
board = Board("/dev/ttyUSB0")

# macOS
board = Board("/dev/cu.usbmodem14101")
```

| Parameter | Type   | Description                                      |
|-----------|--------|--------------------------------------------------|
| `port`    | `str`  | Serial port name of the Arduino.                 |

**Raises:**
- [`BoardConnectionError`](#boardconnectionerror) — if the Arduino cannot be reached.

#### `Board.get_active_board()` *(staticmethod)*

Return the most recently created `Board` instance. This is used internally
by `UltrasonicSensor.attach()`, but can also be called directly.

```python
board = Board.get_active_board()
```

| Returns | Type    | Description                          |
|---------|---------|--------------------------------------|
| Active  | `Board` | The most recently created board.     |

**Raises:**
- `RuntimeError` — if no `Board` has been created yet.

#### `board.is_connected()`

Check whether the board connection is still open.

```python
if board.is_connected():
    print("Board is connected")
```

| Returns | Type   | Description                    |
|---------|--------|--------------------------------|
| `True`  | `bool` | Connection is open.            |
| `False` | `bool` | Connection has been closed.    |

#### `board.close()`

Close the serial connection, stop the sampler thread, and release the
serial port. This is best-effort and will not raise if cleanup fails.

```python
board.close()
```

#### Context Manager

The `Board` can be used as a context manager. It automatically calls
`close()` on exit.

```python
with Board("COM3") as board:
    sensor = UltrasonicSensor()
    sensor.attach(trig=9, echo=10)
    print(sensor.read())
# board.close() called automatically
```

---

### `UltrasonicSensor`

The `UltrasonicSensor` class represents one HC-SR04 distance sensor.
It uses PyFirmata2's callback mechanism to time the echo pulse with
microsecond precision.

#### `UltrasonicSensor(max_distance=400)`

Create a new sensor instance.

```python
sensor = UltrasonicSensor()                # 400 cm range
sensor = UltrasonicSensor(max_distance=200) # 200 cm range (shorter timeout)
```

| Parameter      | Type          | Default | Description                                    |
|----------------|---------------|---------|------------------------------------------------|
| `max_distance` | `int`/`float` | `400`   | Maximum measurable distance in cm. Controls the echo timeout. |

The timeout is calculated as `(2 * max_distance / 34300) + 0.01` seconds,
capped at 100 ms.

#### `sensor.attach(trig, echo)`

Bind the sensor to specific trigger and echo pins on the Arduino.

```python
sensor.attach(trig=9, echo=10)
```

| Parameter | Type  | Description                                    |
|-----------|-------|------------------------------------------------|
| `trig`    | `int` | Digital pin number for the sensor's TRIG pin.  |
| `echo`    | `int` | Digital pin number for the sensor's ECHO pin.  |

The TRIG pin is configured as a digital output; the ECHO pin as a
digital input with port reporting enabled.

**Raises:**
- `RuntimeError` — if no `Board` has been initialised yet.

**Notes:**
- Attaching again to different pins (without detaching first) will
  reassign the pins. The old echo callback is **not** restored in this
  case — detach first if you need clean teardown.
- Multiple `UltrasonicSensor` instances can coexist on different
  pin pairs (see [Multiple Sensors](#multiple-sensors)).

#### `sensor.detach()`

Release the sensor's pins and restore any previous echo callback.

```python
sensor.detach()
```

After calling this, the sensor must be re-attached before further
readings. The `last_distance` property is reset to `None`.

#### `sensor.attached()`

Check whether the sensor is currently attached to pins.

```python
if sensor.attached():
    sensor.read()
```

| Returns | Type   | Description                      |
|---------|--------|----------------------------------|
| `True`  | `bool` | Sensor is attached and ready.    |
| `False` | `bool` | Sensor is not attached.          |

#### `sensor.ping()`

Send a trigger pulse and measure the echo pulse duration in microseconds.
This is the fundamental measurement — all `read*()` methods call `ping()`
internally.

```python
pulse = sensor.ping()
if pulse != -1:
    print(f"Echo pulse: {pulse} µs")
else:
    print("No object detected (timeout)")
```

| Returns | Type  | Description                                                    |
|---------|-------|----------------------------------------------------------------|
| Pulse   | `int` | Echo pulse duration in microseconds (≥ 1).                     |
| `-1`    | `int` | Timeout — no object detected within range, or reading was noise below 2 cm. |

**Raises:**
- [`SensorNotAttachedError`](#sensornotattacherror) — if the sensor has not been attached yet.

**How it works:**

1. Resets all tracking state (`_echo_high_time`, `_echo_low_time`, `_prev_echo_value`).
2. Sends a 1 ms HIGH pulse on the TRIG pin (100× the 10 µs minimum).
3. Waits for the echo callback to fire on rising and falling edges of the
   ECHO pin, capturing `time.perf_counter()` timestamps at each edge.
4. If the falling edge is received within the timeout, calculates the
   pulse duration: `(echo_low_time - echo_high_time) * 1_000_000`.
5. Rejects readings below 2 cm (electrical noise floor).
6. Returns `-1` if no measurement is received within the timeout.

#### `sensor.read(unit='cm')`

Measure the distance to the nearest object.

```python
d = sensor.read()          # centimetres (default)
d = sensor.read('cm')      # centimetres
d = sensor.read('mm')      # millimetres
d = sensor.read('m')       # metres
d = sensor.read('in')      # inches
```

| Parameter | Type  | Default | Description                                |
|-----------|-------|---------|--------------------------------------------|
| `unit`    | `str` | `'cm'`  | Supported: `'cm'`, `'mm'`, `'m'`, `'in'`. |

| Returns  | Type    | Description                                                    |
|----------|---------|----------------------------------------------------------------|
| Distance | `float` | Distance in the requested unit (rounded to 2 decimal places).  |
| `-1.0`   | `float` | Timeout — no object detected within range.                     |

**Raises:**
- [`SensorNotAttachedError`](#sensornotattacherror) — if the sensor has not been attached yet.
- [`InvalidUnitError`](#invaliduniterror) — if `unit` is not recognised.

**Conversion factors used:**

| Unit | Factor (pulse µs → unit) | Derivation                          |
|------|--------------------------|-------------------------------------|
| cm   | × 0.01715               | `0.0343 / 2` (speed of sound / 2)  |
| mm   | × 0.1715                | cm factor × 10                      |
| m    | × 0.0001715             | cm factor × 0.01                    |
| in   | × 0.00675               | `0.0135 / 2` (speed in in/µs / 2)   |

#### `sensor.read_median(samples=5, unit='cm')`

Take multiple readings and return the **median** value. This effectively
rejects outliers caused by acoustic interference or serial timing jitter.

```python
d = sensor.read_median()            # 5 samples, cm
d = sensor.read_median(samples=7)   # 7 samples, cm
d = sensor.read_median(unit='mm')   # 5 samples, mm
```

| Parameter | Type  | Default | Description                                |
|-----------|-------|---------|--------------------------------------------|
| `samples` | `int` | `5`     | Number of readings to take (must be ≥ 1).  |
| `unit`    | `str` | `'cm'`  | Supported: `'cm'`, `'mm'`, `'m'`, `'in'`. |

| Returns  | Type    | Description                                                    |
|----------|---------|----------------------------------------------------------------|
| Distance | `float` | Median distance in the requested unit (rounded to 2 d.p.).     |
| `-1.0`   | `float` | All readings timed out.                                        |

**Raises:**
- [`SensorNotAttachedError`](#sensornotattacherror) — if not attached.
- `ValueError` — if `samples < 1`.
- [`InvalidUnitError`](#invaliduniterror) — if `unit` is not recognised.

**Note:** Only successful readings (non `-1.0`) are included in the
median calculation. If all readings timeout, `-1.0` is returned.

#### `sensor.read_average(samples=5, unit='cm')`

Take multiple readings and return the **arithmetic mean**. This smooths
out random noise but is more sensitive to outliers than the median.

```python
d = sensor.read_average()           # 5 samples, cm
d = sensor.read_average(samples=10) # 10 samples, cm
```

| Parameter | Type  | Default | Description                                |
|-----------|-------|---------|--------------------------------------------|
| `samples` | `int` | `5`     | Number of readings to take (must be ≥ 1).  |
| `unit`    | `str` | `'cm'`  | Supported: `'cm'`, `'mm'`, `'m'`, `'in'`. |

| Returns  | Type    | Description                                                    |
|----------|---------|----------------------------------------------------------------|
| Distance | `float` | Average distance in the requested unit (rounded to 2 d.p.).    |
| `-1.0`   | `float` | All readings timed out.                                        |

**Raises:**
- [`SensorNotAttachedError`](#sensornotattacherror) — if not attached.
- `ValueError` — if `samples < 1`.
- [`InvalidUnitError`](#invaliduniterror) — if `unit` is not recognised.

#### `sensor.last_distance` *(property)*

The last successfully measured distance in **centimetres**, or `None` if
no successful reading has been taken yet (or after `detach()`).

```python
print(f"Last distance: {sensor.last_distance} cm")
```

| Returns       | Type           | Description                          |
|---------------|----------------|--------------------------------------|
| Distance      | `float` or `None` | Last valid reading in cm.         |

> **Note:** This is stored at the `ping()` level and uses the cm unit
> regardless of what unit was requested in `read()`. It updates even if
> the reading subsequently gets filtered out by the 2 cm noise threshold,
> so it may reflect a sub-2 cm value that was reported as `-1`.

---

### Utility Functions

#### `delay(ms)`

Pause execution for a given number of milliseconds. Analogous to
Arduino's `delay()`.

```python
from ultrasonic_like_arduino import delay

delay(1000)   # pause for 1 second
delay(250)    # pause for 250 ms
delay(10.5)   # pause for 10.5 ms (float is accepted)
```

| Parameter | Type          | Description                  |
|-----------|---------------|------------------------------|
| `ms`      | `int`/`float` | Milliseconds to pause.       |

#### `millis()`

Return the current time in milliseconds since the epoch. Analogous to
Arduino's `millis()`.

```python
from ultrasonic_like_arduino import millis

start = millis()
# ... do something ...
elapsed = millis() - start
print(f"Elapsed: {elapsed} ms")
```

| Returns | Type  | Description                         |
|---------|-------|-------------------------------------|
| Time    | `int` | Current time in milliseconds.       |

#### `microseconds()`

Return the current time in microseconds since the epoch. Useful for
high-resolution timing.

```python
from ultrasonic_like_arduino.utils import microseconds

start = microseconds()
# ... do something fast ...
elapsed = microseconds() - start
print(f"Elapsed: {elapsed} µs")
```

| Returns | Type  | Description                         |
|---------|-------|-------------------------------------|
| Time    | `int` | Current time in microseconds.       |

> **Note:** `microseconds()` is defined in `utils.py` but is **not**
> part of the official public `__all__` export list. Import it directly
> from `ultrasonic_like_arduino.utils` if needed.

---

### Exception Hierarchy

All custom exceptions inherit from `UltrasonicError`, which itself
inherits from `Exception`.

```
Exception
 └── UltrasonicError
      ├── BoardConnectionError
      ├── SensorNotAttachedError
      ├── MeasurementTimeoutError
      ├── InvalidUnitError
      └── PinInUseError
```

#### `UltrasonicError`

Base exception for the entire library. Catch this to handle any
library-specific error:

```python
from ultrasonic_like_arduino import UltrasonicError

try:
    board = Board("COM3")
except UltrasonicError as e:
    print(f"Library error: {e}")
```

#### `BoardConnectionError`

Raised when the Arduino board cannot be reached (e.g. wrong port,
board not connected, incorrect firmware).

```python
from ultrasonic_like_arduino import BoardConnectionError

try:
    board = Board("COM99")
except BoardConnectionError as e:
    print(f"Connection failed: {e}")
```

#### `SensorNotAttachedError`

Raised when `ping()`, `read()`, `read_median()`, or `read_average()`
is called before `attach()`.

```python
from ultrasonic_like_arduino import SensorNotAttachedError

sensor = UltrasonicSensor()
try:
    sensor.read()  # not attached yet!
except SensorNotAttachedError as e:
    print(e)  # "Sensor not attached. Call attach(trig, echo) first."
```

#### `MeasurementTimeoutError`

Defined in the exception hierarchy but **currently not raised** by any
method. The library returns `-1` / `-1.0` on timeout instead. Reserved
for future use.

#### `InvalidUnitError`

Raised when `read()`, `read_median()`, or `read_average()` is called
with an unrecognised unit string.

```python
from ultrasonic_like_arduino import InvalidUnitError

try:
    sensor.read(unit='fathoms')
except InvalidUnitError as e:
    print(e)  # "Unknown unit 'fathoms'. Use one of: cm, mm, m, in"
```

#### `PinInUseError`

Defined in the exception hierarchy but **currently not raised** by any
method. Reserved for future use when pin conflict detection is
implemented.

---

## Advanced Usage

### Multiple Sensors

You can attach multiple HC-SR04 sensors to a single Arduino, as long
as each uses a distinct pair of digital pins.

```python
from ultrasonic_like_arduino import Board, UltrasonicSensor

board = Board("COM3")

# Front-facing sensor
front = UltrasonicSensor(max_distance=200)
front.attach(trig=9, echo=10)

# Left-facing sensor
left = UltrasonicSensor(max_distance=150)
left.attach(trig=11, echo=12)

# Right-facing sensor
right = UltrasonicSensor(max_distance=150)
right.attach(trig=13, echo=8)

# Read all three
print(f"Front: {front.read():.1f} cm")
print(f"Left:  {left.read():.1f} cm")
print(f"Right: {right.read():.1f} cm")

# Cleanup
front.detach()
left.detach()
right.detach()
board.close()
```

Each sensor has its own callback, lock, and timing state — they are
fully independent. However, because PyFirmata2 sends DIGITAL_MESSAGE
data per 8-pin port, callbacks for pins on the same port fire together.
The edge-detection logic (`_prev_echo_value`) prevents false triggers.

### Context Manager

The `Board` works as a context manager, automatically closing the
connection when the block exits:

```python
from ultrasonic_like_arduino import Board, UltrasonicSensor

with Board("COM3") as board:
    sensor = UltrasonicSensor()
    sensor.attach(trig=9, echo=10)

    for _ in range(5):
        dist = sensor.read()
        print(f"Distance: {dist} cm")
# board.close() called automatically

# Sensor state persists after the context
print(f"Last reading was: {sensor.last_distance} cm")
sensor.detach()  # still need to detach manually
```

### Noise Filtering

Real-world ultrasonic readings can be noisy due to:
- Acoustic reflections from nearby objects
- Electrical interference on long sensor wires
- Jitter in serial communication timing

**Median filtering** (`read_median`) is generally preferred over
averaging because it completely rejects outliers:

```python
# A single outlier (e.g. 300 cm when the real distance is 50 cm)
# would corrupt an average but be ignored by the median.

raw = sensor.read()              # could be wildly wrong
median = sensor.read_median(5)   # robust against outliers
avg = sensor.read_average(5)     # smoother but outlier-sensitive
```

**When to use each:**

| Method          | Best for                                           |
|-----------------|----------------------------------------------------|
| `read()`        | Fast single-shot checks (obstacle presence).       |
| `read_median()` | Stable, accurate readings (distance measurement).  |
| `read_average()`| Smooth slowly changing distances (ramp detection). |

### Unit Conversion

All units are built-in and validated:

```python
sensor = UltrasonicSensor()
sensor.attach(trig=9, echo=10)

# All return float rounded to 2 decimal places, or -1.0 on timeout
cm  = sensor.read('cm')   # e.g. 45.72
mm  = sensor.read('mm')   # e.g. 457.20
m   = sensor.read('m')    # e.g. 0.46
inc = sensor.read('in')   # e.g. 18.00
```

The conversion uses the speed of sound (34300 cm/s at 20 °C). This
changes slightly with temperature (~0.6 cm/s per °C), but for obstacle
avoidance and presence detection the error is negligible.

### Continuous Monitoring

For obstacle detection loops (e.g. in an autonomous car):

```python
import sys
from ultrasonic_like_arduino import Board, UltrasonicSensor, delay

port = sys.argv[1] if len(sys.argv) > 1 else "COM3"
board = Board(port)
sensor = UltrasonicSensor(max_distance=200)
sensor.attach(trig=9, echo=10)

try:
    while True:
        dist = sensor.read_median(samples=3)

        if dist == -1.0:
            print("No obstacle detected")
        elif dist > 100:
            print(f"Far: {dist:.1f} cm — clear to drive")
        elif dist > 50:
            print(f"Approaching: {dist:.1f} cm — prepare to steer")
        elif dist > 20:
            print(f"Close: {dist:.1f} cm — slow down")
        else:
            print(f"CRITICAL: {dist:.1f} cm — STOP!")

        delay(50)  # 20 Hz update rate
except KeyboardInterrupt:
    pass
finally:
    sensor.detach()
    board.close()
```

### Parsed Output for Scripts

For headless/pipeable output (useful for logging or feeding into other
programs), the `ultrasonic_reader.py` script outputs one number per
line with no headers or debug text:

```bash
python ultrasonic_reader.py COM3
45.72
46.01
44.98
...
```

This can be piped into other programs or redirected to a file:

```bash
python ultrasonic_reader.py COM3 > distances.log
```

---

## Limitations

Be aware of these constraints when using this library:

### Measurement Accuracy

Serial communication between the PC and Arduino introduces latency
(~1–10 ms). While the callback-based timing captures pin transitions
more accurately than polling, there is still uncertainty from:
- The 1 ms sampler interval on the Arduino
- USB serial buffering and latency
- PC OS scheduling jitter

This wrapper is **suitable for obstacle avoidance and presence
detection**, not for precision metrology.

### Minimum Distance

Objects closer than **~2 cm** produce unreliable readings and are
filtered out by the library (returns `-1` / `-1.0`). In practice,
the HC-SR04 itself is unreliable below 5–10 cm due to the long
decay time of the ultrasonic transducer.

### Maximum Distance

The HC-SR04 is specified for 2 cm to 400 cm. The library defaults to
400 cm but is configurable via `UltrasonicSensor(max_distance=...)`.
The timeout is capped at 100 ms regardless of the configured range.

### Speed vs Reliability

Each `ping()` takes approximately:
- 2 ms for the trigger pulse (1 ms settle + 1 ms HIGH)
- Up to the configured timeout waiting for echo (max 100 ms)
- `read_median(5)` takes ~5× the time of a single `read()`

For high-frequency scanning, consider reducing `max_distance` or using
`read()` instead of `read_median()`.

### Temperature Sensitivity

The speed of sound varies with temperature (~0.6 cm/s per °C). The
library uses 34300 cm/s (20 °C). Readings will have a small systematic
error in significantly hotter or colder environments.

---

## Troubleshooting

### "Could not connect to Arduino on COM3"

- Verify the Arduino is plugged in and the correct port is specified.
- Check that **StandardFirmata** is uploaded to the Arduino.
- On Linux, ensure you have read/write permission on the serial port:
  ```bash
  sudo usermod -a -G dialout $USER
  ```
  (log out and back in for the change to take effect)
- On Windows, check Device Manager for the correct COM port number.
- No other program (Arduino IDE, serial monitor) should be using the port.

### All readings return `-1.0`

- Check the wiring (especially TRIG and ECHO pin numbers matching the
  code).
- Ensure the sensor is powered (VCC → 5V, GND → GND).
- Verify the object is within the configured range (default 400 cm).
- The sensor may be too close (< 2 cm) — try measuring a farther object.

### Readings are erratic or jumpy

- Use `read_median()` instead of `read()` to filter noise.
- Check power supply — the HC-SR04 can draw up to 15 mA during
  transmission. A noisy power supply causes erratic readings.
- Avoid placing the sensor near ultrasonic noise sources (motors,
  fans, other ultrasonic sensors operating simultaneously).
- Ensure the sensor is mounted securely and pointing at a flat surface.

### "Sensor not attached" error

Make sure to call `sensor.attach(trig, echo)` before any read operation:

```python
sensor = UltrasonicSensor()
sensor.attach(trig=9, echo=10)  # ← this must come first
distance = sensor.read()
```

---

*For additional help, open an issue on the GitHub repository.*
