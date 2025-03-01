from . import BaseMotorComponent
import asyncio
import numpy as np
import logging

logger = logging.getLogger(__name__)


class VirtualMotorComponent(BaseMotorComponent):
    async def stream_data(self) -> None:
        while True:
            try:
                self.angle = (self.angle + (self.speed * 0.01)) % (np.pi * 2)
                await self.send_data(self.angle, self.speed)
                await asyncio.sleep(0.01)
            except Exception:
                ...
            finally:
                ...
