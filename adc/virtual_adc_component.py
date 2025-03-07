from . import BaseADCComponent
import asyncio
from collections import deque
import numpy as np
import math
import logging

logger = logging.getLogger(__name__)

frequencies = np.array([[5, 1], [10, 3], [20, 5]])


class VirtualADCComponent(BaseADCComponent):
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
    async def sin_stream(cls, angles, n):
        data = []
        for _ in range(n):
            angles = (angles + (2 * np.pi * frequencies[:, [0]].T * 0.001)) % (
                2 * np.pi
            )

            signal = np.sum(frequencies[:, [1]].T * np.sin(angles)) + 0.5
            data.append(signal)
            await asyncio.sleep(0.001)
        return angles, VirtualADCComponent.add_noise(data, noise_level=0.2)

    async def stream_adc(self) -> None:
        data: deque[float] = deque(maxlen=self.Nsig)
        angles = np.zeros((1, frequencies.shape[0]))
        try:
            while True:
                angles, values = await VirtualADCComponent.sin_stream(angles, self.Nbuf)
                await self.send_voltage(values)
                data.extend(values)
                if len(data) >= self.Nsig:
                    T = self.Nsig / 1007  # Sample rate is 1007
                    await self.send_fft(list(data), T)
                    if not self.rolling_fft:
                        data.clear()
        except asyncio.CancelledError:
            logger.debug("stream_adc() cancelled")
        except Exception as e:
            logger.warning("stream_adc() raised an exception:", e)
        finally:
            ...  # Do some clean up
