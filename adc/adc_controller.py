from . import ADCInterface
import asyncio
import json
import time
import numpy as np
from collections import deque
import logging

logger = logging.getLogger(__name__ + ".ADCController")


class ADCController(ADCInterface):
    def __init__(
        self,
        q_data: asyncio.Queue,
        addr: int = 0,
        pin: str = "D0",
        sample_rate: int = 13,
        N: int = 32,
        M: int = 1000,
    ):
        """
        Initializes the ADC controller

        Args:
            q_data (asyncio.Queue): The asyncio queue to store the collected ADC data.
            addr (int, optional): The address of the ADC device. Defaults to 0.
            pin (str, optional): The pin (channel) on the ADC to read from. Defaults to 'D0'.
            sample_rate (int, optional): The sample rate value for ADC readings (Pi-Plate specific). Defaults to 13.
            N (int, optional): The number of samples per buffer for ADC streaming. Defaults to 32.
            M (int, optional): The number of samples needed in the data buffer for calcuating FFT. Defaults to 1000.
        """

        import adc.adc_async as ADC

        self.ADC = ADC

        self.q_data = q_data

        self.addr = addr
        self.pin = pin
        self.sample_rate = sample_rate
        self.N = N
        self.M = M

        adc_id = self.ADC.getID(self.addr)
        if not adc_id:
            raise Exception(f"Failed to connect to ADC at addr={self.addr}")
        logger.info(f"connected ADC-> id={adc_id}")

    async def send_voltage(self, buf: list[float]) -> None:
        """
        Sends a list of voltage readings to the WebSocket server.

        Args:
            buf (list[float]): A list of voltage readings (floats) to be sent to the client.
        """

        logger.debug(f"sending voltage to queue: {buf}")
        # for val in buf:
        await self.q_data.put(json.dumps({"type": "voltage", "val": buf}))

    async def send_fft(self, data: list[float], T: float) -> None:
        """
        Sends the FFT (Fast Fourier Transform) results to the WebSocket server.

        Args:
            data (list[float]): The input data (e.g., time-domain signal) to perform the FFT on.
            T (float): The sampling period (inverse of the sample rate) to be used in the FFT calculation.
        """

        logger.debug(f"sending fft to queue: {data} {T}")
        Ntot = len(data)

        FFT = np.abs(np.fft.fft(data)) / Ntot
        V1 = FFT[0 : int(Ntot / 2 + 1)]
        V1[1:-2] = 2 * V1[1:-2]

        freq = 1 / T * np.linspace(0, int(Ntot / 2 + 1), int(Ntot / 2 + 1))

        await self.q_data.put(
            json.dumps({"type": "fft", "val": [[f, v] for f, v in zip(freq, V1)]})
        )

    async def run(self) -> None:
        """
        Runs the ADC sampling process
        """

        logger.info("running adc controller")
        self.ADC.setMODE(self.addr, "ADV")
        self.ADC.configINPUT(self.addr, self.pin, self.sample_rate, True)
        self.ADC.startSTREAM(self.addr, self.N)
        data: deque[float] = deque([], maxlen=self.M)
        try:
            while True:
                buffer = await self.ADC.getStreamSync(self.addr)
                logger.debug(f"ADC buffer readings: {buffer}")
                await self.send_voltage(buffer)
                data.extend(buffer)

                if len(data) >= self.M:
                    T = 1
                    await self.send_fft(list(data), T)
                await asyncio.sleep(0)  # Might not be necessary
        except Exception:
            self.ADC.stopSTREAM(self.addr)
