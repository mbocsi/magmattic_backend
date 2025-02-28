from . import ADCInterface
import asyncio
from collections import deque
import numpy as np
import math
import logging

logger = logging.getLogger(__name__ + ".NopADC")


class NopADC(ADCInterface):
    def __init__(
        self,
        q_data: asyncio.Queue,
        q_control: asyncio.Queue,
        N: int = 16,
        M: int = 1000,
    ):
        self.q_data = q_data
        self.q_control = q_control
        self.N = N
        self.M = M
        self.stream_task: asyncio.Task | None = None
        self.rolling_fft = True

    async def send_voltage(self, buffer: list[float]) -> None:
        await self.q_data.put({"type": "voltage", "val": buffer})

    async def send_fft(self, data, T) -> None:
        Ntot = len(data)
        FFT = np.abs(np.fft.fft(data)) / Ntot
        V1 = FFT[0 : int(Ntot / 2 + 1)]
        V1[1:-2] = 2 * V1[1:-2]
        freq = 1 / T * np.linspace(0, int(Ntot / 2 + 1), int(Ntot / 2 + 1))

        await self.q_data.put(
            {"type": "fft", "val": [[f, v] for f, v in zip(freq, V1)]}
        )

    @classmethod
    def add_noise(cls, signal, noise_type="gaussian", noise_level=0.1):
        """Adds noise to a signal.

        Args:
            signal []: The input signal.
            noise_type (str, optional): The type of noise to add.
                Options are 'gaussian', 'uniform', and 'salt_pepper'.
                Defaults to 'gaussian'.
            noise_level (float, optional): The noise level,
                expressed as a fraction of the signal's standard deviation.
                Defaults to 0.1.

        Returns:
            np.ndarray: The noisy signal.
        """
        signal = np.array(signal)
        signal_std = np.std(signal)

        if noise_type == "gaussian":
            noise = np.random.normal(0, noise_level * signal_std, len(signal))
        elif noise_type == "uniform":
            noise = np.random.uniform(
                -noise_level * signal_std, noise_level * signal_std, len(signal)
            )
        elif noise_type == "salt_pepper":
            num_noise_points = int(noise_level * len(signal))
            indices = np.random.choice(len(signal), num_noise_points, replace=False)
            noise = np.zeros(len(signal))
            for i in indices:
                noise[i] = np.random.choice([-1, 1]) * signal_std
        else:
            raise ValueError(
                "Invalid noise type. Choose 'gaussian', 'uniform', or 'salt_pepper'."
            )

        noisy_signal = signal + noise
        return noisy_signal.tolist()

    @classmethod
    async def sin_stream(cls, angle, n):
        data = []
        for _ in range(n):
            angle = (angle + (0.003 * 2 * math.pi)) % (2 * math.pi)
            signal = math.sin(angle) + math.sin((angle * 5)) + 0.5
            data.append(signal)
            await asyncio.sleep(0.001)
        return angle, NopADC.add_noise(data, noise_level=0.5)

    async def recv_control(self) -> None:
        while True:
            control = await self.q_control.get()
            if not self.stream_task:
                continue
            original_values = {}
            try:
                for var, value in control["value"].items():
                    if hasattr(self, var):
                        original_values[var] = getattr(self, var)
                    else:
                        raise AttributeError
                    setattr(self, var, value)
                if any(
                    var in original_values.keys() for var in ["N", "M"]
                ):  # Need to restart adc stream
                    self.stream_task.cancel()
                    self.stream_task = asyncio.create_task(self.stream_adc())
            except AttributeError:
                for var, value in original_values.items():
                    setattr(self, var, value)

    async def stream_adc(self) -> None:
        data = deque(maxlen=self.M)
        angle = 0
        try:
            while True:
                angle, values = await NopADC.sin_stream(angle, self.N)
                await self.send_voltage(values)
                data.extend(values)
                if len(data) >= self.M:
                    T = self.M / 1000
                    await self.send_fft(data, T)
                    if not self.rolling_fft:
                        data.clear()
        except asyncio.CancelledError:
            logger.debug("stream_adc() cancelled")
        except Exception as e:
            logger.warning("stream_adc() raised an exception:", e)
        finally:
            ...  # Do some clean up

    async def run(self) -> None:
        logger.info("starting nopadc")
        self.stream_task = asyncio.create_task(self.stream_adc())
        control_task = asyncio.create_task(self.recv_control())
        await control_task
