from . import BaseADCComponent
import asyncio
import numpy as np
import logging
import time
from motor import BaseMotorComponent

logger = logging.getLogger(__name__)

frequencies = np.array([[0, 0.1], [1, 1], [4, 0.05], [12, 0.1]])


class VirtualADCComponent(BaseADCComponent):
    def __init__(
        self,
        pub_queue: asyncio.Queue,
        sub_queue: asyncio.Queue,
        motor_component: BaseMotorComponent,
        addr: int = 0,
        pin: str = "D0",
        sample_rate: int = 1200,
        Nbuf: int = 32,
    ):
        super().__init__(pub_queue, sub_queue, addr, pin, sample_rate, Nbuf)
        self.motor_component = motor_component

    @classmethod
    def add_noise(cls, signal, noise_type="gaussian", noise_level=0.1) -> list[float]:
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
    def sin_at_angle(cls, theta, frequencies):
        """
        Calculate voltage at given angle `theta` based on multiple sine sources.
        `theta` is a scalar (motor angle in radians).
        `frequencies`: shape (num_components, 2), with [ [freq1, amp1], [freq2, amp2], ... ]
        """
        phase = (
            2 * np.pi * frequencies[:, 0] * theta / (2 * np.pi)
        )  # or just `frequencies[:, 0] * theta`
        signal = np.sum(frequencies[:, 1] * np.sin(phase))
        return signal

    async def stream_adc(self) -> None:
        try:
            while True:
                voltages = []
                for _ in range(self.Nbuf):
                    theta = self.motor_component.theta
                    v = VirtualADCComponent.sin_at_angle(theta, frequencies)
                    voltages.append(v)
                    await asyncio.sleep(1 / self.sample_rate)

                voltages = VirtualADCComponent.add_noise(voltages, noise_level=0.2)
                self.send_voltage(voltages)
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            logger.debug("stream_adc() cancelled")
        except Exception as e:
            logger.warning("stream_adc() raised an exception:", e)
        finally:
            ...  # Do some clean up
