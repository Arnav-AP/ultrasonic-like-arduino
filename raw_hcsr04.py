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
import traceback

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

    # Enable sampling so the Iterator thread runs continuously.
    # This is critical: without it, incoming serial data is never read!
    board.samplingOn(1)

    # Callback-based timing state
    cb_lock = threading.Lock()
    echo_high_time = [None]   # list so callback can mutate
    echo_low_time = [None]
    prev_val = [None]
    measurement_done = threading.Event()
    cb_count = [0]            # debug: count how many times callback fires

    def echo_callback(value):
        """Protected callback — any exception here would KILL the Iterator thread."""
        try:
            with cb_lock:
                cb_count[0] += 1
                # Only act on actual transitions
                if value == 1 and prev_val[0] == 0:
                    # Rising edge → echo pulse started
                    echo_high_time[0] = time.perf_counter()
                elif value == 0 and prev_val[0] == 1:
                    # Falling edge → echo pulse ended
                    echo_low_time[0] = time.perf_counter()
                    measurement_done.set()
                prev_val[0] = value
        except Exception as e:
            # If we don't catch this, the Iterator thread dies silently
            # and all future callbacks stop working!
            print(f"\n!!! CALLBACK ERROR: {e}")
            traceback.print_exc()

    echo.register_callback(echo_callback)

    def send_trigger():
        # Ensure TRIG starts LOW, then send a clean pulse.
        # The delay ensures the pulse is long enough (>10 µs).
        trig.write(0)
        time.sleep(0.001)  # 1ms settle
        trig.write(1)
        time.sleep(0.010)  # 10ms pulse (HC-SR04 needs min 10µs)
        trig.write(0)

    def ping():
        with cb_lock:
            echo_high_time[0] = None
            echo_low_time[0] = None
            prev_val[0] = None
        measurement_done.clear()

        # DEBUG: count callbacks before sending
        before_count = cb_count[0]

        send_trigger()
        got = measurement_done.wait(timeout=TIMEOUT_S)

        # DEBUG
        after_count = cb_count[0]
        new_callbacks = after_count - before_count

        with cb_lock:
            if got and echo_high_time[0] is not None and echo_low_time[0] is not None:
                pulse_us = (echo_low_time[0] - echo_high_time[0]) * 1_000_000
                if pulse_us > 0:
                    distance_cm = pulse_us * 0.01715
                    if distance_cm < 2:
                        return -1, None, new_callbacks
                    return pulse_us, distance_cm, new_callbacks
            return -1, None, new_callbacks

    # Give the sensor a moment to stabilize after setup
    time.sleep(2)

    print(f"\nReading 20 samples from TRIG={TRIG}, ECHO={ECHO}...")
    print(f"{'#':>3} {'Pulse':>8} {'Dist':>8} {'CBs':>5} {'Echo state':>12}")
    print("-" * 42)

    for i in range(20):
        pulse, dist_cm, cbs = ping()
        if pulse == -1:
            print(f"{i+1:3d}  {'OUT':>8} {'---':>8} {cbs:>5}")
        else:
            print(f"{i+1:3d}  {int(pulse):>5d}µs  {dist_cm:>6.2f}cm  {cbs:>5}")
        time.sleep(0.1)

    # Stats
    distances = []
    print("\n--- Collecting stats ---")
    for i in range(20):
        pulse, dist_cm, cbs = ping()
        if dist_cm is not None:
            distances.append(dist_cm)
        time.sleep(0.05)

    if distances:
        import statistics
        print(f"\nValid: {len(distances)}/20")
        print(f"Range: {min(distances):.2f} - {max(distances):.2f} cm  (span={max(distances)-min(distances):.2f})")
        print(f"Mean:  {statistics.mean(distances):.2f} cm")
        print(f"Stdev: {statistics.stdev(distances):.2f} cm")
        print(f"Median: {statistics.median(distances):.2f} cm")
    else:
        print("No valid readings.")

    print(f"\nTotal callback fires: {cb_count[0]}")

    # Cleanup
    echo.unregiser_callback()
    board.exit()


if __name__ == '__main__':
    main()
