import asyncio
import logging
import numpy as np
from abc import abstractmethod
from app_interface import AppComponent
from .windows import windows

logger = logging.getLogger(__name__)


class BaseADCComponent(AppComponent):
    def __init__(
        self,
        pub_queue: asyncio.Queue,
        sub_queue: asyncio.Queue,
        addr: int = 0,
        pin: str = "D0",
        sample_rate: int = 13,
        Nbuf: int = 16,
        Nsig: int = 1024,
        Ntot: int = 1024,
    ):
        """
        Initializes the ADC controller

        Args:
            q_data (asyncio.Queue): The asyncio queue to store the collected ADC data.
            q_control (asyncio.Queue): The asyncio queue to store the control signals.
            addr (int, optional): The address of the ADC device. Defaults to 0.
            pin (str, optional): The pin (channel) on the ADC to read from. Defaults to 'D0'.
            sample_rate (int, optional): The sample rate value for ADC readings (Pi-Plate specific). Defaults to 13.
            N (int, optional): The number of samples per buffer for ADC streaming. Defaults to 16.
            M (int, optional): The number of samples needed in the data buffer for calcuating FFT. Defaults to 1024.
        """
        self.pub_queue = pub_queue
        self.sub_queue = sub_queue
        self.Nbuf = Nbuf
        self.Nsig = Nsig
        self.sample_rate = sample_rate
        self.addr = addr
        self.pin = pin

        self.stream_task: asyncio.Task | None = None
        self.rolling_fft = True
        self.window = "rectangular"
        self.Ntot = Ntot  # Signal size + zero padding

    async def send_voltage(self, buf: list[float]) -> None:
        """
        Sends a list of voltage readings to the WebSocket server.

        Args:
            buf (list[float]): A list of voltage readings (floats) to be sent to the client.
        """

        logger.debug(f"sending voltage to queue: {buf}")
        # for val in buf:
        await self.pub_queue.put({"topic": "voltage/data", "payload": buf})

    async def send_fft(self, data: list[float], T: float) -> None:
        """
        Sends the FFT (Fast Fourier Transform) results to the WebSocket server.

        Args:
            data (list[float]): The input data (e.g., time-domain signal) to perform the FFT on.
            T (float): The sampling period (inverse of the sample rate) to be used in the FFT calculation.
        """

        logger.debug(f"sending fft to queue: {data} {T}")

        # Window data
        window = windows[self.window]
        windowed_data = np.array(data) * window.func(self.Nsig) / window.coherent_gain

        # Perform fft
        FFT = np.abs(np.fft.rfft(windowed_data, n=self.Ntot)) / self.Nsig
        V1 = FFT
        V1[1:-1] = 2 * V1[1:-1]

        freq = np.fft.rfftfreq(self.Ntot, d=T / self.Nsig)

        await self.pub_queue.put(
            {
                "topic": "fft/data",
                "payload": [[f, v] for f, v in zip(freq, V1)],
                "metadata": {"window": self.window},
            }
        )

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
                    var in original_values.keys() for var in ["Nbuf", "Nsig"]
                ):  # Need to restart adc stream
                    self.stream_task.cancel()
                    self.stream_task = asyncio.create_task(self.stream_adc())
            except AttributeError:
                for var, value in original_values.items():
                    setattr(self, var, value)

    async def run(self) -> None:
        logger.info("starting adc")
        self.stream_task = asyncio.create_task(self.stream_adc())
        control_task = asyncio.create_task(self.recv_control())
        await control_task

    @abstractmethod
    async def stream_adc(self) -> None: ...
