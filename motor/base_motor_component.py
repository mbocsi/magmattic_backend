import asyncio
import logging

from app_interface import AppComponent
from abc import abstractmethod
from type_defs import MotorStatus

logger = logging.getLogger(__name__)


class BaseMotorComponent(AppComponent):
    def __init__(
        self, pub_queue: asyncio.Queue, sub_queue: asyncio.Queue, init_speed=0
    ):
        self.pub_queue = pub_queue
        self.sub_queue = sub_queue
        self.freq = init_speed
        self.theta = 0
        self.stream_task: asyncio.Task | None = None

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
                if not self.stream_task:
                    self.stream_task = asyncio.create_task(
                        self.stream_data()
                    )  # Attempt restart streaming task
                    continue
                if any(
                    var in original_values.keys() for var in ["freq"]
                ):  # Need to restart adc stream
                    self.stream_task.cancel()
                    self.stream_task = asyncio.create_task(self.stream_data())
                self.pub_queue.put_nowait(
                    {"topic": "motor/status", "payload": self.getStatus()}
                )
            except AttributeError:
                logger.warning(f"Unknown control attribute: {var}")
                for var, value in original_values.items():
                    setattr(self, var, value)

    async def send_data(self, theta: float, freq: float) -> None:
        await self.pub_queue.put(
            {"topic": "motor/data", "payload": {"freq": freq, "theta": theta}}
        )

    def getStatus(self) -> MotorStatus:
        return {"freq": self.freq}

    async def run(self) -> None:
        logger.info("starting motor")
        await self.pub_queue.put({"topic": "motor/status", "payload": self.getStatus()})
        self.stream_task = asyncio.create_task(self.stream_data())
        control_task = asyncio.create_task(self.recv_control())
        await control_task

    @abstractmethod
    async def stream_data(self) -> None: ...
