import RPi.GPIO as GPIO  # type: ignore
from motor_config import *
import time
import numpy as np

# Test script for motor controller (mine now, sorry not sorry gemini)

# Setup GPIO
GPIO.setmode(GPIO.BCM)  # Maybe board
GPIO.setup(PUL, GPIO.OUT)
GPIO.setup(DIR, GPIO.OUT)
GPIO.setup(ENA, GPIO.OUT)

GPIO.output(ENA, GPIO.HIGH)  # Disable at start


def rotate(duration, omega):
    pulse_pin = GPIO.PWM(PUL, abs(omega * STEPS_PER_REV))
    print(int(np.sign(omega)))
    GPIO.output(DIR, int(np.sign(omega)))
    GPIO.output(ENA, GPIO.LOW)
    pulse_pin.start(DUTY)

    time.sleep(duration)
    pulse_pin.stop()
    GPIO.output(ENA, GPIO.HIGH)  # Disable after rotation


try:
    rotate(1, 0.25)
    rotate(1, -0.25)
except KeyboardInterrupt:
    GPIO.cleanup()

finally:
    GPIO.cleanup()
