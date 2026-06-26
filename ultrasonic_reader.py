#!/usr/bin/env python3
"""
Clean HC-SR04 distance reader using ultrasonic_like_arduino wrapper.

Outputs one distance per line (cm), retrying silently on bad readings.
No headers, no noise, no debug — just numbers.

Usage:
    python ultrasonic_reader.py [port]

Default port: /dev/ttyUSB0
"""

import sys
import time

from ultrasonic_like_arduino import Board, UltrasonicSensor


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
    board = Board(port)
    sensor = UltrasonicSensor()
    sensor.attach(trig=7, echo=8)

    # Give the sensor a moment to stabilize after setup
    time.sleep(1)

    try:
        while True:
            d = sensor.read_median(samples=5)
            if d != -1.0:
                print(d)
    except KeyboardInterrupt:
        pass
    finally:
        sensor.detach()
        board.close()


if __name__ == '__main__':
    main()
