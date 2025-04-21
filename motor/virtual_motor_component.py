import asyncio
import numpy as np
import logging

from . import BaseMotorComponent
from .motor_config import STEPS_PER_REV

logger = logging.getLogger(__name__)


class VirtualMotorComponent(BaseMotorComponent):
    async def stream_data(self) -> None:
        """
        Simulates motor rotation and emits synthetic angle/frequency data over time.
        Uses the configured frequency to determine angular speed and delay.
        """
        logger.debug("stream_data() was started")
        try:
            if self.freq == 0:
                raise ValueError("freq is 0")

            delay = 1 / (STEPS_PER_REV * abs(self.freq))  # Time between virtual steps
            delta_theta = (
                np.sign(self.freq) * (np.pi * 2) / STEPS_PER_REV
            )  # Angle per step

            # Simulate stepper motor rotation
            # TODO: Convert this into a scheduled routine
            while True:
                self.theta = (self.theta + delta_theta) % (np.pi * 2)
                await self.send_data(self.theta, self.freq)
                await asyncio.sleep(delay)  # Wait until next step

        except asyncio.CancelledError:
            logger.debug("stream_data() was cancelled")
        except ValueError as e:
            logger.debug(f"Value error: {e}")
        except Exception as e:
            logger.error(f"An unexpected exception was raised: {e}")
