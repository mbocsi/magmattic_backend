from app_interface import AppComponent
from collections import deque
import asyncio
import logging
import numpy as np
import math
from scipy.signal import find_peaks
from .windows import windows
from type_defs import Window, CalculationStatus

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
        window: Window = "rectangular",
        coil_props: dict[str, float] | None = None,
    ):
        self.pub_queue = pub_queue
        self.sub_queue = sub_queue
        self.Nsig = Nsig
        self.Ntot = Ntot
        self.rolling_fft = rolling_fft
        self.window: Window = window
        self.sample_rate = 1200
        self.voltage_data: deque[float] = deque(maxlen=Nsig)

        self.coil_props = parse_coil_props(coil_props)
        self.motor_theta = 0
        self.theta_init = 0
        self.min_snr = 5

    def calc_fft(self, data, T) -> tuple[np.ndarray, np.ndarray]:
        logger.debug(f"sending fft to queue: {data} {T}")

        # Window data
        window = windows[self.window]
        windowed_data = np.array(data) * window.func(self.Nsig) / window.coherent_gain

        # Perform fft
        fft = np.fft.rfft(windowed_data, n=self.Ntot) / self.Nsig

        # Obtain magnitude and phase
        magnitude = np.abs(fft)
        phase = np.angle(fft)

        magnitude[1:-1] = 2 * magnitude[1:-1]

        freq = np.fft.rfftfreq(self.Ntot, d=T / self.Nsig)

        freq = freq.reshape((len(freq), 1))
        magnitude = magnitude.reshape((len(magnitude), 1))
        phase = phase.reshape((len(phase), 1))

        magnitude_data = np.hstack((freq, magnitude))
        phase_data = np.hstack((freq, phase))

        return magnitude_data, phase_data

    def calc_vampl(
        self, fft: np.ndarray, phase: np.ndarray, freq_calc_range: float = 3
    ) -> tuple[float, float, float]:
        freq_res = ((fft[[-1], [0]] - fft[[0], [0]]) / fft.shape[0])[0]

        idx_range = freq_calc_range // freq_res
        filtered_fft = fft[(fft[:, 0] >= 1)]
        filtered_phase = phase[(phase[:, 0] >= 1)]
        filtered_fft = filtered_fft[filtered_fft[:, 0] <= 30]
        filtered_phase = filtered_phase[filtered_phase[:, 0] <= 30]

        max_idx = np.argmax(filtered_fft, axis=0)[1]

        lower_idx, upper_idx = int(max_idx - idx_range), int(max_idx + idx_range)

        magnitudes = filtered_fft[lower_idx : upper_idx + 1, 1]
        raw_power = (freq_res * magnitudes**2).sum()

        estimated_power = raw_power / windows[self.window].enbw
        estimated_amplitude = math.sqrt(estimated_power)

        estimated_phase = filtered_phase[max_idx, 1]

        return (
            estimated_amplitude,
            estimated_phase,
            filtered_fft[max_idx, 0] * 2 * math.pi,
        )

    def peaks(self, magnitude: np.ndarray, phase: np.ndarray, min_snr=5) -> np.ndarray:
        # logger.info(magnitude[:, 1])
        # widths = np.arange(1, max_width + 1)
        noise_floor = self.noise_floor(magnitude[:, 1])
        indices = find_peaks(magnitude[:, 1], prominence=noise_floor * min_snr)[0]
        peak_mags = magnitude[indices, :]
        peak_phases = phase[indices, :]
        return np.hstack((peak_mags, peak_phases[:, [1]]))

    def noise_floor(self, magnitude: np.ndarray, noise_perc=0.9) -> float:
        values = int(magnitude.shape[0] * 0.9)
        lowest_values = np.sort(magnitude)[:values]
        return np.sqrt(np.sum(lowest_values**2) / lowest_values.shape[0])

    def calc_bfield(self, volts: float, omega: float, theta: float) -> np.ndarray:
        vector = np.array([-np.cos(theta), np.sin(theta)])
        mag = volts / (self.coil_props["windings"] * self.coil_props["area"] * omega)
        return vector * mag

    def process_voltage_data(self, data, loop):
        # starTime = time.perf_counter()
        self.voltage_data.extend(data["payload"])
        if len(self.voltage_data) < self.Nsig:
            return

        T = self.Nsig / self.sample_rate

        magnitude, phase = self.calc_fft(self.voltage_data, T)
        voltage_amplitude, theta, omega = self.calc_vampl(magnitude, phase)
        peaks = self.peaks(magnitude, phase, min_snr=self.min_snr)
        bfield = self.calc_bfield(voltage_amplitude, omega, theta)

        # Use run_coroutine_threadsafe() to ensure safe queue insertion
        loop.call_soon_threadsafe(
            self.pub_queue.put_nowait,
            {"topic": "fft_mags/data", "payload": magnitude.tolist()},
        )
        loop.call_soon_threadsafe(
            self.pub_queue.put_nowait,
            {
                "topic": "fft_phases/data",
                "payload": np.column_stack(
                    (phase[:, 0], phase[:, 1] * 180 / np.pi)
                ).tolist(),
            },
        )
        loop.call_soon_threadsafe(
            self.pub_queue.put_nowait,
            {
                "topic": "signal/data",
                "payload": {
                    "amplitude": voltage_amplitude,
                    "theta": theta,
                    "omega": omega,
                },
            },
        )
        loop.call_soon_threadsafe(
            self.pub_queue.put_nowait,
            {"topic": "bfield/data", "payload": bfield.tolist()},
        )
        loop.call_soon_threadsafe(
            self.pub_queue.put_nowait,
            {
                "topic": "signals/data",
                "payload": [
                    {
                        "freq": peak[0],
                        "mag": peak[1],
                        "phase": peak[2],
                    }
                    for peak in peaks.tolist()
                ],
            },
        )

        if not self.rolling_fft:
            self.voltage_data.clear()
        self.theta_init = self.motor_theta

    async def recv_control(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            try:
                data = await self.sub_queue.get()
                # startTime = time.perf_counter()
                match data["topic"]:
                    case "voltage/data":
                        asyncio.create_task(
                            asyncio.to_thread(self.process_voltage_data, data, loop)
                        )
                    case "calculation/command":
                        asyncio.create_task(asyncio.to_thread(self.control, data, loop))
                    case "adc/status":
                        self.sample_rate = data["payload"]["sample_rate"]
                    case "motor/data":
                        self.motor_theta = data["payload"]["theta"]
                    case _:
                        logger.warning(f"unknown topic received: {data['topic']}")
                # endTime = time.perf_counter()
                # logger.info(endTime - startTime)
            except Exception as e:
                logger.error(f"An unexpected exception occured in recv_control: {e}")

    def control(self, control, loop):
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

                loop.call_soon_threadsafe(
                    self.pub_queue.put_nowait,
                    {"topic": "calculation/status", "payload": self.getStatus()},
                )
        except AttributeError:
            for var, value in original_values.items():
                setattr(self, var, value)

    def getStatus(self) -> CalculationStatus:
        return {
            "Nsig": self.Nsig,
            "Ntot": self.Ntot,
            "rolling_fft": self.rolling_fft,
            "window": self.window,
            "min_snr": self.min_snr,
        }

    async def run(self):
        await self.pub_queue.put(
            {"topic": "calculation/status", "payload": self.getStatus()}
        )
        logger.info("starting calculation")
        await self.recv_control()
