"""Basic example: reading distance from an HC-SR04 ultrasonic sensor.

Prerequisites:
    1. An Arduino running StandardFirmata
       (File → Examples → Firmata → StandardFirmata)
    2. HC-SR04 wired as:
         VCC → Arduino 5V
         GND → Arduino GND
         TRIG → Arduino digital pin 9
         ECHO → Arduino digital pin 10
    3. This package installed (`pip install -e .`)

Usage:
    python examples/basic_usage.py

    On Windows, you may need to specify the COM port:
        python examples/basic_usage.py COM5

    On Linux:
        python examples/basic_usage.py /dev/ttyUSB0

    On macOS:
        python examples/basic_usage.py /dev/cu.usbmodem14101
"""

import sys
import time

from ultrasonic_like_arduino import Board, UltrasonicSensor, delay


def main():
    # Determine port from command line or use default.
    port = sys.argv[1] if len(sys.argv) > 1 else "COM3"
    print(f"Connecting to Arduino on {port}...")

    try:
        board = Board(port)
    except Exception as e:
        print(f"Failed to connect: {e}")
        print("Make sure the Arduino is connected and running StandardFirmata.")
        sys.exit(1)

    print("Connected! Creating sensor...")
    sensor = UltrasonicSensor(max_distance=400)

    try:
        sensor.attach(trig=9, echo=10)
        print(f"Sensor attached to TRIG={sensor.trig_pin}, ECHO={sensor.echo_pin}")
        print("Reading distance. Press Ctrl+C to stop.\n")

        while True:
            # Single reading in cm.
            dist_cm = sensor.read('cm')
            if dist_cm != -1.0:
                print(f"Distance: {dist_cm:6.2f} cm  ({dist_cm / 2.54:5.2f} in)")
            else:
                print("Out of range (no object detected)")

            # Also demonstrate median filtering.
            # dist_median = sensor.read_median(samples=5)
            # print(f"  Median (5): {dist_median:6.2f} cm")

            delay(200)  # 200 ms between readings

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        print("Cleaning up...")
        sensor.detach()
        board.close()
        print("Done.")


if __name__ == "__main__":
    main()
