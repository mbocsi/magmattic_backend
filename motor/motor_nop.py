from . import MotorInterface
import asyncio
import numpy as np
import logging

logger = logging.getLogger(__name__)


class MotorNop(MotorInterface):
    def __init__(self, q_data: asyncio.Queue, q_control: asyncio.Queue, init_speed=10):
        self.q_data = q_data
        self.q_control = q_control
        self.speed = init_speed
        self.angle = 0

    async def recv_control(self) -> None:
        while True:
            control = await self.q_control.get()
            logger.info(f"recv control: {control}")
            original_values = {}
            try:
                for var, value in control["value"].items():
                    if hasattr(self, var):
                        original_values[var] = getattr(self, var)
                    else:
                        raise AttributeError
                    setattr(self, var, value)
            except AttributeError:
                logger.warning(f"Unknown control attribute: {var}")
                for var, value in original_values.items():
                    setattr(self, var, value)

    async def stream_data(self) -> None:
        while True:
            try:
                self.angle = (self.angle + (self.speed * 0.01)) % (np.pi * 2)
                await self.q_data.put(
                    {"type": "motor", "val": {"speed": self.speed, "angle": self.angle}}
                )
                await asyncio.sleep(0.01)
            except Exception:
                ...
            finally:
                ...

    async def run(self) -> None:
        asyncio.gather(self.stream_data(), self.recv_control())
