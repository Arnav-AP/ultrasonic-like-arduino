import time
import statistics
import threading

import ultrasonic_like_arduino.board as board_module
from .exceptions import SensorNotAttachedError, InvalidUnitError


# Conversion factor: pulse_duration(µs) * SPEED_OF_SOUND / 2  = distance
# Speed of sound = 34300 cm/s = 0.0343 cm/µs
# distance(cm) = pulse(µs) * 0.0343 / 2 = pulse * 0.01715
_DISTANCE_FACTOR = {
    'cm': 0.0343 / 2,    # 0.01715
    'mm': 0.343 / 2,     # 0.1715
    'm':  0.000343 / 2,  # 0.0001715
    'in': 0.0135 / 2,    # 0.00675
}

# Round-trip time at 400 cm = 2 * 400 / 34300 = ~0.0233 s
# Add margin for safety.
_MAX_TIMEOUT_SECONDS = 0.10  # 100 ms


class UltrasonicSensor:
    """Represents an HC-SR04 (or compatible) ultrasonic distance sensor.

    Uses an Arduino running StandardFirmata via PyFirmata2. The sensor
    measures distance by sending a pulse on the *trig* pin and
    timing the echo pulse on the *echo* pin via digital pin callbacks.

    **Usage**::

        from ultrasonic_like_arduino import Board, UltrasonicSensor

        board = Board("/dev/ttyUSB0")
        sensor = UltrasonicSensor()
        sensor.attach(trig=7, echo=8)

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
            (2 * max_distance) / 34300 + 0.01,  # round-trip + 10 ms margin
            _MAX_TIMEOUT_SECONDS
        )
        self._last_distance = None

        # Callback-based timing state (thread-safe)
        self._cb_lock = threading.Lock()
        self._echo_high_time = None
        self._echo_low_time = None
        self._measurement_done = threading.Event()
        self._old_callback = None  # store previous callback if any

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

        # Register our callback on the echo pin.
        # The callback fires from the sampler thread when a DIGITAL_MESSAGE
        # updates this pin's value. We capture timestamps here because
        # they're much closer to the actual pin transition than polling
        # from the main thread.
        self._old_callback = self._echo.callback
        self._echo.register_callback(self._echo_callback)

        # Start the sampler thread so pin values update asynchronously.
        if hasattr(board._board, 'samplerThread'):
            board._board.samplingOn(1)  # 1 ms sampling interval

    def detach(self):
        """Release the sensor pins.

        After calling this, the sensor must be re-attached before
        further readings.
        """
        if self._echo is not None:
            # Restore old callback (or None)
            self._echo.unregiser_callback()
            if self._old_callback is not None:
                self._echo.register_callback(self._old_callback)
            self._old_callback = None
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

    def _echo_callback(self, value):
        """Called from the sampler thread when the echo pin value changes.

        Records precise timestamps used to calculate the echo pulse width.
        """
        with self._cb_lock:
            if value == 1:
                # ECHO just went HIGH → mark the start of the echo pulse
                self._echo_high_time = time.perf_counter()
            else:
                # ECHO just went LOW → mark the end
                self._echo_low_time = time.perf_counter()
                self._measurement_done.set()

    def _send_trigger_pulse(self):
        """Send the trigger pulse to start a measurement.

        The HC-SR04 needs a minimum 10 µs HIGH pulse on TRIG.
        With Firmata's serial latency the pulse will be ~1-5 ms,
        which is well within the sensor's tolerance.
        """
        self._trig.write(1)
        self._trig.write(0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ping(self):
        """Measure the echo pulse duration in microseconds.

        Uses PyFirmata2's pin callback mechanism for accurate timing.
        The callback fires from the sampler thread when the Arduino
        reports a digital port state change, capturing timestamps
        close to the actual pin transitions.

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

        # Prepare for a new measurement.
        with self._cb_lock:
            self._echo_high_time = None
            self._echo_low_time = None
        self._measurement_done.clear()

        # Send the trigger pulse.
        self._send_trigger_pulse()

        # Wait until the callback signals that ECHO went LOW,
        # or until timeout.
        got_measurement = self._measurement_done.wait(timeout=self._timeout)

        with self._cb_lock:
            if got_measurement and self._echo_high_time is not None and self._echo_low_time is not None:
                # Both timestamps captured — calculate pulse width.
                pulse_duration = (self._echo_low_time - self._echo_high_time) * 1_000_000  # seconds → µs
                if pulse_duration > 0:
                    self._last_distance = pulse_duration * _DISTANCE_FACTOR['cm']
                    return max(1, int(pulse_duration))

            # If echo_high_time is set but echo_low_time is not,
            # ECHO went HIGH but never came LOW (stuck high or timeout).
            # If echo_high_time is None, the trigger pulse may not have
            # been received, or the sensor isn't responding.
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
