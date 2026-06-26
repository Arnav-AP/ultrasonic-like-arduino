import time
import statistics

import ultrasonic_like_arduino.board as board_module
from .exceptions import SensorNotAttachedError, MeasurementTimeoutError, InvalidUnitError


# Speed of sound in various units (cm per microsecond at 20°C).
# Speed of sound = 343 m/s = 34300 cm/s = 0.0343 cm/µs
# Round-trip distance = time * speed / 2
_SOUND_SPEED = {
    'cm': 0.0343,       # cm/µs  → distance(cm) = pulse(µs) * 0.0343 / 2
    'mm': 0.343,        # mm/µs
    'm':  0.000343,     # m/µs
    'in': 0.0135,       # in/µs  (1 in = 2.54 cm)
}

# Conversion factor: pulse_duration(µs) * SPEED_OF_SOUND / 2  = distance
# Pre-computed as pulse_duration * factor = distance
_DISTANCE_FACTOR = {
    'cm': 0.0343 / 2,    # = 0.01715
    'mm': 0.343 / 2,     # = 0.1715
    'm':  0.000343 / 2,  # = 0.0001715
    'in': 0.0135 / 2,    # = 0.00675
}

# Maximum reasonable timeout for HC-SR04 (400 cm range).
# Round-trip time at 400 cm = 2 * 400 / 34300 = ~0.0233 s = 23.3 ms
# Add margin for safety.
_MAX_TIMEOUT_SECONDS = 0.05  # 50 ms


class UltrasonicSensor:
    """Represents an HC-SR04 (or compatible) ultrasonic distance sensor.

    Uses an Arduino running StandardFirmata via PyFirmata2. The sensor
    measures distance by sending a 10 µs pulse on the *trig* pin and
    timing the echo pulse on the *echo* pin.

    **Usage**::

        from ultrasonic_like_arduino import Board, UltrasonicSensor

        board = Board("COM3")
        sensor = UltrasonicSensor()
        sensor.attach(trig=9, echo=10)

        dist = sensor.read()         # distance in cm
        dist = sensor.read('in')     # distance in inches
        raw  = sensor.ping()         # raw pulse duration in µs

        sensor.detach()
        board.close()

    Parameters
    ----------
    max_distance : int or float, optional
        Maximum measurable distance in cm. Controls the echo timeout.
        Defaults to 400 (HC-SR04 spec).
    """

    def __init__(self, max_distance=400):
        self._trig = None
        self._echo = None
        self.trig_pin = None
        self.echo_pin = None
        self.max_distance = max_distance
        self._timeout = min(
            (2 * max_distance) / 34300 + 0.005,  # round-trip time + 5 ms margin
            _MAX_TIMEOUT_SECONDS
        )
        self._last_distance = None

    # ------------------------------------------------------------------
    # Attach / detach
    # ------------------------------------------------------------------

    def attach(self, trig, echo):
        """Bind the ultrasonic sensor to trigger and echo pins.

        Both pins must be digital-capable pins on the Arduino.

        Parameters
        ----------
        trig : int
            Digital pin number for the sensor's TRIG pin (output).
        echo : int
            Digital pin number for the sensor's ECHO pin (input).

        Raises
        ------
        RuntimeError
            If no Board has been created yet.
        """
        board = board_module.Board.get_active_board()
        self.trig_pin = trig
        self.echo_pin = echo

        # TRIG → digital output
        self._trig = board._board.get_pin(f"d:{trig}:o")

        # ECHO → digital input (enables port reporting for this pin)
        self._echo = board._board.get_pin(f"d:{echo}:i")

        # Start the sampler thread so pin values update asynchronously.
        if hasattr(board._board, 'samplerThread'):
            board._board.samplingOn(1)  # 1 ms sampling interval

    def detach(self):
        """Release the sensor pins.

        After calling this, the sensor must be re-attached before
        further readings.
        """
        self._trig = None
        self._echo = None
        self.trig_pin = None
        self.echo_pin = None
        self._last_distance = None

    def attached(self):
        """Check whether the sensor is currently attached to pins.

        Returns
        -------
        bool
            ``True`` if the sensor is attached and ready.
        """
        return self._trig is not None and self._echo is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_attached(self):
        if not self.attached():
            raise SensorNotAttachedError(
                "Sensor not attached. Call attach(trig, echo) first."
            )

    def _send_trigger_pulse(self):
        """Send the 10 µs trigger pulse to start a measurement."""
        # Ensure the pin starts LOW.
        self._trig.write(0)
        self._trig.write(1)
        self._trig.write(0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ping(self):
        """Measure the echo pulse duration in microseconds.

        This is analogous to Arduino's ``pulseIn()``.

        Returns
        -------
        int
            Pulse duration in microseconds, or ``-1`` if a timeout occurred
            (no object detected within range).

        Raises
        ------
        SensorNotAttachedError
            If the sensor has not been attached yet.
        """
        self._ensure_attached()

        # Send the trigger pulse.
        self._send_trigger_pulse()

        # Record the time just after the trigger.
        pulse_start = time.perf_counter()

        # --- Wait for ECHO to go HIGH (with timeout) ---
        timeout_end = time.perf_counter() + self._timeout
        while time.perf_counter() < timeout_end:
            # The sampler thread updates _echo.value asynchronously.
            if self._echo.value == 1:
                pulse_start = time.perf_counter()
                break
        else:
            # Timeout — no echo received.
            return -1

        # --- Wait for ECHO to go LOW (with timeout) ---
        timeout_end = time.perf_counter() + self._timeout
        while time.perf_counter() < timeout_end:
            if self._echo.value == 0:
                pulse_end = time.perf_counter()
                pulse_duration = (pulse_end - pulse_start) * 1_000_000  # seconds → µs
                self._last_distance = pulse_duration * _DISTANCE_FACTOR['cm']
                return int(pulse_duration)
        else:
            # Echo stayed HIGH too long — out of range.
            return -1

    def read(self, unit='cm'):
        """Measure the distance to the nearest object.

        Parameters
        ----------
        unit : str, optional
            Unit of measurement. One of ``'cm'`` (default), ``'mm'``,
            ``'m'``, or ``'in'`` (inches).

        Returns
        -------
        float
            Distance in the requested unit, or ``-1.0`` if no object was
            detected within range.

        Raises
        ------
        SensorNotAttachedError
            If the sensor has not been attached yet.
        InvalidUnitError
            If *unit* is not recognised.
        """
        self._ensure_attached()

        if unit not in _DISTANCE_FACTOR:
            raise InvalidUnitError(
                f"Unknown unit '{unit}'. Use one of: {', '.join(_DISTANCE_FACTOR.keys())}"
            )

        pulse = self.ping()
        if pulse == -1:
            return -1.0

        distance = pulse * _DISTANCE_FACTOR[unit]
        return round(distance, 2)

    def read_median(self, samples=5, unit='cm'):
        """Return the median of multiple distance readings.

        This reduces noise and spurious readings caused by acoustic
        interference or serial timing jitter.

        Parameters
        ----------
        samples : int, optional
            Number of readings to take (default 5). Must be >= 1.
        unit : str, optional
            Unit of measurement (see :meth:`read`).

        Returns
        -------
        float
            Median distance in the requested unit, or ``-1.0`` if all
            readings timed out.

        Raises
        ------
        SensorNotAttachedError
            If the sensor has not been attached yet.
        """
        self._ensure_attached()

        if samples < 1:
            raise ValueError("samples must be at least 1")

        readings = []
        for _ in range(samples):
            d = self.read(unit)
            if d != -1.0:
                readings.append(d)

        if not readings:
            return -1.0

        return round(statistics.median(readings), 2)

    def read_average(self, samples=5, unit='cm'):
        """Return the average of multiple distance readings.

        Parameters
        ----------
        samples : int, optional
            Number of readings to average (default 5). Must be >= 1.
        unit : str, optional
            Unit of measurement (see :meth:`read`).

        Returns
        -------
        float
            Average distance in the requested unit, or ``-1.0`` if all
            readings timed out.
        """
        self._ensure_attached()

        if samples < 1:
            raise ValueError("samples must be at least 1")

        readings = []
        for _ in range(samples):
            d = self.read(unit)
            if d != -1.0:
                readings.append(d)

        if not readings:
            return -1.0

        return round(sum(readings) / len(readings), 2)

    @property
    def last_distance(self):
        """The last successfully measured distance in cm, or ``None``.

        Returns
        -------
        float or None
        """
        return self._last_distance
