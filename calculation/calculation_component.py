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
        self,
        fft: np.ndarray,
        freq: float,
        freq_calc_range: float = 3,
    ) -> float:
        # Determine frequency resolution
        freq_res = ((fft[[-1], [0]] - fft[[0], [0]]) / fft.shape[0])[0]

        # Convert frequency range to index range
        idx_range = freq_calc_range // freq_res

        # Find magnitudes and power within range
        idx = np.where(fft[:, 0] == freq)[0]
        lower_idx, upper_idx = int(idx - idx_range), int(idx + idx_range)
        magnitudes = fft[lower_idx : upper_idx + 1, 1]
        raw_power = (freq_res * magnitudes**2).sum()

        # Convert power into amplitude
        estimated_power = raw_power / windows[self.window].enbw
        estimated_amplitude = math.sqrt(estimated_power)

        return estimated_amplitude

    def peaks(self, magnitude: np.ndarray, phase: np.ndarray, min_snr=5) -> np.ndarray:
        noise_floor = self.noise_floor(magnitude[:, 1])
        indices = find_peaks(magnitude[:, 1], prominence=noise_floor * min_snr)[0]
        peak_mags = magnitude[indices, :]
        peak_phases = phase[indices, :]
        return np.hstack((peak_mags, peak_phases[:, [1]]))

    def noise_floor(self, magnitude: np.ndarray, noise_perc=0.9) -> float:
        values = int(magnitude.shape[0] * noise_perc)
        lowest_values = np.sort(magnitude)[:values]
        return np.sqrt(np.sum(lowest_values**2) / lowest_values.shape[0])

    def calc_bfield(self, volts: float, omega: float, theta: float) -> np.ndarray:
        vector = np.array([-np.cos(theta), np.sin(theta)])
        mag = volts / (self.coil_props["windings"] * self.coil_props["area"] * omega)
        return vector * mag

    def process_voltage_data(self, data, loop):
        self.voltage_data.extend(data["payload"])
        if len(self.voltage_data) < self.Nsig:
            return

        T = self.Nsig / self.sample_rate

        # Calculate FFT
        magnitude, phase = self.calc_fft(self.voltage_data, T)

        # Find signals
        peaks = self.peaks(magnitude, phase, min_snr=self.min_snr)

        # Find amplitudes of signals
        voltage_amplitudes = np.zeros((peaks.shape[0], 1))
        voltage_amplitudes[:, 0] = np.array(
            [self.calc_vampl(magnitude, freq) for freq in peaks[:, 0].tolist()]
        )
        peaks = np.hstack((peaks, voltage_amplitudes))

        # Find bfield of signals
        bfields = np.zeros((peaks.shape[0], 2))
        bfields[:, 0:2] = [
            self.calc_bfield(
                volts=volt_ampl[2], omega=volt_ampl[0] * 2 * np.pi, theta=volt_ampl[1]
            )
            for volt_ampl in peaks[:, [0, 2, 3]].tolist()
        ]
        peaks = np.hstack((peaks, bfields))

        # Filter phase by detected signals
        phase[:, 1] = np.where(
            np.isin(phase[:, 0], peaks[:, 0]), phase[:, 1], np.zeros_like(phase[:, 1])
        )

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
                "topic": "signals/data",
                "payload": [
                    {
                        "freq": peak[0],
                        "mag": peak[1],
                        "phase": peak[2],
                        "ampl": peak[3],
                        "bfield": peak[4:],
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
                if var == "acquisition_time":
                    self.Nsig = int(self.sample_rate * value)
                    self.Ntot = int(self.sample_rate * value)
                    self.voltage_data = deque(maxlen=self.Ntot)
                    continue
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
