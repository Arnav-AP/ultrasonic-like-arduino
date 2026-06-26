from .exceptions import BoardConnectionError


# Module-level active board reference (singleton-style, mirrors MegaWrapper).
_active_board = None


class Board:
    """Represents a connection to an Arduino board running StandardFirmata.

    This is the entry point for all sensor operations. Create one ``Board``
    before attaching any ultrasonic sensors.

    **Usage**::

        board = Board("COM3")
        sensor = UltrasonicSensor()
        sensor.attach(trig=9, echo=10)
        distance = sensor.read()
        board.close()

    Parameters
    ----------
    port : str
        The serial port the Arduino is connected to (e.g. ``/dev/ttyUSB0``,
        ``COM3``, ``/dev/cu.usbmodem14101``).
    """

    def __init__(self, port):
        global _active_board

        # Lazy import so tests can monkeypatch pyfirmata2.Arduino.
        from pyfirmata2 import Arduino  # noqa: PLC0415

        try:
            self._board = Arduino(port)
        except Exception as e:
            raise BoardConnectionError(
                f"Could not connect to Arduino on {port}: {e}"
            )

        self.port = port
        self._connected = True

        # Register as the active board (used by UltrasonicSensor.attach).
        _active_board = self

    # ------------------------------------------------------------------
    # Singleton access (used by UltrasonicSensor)
    # ------------------------------------------------------------------

    @staticmethod
    def get_active_board():
        """Return the most recently created Board instance.

        Returns
        -------
        Board
            The active board instance.

        Raises
        ------
        RuntimeError
            If no Board has been created yet.
        """
        global _active_board
        if _active_board is None:
            raise RuntimeError(
                "No board initialised. Create a Board first."
            )
        return _active_board

    # ------------------------------------------------------------------
    # Connection state
    # ------------------------------------------------------------------

    def is_connected(self):
        """Check whether the board is still connected.

        Returns
        -------
        bool
            ``True`` if the board connection is open.
        """
        return self._connected

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self):
        """Close the serial connection to the Arduino.

        This stops the sampler thread (if running), disables reporting,
        and releases the serial port.
        """
        if self._board:
            try:
                self._board.exit()
            except Exception:
                pass  # Best-effort cleanup.
            self._connected = False

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
