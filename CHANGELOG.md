# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0-beta] — 2026-06-26

### Added

- **`Board` class** — Arduino connection via PyFirmata2 with singleton access, context manager support, and automatic cleanup
- **`UltrasonicSensor` class** — Arduino-style API for HC-SR04 distance measurement:
  - `attach(trig, echo)` / `detach()` — bind and release sensor pins
  - `ping()` — raw echo pulse duration in microseconds
  - `read(unit)` — distance in cm, mm, m, or inches
  - `read_median(samples, unit)` — median filtering for noise reduction
  - `read_average(samples, unit)` — averaging for smoother readings
  - `last_distance` property — last valid measured distance
- **Callback-based echo timing** — Uses PyFirmata2's digital pin callbacks with `threading.Event` and `threading.Lock` for accurate, non-blocking pulse measurement
- **Noise rejection** — readings below 2 cm are discarded as electrical noise
- **Utility functions** — `delay(ms)` and `millis()` mirroring Arduino's API
- **Custom exception hierarchy**:
  - `UltrasonicError` (base)
  - `BoardConnectionError`
  - `SensorNotAttachedError`
  - `MeasurementTimeoutError`
  - `InvalidUnitError`
  - `PinInUseError`
- **Test suite** — 27 tests covering board lifecycle, sensor attach/detach, error handling, edge cases, and utilities (mocked, no hardware required)
- **Example script** — `examples/basic_usage.py` with continuous reading loop
- **Raw test script** — `raw_hcsr04.py` for direct PyFirmata2 testing without the wrapper
- **Clean reader script** — `ultrasonic_reader.py` for simple headless distance output

### Fixed

- Callback exception guard prevents PyFirmata2 sampler thread from dying silently
- Reliable trigger pulse sequence with proper settle timing
- Edge detection on echo pin (rising/falling) for accurate timestamping
- Pulse duration cast to int for consistent return type

### Known Limitations

- Measurement accuracy limited by serial communication latency (~1–10 ms)
- Minimum reliable distance is approximately 5–10 cm
- Not suitable for high-precision or high-speed applications — consider a native Arduino sketch for those use cases

---

*Initial release of `ultrasonic-like-arduino`.*
