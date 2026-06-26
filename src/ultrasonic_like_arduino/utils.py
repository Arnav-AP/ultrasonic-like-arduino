import time


def delay(ms):
    """Pause execution for *ms* milliseconds.

    Analogous to Arduino's ``delay()``.

    Parameters
    ----------
    ms : int or float
        Milliseconds to pause.
    """
    time.sleep(ms / 1000)


def millis():
    """Return the number of milliseconds since the epoch.

    Analogous to Arduino's ``millis()``.

    Returns
    -------
    int
        Current time in milliseconds.
    """
    return int(time.time() * 1000)


def microseconds():
    """Return the number of microseconds since the epoch.

    Useful for high-resolution timing of sensor pulses.

    Returns
    -------
    int
        Current time in microseconds.
    """
    return int(time.time() * 1_000_000)
