"""Tests for the ultrasonic-like-arduino package.

These tests use a mock board so they can run without an actual Arduino
connected. They verify logic, error handling, edge cases, and the public
API contract.
"""
import sys
import os

# Add the src directory to the path so we can import the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import time
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Mock pyfirmata2 before importing our package
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_pyfirmata2(monkeypatch):
    """Replace pyfirmata2.Arduino with a mock so tests run without hardware."""
    mock_arduino = MagicMock()
    mock_arduino.AUTODETECT = None

    # Mock pin objects returned by get_pin
    class MockPin:
        def __init__(self, pin_def):
            self.pin_def = pin_def
            self.mode = None
            self.value = 0  # default LOW
            self.reporting = False
            self.callback = None

        def write(self, value):
            self.value = value

        def read(self):
            return self.value

        def enable_reporting(self):
            self.reporting = True

        def disable_reporting(self):
            self.reporting = False

        def register_callback(self, cb):
            self.callback = cb

        def unregiser_callback(self):
            self.callback = None

    def mock_get_pin(pin_def):
        return MockPin(pin_def)

    def mock_sampling_on(interval):
        pass

    def mock_exit():
        pass

    mock_arduino_instance = MagicMock()
    mock_arduino_instance.get_pin = mock_get_pin
    mock_arduino_instance.samplingOn = mock_sampling_on
    mock_arduino_instance.exit = mock_exit
    mock_arduino_instance.taken = {'digital': {}, 'analog': {}}

    # Make the constructor return our mock instance
    mock_arduino.return_value = mock_arduino_instance

    monkeypatch.setattr('pyfirmata2.Arduino', mock_arduino)

    import ultrasonic_like_arduino
    return ultrasonic_like_arduino


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBoard:
    """Board connection and lifecycle."""

    def test_board_creation(self, mock_pyfirmata2):
        """Creating a Board should succeed."""
        board = mock_pyfirmata2.Board("COM3")
        assert board.port == "COM3"
        assert board.is_connected() is True

    def test_board_close(self, mock_pyfirmata2):
        """Board.close() should mark as disconnected."""
        board = mock_pyfirmata2.Board("COM3")
        board.close()
        assert board.is_connected() is False

    def test_get_active_board(self, mock_pyfirmata2):
        """get_active_board() should return the most recent Board."""
        board1 = mock_pyfirmata2.Board("COM3")
        board2 = mock_pyfirmata2.Board("COM5")
        active = mock_pyfirmata2.Board.get_active_board()
        assert active is board2

    def test_get_active_board_no_board(self, mock_pyfirmata2):
        """get_active_board() should raise RuntimeError if no board exists."""
        # Clear the global _active_board via the module
        import ultrasonic_like_arduino.board as board_mod
        board_mod._active_board = None
        with pytest.raises(RuntimeError, match="No board initialised"):
            mock_pyfirmata2.Board.get_active_board()

    def test_context_manager(self, mock_pyfirmata2):
        """Board should work as a context manager and close on exit."""
        with mock_pyfirmata2.Board("COM3") as board:
            assert board.is_connected() is True
        assert board.is_connected() is False

    def test_board_connection_error(self, monkeypatch):
        """Board creation should raise BoardConnectionError on failure."""
        import ultrasonic_like_arduino
        import ultrasonic_like_arduino.board as board_mod

        def failing_arduino(port):
            raise Exception("Port not found")

        monkeypatch.setattr('pyfirmata2.Arduino', failing_arduino)

        with pytest.raises(ultrasonic_like_arduino.BoardConnectionError):
            board_mod.Board("COM99")


class TestUltrasonicSensor:
    """Ultrasonic sensor operations."""

    def test_attach(self, mock_pyfirmata2):
        """Attaching a sensor should set trig and echo pins."""
        board = mock_pyfirmata2.Board("COM3")
        sensor = mock_pyfirmata2.UltrasonicSensor()
        sensor.attach(trig=9, echo=10)

        assert sensor.trig_pin == 9
        assert sensor.echo_pin == 10
        assert sensor.attached() is True

    def test_detach(self, mock_pyfirmata2):
        """Detaching should clear pin references."""
        board = mock_pyfirmata2.Board("COM3")
        sensor = mock_pyfirmata2.UltrasonicSensor()
        sensor.attach(trig=9, echo=10)
        sensor.detach()

        assert sensor.attached() is False
        assert sensor.trig_pin is None

    def test_read_before_attach(self, mock_pyfirmata2):
        """read() before attach() should raise SensorNotAttachedError."""
        board = mock_pyfirmata2.Board("COM3")
        sensor = mock_pyfirmata2.UltrasonicSensor()
        with pytest.raises(mock_pyfirmata2.SensorNotAttachedError):
            sensor.read()

    def test_ping_before_attach(self, mock_pyfirmata2):
        """ping() before attach() should raise SensorNotAttachedError."""
        board = mock_pyfirmata2.Board("COM3")
        sensor = mock_pyfirmata2.UltrasonicSensor()
        with pytest.raises(mock_pyfirmata2.SensorNotAttachedError):
            sensor.ping()

    def test_invalid_unit(self, mock_pyfirmata2):
        """read() with an invalid unit should raise InvalidUnitError."""
        board = mock_pyfirmata2.Board("COM3")
        sensor = mock_pyfirmata2.UltrasonicSensor()
        sensor.attach(trig=9, echo=10)
        with pytest.raises(mock_pyfirmata2.InvalidUnitError):
            sensor.read(unit='fathoms')

    def test_read_timeout_returns_negative_one(self, mock_pyfirmata2):
        """When echo never goes HIGH, read() should return -1.0."""
        board = mock_pyfirmata2.Board("COM3")
        sensor = mock_pyfirmata2.UltrasonicSensor()
        sensor.attach(trig=9, echo=10)

        # Keep echo pin LOW (never goes HIGH → timeout)
        sensor._echo.value = 0

        result = sensor.read()
        assert result == -1.0

    def test_ping_timeout_returns_negative_one(self, mock_pyfirmata2):
        """When echo never goes HIGH, ping() should return -1."""
        board = mock_pyfirmata2.Board("COM3")
        sensor = mock_pyfirmata2.UltrasonicSensor()
        sensor.attach(trig=9, echo=10)

        sensor._echo.value = 0

        result = sensor.ping()
        assert result == -1

    @pytest.mark.skip(reason="Requires timing-dependent mock for echo pulse")
    def test_read_returns_distance(self, mock_pyfirmata2):
        """With proper echo simulation, read() should return a distance."""
        # This test needs more sophisticated mocking of the timing loop.
        # It's included as a placeholder for hardware-in-the-loop testing.
        pass

    def test_read_median_with_timeout(self, mock_pyfirmata2):
        """read_median() should return -1.0 if all readings timeout."""
        board = mock_pyfirmata2.Board("COM3")
        sensor = mock_pyfirmata2.UltrasonicSensor()
        sensor.attach(trig=9, echo=10)

        sensor._echo.value = 0
        result = sensor.read_median(samples=3)
        assert result == -1.0

    def test_read_average_with_timeout(self, mock_pyfirmata2):
        """read_average() should return -1.0 if all readings timeout."""
        board = mock_pyfirmata2.Board("COM3")
        sensor = mock_pyfirmata2.UltrasonicSensor()
        sensor.attach(trig=9, echo=10)

        sensor._echo.value = 0
        result = sensor.read_average(samples=3)
        assert result == -1.0

    def test_last_distance_none_initially(self, mock_pyfirmata2):
        """last_distance should be None before any successful reading."""
        board = mock_pyfirmata2.Board("COM3")
        sensor = mock_pyfirmata2.UltrasonicSensor()
        sensor.attach(trig=9, echo=10)
        assert sensor.last_distance is None

    def test_detach_after_attach(self, mock_pyfirmata2):
        """Detach should work correctly after attach."""
        board = mock_pyfirmata2.Board("COM3")
        sensor = mock_pyfirmata2.UltrasonicSensor()
        sensor.attach(trig=9, echo=10)
        assert sensor.attached() is True
        sensor.detach()
        assert sensor.attached() is False

    def test_read_median_invalid_samples(self, mock_pyfirmata2):
        """read_median() with samples < 1 should raise ValueError."""
        board = mock_pyfirmata2.Board("COM3")
        sensor = mock_pyfirmata2.UltrasonicSensor()
        sensor.attach(trig=9, echo=10)
        with pytest.raises(ValueError):
            sensor.read_median(samples=0)

    def test_read_average_invalid_samples(self, mock_pyfirmata2):
        """read_average() with samples < 1 should raise ValueError."""
        board = mock_pyfirmata2.Board("COM3")
        sensor = mock_pyfirmata2.UltrasonicSensor()
        sensor.attach(trig=9, echo=10)
        with pytest.raises(ValueError):
            sensor.read_average(samples=0)

    def test_attach_twice(self, mock_pyfirmata2):
        """Attaching to different pins should work."""
        board = mock_pyfirmata2.Board("COM3")
        sensor = mock_pyfirmata2.UltrasonicSensor()
        sensor.attach(trig=9, echo=10)
        assert sensor.trig_pin == 9
        sensor.attach(trig=8, echo=11)
        assert sensor.trig_pin == 8
        assert sensor.echo_pin == 11


class TestUtils:
    """Utility functions."""

    def test_delay(self, mock_pyfirmata2):
        """delay() should pause for approximately the requested time."""
        start = time.time()
        mock_pyfirmata2.delay(50)  # 50 ms
        elapsed = (time.time() - start) * 1000
        assert 40 <= elapsed <= 200  # generous tolerance

    def test_millis(self, mock_pyfirmata2):
        """millis() should return an integer."""
        result = mock_pyfirmata2.millis()
        assert isinstance(result, int)
        assert result > 0

    def test_millis_increasing(self, mock_pyfirmata2):
        """Consecutive calls to millis() should increase."""
        t1 = mock_pyfirmata2.millis()
        time.sleep(0.01)
        t2 = mock_pyfirmata2.millis()
        assert t2 >= t1


class TestExceptions:
    """Exception hierarchy."""

    def test_exception_inheritance(self, mock_pyfirmata2):
        """All custom exceptions should inherit from UltrasonicError."""
        assert issubclass(
            mock_pyfirmata2.BoardConnectionError,
            mock_pyfirmata2.UltrasonicError
        )
        assert issubclass(
            mock_pyfirmata2.SensorNotAttachedError,
            mock_pyfirmata2.UltrasonicError
        )
        assert issubclass(
            mock_pyfirmata2.MeasurementTimeoutError,
            mock_pyfirmata2.UltrasonicError
        )
        assert issubclass(
            mock_pyfirmata2.InvalidUnitError,
            mock_pyfirmata2.UltrasonicError
        )
        assert issubclass(
            mock_pyfirmata2.PinInUseError,
            mock_pyfirmata2.UltrasonicError
        )


class TestVersion:
    """Package version."""

    def test_version_exists(self, mock_pyfirmata2):
        """Package should have a __version__."""
        assert hasattr(mock_pyfirmata2, '__version__')
        assert isinstance(mock_pyfirmata2.__version__, str)


class TestImports:
    """All public API members should be importable from the package root."""

    def test_all_imports(self, mock_pyfirmata2):
        """Every name in __all__ should be accessible."""
        expected = [
            "Board",
            "UltrasonicSensor",
            "delay",
            "millis",
            "UltrasonicError",
            "BoardConnectionError",
            "SensorNotAttachedError",
            "MeasurementTimeoutError",
            "InvalidUnitError",
            "PinInUseError",
            "__version__",
        ]
        for name in expected:
            assert hasattr(mock_pyfirmata2, name), f"Missing {name} in package"
