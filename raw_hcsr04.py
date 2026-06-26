#!/usr/bin/env python3
"""
Raw PyFirmata2 HC-SR04 test — no wrapper, no library, just Firmata.

Usage:
    python raw_hcsr04.py [port]

Default port: /dev/ttyUSB0
"""

import sys
import time
import threading

try:
    import pyfirmata2
except ImportError:
    print("ERROR: pyfirmata2 not installed. Run: pip install pyfirmata2")
    sys.exit(1)


TRIG = 7
ECHO = 8
TIMEOUT_S = 0.1  # 100 ms max wait for echo


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'

    print(f"Connecting to Arduino on {port}...")
    board = pyfirmata2.Arduino(port)
    print("Connected!")

    # Set up pins
    trig = board.get_pin(f"d:{TRIG}:o")
    echo = board.get_pin(f"d:{ECHO}:i")

    # Enable sampling so digital pins report changes
    board.samplingOn(1)  # 1 ms interval

    # Callback-based timing state
    cb_lock = threading.Lock()
    echo_high_time = [None]   # list so callback can mutate
    echo_low_time = [None]
    prev_val = [None]
    measurement_done = threading.Event()

    def echo_callback(value):
        with cb_lock:
            # Only act on actual transitions
            if value == 1 and prev_val[0] == 0:
                echo_high_time[0] = time.perf_counter()
            elif value == 0 and prev_val[0] == 1:
                echo_low_time[0] = time.perf_counter()
                measurement_done.set()
            prev_val[0] = value

    echo.register_callback(echo_callback)

    def send_trigger():
        trig.write(1)
        trig.write(0)

    def ping():
        with cb_lock:
            echo_high_time[0] = None
            echo_low_time[0] = None
            prev_val[0] = None
        measurement_done.clear()

        send_trigger()
        got = measurement_done.wait(timeout=TIMEOUT_S)

        with cb_lock:
            if got and echo_high_time[0] is not None and echo_low_time[0] is not None:
                pulse_us = (echo_low_time[0] - echo_high_time[0]) * 1_000_000
                if pulse_us > 0:
                    distance_cm = pulse_us * 0.01715  # speed of sound
                    # Reject noise below 2 cm
                    if distance_cm < 2:
                        return -1, None
                    return pulse_us, distance_cm
            return -1, None

    print(f"\nReading 20 samples from TRIG={TRIG}, ECHO={ECHO}...\n")

    for i in range(20):
        pulse, dist_cm = ping()
        if pulse == -1:
print(f"  {i+1:2d}: OUT        (timeout or noise)")
            else:
                print(f"  {i+1:2d}: {int(pulse):5d} µs  →  {dist_cm:6.2f} cm")
        time.sleep(0.05)

    # Stats
    distances = []
    print("\n--- Done ---")
    for i in range(20):
        pulse, dist_cm = ping()
        if dist_cm is not None:
            distances.append(dist_cm)
        time.sleep(0.02)

    if distances:
        import statistics
        print(f"Valid: {len(distances)}/20")
        print(f"Range: {min(distances):.2f} - {max(distances):.2f} cm  (span={max(distances)-min(distances):.2f})")
        print(f"Mean:  {statistics.mean(distances):.2f} cm")
        print(f"Stdev: {statistics.stdev(distances):.2f} cm")
    else:
        print("No valid readings.")

    # Cleanup
    echo.unregiser_callback()
    board.exit()


if __name__ == '__main__':
    main()
