# Contributing to ultrasonic-like-arduino

> **Note:** This file has been modified using AI.

Thank you for contributing to **ultrasonic-like-arduino** — an Arduino-style HC-SR04 ultrasonic distance sensor library for Python using PyFirmata2.

## Quick Links

- **PyPI:** `pip install ultrasonic-like-arduino` (install from source: `pip install -e path/to/ultrasonic-like-arduino`)
- **Issues:** GitHub Issues
- **Discussions:** GitHub Discussions

---

## Ways to Contribute

### Bug Reports
- Search existing issues first
- Include: Python version, OS, Arduino board, HC-SR04 wiring, PyFirmata2 version
- Minimal reproducible example
- Note: Serial latency (~1–10 ms) limits precision — this is expected (see [README Limitations](README.md#limitations))

### Feature Requests
- Explain the use case
- Consider API consistency with `motor-like-arduino`, `servo-like-arduino`, `PyFirmata Simplifier`
- Keep it simple — focus on HC-SR04 and compatible sensors

### Pull Requests
**We welcome PRs for:**
- Bug fixes (especially callback/timing edge cases)
- Additional noise filtering methods
- Support for other ultrasonic sensors (HY-SRF05, JSN-SR04T, etc.)
- Documentation improvements
- Type hints / stubs
- Tests in `tests/`

**Before submitting:**
1. Run tests: `python -m pytest tests/`
2. Run examples: `python examples/basic_usage.py`
3. Follow existing code style (PEP 8, type hints, comprehensive docstrings)
4. Update `CHANGELOG.md` under `## Unreleased`
5. Keep changes focused — one logical change per PR

---

## Development Setup

```bash
git clone https://github.com/vihaanvp/ultrasonic-like-arduino.git
cd ultrasonic-like-arduino
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
pip install pytest  # for tests
```

**Requirements:**
- Python 3.8+
- Arduino running StandardFirmata (File → Examples → Firmata → StandardFirmata)
- `pyfirmata2`, `pyserial`

---

## Project Structure

```
ultrasonic-like-arduino/
├── src/ultrasonic_like_arduino/     # Package source
│   ├── __init__.py                  # Public exports
│   ├── board.py                     # Board class (singleton, connection)
│   ├── sensor.py                    # UltrasonicSensor class (callback-based timing)
│   ├── exceptions.py                # Custom exception hierarchy
│   ├── utils.py                     # delay(), millis() — Arduino-like utilities
│   └── version.py                   # __version__
├── examples/                        # Runnable examples
│   └── basic_usage.py
├── tests/                           # Unit tests
│   ├── __init__.py
│   └── test_sensor.py
├── pyproject.toml                   # Build config (setuptools)
├── requirements.txt
├── README.md
├── USAGE.md                         # Extended usage guide
├── CHANGELOG.md
├── LICENSE
└── CONTRIBUTING.md                  # This file
```

---

## Key Implementation Details

### Callback-Based Timing (Critical)
The sensor uses **PyFirmata2 pin callbacks** (not blocking `pulseIn`-style polling) for accurate timing:

1. `attach()` registers a callback on the ECHO pin via `pin.register_callback()`
2. `_echo_callback()` runs in the PyFirmata2 **sampler thread** on every digital port update
3. Rising edge (0→1) captures `_echo_high_time = time.perf_counter()`
4. Falling edge (1→0) captures `_echo_low_time` and sets `_measurement_done` Event
5. `ping()` sends trigger pulse, waits on `_measurement_done.wait(timeout=...)`
6. **Critical:** All callback code is wrapped in `try/except` — any exception kills the Iterator thread permanently

### Thread Safety
- `threading.Lock` (`_cb_lock`) protects shared timestamps
- `threading.Event` (`_measurement_done`) signals measurement completion
- Callback must be fast and exception-safe

### Distance Calculation
```python
# Speed of sound = 34300 cm/s = 0.0343 cm/µs
# distance(cm) = pulse(µs) * 0.0343 / 2 = pulse * 0.01715
_DISTANCE_FACTOR = {
    'cm': 0.01715,
    'mm': 0.1715,
    'm':  0.0001715,
    'in': 0.00675,
}
```

### Noise Filtering
- `read_median(samples=5)` — statistical median (robust to outliers)
- `read_average(samples=5)` — arithmetic mean
- Minimum distance threshold: 2 cm (rejects electrical noise)

---

## Testing

```bash
# Run unit tests (requires hardware or mock)
python -m pytest tests/ -v

# Run examples (requires Arduino + HC-SR04)
python examples/basic_usage.py
```

**Test Coverage Gaps (help wanted):**
- Mock PyFirmata2 board for CI testing without hardware
- Edge cases: timeout, callback exceptions, pin conflicts
- Multiple sensors on same board

---

## Release Process

Maintainer only:
```bash
# Update version in src/ultrasonic_like_arduino/version.py
# Update CHANGELOG.md
git tag vX.Y.Z
git push origin vX.Y.Z
python -m build
python -m twine upload dist/*
```

---

## Related Projects

| Project | Purpose |
|---------|---------|
| [motor-like-arduino](https://github.com/vihaanvp/motor-like-arduino) | DC motor control |
| [servo-like-arduino](https://github.com/vihaanvp/servo-like-arduino) | Servo control |
| [PyFirmata Simplifier](https://github.com/vihaanvp/pyfirmata-simplifier) | Unified motor + servo + ultrasonic |

When adding features, consider API consistency across these libraries.

---

## License

By contributing, you agree your contributions are licensed under the MIT License (see [LICENSE](LICENSE)).