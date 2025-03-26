import asyncio
import logging
from abc import abstractmethod
from app_interface import AppComponent
from type_defs import ADCStatus

logger = logging.getLogger(__name__)


class BaseADCComponent(AppComponent):
    def __init__(
        self,
        pub_queue: asyncio.Queue,
        sub_queue: asyncio.Queue,
        addr: int = 0,
        pin: str = "D0",
        sample_rate: int = 1000,
        Nbuf: int = 32,
    ):
        """
        Initializes the ADC controller

        Args:
            pub_queue (asyncio.Queue): The asyncio queue for publishing voltage measurements.
            sub_queue (asyncio.Queue): The asyncio queue for receiving incoming messages.
            addr (int, optional): The address of the ADC device. Defaults to 0.
            pin (str, optional): The pin (channel) on the ADC to read from. Defaults to 'D0'.
            sample_rate (int, optional): The sample rate value for ADC readings. Defaults to 1000.
            Nbuf (int, optional): The number of samples per buffer for ADC streaming. Defaults to 16.
        """
        self.pub_queue = pub_queue
        self.sub_queue = sub_queue
        self.Nbuf = Nbuf
        self.sample_rate = sample_rate
        self.addr = addr
        self.pin = pin

        self.stream_task: asyncio.Task | None = None
        self.rolling_fft = True
        self.window = "rectangular"

    async def send_voltage(self, buf: list[float]) -> None:
        """
        Sends a list of voltage readings to the WebSocket server.

        Args:
            buf (list[float]): A list of voltage readings (floats) to be sent to the client.
        """

        logger.debug(f"sending voltage to queue: {buf}")

        await self.pub_queue.put({"topic": "voltage/data", "payload": buf})

    async def recv_control(self) -> None:
        while True:
            control = await self.sub_queue.get()
            if not self.stream_task:
                continue
            original_values = {}
            try:
                for var, value in control["payload"].items():
                    if hasattr(self, var):
                        original_values[var] = getattr(self, var)
                    else:
                        raise AttributeError
                    setattr(self, var, value)
                if any(
                    var in original_values.keys() for var in ["Nbuf", "sample_rate"]
                ):  # Need to restart adc stream
                    self.stream_task.cancel()
                    self.stream_task = asyncio.create_task(self.stream_adc())
                self.pub_queue.put_nowait(
                    {"topic": "adc/status", "payload": self.getStatus()}
                )
            except AttributeError:
                for var, value in original_values.items():
                    setattr(self, var, value)

    def getStatus(self) -> ADCStatus:
        return {"sample_rate": self.sample_rate, "Nbuf": self.Nbuf}

    async def run(self) -> None:
        logger.info("starting adc")
        await self.pub_queue.put({"topic": "adc/status", "payload": self.getStatus()})
        self.stream_task = asyncio.create_task(self.stream_adc())
        control_task = asyncio.create_task(self.recv_control())
        await control_task

    @abstractmethod
    async def stream_adc(self) -> None: ...
