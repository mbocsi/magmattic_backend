import RPi.GPIO as GPIO
from .motor_config import *
import time

# Test script for DM542s motor controller, thank you Gemini

# Motor control parameters
speed = 0.25  # hz
step_delay = 1 / (2 * STEPS_PER_REV * speed)

# Setup GPIO
GPIO.setmode(GPIO.BCM)  # Maybe board
GPIO.setup(PUL, GPIO.OUT)
GPIO.setup(DIR, GPIO.OUT)
GPIO.setup(ENA, GPIO.OUT)

# Enable driver
GPIO.output(ENA, GPIO.HIGH)  # Disable at start


def rotate_steps(steps, direction):
    GPIO.output(DIR, direction)
    GPIO.output(ENA, GPIO.LOW)  # Enable driver
    for _ in range(steps):
        GPIO.output(PUL, GPIO.HIGH)
        time.sleep(step_delay)
        GPIO.output(PUL, GPIO.LOW)
        time.sleep(step_delay)
    GPIO.output(ENA, GPIO.HIGH)  # Disable after rotation


try:
    # Rotate clockwise 1 revolution
    rotate_steps(STEPS_PER_REV, 1)
    time.sleep(1)

    # Rotate counterclockwise 0.5 revolution
    rotate_steps(STEPS_PER_REV // 2, 0)
    time.sleep(1)

except KeyboardInterrupt:
    GPIO.cleanup()

finally:
    GPIO.cleanup()
