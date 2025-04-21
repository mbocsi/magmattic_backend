import asyncio
import numpy as np
import logging

from . import BaseADCComponent
from motor import BaseMotorComponent

logger = logging.getLogger(__name__)

# Frequency-amplitude pairs for synthetic signal generation (Frequency is multiple of motor frequency)
# Ex. if motor frequency = 5Hz and element in this list is [2, 1] -> Actual frequency = 10hz and amplitude = 1
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
        """
        Simulated ADC component that generates synthetic voltage data based on motor angle.

        Args:
            pub_queue: Queue for publishing voltage data.
            sub_queue: Queue for receiving control commands.
            motor_component: Reference to the motor for retrieving current angle.
            addr: Simulated address (unused but required for interface consistency).
            pin: Simulated input pin.
            sample_rate: Sampling frequency in Hz.
            Nbuf: Number of samples per buffer.
        """
        super().__init__(pub_queue, sub_queue, addr, pin, sample_rate, Nbuf)
        self.motor_component = motor_component

    @classmethod
    def add_noise(cls, signal, noise_type="gaussian", noise_level=0.1) -> list[float]:
        """
        Adds synthetic noise to a clean signal.

        Args:
            signal (list[float]): Input signal.
            noise_type (str): Type of noise ('gaussian', 'uniform', 'salt_pepper').
            noise_level (float): Noise intensity as a fraction of signal std deviation.

        Returns:
            list[float]: Noisy signal.
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
        Computes the total voltage from multiple sinusoidal sources at a given angle.

        Args:
            theta (float): Motor angle in radians.
            frequencies (np.ndarray): Array of shape (N, 2) with frequency and amplitude.

        Returns:
            float: Instantaneous voltage value.
        """
        phase = (
            2 * np.pi * frequencies[:, 0] * theta / (2 * np.pi)
        )  # or just `frequencies[:, 0] * theta`
        signal = np.sum(frequencies[:, 1] * np.sin(phase))
        return signal

    async def stream_adc(self) -> None:
        """
        Simulates continuous ADC sampling based on motor position and synthetic signal model.
        Sends noisy voltage samples in chunks of `Nbuf` to the backend.
        """
        try:
            while True:
                voltages = []
                for _ in range(self.Nbuf):
                    theta = self.motor_component.theta  # Get current motor angle
                    v = VirtualADCComponent.sin_at_angle(theta, frequencies)
                    voltages.append(v)
                    await asyncio.sleep(1 / self.sample_rate)  # Wait between samples

                # Add noise and publish voltage buffer
                voltages = VirtualADCComponent.add_noise(voltages, noise_level=0.2)
                self.send_voltage(voltages)
                await asyncio.sleep(0)  # Yield control to event loop

        except asyncio.CancelledError:
            logger.debug("stream_adc() cancelled")
        except Exception as e:
            logger.warning(f"stream_adc() raised an exception: {e}")
        finally:
            ...  # Optional cleanup
