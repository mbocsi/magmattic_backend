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
        """
        Base class for a motor component that supports control message handling and status publishing.

        Args:
            pub_queue (asyncio.Queue): Queue to publish motor data and status updates.
            sub_queue (asyncio.Queue): Queue to receive control messages.
            init_speed (float, optional): Initial frequency of the motor. Defaults to 0.
        """
        self.pub_queue = pub_queue
        self.sub_queue = sub_queue
        self.freq = init_speed  # Rotational frequency in Hz
        self.theta = 0  # Angular position in radians
        self.stream_task: asyncio.Task | None = (
            None  # Async task for streaming motor data
        )

    async def recv_control(self) -> None:
        """
        Listens for and processes control messages to update motor parameters.
        If key parameters change (like freq), restarts the stream task.
        """
        while True:
            control = await self.sub_queue.get()
            logger.info(f"recv control: {control}")
            original_values = {}  # maintain original for rollback
            try:
                for var, value in control["payload"].items():
                    if hasattr(self, var):
                        original_values[var] = getattr(self, var)
                    else:
                        raise AttributeError
                    setattr(self, var, value)

                # Start or restart stream task if frequency is modified
                if not self.stream_task:
                    self.stream_task = asyncio.create_task(self.stream_data())
                elif any(var in original_values.keys() for var in ["freq"]):
                    self.stream_task.cancel()
                    self.stream_task = asyncio.create_task(self.stream_data())

                # Publish updated motor status
                self.pub_queue.put_nowait(
                    {"topic": "motor/status", "payload": self.getStatus()}
                )
            except AttributeError:
                # Rollback values on error
                logger.warning(f"Unknown control attribute: {var}")
                for var, value in original_values.items():
                    setattr(self, var, value)

    async def send_data(self, theta: float, freq: float) -> None:
        """
        Publishes motor data to the WebSocket server.

        Args:
            theta (float): Current angular position in radians.
            freq (float): Current frequency in Hz.
        """
        await self.pub_queue.put(
            {"topic": "motor/data", "payload": {"freq": freq, "theta": theta}}
        )

    def getStatus(self) -> MotorStatus:
        """
        Returns a dictionary with the current motor configuration.

        Returns:
            MotorStatus: Dictionary containing current frequency.
        """
        return {"freq": self.freq}

    async def run(self) -> None:
        """
        Starts the motor component, launches streaming and control coroutines.
        """
        logger.info(f"starting motor: {type(self).__name__}")
        await self.pub_queue.put({"topic": "motor/status", "payload": self.getStatus()})
        self.stream_task = asyncio.create_task(self.stream_data())
        control_task = asyncio.create_task(self.recv_control())
        await control_task

    @abstractmethod
    async def stream_data(self) -> None:
        """
        Abstract method to be implemented by subclasses.
        Should continuously emit motor angle and frequency.
        """
        ...
