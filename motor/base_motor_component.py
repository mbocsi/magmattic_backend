from app_interface import AppComponent
import asyncio
import logging
from abc import abstractmethod

logger = logging.getLogger(__name__)


class BaseMotorComponent(AppComponent):
    def __init__(
        self, pub_queue: asyncio.Queue, sub_queue: asyncio.Queue, init_speed=10
    ):
        self.pub_queue = pub_queue
        self.sub_queue = sub_queue
        self.speed = init_speed
        self.angle = 0

    async def recv_control(self) -> None:
        while True:
            control = await self.sub_queue.get()
            logger.info(f"recv control: {control}")
            original_values = {}
            try:
                for var, value in control["payload"].items():
                    if hasattr(self, var):
                        original_values[var] = getattr(self, var)
                    else:
                        raise AttributeError
                    setattr(self, var, value)
            except AttributeError:
                logger.warning(f"Unknown control attribute: {var}")
                for var, value in original_values.items():
                    setattr(self, var, value)

    async def send_data(self, angle: float, speed: float) -> None:
        await self.pub_queue.put(
            {"topic": "motor/data", "payload": {"speed": speed, "angle": angle}}
        )

    async def run(self) -> None:
        logger.info("starting motor")
        asyncio.gather(self.stream_data(), self.recv_control())

    @abstractmethod
    async def stream_data(self) -> None: ...
