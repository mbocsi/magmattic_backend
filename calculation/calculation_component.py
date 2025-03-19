from app_interface import AppComponent
from collections import deque
import asyncio
import logging
import numpy as np
import math
from .windows import windows

logger = logging.getLogger(__name__)


class CalculationComponent(AppComponent):
    def __init__(
        self,
        pub_queue: asyncio.Queue,
        sub_queue: asyncio.Queue,
        Nsig: int = 1024,
        Ntot: int = 1024,
    ):
        self.pub_queue = pub_queue
        self.sub_queue = sub_queue
        self.Nsig = Nsig
        self.Ntot = Ntot
        self.rolling_fft = True
        self.window = "rectangular"
        self.sample_rate = 1200
        self.voltage_data: deque[float] = deque(maxlen=Nsig)
        self.rolling_fft = False

        self.coil_resistance = 90  # ohms
        self.coil_turns = 1000
        self.coil_area = 0.1 * 0.1  # m^2

    async def calc_fft(self, data, T) -> np.ndarray:
        logger.debug(f"sending fft to queue: {data} {T}")

        # Window data
        window = windows[self.window]
        windowed_data = np.array(data) * window.func(self.Nsig) / window.coherent_gain

        # Perform fft
        FFT = np.abs(np.fft.rfft(windowed_data, n=self.Ntot)) / self.Nsig
        V1 = FFT
        V1[1:-1] = 2 * V1[1:-1]

        freq = np.fft.rfftfreq(self.Ntot, d=T / self.Nsig)

        payload = np.hstack((freq, V1))
        # payload = [[f, v] for f, v in zip(freq, V1)]

        return payload

    async def calc_vampl(self, fft: np.ndarray, freq_calc_range: float = 3) -> float:
        freq_res = (fft[0, 0] - fft[-1, 0]) / fft.shape[0]
        idx_range = freq_calc_range // freq_res
        filtered_fft = fft[fft[:, 0] >= 5 and fft[:, 0] <= 30]
        max_idx = np.argmax(filtered_fft, axis=0)
        raw_power = (
            freq_res
            * filtered_fft[(max_idx - idx_range) : (max_idx + idx_range), 1] ** 2
        ).sum()
        estimated_power = raw_power / windows[self.window].enbw
        estimated_amplitude = math.sqrt(estimated_power)
        return estimated_amplitude

    async def calc_moment(self, volts: float) -> float:
        i_amps = volts / self.coil_resistance  # ohms
        return self.coil_turns * self.coil_area * i_amps

    async def recv_control(self) -> None:
        while True:
            data = await self.sub_queue.get()
            match data["topic"]:
                case "voltage/data":
                    self.voltage_data.extend(data["payload"])
                    if len(self.voltage_data) < self.Nsig:
                        continue
                    T = self.Nsig / self.sample_rate
                    fft = await self.calc_fft(self.voltage_data, T)
                    self.pub_queue.put_nowait(
                        {
                            "topic": "fft/data",
                            "payload": fft.tolist(),
                            "metadata": {"window": self.window},
                        }
                    )
                    voltage_amplitude = await self.calc_vampl(fft)
                    moment = await self.calc_moment(voltage_amplitude)
                    self.pub_queue.put_nowait(
                        {
                            "topic": "moment/data",
                            "payload": moment,
                        }
                    )
                    if not self.rolling_fft:
                        self.voltage_data.clear()
                case _:
                    logger.warning(f"unknown topic received: {data["topic"]}")

    async def run(self):
        logger.info("starting calculation")
        await self.recv_control()
