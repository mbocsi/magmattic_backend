from . import BaseMotorComponent
from .motor_config import *
import logging
import asyncio
import numpy as np

logger = logging.getLogger(__name__)


class MotorComponent(BaseMotorComponent):

    def __init__(self, *args, **kargs):
        super.__init__(*args, **kargs)
        import RPi.GPIO as GPIO

        self.GPIO = GPIO

        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(PUL, GPIO.OUT)
        GPIO.setup(DIR, GPIO.OUT, initial=np.sign(self.omega))
        GPIO.setup(ENA, GPIO.OUT, initial=GPIO.HIGH)
        self.pulse_pin = GPIO.PWM(PUL, abs(self.omega * STEPS_PER_REV))

    async def stream_data(self) -> None:
        try:
            if self.omega == 0:
                raise ValueError("Omega is 0")

            delay = 1 / (STEPS_PER_REV * abs(self.omega))
            delta_theta = np.sign(self.omega) * (np.pi * 2) / STEPS_PER_REV

            self.GPIO.output(ENA, self.GPIO.LOW)
            self.GPIO.output(DIR, np.sign(self.omega))
            self.pulse_pin.start(DUTY)

            # TODO: convert this loop into a scheduled routine
            while True:
                self.theta = (self.theta + delta_theta) % (np.pi * 2)
                await self.send_data(self.theta, self.omega)
                await asyncio.sleep(delay)

        except asyncio.CancelledError:
            logger.debug("stream_data() was cancelled")
        except ValueError as e:
            logger.debug(f"Value error: {e}")
        except Exception as e:
            logger.error(f"An unexpected exception was raised: {e}")
        finally:
            self.pulse_pin.stop()
            self.GPIO.output(ENA, self.GPIO.HIGH)
