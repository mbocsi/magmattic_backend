from . import ADCInterface
import asyncio
from collections import deque
import time
import json
import numpy as np
import math
import logging

logger = logging.getLogger(__name__ + ".NopADC")


class NopADC(ADCInterface):
    def __init__(self, q_data: asyncio.Queue, N: int = 16, M: int = 1000):
        self.q_data = q_data
        self.N = N
        self.M = M

    async def send_voltage(self, buffer: list[float]) -> None:
        await self.q_data.put(json.dumps({"type": "voltage", "val": buffer}))

    async def send_fft(self, data, T) -> None:
        Ntot = len(data)
        FFT = np.abs(np.fft.fft(data)) / Ntot
        V1 = FFT[0 : int(Ntot / 2 + 1)]
        V1[1:-2] = 2 * V1[1:-2]
        freq = 1 / T * np.linspace(0, int(Ntot / 2 + 1), int(Ntot / 2 + 1))

        await self.q_data.put(
            json.dumps({"type": "fft", "val": [[f, v] for f, v in zip(freq, V1)]})
        )

    @classmethod
    async def sin_stream(cls, angle, n):
        data = []
        for _ in range(n):
            angle = (angle + (0.003 * 2 * math.pi)) % (2 * math.pi)
            data.append(math.sin(angle) + math.sin((angle * 2)))
            await asyncio.sleep(0.001)
        return angle, data

    async def run(self) -> None:
        data = deque(maxlen=self.M)
        angle = 0
        while True:
            angle, values = await NopADC.sin_stream(angle, self.N)
            await self.send_voltage(values)
            data.extend(values)
            if len(data) >= self.M:
                T = 1
                await self.send_fft(data, T)
