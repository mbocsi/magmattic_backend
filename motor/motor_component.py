import logging
import asyncio
import numpy as np

from . import BaseMotorComponent
from .motor_config import *

logger = logging.getLogger(__name__)


class MotorComponent(BaseMotorComponent):

    def __init__(
        self, pub_queue: asyncio.Queue, sub_queue: asyncio.Queue, init_speed=5
    ):
        """
        Motor component implementation for controlling a stepper motor on a Raspberry Pi.

        Args:
            pub_queue (asyncio.Queue): Queue to publish motor data.
            sub_queue (asyncio.Queue): Queue to receive control commands.
            init_speed (float, optional): Initial frequency of rotation (Hz). Defaults to 5.
        """
        super().__init__(pub_queue, sub_queue, init_speed)
        import RPi.GPIO as GPIO  # type: ignore

        self.GPIO = GPIO

        # Configure GPIO pins
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(STEP, GPIO.OUT)
        GPIO.setup(DIR, GPIO.OUT, initial=np.sign(self.freq))
        GPIO.setup(ENA, GPIO.OUT, initial=GPIO.HIGH)

    async def stream_data(self) -> None:
        """
        Continuously generates motor angle updates based on the configured frequency.
        Simulates the motion of the stepper motor and sends data at the appropriate interval.
        """
        try:
            # Create a PWM signal for generating motor pulses
            pulse_pin = self.GPIO.PWM(STEP, abs(self.freq * STEPS_PER_REV))

            if self.freq == 0:
                raise ValueError("freq is 0")

            delay = 1 / (STEPS_PER_REV * abs(self.freq))  # Time per step
            delta_theta = (
                np.sign(self.freq) * (np.pi * 2) / STEPS_PER_REV
            )  # Angle per step

            # Enable motor and set direction
            self.GPIO.output(ENA, self.GPIO.LOW)
            self.GPIO.output(DIR, bool(max(0, np.sign(self.freq))))
            pulse_pin.start(DUTY)

            # Simulate motor stepping and angle update
            # TODO: convert this loop into a interrupt routine on the pulse pin
            while True:
                self.theta = (self.theta + delta_theta) % (np.pi * 2)
                await self.send_data(self.theta, self.freq)
                await asyncio.sleep(delay)

        except asyncio.CancelledError:
            logger.debug("stream_data() was cancelled")
        except ValueError as e:
            logger.error(f"Value error: {e}")
        except Exception as e:
            logger.error(f"An unexpected exception was raised: {e}")
        finally:
            # Cleanup on exit or cancellation
            pulse_pin.stop()
            self.GPIO.output(ENA, self.GPIO.HIGH)
