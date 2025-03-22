from app_interface import AppComponent
from collections import deque
import asyncio
import logging
import numpy as np
import math
from .windows import windows

logger = logging.getLogger(__name__)


def parse_coil_props(props: dict[str, float] | None) -> dict[str, float]:
    if props is None:
        return {"impedence": 90, "windings": 1000, "area": 0.01}
    attrs = ["impedence", "windings", "area"]
    missing_attrs = []
    for attr in attrs:
        if attr not in props.keys():
            missing_attrs.append(attr)
    if missing_attrs:
        raise ValueError(f"Missing attributes in coil_props: {missing_attrs}")
    return props


class CalculationComponent(AppComponent):
    def __init__(
        self,
        pub_queue: asyncio.Queue,
        sub_queue: asyncio.Queue,
        Nsig: int = 1024,
        Ntot: int = 1024,
        rolling_fft: bool = False,
        window: str = "rectangular",
        coil_props: dict[str, float] | None = None,
    ):
        self.pub_queue = pub_queue
        self.sub_queue = sub_queue
        self.Nsig = Nsig
        self.Ntot = Ntot
        self.rolling_fft = rolling_fft
        self.window = window
        self.sample_rate = 1200
        self.voltage_data: deque[float] = deque(maxlen=Nsig)

        self.coil_props = parse_coil_props(coil_props)

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

        freq = freq.reshape((len(freq), 1))
        V1 = V1.reshape((len(V1), 1))

        payload = np.hstack((freq, V1))

        return payload

    async def calc_vampl(
        self, fft: np.ndarray, freq_calc_range: float = 3
    ) -> tuple[float, float]:
        freq_res = ((fft[[-1], [0]] - fft[[0], [0]]) / fft.shape[0])[0]

        idx_range = freq_calc_range // freq_res
        filtered_fft = fft[(fft[:, 0] >= 5)]
        filtered_fft = filtered_fft[filtered_fft[:, 0] <= 30]

        max_idx = np.argmax(filtered_fft, axis=0)[1]

        lower_idx, upper_idx = int(max_idx - idx_range), int(max_idx + idx_range)

        magnitudes = filtered_fft[lower_idx : upper_idx + 1, 1]
        raw_power = (freq_res * magnitudes**2).sum()

        estimated_power = raw_power / windows[self.window].enbw
        estimated_amplitude = math.sqrt(estimated_power)
        return estimated_amplitude, filtered_fft[max_idx, 0] * 2 * math.pi

    async def calc_bfield(self, volts: float, omega: float) -> float:
        return volts / (self.coil_props["windings"] * self.coil_props["area"] * omega)

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
                    voltage_amplitude, omega = await self.calc_vampl(fft)
                    # logger.info(f"{voltage_amplitude=}")
                    # logger.info(f"{omega=}")
                    bfield = await self.calc_bfield(voltage_amplitude, omega)
                    # logger.info(f"{bfield=}")
                    self.pub_queue.put_nowait(
                        {
                            "topic": "bfield/data",
                            "payload": bfield,
                        }
                    )
                    if not self.rolling_fft:
                        self.voltage_data.clear()
                case "calculation/command":
                    await self.control(data)
                case _:
                    logger.warning(f"unknown topic received: {data['topic']}")

    async def control(self, control):
        original_values = {}
        try:
            for var, value in control["payload"].items():
                if hasattr(self, var):
                    original_values[var] = getattr(self, var)
                else:
                    raise AttributeError
                setattr(self, var, value)
                if var == "Nsig":
                    self.voltage_data = deque(maxlen=value)
        except AttributeError:
            for var, value in original_values.items():
                setattr(self, var, value)

    async def run(self):
        logger.info("starting calculation")
        await self.recv_control()
