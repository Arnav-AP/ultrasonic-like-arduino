class UltrasonicError(Exception):
    """Base exception for ultrasonic-like-arduino."""
    pass


class BoardConnectionError(UltrasonicError):
    """Raised when the board cannot be reached."""
    pass


class SensorNotAttachedError(UltrasonicError):
    """Raised when an operation is attempted before attaching the sensor."""
    pass


class MeasurementTimeoutError(UltrasonicError):
    """Raised when the sensor echo times out (no object detected)."""
    pass


class InvalidUnitError(UltrasonicError):
    """Raised when an invalid unit is specified."""
    pass


class PinInUseError(UltrasonicError):
    """Raised when a pin is already configured for another use."""
    pass
